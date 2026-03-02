"""Tests for runtime piece-availability checks in _faction_event_conditions.

Each bot's _faction_event_conditions() now verifies that pieces are actually
available (or on the map) before returning True for static CARD_EFFECTS flags.
These tests confirm that the runtime guards work correctly.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.french import FrenchBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.indians import IndianBot
from lod_ai import rules_consts as C


# -----------------------------------------------------------------------
#  Helpers
# -----------------------------------------------------------------------

def _base_state(**overrides):
    """Minimal state dict sufficient for _faction_event_conditions."""
    s = {
        "spaces": {},
        "available": {},
        "unavailable": {},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    s.update(overrides)
    return s


# =======================================================================
#  FRENCH BOT — places_french_on_map
# =======================================================================

class TestFrenchEventAvailability:
    """Card 50 shaded: places_french_on_map=True.
    French bot should only accept this if French Regulars are in Available
    or West Indies.
    """

    def test_no_french_regulars_anywhere_returns_false(self):
        """1775 setup: all 15 French Regulars Unavailable, none in Available
        or West Indies. _faction_event_conditions should return False for
        the places_french_on_map flag (Card 50)."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": {}, "West_Indies": {}},
            available={},
            unavailable={C.FRENCH_UNAVAIL: 15},
        )
        card = {"id": 50}
        assert bot._faction_event_conditions(state, card) is False

    def test_french_regulars_in_available_returns_true(self):
        """Move 2 French Regulars to Available → should return True."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": {}, "West_Indies": {}},
            available={C.REGULAR_FRE: 2},
            unavailable={C.FRENCH_UNAVAIL: 13},
        )
        card = {"id": 50}
        assert bot._faction_event_conditions(state, card) is True

    def test_french_regulars_in_west_indies_returns_true(self):
        """French Regulars in West Indies (not Available) → should return True."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": {}, "West_Indies": {C.REGULAR_FRE: 3}},
            available={},
            unavailable={C.FRENCH_UNAVAIL: 12},
        )
        card = {"id": 50}
        assert bot._faction_event_conditions(state, card) is True

    def test_places_french_from_unavailable_no_pieces(self):
        """Card 49 shaded: places_french_from_unavailable but zero in
        Unavailable → returns False."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": {}},
            unavailable={},  # nothing unavailable
        )
        card = {"id": 49}
        assert bot._faction_event_conditions(state, card) is False

    def test_places_french_from_unavailable_with_pieces(self):
        """Card 49 shaded: places_french_from_unavailable with Unavailable
        French Regulars → returns True."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": {}},
            unavailable={C.FRENCH_UNAVAIL: 5},
        )
        card = {"id": 49}
        assert bot._faction_event_conditions(state, card) is True


# =======================================================================
#  BRITISH BOT — places_british_regulars
# =======================================================================

class TestBritishEventAvailability:
    """Card 2 unshaded: places_british_regulars=True.
    British bot should only accept if British Regulars are in Available.
    """

    def test_no_british_regulars_returns_false(self):
        """Zero British Regulars in Available → returns False for
        places_british_regulars (Card 2)."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": {}, "New_York": {}},
            available={},  # no British Regulars
        )
        card = {"id": 2}
        # Card 2 also has places_tories=True, so ensure no Tories either
        # to isolate the test
        assert bot._faction_event_conditions(state, card) is False

    def test_british_regulars_available_returns_true(self):
        """Add 1 Regular to Available → returns True."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": {}, "New_York": {}},
            available={C.REGULAR_BRI: 1},
        )
        card = {"id": 2}
        assert bot._faction_event_conditions(state, card) is True

    def test_places_british_from_unavailable_no_pieces(self):
        """places_british_from_unavailable with zero in Unavailable →
        returns False."""
        bot = BritishBot()
        # Card 27 unshaded has places_british_from_unavailable=True
        # and places_tories=True — set no tories available either
        state = _base_state(
            spaces={"Boston": {}},
            unavailable={},
            available={},
        )
        card = {"id": 27}
        assert bot._faction_event_conditions(state, card) is False

    def test_places_british_from_unavailable_with_pieces(self):
        """places_british_from_unavailable with Unavailable pieces →
        returns True."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": {}},
            unavailable={C.BRIT_UNAVAIL: 3},
        )
        card = {"id": 27}
        assert bot._faction_event_conditions(state, card) is True


# =======================================================================
#  PATRIOT BOT — places_patriot_fort
# =======================================================================

class TestPatriotEventAvailability:
    """Card 4 shaded: places_patriot_fort=True.
    Patriot bot should only accept if Patriot Forts are in Available.
    """

    def test_no_patriot_forts_returns_false(self):
        """All 3 Patriot Forts placed on map (none in Available) → returns
        False for places_patriot_fort (Card 4 shaded, which also has
        places_village and places_patriot_militia_u)."""
        bot = PatriotBot()
        state = _base_state(
            spaces={
                "Boston": {C.FORT_PAT: 1},
                "New_York": {C.FORT_PAT: 1},
                "Philadelphia": {C.FORT_PAT: 1},
            },
            available={},  # no forts available
        )
        # Card 4 shaded also has places_patriot_militia_u and places_village.
        # Since no Militia_U available and no Village on map, those won't
        # trigger either → isolates the fort check.
        card = {"id": 4}
        assert bot._faction_event_conditions(state, card) is False

    def test_patriot_fort_available_returns_true(self):
        """Add 1 fort to Available → returns True."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": {}},
            available={C.FORT_PAT: 1},
        )
        card = {"id": 4}
        assert bot._faction_event_conditions(state, card) is True

    def test_removes_village_none_on_map(self):
        """removes_village with no Villages on map → returns False.
        Card 17 shaded has removes_village=True."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": {}, "New_York": {}},
            available={},
        )
        card = {"id": 17}
        assert bot._faction_event_conditions(state, card) is False

    def test_removes_village_present_on_map(self):
        """removes_village with a Village on map → returns True."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": {C.VILLAGE: 1}, "New_York": {}},
            available={},
        )
        card = {"id": 17}
        assert bot._faction_event_conditions(state, card) is True


# =======================================================================
#  INDIAN BOT — places_village / removes_patriot_fort
# =======================================================================

class TestIndianEventAvailability:
    """Indian bot checks for piece availability at runtime."""

    def test_no_villages_available_returns_false(self):
        """places_village with zero Villages in Available → returns False.
        Card 72 unshaded has places_village=True."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Boston": {}},
            available={},  # no Villages
        )
        card = {"id": 72}
        assert bot._faction_event_conditions(state, card) is False

    def test_villages_available_returns_true(self):
        """Add 1 Village to Available → returns True."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Boston": {}},
            available={C.VILLAGE: 1},
        )
        card = {"id": 72}
        assert bot._faction_event_conditions(state, card) is True

    def test_removes_patriot_fort_none_on_map(self):
        """removes_patriot_fort with zero Patriot Forts on map → returns
        False. Card 73 unshaded has removes_patriot_fort=True."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Boston": {}, "New_York": {}},
            available={},
        )
        card = {"id": 73}
        assert bot._faction_event_conditions(state, card) is False

    def test_removes_patriot_fort_present_on_map(self):
        """Patriot Fort on the map → returns True."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Boston": {C.FORT_PAT: 1}, "New_York": {}},
            available={},
        )
        card = {"id": 73}
        assert bot._faction_event_conditions(state, card) is True
