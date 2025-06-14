import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import muster
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 1, "adjacent": ["Massachusetts"], "support": C.NEUTRAL},
            "Massachusetts": {"adjacent": ["Boston", "New_York"], "support": C.NEUTRAL},
            "New_York": {"adjacent": ["Massachusetts"], "support": C.NEUTRAL},
        },
        "resources": {C.BRITISH: 5, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_BRI: 2, C.TORY: 2},
        "rng": __import__('random').Random(1),
    }


def test_muster_cost_and_adjacent_tory(monkeypatch):
    calls = []
    monkeypatch.setattr(muster, "refresh_control", lambda s: calls.append("refresh"))
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: calls.append("caps"))
    state = simple_state()
    muster.execute(
        state,
        C.BRITISH,
        {},
        ["Boston", "Massachusetts", "New_York"],
        regular_plan={"space": "Boston", "n": 1},
        tory_plan={"Massachusetts": 1, "New_York": 1},
    )
    assert state["resources"][C.BRITISH] == 2
    assert state["spaces"]["Massachusetts"].get(C.TORY, 0) == 1
    assert state["spaces"]["New_York"].get(C.TORY, 0) == 0
    assert "refresh" in calls and "caps" in calls
