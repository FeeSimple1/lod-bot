import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.patriot import PatriotBot
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {"Patriot_Militia_A": 1, "British_Regular": 1, "adj": ["New_York"]},
            "New_York": {"Patriot_Militia_A": 1, "adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 3, "FRENCH": 5, "INDIANS": 5},
        "available": {"Patriot_Continental": 5},
        "rng": __import__('random').Random(1),
        "history": [],
        "support": {"Boston": 0, "New_York": 0},
        "casualties": {},
    }


def test_patriot_bot_turn():
    state = simple_state()
    card_path = Path(__file__).resolve().parents[2] / 'lod_ai' / 'cards' / 'data.json'
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    bot = PatriotBot()
    bot.take_turn(state, card)
    assert state.get("history")


def test_p6_battle_uses_cubes_not_militia():
    """P6: 'Rebel cubes + Leader > Active British' — Militia are NOT cubes."""
    bot = PatriotBot()
    # Only Militia, no Continentals or French Regulars → 0 cubes
    state = {
        "spaces": {
            "Boston": {
                C.MILITIA_A: 5,
                C.MILITIA_U: 3,
                C.REGULAR_PAT: 0,
                C.REGULAR_FRE: 0,
                C.REGULAR_BRI: 2,
                C.TORY: 1,
                C.WARPARTY_A: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {},
        "control": {},
    }
    # 0 cubes + 0 leader → 0 vs 3 Royal → no battle
    assert bot._battle_possible(state) is False

    # Add Continentals: 3 cubes + 0 leader = 3 vs 3 → not exceeded
    state["spaces"]["Boston"][C.REGULAR_PAT] = 3
    assert bot._battle_possible(state) is False

    # Add Washington: 3 + 1 = 4 > 3 → battle possible
    state["leaders"] = {"Boston": "LEADER_WASHINGTON"}
    assert bot._battle_possible(state) is True


def test_p2_event_checks_shaded_text():
    """P2: Patriots play shaded events, so conditions should check shaded text."""
    bot = PatriotBot()
    state = {
        "spaces": {},
        "resources": {C.PATRIOTS: 5},
        "support": {},
        "available": {},
    }
    # Card with Support/Opposition in shaded text only
    card_shaded = {
        "id": 9999,
        "unshaded_event": "British gain 3 Resources.",
        "shaded_event": "Shift 2 spaces toward Opposition.",
    }
    # Support > Opposition triggers the first bullet
    state["support"] = {"Boston": 1}
    assert bot._faction_event_conditions(state, card_shaded) is True

    # Same card but no relevant text in shaded
    card_no_match = {
        "id": 9998,
        "unshaded_event": "Shift toward Opposition.",
        "shaded_event": "Draw a card.",
    }
    state["support"] = {"Boston": 1}
    assert bot._faction_event_conditions(state, card_no_match) is False
