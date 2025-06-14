import json
from pathlib import Path

from lod_ai.cards import determine_eligible_factions
from lod_ai.engine import Engine
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "eligible": {
            C.BRITISH: True,
            C.PATRIOTS: True,
            C.FRENCH: True,
            C.INDIANS: True,
        },
        "rng": __import__('random').Random(1),
        "history": [],
    }


def load_first_card():
    card_path = Path(__file__).resolve().parents[2] / "lod_ai" / "cards" / "data.json"
    return json.loads(card_path.read_text())[0]


def test_determine_eligible_skips_ineligible():
    card = load_first_card()
    state = simple_state()
    assert determine_eligible_factions(state, card) == (C.PATRIOTS, C.BRITISH)
    state["eligible"][C.PATRIOTS] = False
    assert determine_eligible_factions(state, card) == (C.BRITISH, C.FRENCH)


def test_action_sets_ineligible_next(monkeypatch):
    state = simple_state()
    card = load_first_card()
    monkeypatch.setattr("lod_ai.engine.resolve_year_end", lambda s: None)
    monkeypatch.setattr("lod_ai.util.free_ops.pop_free_ops", lambda s, f: [])
    monkeypatch.setattr("lod_ai.board.control.refresh_control", lambda s: None)
    monkeypatch.setattr("lod_ai.util.caps.enforce_global_caps", lambda s: None)
    engine = Engine(state)
    engine.bots[C.BRITISH].take_turn = lambda *a, **k: None
    engine.play_turn(C.BRITISH, card=card)
    assert C.BRITISH in state.get("ineligible_next", set())

    next_card = {"order_icons": "PBFI"}
    order = engine._start_card(next_card)
    assert state["eligible"][C.BRITISH] is False
    assert order == (C.PATRIOTS, C.FRENCH)
