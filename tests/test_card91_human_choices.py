"""Card 91 permits the executing human to choose the Reserve Province."""

from copy import deepcopy

import pytest

from lod_ai import cli_utils
from lod_ai import rules_consts as C
from lod_ai.cards.effects.early_war import evt_091_indians_help
from lod_ai.engine import Engine
from lod_ai.event_choices import collect_event_choices
from lod_ai.state.setup_state import build_state


def _engine():
    state = build_state("1775", seed=91)
    for sid in ("Northwest", "Southwest", "Quebec", "Florida"):
        state["spaces"][sid].clear()
    state["spaces"]["Florida"][C.WARPARTY_U] = 3
    state["available"].update({C.WARPARTY_U: 10, C.VILLAGE: 5})
    engine = Engine(initial_state=state)
    engine.set_human_factions({C.INDIANS})
    return engine


def _collect(engine, shaded):
    class _Southwest:
        def prompt(self, label, menu):
            assert "Boston" not in menu["options"]
            assert "Southwest" in menu["options"]
            return str(menu["options"].index("Southwest") + 1)

    previous = cli_utils.get_input_provider()
    cli_utils.set_input_provider(_Southwest())
    try:
        return collect_event_choices(
            engine, C.INDIANS,
            {"id": 91, "title": "Indians Help British Outside Colonies"}, shaded)
    finally:
        cli_utils.set_input_provider(previous)


def test_unshaded_human_selects_reserve_instead_of_bot_protected_target():
    engine = _engine()
    bot_state = deepcopy(engine.state)
    evt_091_indians_help(bot_state)
    assert bot_state["spaces"]["Florida"][C.VILLAGE] == 1
    assert not bot_state["spaces"]["Southwest"].get(C.VILLAGE)

    engine.state.update(_collect(engine, False))
    evt_091_indians_help(engine.state)
    assert engine.state["spaces"]["Southwest"][C.VILLAGE] == 1
    assert engine.state["spaces"]["Southwest"][C.WARPARTY_U] == 2
    assert not engine.state["spaces"]["Southwest"].get(C.WARPARTY_A)
    assert engine.state["spaces"]["Florida"][C.WARPARTY_U] == 3
    assert not engine.state["spaces"]["Florida"].get(C.VILLAGE)


def test_shaded_human_removes_chosen_village_only():
    engine = _engine()
    for sid in ("Florida", "Southwest"):
        engine.state["spaces"][sid][C.VILLAGE] = 1
    villages_before = engine.state["available"][C.VILLAGE]
    engine.state.update(_collect(engine, True))
    evt_091_indians_help(engine.state, shaded=True)
    assert not engine.state["spaces"]["Southwest"].get(C.VILLAGE)
    assert engine.state["spaces"]["Florida"][C.VILLAGE] == 1
    assert engine.state["available"][C.VILLAGE] == villages_before + 1


@pytest.mark.parametrize("shaded", [False, True])
def test_invalid_reserve_target_preserves_nonplayer_default(shaded):
    state = _engine().state
    state["spaces"]["Southwest"][C.VILLAGE] = 1
    state["spaces"]["Florida"][C.VILLAGE] = 1
    expected = deepcopy(state)
    evt_091_indians_help(expected, shaded=shaded)
    state["card91_target"] = "Boston"
    evt_091_indians_help(state, shaded=shaded)
    assert state["spaces"] == expected["spaces"]
    assert state["available"] == expected["available"]
    assert state["rng"].getstate() == expected["rng"].getstate()


def test_shaded_does_not_offer_reserve_without_village():
    from lod_ai.event_choices import EVENT_CHOICES
    state = _engine().state
    state["spaces"]["Southwest"][C.VILLAGE] = 1
    shaded_step = next(step for step in EVENT_CHOICES[91] if step.side is True)
    assert shaded_step.options(state, C.INDIANS, {}) == [("Southwest", "Southwest")]
