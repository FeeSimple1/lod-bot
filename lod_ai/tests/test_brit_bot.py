import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.british_bot import BritishBot


def simple_state():
    return {
        "spaces": {
            "Boston": {"British_Regulars": 2, "Patriot_Militia_A": 1, "adj": ["New_York"]},
            "New_York": {"British_Regulars": 1, "adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"British_Regulars": 5, "Tory": 5},
        "rng": __import__('random').Random(1),
        "history": [],
    }


def test_british_bot_turn():
    state = simple_state()
    card = json.loads(open('lod_ai/cards/data.json').read())[0]
    bot = BritishBot()
    bot.take_turn(state, card)
    assert state.get("history")
