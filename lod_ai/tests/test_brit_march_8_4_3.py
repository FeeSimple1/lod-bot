"""British March destination rules (§8.4.3 / B10) — Session 39.

Covers the survey British #3 March remnants: the Population 1-2 limit,
the already-selected-destination preference (was inverted), the removal
of the tier-2 catch-all (only the two destination profiles in the rule
qualify), the Common-Cause Tory double-count (group counts, not space
totals), Phase 1 multi-group accumulation with the add-Control goal,
and the §3.2.3 one-Militia-per-three-cubes activation in march-in-place
(the flip-all bug is pinned in test_british_march_in_place.py).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai.bots.british_bot import BritishBot
from lod_ai import rules_consts as C


def _state(spaces, support=None, control=None, resources=10):
    s = {
        "spaces": spaces,
        "resources": {C.BRITISH: resources, C.PATRIOTS: 0, C.FRENCH: 0,
                      C.INDIANS: 0},
        "available": {},
        "unavailable": {},
        "casualties": {},
        "support": support or {},
        "control": control or {},
        "markers": {},
        "leaders": {},
        "rng": random.Random(7),
        "history": [],
        "fni_level": 0,
        "_turn_affected_spaces": set(),
        "_turn_used_special": False,
    }
    return s


class TestMarchPhase2DestinationRules:
    def test_tier2_catch_all_removed(self):
        """§8.4.3 lists exactly two Phase 2 destination profiles ("add
        Tories where Regulars are the only British units", "add Regulars
        where Tories are the only British units").  A Pop 1-2 space with
        mixed British units — or none at all — is NOT a March
        destination (the old tier-2 admitted every Pop 1+ space)."""
        state = _state(
            spaces={
                "Boston": {C.REGULAR_BRI: 4},
                # mixed British units -> neither profile
                "Massachusetts": {C.REGULAR_BRI: 1, C.TORY: 1},
            },
            support={"Boston": 0, "Massachusetts": 0},
            control={"Boston": C.BRITISH, "Massachusetts": C.BRITISH},
        )
        state["_no_special"] = True
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert not ok, "no legal §8.4.3 destination — March must decline"
        assert state["spaces"]["Massachusetts"].get(C.REGULAR_BRI, 0) == 1

    def test_pop_zero_space_excluded(self):
        """§8.4.3: Phase 2 destinations are "spaces with Population one
        or two" — a Pop 0 space is excluded even when it matches a
        destination profile."""
        state = _state(
            spaces={
                "Virginia": {C.REGULAR_BRI: 3, C.TORY: 3},
                "Southwest": {C.REGULAR_BRI: 1},  # Reserve, Pop 0, regs-only
            },
            support={"Virginia": 0, "Southwest": 0},
            control={"Virginia": C.BRITISH, "Southwest": None},
        )
        state["_no_special"] = True
        bot = BritishBot()
        bot._march(state, tried_muster=True)
        assert state["spaces"]["Southwest"].get(C.TORY, 0) == 0
        assert state["spaces"]["Southwest"].get(C.REGULAR_BRI, 0) == 1

    def test_already_selected_destination_preferred(self):
        """§8.4.3: "within each, move first to March destinations
        already selected above" — the old code EXCLUDED already-selected
        destinations from Phase 2.  A Phase 1 destination that ends up
        Regulars-only is topped up with Tories in preference to a fresh
        space, and re-using it consumes no new destination slot."""
        state = _state(
            spaces={
                "New_York_City": {C.MILITIA_A: 1},          # Phase 1 target
                "New_York": {C.REGULAR_BRI: 4},              # regs-only origin
                "New_Jersey": {C.REGULAR_BRI: 2, C.TORY: 2}, # tory-bearing origin
            },
            support={"New_York_City": 0, "New_York": 0, "New_Jersey": 0},
            control={"New_York_City": "REBELLION",
                     "New_York": C.BRITISH, "New_Jersey": C.BRITISH},
        )
        state["_no_special"] = True
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert ok
        nyc = state["spaces"]["New_York_City"]
        # Phase 1 flipped NYC with New_York's Regulars; Phase 2 preferred
        # the already-selected NYC (tier 0: add Tories where Regulars are
        # the only British units) over the fresh New_York colony.
        assert nyc.get(C.TORY, 0) >= 1, "Tories should top up the Phase 1 dest"
        assert state.get("control", {}).get("New_York_City") == C.BRITISH
        # New_Jersey's group went to NYC, not to the New_York colony.
        assert state["spaces"]["New_York"].get(C.TORY, 0) == 0

    def test_march_in_place_needs_three_cubes(self):
        """§3.2.3: destinations Activate one Militia per three British
        cubes — an in-place space with fewer than 3 cubes activates
        nothing, so the bot must not select (and pay for) it."""
        state = _state(
            spaces={"Virginia": {C.REGULAR_BRI: 2, C.MILITIA_U: 2}},
            support={"Virginia": 1},
            control={"Virginia": None},
        )
        state["_no_special"] = True
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert not ok, "2 cubes cannot activate any Militia — dead move"
        assert state["spaces"]["Virginia"][C.MILITIA_U] == 2


class TestMarchPhase1ControlGoal:
    def test_multi_group_accumulation_until_control(self):
        """§8.4.1... §8.4.3: "Stop moving groups into each destination
        space once British Control is established" — several groups may
        feed one destination (the old planner sent exactly one group and
        never checked the Control goal)."""
        state = _state(
            spaces={
                "New_York_City": {C.MILITIA_A: 4},
                "New_York": {C.REGULAR_BRI: 4},      # movable 3
                "New_Jersey": {C.REGULAR_BRI: 3},    # movable 2
            },
            support={"New_York_City": 0, "New_York": 0, "New_Jersey": 0},
            control={"New_York_City": "REBELLION",
                     "New_York": C.BRITISH, "New_Jersey": C.BRITISH},
        )
        state["_no_special"] = True
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert ok
        nyc = state["spaces"]["New_York_City"]
        # needed 5; New_York alone provides 3 — New_Jersey joins.
        assert nyc.get(C.REGULAR_BRI, 0) == 5
        assert state.get("control", {}).get("New_York_City") == C.BRITISH

    def test_unreachable_control_target_skipped(self):
        """A destination whose British Control cannot be established with
        the available groups is skipped entirely — moving a too-small
        group adds nothing (the old planner marched it anyway)."""
        state = _state(
            spaces={
                "Boston": {C.REGULAR_BRI: 2},
                "Massachusetts": {C.MILITIA_A: 5},
            },
            support={"Boston": 0, "Massachusetts": -2},
            control={"Boston": C.BRITISH, "Massachusetts": "REBELLION"},
        )
        state["_no_special"] = True
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert not ok
        assert state["spaces"]["Massachusetts"].get(C.REGULAR_BRI, 0) == 0


class TestMarchCommonCause:
    def test_cc_difference_uses_group_counts(self):
        """§8.4.3 COMMON CAUSE: "make up the difference between the
        number of Regulars and Tories in the group."  Group: 3 Regulars,
        2 Tories → 1 War Party joins (the old code compared the space's
        4 Regulars against space-plus-movable Tories, 3+2=5, and sent
        none), marches with the group and arrives Active (§4.2.1)."""
        state = _state(
            spaces={
                "Virginia": {C.REGULAR_BRI: 4, C.TORY: 3, C.WARPARTY_U: 3},
                "North_Carolina": {C.MILITIA_A: 3, C.MILITIA_U: 2},
            },
            support={"Virginia": 0, "North_Carolina": -2},
            control={"Virginia": C.BRITISH, "North_Carolina": "REBELLION"},
        )
        bot = BritishBot()
        ok = bot._march(state, tried_muster=True)
        assert ok
        nc = state["spaces"]["North_Carolina"]
        assert nc.get(C.REGULAR_BRI, 0) == 3
        assert nc.get(C.TORY, 0) == 2
        assert nc.get(C.WARPARTY_A, 0) == 1, "CC War Party must arrive (Active)"
        assert state.get("control", {}).get("North_Carolina") == C.BRITISH
        # "do not use the last War Party": 3 - 1 moved = 2 remain in origin
        vsp = state["spaces"]["Virginia"]
        assert vsp.get(C.WARPARTY_U, 0) + vsp.get(C.WARPARTY_A, 0) == 2
        assert state["_turn_used_special"] is True
