import pytest

from lod_ai.map.adjacency import is_adjacent, space_type
from lod_ai.map.control import refresh_control


def test_is_adjacent_lookup():
    assert is_adjacent("Boston", "Massachusetts")
    assert not is_adjacent("Boston", "New_York")


def test_space_type_lookup():
    assert space_type("Boston") == "City"
    assert space_type("Northwest") == "Reserve"
    assert space_type("Atlantis") is None


def test_refresh_control_assignment():
    state = {
        "spaces": {
            "A": {"Patriot_Militia_A": 2, "British_Regular": 1},
            "B": {"British_Regular": 2, "Patriot_Militia_A": 1},
            "C": {"Indian_WP_A": 3, "Patriot_Militia_A": 1},
        }
    }
    refresh_control(state)

    assert state["control"] == {"A": "REBELLION", "B": "BRITISH", "C": None}
    assert state["control_map"] == {"A": "REBELLION", "B": "BRITISH", "C": None}
