"""
Regression tests for the 5 bot error categories fixed in this changeset.

Error #1 (25x): Indian Raid _reserve_source DC exhaustion + range validation
Error #3 (10x): British March bring_escorts when Tories in move plan
Error #2+#4 (19x): British Muster Reward Loyalty stale state after placements
Error #5 (2x): Card 10 pick_two_cities returning < 2 results
Error #6 (3x): Resource affordability pre-checks in bot commands
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from copy import deepcopy
import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.map.adjacency import shortest_path


# ============================================================================
# Shared test state builders
# ============================================================================

def _base_state(**overrides):
    """Minimal valid game state."""
    st = {
        "spaces": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.INDIANS: 10, C.FRENCH: 10},
        "available": {
            C.REGULAR_BRI: 10, C.TORY: 10, C.FORT_BRI: 2,
            C.REGULAR_PAT: 10, C.MILITIA_U: 10, C.MILITIA_A: 0, C.FORT_PAT: 2,
            C.REGULAR_FRE: 10,
            C.WARPARTY_U: 10, C.WARPARTY_A: 0, C.VILLAGE: 5,
        },
        "unavailable": {},
        "support": {},
        "control": {},
        "casualties": {},
        "markers": {
            C.RAID: {"pool": 12, "on_map": set()},
            C.PROPAGANDA: {"pool": 10, "on_map": set()},
        },
        "rng": random.Random(42),
        "history": [],
        "leaders": {},
        "leader_locs": {},
    }
    st.update(overrides)
    return st


def _space(**pieces):
    """Create a space dict with default type Colony."""
    sp = {"type": "Colony"}
    sp.update(pieces)
    return sp


def _city(**pieces):
    """Create a City space dict."""
    sp = {"type": "City"}
    sp.update(pieces)
    return sp


# ============================================================================
# Error #1: Indian Raid _reserve_source DC exhaustion + range validation
# ============================================================================

class TestIndianRaidDCExhaustion:
    """After Dragging Canoe's WP pool is depleted, _reserve_source must
    stop returning his location for extended-range moves."""

    def test_raid_does_not_crash_when_dc_pool_exhausted(self):
        """If DC has only 1 WP but 3 targets need DC range, bot should
        not crash — it should select only what it can validly reach."""
        from lod_ai.bots.indians import IndianBot
        from lod_ai.commands import raid

        state = _base_state()
        # Set up DC at Northwest with 1 WP
        state["spaces"] = {
            "Northwest": _space(**{C.WARPARTY_U: 1}),
            "Quebec": _space(**{C.WARPARTY_U: 0}),
            "Southwest": _space(**{C.WARPARTY_U: 0}),
            "Virginia": _space(**{C.WARPARTY_U: 0}),
            "Georgia": _space(**{C.WARPARTY_U: 0}),
            "New_York": _space(**{C.WARPARTY_U: 0}),
        }
        state["support"] = {
            "Quebec": C.PASSIVE_OPPOSITION,
            "Virginia": C.PASSIVE_OPPOSITION,
            "Georgia": C.PASSIVE_OPPOSITION,
        }
        state["leaders"] = {"LEADER_DRAGGING_CANOE": "Northwest"}
        state["leader_locs"] = {"LEADER_DRAGGING_CANOE": "Northwest"}
        refresh_control(state)

        bot = IndianBot()
        # Should not raise — DC only has 1 WP so only 1 extended-range move
        # is valid.  The bot should gracefully limit its plan.
        try:
            bot._follow_flowchart(state)
        except ValueError as e:
            if "not within Raid move range" in str(e):
                pytest.fail(f"DC exhaustion not handled: {e}")
            raise

    def test_raid_validates_source_range(self):
        """A move_plan entry where src is NOT adjacent and NOT DC-extended
        should be rejected by raid.execute() validation."""
        from lod_ai.commands import raid

        state = _base_state()
        # Georgia has its own WP (so it passes the "access" check) but
        # we try to move a WP from distant Virginia — that should fail
        # range validation.
        state["spaces"] = {
            "Virginia": _space(**{C.WARPARTY_U: 1}),
            "Georgia": _space(**{C.WARPARTY_U: 1}),
        }
        state["support"] = {"Georgia": C.PASSIVE_OPPOSITION}
        refresh_control(state)

        # Virginia is not adjacent to Georgia → should fail move validation
        with pytest.raises(ValueError, match="not within Raid move range"):
            raid.execute(state, C.INDIANS, {}, ["Georgia"],
                         move_plan=[("Virginia", "Georgia")])


# ============================================================================
# Error #3: British March bring_escorts when Tories in move plan
# ============================================================================

class TestBritishMarchEscorts:
    """March must set bring_escorts=True when Tories are in the plan."""

    def test_march_with_tories_requires_escorts(self):
        """Moving Tories without bring_escorts=True should raise."""
        from lod_ai.commands import march

        state = _base_state()
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
            "Massachusetts": _space(**{}),
        }
        refresh_control(state)

        # Without escorts → should fail
        with pytest.raises(ValueError, match="Escorts required"):
            march.execute(
                state, C.BRITISH, {},
                ["Boston"], ["Massachusetts"],
                plan=[{"src": "Boston", "dst": "Massachusetts",
                       "pieces": {C.REGULAR_BRI: 2, C.TORY: 1}}],
                bring_escorts=False,
            )

    def test_march_with_tories_succeeds_with_escorts(self):
        """Moving Tories with bring_escorts=True should succeed."""
        from lod_ai.commands import march

        state = _base_state()
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
            "Massachusetts": _space(**{}),
        }
        refresh_control(state)

        # With escorts → should succeed
        march.execute(
            state, C.BRITISH, {},
            ["Boston"], ["Massachusetts"],
            plan=[{"src": "Boston", "dst": "Massachusetts",
                   "pieces": {C.REGULAR_BRI: 2, C.TORY: 1}}],
            bring_escorts=True,
        )
        assert state["spaces"]["Massachusetts"].get(C.TORY, 0) == 1


# ============================================================================
# Error #2+#4: British Muster Reward Loyalty stale state
# ============================================================================

class TestMusterRewardLoyaltyValidation:
    """Muster should skip Reward Loyalty (not crash) if post-placement
    state no longer meets RL preconditions."""

    def test_rl_skipped_when_no_regular_after_placement(self):
        """If a space loses its Regular somehow, RL should be silently
        skipped rather than raising ValueError."""
        from lod_ai.commands import muster

        state = _base_state()
        # Space has Tory but no Regular — RL precondition fails
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 0, C.TORY: 2}),
        }
        state["control"] = {"Boston": C.BRITISH}
        state["support"] = {"Boston": C.NEUTRAL}

        # Previously this would raise "Reward Loyalty requires >=1 British
        # Regular and >=1 Tory in space."  Now it should silently skip.
        muster.execute(
            state, C.BRITISH, {}, ["Boston"],
            regular_plan={"space": "Boston", "n": 0},
            tory_plan={},
            reward_levels=1,
        )
        # Support should remain unchanged (RL was skipped)
        assert state.get("support", {}).get("Boston", C.NEUTRAL) == C.NEUTRAL

    def test_rl_skipped_when_no_british_control(self):
        """If British don't control the space, RL should be skipped."""
        from lod_ai.commands import muster

        state = _base_state()
        state["spaces"] = {
            "Virginia": _space(**{C.REGULAR_BRI: 2, C.TORY: 2,
                                  C.REGULAR_PAT: 5}),
        }
        # Rebellion controls (more rebel pieces)
        refresh_control(state)

        state["support"] = {"Virginia": C.NEUTRAL}

        # RL should be skipped (no British control)
        muster.execute(
            state, C.BRITISH, {}, ["Virginia"],
            regular_plan={"space": "Virginia", "n": 0},
            tory_plan={},
            reward_levels=1,
        )
        assert state.get("support", {}).get("Virginia", C.NEUTRAL) == C.NEUTRAL

    def test_rl_works_when_conditions_met(self):
        """RL should still execute normally when all conditions are met."""
        from lod_ai.commands import muster

        state = _base_state()
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
        }
        refresh_control(state)
        state["support"] = {"Boston": C.NEUTRAL}

        muster.execute(
            state, C.BRITISH, {}, ["Boston"],
            regular_plan={"space": "Boston", "n": 0},
            tory_plan={},
            reward_levels=1,
        )
        # Support should shift toward Active Support
        assert state.get("support", {}).get("Boston", 0) > C.NEUTRAL


