"""Human command checkpoints must preserve financing and move-once rules."""

import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.bots.indians import IndianBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.commands import gather, rabble_rousing, raid, rally
from lod_ai.special_activities import partisans, persuasion, plunder, trade
from lod_ai.util.movement_provenance import MovementProvenance


def _state(spaces, *, resources=None, available=None, support=None):
    state = {
        "spaces": spaces,
        "resources": {C.PATRIOTS: 5, C.INDIANS: 5, C.BRITISH: 5, C.FRENCH: 5,
                      **(resources or {})},
        "available": available or {},
        "casualties": {},
        "support": support or {},
        "control": {},
        "leaders": {},
        "history": [],
        "rng": random.Random(1),
    }
    refresh_control(state)
    return state


def test_persuasion_finances_later_rally_space_after_first_placement():
    state = _state({"New_York": {}, "Massachusetts": {}},
                   resources={C.PATRIOTS: 1}, available={C.MILITIA_U: 2})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts":
            assert st["spaces"]["New_York"].get(C.MILITIA_U) == 1
            assert st["resources"][C.PATRIOTS] == 0
            persuasion.execute(st, C.PATRIOTS, {}, spaces=["New_York"])

    rally.execute(state, C.PATRIOTS, {"_command_checkpoint": checkpoint},
                  ["New_York", "Massachusetts"])

    assert state["resources"][C.PATRIOTS] == 0
    assert state["spaces"]["New_York"].get(C.MILITIA_A) == 1
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U) == 1


def test_persuasion_finances_later_rabble_rousing_space():
    state = _state({"New_York": {C.MILITIA_U: 1},
                    "Massachusetts": {C.MILITIA_U: 1}},
                   resources={C.PATRIOTS: 1})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts":
            assert st["support"]["New_York"] == C.PASSIVE_OPPOSITION
            assert st["resources"][C.PATRIOTS] == 0
            persuasion.execute(st, C.PATRIOTS, {}, spaces=["New_York"])

    rabble_rousing.execute(state, C.PATRIOTS, {"_command_checkpoint": checkpoint},
                           ["New_York", "Massachusetts"])

    assert state["resources"][C.PATRIOTS] == 0
    assert state["support"]["Massachusetts"] == C.PASSIVE_OPPOSITION


def test_trade_finances_gather_after_first_space_places_eligible_war_party():
    state = _state({"New_York": {C.VILLAGE: 1}, "Massachusetts": {}},
                   resources={C.INDIANS: 1}, available={C.WARPARTY_U: 2})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts":
            assert st["resources"][C.INDIANS] == 0
            trade.execute(st, C.INDIANS, {}, "New_York")

    gather.execute(state, C.INDIANS, {"_command_checkpoint": checkpoint},
                   ["New_York", "Massachusetts"])

    assert state["resources"][C.INDIANS] == 0
    assert state["spaces"]["New_York"].get(C.WARPARTY_A) == 1
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_U) == 1


def test_only_first_reserve_is_free_with_interleaved_gather():
    state = _state({"Quebec": {C.VILLAGE: 1}, "Northwest": {}},
                   resources={C.INDIANS: 0}, available={C.WARPARTY_U: 2})

    def checkpoint(st, ctx, label, sid):
        if sid == "Northwest":
            assert st["resources"][C.INDIANS] == 0
            trade.execute(st, C.INDIANS, {}, "Quebec")

    gather.execute(state, C.INDIANS, {"_command_checkpoint": checkpoint},
                   ["Quebec", "Northwest"])

    assert state["resources"][C.INDIANS] == 0
    assert state["spaces"]["Northwest"].get(C.WARPARTY_U) == 1


def test_plunder_finances_remaining_raid_after_first_space():
    state = _state({"New_York": {C.WARPARTY_U: 1, C.WARPARTY_A: 1},
                    "Massachusetts": {C.WARPARTY_U: 1}},
                   resources={C.INDIANS: 1},
                   support={"New_York": C.PASSIVE_OPPOSITION,
                            "Massachusetts": C.PASSIVE_OPPOSITION})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts" and label == "Before resolving Raid":
            assert st["support"]["New_York"] == C.NEUTRAL
            assert st["resources"][C.INDIANS] == 0
            plunder.execute(st, C.INDIANS, ctx, "New_York")

    raid.execute(state, C.INDIANS, {"_command_checkpoint": checkpoint},
                 ["New_York", "Massachusetts"])

    assert state["resources"][C.INDIANS] == 1
    assert state["support"]["Massachusetts"] == C.NEUTRAL


@pytest.mark.parametrize("command,faction,underground,active,base", [
    (rally, C.PATRIOTS, C.MILITIA_U, C.MILITIA_A, C.FORT_PAT),
    (gather, C.INDIANS, C.WARPARTY_U, C.WARPARTY_A, C.VILLAGE),
])
def test_move_and_hide_is_alternative_to_placement(command, faction, underground, active, base):
    state = _state({"New_York": {base: 1, active: 1},
                    "Massachusetts": {active: 1}},
                   available={underground: 3})

    command.execute(state, faction, {}, ["New_York"],
                    move_plan=[("Massachusetts", "New_York", 1)])

    assert state["available"][underground] == 3
    assert state["spaces"]["New_York"].get(underground) == 2
    assert state["spaces"]["New_York"].get(active, 0) == 0
    assert state["spaces"]["Massachusetts"].get(active, 0) == 0


