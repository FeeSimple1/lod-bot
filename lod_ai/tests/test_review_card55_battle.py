"""Card 55 optional Battle retains §3.5.5 prerequisites under §5.3."""
import pytest

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.cards.effects.middle_war import evt_055_french_navy
from lod_ai.commands import battle
from lod_ai.state.setup_state import build_state


@pytest.mark.parametrize("scenario", ["1775", "1776"])
def test_pre_treaty_card55_preview_is_ineffective_without_an_error(scenario):
    state = build_state(scenario, seed=10000)
    bot = BaseBot()
    bot.faction = C.BRITISH
    assert bot._is_ineffective_event({"id": 55, "dual": True}, state)
    assert not state.get("_event_preview_error_log")


@pytest.mark.parametrize("requested", [None, True, False])
def test_pre_treaty_card55_resolves_without_attempting_french_battle(requested):
    state = build_state("1775", seed=1)
    if requested is not None:
        state["card55_do_battle"] = requested
    before = state["available"].get(C.REGULAR_FRE, 0)
    evt_055_french_navy(state)
    assert state["fni_level"] == 0
    assert state["available"].get(C.REGULAR_FRE, 0) == before
    assert all(sp.get(C.REGULAR_FRE, 0) == 0 for sp in state["spaces"].values())
    assert state.get("_turn_command") != battle.COMMAND_NAME


@pytest.mark.parametrize("french,british", [(0, 2), (2, 0), (0, 0)])
def test_card55_no_battle_without_both_sides_but_fni_still_lowers(french, british):
    state = build_state("1778", seed=1)
    for sp in state["spaces"].values():
        sp.pop(C.REGULAR_FRE, None)
    state["spaces"][C.WEST_INDIES_ID] = {C.REGULAR_FRE: french, C.REGULAR_BRI: british}
    state["fni_level"] = 2
    evt_055_french_navy(state)
    assert state["fni_level"] == 1
    assert state.get("_turn_command") != battle.COMMAND_NAME


@pytest.mark.parametrize("decline", [False, True])
def test_card55_post_treaty_relocation_enables_optional_free_battle(decline):
    state = build_state("1778", seed=1)
    for sp in state["spaces"].values():
        sp.pop(C.REGULAR_FRE, None)
    state["spaces"]["Georgia"][C.REGULAR_FRE] = 3
    state["spaces"][C.WEST_INDIES_ID] = {C.REGULAR_BRI: 2}
    state["fni_level"] = 2
    state["resources"][C.FRENCH] = 0
    state["card55_do_battle"] = not decline
    evt_055_french_navy(state)
    assert state["spaces"]["Georgia"].get(C.REGULAR_FRE, 0) == 0
    assert state["fni_level"] == 1
    assert (state.get("_turn_command") == battle.COMMAND_NAME) is not decline
    assert state["resources"][C.FRENCH] == 0
    if decline:
        assert state["spaces"][C.WEST_INDIES_ID][C.REGULAR_FRE] == 3


def test_card55_unshaded_lowers_fni_after_battle(monkeypatch):
    state = build_state("1778", seed=1)
    state["spaces"][C.WEST_INDIES_ID] = {C.REGULAR_BRI: 2, C.REGULAR_FRE: 2}
    state["fni_level"] = 2
    seen_fni = []
    monkeypatch.setattr(battle, "execute", lambda *args, **kwargs: seen_fni.append(args[0]["fni_level"]))

    evt_055_french_navy(state)

    assert seen_fni == [2]
    assert state["fni_level"] == 1


@pytest.mark.parametrize("french,british", [(0, 4), (2, 0), (2, 4)])
def test_card55_shaded_requires_both_sides_after_relocation(french, british, monkeypatch):
    state = build_state("1778", seed=1)
    state["spaces"] = {sid: {} for sid in state["spaces"]}
    state["spaces"]["Georgia"] = {C.REGULAR_BRI: british}
    state["spaces"][C.WEST_INDIES_ID] = {C.REGULAR_FRE: french}
    calls = []
    monkeypatch.setattr(battle, "execute", lambda *args, **kwargs: calls.append((args, kwargs)))

    evt_055_french_navy(state, shaded=True)

    assert state["spaces"]["Georgia"].get(C.REGULAR_BRI, 0) == 0
    assert state["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_BRI, 0) == british
    assert len(calls) == int(bool(french and british))
    if calls:
        assert calls[0][0][1] == C.BRITISH
        assert calls[0][1]["free"] is True