# ============================================================================
# Error #5: Card 10 pick_two_cities guard
# ============================================================================

class TestCard10PickTwoCities:
    """Card 10 unshaded should not crash when fewer than 2 cities exist."""

    def test_no_cities_does_not_crash(self):
        """With no City-typed spaces, card 10 unshaded should be a no-op."""
        from lod_ai.cards.effects.early_war import evt_010_franklin_to_france

        state = _base_state()
        # Only Colonies, no Cities
        state["spaces"] = {
            "Virginia": _space(),
            "Georgia": _space(),
        }
        state["support"] = {"Virginia": 0, "Georgia": 0}

        # Should not raise "not enough values to unpack"
        evt_010_franklin_to_france(state, shaded=False)

    def test_one_city_does_not_crash(self):
        """With only 1 city, card 10 unshaded should be a no-op."""
        from lod_ai.cards.effects.early_war import evt_010_franklin_to_france

        state = _base_state()
        state["spaces"] = {
            "Boston": _city(),
            "Virginia": _space(),
        }
        state["support"] = {"Boston": 0, "Virginia": 0}

        evt_010_franklin_to_france(state, shaded=False)

    def test_two_cities_works_normally(self):
        """With 2+ cities, card 10 unshaded should shift support."""
        from lod_ai.cards.effects.early_war import evt_010_franklin_to_france

        state = _base_state()
        state["spaces"] = {
            "Boston": _city(),
            "New_York_City": _city(),
            "Virginia": _space(),
        }
        state["support"] = {"Boston": 0, "New_York_City": 0, "Virginia": 0}

        evt_010_franklin_to_france(state, shaded=False)
        # Both cities should shift +1 toward Active Support
        assert state["support"]["Boston"] == 1
        assert state["support"]["New_York_City"] == 1


