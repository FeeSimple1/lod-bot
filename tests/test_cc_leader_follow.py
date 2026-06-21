"""Regression test: an Indian Leader follows War Parties that move out of its
space via a British Common-Cause March (previously the follow only fired on
Indian commands)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lod_ai import rules_consts as C
from lod_ai.leaders import leader_location
from lod_ai.map import adjacency as map_adj
from lod_ai.bots.indians import follow_indian_leaders_after_move


def test_indian_leader_follows_largest_wp_group_after_move():
    # Brant in 'A'; more War Parties end up in adjacent 'B' than remain in 'A'.
    loc = "Northwest"
    nbr = map_adj.adjacent_spaces(loc)[0]
    state = {
        "spaces": {
            loc: {C.WARPARTY_A: 1},
            nbr: {C.WARPARTY_A: 3},
        },
        "leaders": {"LEADER_BRANT": loc},
        "history": [],
    }
    follow_indian_leaders_after_move(state)
    assert leader_location(state, "LEADER_BRANT") == nbr


def test_indian_leader_stays_when_origin_has_largest_group():
    loc = "Northwest"
    nbr = map_adj.adjacent_spaces(loc)[0]
    state = {
        "spaces": {
            loc: {C.WARPARTY_A: 4},
            nbr: {C.WARPARTY_A: 1},
        },
        "leaders": {"LEADER_BRANT": loc},
        "history": [],
    }
    follow_indian_leaders_after_move(state)
    assert leader_location(state, "LEADER_BRANT") == loc


def test_no_leader_no_op():
    state = {"spaces": {"Northwest": {C.WARPARTY_A: 2}}, "leaders": {}, "history": []}
    follow_indian_leaders_after_move(state)  # must not raise


def test_british_cc_march_invokes_follow():
    """The British March calls the Indian leader-follow helper, gated on a
    Common-Cause March having been used."""
    import inspect
    import lod_ai.bots.british_bot as bb
    march_src = inspect.getsource(bb.BritishBot._march)
    assert "follow_indian_leaders_after_move" in march_src
    assert "if used_cc" in march_src
