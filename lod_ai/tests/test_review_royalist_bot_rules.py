"""Regressions for the British/Indian source-rule review."""

from copy import deepcopy
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.indians import IndianBot
from lod_ai.commands import gather


def _state(spaces, *, available=None, support=None, leaders=None):
    return {
        "spaces": spaces,
        "resources": {f: 5 for f in (C.BRITISH, C.INDIANS, C.PATRIOTS, C.FRENCH)},
        "available": available or {},
        "unavailable": {},
        "casualties": {},
        "support": support or {},
        "control": {},
        "markers": {},
        "leaders": leaders or {},
        "rng": random.Random(42),
        "history": [],
        "_no_special": True,
    }


def test_indian_gather_ignores_city_without_spending_its_resource():
    """§3.4.1: only the eligible Reserve is selected, and it is free."""
    state = _state(
        {"Boston": {}, "Northwest": {}},
        available={C.WARPARTY_U: 5, C.VILLAGE: 3},
    )

    assert IndianBot()._gather(state)

    assert state["_turn_affected_spaces"] == {"Northwest"}
    assert state["resources"][C.INDIANS] == 5
    assert state["spaces"]["Northwest"][C.WARPARTY_U] == 1
    assert state["spaces"]["Boston"].get(C.WARPARTY_U, 0) == 0
    assert not any("Indians not allowed" in h["msg"] for h in state["history"])


@pytest.mark.parametrize("invalid_space", ["Boston", C.WEST_INDIES_ID])
def test_gather_rejects_nonprovince_before_mutating_state(invalid_space):
    """§3.4.1: human/direct callers cannot pay for a City or West Indies."""
    state = _state(
        {"Northwest": {}, invalid_space: {}},
        available={C.WARPARTY_U: 5, C.VILLAGE: 3},
    )
    before = deepcopy({k: v for k, v in state.items() if k != "rng"})
    rng_before = state["rng"].getstate()

    with pytest.raises(ValueError, match="Gather selects Provinces only"):
        gather.execute(state, C.INDIANS, {}, ["Northwest", invalid_space])

    assert {k: v for k, v in state.items() if k != "rng"} == before
    assert state["rng"].getstate() == rng_before


def test_dragging_canoe_raid_preserves_last_war_party_at_village():
    """§8.7.1: two-space range never waives the Village retention rule."""
    state = _state(
        {"Southwest": {C.VILLAGE: 1, C.WARPARTY_U: 1}, "Pennsylvania": {}},
        support={"Pennsylvania": C.ACTIVE_OPPOSITION},
        leaders={"LEADER_DRAGGING_CANOE": "Southwest"},
    )

    assert not IndianBot()._raid(state)

    assert state["spaces"]["Southwest"][C.WARPARTY_U] == 1
    assert state["support"]["Pennsylvania"] == C.ACTIVE_OPPOSITION
    assert state["resources"][C.INDIANS] == 5


@pytest.mark.parametrize("target", ["Virginia", "Pennsylvania"])
def test_raid_can_leave_active_war_party_at_village(target):
    """§8.7.1: leaving an Active War Party satisfies retention at either range."""
    state = _state(
        {
            "Southwest": {C.VILLAGE: 1, C.WARPARTY_U: 1, C.WARPARTY_A: 1},
            target: {},
        },
        support={target: C.ACTIVE_OPPOSITION},
        leaders={"LEADER_DRAGGING_CANOE": "Southwest"},
    )

    assert IndianBot()._raid(state)

    assert state["spaces"]["Southwest"].get(C.WARPARTY_U, 0) == 0
    assert state["spaces"]["Southwest"][C.WARPARTY_A] == 1
    assert state["spaces"][target][C.WARPARTY_A] == 1
    assert state["support"][target] == C.PASSIVE_OPPOSITION


def test_british_battle_declines_militia_only_target():
    """§8.4.4: a valid B9 entry does not bypass B12's cubes/Forts filter."""
    state = _state({"Virginia": {C.REGULAR_BRI: 3, C.MILITIA_A: 2}})
    bot = BritishBot()

    assert bot._can_battle(state)
    assert not bot._battle(state)

    assert state["spaces"]["Virginia"][C.MILITIA_A] == 2
    assert state["resources"][C.BRITISH] == 5
    assert not state["history"]


def test_british_march_fallback_builds_fort_with_empty_cube_pools():
    """§8.4.2: pinned cubes may build a Fort when no cube can be placed."""
    state = _state(
        {"Virginia": {C.REGULAR_BRI: 1, C.TORY: 4, C.MILITIA_A: 4}},
        available={C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 1},
    )

    BritishBot()._follow_flowchart(state)

    assert state["_turn_command"] == "MUSTER"
    assert state["spaces"]["Virginia"][C.FORT_BRI] == 1
    assert state["resources"][C.BRITISH] == 4
    assert not state.get("_pass_reason")


def test_british_muster_rewards_loyalty_with_empty_cube_pools():
    """§8.4.2: Reward Loyalty likewise does not require an Available cube."""
    state = _state(
        {"Virginia": {C.REGULAR_BRI: 1, C.TORY: 1}},
        available={C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        support={"Virginia": C.NEUTRAL},
    )

    assert BritishBot()._muster(state, tried_march=True)

    assert state["support"]["Virginia"] == C.ACTIVE_SUPPORT
    assert state["resources"][C.BRITISH] == 2
    assert state["_turn_affected_spaces"] == {"Virginia"}