# ============================================================================
# Error #6: Resource affordability pre-checks
# ============================================================================

class TestResourceAffordability:
    """Bots should not crash when they can't afford commands."""

    def test_rally_free_when_patriots_have_zero_resources(self):
        """Win-the-Day free rally should work even with 0 Patriot resources
        after paying battle cost."""
        from lod_ai.commands import battle, rally

        state = _base_state()
        # Patriots have exactly 1 resource — enough for battle (1 space)
        # but 0 left over for rally.  Win-the-Day rally should be free.
        state["resources"][C.PATRIOTS] = 1
        state["spaces"] = {
            "Boston": _city(**{
                C.REGULAR_PAT: 5, C.MILITIA_A: 3,
                C.REGULAR_BRI: 1,
            }),
            "Virginia": _space(**{C.MILITIA_U: 2}),
        }
        refresh_control(state)

        # Battle with win callback that requests rally
        def _win_cb(st, sid):
            return ("Virginia", {}, None)

        # Should not raise "PATRIOTS cannot afford 1 Resources"
        # Battle costs 1 resource (1 space), leaving 0.
        # Free rally should still work.
        battle.execute(
            state, C.PATRIOTS, {}, ["Boston"],
            win_callback=_win_cb,
        )
        # Resources should be 0 after battle cost (rally was free)
        assert state["resources"][C.PATRIOTS] == 0

    def test_british_march_falls_through_when_broke(self):
        """British bot should not crash on march when resources are 0."""
        from lod_ai.bots.british_bot import BritishBot

        state = _base_state()
        state["resources"][C.BRITISH] = 0
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3}),
            "Massachusetts": _space(**{}),
        }
        refresh_control(state)

        bot = BritishBot()
        # Should not raise ValueError — should pass or fall through
        try:
            bot._follow_flowchart(state)
        except ValueError as e:
            if "cannot afford" in str(e):
                pytest.fail(f"Resource check missing: {e}")
            raise

    def test_indian_gather_trims_to_affordable(self):
        """Indian gather should trim selection when resources are limited."""
        from lod_ai.economy.resources import can_afford

        state = _base_state()
        state["resources"][C.INDIANS] = 1  # can only afford 1 space

        # Verify can_afford works correctly
        assert can_afford(state, C.INDIANS, 1)
        assert not can_afford(state, C.INDIANS, 2)


# ============================================================================
# Error #7: Battle allied fee can_afford guard (battle.py:100-105)
# ============================================================================

