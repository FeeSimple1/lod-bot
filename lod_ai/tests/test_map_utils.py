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


def test_refresh_control_villages_count_as_indian():
    """Villages are Indian pieces (§1.6.5) and must count toward Royalist side for control."""
    state = {
        "spaces": {
            # 2 rebels vs 1 WP + 1 Village = 2 Royalist -> no control (Indians only, no British)
            "SC": {"Patriot_Militia_A": 2, "Indian_WP_A": 1, "Village": 1},
            # 1 rebel vs 1 British + 1 Village = 2 Royalist -> BRITISH control
            "NY": {"Patriot_Militia_A": 1, "British_Regular": 1, "Village": 1},
            # Village alone shouldn't give British control (no British piece)
            "WI": {"Village": 2, "Patriot_Militia_A": 1},
        }
    }
    refresh_control(state)

    # SC: 2 vs 2 with no British piece -> None
    assert state["control"]["SC"] is None
    # NY: 1 vs 2 with British piece -> BRITISH
    assert state["control"]["NY"] == "BRITISH"
    # WI: 1 vs 2 but no British piece -> None (Indians-only rule)
    assert state["control"]["WI"] is None