@pytest.mark.parametrize("command,faction,underground,active,base", [
    (rally, C.PATRIOTS, C.MILITIA_U, C.MILITIA_A, C.FORT_PAT),
    (gather, C.INDIANS, C.WARPARTY_U, C.WARPARTY_A, C.VILLAGE),
])
def test_move_option_can_hide_existing_units_without_arrivals(command, faction, underground, active, base):
    state = _state({"New_York": {base: 1, active: 2}}, available={underground: 3})

    command.execute(state, faction, {}, ["New_York"],
                    move_plan=[("New_York", "New_York", 0)])

    assert state["available"][underground] == 3
    assert state["spaces"]["New_York"].get(underground) == 2
    assert state["spaces"]["New_York"].get(active, 0) == 0


@pytest.mark.parametrize("command,faction,underground,base", [
    (rally, C.PATRIOTS, C.MILITIA_U, C.FORT_PAT),
    (gather, C.INDIANS, C.WARPARTY_U, C.VILLAGE),
])
def test_special_activation_cannot_make_arriving_unit_move_again(command, faction, underground, base):
    state = _state({"New_Hampshire": {underground: 1},
                    "New_York": {base: 1}, "Massachusetts": {base: 1}},
                   resources={faction: 1})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts":
            if faction == C.PATRIOTS:
                persuasion.execute(st, faction, {}, spaces=["New_York"])
            else:
                trade.execute(st, faction, {}, "New_York")

    with pytest.raises(ValueError, match="unmoved"):
        command.execute(state, faction, {"_command_checkpoint": checkpoint},
                        ["New_York", "Massachusetts"],
                        move_plan=[("New_Hampshire", "New_York", 1),
                                   ("New_York", "Massachusetts", 1)])

    assert state["spaces"]["Massachusetts"].get(underground, 0) == 0


def test_partisans_can_sacrifice_arrival_and_leave_original_units_movable():
    state = _state({"New_Hampshire": {C.MILITIA_U: 1},
                    "New_York": {C.FORT_PAT: 1, C.MILITIA_U: 2, C.TORY: 2},
                    "Massachusetts": {C.FORT_PAT: 1}})

    def checkpoint(st, ctx, label, sid):
        if sid == "Massachusetts":
            partisans.execute(st, C.PATRIOTS, {}, "New_York", option=2)

    rally.execute(state, C.PATRIOTS, {"_command_checkpoint": checkpoint},
                  ["New_York", "Massachusetts"],
                  move_plan=[("New_Hampshire", "New_York", 1),
                             ("New_York", "Massachusetts", 2)])

    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U) == 2
    assert state["spaces"]["New_York"].get(C.MILITIA_U, 0) == 0
    assert state["spaces"]["New_York"].get(C.MILITIA_A, 0) == 0


def test_unmoved_active_unit_remains_available_beside_moved_underground_unit():
    state = _state({"New_York": {C.MILITIA_U: 1, C.MILITIA_A: 1}})
    provenance = MovementProvenance(C.MILITIA_U, C.MILITIA_A)
    provenance.arrive_and_hide("New_York", 1)

    # The Underground unit has moved; the original Active unit has not.
    assert provenance.take(state, "New_York", 1) == (0, 1)
    state["spaces"]["New_York"][C.MILITIA_A] = 0
    with pytest.raises(ValueError, match="unmoved"):
        provenance.take(state, "New_York", 1)


def test_indian_bot_preserves_prior_placement_instead_of_reusing_gather_space():
    state = _state({"New_York": {C.VILLAGE: 1},
                    "Massachusetts": {C.WARPARTY_A: 1}},
                   available={C.WARPARTY_U: 2})

    assert IndianBot()._gather(state)

    assert state["spaces"]["New_York"].get(C.WARPARTY_U) == 2
    assert state["available"].get(C.WARPARTY_U, 0) == 0
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_A) == 1


def test_indian_gather_bot_moves_active_war_party_and_leaves_underground():
    state = _state({"New_York": {C.VILLAGE: 1},
                    "Massachusetts": {C.WARPARTY_U: 1, C.WARPARTY_A: 1}})

    assert IndianBot()._gather(state)

    assert state["spaces"]["New_York"].get(C.WARPARTY_U) == 1
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_U) == 1
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_A, 0) == 0


def test_patriot_rally_bot_moves_active_militia_and_leaves_underground():
    # At Active Opposition, placing one Militia cannot improve either
    # space's Control. The Rally therefore reaches its regrouping bullet.
    state = _state({"New_York": {C.FORT_PAT: 1, C.REGULAR_PAT: 1},
                    "Massachusetts": {C.MILITIA_U: 1, C.MILITIA_A: 1}},
                   support={"New_York": C.ACTIVE_OPPOSITION,
                            "Massachusetts": C.ACTIVE_OPPOSITION})

    assert PatriotBot()._execute_rally(state)

    assert state["spaces"]["New_York"].get(C.MILITIA_U) == 1
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U) == 1
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_A, 0) == 0
