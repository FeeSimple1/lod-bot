"""Source-backed regressions for the October 2026 Patriot/French review."""

from copy import deepcopy
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.bots.french import FrenchBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.special_activities import partisans


def _state(spaces, *, support=None):
    state = {
        "spaces": spaces,
        "resources": {f: 5 for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "available": {},
        "casualties": {},
        "support": support or {},
        "control": {},
        "leaders": {},
        "history": [],
        "rng": random.Random(1),
        "toa_played": True,
    }
    refresh_control(state)
    return state


@pytest.mark.parametrize("base", [C.VILLAGE, C.FORT_BRI])
def test_patriot_battles_exposed_royalist_base(base):
    """§1.4.3/§8.5.1: Active enemy bases qualify without defending units."""
    state = _state({"New_York": {C.REGULAR_PAT: 4, base: 1}})
    bot = PatriotBot()

    assert bot._battle_possible(state)
    assert bot._execute_battle(state)

    assert "New_York" in state["_turn_battle_spaces"]
    assert state["resources"][C.PATRIOTS] == 4


def test_patriot_battle_gate_counts_royalist_bases():
    """Two cubes do not outnumber one enemy cube plus one Active Fort."""
    state = _state({"New_York": {
        C.REGULAR_PAT: 2, C.REGULAR_BRI: 1, C.FORT_BRI: 1,
    }})
    assert not PatriotBot()._battle_possible(state)


def test_french_march_does_not_spend_source_control_on_escorts():
    """§8.6.5: French plus Continental departures must retain Control."""
    state = _state({
        "New_York": {C.REGULAR_FRE: 1, C.REGULAR_PAT: 1},
        "Massachusetts": {C.REGULAR_BRI: 1},
    })

    assert not FrenchBot()._march(state)

    assert state["control"]["New_York"] == "REBELLION"
    assert state["spaces"]["New_York"].get(C.REGULAR_FRE) == 1
    assert state["spaces"]["New_York"].get(C.REGULAR_PAT) == 1
    assert state["resources"][C.FRENCH] == 5


def test_french_march_keeps_legal_continental_escort():
    state = _state({
        "New_York": {C.REGULAR_FRE: 1, C.REGULAR_PAT: 2},
        "Massachusetts": {C.REGULAR_BRI: 1},
    })

    assert FrenchBot()._march(state)

    assert state["control"]["New_York"] == "REBELLION"
    assert state["control"]["Massachusetts"] == "REBELLION"
    assert state["spaces"]["New_York"].get(C.REGULAR_PAT) == 1
    assert state["spaces"]["Massachusetts"].get(C.REGULAR_PAT) == 1


@pytest.mark.parametrize("fort", [False, True])
def test_patriot_march_does_not_leave_french_in_place_of_patriot(fort):
    """§8.5.4: a French Regular cannot satisfy a Patriot leave-behind."""
    origin = {C.REGULAR_PAT: 1, C.REGULAR_FRE: 4}
    if fort:
        origin[C.FORT_PAT] = 1
    state = _state({
        "New_York": origin,
        "Massachusetts": {C.REGULAR_BRI: 1},
    })

    assert not PatriotBot()._execute_march(state)

    assert state["spaces"]["New_York"].get(C.REGULAR_PAT) == 1


def test_patriot_march_moves_surplus_while_retaining_active_guard():
    state = _state({
        "New_York": {C.REGULAR_PAT: 2, C.REGULAR_FRE: 4, C.FORT_PAT: 1},
        "Massachusetts": {C.REGULAR_BRI: 1},
    })

    assert PatriotBot()._execute_march(state)

    assert state["spaces"]["New_York"].get(C.REGULAR_PAT) == 1
    assert state["spaces"]["Massachusetts"].get(C.REGULAR_PAT) == 1
    assert state["spaces"]["Massachusetts"].get(C.REGULAR_FRE) == 1


@pytest.mark.parametrize("option,enemy,remaining", [
    (2, {C.WARPARTY_U: 2, C.TORY: 2}, {C.WARPARTY_U: 0, C.TORY: 2}),
    (2, {C.WARPARTY_U: 1, C.WARPARTY_A: 2, C.TORY: 1},
     {C.WARPARTY_U: 0, C.WARPARTY_A: 1, C.TORY: 1}),
    (2, {C.REGULAR_BRI: 2, C.TORY: 2}, {C.REGULAR_BRI: 1, C.TORY: 1}),
    (1, {C.REGULAR_BRI: 3, C.TORY: 1}, {C.REGULAR_BRI: 3, C.TORY: 0}),
    (1, {C.REGULAR_BRI: 1, C.TORY: 3}, {C.REGULAR_BRI: 0, C.TORY: 3}),
])
def test_partisans_nonplayer_removal_priorities(option, enemy, remaining):
    """§8.5.1/§8.1.2: Underground WP, Active WP, then alternating cubes."""
    state = _state({"New_York": {C.MILITIA_U: 2, **enemy}})

    partisans.execute(state, C.PATRIOTS, {}, "New_York", option=option)

    for tag, count in remaining.items():
        assert state["spaces"]["New_York"].get(tag, 0) == count


def test_partisans_player_can_select_british_cube_instead_of_war_party():
    """§4.1: explicit player choice overrides non-player priorities."""
    state = _state({"New_York": {C.MILITIA_U: 1, C.WARPARTY_U: 1, C.TORY: 1}})

    partisans.execute(state, C.PATRIOTS, {}, "New_York", option=1,
                      remove_plan={C.TORY: 1})

    assert state["spaces"]["New_York"].get(C.WARPARTY_U) == 1
    assert state["spaces"]["New_York"].get(C.TORY, 0) == 0
    assert state["casualties"].get(C.TORY) == 1


@pytest.mark.parametrize("plan", [
    {C.TORY: 2}, {C.TORY: -1}, {C.FORT_BRI: 1}, {C.TORY: True}, {},
])
def test_invalid_partisans_player_choices_do_not_mutate_state(plan):
    state = _state({"New_York": {C.MILITIA_U: 2, C.TORY: 1, C.FORT_BRI: 1}})
    state.pop("rng")
    before = deepcopy(state)

    with pytest.raises(ValueError):
        partisans.execute(state, C.PATRIOTS, {}, "New_York", option=1,
                          remove_plan=plan)

    assert state == before
