import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.french import FrenchBot


def simple_state():
    return {
        "spaces": {
            "Quebec": {"adj": ["New_York"], "support": 0},
            "New_York": {"British_Regulars": 1, "adj": ["Quebec"], "support": 0},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"French_Regulars": 4},
        "rng": __import__('random').Random(1),
        "history": [],
        "toa_played": True,
    }


def test_french_bot_turn():
    state = simple_state()
    card = json.loads(open('lod_ai/cards/data.json').read())[0]
    bot = FrenchBot()
    bot.take_turn(state, card)
    assert state.get("history")
