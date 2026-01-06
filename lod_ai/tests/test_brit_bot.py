import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.british_bot import BritishBot


def simple_state():
    return {
        "spaces": {
            "Boston": {"British_Regular": 2, "Patriot_Militia_A": 1, "adj": ["New_York"]},
            "New_York": {"British_Regular": 1, "adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"British_Regular": 5, "British_Tory": 5},
        "rng": __import__('random').Random(1),
        "history": [],
        "support": {"Boston": 0, "New_York": 0},
        "casualties": {},
    }


def test_british_bot_turn():
    state = simple_state()
    card_path = Path(__file__).resolve().parents[2] / 'lod_ai' / 'cards' / 'data.json'
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    bot = BritishBot()
    bot.take_turn(state, card)
    assert state.get("history")
