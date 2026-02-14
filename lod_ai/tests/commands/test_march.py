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


# --------------------------------------------------------------------------- #
# §3.2.3 British March: militia activation uses total British cubes
# --------------------------------------------------------------------------- #
def test_british_march_militia_activation_uses_total_cubes(monkeypatch):
    """§3.2.3: 'Activate one Militia for every three British cubes there
    (whether they just moved or were already there).'"""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    state = {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 1},
            # Destination already has 2 Regulars and 2 Underground Militia
            "Massachusetts": {C.REGULAR_BRI: 2, C.MILITIA_U: 2},
        },
        "resources": {C.BRITISH: 3, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Boston", "dst": "Massachusetts", "pieces": {C.REGULAR_BRI: 1}}]
    march.execute(state, C.BRITISH, {}, [], ["Massachusetts"], plan=plan)
    # 3 total British cubes → activate 1 Militia
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_A, 0) == 1
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 1


# --------------------------------------------------------------------------- #
# §3.3.2 Patriot March: militia conditional activation
# --------------------------------------------------------------------------- #
def test_patriot_march_militia_not_activated_by_default(monkeypatch):
    """§3.3.2: Militia should NOT always be set Active when moving.
    They only activate if destination is a British Controlled City AND
    group + British cubes > 3."""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 2, C.REGULAR_PAT: 1},
            "Massachusetts": {"type": "Province"},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "control": {"Massachusetts": None},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Boston", "dst": "Massachusetts",
             "pieces": {C.MILITIA_U: 2, C.REGULAR_PAT: 1}}]
    march.execute(state, C.PATRIOTS, {}, [], ["Massachusetts"], plan=plan)
    # Province with no British Control → militia stay Underground
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 2
    assert state["spaces"]["Massachusetts"].get(C.MILITIA_A, 0) == 0


def test_patriot_march_militia_activated_in_british_city(monkeypatch):
    """§3.3.2: Militia activate when entering a British Controlled City
    and moving group + British cubes > 3."""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    monkeypatch.setattr(march, "_is_city", lambda sid: sid == "Boston")
    state = {
        "spaces": {
            "Mass": {C.MILITIA_U: 2, C.REGULAR_PAT: 2},
            "Boston": {C.REGULAR_BRI: 2, "is_city": True},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "control": {"Boston": C.BRITISH},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Mass", "dst": "Boston",
             "pieces": {C.MILITIA_U: 2, C.REGULAR_PAT: 2}}]
    march.execute(state, C.PATRIOTS, {}, [], ["Boston"], plan=plan)
    # 4 units moving + 2 British cubes = 6 > 3 → activate militia
    assert state["spaces"]["Boston"].get(C.MILITIA_A, 0) == 2
    assert state["spaces"]["Boston"].get(C.MILITIA_U, 0) == 0


# --------------------------------------------------------------------------- #
# §3.3.2 Patriot March: War Party activation
# --------------------------------------------------------------------------- #
def test_patriot_march_activates_war_parties(monkeypatch):
    """§3.3.2: 'Activate one War Party for every two Continentals in the
    destination space.'"""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    state = {
        "spaces": {
            "Boston": {C.REGULAR_PAT: 4},
            # Destination has Underground War Parties
            "Massachusetts": {C.WARPARTY_U: 3},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "control": {},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Boston", "dst": "Massachusetts",
             "pieces": {C.REGULAR_PAT: 4}}]
    march.execute(state, C.PATRIOTS, {}, [], ["Massachusetts"], plan=plan)
    # 4 Continentals / 2 = 2 War Parties activated
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_A, 0) == 2
    assert state["spaces"]["Massachusetts"].get(C.WARPARTY_U, 0) == 1


# --------------------------------------------------------------------------- #
# §3.3.2 Patriot March: French must pay for destinations
# --------------------------------------------------------------------------- #
def test_patriot_march_french_pay_for_destinations(monkeypatch):
    """§3.3.2: 'For each destination space French enter, the French must
    also pay one Resource.'"""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    state = {
        "spaces": {
            "Boston": {C.REGULAR_PAT: 2, C.REGULAR_FRE: 1},
            "Massachusetts": {},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 3, C.FRENCH: 3, C.INDIANS: 0},
        "available": {},
        "control": {},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Boston", "dst": "Massachusetts",
             "pieces": {C.REGULAR_PAT: 2, C.REGULAR_FRE: 1}}]
    march.execute(state, C.PATRIOTS, {}, [], ["Massachusetts"],
                  plan=plan, bring_escorts=True)
    # Patriots pay 1 for destination, French pay 1 for French entering
    assert state["resources"][C.PATRIOTS] == 2
    assert state["resources"][C.FRENCH] == 2


# --------------------------------------------------------------------------- #
# §3.4.2 Indian March: conditional WP activation
# --------------------------------------------------------------------------- #
def test_indian_march_wp_not_activated_by_default(monkeypatch):
    """§3.4.2: War Parties should NOT always activate. Only activate if
    destination is a Rebellion-Controlled Colony AND group + militia > 3."""
    monkeypatch.setattr(march, "refresh_control", lambda s: None)
    monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
    monkeypatch.setattr(march, "_is_city", lambda sid: False)
    state = {
        "spaces": {
            "Province_A": {C.WARPARTY_U: 2},
            "Province_B": {"type": "Province"},
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 3},
        "available": {},
        "control": {"Province_B": C.BRITISH},
        "rng": __import__('random').Random(1),
    }
    plan = [{"src": "Province_A", "dst": "Province_B",
             "pieces": {C.WARPARTY_U: 2}}]
    march.execute(state, C.INDIANS, {}, [], ["Province_B"], plan=plan)
    # Not a Rebellion-Controlled Colony → War Parties stay Underground
    assert state["spaces"]["Province_B"].get(C.WARPARTY_U, 0) == 2
    assert state["spaces"]["Province_B"].get(C.WARPARTY_A, 0) == 0
