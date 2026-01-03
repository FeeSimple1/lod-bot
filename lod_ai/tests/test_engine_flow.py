import sys

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.cards import CARD_HANDLERS


def _pass_decider(faction, card, allowed, engine):
    return {"action": "pass", "used_special": False}, True, None, None


def test_year_end_runs_only_for_winter_cards(monkeypatch):
    calls = []
    monkeypatch.setattr("lod_ai.engine.resolve_year_end", lambda state: calls.append(True))
    engine = Engine()
    engine.set_human_factions({C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS})

    normal_card = {"id": 9001, "title": "Test", "order": [C.BRITISH, C.PATRIOTS], "winter_quarters": False}
    engine.play_card(normal_card, human_decider=_pass_decider)
    assert calls == []

    winter_card = {"id": 9002, "title": "Winter", "order": [C.BRITISH, C.PATRIOTS], "winter_quarters": True}
    engine.play_card(winter_card, human_decider=_pass_decider)
    assert calls == [True]


def test_passing_awards_resources_and_keeps_eligibility():
    engine = Engine()
    engine.set_human_factions({C.BRITISH, C.PATRIOTS})
    start = dict(engine.state["resources"])

    card = {"id": 9003, "title": "Pass Check", "order": [C.BRITISH, C.PATRIOTS], "winter_quarters": False}
    engine.play_card(card, human_decider=_pass_decider)

    assert engine.state["resources"][C.BRITISH] == start[C.BRITISH] + 2
    assert engine.state["resources"][C.PATRIOTS] == start[C.PATRIOTS] + 1
    eligible_next = engine.state.get("eligible_next", set())
    assert C.BRITISH in eligible_next
    assert C.PATRIOTS in eligible_next


def test_card_handlers_auto_import():
    assert "lod_ai.cards.effects.early_war" in sys.modules
    assert 2 in CARD_HANDLERS
    assert 24 in CARD_HANDLERS
