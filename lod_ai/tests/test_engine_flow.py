import sys

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.commands import march
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


def test_winter_quarters_card_skips_actions(monkeypatch):
    calls = []
    monkeypatch.setattr("lod_ai.engine.resolve_year_end", lambda state: calls.append(True))
    engine = Engine()
    engine.set_human_factions({C.BRITISH})

    def _raising_decider(*args, **kwargs):
        raise AssertionError("human_decider should not be called for Winter Quarters")

    wq_card = {"id": 9100, "title": "Winter", "order": [C.BRITISH], "winter_quarters": True}
    actions = engine.play_card(wq_card, human_decider=_raising_decider)

    assert actions == []
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


def test_winter_quarters_swap():
    engine = Engine()
    engine.state["deck"] = [
        {"id": 5000, "title": "Event A", "order": [], "winter_quarters": False},
        {"id": 6000, "title": "WQ", "order": [], "winter_quarters": True},
    ]
    engine.state.pop("upcoming_card", None)
    card = engine.draw_card()
    assert card["id"] == 6000
    assert engine.state["current_card"]["id"] == 6000
    assert engine.state["upcoming_card"]["id"] == 5000


def test_dual_use_event_side_choice(monkeypatch):
    calls = []

    def handler(state, shaded=False):
        calls.append(shaded)

    monkeypatch.setitem(CARD_HANDLERS, 9999, handler)
    engine = Engine()
    card = {"id": 9999, "title": "Dual", "dual": True, "unshaded_event": "U", "shaded_event": "S"}

    engine.handle_event(C.PATRIOTS, card, shaded=False)
    engine.handle_event(C.PATRIOTS, card, shaded=True)
    assert calls == [False, True]


def test_bot_event_drains_free_ops(monkeypatch):
    """Free ops queued by a card handler should be drained after a bot turn."""
    from lod_ai.util.free_ops import queue_free_op

    executed_ops = []

    def fake_handler(state, shaded=False):
        queue_free_op(state, C.PATRIOTS, "march", "Boston")

    monkeypatch.setitem(CARD_HANDLERS, 8888, fake_handler)

    engine = Engine()
    engine.state["spaces"].setdefault("Boston", {})

    # Monkeypatch the dispatcher to record free op execution
    original_execute = engine.dispatcher.execute

    def tracking_execute(*args, **kwargs):
        executed_ops.append((args, kwargs))

    monkeypatch.setattr(engine.dispatcher, "execute", tracking_execute)

    card = {"id": 8888, "title": "Free Op Test", "order": [C.PATRIOTS],
            "winter_quarters": False, "unshaded_event": "text"}
    engine.handle_event(C.PATRIOTS, card)

    # After handle_event, free ops should have been drained
    assert engine.state.get("free_ops", []) == []
    assert len(executed_ops) == 1


def test_march_move_plan_moves_only_selected(monkeypatch):
    import random

    state = {
        "spaces": {
            "Quebec_City": {C.REGULAR_PAT: 2},
            "Quebec": {},
        },
        "resources": {C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
        "available": {C.REGULAR_PAT: 10},
        "unavailable": {},
        "markers": {},
        "support": {"Quebec_City": 0, "Quebec": 0},
        "rng": random.Random(1),
    }
    engine = Engine(initial_state=state)
    move_plan = [{"src": "Quebec_City", "dst": "Quebec", "pieces": {C.REGULAR_PAT: 1}}]
    march.execute(engine.state, C.PATRIOTS, engine.ctx, [], ["Quebec"], move_plan=move_plan)

    assert engine.state["spaces"]["Quebec_City"].get(C.REGULAR_PAT, 0) == 1
    assert engine.state["spaces"]["Quebec"].get(C.REGULAR_PAT, 0) == 1
