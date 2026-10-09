"""Human Special Activity interruptions preserve Command phases and payments."""

import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.commands import (
    battle, french_agent_mobilization, garrison, hortelez, muster, scout,
)
from lod_ai.special_activities import naval_pressure, preparer, trade


def _state(spaces, *, available=None, resources=None):
    return {
        "spaces": spaces,
        "resources": {f: 5 for f in (C.BRITISH, C.INDIANS, C.PATRIOTS, C.FRENCH)}
                     | (resources or {}),
        "available": available or {},
        "unavailable": {},
        "casualties": {},
        "markers": {},
        "support": {},
        "control": {},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
    }


@pytest.mark.parametrize("tory_space", ["Boston", "Massachusetts"])
def test_muster_can_use_naval_pressure_between_regulars_and_tories(tory_space):
    state = _state(
        {"Boston": {}, "Massachusetts": {}},
        available={C.REGULAR_BRI: 1, C.TORY: 2},
        resources={C.BRITISH: 1},
    )
    selected = list(dict.fromkeys(["Boston", tory_space]))
    observed = []

    def checkpoint(s, c, label, space):
        assert c["_planned_command"] == "MUSTER"
        assert c["_command_selected_spaces"] == set(selected)
        assert s["_turn_muster_spaces"] == set(selected)
        if label == "Before placing Tories":
            observed.append((s["resources"][C.BRITISH],
                             s["spaces"]["Boston"].get(C.REGULAR_BRI, 0)))
            naval_pressure.execute(s, C.BRITISH, c)

    muster.execute(
        state, C.BRITISH, {"_command_checkpoint": checkpoint}, selected,
        regular_plan={"space": "Boston", "n": 1},
        tory_plan={tory_space: 2},
    )

    assert observed == [(0, 1)]
    assert state["spaces"][tory_space][C.TORY] == 2
    gain = state["rng_log"][0][1]
    assert state["resources"][C.BRITISH] == 1 + gain - len(selected)


def test_battle_can_fund_next_space_after_first_battle(monkeypatch):
    state = _state(
        {"Virginia": {C.REGULAR_BRI: 3, C.REGULAR_PAT: 1},
         "Pennsylvania": {C.REGULAR_BRI: 3, C.REGULAR_PAT: 1}},
        resources={C.BRITISH: 1},
    )
    resolved = []

    def resolve(s, c, faction, sid, bonus, **kwargs):
        resolved.append(sid)
        return "ROYALIST"

    monkeypatch.setattr(battle, "_resolve_space", resolve)

    def checkpoint(s, c, label, sid):
        assert c["_command_selected_spaces"] == {"Virginia", "Pennsylvania"}
        assert s["_turn_battle_spaces"] == {"Virginia", "Pennsylvania"}
        if sid == "Pennsylvania":
            assert resolved == ["Virginia"]
            assert s["resources"][C.BRITISH] == 0
            naval_pressure.execute(s, C.BRITISH, c)

    battle.execute(
        state, C.BRITISH, {"_command_checkpoint": checkpoint},
        ["Virginia", "Pennsylvania"],
    )

    assert resolved == ["Virginia", "Pennsylvania"]
    assert state["resources"][C.BRITISH] == state["rng_log"][0][1] - 1


def test_garrison_checkpoint_observes_moved_regulars_before_activation():
    state = _state(
        {"Virginia": {C.REGULAR_BRI: 3}, "Boston": {C.MILITIA_U: 1}},
        resources={C.BRITISH: 2},
    )
    observed = []

    def checkpoint(s, c, label, sid):
        assert c["_planned_command"] == "GARRISON"
        assert s["_turn_garrison_destinations"] == {"Boston"}
        if label == "Before Garrison Militia activation":
            observed.append((s["spaces"][sid].get(C.REGULAR_BRI, 0),
                             s["spaces"][sid].get(C.MILITIA_U, 0)))
            naval_pressure.execute(s, C.BRITISH, c)

    garrison.execute(
        state, C.BRITISH, {"_command_checkpoint": checkpoint},
        {"Virginia": {"Boston": 3}},
    )

    assert observed == [(3, 1)]
    assert state["spaces"]["Boston"][C.MILITIA_A] == 1
    assert state["resources"][C.BRITISH] == state["rng_log"][0][1]


def test_scout_can_trade_after_movement_before_militia_activation():
    state = _state(
        {"Southwest": {C.VILLAGE: 1, C.WARPARTY_U: 2, C.REGULAR_BRI: 1},
         "Virginia": {C.MILITIA_U: 1}},
        resources={C.INDIANS: 1, C.BRITISH: 1},
    )
    observed = []

    def checkpoint(s, c, label, sid):
        if label == "Before Scout Militia activation":
            observed.append((s["spaces"][sid].get(C.WARPARTY_A, 0),
                             s["spaces"][sid].get(C.MILITIA_U, 0)))
            trade.execute(s, C.INDIANS, c, "Southwest", transfer=0)

    scout.execute(
        state, C.INDIANS, {"_command_checkpoint": checkpoint},
        "Southwest", "Virginia", n_warparties=1, n_regulars=1,
    )

    assert observed == [(1, 1)]
    assert state["spaces"]["Virginia"][C.MILITIA_A] == 1
    assert state["resources"][C.INDIANS] == 1
    assert state["resources"][C.BRITISH] == 0


@pytest.mark.parametrize("command", ["HORTELEZ", "FRENCH_AGENT_MOBILIZATION"])
def test_atomic_french_command_can_receive_resources_before_payment(command):
    state = _state(
        {"Quebec": {}}, available={C.MILITIA_U: 2},
        resources={C.FRENCH: 0, C.PATRIOTS: 0},
    )

    def checkpoint(s, c, label, sid):
        assert c["_planned_command"] == command
        preparer.execute(s, C.FRENCH, c, choice="RESOURCES")

    ctx = {"_command_checkpoint": checkpoint}
    if command == "HORTELEZ":
        hortelez.execute(state, C.FRENCH, ctx, 1)
        assert state["resources"][C.PATRIOTS] == 2
    else:
        french_agent_mobilization.execute(state, C.FRENCH, ctx, "Quebec")
        assert state["spaces"]["Quebec"][C.MILITIA_U] == 2

    assert state["resources"][C.FRENCH] == 1
