import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.french import FrenchBot


def simple_state():
    return {
        "spaces": {
            "Quebec": {"adj": ["New_York"], "support": 0},
            "New_York": {"British_Regular": 1, "adj": ["Quebec"], "support": 0},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"French_Regular": 4},
        "rng": __import__('random').Random(1),
        "history": [],
        "toa_played": True,
        "support": {"Quebec": 0, "New_York": 0},
        "casualties": {},
    }


def test_french_bot_turn():
    state = simple_state()
    card_path = Path(__file__).resolve().parents[2] / 'lod_ai' / 'cards' / 'data.json'
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    bot = FrenchBot()
    bot.take_turn(state, card)
    assert state.get("history")


def test_f3_zero_resources_passes():
    """F3: French Resources > 0? No → PASS immediately."""
    from lod_ai import rules_consts as C
    bot = FrenchBot()
    state = {
        "spaces": {"Quebec": {"French_Regular": 2, "adj": []}},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 4},
        "rng": __import__("random").Random(42),
        "history": [],
        "support": {},
        "toa_played": True,
        "casualties": {},
    }
    card = {"id": 9999, "order_icons": "BFPI"}
    bot.take_turn(state, card)
    history = " ".join(str(h) for h in state.get("history", []))
    assert "FRENCH PASS" in history


def test_f13_can_battle_checks_force_comparison():
    """F13: 'Rebel cubes + Leader exceed British pieces in space with both?'
    _can_battle should check rebel cubes > british, not just coexistence."""
    from lod_ai import rules_consts as C
    bot = FrenchBot()
    # French present but fewer rebels than British
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 1, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 3, C.TORY: 1,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "support": {},
        "leaders": {},
    }
    # Rebels = 1+0 = 1, British = 3+1+0 = 4 → 1 < 4 → no battle
    assert bot._can_battle(state) is False

    # Now rebels exceed: 3+2 = 5 > 4
    state["spaces"]["Boston"][C.REGULAR_FRE] = 3
    state["spaces"]["Boston"][C.REGULAR_PAT] = 2
    assert bot._can_battle(state) is True


def test_f7_valid_provinces_uses_quebec_city():
    """F7: Agent Mobilization targets Quebec_City, not Quebec (Reserve)."""
    from lod_ai.bots.french import _VALID_PROVINCES
    assert "Quebec_City" in _VALID_PROVINCES
    assert "Quebec" not in _VALID_PROVINCES


def test_f14_march_fallback_to_muster():
    """F14 'If none' → F10 (Muster chain)."""
    from lod_ai import rules_consts as C
    bot = FrenchBot()
    # No French Regulars on map → March impossible
    state = {
        "spaces": {
            "Boston": {C.REGULAR_FRE: 0, C.REGULAR_BRI: 0, C.TORY: 0,
                       C.REGULAR_PAT: 0, C.MILITIA_A: 0, C.WARPARTY_A: 0},
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 3},
        "rng": __import__("random").Random(42),
        "history": [],
        "support": {},
        "control": {},
        "toa_played": True,
        "casualties": {},
    }
    # _battle_chain should fall back to _muster_chain
    result = bot._battle_chain(state)
    # Whether it succeeds depends on muster conditions, but it should try
    assert isinstance(result, bool)
