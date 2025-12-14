import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import march
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 2},
            "Connecticut_Rhode_Island": {},
            "New_York": {},
        },
        "resources": {C.BRITISH: 3, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "rng": __import__('random').Random(1),
    }


def test_march_deducts_resources_and_calls_caps(monkeypatch):
    calls = []
    monkeypatch.setattr(march, "refresh_control", lambda s: calls.append("refresh"))
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: calls.append("caps"))
    state = simple_state()
    march.execute(state, C.BRITISH, {}, ["Boston"], ["Connecticut_Rhode_Island"])
    assert state["resources"][C.BRITISH] == 2
    assert state["spaces"]["Boston"].get(C.REGULAR_BRI, 0) == 0
    assert state["spaces"]["Connecticut_Rhode_Island"].get(C.REGULAR_BRI, 0) == 2
    assert "refresh" in calls and "caps" in calls


def test_march_invalid_adjacency():
    state = simple_state()
    with pytest.raises(ValueError):
        march.execute(state, C.BRITISH, {}, ["Boston"], ["New_York"])
