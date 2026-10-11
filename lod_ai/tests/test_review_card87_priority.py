"""Card 87: §8.3.5 faction choice followed by §8.1.2 piece removal."""

import pytest

from lod_ai import rules_consts as C
from lod_ai.cards.effects.late_war import evt_087_lenape


def _state(executor, pieces):
    return {
        "active": executor,
        "spaces": {"Pennsylvania": dict(pieces)},
        "available": {},
        "unavailable": {},
        "casualties": {},
    }


@pytest.mark.parametrize("executor,pieces,removed", [
    (C.BRITISH, {C.FORT_PAT: 1, C.MILITIA_U: 1}, C.FORT_PAT),
    (C.PATRIOTS, {C.FORT_BRI: 1, C.REGULAR_BRI: 1}, C.FORT_BRI),
    (C.PATRIOTS, {C.VILLAGE: 1, C.WARPARTY_U: 1}, C.VILLAGE),
    (C.BRITISH, {C.MILITIA_U: 1, C.MILITIA_A: 1,
                 C.REGULAR_PAT: 1}, C.MILITIA_U),
    (C.PATRIOTS, {C.WARPARTY_U: 1, C.WARPARTY_A: 1}, C.WARPARTY_U),
    (C.PATRIOTS, {C.REGULAR_BRI: 3, C.TORY: 1}, C.TORY),
    (C.PATRIOTS, {C.REGULAR_BRI: 1, C.TORY: 3}, C.REGULAR_BRI),
    (C.PATRIOTS, {C.REGULAR_BRI: 2, C.TORY: 2}, C.REGULAR_BRI),
    (C.PATRIOTS, {C.TORY: 1}, C.TORY),
])
def test_enemy_piece_priority(executor, pieces, removed):
    state = _state(executor, pieces)

    evt_087_lenape(state)

    assert state["available"] == {removed: 1}
    assert sum(state["spaces"]["Pennsylvania"].values()) == sum(pieces.values()) - 1
    assert executor in state["remain_eligible"]


@pytest.mark.parametrize("executor,pieces,removed", [
    (C.INDIANS, {C.FORT_BRI: 1, C.REGULAR_BRI: 1, C.TORY: 3}, C.TORY),
    (C.INDIANS, {C.REGULAR_BRI: 2, C.TORY: 1}, C.REGULAR_BRI),
    (C.INDIANS, {C.REGULAR_BRI: 2, C.TORY: 2}, C.REGULAR_BRI),
    (C.FRENCH, {C.REGULAR_PAT: 2, C.MILITIA_U: 1,
                C.MILITIA_A: 1, C.FORT_PAT: 1}, C.REGULAR_PAT),
    (C.FRENCH, {C.REGULAR_PAT: 1, C.MILITIA_U: 1,
                C.MILITIA_A: 1, C.FORT_PAT: 1}, C.MILITIA_A),
    (C.FRENCH, {C.REGULAR_PAT: 1, C.FORT_PAT: 1}, C.FORT_PAT),
    (C.INDIANS, {C.TORY: 1, C.FORT_BRI: 1}, C.FORT_BRI),
    (C.FRENCH, {C.REGULAR_PAT: 1}, C.REGULAR_PAT),
    (C.INDIANS, {C.TORY: 1}, C.TORY),
    (C.FRENCH, {C.MILITIA_U: 1, C.MILITIA_A: 1, C.FORT_PAT: 1}, C.MILITIA_A),
    (C.BRITISH, {C.WARPARTY_U: 1, C.WARPARTY_A: 1,
                 C.VILLAGE: 1}, C.WARPARTY_A),
])
def test_friendly_fallback_piece_priority(executor, pieces, removed):
    state = _state(executor, pieces)

    evt_087_lenape(state)

    expected = dict(pieces)
    expected[removed] -= 1
    assert {tag: n for tag, n in state["spaces"]["Pennsylvania"].items() if n} == {
        tag: n for tag, n in expected.items() if n}
    assert executor in state["remain_eligible"]


def test_human_enemy_faction_priority_precedes_piece_priority():
    state = _state(C.BRITISH, {C.FORT_PAT: 1, C.REGULAR_FRE: 1})
    state["human_factions"] = {C.FRENCH}

    evt_087_lenape(state)

    assert state["available"] == {C.REGULAR_FRE: 1}
    assert state["spaces"]["Pennsylvania"][C.FORT_PAT] == 1


def test_friendly_fallback_harms_ally_before_self():
    state = _state(C.BRITISH, {C.FORT_BRI: 1, C.REGULAR_BRI: 1, C.VILLAGE: 1})

    evt_087_lenape(state)

    assert state["available"] == {C.VILLAGE: 1}
    assert state["spaces"]["Pennsylvania"][C.REGULAR_BRI] == 1


def test_explicit_player_choice_overrides_bot_piece_priority():
    state = _state(C.BRITISH, {C.FORT_PAT: 1, C.MILITIA_U: 1})
    state["card87_piece"] = C.MILITIA_U

    evt_087_lenape(state)

    assert state["available"] == {C.MILITIA_U: 1}
    assert state["spaces"]["Pennsylvania"][C.FORT_PAT] == 1


def test_empty_pennsylvania_still_grants_eligibility():
    state = _state(C.INDIANS, {})

    evt_087_lenape(state)

    assert state["available"] == {}
    assert state["remain_eligible"] == {C.INDIANS}
