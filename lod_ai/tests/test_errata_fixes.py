"""
Diagnostic smoke tests for errata fixes applied to the bot system.

Covers:
  1. Event instruction table correctness (cards 80, 86)
  2. Indian bot _force_condition_met for card 80 (Patriot Forts)
  3. Patriot bot _force_condition_met for card 80 (Indian Villages)
  4. British bot _force_condition_met for card 52 (French Regs in rebel spaces)
  5. Indian March Gather-eligible retention (§8.7.3)
  6. Full-game regression across all three scenarios
"""

from __future__ import annotations

import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.bots import event_instructions as EI
from lod_ai.bots.indians import IndianBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai.state.setup_state import build_state


# =====================================================================
#  Group 1: Event instruction table correctness
# =====================================================================

class TestEventInstructionTable:
    """Verify errata changes to the event instruction dicts."""

    def test_indians_card_80_is_force_if_80(self):
        assert EI.INDIANS[80] == "force_if_80"

    def test_indians_card_86_is_force(self):
        assert EI.INDIANS[86] == "force"

    def test_patriots_card_80_is_force_if_80(self):
        assert EI.PATRIOTS[80] == "force_if_80"

    def test_indians_card_86_present_regression_guard(self):
        """Card 86 must be present in the INDIANS dict (regression guard)."""
        assert 86 in EI.INDIANS


# =====================================================================
#  Group 2: Indian bot _force_condition_met for card 80
# =====================================================================

