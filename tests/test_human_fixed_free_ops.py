"""Event-pinned free Commands still belong to the receiving human (§5.1/5.3)."""
from copy import deepcopy

import pytest

from lod_ai import cli_utils as U
from lod_ai import interactive_cli as cli
from lod_ai import rules_consts as C
from lod_ai.board.pieces import add_piece
from lod_ai.cards.effects.late_war import evt_094_herkimer
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.util.free_ops import queue_free_op


@pytest.fixture(autouse=True)
def reset_provider():
    previous = U.get_input_provider()
    yield
    U.set_input_provider(previous)


class Answers:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.menus = []

    def prompt(self, label, menu):
        self.menus.append(deepcopy(menu))
        return next(self.answers)


def engine_for(*factions):
    engine = Engine(initial_state=build_state("1776", seed=21))
    engine.set_human_factions(set(factions))
    return engine


def test_card94_humans_choose_village_and_tory_in_pinned_province():
    """Printed94: free Gather/Muster in New York; do not auto-place a WP/no-op."""
    engine = engine_for(C.INDIANS, C.BRITISH)
    state = engine.state
    resources = dict(state["resources"])
    # Gather New York -> build Village; Muster New York -> no Regulars,
    # one Tory, no Fort/Reward Loyalty.
    provider = Answers(["1", "2", "1", "1", "1", "1"])
    U.set_input_provider(provider)
    evt_094_herkimer(state)
    engine._drain_free_ops(state, 94)
    assert state["spaces"]["New_York"][C.VILLAGE] == 1
    assert state["spaces"]["New_York"].get(C.WARPARTY_U, 0) == 0
    assert state["spaces"]["New_York"][C.TORY] == 4
    assert state["spaces"]["New_York"][C.REGULAR_BRI] == 3
    assert state["resources"] == resources
    assert not state.get("_free_op_error_log")
    target_menus = [m for m in provider.menus
                   if m["prompt"].startswith(("Select Gather", "Select Muster"))]
    assert len(target_menus) == 2
    assert all(m["options"] == ["New_York"] for m in target_menus)


def test_fixed_march_uses_human_origin_and_piece_counts():
    engine = engine_for(C.PATRIOTS)
    state = engine.state
    original = state["spaces"]["New_York"][C.REGULAR_PAT]

    class MarchChoices:
        picked_origin = False

        def prompt(self, label, menu):
            prompt = menu["prompt"]
            if prompt.startswith("Bring escorts"):
                return "1"
            if prompt.startswith("Select March destinations"):
                assert menu["options"] == ["New_York"]
                return "1"
            if prompt.startswith("Select origins"):
                if self.picked_origin:
                    return "0"
                self.picked_origin = True
                return str(menu["options"].index("Massachusetts") + 1)
            if C.REGULAR_PAT in prompt:
                return "1"
            return "0"  # Keep the Massachusetts Militia in place.

    U.set_input_provider(MarchChoices())
    queue_free_op(state, C.PATRIOTS, "march", "New_York")
    engine._drain_free_ops(state, 1)
    assert state["spaces"]["New_York"][C.REGULAR_PAT] == original + 1
    assert state["spaces"]["Massachusetts"].get(C.REGULAR_PAT, 0) == 0
    assert state["spaces"]["Massachusetts"][C.MILITIA_U] == 1
    assert not state.get("_free_op_error_log")


def test_pinned_bonus_battle_preserves_activation_choice_and_bonus(monkeypatch):
    engine = engine_for(C.PATRIOTS)
    state = engine.state
    add_piece(state, C.MILITIA_U, "New_York", 2)
    provider = Answers(["1", "2"])
    U.set_input_provider(provider)
    calls = []
    real_battle = cli.battle.execute

    def capture(*args, **kwargs):
        calls.append(kwargs)
        return real_battle(*args, **kwargs)

    monkeypatch.setattr(cli.battle, "execute", capture)
    resources = dict(state["resources"])
    queue_free_op(state, C.PATRIOTS, "battle_plus2", "New_York")
    engine._drain_free_ops(state, 66)
    assert len(calls) == 1
    assert calls[0]["spaces"] == ["New_York"]
    assert calls[0]["activate"] == {"New_York": 2}
    assert calls[0]["choices"] == {"force_bonus": 2}
    assert state["_battle_commands_executed"] == 1
    assert state["resources"] == resources
    assert provider.menus[0]["options"] == ["New_York"]
    assert not state.get("_free_op_error_log")


def test_treaty_pinned_west_indies_muster_prompts_french_human():
    engine = engine_for(C.FRENCH)
    state = engine.state
    state["toa_played"] = True
    state["available"][C.REGULAR_FRE] = 6
    before = state["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_FRE, 0)
    provider = Answers(["1", "4"])
    U.set_input_provider(provider)
    queue_free_op(state, C.FRENCH, "muster", C.WEST_INDIES_ID)
    engine._drain_free_ops(state, 110)
    assert state["spaces"][C.WEST_INDIES_ID][C.REGULAR_FRE] == before + 4
    assert provider.menus[0]["options"] == [C.WEST_INDIES_ID]
    assert not state.get("_free_op_error_log")


def test_pinned_rally_respects_human_placement_choice():
    engine = engine_for(C.PATRIOTS)
    state = engine.state
    before = state["spaces"]["New_York"].get(C.MILITIA_U, 0)
    resources = dict(state["resources"])
    provider = Answers(["1", "1"])
    U.set_input_provider(provider)
    queue_free_op(state, C.PATRIOTS, "rally", "New_York")
    engine._drain_free_ops(state, 39)
    assert state["spaces"]["New_York"][C.MILITIA_U] == before + 1
    assert state["resources"] == resources
    assert provider.menus[0]["options"] == ["New_York"]
    assert not state.get("_free_op_error_log")


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_failed_human_free_command_rolls_back_and_reports_without_fallback(
        monkeypatch, error_type):
    engine = engine_for(C.INDIANS)
    state = engine.state
    resources = deepcopy(state["resources"])
    U.set_input_provider(Answers([]))

    def bad_wizard(*args, **kwargs):
        def runner(state, ctx):
            state["resources"][C.BRITISH] -= 1
            raise error_type("controlled command failure")
        return runner

    monkeypatch.setattr(cli, "_gather_wizard", bad_wizard)
    monkeypatch.setattr(engine.dispatcher, "execute", lambda *a, **k:
                        pytest.fail("must not replace a failed human plan"))
    queue_free_op(state, C.INDIANS, "gather", "New_York")
    engine._drain_free_ops(state, 94)
    assert state["resources"] == resources
    assert state["_free_op_error_log"] == [{
        "faction": C.INDIANS, "operation": "gather", "location": "New_York",
        "card_id": 94, "error_type": error_type.__name__,
        "message": "controlled command failure",
    }]
    assert "bs_free" not in state


def test_no_legal_pinned_gather_declines_without_prompt_or_default(monkeypatch):
    engine = engine_for(C.INDIANS)
    state = engine.state
    state["support"]["New_York"] = C.ACTIVE_SUPPORT
    U.set_input_provider(Answers([]))
    monkeypatch.setattr(engine.dispatcher, "execute", lambda *a, **k:
                        pytest.fail("illegal fixed target must not fall back"))
    queue_free_op(state, C.INDIANS, "gather", "New_York")
    engine._drain_free_ops(state, 94)
    assert not state.get("_free_op_error_log")
    assert any("no legal target" in h.get("msg", "") for h in state["history"])
