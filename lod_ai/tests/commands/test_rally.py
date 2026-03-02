import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import rally
from lod_ai import rules_consts as C
from lod_ai.bots.patriot import PatriotBot


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
    with pytest.raises(ValueError, match="Cannot Rally"):
        rally.execute(
            state, C.PATRIOTS, {}, ["Northwest"],
            place_one={"Northwest"},
        )


# --------------------------------------------------------------------------- #
# Bug fix: rally.execute() must validate before charging resources
# --------------------------------------------------------------------------- #
def test_active_support_raises_without_spending(monkeypatch):
    """Rally in an Active Support space must raise ValueError AND leave
    Patriot Resources unchanged (validation before spend)."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Massachusetts": {C.MILITIA_U: 2},
        },
        "support": {"Massachusetts": C.ACTIVE_SUPPORT},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    with pytest.raises(ValueError, match="Active Support"):
        rally.execute(state, C.PATRIOTS, {}, ["Massachusetts"])
    # Resources must be unchanged — validation happened before spend
    assert state["resources"][C.PATRIOTS] == 3


def test_active_support_multi_space_raises_without_spending(monkeypatch):
    """When one space in a multi-space Rally is at Active Support, the
    entire call must raise before any resources are spent."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 1, C.FORT_PAT: 1},
            "Massachusetts": {C.MILITIA_U: 2},
        },
        "support": {"Massachusetts": C.ACTIVE_SUPPORT},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    with pytest.raises(ValueError, match="Active Support"):
        rally.execute(
            state, C.PATRIOTS, {}, ["Boston", "Massachusetts"],
            place_one={"Boston", "Massachusetts"},
        )
    # No resources spent at all
    assert state["resources"][C.PATRIOTS] == 5


def test_indian_reserve_raises_without_spending(monkeypatch):
    """Rally in Indian Reserve must raise before spending resources."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = {
        "spaces": {
            "Northwest": {},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.MILITIA_U: 10},
        "rng": __import__('random').Random(1),
    }
    with pytest.raises(ValueError, match="Cannot Rally"):
        rally.execute(state, C.PATRIOTS, {}, ["Northwest"])
    assert state["resources"][C.PATRIOTS] == 3


# --------------------------------------------------------------------------- #
# Bug fix: PatriotBot._execute_rally() must skip Active Support spaces
# --------------------------------------------------------------------------- #
def _bot_rally_state(support_overrides=None):
    """Minimal state for bot rally tests.  All four factions' spaces included
    so the bot's iteration over state['spaces'] works."""
    import json
    from pathlib import Path
    map_data = json.load(
        open(Path(__file__).resolve().parents[2] / "map" / "data" / "map.json")
    )
    spaces = {}
    for sid in map_data:
        spaces[sid] = {}
    # Put some rebel pieces in Massachusetts and Boston
    spaces["Massachusetts"] = {C.MILITIA_U: 3, C.MILITIA_A: 1}
    spaces["Boston"] = {C.MILITIA_U: 1}
    spaces["New_York"] = {C.MILITIA_U: 2}
    spaces["Connecticut_Rhode_Island"] = {C.MILITIA_U: 1}

    support = {sid: C.NEUTRAL for sid in map_data}
    if support_overrides:
        support.update(support_overrides)

    return {
        "spaces": spaces,
        "support": support,
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {
            C.MILITIA_U: 10, C.REGULAR_PAT: 5,
            C.FORT_PAT: 2, C.MILITIA_A: 0,
        },
        "control": {},
        "rng": __import__('random').Random(42),
    }


def test_bot_rally_skips_active_support(monkeypatch):
    """PatriotBot._execute_rally() must NOT select Massachusetts when it
    is at Active Support, even though it has rebel pieces."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = _bot_rally_state({"Massachusetts": C.ACTIVE_SUPPORT})
    bot = PatriotBot()
    result = bot._execute_rally(state)
    # Rally should succeed (other spaces are valid)
    assert result is True
    # Massachusetts must not have been rallied — its pieces should be untouched
    assert state["spaces"]["Massachusetts"][C.MILITIA_U] == 3
    assert state["spaces"]["Massachusetts"][C.MILITIA_A] == 1


def test_bot_rally_all_active_support_except_one(monkeypatch):
    """When all spaces are Active Support except one, only that space
    should be selected for Rally."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    import json
    from pathlib import Path
    map_data = json.load(
        open(Path(__file__).resolve().parents[2] / "map" / "data" / "map.json")
    )
    overrides = {sid: C.ACTIVE_SUPPORT for sid in map_data}
    # Leave only New_York at Neutral
    overrides["New_York"] = C.NEUTRAL
    state = _bot_rally_state(overrides)
    bot = PatriotBot()
    result = bot._execute_rally(state)
    assert result is True
    # Resources should have decreased by exactly 1 (one space rallied)
    assert state["resources"][C.PATRIOTS] == 4


def test_bot_rally_integration_scenario(monkeypatch):
    """Integration test matching the live-play scenario: Patriots have 3
    Resources, Massachusetts at Active Support.  After _execute_rally(),
    resources should only be spent for spaces that actually executed.
    Note: Bullet 7 gather may move militia FROM Massachusetts (adjacent to
    a fort) — that's valid, it's not rallying IN Massachusetts."""
    monkeypatch.setattr(rally, "refresh_control", lambda s: None)
    monkeypatch.setattr(rally, "enforce_global_caps", lambda s: None)
    state = _bot_rally_state({"Massachusetts": C.ACTIVE_SUPPORT})
    state["resources"][C.PATRIOTS] = 3
    bot = PatriotBot()
    result = bot._execute_rally(state)
    assert result is True
    # Resources should never go below 0 and should reflect only valid spaces
    assert state["resources"][C.PATRIOTS] >= 0
    # Massachusetts must NOT be among the rally-affected spaces
    affected = state.get("_turn_affected_spaces", set())
    assert "Massachusetts" not in affected, (
        "Massachusetts at Active Support should not be a Rally space"
    )
