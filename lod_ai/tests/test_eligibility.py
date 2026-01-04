import json
from pathlib import Path

from lod_ai.cards import determine_eligible_factions
from lod_ai.state import setup_state
from lod_ai.engine import Engine
from lod_ai import rules_consts as C


def test_initial_state_has_eligible(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
        "deck": [],
    }
    path = tmp_path / "scen.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)
    state = setup_state.build_state(path.name)
    assert state["eligible"] == {
        C.BRITISH: True,
        C.PATRIOTS: True,
        C.FRENCH: True,
        C.INDIANS: True,
    }


def test_determine_eligible_factions():
    card = {"order_icons": "PBFI"}
    state = {"eligible": {C.BRITISH: True, C.PATRIOTS: True, C.FRENCH: True, C.INDIANS: True}}
    assert determine_eligible_factions(state, card) == (C.PATRIOTS, C.BRITISH)
    state["eligible"][C.PATRIOTS] = False
    assert determine_eligible_factions(state, card) == (C.BRITISH, C.FRENCH)


def test_engine_turn_marks_ineligible(tmp_path, monkeypatch):
    card_path = Path(__file__).resolve().parents[2] / "lod_ai" / "cards" / "data.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    state = {
        "spaces": {
            "Boston": {"British_Regular": 1, "adj": ["New_York"]},
            "New_York": {"adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"British_Regular": 5, "Tory": 5},
        "rng": __import__('random').Random(1),
        "history": [],
        "support": {"Boston": 0, "New_York": 0},
        "casualties": {},
        "eligible": {
            C.BRITISH: True,
            C.PATRIOTS: True,
            C.FRENCH: True,
            C.INDIANS: True,
        },
    }
    monkeypatch.setattr("lod_ai.engine.resolve_year_end", lambda s: None)
    engine = Engine(state)
    engine.play_turn("BRITISH", card=card)
    assert state["eligible"][C.BRITISH] is False
    assert C.BRITISH in state.get("ineligible_next", set())


def test_play_card_orders_and_skips(monkeypatch):
    card = {"order_icons": "PBFI"}
    state = {
        "spaces": {},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "eligible": {
            C.BRITISH: True,
            C.PATRIOTS: True,
            C.FRENCH: True,
            C.INDIANS: True,
        },
        "ineligible_next": {C.PATRIOTS},
    }
    engine = Engine(state)

    calls = []

    def stub_turn(self, faction, card=None):
        calls.append(faction)
        self.state["eligible"][faction] = False

    monkeypatch.setattr(Engine, "play_turn", stub_turn)
    engine.play_card(card)

    assert calls == [C.BRITISH, C.FRENCH]
    assert state["eligible"][C.BRITISH] is False
    assert state["eligible"][C.FRENCH] is False
    assert state.get("ineligible_next", set()) == set()


def test_eligibility_resets_each_card(monkeypatch):
    def _pass_decider(faction, card, allowed, engine):
        return {"action": "pass", "used_special": False}, True, None, None

    state = {
        "spaces": {},
        "resources": {C.BRITISH: 1, C.PATRIOTS: 1, C.FRENCH: 1, C.INDIANS: 1},
        "available": {C.REGULAR_BRI: 1, C.REGULAR_PAT: 1},
        "eligible": {
            C.BRITISH: True,
            C.PATRIOTS: True,
            C.FRENCH: True,
            C.INDIANS: True,
        },
        "ineligible_next": {C.BRITISH},
        "rng": __import__('random').Random(1),
        "support": {},
        "history": [],
    }
    engine = Engine(state)
    engine.set_human_factions({C.PATRIOTS, C.FRENCH})

    card_one = {"id": 2001, "title": "Card One", "order": [C.PATRIOTS, C.FRENCH]}
    engine.play_card(card_one, human_decider=_pass_decider)

    queue = engine._prepare_card({"id": 2002, "title": "Card Two", "order": [C.BRITISH, C.PATRIOTS]})
    assert C.BRITISH in queue
