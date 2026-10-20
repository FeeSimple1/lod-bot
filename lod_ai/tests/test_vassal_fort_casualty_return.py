"""§1.6.4: all casualty Forts return immediately without losing CBC/CRC."""
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.pieces import add_piece, lift_casualties, remove_piece
from lod_ai.commands import battle
from lod_ai.special_activities import skirmish, war_path


def _state(spaces):
    return {
        "spaces": spaces, "available": {}, "casualties": {},
        "unavailable": {}, "support": {}, "control": {}, "leaders": {},
        "resources": {faction: 10 for faction in
                      (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "toa_played": True, "history": [], "rng": random.Random(1),
        "cbc": 4, "crc": 7,
    }


@pytest.mark.parametrize("fort,counter,other", [
    (C.FORT_BRI, "cbc", "crc"), (C.FORT_PAT, "crc", "cbc"),
])
@pytest.mark.parametrize("location", ["Boston", None])
def test_casualty_fort_can_be_built_again_before_winter_quarters(fort, counter, other, location):
    """A requested casualty has one cumulative loss and no Reset delay."""
    state = _state({"Boston": {fort: 1}, "Georgia": {}})
    before, other_before = state[counter], state[other]

    assert remove_piece(state, fort, location, 3, to="casualties") == 1

    assert state["available"][fort] == 1
    assert state["casualties"].get(fort, 0) == 0
    assert state[counter] == before + 1
    assert state[other] == other_before
    # No Reset, pool transfer, or voluntary map-pull is required.
    assert add_piece(state, fort, "Georgia", 1) == 1
    assert state["spaces"]["Georgia"][fort] == 1
    assert state[counter] == before + 1
    lift_casualties(state)
    assert state[counter] == before + 1


@pytest.mark.parametrize("fort,counter", [(C.FORT_BRI, "cbc"), (C.FORT_PAT, "crc")])
def test_map_wide_fort_casualties_count_only_actual_removals(fort, counter):
    state = _state({"Boston": {fort: 2}, "Georgia": {fort: 1}})
    before = state[counter]

    assert remove_piece(state, fort, None, 5, to="casualties") == 3

    assert state["available"][fort] == 3
    assert state["casualties"].get(fort, 0) == 0
    assert state[counter] == before + 3


@pytest.mark.parametrize("fort,counter", [(C.FORT_BRI, "cbc"), (C.FORT_PAT, "crc")])
def test_noncasualty_fort_return_does_not_record_a_loss(fort, counter):
    state = _state({"Boston": {fort: 1}})
    before = state[counter]
    remove_piece(state, fort, "Boston", 1, to="available")
    assert state["available"][fort] == 1
    assert state[counter] == before


@pytest.mark.parametrize("faction,own_tag,fort,fort_counter,unit_counter", [
    (C.BRITISH, C.REGULAR_BRI, C.FORT_PAT, "crc", "cbc"),
    (C.PATRIOTS, C.REGULAR_PAT, C.FORT_BRI, "cbc", "crc"),
    (C.FRENCH, C.REGULAR_FRE, C.FORT_BRI, "cbc", "crc"),
])
def test_skirmish_fort_returns_but_own_cube_stays_in_casualties(
        faction, own_tag, fort, fort_counter, unit_counter):
    """§§4.2.2/4.3.3/4.5.2 option 3: Fort bounces; cube waits for Reset."""
    state = _state({"Boston": {own_tag: 1, fort: 1}})
    fort_before, unit_before = state[fort_counter], state[unit_counter]

    skirmish.execute(state, faction, {}, "Boston", option=3)

    assert state["available"][fort] == 1
    assert state["casualties"].get(fort, 0) == 0
    assert state["casualties"][own_tag] == 1
    assert state["available"].get(own_tag, 0) == 0
    assert state[fort_counter] == fort_before + 1
    assert state[unit_counter] == unit_before + 1


def test_war_path_fort_casualty_counts_once_and_returns_immediately():
    state = _state({"Pennsylvania": {C.WARPARTY_U: 2, C.FORT_PAT: 1}})
    war_path.execute(state, C.INDIANS, {}, "Pennsylvania", option=3)
    assert state["available"][C.FORT_PAT] == 1
    assert state["casualties"].get(C.FORT_PAT, 0) == 0
    assert state["crc"] == 8
    assert state["cbc"] == 4


def test_battle_existing_explicit_fort_counter_is_not_doubled(monkeypatch):
    """Battle's existing Available-plus-counter path remains one loss."""
    state = _state({"Boston": {C.REGULAR_PAT: 9, C.FORT_BRI: 1}})
    monkeypatch.setattr(battle, "_roll_d3", lambda state: 3)

    battle.execute(state, C.PATRIOTS, {}, ["Boston"], free=True)

    assert state["spaces"]["Boston"].get(C.FORT_BRI, 0) == 0
    assert state["available"][C.FORT_BRI] == 1
    assert state["casualties"].get(C.FORT_BRI, 0) == 0
    assert state["cbc"] == 5
