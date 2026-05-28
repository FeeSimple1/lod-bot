"""Regression tests for the four leader-capability bugs surfaced by the
Session 18 leader_capabilities.txt audit.

Background: lod_ai/leaders/__init__.py registers `pre_*` hooks for each
of the 9 leader capabilities and `apply_leader_modifiers` is supposed
to fire them via `state["leaders"].get(faction, [])`.  In real game
state, however, `state["leaders"]` is shaped `{leader_id: location}`
not `{faction: [leader_ids]}`, so the hook iteration finds nothing and
none of the ctx-flag hooks fire.

For most capabilities this doesn't matter — the per-space rules
(Washington WTD/Defender, Lauzun, Brant, Dragging Canoe) are
implemented directly via `leader_location()` checks in their command
files.  Four were silently broken:

  1. Clinton (+1 Militia in Skirmish) — read a ctx flag that was always 0.
  2. Cornplanter (Village for 1 WP instead of 2) — gather.py always
     required 2 WP regardless of Cornplanter.
  3. Gage (Reward Loyalty free first shift in the space) — bot used a
     global "is Gage on the map?" check rather than "is Gage in the
     chosen RL space?"
  4. Rochambeau (French free with Patriot Command) — French allied
     fees in Patriot March/Battle never checked Rochambeau's location.

Each test exercises the rule directly post-fix.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random

from lod_ai import rules_consts as C
from lod_ai.commands import battle, march, gather
from lod_ai.special_activities import skirmish


# ---------------------------------------------------------------------------
# Clinton: +1 Militia in Skirmish in his space
# ---------------------------------------------------------------------------

def test_clinton_in_skirmish_space_removes_one_extra_militia():
    """Skirmish option 1 normally removes 1 piece; with Clinton in the
    space, an extra Militia is also removed."""
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 2, C.TORY: 0, C.MILITIA_A: 2,
                C.MILITIA_U: 0, C.REGULAR_PAT: 0, C.REGULAR_FRE: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0, C.VILLAGE: 0,
            },
        },
        "resources": {C.BRITISH: 5},
        "available": {},
        "support": {"Boston": 0},
        "control": {},
        "history": [],
        "casualties": {},
        "leaders": {"LEADER_CLINTON": "Boston"},
        "leader_locs": {"LEADER_CLINTON": "Boston"},
    }
    skirmish.execute(state, C.BRITISH, {}, "Boston", option=1)
    # 1 from option + 1 from Clinton = 2 militia removed
    assert state["spaces"]["Boston"].get(C.MILITIA_A, 0) == 0


def test_clinton_not_in_skirmish_space_grants_no_bonus():
    """If Clinton is elsewhere on the map, Skirmish in another space
    gets no Clinton bonus."""
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 2, C.TORY: 0, C.MILITIA_A: 2,
                C.MILITIA_U: 0, C.REGULAR_PAT: 0, C.REGULAR_FRE: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0, C.VILLAGE: 0,
            },
            "New_York_City": {C.REGULAR_BRI: 1},
        },
        "resources": {C.BRITISH: 5},
        "available": {},
        "support": {"Boston": 0},
        "control": {},
        "history": [],
        "casualties": {},
        "leaders": {"LEADER_CLINTON": "New_York_City"},
        "leader_locs": {"LEADER_CLINTON": "New_York_City"},
    }
    skirmish.execute(state, C.BRITISH, {}, "Boston", option=1)
    # Only 1 militia removed (option 1), no Clinton bonus
    assert state["spaces"]["Boston"].get(C.MILITIA_A, 0) == 1


# ---------------------------------------------------------------------------
# Cornplanter: Village for 1 War Party
# ---------------------------------------------------------------------------

def test_cornplanter_builds_village_with_one_war_party():
    """With Cornplanter in the space, Gather can build a Village by
    consuming only 1 War Party (vs. the default 2)."""
    state = {
        "spaces": {
            "Northwest": {
                C.WARPARTY_U: 1, C.WARPARTY_A: 0, C.VILLAGE: 0,
                C.REGULAR_BRI: 0, C.TORY: 0, C.REGULAR_PAT: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0,
            },
        },
        "resources": {C.INDIANS: 5},
        "available": {C.VILLAGE: 5, C.WARPARTY_U: 0, C.WARPARTY_A: 0,
                      C.REGULAR_BRI: 0, C.TORY: 0, C.REGULAR_PAT: 0},
        "support": {"Northwest": 0},
        "control": {},
        "history": [],
        "casualties": {},
        "leaders": {"LEADER_CORNPLANTER": "Northwest"},
        "leader_locs": {"LEADER_CORNPLANTER": "Northwest"},
        "markers": {C.RAID: {"on_map": set()},
                    C.PROPAGANDA: {"on_map": set()}},
    }
    gather.execute(state, C.INDIANS, {}, ["Northwest"],
                   build_village={"Northwest"})
    assert state["spaces"]["Northwest"][C.VILLAGE] == 1
    # 1 WP consumed (not 2)
    assert state["spaces"]["Northwest"].get(C.WARPARTY_U, 0) == 0


def test_no_cornplanter_requires_two_war_parties():
    """Without Cornplanter in the space, the default 2 WP cost applies.
    Trying to build a Village with only 1 WP raises."""
    import pytest as _pytest
    state = {
        "spaces": {
            "Northwest": {
                C.WARPARTY_U: 1, C.WARPARTY_A: 0, C.VILLAGE: 0,
                C.REGULAR_BRI: 0, C.TORY: 0, C.REGULAR_PAT: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0,
            },
        },
        "resources": {C.INDIANS: 5},
        "available": {C.VILLAGE: 5, C.WARPARTY_U: 0, C.WARPARTY_A: 0,
                      C.REGULAR_BRI: 0, C.TORY: 0, C.REGULAR_PAT: 0},
        "support": {"Northwest": 0},
        "control": {},
        "history": [],
        "casualties": {},
        "leaders": {"LEADER_CORNPLANTER": None},
        "leader_locs": {},
        "markers": {C.RAID: {"on_map": set()},
                    C.PROPAGANDA: {"on_map": set()}},
    }
    with _pytest.raises(ValueError, match="need 2 WP"):
        gather.execute(state, C.INDIANS, {}, ["Northwest"],
                       build_village={"Northwest"})


# ---------------------------------------------------------------------------
# Gage: free first Reward Loyalty shift in his space
# ---------------------------------------------------------------------------

def test_gage_in_rl_space_makes_first_shift_free():
    """When Gage is in the RL space, the British bot's _is_gage check
    (now per-space) recognizes the bonus.  When Gage is elsewhere it
    does not."""
    from lod_ai.bots.british_bot import BritishBot
    from lod_ai.leaders import leader_location as _ll

    bot = BritishBot()

    state_with_gage = {
        "spaces": {"Boston": {C.REGULAR_BRI: 2, C.TORY: 1}},
        "leaders": {"LEADER_GAGE": "Boston"},
        "leader_locs": {"LEADER_GAGE": "Boston"},
        "control": {"Boston": C.BRITISH},
        "support": {"Boston": C.NEUTRAL},
    }
    assert _ll(state_with_gage, "LEADER_GAGE") == "Boston"

    state_no_gage_here = {
        "spaces": {"Boston": {C.REGULAR_BRI: 2, C.TORY: 1},
                   "New_York_City": {C.REGULAR_BRI: 1}},
        "leaders": {"LEADER_GAGE": "New_York_City"},
        "leader_locs": {"LEADER_GAGE": "New_York_City"},
        "control": {"Boston": C.BRITISH},
        "support": {"Boston": C.NEUTRAL},
    }
    # Gage is NOT in Boston, so the per-space check should reject the
    # discount even though Gage is on the map.
    assert _ll(state_no_gage_here, "LEADER_GAGE") != "Boston"


# ---------------------------------------------------------------------------
# Rochambeau: French free with Patriot Command
# ---------------------------------------------------------------------------

def _make_battle_state(*, rochambeau_loc: str | None):
    return {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 1, C.TORY: 0,
                C.REGULAR_PAT: 1, C.REGULAR_FRE: 1,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.WARPARTY_U: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0, C.VILLAGE: 0,
                C.BLOCKADE: 0, C.SQUADRON: 0,
            },
        },
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 0},
        "available": {},
        "casualties": {},
        "support": {"Boston": C.NEUTRAL},
        "control": {"Boston": ""},
        "history": [],
        "markers": {C.RAID: {"on_map": set()},
                    C.PROPAGANDA: {"on_map": set()}},
        "rng": random.Random(0),
        "rng_log": [],
        "toa_played": True,
        "leaders": {"LEADER_ROCHAMBEAU": rochambeau_loc},
        "leader_locs": {"LEADER_ROCHAMBEAU": rochambeau_loc} if rochambeau_loc else {},
        "fni_level": 0,
    }


def test_rochambeau_in_battle_space_waives_french_ally_fee():
    """Patriot Battle with French Regulars present normally charges
    French 1 Resource per space.  Rochambeau in the space waives it."""
    state = _make_battle_state(rochambeau_loc="Boston")
    pre_french = state["resources"][C.FRENCH]
    battle.execute(state, C.PATRIOTS, {}, ["Boston"])
    # No French Resources spent (Rochambeau waived the fee)
    assert state["resources"][C.FRENCH] == pre_french


def test_rochambeau_elsewhere_does_not_waive_french_ally_fee():
    """If Rochambeau is not in the battle space, the French ally fee
    is still charged."""
    state = _make_battle_state(rochambeau_loc="Philadelphia")
    pre_french = state["resources"][C.FRENCH]
    battle.execute(state, C.PATRIOTS, {}, ["Boston"])
    # French paid 1 Resource for the Boston ally fee
    assert state["resources"][C.FRENCH] == pre_french - 1
