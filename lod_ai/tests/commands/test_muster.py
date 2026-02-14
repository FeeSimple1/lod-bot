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


# --------------------------------------------------------------------------- #
# §3.2.1 Reward Loyalty: no level cap
# --------------------------------------------------------------------------- #
def test_reward_loyalty_no_level_cap(monkeypatch):
    """§3.2.1: 'There is no limit to the number of levels shifted when
    Rewarding Loyalty during Muster.'  Previously capped at 2."""
    monkeypatch.setattr(muster, "refresh_control", lambda s: None)
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 3, C.TORY: 2, "is_city": True},
        },
        "resources": {C.BRITISH: 20, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_BRI: 6},
        "control": {"Boston": C.BRITISH},
        "support": {"Boston": C.ACTIVE_OPPOSITION},   # -2
        "rng": __import__('random').Random(1),
    }
    muster.execute(
        state, C.BRITISH, {}, ["Boston"],
        regular_plan={"space": "Boston", "n": 0},
        reward_levels=4,
    )
    # Active Opposition (-2) shifted 4 toward Active Support → capped at +2
    assert state["support"]["Boston"] == C.ACTIVE_SUPPORT


# --------------------------------------------------------------------------- #
# §3.5.3 French Muster: Rebellion Control required
# --------------------------------------------------------------------------- #
def test_french_muster_requires_rebellion_control(monkeypatch):
    """§3.5.3 says space must have Rebellion Control or be West Indies."""
    monkeypatch.setattr(muster, "refresh_control", lambda s: None)
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {"Boston": {}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 5, C.INDIANS: 0},
        "available": {C.REGULAR_FRE: 4},
        "control": {"Boston": C.BRITISH},  # NOT Rebellion-controlled
        "toa_played": True,
        "rng": __import__('random').Random(1),
    }
    with pytest.raises(ValueError, match="Rebellion Control"):
        muster.execute(state, C.FRENCH, {}, ["Boston"])


def test_french_muster_west_indies_ok(monkeypatch):
    """§3.5.3: West Indies is always valid for French Muster."""
    monkeypatch.setattr(muster, "refresh_control", lambda s: None)
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {C.WEST_INDIES_ID: {}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 5, C.INDIANS: 0},
        "available": {C.REGULAR_FRE: 4},
        "control": {},
        "toa_played": True,
        "rng": __import__('random').Random(1),
    }
    muster.execute(state, C.FRENCH, {}, [C.WEST_INDIES_ID])
    assert state["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_FRE, 0) == 4


# --------------------------------------------------------------------------- #
# §3.5.3 French Muster: Fort replacement is caller-controlled
# --------------------------------------------------------------------------- #
def test_french_muster_no_auto_fort(monkeypatch):
    """Fort replacement should NOT happen automatically — caller must opt in."""
    monkeypatch.setattr(muster, "refresh_control", lambda s: None)
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {"Boston": {}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 0},
        "available": {C.REGULAR_FRE: 4, C.FORT_PAT: 1},
        "control": {"Boston": "REBELLION"},
        "toa_played": True,
        "rng": __import__('random').Random(1),
    }
    muster.execute(state, C.FRENCH, {}, ["Boston"])
    # Without french_fort=True, no Fort should be placed
    assert state["spaces"]["Boston"].get(C.FORT_PAT, 0) == 0
    assert state["spaces"]["Boston"].get(C.REGULAR_FRE, 0) == 4


def test_french_muster_fort_when_requested(monkeypatch):
    """When french_fort=True, replace 2 French Regulars with 1 Patriot Fort."""
    monkeypatch.setattr(muster, "refresh_control", lambda s: None)
    monkeypatch.setattr(muster, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {"Boston": {}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 0},
        "available": {C.REGULAR_FRE: 4, C.FORT_PAT: 1},
        "control": {"Boston": "REBELLION"},
        "toa_played": True,
        "rng": __import__('random').Random(1),
    }
    muster.execute(state, C.FRENCH, {}, ["Boston"], french_fort=True)
    assert state["spaces"]["Boston"].get(C.FORT_PAT, 0) == 1
    assert state["spaces"]["Boston"].get(C.REGULAR_FRE, 0) == 2
    assert state["resources"][C.PATRIOTS] == 4  # paid 1
