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


# --------------------------------------------------------------------------- #
# §3.3.1: No auto-Persuasion on zero Resources
# --------------------------------------------------------------------------- #
def test_no_auto_persuasion_on_zero_resources(monkeypatch):
    """_mid_rally_persuasion was removed — Rally should NOT trigger Persuasion
    when Patriot Resources hit 0.  That logic belongs in the bot flowchart."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 1, C.FORT_PAT: 1},
            "Massachusetts": {C.MILITIA_U: 3},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 1, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 5},
        "control": {"Massachusetts": "REBELLION"},
        "rng": __import__('random').Random(1),
    }
    rally.execute(state, C.PATRIOTS, {}, ["Boston"], place_one={"Boston"})
    # After paying 1 Resource, Patriots have 0.  Militia in Massachusetts
    # should be unchanged (no Persuasion side-effect).
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 3


# --------------------------------------------------------------------------- #
# §3.3.1: Promotion is caller-controlled via promote_n
# --------------------------------------------------------------------------- #
def test_promotion_caller_controlled(monkeypatch):
    """Caller can limit how many Militia to promote via promote_n."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 4, C.FORT_PAT: 1},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_PAT: 10, C.MILITIA_U: 5},
        "rng": __import__('random').Random(1),
    }
    rally.execute(
        state, C.PATRIOTS, {}, ["Boston"],
        place_one={"Boston"},
        promote_space="Boston",
        promote_n=2,
    )
    # Only 2 should be promoted, not all 4+1 militia
    assert state["spaces"]["Boston"].get(C.REGULAR_PAT, 0) == 2
    # Remaining militia: 4 initial + 1 placed - 2 promoted = 3
    assert state["spaces"]["Boston"].get(C.MILITIA_U, 0) == 3
