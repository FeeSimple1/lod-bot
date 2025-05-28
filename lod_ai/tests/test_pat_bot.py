import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.patriot import PatriotBot


def simple_state():
    return {
        "spaces": {
            "Boston": {"Patriot_Militia_A": 1, "British_Regulars": 1, "adj": ["New_York"]},
            "New_York": {"Patriot_Militia_A": 1, "adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 3, "FRENCH": 5, "INDIANS": 5},
        "available": {"Patriot_Continentals": 5},
        "rng": __import__('random').Random(1),
        "history": [],
    }


def test_patriot_bot_turn():
    state = simple_state()
    card = json.loads(open('lod_ai/cards/data.json').read())[0]
    bot = PatriotBot()
    bot.take_turn(state, card)
    assert state.get("history")

