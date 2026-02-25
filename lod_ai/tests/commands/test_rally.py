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


# --------------------------------------------------------------------------- #
# §3.3.1: Bulk placement cap = Forts + Population (from map data)
# --------------------------------------------------------------------------- #
def test_bulk_place_cap_uses_map_population(monkeypatch):
    """§3.3.1: 'Place a number of Militia up to the number of Patriot Forts
    there plus the space's Population value.'  Massachusetts has population 2
    in map.json, so with 1 Fort the cap should be 3 (1+2), not 1 (1+0)."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Massachusetts": {C.FORT_PAT: 1, C.MILITIA_U: 0},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    # Place 3 Militia (1 Fort + 2 population) — should succeed
    rally.execute(
        state, C.PATRIOTS, {}, ["Massachusetts"],
        bulk_place={"Massachusetts": 3},
    )
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 3


def test_bulk_place_cap_rejects_over_limit(monkeypatch):
    """Placing more Militia than Forts + Population must raise."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Massachusetts": {C.FORT_PAT: 1, C.MILITIA_U: 0},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    # Cap is 3 (1 Fort + 2 pop), so 4 must be rejected
    with pytest.raises(ValueError, match="limit is 3"):
        rally.execute(
            state, C.PATRIOTS, {}, ["Massachusetts"],
            bulk_place={"Massachusetts": 4},
        )


# --------------------------------------------------------------------------- #
# §3.3.1: Indian Reserve detection uses map data, not runtime space dict
# --------------------------------------------------------------------------- #
def test_is_indian_reserve_identifies_reserve_spaces():
    """Northwest is type 'Reserve' in map.json — _is_indian_reserve must
    return True for it, confirming it reads from map data not the space dict."""
    assert rally._is_indian_reserve("Northwest") is True
    assert rally._is_indian_reserve("Southwest") is True
    assert rally._is_indian_reserve("Florida") is True
    assert rally._is_indian_reserve("Quebec") is True
    # Non-reserve spaces
    assert rally._is_indian_reserve("Massachusetts") is False
    assert rally._is_indian_reserve("Boston") is False


def test_rally_rejects_militia_in_indian_reserve(monkeypatch):
    """§3.3.1: 'Militia may not be placed in an Indian Reserve space.'
    Rally must raise when attempting to place Militia in Northwest."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Northwest": {},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    with pytest.raises(ValueError, match="Indian Reserve"):
        rally.execute(
            state, C.PATRIOTS, {}, ["Northwest"],
            place_one={"Northwest"},
        )
