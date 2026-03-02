"""Tests for per-faction sword/musket icon checks in BaseBot._choose_event_vs_flowchart.

The sword and musket icons are per-faction, not global. Only the faction whose
own icon is SWORD should skip the event; only the faction whose own icon is
MUSKET should consult the instruction sheet. Other factions on the same card
should evaluate _faction_event_conditions normally.
"""

import json
from pathlib import Path
from unittest.mock import patch

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.indians import IndianBot
from lod_ai.bots.french import FrenchBot


def _load_card(card_id: int) -> dict:
    data_path = Path(__file__).resolve().parents[1] / "cards" / "data.json"
    with open(data_path) as f:
        cards = json.load(f)
    return next(c for c in cards if c["id"] == card_id)


def _minimal_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.INDIANS: 5, C.FRENCH: 5},
        "available": {},
        "unavailable": {},
        "support": {},
        "control": {},
        "casualties": {},
        "history": [],
    }


# ===================================================================
# Card 17: French has SWORD — only French should skip
# ===================================================================

class TestCard17FrenchSword:
    def test_patriot_does_not_skip(self):
        """PatriotBot should NOT skip the event on Card 17 (French SWORD)."""
        bot = PatriotBot()
        card = _load_card(17)
        state = _minimal_state()
        # Patch _is_ineffective_event (would otherwise return True on minimal state)
        # and _faction_event_conditions to return True so we can detect
        # that the bot reaches that branch (not blocked by sword).
        with patch.object(BaseBot, "_is_ineffective_event", return_value=False):
            with patch.object(PatriotBot, "_faction_event_conditions", return_value=True):
                with patch.object(PatriotBot, "_execute_event"):
                    result = bot._choose_event_vs_flowchart(state, card)
        # Should reach _faction_event_conditions and return True
        assert result is True

    def test_french_skips(self):
        """FrenchBot SHOULD skip the event on Card 17 (French has SWORD)."""
        bot = FrenchBot()
        card = _load_card(17)
        state = _minimal_state()
        # French has SWORD — should return False immediately, before any other check
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is False


# ===================================================================
# Card 9: Indians has SWORD — only Indians should skip
# ===================================================================

class TestCard9IndianSword:
    def test_british_does_not_skip(self):
        """BritishBot should NOT skip the event on Card 9 (Indian SWORD)."""
        bot = BritishBot()
        card = _load_card(9)
        state = _minimal_state()
        with patch.object(BaseBot, "_is_ineffective_event", return_value=False):
            with patch.object(BritishBot, "_faction_event_conditions", return_value=True):
                with patch.object(BritishBot, "_execute_event"):
                    result = bot._choose_event_vs_flowchart(state, card)
        assert result is True

    def test_indian_skips(self):
        """IndianBot SHOULD skip the event on Card 9 (Indians has SWORD)."""
        bot = IndianBot()
        card = _load_card(9)
        state = _minimal_state()
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is False


# ===================================================================
# Card 44: BRITISH/INDIANS/PATRIOTS=MUSKET, FRENCH=SWORD
# ===================================================================

class TestCard44Mixed:
    def test_french_skips_sword(self):
        """FrenchBot has SWORD on Card 44 — should skip."""
        bot = FrenchBot()
        card = _load_card(44)
        state = _minimal_state()
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is False

    def test_british_gets_musket(self):
        """BritishBot has MUSKET on Card 44 — should consult instruction sheet."""
        bot = BritishBot()
        card = _load_card(44)
        state = _minimal_state()
        # Patch _event_directive to return "ignore" so we can verify the
        # musket branch is reached (not blocked by sword or falling through).
        with patch.object(BritishBot, "_event_directive", return_value="ignore"):
            result = bot._choose_event_vs_flowchart(state, card)
        assert result is False  # "ignore" directive → return False

    def test_indians_gets_musket(self):
        """IndianBot has MUSKET on Card 44 — should consult instruction sheet."""
        bot = IndianBot()
        card = _load_card(44)
        state = _minimal_state()
        with patch.object(IndianBot, "_event_directive", return_value="force"):
            with patch.object(IndianBot, "_execute_event"):
                result = bot._choose_event_vs_flowchart(state, card)
        assert result is True  # "force" directive → execute event

    def test_patriots_gets_musket(self):
        """PatriotBot has MUSKET on Card 44 — should consult instruction sheet."""
        bot = PatriotBot()
        card = _load_card(44)
        state = _minimal_state()
        with patch.object(PatriotBot, "_event_directive", return_value="ignore"):
            result = bot._choose_event_vs_flowchart(state, card)
        assert result is False


# ===================================================================
# Card 1: No icons at all — all factions use _faction_event_conditions
# ===================================================================

class TestCard1NoIcons:
    def test_all_factions_evaluate_normally(self):
        """With no icons, all factions should reach _faction_event_conditions."""
        card = _load_card(1)
        state = _minimal_state()
        for BotClass in (BritishBot, PatriotBot, IndianBot, FrenchBot):
            bot = BotClass()
            with patch.object(BaseBot, "_is_ineffective_event", return_value=False):
                with patch.object(BotClass, "_faction_event_conditions", return_value=True):
                    with patch.object(BotClass, "_execute_event"):
                        result = bot._choose_event_vs_flowchart(state, card)
            assert result is True, f"{BotClass.__name__} should evaluate event conditions normally"
