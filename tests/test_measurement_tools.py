"""Statistics and smoke gates must describe what the engine actually did."""
from copy import deepcopy
import json

import pytest

from lod_ai import rules_consts as C
from lod_ai.tools import batch_smoke as batch
from lod_ai.tools import clean_sweep_gate, soak, invariants
from lod_ai.tools.run_diagnostics import collect_runtime_diagnostics, result_is_clean


def _state():
    return {"spaces": {"Boston": {}, "New_York_City": {}, "Virginia": {}},
            "support": {"Boston": C.ACTIVE_SUPPORT, "New_York_City": C.ACTIVE_OPPOSITION,
                        "Virginia": C.PASSIVE_SUPPORT},
            "markers": {C.BLOCKADE: {"pool": 0, "on_map": {"Boston", "New_York_City"}}},
            "resources": {f: 5 for f in batch.FACTIONS}, "history": [],
            "toa_played": False}


def _result(**updates):
    result = {"scenario": "1775", "seed": 1, "winner": C.BRITISH,
              "end_reason": "WINNER", "cards_played": 5, "error": None,
              "traceback": None, "diagnostics": {}, "large_data": {"victory_type": "final_scoring"}}
    result.update(collect_runtime_diagnostics({}))
    result.update(updates)
    return result


def _fake_engine(monkeypatch, mutate=None, card=None):
    class Engine:
        def __init__(self, initial_state, **kwargs):
            self.state = initial_state
            self.draws = 0

        def set_human_factions(self, factions):
            pass

        def draw_card(self):
            self.draws += 1
            return (card or {"id": 1}) if self.draws == 1 else None

        def play_card(self, card, **kwargs):
            self.state["victory_result"] = {"type": "final_scoring", "outcome": "victory",
                                            "winner": C.BRITISH, "margins": {C.BRITISH: 3}}
            if mutate:
                mutate(self.state)
    monkeypatch.setattr(batch, "build_state", lambda *a, **k: _state())
    monkeypatch.setattr(batch, "Engine", Engine)


def test_blockade_reduces_only_support_in_report_snapshot():
    state = _state()
    assert batch._support_opposition_totals(state) == (2, 4)
    snapshot = batch._capture_wq_snapshot(state, 1)
    assert (snapshot["support_total"], snapshot["opposition_total"]) == (2, 4)


@pytest.mark.parametrize("ending", ["victory_check", "final_scoring"])
def test_wq_snapshot_precedes_phase_changes_even_on_terminal_card(monkeypatch, ending):
    def resolve(state):
        state["support"]["Virginia"] = C.ACTIVE_OPPOSITION
        state["resources"][C.BRITISH] = 20
        state["victory_result"]["type"] = ending

    _fake_engine(monkeypatch, resolve, card={"id": 97, "winter_quarters": True})
    result = batch.run_one_game("1775", 1, detailed=True)
    assert result["end_reason"] == "WINNER"
    snapshot, = result["large_data"]["wq_snapshots"]
    assert snapshot["phase"] == "before_resolution"
    assert (snapshot["support_total"], snapshot["opposition_total"]) == (2, 4)
    assert snapshot["resources"][C.BRITISH] == 5
    assert result["diagnostics"]["final_resources"][C.BRITISH] == 20


def test_wq_margin_sum_tie_order_is_explicit_and_consistent(capsys):
    snapshot = {"margins": {"BRI": [-1, 0], "PAT": [-1, 0],
                            "FRE": [2, 3], "IND": [2, 3]}}
    assert batch._margin_sum_leader(snapshot) == "IND"
    batch._print_game_dynamics([], {})
    output = capsys.readouterr().out
    assert "before WQ resolution" in output
    assert "ties use BRI, PAT, IND, FRE order" in output
    assert "closest to victory" not in output


def test_treaty_timing_uses_state_not_history_phrase():
    diag = batch._empty_diagnostics()
    state = _state()
    history = [{"msg": "Treaty of Alliance not yet played"},
               {"msg": "French may arrange Treaty of Alliance"}]
    batch._scan_history_for_events(diag, history, 0, 3)
    batch._record_treaty_status(diag, state, 3)
    batch._finalize_diagnostics(diag, state)
    assert diag["treaty_played"] is False
    assert diag["treaty_card_number"] is None
    state["toa_played"] = True
    batch._record_treaty_status(diag, state, 7)
    batch._record_treaty_status(diag, state, 8)
    assert diag["treaty_card_number"] == 7
    initial = batch._empty_diagnostics()
    batch._record_treaty_status(initial, state, 0)
    assert initial["treaty_card_number"] == 0


