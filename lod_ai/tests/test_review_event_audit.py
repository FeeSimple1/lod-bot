"""§8.3.3 decisions versus complete event and contingent Battle outcomes."""
from copy import deepcopy
import random
from types import SimpleNamespace

import pytest

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.cards import CARD_HANDLERS
from lod_ai.commands.battle import _roll_d3
from lod_ai.engine import Engine
from lod_ai.save_game import _serialize_state, _deserialize_state
from lod_ai.state.setup_state import build_state
from lod_ai.tools.invariants import _rules_property_violations
from lod_ai.util.event_audit import record_choice, support_difference


CARD = {"id": 9908, "dual": False}


def bot(monkeypatch, effect, conditions=None):
    obj = BaseBot()
    obj.faction = C.BRITISH
    monkeypatch.setitem(CARD_HANDLERS, CARD["id"], effect)
    obj._faction_event_conditions = conditions or (lambda state, card: True)
    return obj


def violations(state):
    return [v for v in _rules_property_violations(state, None) if "S8.3.3" in v]


def snapshot(state):
    serialized = _serialize_state(state, set())
    serialized.pop("_save_meta", None)
    return serialized


def test_harmful_deterministic_event_is_rejected(monkeypatch):
    st = build_state("1776", seed=1)
    obj = bot(monkeypatch, lambda state, **kw: state["support"].update(Boston=-2))
    before = deepcopy(st["support"])
    assert not obj._choose_event_vs_flowchart(st, CARD)
    assert st["support"] == before
    assert obj._event_choice_preview["d_after"] < obj._event_choice_preview["d_before"]


@pytest.mark.parametrize("field", ["no_effect", "only_friendly_removal"])
def test_independent_preview_evidence_rejects_wrongly_accepted_event(field):
    st = build_state("1776", seed=1)
    record_choice(st, C.BRITISH, CARD, support_difference(st), 0,
                  {"d_before": 1, "d_after": 2, field: True})
    assert violations(st)


def test_harmful_preview_not_hidden_by_lucky_actual_battle():
    st = build_state("1776", seed=1)
    _roll_d3(st)
    record_choice(st, C.BRITISH, CARD, support_difference(st) - 1, 0,
                  {"d_before": 2, "d_after": 1})
    assert any("harmful preview" in v for v in violations(st))


def test_completed_bad_battle_outcome_is_observed_not_illegal():
    st = build_state("1776", seed=1)
    before = support_difference(st)
    st["support"]["Boston"] -= 1
    _roll_d3(st)
    record_choice(st, C.BRITISH, CARD, before, 0,
                  {"d_before": before, "d_after": before + 1})
    assert violations(st) == []
    observed = st["event_outcome_observations"][0]
    assert observed["d_after"] < observed["d_before"]
    assert observed["battle_dice"] == 1


def test_random_space_rng_is_not_a_battle_outcome_exemption():
    st = build_state("1776", seed=1)
    before = support_difference(st)
    st["support"]["Boston"] -= 1
    st["rng_log"] = [("D3", st["rng"].randint(1, 3))]
    record_choice(st, C.BRITISH, CARD, before, 0,
                  {"d_before": before, "d_after": before + 1})
    assert any("completed deterministic" in v for v in violations(st))


def test_audit_waits_for_engine_to_complete_granted_free_operations(monkeypatch):
    st = build_state("1776", seed=1)
    before = support_difference(st)
    st["support"]["Boston"] -= 1
    st["free_ops"] = [(C.PATRIOTS, "battle", "Boston")]
    record_choice(st, C.BRITISH, CARD, before, 0,
                  {"d_before": before, "d_after": before + 1})
    assert violations(st) == []
    assert st["event_choice_audit"][0]["complete"] is False
    st, _ = _deserialize_state(_serialize_state(st, set()))
    assert st["event_choice_audit"][0]["complete"] is False
    eng = Engine.__new__(Engine)
    eng.state, eng.human_factions = st, set()
    eng._plan_bot_free_op = lambda *args: {"space": "Boston"}
    eng.dispatcher = SimpleNamespace(execute=lambda *a, **kw:
                                    st["support"].__setitem__("Boston", 2))
    eng._drain_free_ops(st, CARD["id"])
    entry = st["event_choice_audit"][0]
    assert entry["complete"] is True
    assert entry["d_after"] == support_difference(st)
    assert violations(st) == []


