"""§2.3.9/§5.1.1 apply even to French deployment granted by Events."""
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.pieces import move_piece
from lod_ai.bots.free_op_planner import plan_free_march
from lod_ai.cards.effects import brilliant_stroke, early_war, late_war, middle_war
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.util.free_ops import queue_free_op


def _state(*spaces, treaty=False):
    return {
        "spaces": {sid: {} for sid in spaces},
        "available": {C.REGULAR_FRE: 8, C.REGULAR_PAT: 4, C.MILITIA_U: 4},
        "unavailable": {}, "casualties": {}, "markers": {},
        "resources": {fac: 0 for fac in (C.BRITISH, C.FRENCH, C.PATRIOTS, C.INDIANS)},
        "support": {}, "control": {}, "active": C.FRENCH,
        "toa_played": treaty, "rng": random.Random(1),
    }


@pytest.mark.parametrize("destination", ["Quebec", C.WEST_INDIES_ID])
@pytest.mark.parametrize("source", ["available", "unavailable", "casualties"])
def test_pre_treaty_deployment_leaves_source_pool_intact(destination, source):
    state = _state(destination)
    state[source][C.REGULAR_FRE] = 3
    assert move_piece(state, C.REGULAR_FRE, source, destination, 2) == 0
    assert state[source][C.REGULAR_FRE] == 3
    assert state["spaces"][destination].get(C.REGULAR_FRE, 0) == 0


@pytest.mark.parametrize("treaty", [False, True])
@pytest.mark.parametrize("card", [50, 57, 85])
def test_direct_french_deployment_obeys_treaty_and_keeps_legal_effects(card, treaty):
    state = _state("Georgia", "Southwest", C.WEST_INDIES_ID, treaty=treaty)
    if card == 50:
        state["card50_colony"] = "Georgia"
        middle_war.evt_050_destaing_arrives(state, shaded=True)
        target = "Georgia"
        assert state["spaces"][target].get(C.REGULAR_PAT) == 2
    elif card == 57:
        late_war.evt_057_french_caribbean(state)
        target = C.WEST_INDIES_ID
        assert C.FRENCH in state["ineligible_through_next"]
    else:
        late_war.evt_085_mississippi_raids(state, shaded=True)
        target = "Southwest"
        assert state["spaces"][target].get(C.MILITIA_U) == 2
    expected = 2 if treaty else 0
    assert state["spaces"][target].get(C.REGULAR_FRE, 0) == expected
    assert state["available"][C.REGULAR_FRE] == 8 - expected


def test_card62_default_uses_legal_militia_branch_before_treaty():
    state = _state("Northwest", "Quebec")
    late_war.evt_062_langlade(state, shaded=True)
    assert state["spaces"]["Northwest"][C.MILITIA_U] == 3
    assert state["available"][C.REGULAR_FRE] == 8


def test_card62_explicit_french_choice_cannot_override_treaty_gate():
    state = _state("Northwest", "Quebec")
    state["card62_shaded_choice"] = "FRENCH_QUEBEC"
    late_war.evt_062_langlade(state, shaded=True)
    assert state["spaces"]["Quebec"].get(C.REGULAR_FRE, 0) == 0
    assert state["available"][C.REGULAR_FRE] == 8


@pytest.mark.parametrize("actor", [C.FRENCH, C.PATRIOTS])
def test_card62_post_treaty_defaults_to_executing_factions_units(actor):
    state = _state("Northwest", "Quebec", treaty=True)
    state["active"] = actor
    late_war.evt_062_langlade(state, shaded=True)
    expected_tag, target = ((C.REGULAR_FRE, "Quebec") if actor == C.FRENCH
                            else (C.MILITIA_U, "Northwest"))
    assert state["spaces"][target][expected_tag] == 3


@pytest.mark.parametrize("actor", [C.FRENCH, C.PATRIOTS])
def test_card62_uses_ally_when_executors_pieces_are_unavailable(actor):
    state = _state("Northwest", "Quebec", treaty=True)
    state["active"] = actor
    state["available"][C.REGULAR_FRE if actor == C.FRENCH else C.MILITIA_U] = 0
    late_war.evt_062_langlade(state, shaded=True)
    expected_tag, target = ((C.MILITIA_U, "Northwest") if actor == C.FRENCH
                            else (C.REGULAR_FRE, "Quebec"))
    assert state["spaces"][target][expected_tag] == 3