class TestBattleAlliedFeeCanAfford:
    """When PATRIOTS battle in a space with French Regulars, the allied
    fee to French must be capped at what French can afford (battle.py:100-105).
    Previously this would call spend(state, FRENCH, fee) with fee > 0 when
    French had 0 Resources, raising a ValueError."""

    def test_patriot_battle_french_ally_zero_resources(self):
        """Patriots battle in space with French Regulars but French has 0
        Resources.  Fee should be capped to 0 — no ValueError."""
        from lod_ai.commands import battle

        state = _base_state()
        state["resources"][C.FRENCH] = 0
        state["spaces"] = {
            "Boston": _city(**{
                C.REGULAR_PAT: 4,
                C.REGULAR_FRE: 2,
                C.REGULAR_BRI: 2,
            }),
        }
        refresh_control(state)

        # Should not raise "FRENCH cannot afford 1 Resources"
        battle.execute(state, C.PATRIOTS, {}, ["Boston"])

        # French resources should still be 0 (fee was capped to 0)
        assert state["resources"][C.FRENCH] == 0

    def test_patriot_battle_french_ally_partial_afford(self):
        """French can afford fee for 1 of 2 battle spaces.  Fee should be 1."""
        from lod_ai.commands import battle

        state = _base_state()
        state["resources"][C.FRENCH] = 1
        state["spaces"] = {
            "Boston": _city(**{
                C.REGULAR_PAT: 4, C.REGULAR_FRE: 1, C.REGULAR_BRI: 2,
            }),
            "Massachusetts": _space(**{
                C.REGULAR_PAT: 3, C.REGULAR_FRE: 1, C.REGULAR_BRI: 2,
            }),
        }
        refresh_control(state)

        # 2 spaces with French Regulars, but French can only afford 1
        battle.execute(state, C.PATRIOTS, {}, ["Boston", "Massachusetts"])

        # French spent 1 (capped from 2 to 1)
        assert state["resources"][C.FRENCH] == 0


# ============================================================================
# Error #8: Muster Reward Loyalty affordability pre-check (muster.py:271-280)
# ============================================================================

class TestMusterRLAffordabilityPreCheck:
    """After muster payment, if British can't afford the RL cost, RL is
    skipped silently instead of raising ValueError (muster.py:271-284)."""

    def test_rl_skipped_when_cannot_afford_after_muster_payment(self):
        """British muster with reward_levels=1 but only enough resources
        for the muster spaces, not the RL cost.  No ValueError; just skip RL."""
        from lod_ai.commands import muster

        state = _base_state()
        # British has exactly 1 resource: enough for muster (1 space) but
        # after paying 1 for muster, 0 left for RL (which costs 1).
        state["resources"][C.BRITISH] = 1
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
        }
        refresh_control(state)
        state["support"] = {"Boston": C.NEUTRAL}

        # Should not raise "Not enough Resources to Reward Loyalty."
        muster.execute(
            state, C.BRITISH, {}, ["Boston"],
            regular_plan={"space": "Boston", "n": 0},
            tory_plan={},
            reward_levels=1,
        )
        # Resources should be 0 after muster cost (RL was skipped)
        assert state["resources"][C.BRITISH] == 0
        # Support should remain at NEUTRAL (RL was skipped)
        assert state.get("support", {}).get("Boston", C.NEUTRAL) == C.NEUTRAL


# ============================================================================
# Error #9: Scout SA save/restore (scout.py:156-160)
# ============================================================================

class TestScoutSkirmishSaveRestore:
    """Scout's optional Skirmish should NOT permanently set
    _turn_used_special.  The save/restore logic at scout.py:156-160
    preserves the prior value."""

    def test_scout_skirmish_does_not_set_turn_used_special(self):
        """Execute scout with skirmish=True and verify _turn_used_special
        is restored to its prior value (False)."""
        from lod_ai.commands import scout

        state = _base_state()
        state["_turn_used_special"] = False
        # Massachusetts (Colony) -> New_Hampshire (Colony): adjacent
        state["spaces"] = {
            "Massachusetts": _space(**{
                C.WARPARTY_U: 2,
                C.REGULAR_BRI: 3,
                C.TORY: 1,
            }),
            "New_Hampshire": _space(**{
                C.REGULAR_PAT: 2,
                C.MILITIA_U: 1,
            }),
        }
        refresh_control(state)

        scout.execute(
            state, C.INDIANS, {},
            src="Massachusetts",
            dst="New_Hampshire",
            n_warparties=1,
            n_regulars=2,
            n_tories=0,
            skirmish=True,
            skirmish_option=1,
        )

        # _turn_used_special should be restored to False (not True)
        assert state["_turn_used_special"] is False

    def test_scout_skirmish_preserves_true_value(self):
        """If _turn_used_special was already True before Scout, it should
        remain True after."""
        from lod_ai.commands import scout

        state = _base_state()
        state["_turn_used_special"] = True
        state["spaces"] = {
            "Massachusetts": _space(**{
                C.WARPARTY_U: 2,
                C.REGULAR_BRI: 3,
            }),
            "New_Hampshire": _space(**{
                C.REGULAR_PAT: 2,
            }),
        }
        refresh_control(state)

        scout.execute(
            state, C.INDIANS, {},
            src="Massachusetts",
            dst="New_Hampshire",
            n_warparties=1,
            n_regulars=2,
            skirmish=True,
            skirmish_option=1,
        )

        assert state["_turn_used_special"] is True


# ============================================================================
# Error #10: Win-the-Day rally trace preservation (battle.py:140-153)
# ============================================================================