@pytest.mark.parametrize("mode", ["decline", "error", "no_ops"])
def test_followups_resolve_and_clear_even_when_free_operation_does_not_execute(mode):
    from lod_ai.util.free_ops import queue_after_free_ops
    st = build_state("1776", seed=1)
    st["support"]["Boston"] = 2
    if mode != "no_ops":
        st["free_ops"] = [(C.PATRIOTS, "battle", "Boston")]
    queue_after_free_ops(st, "shift_support_toward", space="Boston", target=0, steps=1)
    record_choice(st, C.PATRIOTS, CARD, support_difference(st), 0,
                  {"d_before": 0, "d_after": 0})
    st, _ = _deserialize_state(_serialize_state(st, set()))
    eng = Engine.__new__(Engine)
    eng.state, eng.human_factions = st, set()
    eng._plan_bot_free_op = lambda *args: None if mode == "decline" else {"space": "Boston"}

    def fail(*args, **kwargs):
        raise ValueError("injected free-op failure")

    eng.dispatcher = SimpleNamespace(execute=fail)
    eng._drain_free_ops(st, CARD["id"])
    assert st["support"]["Boston"] == 1
    assert "free_op_followups" not in st
    assert "free_ops" not in st
    assert st["event_choice_audit"][0]["complete"] is True
    assert bool(st.get("_free_op_error_log")) == (mode == "error")


def test_preview_errors_are_structured_diagnostics(monkeypatch):
    st = build_state("1776", seed=1)

    def fail(state, **kwargs):
        raise NameError("missing event constant")

    obj = bot(monkeypatch, fail)
    assert obj._is_ineffective_event(CARD, st)
    assert st["_event_preview_error_log"] == [{
        "faction": C.BRITISH, "card_id": CARD["id"], "error_type": "NameError",
        "message": "missing event constant", "source": "ineffective_event_preview",
    }]


def test_question_spaces_recheck_rejects_changed_harmful_target(monkeypatch):
    from lod_ai.cards.effects.shared import select_support_shift_spaces
    st = build_state("1776", seed=1)
    st["support"].update(Boston=2, Philadelphia=-2)

    def effect(state, **kw):
        target = select_support_shift_spaces(
            state, ["Boston", "Philadelphia"], 1, target=0, steps=1,
            shaded=False)[0]
        state["support"][target] += -1 if state["support"][target] > 0 else 1

    def conditions(state, card):
        state["_event_q_spaces"] = {"Boston"}
        return True

    obj = bot(monkeypatch, effect, conditions)
    assert not obj._is_ineffective_event(CARD, st)  # prefers Opposition loss
    assert not obj._choose_event_vs_flowchart(st, CARD)
    assert st["support"]["Boston"] == 2
    assert "_event_q_spaces" not in st


@pytest.mark.parametrize("faction", [C.PATRIOTS, C.FRENCH])
def test_waxhaws_declined_battle_does_not_hide_harmful_neutral_shift(faction):
    """Card 1 / §5.3: with no Patriot forces, only the follow-ups remain."""
    st = build_state("1776", seed=1)
    for space in st["spaces"].values():
        for tag in (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U):
            pool_tag = C.MILITIA_U if tag == C.MILITIA_A else tag
            st["available"][pool_tag] += space.get(tag, 0)
            space[tag] = 0
    st["support"]["Boston"] = C.PASSIVE_OPPOSITION
    st["_event_q_spaces"] = {"Boston"}
    original = snapshot(st)
    obj = BaseBot()
    obj.faction = faction

    assert obj._is_ineffective_event({"id": 1, "dual": True}, st)

    preview = obj._event_choice_preview
    assert preview["d_after"] == preview["d_before"] + 1
    assert preview["pending_free_ops"] is False
    assert preview["battle_dice"] == 0
    assert snapshot(st) == original


def test_event_condition_die_rechecks_queued_deterministic_target(monkeypatch):
    """The deciding D6 changes target ties even without question spaces."""
    from lod_ai.util.free_ops import queue_after_free_ops
    st = build_state("1776", seed=1)
    st["support"].update(Boston=C.PASSIVE_SUPPORT,
                         Philadelphia=C.PASSIVE_OPPOSITION)
    st["rng"] = random.Random(1)
    # Seed 1 yields D6 = 2, 5: first preview benefits British, next harms.
    def effect(state, **kw):
        target = "Philadelphia" if state["rng"].randint(1, 6) <= 3 else "Boston"
        queue_after_free_ops(state, "shift_support_toward", space=target,
                             target=C.NEUTRAL, steps=1)

    def conditions(state, card):
        state["rng"].randint(1, 6)
        return True

    obj = bot(monkeypatch, effect, conditions)
    assert not obj._is_ineffective_event(CARD, st)
    assert not obj._choose_event_vs_flowchart(st, CARD)
    assert st["support"]["Boston"] == C.PASSIVE_SUPPORT
    assert not st.get("free_op_followups")


