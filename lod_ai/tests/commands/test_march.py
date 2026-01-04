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


def test_limited_march_allows_multiple_origins_with_plan(monkeypatch):
    state = simple_state()
    state["spaces"]["New_York"][C.REGULAR_BRI] = 1
    state["available"] = {C.REGULAR_BRI: 5}

    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)

    move_plan = [
        {"src": "Boston", "dst": "Connecticut_Rhode_Island", "pieces": {C.REGULAR_BRI: 1}},
        {"src": "New_York", "dst": "Connecticut_Rhode_Island", "pieces": {C.REGULAR_BRI: 1}},
    ]

    march.execute(
        state,
        C.BRITISH,
        {},
        [],
        ["Connecticut_Rhode_Island"],
        limited=True,
        plan=move_plan,
    )

    assert state["spaces"]["Connecticut_Rhode_Island"].get(C.REGULAR_BRI, 0) == 2
    assert state["spaces"]["Boston"].get(C.REGULAR_BRI, 0) == 1
    assert state["spaces"]["New_York"].get(C.REGULAR_BRI, 0) == 0
