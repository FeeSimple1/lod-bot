"""Card 1's printed target choice belongs to the player, not bot priorities."""

from copy import deepcopy

import pytest

from lod_ai import cli_utils
from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.cards.effects.late_war import evt_001_waxhaws
from lod_ai.engine import Engine
from lod_ai.event_choices import collect_event_choices
from lod_ai.state.setup_state import build_state


def _engine():
    state = build_state("1778", seed=1)
    for space in state["spaces"].values():
        for tag in Engine._CROWN_SIDE + Engine._REBEL_SIDE:
            space.pop(tag, None)
    state["spaces"]["Boston"].update({C.TORY: 1, C.REGULAR_PAT: 2})
    state["spaces"]["Norfolk"].update({C.REGULAR_BRI: 1, C.REGULAR_PAT: 2})
    state["support"].update({"Boston": C.ACTIVE_SUPPORT, "Norfolk": C.NEUTRAL})
    refresh_control(state)
    return Engine(initial_state=state)


class _BostonTarget:
    def __init__(self):
        self.menus = []

    def prompt(self, label, menu):
        self.menus.append(deepcopy(menu))
        return str(menu["options"].index("Boston") + 1)


def test_unshaded_human_can_select_target_that_bot_does_not_prefer():
    """Printed 'one space with British' includes Tory-only Boston."""
    engine = _engine()
    engine.set_human_factions({C.BRITISH})
    bot_state = deepcopy(engine.state)
    evt_001_waxhaws(bot_state)
    assert bot_state["spaces"]["Boston"][C.REGULAR_PAT] == 2
    assert bot_state["spaces"]["Norfolk"].get(C.REGULAR_PAT, 0) == 0

    provider = _BostonTarget()
    previous = cli_utils.get_input_provider()
    cli_utils.set_input_provider(provider)
    try:
        overrides = collect_event_choices(
            engine, C.BRITISH, {"id": 1, "title": "Waxhaws Massacre"}, False)
    finally:
        cli_utils.set_input_provider(previous)
    assert overrides == {"card1_target": "Boston"}
    assert provider.menus[0]["options"] == ["Boston", "Norfolk"]
    engine.state.update(overrides)
    evt_001_waxhaws(engine.state)

    assert engine.state["spaces"]["Boston"].get(C.REGULAR_PAT, 0) == 0
    assert engine.state["spaces"]["Norfolk"][C.REGULAR_PAT] == 2
    assert engine.state["support"]["Norfolk"] == C.NEUTRAL
    assert engine.state["casualties"][C.REGULAR_PAT] == 2
    assert engine.state["markers"][C.PROPAGANDA]["on_map"] == {"Boston": 2}


@pytest.mark.parametrize("invalid_target", ["Massachusetts", "not_a_space"])
def test_unshaded_rejects_target_without_british_and_retains_bot_default(invalid_target):
    state = _engine().state
    expected = deepcopy(state)
    evt_001_waxhaws(expected)
    state["card1_target"] = invalid_target
    evt_001_waxhaws(state)
    state.pop("card1_target")
    assert state["spaces"] == expected["spaces"]
    assert state["support"] == expected["support"]
    assert state["markers"] == expected["markers"]
    assert state["rng"].getstate() == expected["rng"].getstate()


def test_shaded_human_chooses_march_pieces_and_battle_in_event_target():
    """The printed free Commands use human choices and precede the aftermath."""
    engine = _engine()
    state = engine.state
    state["spaces"]["Boston"].pop(C.REGULAR_PAT)
    state["spaces"]["Massachusetts"][C.REGULAR_PAT] = 6
    state["support"]["Boston"] = C.PASSIVE_SUPPORT
    state["resources"][C.PATRIOTS] = 0
    engine.set_human_factions({C.PATRIOTS})
    refresh_control(state)
    menus = []

    class _Player:
        def prompt(self, label, menu):
            prompt = menu["prompt"]
            menus.append(deepcopy(menu))
            if "destination space" in prompt:
                return str(menu["options"].index("Boston") + 1)
            if prompt == "Bring escorts?":
                return "1"
            if "Select March destinations:" in prompt or "Select Battle spaces:" in prompt:
                assert menu["options"] == ["Boston"]
                return "1"
            if "Select origins marching to Boston:" in prompt:
                return "1" if menu["options"] else "0"
            if "Move how many" in prompt and C.REGULAR_PAT in prompt:
                return "2"
            raise AssertionError(f"Unexpected prompt: {menu!r}")

    previous = cli_utils.get_input_provider()
    cli_utils.set_input_provider(_Player())
    try:
        overrides = collect_event_choices(
            engine, C.PATRIOTS, {"id": 1, "title": "Waxhaws Massacre"}, True)
        state.update(overrides)
        evt_001_waxhaws(state, shaded=True)
        assert state["free_ops"] == [
            (C.PATRIOTS, "march", "Boston"),
            (C.PATRIOTS, "battle", "Boston"),
        ]
        assert not state["markers"][C.PROPAGANDA]["on_map"]
        engine._drain_free_ops(state, card_id=1)
    finally:
        cli_utils.set_input_provider(previous)

    assert state["spaces"]["Massachusetts"][C.REGULAR_PAT] == 4
    assert state["spaces"]["Norfolk"][C.REGULAR_PAT] == 2
    assert state["resources"][C.PATRIOTS] == 0
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Boston": 2}
    assert state["support"]["Boston"] == C.NEUTRAL
    assert any("Select Battle spaces:" in menu["prompt"] for menu in menus)
    assert not state.get("_free_op_error_log")
    assert not state.get("free_op_followups")