def test_battle_commands_and_space_battles_are_distinct_and_losses_unchanged():
    data = batch._empty_large_data()
    history = [{"msg": message} for message in [
        f"{C.BRITISH} BATTLE in Boston, New_York_City",
        "BATTLE Boston: ROYALIST-loss=1, REBELLION-loss=3, winner=ROYALIST",
        "BATTLE New_York_City: ROYALIST-loss=4, REBELLION-loss=2, winner=REBELLION",
    ]]
    offset = batch._scan_history_large(data, history, 0, 1)
    batch._scan_history_large(data, history, offset, 2)
    assert data["battle_commands_total"] == 1
    assert data["battle_commands_by_faction"][C.BRITISH] == 1
    assert data["battles_total"] == 2
    assert data["battles_as_attacker"][C.BRITISH] == 2
    assert data["battle_losses"] == {"ROYALIST": 5, "REBELLION": 5}


def test_structured_victory_is_authoritative_for_winner_and_finish():
    state = _state()
    state["history"] = [{"msg": f"Winner: {C.INDIANS}"}]
    state["victory_result"] = {"outcome": "victory", "type": "final_scoring",
                               "winner": C.FRENCH, "margins": {C.FRENCH: 9}}
    assert batch._check_game_over(state) == C.FRENCH
    data = batch._empty_large_data()
    batch._determine_victory_detail(data, state, 3, "1778", C.FRENCH, "WINNER")
    assert data["victory_type"] == "final_scoring"
    assert data["final_scores"] == {C.FRENCH: 9}
    state["victory_result"] = {"outcome": "stalemate", "winner": None}
    assert batch._check_game_over(state) is None


@pytest.mark.parametrize("key,entry,count_key", [
    ("_bot_error_log", {"exception_message": "failed"}, "bot_error_count"),
    ("_illegal_action_log", {"illegal_reason": "special_forbidden"}, "illegal_action_count"),
    ("_free_op_error_log", {"operation": "march", "message": "failed"}, "free_op_error_count"),
    ("_event_preview_error_log", {"card_id": 5, "message": "failed"}, "event_preview_error_count"),
])
def test_completed_winner_with_engine_error_is_dirty(monkeypatch, key, entry, count_key):
    _fake_engine(monkeypatch, lambda state: state.update({key: [entry]}))
    result = batch.run_one_game("1775", 1, detailed=True)
    assert result["end_reason"] == "WINNER"
    assert result["winner"] == C.BRITISH
    assert result[count_key] == 1
    assert result["clean"] is False
    assert not result_is_clean(result)


def test_failed_invariant_retains_resolved_card_count(monkeypatch):
    _fake_engine(monkeypatch)
    monkeypatch.setattr(invariants, "capture_baseline", lambda state: {})

    def fail(*args, **kwargs):
        raise invariants.InvariantError("fixture failure")
    monkeypatch.setattr(invariants, "check_all", fail)
    result = batch.run_one_game("1775", 1, detailed=True, check_invariants=True)
    assert result["end_reason"] == "INVARIANT"
    assert result["cards_played"] == result["large_data"]["total_cards"] == 1
    assert not result["clean"]


def test_winners_table_counts_invariant_as_error_and_labels_flagged_win(capsys):
    results = [_result(end_reason="INVARIANT", winner=None),
               _result(bot_error_count=1, clean=False)]
    grouped = {s: results if s == "1775" else [] for s in batch.SCENARIOS}
    batch._print_winners_table(results, grouped)
    output = capsys.readouterr().out
    assert "Completed wins with recorded flags: 1" in output
    assert "Errors" in output
    assert "Unresolved" not in output


def test_large_json_serialization_does_not_mutate_live_statistics():
    original = [_result(large_data={"final_scores": {C.FRENCH: float("-inf")}})]
    before = deepcopy(original)
    serialized = batch._serialize_large_results(original)
    assert serialized[0]["large_data"]["final_scores"][C.FRENCH] is None
    assert original == before


@pytest.mark.parametrize("flag", ["bot_error_count", "illegal_action_count", "free_op_error_count", "free_op_skip_count", "event_preview_error_count"])
def test_repro_cli_fails_completed_but_dirty_game(monkeypatch, flag):
    monkeypatch.setattr(batch.sys, "argv", ["batch_smoke", "--repro", "1775:1"])
    monkeypatch.setattr(batch, "run_one_game", lambda *a, **k: _result(**{flag: 1}))
    assert batch.main() == 1


