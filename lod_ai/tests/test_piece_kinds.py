import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai import rules_consts as C
from lod_ai.commands import battle, raid
from lod_ai.util import piece_kinds


def test_cube_and_loss_classification():
    assert piece_kinds.is_cube(C.REGULAR_BRI)
    assert piece_kinds.is_cube(C.REGULAR_PAT)
    assert piece_kinds.is_cube(C.REGULAR_FRE)
    assert piece_kinds.is_cube(C.TORY)
    assert not piece_kinds.is_cube(C.MILITIA_A)
    assert not piece_kinds.is_cube(C.WARPARTY_U)

    assert piece_kinds.loss_value(C.REGULAR_BRI) == 2
    assert piece_kinds.loss_value(C.REGULAR_FRE) == 2
    assert piece_kinds.loss_value(C.REGULAR_PAT) == 2
    assert piece_kinds.loss_value(C.FORT_BRI) == 2
    assert piece_kinds.loss_value(C.TORY) == 1
    assert piece_kinds.loss_value(C.MILITIA_U) == 1


def test_washington_doubles_win_the_day(monkeypatch):
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 1,
                C.TORY: 1,
                C.REGULAR_PAT: 3,
            }
        },
        "support": {"Boston": C.NEUTRAL},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "casualties": {},
        "markers": {},
        "rng": random.Random(1),
        "leaders": {"LEADER_WASHINGTON": "Boston"},
    }

    monkeypatch.setattr(battle, "_roll_d3", lambda st: 3)
    battle.execute(state, C.PATRIOTS, {}, ["Boston"])

    # §3.6.8: Rebellion wins → shifts toward Opposition. Washington doubles
    # the shift.  NEUTRAL(0) with 2 shifts → ACTIVE_OPPOSITION(-2).
    assert state["support"]["Boston"] == C.ACTIVE_OPPOSITION


def _raid_state():
    return {
        "spaces": {
            "Virginia": {},
            "North_Carolina": {},
            "South_Carolina": {},
            "Georgia": {},
        },
        "support": {
            "Virginia": C.NEUTRAL,
            "North_Carolina": C.NEUTRAL,
            "South_Carolina": C.PASSIVE_OPPOSITION,
            "Georgia": C.PASSIVE_OPPOSITION,
        },
        "resources": {C.INDIANS: 3},
        "available": {},
        "casualties": {},
        "markers": {C.RAID: {"pool": 3, "on_map": set()}},
        "rng": random.Random(2),
        "leaders": {"LEADER_DRAGGING_CANOE": "Virginia"},
    }


def test_dragging_canoe_allows_distance_two_move():
    state = _raid_state()
    state["spaces"]["Virginia"][C.WARPARTY_U] = 1

    raid.execute(state, "INDIANS", {}, ["South_Carolina"], move_plan=[("Virginia", "South_Carolina")])

    assert state["spaces"]["South_Carolina"].get(C.WARPARTY_A, 0) == 1


def test_non_dragging_canoe_source_still_adjacent_only():
    state = _raid_state()
    state["spaces"]["North_Carolina"][C.WARPARTY_U] = 1
    state["spaces"]["South_Carolina"][C.WARPARTY_U] = 1  # keeps Raid valid without the move

    with pytest.raises(ValueError):
        raid.execute(state, "INDIANS", {}, ["Georgia"], move_plan=[("North_Carolina", "Georgia")])