def test_card62_specific_french_bot_instruction_preserves_militia_choice():
    state = _state("Northwest", "Quebec", treaty=True)
    state["card62_shaded_choice"] = "MILITIA_NORTHWEST"
    late_war.evt_062_langlade(state, shaded=True)
    assert state["spaces"]["Northwest"][C.MILITIA_U] == 3
    assert state["available"][C.REGULAR_FRE] == 8


@pytest.mark.parametrize("card", [72, 83, 95])
def test_generic_friendly_placement_cannot_deploy_french_before_treaty(card):
    state = _state("Northwest", "Quebec", "Quebec_City")
    if card == 72:
        # Force the generic fallback list to reach its French entry.
        state["available"] = {C.REGULAR_FRE: 8}
        early_war.evt_072_french_settlers(state)
    elif card == 83:
        state["card83_target"] = "Quebec_City"
        early_war.evt_083_carleton_negotiates(state, shaded=True)
        assert state["spaces"]["Quebec_City"].get(C.MILITIA_U) == 3
    else:
        late_war.evt_095_ohio_frontier(state)
        assert state["spaces"]["Northwest"].get(C.MILITIA_U) == 3
    assert all(sp.get(C.REGULAR_FRE, 0) == 0 for sp in state["spaces"].values())
    assert state["available"][C.REGULAR_FRE] == 8


def test_card49_preparations_pool_transfers_remain_legal_before_treaty():
    state = _state(C.WEST_INDIES_ID)
    early_war.evt_049_st_germain(state)
    assert state["unavailable"][C.REGULAR_FRE] == 5
    early_war.evt_049_st_germain(state, shaded=True)
    assert state["available"][C.REGULAR_FRE] == 8


def test_treaty_itself_opens_gate_before_placing_regulars():
    state = build_state("1775", seed=1)
    state["cbc"] = 20
    assert brilliant_stroke.apply_treaty_of_alliance(state)
    assert state["toa_played"]
    assert state["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_FRE) == 3


@pytest.mark.parametrize("actor", [C.FRENCH, C.PATRIOTS])
@pytest.mark.parametrize("treaty", [False, True])
def test_card66_default_benefits_executing_faction_when_legal(actor, treaty):
    state = _state("Florida", treaty=treaty)
    state["active"] = actor
    late_war.evt_066_don_bernardo(state, shaded=True)
    expected = actor if treaty else C.PATRIOTS
    assert state["free_ops"] == [(expected, "march", "Florida"),
                                 (expected, "battle_plus2", "Florida")]


def test_free_french_march_declines_pre_treaty_even_with_stale_illegal_pieces():
    state = _state("Georgia", "Florida")
    state["spaces"]["Georgia"][C.REGULAR_FRE] = 3
    assert plan_free_march(state, C.FRENCH, "Florida") is None


def test_free_operation_execution_error_is_recorded_distinctly(monkeypatch):
    engine = Engine(initial_state=build_state("1775", seed=1))
    queue_free_op(engine.state, C.PATRIOTS, "march", "Florida")
    monkeypatch.setattr(engine, "_plan_bot_free_op", lambda *args: {"space": "Florida"})

    def reject(*args, **kwargs):
        raise ValueError("invalid test plan")

    monkeypatch.setattr(engine.dispatcher, "execute", reject)
    engine._drain_free_ops(engine.state, card_id=66)
    assert engine.state["_free_op_error_log"] == [{
        "faction": C.PATRIOTS, "operation": "march", "location": "Florida",
        "card_id": 66, "error_type": "ValueError", "message": "invalid test plan",
    }]
    assert "bs_free" not in engine.state


def test_legal_pre_treaty_free_march_decline_is_not_an_execution_error():
    engine = Engine(initial_state=build_state("1775", seed=1))
    queue_free_op(engine.state, C.FRENCH, "march", "Florida")
    engine._drain_free_ops(engine.state, card_id=66)
    assert not engine.state.get("_free_op_error_log")
    assert any("declined (no legal plan)" in entry["msg"]
               for entry in engine.state["history"])