def test_large_mode_honors_invariants(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(batch.sys, "argv", ["batch_smoke", "--large", "--invariants"])
    monkeypatch.setattr(batch, "LARGE_SEEDS_PER_SCENARIO", 1)
    monkeypatch.setattr(batch, "LARGE_RESULTS_PATH", tmp_path / "large.json")

    def run(scenario, seed, **kwargs):
        calls.append(kwargs)
        return _result(scenario=scenario, seed=seed)
    monkeypatch.setattr(batch, "run_one_game", run)
    assert batch.main() == 0
    assert len(calls) == 3
    assert all(call["check_invariants"] for call in calls)


def test_clean_sweep_reads_rejected_action_log_without_history_text(monkeypatch):
    _fake_engine(monkeypatch, lambda state: state.update({
        "_illegal_action_log": [{"illegal_reason": "special_forbidden"}]}))
    errors, illegal, skips, failures, cards = clean_sweep_gate.play("1775", 1, check_invariants=False)
    assert not errors and not skips and not failures
    assert cards == 1
    assert illegal == [{"illegal_reason": "special_forbidden"}]


def test_clean_sweep_rejects_event_preview_failure(monkeypatch):
    _fake_engine(monkeypatch, lambda state: state.update({
        "_event_preview_error_log": [{"card_id": 5, "message": "failed"}]}))
    errors, illegal, skips, failures, cards = clean_sweep_gate.play("1775", 1, check_invariants=False)
    assert not errors and not illegal and not skips
    assert any("Event preview failed" in message for message in failures)


@pytest.mark.parametrize("end_reason", ["TIMEOUT", "DECK_EXHAUSTED", "INVARIANT", "CRASH", "INTERACTIVE_PROMPT"])
def test_clean_sweep_rejects_incomplete_run(monkeypatch, end_reason):
    monkeypatch.setattr(clean_sweep_gate, "run_one_game", lambda *a, **k:
                        _result(end_reason=end_reason, winner=None))
    assert clean_sweep_gate.main(["--scenarios", "1775", "--seeds", "1"]) == 1


@pytest.mark.parametrize("previous", [
    _result(clean=False, illegal_action_count=1),
    _result(end_reason="DIRTY"),
    _result(end_reason="TIMEOUT", winner=None),
    _result(free_op_error_count=1),
    _result(event_preview_error_count=1),
])
def test_resumed_soak_retains_prior_failures(monkeypatch, tmp_path, previous):
    out = tmp_path / "soak.jsonl"
    out.write_text(json.dumps(previous) + "\n")
    monkeypatch.setattr(soak, "run_one_game", lambda *a, **k: pytest.fail("must not replay completed rows"))
    assert soak.main(["--games", "1", "--out", str(out)]) == 1


def test_soak_persists_hidden_operation_errors(monkeypatch, tmp_path):
    out = tmp_path / "soak.jsonl"
    monkeypatch.setattr(soak, "run_one_game", lambda *a, **k:
                        _result(free_op_error_count=1, free_op_errors=[{"message": "failed"}]))
    assert soak.main(["--games", "1", "--out", str(out)]) == 1
    row = json.loads(out.read_text())
    assert row["end_reason"] == "WINNER"
    assert row["clean"] is False
    assert row["free_op_error_count"] == 1


def test_contingent_event_observations_survive_reports_without_becoming_errors(monkeypatch, tmp_path):
    observation = {"faction": C.FRENCH, "card": 5, "d_before": -4,
                   "d_after": -2, "battle_dice": 2, "complete": True}
    _fake_engine(monkeypatch, lambda state: state.update({
        "event_outcome_observations": [observation]}))
    result = batch.run_one_game("1775", 1, detailed=True)
    assert result["event_outcome_observations"] == [observation]
    assert result["event_outcome_observation_count"] == 1
    assert result["clean"] is True
    assert result["event_outcome_observations"][0] is not observation
    out = tmp_path / "observations.jsonl"
    monkeypatch.setattr(soak, "run_one_game", lambda *a, **k: result)
    assert soak.main(["--games", "1", "--out", str(out)]) == 0
    row = json.loads(out.read_text())
    assert row["event_outcome_observations"] == [observation]
    assert row["event_outcome_observation_count"] == 1
