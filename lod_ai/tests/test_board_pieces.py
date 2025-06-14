import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.board.pieces import (
    move_piece,
    add_piece,
    remove_piece,
    place_with_caps,
    return_leaders,
)
from lod_ai.util.history import last_entry
from lod_ai import rules_consts as C


def blank_state():
    return {
        "spaces": {"A": {}, "B": {}},
        "available": {},
        "history": [],
        "casualties": {},
    }


def test_move_piece_updates_locations_and_history():
    state = blank_state()
    state["spaces"]["A"][C.REGULAR_BRI] = 2

    moved = move_piece(state, C.REGULAR_BRI, "A", "B", 1)

    assert moved == 1
    assert state["spaces"]["A"].get(C.REGULAR_BRI) == 1
    assert state["spaces"]["B"][C.REGULAR_BRI] == 1
    assert last_entry(state) == "1\xd7British_Regular  A \u2192 B"


def test_add_piece_from_available_with_history():
    state = blank_state()
    state["available"][C.REGULAR_BRI] = 2

    placed = add_piece(state, C.REGULAR_BRI, "A", 1)

    assert placed == 1
    assert state["available"].get(C.REGULAR_BRI) == 1
    assert state["spaces"]["A"][C.REGULAR_BRI] == 1
    assert last_entry(state) == "1\xd7British_Regular  available \u2192 A"


def test_remove_piece_specific_location():
    state = blank_state()
    state["spaces"]["A"][C.REGULAR_BRI] = 1

    removed = remove_piece(state, C.REGULAR_BRI, "A", 1)

    assert removed == 1
    assert C.REGULAR_BRI not in state["spaces"]["A"]
    assert state["available"][C.REGULAR_BRI] == 1
    assert last_entry(state) == "1\xd7British_Regular  A \u2192 available"


def test_place_with_caps_respects_limit_and_logs():
    state = blank_state()
    # fill to cap for British forts
    for i in range(C.MAX_FORT_BRI):
        state["spaces"][f"S{i}"] = {C.FORT_BRI: 1}

    result = place_with_caps(state, C.FORT_BRI, "A", 1)

    assert result == 0
    assert last_entry(state) == f"(\u26d4 cap reached: {C.FORT_BRI} {C.MAX_FORT_BRI})"


def test_return_leaders_moves_all_and_logs():
    state = blank_state()
    # place two leaders on the map
    for leader in C.LEADERS[:2]:
        state["spaces"]["A"][leader] = 1

    return_leaders(state)

    for leader in C.LEADERS[:2]:
        assert leader not in state["spaces"]["A"]
        assert state["available"][leader] == 1
    assert last_entry(state) == "Leaders returned to Available (2)"