def test_queued_combat_preview_uses_known_followup_without_rolling(monkeypatch):
    """Q24: an offered Battle cannot hide a harmful known Neutral shift."""
    from lod_ai.util.free_ops import queue_after_free_ops, queue_free_op
    st = build_state("1776", seed=1)
    st["support"]["Boston"] = C.PASSIVE_SUPPORT

    def effect(state, **kw):
        queue_free_op(state, C.PATRIOTS, "battle", "Boston")
        queue_after_free_ops(state, "shift_support_toward", space="Boston",
                             target=C.NEUTRAL, steps=1)

    monkeypatch.setattr("lod_ai.commands.battle._roll_d3", lambda *args:
                        pytest.fail("must not roll speculative Battle dice"))
    obj = bot(monkeypatch, effect)
    original = snapshot(st)
    assert obj._is_ineffective_event(CARD, st)
    preview = obj._event_choice_preview
    assert preview["d_after"] == preview["d_before"] - 1
    assert preview["pending_free_ops"] is False
    assert preview["battle_dice"] == 0
    assert snapshot(st) == original


def test_preview_does_not_choose_a_human_granted_command(monkeypatch):
    from lod_ai.bots.base_bot import _complete_pre_roll_preview
    from lod_ai.util.free_ops import queue_free_op
    st = build_state("1776", seed=1)
    st["human_factions"] = {C.PATRIOTS}
    queue_free_op(st, C.PATRIOTS, "march", "Boston")
    monkeypatch.setattr(Engine, "_drain_free_ops", lambda *args:
                        pytest.fail("must not plan a human choice"))
    assert _complete_pre_roll_preview(st, 1) is None


@pytest.mark.parametrize("empty_queue", [False, True])
def test_entirely_declined_queued_event_is_ineffective(monkeypatch, empty_queue):
    from lod_ai.util.free_ops import queue_free_op
    st = build_state("1776", seed=1)
    if empty_queue:
        st["free_ops"] = []
    obj = bot(monkeypatch, lambda state, **kw:
              queue_free_op(state, C.FRENCH, "battle", "Boston"))
    assert obj._is_ineffective_event(CARD, st)
    assert obj._event_choice_preview["no_effect"] is True


def test_failed_deterministic_free_operation_is_a_preview_error(monkeypatch):
    from lod_ai.util.free_ops import queue_free_op
    st = build_state("1776", seed=1)
    obj = bot(monkeypatch, lambda state, **kw:
              queue_free_op(state, C.PATRIOTS, "battle", "Boston"))

    def failed_operation(engine, state, card_id):
        state.setdefault("_free_op_error_log", []).append({
            "operation": "battle", "message": "injected planner error"})

    monkeypatch.setattr(Engine, "_drain_free_ops", failed_operation)
    assert obj._is_ineffective_event(CARD, st)
    assert "injected planner error" in st["_event_preview_error_log"][0]["message"]


def test_battle_counter_is_nonsemantic_and_roundtrips(monkeypatch):
    st = build_state("1776", seed=1)
    obj = bot(monkeypatch, lambda state, **kw: None)
    st["_battle_dice_rolled"] = 0
    assert obj._is_ineffective_event(CARD, st)
    _roll_d3(st)
    encoded = _serialize_state(st, set())
    restored, _ = _deserialize_state(encoded)
    assert restored["_battle_dice_rolled"] == 1
    assert restored["rng"].getstate() == st["rng"].getstate()


@pytest.mark.parametrize("space", ["Boston", C.WEST_INDIES_ID])
@pytest.mark.parametrize("treaty", [False, True])
def test_french_before_treaty_guard_catches_conserved_illegal_placement(space, treaty):
    st = build_state("1776", seed=1)
    st["toa_played"] = treaty
    st["available"][C.REGULAR_FRE] -= 1
    st["spaces"][space][C.REGULAR_FRE] += 1
    found = _rules_property_violations(st, None)
    assert any("S2.3.9/S5.1.1" in v for v in found) == (not treaty)
    assert not any("piece conservation" in v for v in found)
