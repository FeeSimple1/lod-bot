"""The LLM bridge must stop/fail without silently executing another policy."""
import builtins
import json
import threading
import time

import pytest

from lod_ai import cli_utils, rules_consts as C
from lod_ai.commands import battle
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.tools import llm_playtest as trial


def _provider(tmp_path, **kwargs):
    engine = Engine(initial_state=build_state("1775", seed=1), use_cli=True)
    output = trial.OutputCapture(tmp_path / "cli_output.txt")
    provider = trial.FileDecisionProvider(engine, tmp_path, output, **kwargs)
    return provider, output


def test_transcript_keeps_exact_player_response_and_visible_cli(tmp_path):
    provider, output = _provider(tmp_path)
    output.write("Event text and actual legal choices\n")
    trial._write_json(tmp_path / "response.json", {
        "request_id": 1, "answer": "undo", "rationale": "Test recovery"})
    try:
        assert provider.prompt("Choose", {"kind": "select", "options": ["Pass"]}) == "undo"
        log = [json.loads(line) for line in (tmp_path / "transcript.jsonl").read_text().splitlines()]
        assert log[0]["cli_output"] == "Event text and actual legal choices\n"
        assert log[1]["rationale"] == "Test recovery"
        assert provider.decisions == 1
        assert not (tmp_path / "decision.json").exists()
    finally:
        output.close()


@pytest.mark.parametrize("response", [
    {"request_id": 99, "answer": "1"}, {"request_id": 1},
    {"request_id": 1, "answer": 1}, {"request_id": True, "answer": "1"},
    {"request_id": 1, "stop": "false", "answer": "1"}, [],
])
def test_bad_responses_fail_instead_of_substituting_a_choice(tmp_path, response):
    provider, output = _provider(tmp_path)
    trial._write_json(tmp_path / "response.json", response)
    try:
        with pytest.raises(trial.BridgeFailure):
            provider.prompt("Choose", {"kind": "select", "options": ["Pass"]})
        assert provider.decisions == 0
    finally:
        output.close()


def test_duplicate_consumed_response_waits_for_the_new_actual_answer(tmp_path):
    provider, output = _provider(tmp_path, timeout=2)
    trial._write_json(tmp_path / "response.json", {"request_id": 1, "answer": "1"})
    assert provider.prompt("Choose", {"kind": "select", "options": ["Pass"]}) == "1"
    trial._write_json(tmp_path / "response.json", {"request_id": 1, "answer": "1"})
    def current_answer():
        deadline = time.monotonic() + 1
        while "duplicate_response" not in (tmp_path / "transcript.jsonl").read_text():
            if time.monotonic() > deadline:
                return
            time.sleep(.01)
        trial._write_json(tmp_path / "response.json", {
            "request_id": 2, "answer": "2", "rationale": "The new player choice"})
    thread = threading.Thread(target=current_answer, daemon=True)
    thread.start()
    try:
        assert provider.prompt("Next", {"kind": "select", "options": ["Pass", "Event"]}) == "2"
        thread.join(timeout=1)
        assert provider.decisions == 2
        log = [json.loads(line) for line in (tmp_path / "transcript.jsonl").read_text().splitlines()]
        duplicate = next(entry for entry in log if entry["type"] == "duplicate_response")
        assert duplicate["request_id"] == 1 and duplicate["waiting_for"] == 2
        assert log[-1]["rationale"] == "The new player choice"
    finally:
        output.close()


def test_timeout_is_visible_not_an_automatic_first_option(tmp_path):
    provider, output = _provider(tmp_path, timeout=0.001)
    try:
        with pytest.raises(trial.BridgeFailure, match="player_timeout"):
            provider.prompt("Choose", {"kind": "select", "options": ["Pass"]})
        assert provider.decisions == 0
    finally:
        output.close()


def test_bare_pause_is_separate_from_player_decisions(tmp_path):
    provider, output = _provider(tmp_path)
    try:
        assert provider.prompt("[Press Enter to continue, or type a command] ", None) == ""
        assert provider.decisions == 0
        assert provider.automatic_pauses == 1
        assert not (tmp_path / "decision.json").exists()
    finally:
        output.close()


def test_bridge_restores_existing_global_hooks_even_on_stop(tmp_path):
    provider, output = _provider(tmp_path)
    previous = (builtins.input, cli_utils.get_input_provider(),
                cli_utils._game_state, cli_utils._engine_ref,
                cli_utils.get_undo_checkpoint(), battle._DEFENDER_ACTIVATION_HOOK,
                trial.cli._human_decider)
    try:
        with pytest.raises(trial.TrialStop):
            with trial._installed(provider.engine, provider):
                raise trial.TrialStop("player_stop")
        assert previous == (builtins.input, cli_utils.get_input_provider(),
                            cli_utils._game_state, cli_utils._engine_ref,
                            cli_utils.get_undo_checkpoint(), battle._DEFENDER_ACTIVATION_HOOK,
                            trial.cli._human_decider)
    finally:
        output.close()


def test_each_normal_human_turn_binds_the_correct_seat(tmp_path, monkeypatch):
    provider, output = _provider(tmp_path)
    seen = []
    def decider(faction, card, allowed, engine):
        seen.append(provider.current_faction)
        return faction
    monkeypatch.setattr(trial.cli, "_human_decider", decider)
    try:
        with trial._installed(provider.engine, provider):
            trial.cli._human_decider(C.BRITISH, {}, {}, provider.engine)
            trial.cli._human_decider(C.INDIANS, {}, {}, provider.engine)
        assert seen == [C.BRITISH, C.INDIANS]
        assert trial.cli._human_decider is decider
    finally:
        output.close()


@pytest.mark.parametrize("scenario,faction", [("1775", C.PATRIOTS), ("1778", C.FRENCH)])
def test_real_cli_player_stop_produces_valid_isolated_result(tmp_path, scenario, faction):
    directory = tmp_path / "trial"
    def player():
        deadline = time.monotonic() + 10
        while not (directory / "decision.json").exists():
            if time.monotonic() > deadline:
                return
            time.sleep(.01)
        request = json.loads((directory / "decision.json").read_text())
        trial._write_json(directory / "response.json", {
            "request_id": request["request_id"], "stop": True,
            "rationale": "End this infrastructure test at the first actual choice"})
    thread = threading.Thread(target=player, daemon=True)
    thread.start()
    result = trial.run_trial(directory, scenario=scenario, seed=1,
                             factions=(faction,), timeout=3)
    thread.join(timeout=1)
    assert result["stop_reason"] == "player_stop"
    assert result["decisions"] == 0
    assert result["state_valid"] and result["save_roundtrip"]
    assert result["clean"]
    assert (directory / "saves" / "autosave.json").exists()
    requests = [json.loads(line) for line in (directory / "transcript.jsonl").read_text().splitlines()
                if json.loads(line)["type"] == "request"]
    assert "Victory margins" in requests[0]["observation"]
    assert "One-player rules (8.8)" in requests[0]["observation"]
    assert json.loads((directory / "result.json").read_text()) == result


def test_existing_directory_is_rejected(tmp_path):
    (tmp_path / "response.json").write_text("stale")
    with pytest.raises(ValueError, match="empty trial directory"):
        trial.run_trial(tmp_path)
