"""Card 14: free operations retain prerequisites and resolve possible parts."""
import pytest

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.cards.effects.middle_war import evt_014_overmountain_men
from lod_ai.commands import battle
from lod_ai.state.setup_state import build_state


def _state(destination, origin=None):
    state = build_state("1775", seed=10284)
    state["spaces"] = {sid: {} for sid in state["spaces"]}
    state["spaces"]["North_Carolina"] = dict(destination)
    state["spaces"]["Virginia"] = dict(origin or {})
    state["card14_dest"] = "North_Carolina"
    state["card14_src"] = "Virginia"
    state["card14_op"] = "MARCH"
    return state


@pytest.mark.parametrize("preexisting", [0, 1])
def test_card14_fort_only_requires_two_underground_war_parties(preexisting):
    state = _state({C.FORT_PAT: 1, C.WARPARTY_U: preexisting}, {C.WARPARTY_U: 1})
    state["card14_followup"] = "WAR_PATH"

    evt_014_overmountain_men(state)

    destination = state["spaces"]["North_Carolina"]
    assert state["spaces"]["Virginia"].get(C.WARPARTY_U, 0) == 0
    assert destination.get(C.FORT_PAT, 0) == 1 - preexisting
    assert destination.get(C.WARPARTY_U, 0) == 1 - preexisting
    assert destination.get(C.WARPARTY_A, 0) == preexisting
    assert bool(state.get("_turn_used_special")) == bool(preexisting)
    assert state["resources"][C.INDIANS] == 0


def test_card14_fort_only_preview_does_not_raise_or_record_error():
    state = _state({C.FORT_PAT: 1}, {C.WARPARTY_U: 1})
    bot = BaseBot()
    bot.faction = C.INDIANS

    bot._is_ineffective_event({"id": 14, "dual": True}, state)

    assert not state.get("_event_preview_error_log")
    assert state["spaces"]["Virginia"][C.WARPARTY_U] == 1


def test_card14_war_path_removes_maximum_units_in_destination():
    state = _state({C.MILITIA_U: 2, C.WARPARTY_U: 1}, {C.WARPARTY_U: 1})
    state["card14_followup"] = "WAR_PATH"
    evt_014_overmountain_men(state)
    destination = state["spaces"]["North_Carolina"]
    assert destination.get(C.MILITIA_U, 0) == 0
    assert destination.get(C.WARPARTY_U, 0) == 0
    assert destination.get(C.WARPARTY_A, 0) == 1


def test_card14_war_path_can_resolve_without_an_available_first_move():
    state = _state({C.FORT_PAT: 1, C.WARPARTY_U: 2})
    evt_014_overmountain_men(state)
    assert state["spaces"]["North_Carolina"].get(C.FORT_PAT, 0) == 0
    assert state["_turn_special_type"] == "WAR_PATH"


@pytest.mark.parametrize("shaded", [False, True])
def test_card14_battle_can_resolve_without_an_available_first_move(shaded, monkeypatch):
    state = _state({C.REGULAR_PAT: 2, C.REGULAR_BRI: 2})
    state["card14_followup"] = "BRITISH_BATTLE"
    calls = []
    monkeypatch.setattr(battle, "execute", lambda *args, **kwargs: calls.append((args, kwargs)))
    evt_014_overmountain_men(state, shaded=shaded)
    assert len(calls) == 1
    assert calls[0][0][1] == (C.PATRIOTS if shaded else C.BRITISH)
    assert calls[0][1]["spaces"] == ["North_Carolina"]
    assert calls[0][1]["free"] is True


@pytest.mark.parametrize("shaded,origin", [(False, {C.WARPARTY_U: 1}),
                                          (True, {C.REGULAR_PAT: 1})])
def test_card14_keeps_march_when_no_battle_is_legal(shaded, origin, monkeypatch):
    state = _state({}, origin)
    state["card14_followup"] = "BRITISH_BATTLE"
    calls = []
    monkeypatch.setattr(battle, "execute", lambda *args, **kwargs: calls.append(args))
    evt_014_overmountain_men(state, shaded=shaded)
    assert not calls
    tag = next(iter(origin))
    assert state["spaces"]["North_Carolina"].get(tag) == 1
    assert state["spaces"]["Virginia"].get(tag, 0) == 0


def test_card14_cannot_choose_an_unprinted_destination():
    state = _state({}, {C.WARPARTY_U: 1})
    state["card14_dest"] = "Georgia"
    evt_014_overmountain_men(state)
    assert state["spaces"]["Georgia"].get(C.WARPARTY_U, 0) == 0
    assert state["spaces"]["North_Carolina"].get(C.WARPARTY_U) == 1