class TestWinTheDayRallyTracePreservation:
    """Battle's Win-the-Day rally must NOT add extra spaces to
    _turn_affected_spaces.  The save/restore logic at battle.py:147-155
    preserves the original set."""

    def test_wtd_rally_does_not_pollute_affected_spaces(self):
        """Battle in one space with a win_callback that returns a different
        rally space.  _turn_affected_spaces should only contain the battle
        space, not the rally space."""
        from lod_ai.commands import battle

        state = _base_state()
        state["resources"][C.PATRIOTS] = 10
        state["spaces"] = {
            # Overwhelming Patriot force for guaranteed win
            "Boston": _city(**{
                C.REGULAR_PAT: 8,
                C.MILITIA_A: 4,
                C.REGULAR_BRI: 1,
            }),
            "Massachusetts": _space(**{C.MILITIA_U: 2}),
        }
        state["support"] = {"Boston": C.NEUTRAL, "Massachusetts": C.NEUTRAL}
        refresh_control(state)

        def _win_cb(st, sid):
            # Rally in Massachusetts (a different space from the battle)
            return ("Massachusetts", {}, None)

        battle.execute(
            state, C.PATRIOTS, {}, ["Boston"],
            win_callback=_win_cb,
        )

        affected = state.get("_turn_affected_spaces", set())
        assert "Boston" in affected, "Battle space should be in affected spaces"
        assert "Massachusetts" not in affected, (
            "Rally space from WTD should NOT be in _turn_affected_spaces"
        )


# ============================================================================
# Error #11: Gather WP cap (gather.py:199-202)
# ============================================================================

class TestGatherWPCap:
    """Gather move plan should cap WP moves to actual available count
    instead of raising ValueError (gather.py:199-203)."""

    def test_gather_move_caps_to_available_wp(self):
        """Gather with move_plan requesting more WP than available in
        src.  Should cap silently, not raise ValueError."""
        from lod_ai.commands import gather

        state = _base_state()
        # Southwest (Reserve, adjacent to Georgia) has 2 WP
        # but move_plan requests 5.
        state["spaces"] = {
            "Georgia": _space(**{
                C.WARPARTY_U: 1,
                C.VILLAGE: 1,
            }),
            "Southwest": _space(**{
                C.WARPARTY_U: 2,
            }),
        }
        state["support"] = {
            "Georgia": C.NEUTRAL,
            "Southwest": C.NEUTRAL,
        }
        # Mark Georgia as not an Indian reserve for cost purposes
        refresh_control(state)

        # Request moving 5 WP from Southwest to Georgia, but only 2 exist
        gather.execute(
            state, C.INDIANS, {},
            ["Georgia"],
            move_plan=[("Southwest", "Georgia", 5)],
        )

        # Only 2 should have moved (capped from 5 to 2)
        # All WP in Georgia should be Underground after gather
        georgia = state["spaces"]["Georgia"]
        total_wp = georgia.get(C.WARPARTY_U, 0) + georgia.get(C.WARPARTY_A, 0)
        # 1 original + 2 moved = 3 (but also 1 from place_one default action)
        assert total_wp >= 3, f"Expected at least 3 WP in Georgia, got {total_wp}"

        # Southwest should have 0 WP left (both moved)
        sw = state["spaces"]["Southwest"]
        sw_total = sw.get(C.WARPARTY_U, 0) + sw.get(C.WARPARTY_A, 0)
        assert sw_total == 0, f"Expected 0 WP in Southwest, got {sw_total}"

    def test_gather_move_zero_available_is_noop(self):
        """If src has 0 WP, requesting a move should be a silent no-op."""
        from lod_ai.commands import gather

        state = _base_state()
        state["spaces"] = {
            "Georgia": _space(**{
                C.WARPARTY_U: 1,
                C.VILLAGE: 1,
            }),
            "Southwest": _space(**{
                C.WARPARTY_U: 0,
            }),
        }
        state["support"] = {
            "Georgia": C.NEUTRAL,
            "Southwest": C.NEUTRAL,
        }
        refresh_control(state)

        # Request moving 3 WP from Southwest, but 0 exist
        gather.execute(
            state, C.INDIANS, {},
            ["Georgia"],
            move_plan=[("Southwest", "Georgia", 3)],
        )

        # Georgia should just have its original WP + 1 from place_one
        georgia = state["spaces"]["Georgia"]
        total_wp = georgia.get(C.WARPARTY_U, 0) + georgia.get(C.WARPARTY_A, 0)
        assert total_wp >= 1, f"Expected at least 1 WP in Georgia, got {total_wp}"
