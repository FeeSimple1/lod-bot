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