class TestIndianForceIf80:
    """Card 80 errata: Indians should force event only if Patriot Forts exist."""

    def _make_state(self, spaces):
        return {
            "spaces": spaces,
            "resources": {C.INDIANS: 3, C.BRITISH: 5, C.PATRIOTS: 3, C.FRENCH: 0},
            "available": {},
            "support": {},
            "control": {},
            "rng": random.Random(42),
            "history": [],
        }

    def test_true_when_patriot_fort_exists(self):
        bot = IndianBot()
        state = self._make_state({
            "Pennsylvania": {C.FORT_PAT: 1},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is True

    def test_false_when_no_patriot_forts(self):
        bot = IndianBot()
        state = self._make_state({
            "Pennsylvania": {C.FORT_PAT: 0, C.REGULAR_PAT: 3},
            "New_York": {C.MILITIA_A: 2},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is False

    def test_true_with_fort_in_different_space(self):
        bot = IndianBot()
        state = self._make_state({
            "Pennsylvania": {C.FORT_PAT: 0},
            "Georgia": {C.FORT_PAT: 1},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is True


# =====================================================================
#  Group 3: Patriot bot _force_condition_met for card 80
# =====================================================================

class TestPatriotForceIf80:
    """Card 80 errata: Patriots should force event only if Indian Villages exist."""

    def _make_state(self, spaces):
        return {
            "spaces": spaces,
            "resources": {C.INDIANS: 3, C.BRITISH: 5, C.PATRIOTS: 3, C.FRENCH: 0},
            "available": {},
            "support": {},
            "control": {},
            "rng": random.Random(42),
            "history": [],
        }

    def test_true_when_village_exists(self):
        bot = PatriotBot()
        state = self._make_state({
            "Northwest": {C.VILLAGE: 1},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is True

    def test_false_when_no_villages(self):
        bot = PatriotBot()
        state = self._make_state({
            "Northwest": {C.VILLAGE: 0, C.WARPARTY_A: 3},
            "Quebec": {C.WARPARTY_U: 2},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is False

    def test_true_with_village_in_different_space(self):
        bot = PatriotBot()
        state = self._make_state({
            "Northwest": {C.VILLAGE: 0},
            "Southwest": {C.VILLAGE: 2},
        })
        card = {"id": 80}
        assert bot._force_condition_met("force_if_80", state, card) is True


# =====================================================================
#  Group 4: British bot _force_condition_met for card 52
# =====================================================================

class TestBritishForceIf52:
    """Card 52 errata: British force event when French Regs in rebel-outnumbering spaces."""

    def _make_state(self, spaces):
        return {
            "spaces": spaces,
            "resources": {C.BRITISH: 5, C.PATRIOTS: 3, C.INDIANS: 2, C.FRENCH: 3},
            "available": {},
            "support": {},
            "control": {},
            "rng": random.Random(42),
            "history": [],
        }

    def test_true_french_regs_rebels_outnumber_british(self):
        """French Regulars in a space where Rebel pieces > British pieces."""
        bot = BritishBot()
        state = self._make_state({
            "Pennsylvania": {
                C.REGULAR_FRE: 2,
                C.REGULAR_PAT: 3,  # rebel = 3+2=5 (PAT+FRE)
                C.REGULAR_BRI: 1,  # british = 1
                C.TORY: 0, C.FORT_BRI: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0, C.FORT_PAT: 0,
            },
        })
        card = {"id": 52}
        assert bot._force_condition_met("force_if_52", state, card) is True

    def test_false_british_equal_or_exceed_rebels(self):
        """French Regulars present but British pieces >= Rebel pieces."""
        bot = BritishBot()
        state = self._make_state({
            "Pennsylvania": {
                C.REGULAR_FRE: 1,
                C.REGULAR_PAT: 1,  # rebel = 1+1+0+0+0=2
                C.REGULAR_BRI: 2,  # british = 2+1+0=3
                C.TORY: 1, C.FORT_BRI: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0, C.FORT_PAT: 0,
            },
        })
        card = {"id": 52}
        assert bot._force_condition_met("force_if_52", state, card) is False

    def test_false_no_french_regulars(self):
        """No French Regulars on the map at all."""
        bot = BritishBot()
        state = self._make_state({
            "Pennsylvania": {
                C.REGULAR_FRE: 0,
                C.REGULAR_PAT: 5,
                C.REGULAR_BRI: 1,
                C.TORY: 0, C.FORT_BRI: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0, C.FORT_PAT: 0,
            },
        })
        card = {"id": 52}
        assert bot._force_condition_met("force_if_52", state, card) is False

    def test_force_if_51_still_works(self):
        """Regression: force_if_51 should still function independently after the split."""
        bot = BritishBot()
        # Set up a space where Royalist force exceeds Rebel force
        state = self._make_state({
            "Pennsylvania": {
                C.REGULAR_BRI: 5, C.TORY: 3,
                C.REGULAR_PAT: 1, C.MILITIA_A: 1, C.MILITIA_U: 0,
                C.REGULAR_FRE: 0, C.FORT_PAT: 0, C.FORT_BRI: 0,
                C.WARPARTY_A: 0,
            },
        })
        card = {"id": 51}
        # Royal force = 5 + min(3,5)=3 + 0 = 8; Rebel force = 1 + 0 + 0 = 1
        # Royalist exceeds → should return True
        assert bot._force_condition_met("force_if_51", state, card) is True

    def test_force_if_51_false_when_no_advantage(self):
        """force_if_51 should return False when Royalists can't achieve battle advantage."""
        bot = BritishBot()
        state = self._make_state({
            "Pennsylvania": {
                C.REGULAR_BRI: 0, C.TORY: 0,
                C.REGULAR_PAT: 5, C.MILITIA_A: 4, C.MILITIA_U: 0,
                C.REGULAR_FRE: 0, C.FORT_PAT: 1, C.FORT_BRI: 0,
                C.WARPARTY_A: 0,
            },
        })
        card = {"id": 51}
        assert bot._force_condition_met("force_if_51", state, card) is False


# =====================================================================
#  Group 5: Indian March Gather-eligible retention (§8.7.3)
# =====================================================================

class TestIndianMarchGatherRetention:
    """§8.7.3: Don't strip WP below 3 from Gather-eligible spaces during March."""

    def _build_state_for_march(self, *, seed=42):
        """Build a full 1775 state (for map adjacency) and clear it for testing."""
        state = build_state("1775", seed=seed)
        # Clear all pieces from all spaces
        for sid in state["spaces"]:
            for tag in list(state["spaces"][sid].keys()):
                if isinstance(state["spaces"][sid].get(tag), int):
                    state["spaces"][sid][tag] = 0
        state["resources"][C.INDIANS] = 5
        state["history"] = []
        return state

    def test_retains_3wp_in_gather_eligible_province(self):
        """A Province with exactly 3 WP, no Village, room for one → must NOT donate WP."""
        state = self._build_state_for_march()
        bot = IndianBot()

        # Northwest is a Reserve (type != City), adjacent to Quebec
        # Pennsylvania is a Colony (type != City), adjacent to Northwest
        # Set up: Pennsylvania has 3 WP, no Village, has room for Village → Gather-eligible
        state["spaces"]["Pennsylvania"][C.WARPARTY_U] = 3
        state["spaces"]["Pennsylvania"][C.VILLAGE] = 0
        state["spaces"]["Pennsylvania"][C.FORT_BRI] = 0
        state["spaces"]["Pennsylvania"][C.FORT_PAT] = 0

        # Give adjacent space (Northwest) some WP too, so march has sources
        state["spaces"]["Northwest"][C.WARPARTY_U] = 4
        state["spaces"]["Northwest"][C.VILLAGE] = 0

        # Place some enemies to give the bot a march destination
        state["spaces"]["Virginia"][C.REGULAR_PAT] = 2
        state["support"]["Virginia"] = C.PASSIVE_OPPOSITION

        # Run march
        bot._march(state)

        # Pennsylvania should retain at least 3 WP
        pa_wp = (state["spaces"]["Pennsylvania"].get(C.WARPARTY_U, 0)
                 + state["spaces"]["Pennsylvania"].get(C.WARPARTY_A, 0))
        assert pa_wp >= 3, (
            f"Pennsylvania WP dropped to {pa_wp}; expected >= 3 (Gather-eligible retention)"
        )

    def test_can_take_from_4wp_leaving_3(self):
        """A Province with 4+ WP → bot CAN take 1, leaving 3 (still Gather-eligible)."""
        state = self._build_state_for_march(seed=99)
        bot = IndianBot()

        # Set up Pennsylvania with 4 WP, gather-eligible
        state["spaces"]["Pennsylvania"][C.WARPARTY_U] = 4
        state["spaces"]["Pennsylvania"][C.VILLAGE] = 0
        state["spaces"]["Pennsylvania"][C.FORT_BRI] = 0
        state["spaces"]["Pennsylvania"][C.FORT_PAT] = 0

        # Place enemies to attract march
        state["spaces"]["Virginia"][C.REGULAR_PAT] = 3
        state["support"]["Virginia"] = C.PASSIVE_OPPOSITION

        bot._march(state)

        pa_wp = (state["spaces"]["Pennsylvania"].get(C.WARPARTY_U, 0)
                 + state["spaces"]["Pennsylvania"].get(C.WARPARTY_A, 0))
        # Should still have at least 3 (the min_keep), but could have taken 1
        assert pa_wp >= 3, (
            f"Pennsylvania WP dropped to {pa_wp}; expected >= 3 (Gather-eligible retention)"
        )

    def test_village_present_uses_village_constraint(self):
        """A Province with 3 WP and a Village → the Village constraint (keep ≥1) applies,
        not the Gather constraint (keep ≥3), since Gather doesn't apply when Village present."""
        state = self._build_state_for_march(seed=77)
        bot = IndianBot()

        # Pennsylvania: 3 WP + 1 Village → NOT gather-eligible (already has Village)
        state["spaces"]["Pennsylvania"][C.WARPARTY_U] = 3
        state["spaces"]["Pennsylvania"][C.VILLAGE] = 1
        state["spaces"]["Pennsylvania"][C.FORT_BRI] = 0
        state["spaces"]["Pennsylvania"][C.FORT_PAT] = 0

        # Place enemies
        state["spaces"]["Virginia"][C.REGULAR_PAT] = 3
        state["support"]["Virginia"] = C.PASSIVE_OPPOSITION

        bot._march(state)

        pa_wp = (state["spaces"]["Pennsylvania"].get(C.WARPARTY_U, 0)
                 + state["spaces"]["Pennsylvania"].get(C.WARPARTY_A, 0))
        # Village constraint: keep ≥1 (not ≥3)
        assert pa_wp >= 1, (
            f"Pennsylvania WP dropped to {pa_wp}; expected >= 1 (Village constraint)"
        )


# =====================================================================
#  Group 6: Quick full-game regression (one per scenario)
# =====================================================================

class TestFullGameRegression:
    """Run one full game per scenario to verify no integration breakage."""

    @pytest.mark.parametrize("scenario,seed", [
        ("1775", 42),
        ("1776", 42),
        ("1778", 42),
    ])
    def test_full_game_completes(self, scenario, seed):
        """Run a full 4-bot game and verify no unhandled exceptions."""
        from lod_ai.engine import Engine
        from lod_ai.util.normalize_state import normalize_state
        from lod_ai.util.validate import validate_state

        state = build_state(scenario, seed=seed)
        engine = Engine(initial_state=state)

        max_cards = 200
        cards_played = 0

        for _ in range(max_cards):
            card = engine.draw_card()
            if card is None:
                break

            engine.play_card(card)
            normalize_state(engine.state)
            cards_played += 1

            # Basic validation
            try:
                validate_state(engine.state)
            except (ValueError, TypeError, KeyError) as exc:
                pytest.fail(
                    f"Scenario {scenario}, seed {seed}, card #{cards_played} "
                    f"(id={card.get('id')}): validate_state failed: {exc}"
                )

            # Check for victory ending
            history = engine.state.get("history", [])
            if any("Victory achieved" in str(h) or "Winner:" in str(h) for h in history):
                break

        assert cards_played > 0, f"Scenario {scenario}: no cards were played"
