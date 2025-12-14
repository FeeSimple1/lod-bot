import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import rally
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {C.MILITIA_U: 1, C.FORT_PAT: 1},
            "Massachusetts": {C.MILITIA_U: 1},
            "New_York": {C.MILITIA_U: 1},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "rng": __import__('random').Random(1),
    }


def test_rally_moves_and_cost(monkeypatch):
    calls = []
    monkeypatch.setattr(rally, "refresh_control", lambda s: calls.append("refresh"))
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: calls.append("caps"))
    state = simple_state()
    rally.execute(state, C.PATRIOTS, {}, ["Boston"], move_plan=[("Massachusetts", "Boston", 1)])
    assert state["resources"][C.PATRIOTS] == 2
    assert state["spaces"]["Boston"].get(C.MILITIA_U, 0) >= 2
    assert "refresh" in calls and "caps" in calls


def test_rally_invalid_adjacency():
    state = simple_state()
    with pytest.raises(ValueError):
        rally.execute(state, C.PATRIOTS, {}, ["Boston"], move_plan=[("New_York", "Boston", 1)])
