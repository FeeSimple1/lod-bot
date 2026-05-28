"""Regression tests for the two leader-movement follow-up wirings.

After the initial OPS-wiring PR, two gaps remained:

  * British leaders followed Marches but not Garrisons.  Garrison can
    shift British Regulars between cities and the OPS rule applies to
    any movement.

  * Indians had `ops_leader_movement` (state-based, returns the
    destination space ID or None) defined and unit-tested but no
    code invoked it after the three Indian movement commands
    (March, Scout, Gather) or after Raid.

This file verifies the wiring.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.indians import IndianBot
from lod_ai import rules_consts as C


# ---------------------------------------------------------------------------
# British Garrison-induced leader movement
# ---------------------------------------------------------------------------

def test_follow_leaders_after_garrison_updates_state():
    """If New_York (leader's space) garrisons 5 Regulars to NYC, the
    leader follows to NYC (5 > the staying group)."""
    state = {
        "spaces": {
            "New_York": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
            "New_York_City": {C.REGULAR_BRI: 5, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
        "history": [],
    }
    move_map = {"New_York": {"New_York_City": 5}}
    bot = BritishBot()
    bot._follow_leaders_after_garrison(state, move_map)
    assert state["leaders"]["LEADER_HOWE"] == "New_York_City"


def test_follow_leaders_after_garrison_no_move_if_leader_not_origin():
    """Garrison from a non-leader space leaves the leader put."""
    state = {
        "spaces": {
            "New_York": {C.REGULAR_BRI: 2, C.TORY: 0, "adj": []},
            "Philadelphia": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
            "Boston": {C.REGULAR_BRI: 4, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
        "history": [],
    }
    move_map = {"Philadelphia": {"Boston": 4}}
    bot = BritishBot()
    bot._follow_leaders_after_garrison(state, move_map)
    assert state["leaders"]["LEADER_HOWE"] == "New_York"


def test_follow_leaders_after_garrison_no_op_when_no_leaders_on_map():
    """All three British leaders off-map: nothing to do, no error."""
    state = {
        "spaces": {"New_York": {C.REGULAR_BRI: 3, C.TORY: 0, "adj": []}},
        "leaders": {"LEADER_GAGE": None, "LEADER_HOWE": None,
                    "LEADER_CLINTON": None},
        "history": [],
    }
    bot = BritishBot()
    # Must not raise.
    bot._follow_leaders_after_garrison(state, {"New_York": {"Boston": 3}})


# ---------------------------------------------------------------------------
# Indian leader movement
# ---------------------------------------------------------------------------

def test_follow_indian_leaders_after_move_updates_state():
    """Brant in Quebec, Northwest adjacent has more War Parties post-march
    -> Brant follows to Northwest."""
    state = {
        "spaces": {
            "Quebec": {C.WARPARTY_U: 1, C.WARPARTY_A: 0,
                       "adj": ["Quebec_City", "Northwest"]},
            "Northwest": {C.WARPARTY_U: 5, C.WARPARTY_A: 0,
                          "adj": ["Quebec"]},
            "Quebec_City": {"adj": []},
        },
        # Use the leader_locs structure since ops_leader_movement supports it
        "leader_locs": {"LEADER_BRANT": "Quebec"},
        "leaders": {"LEADER_BRANT": "Quebec"},
        "history": [],
    }
    bot = IndianBot()
    bot._follow_leaders_after_move(state)
    assert state["leader_locs"]["LEADER_BRANT"] == "Northwest"
    assert state["leaders"]["LEADER_BRANT"] == "Northwest"


def test_follow_indian_leaders_keeps_leader_when_origin_largest():
    """If Brant's origin has the largest WP group, Brant stays put."""
    state = {
        "spaces": {
            "Quebec": {C.WARPARTY_U: 6, C.WARPARTY_A: 0, "adj": ["Northwest"]},
            "Northwest": {C.WARPARTY_U: 2, C.WARPARTY_A: 0, "adj": ["Quebec"]},
        },
        "leader_locs": {"LEADER_BRANT": "Quebec"},
        "leaders": {"LEADER_BRANT": "Quebec"},
        "history": [],
    }
    bot = IndianBot()
    bot._follow_leaders_after_move(state)
    assert state["leader_locs"]["LEADER_BRANT"] == "Quebec"


def test_follow_indian_leaders_handles_off_map_leaders():
    """Leaders not on the map are skipped, no error raised."""
    state = {
        "spaces": {"Quebec": {C.WARPARTY_U: 0, "adj": []}},
        "leader_locs": {"LEADER_BRANT": None,
                        "LEADER_CORNPLANTER": None,
                        "LEADER_DRAGGING_CANOE": None},
        "leaders": {},
        "history": [],
    }
    bot = IndianBot()
    bot._follow_leaders_after_move(state)  # must not raise


def test_follow_indian_leaders_handles_three_leaders_independently():
    """Each Indian leader (Brant, Cornplanter, Dragging Canoe) is
    evaluated independently against its own origin space."""
    state = {
        "spaces": {
            "Quebec": {C.WARPARTY_U: 1, C.WARPARTY_A: 0, "adj": ["Northwest"]},
            "Northwest": {C.WARPARTY_U: 4, C.WARPARTY_A: 0,
                          "adj": ["Quebec", "Southwest"]},
            "Southwest": {C.WARPARTY_U: 3, C.WARPARTY_A: 0,
                          "adj": ["Northwest"]},
        },
        # Brant in Quebec: should follow to Northwest (1 < 4)
        # Cornplanter in Southwest: stays (3 > 4? no - 4 wins; should move to NW)
        # Dragging Canoe in Northwest: stays (4 > both neighbors)
        "leader_locs": {"LEADER_BRANT": "Quebec",
                        "LEADER_CORNPLANTER": "Southwest",
                        "LEADER_DRAGGING_CANOE": "Northwest"},
        "leaders": {"LEADER_BRANT": "Quebec",
                    "LEADER_CORNPLANTER": "Southwest",
                    "LEADER_DRAGGING_CANOE": "Northwest"},
        "history": [],
    }
    bot = IndianBot()
    bot._follow_leaders_after_move(state)
    assert state["leader_locs"]["LEADER_BRANT"] == "Northwest"
    assert state["leader_locs"]["LEADER_CORNPLANTER"] == "Northwest"
    assert state["leader_locs"]["LEADER_DRAGGING_CANOE"] == "Northwest"
