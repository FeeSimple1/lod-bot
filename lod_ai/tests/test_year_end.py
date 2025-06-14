import pytest

from lod_ai.util import year_end
from lod_ai import rules_consts as C


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def supply_state(resources):
    return {
        "spaces": {
            "A": {C.REGULAR_BRI: 1, "type": "Colony"},
            C.WEST_INDIES_ID: {},
        },
        "resources": {
            C.BRITISH: resources,
            C.PATRIOTS: 0,
            C.FRENCH: 0,
            C.INDIANS: 0,
        },
        "available": {},
        "history": [],
    }


def income_state():
    return {
        "spaces": {
            C.WEST_INDIES_ID: {C.BLOCKADE: 2, "British_Control": True, "Patriot_Control": False},
            "Town": {C.FORT_BRI: 1, "type": "City", "British_Control": True, "pop": 2},
            "Colony": {C.FORT_PAT: 1, "Patriot_Control": True, "type": "Colony"},
            "Village": {C.VILLAGE: 2},
        },
        "resources": {f: 0 for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "history": [],
    }


def support_state():
    return {
        "spaces": {
            "A": {C.REGULAR_BRI: 1, C.TORY: 1, "type": "City", "British_Control": True, C.RAID: 1},
            "B": {C.MILITIA_A: 1, "type": "Colony", "Patriot_Control": True},
        },
        "support": {"A": 0, "B": 0},
        "resources": {C.BRITISH: 2, C.PATRIOTS: 2},
        "available": {},
        "history": [],
    }


def leader_state():
    return {
        "spaces": {
            "A": {C.REGULAR_BRI: 2},
            "B": {C.REGULAR_BRI: 1},
            C.WEST_INDIES_ID: {},
        },
        "leaders": {C.BRITISH: "LEADER_GAGE"},
        "history": [],
    }


def reset_state():
    return {
        "spaces": {
            "A": {C.MILITIA_A: 1, C.RAID: 1},
            "B": {C.WARPARTY_A: 2},
            C.WEST_INDIES_ID: {},
        },
        "deck": [{"title": "CardX"}],
        "casualties": {C.REGULAR_BRI: 1},
        "available": {},
        "history": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_supply_phase_pays(monkeypatch):
    state = supply_state(1)
    monkeypatch.setattr(year_end.board_control, "shift_support", lambda *a, **k: False, raising=False)
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None)
    year_end._supply_phase(state)
    assert state["resources"][C.BRITISH] == 0
    assert state["spaces"]["A"].get(C.REGULAR_BRI) == 1
    assert any("paid" in h["msg"] for h in state["history"])

def test_supply_phase_removes(monkeypatch):
    state = supply_state(0)
    monkeypatch.setattr(year_end.board_control, "shift_support", lambda *a, **k: False, raising=False)
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None)
    year_end._supply_phase(state)
    assert C.REGULAR_BRI not in state["spaces"]["A"]
    assert state["available"][C.REGULAR_BRI] == 1
    assert any("cubes removed" in h["msg"] for h in state["history"])

def test_resource_income_totals():
    state = income_state()
    year_end._resource_income(state)
    assert state["resources"][C.BRITISH] == 8
    assert state["resources"][C.INDIANS] == 1
    assert state["resources"][C.PATRIOTS] == 1
    assert state["resources"][C.FRENCH] == 4

def test_support_phase_shifts(monkeypatch):
    state = support_state()
    year_end._support_phase(state)
    # Raid removed before spending
    assert C.RAID not in state["spaces"]["A"]
    # British remove Raid but do not shift further
    assert state["support"]["A"] == 0
    # Patriots spend 1 to shift B toward opposition
    assert state["support"]["B"] == -1

def test_leader_redeploy_destination():
    state = leader_state()
    year_end._leader_redeploy(state)
    assert state["leader_locs"]["LEADER_GAGE"] == "A"


def test_reset_phase_cleanup(monkeypatch):
    state = reset_state()
    monkeypatch.setattr(year_end, "lift_casualties", year_end.lift_casualties)
    year_end._reset_phase(state)
    # Markers removed and pieces flipped
    assert C.RAID not in state["spaces"]["A"]
    assert state["spaces"]["A"].get(C.MILITIA_A, 0) == 0
    assert state["spaces"]["A"][C.MILITIA_U] == 1
    assert state["spaces"]["B"].get(C.WARPARTY_A, 0) == 0
    assert state["spaces"]["B"][C.WARPARTY_U] == 2
    # Deck reveal and casualties lifted
    assert state.get("upcoming_card", {}).get("title") == "CardX"
    assert C.REGULAR_BRI in state["available"]
    assert any("Reset Phase complete" in h["msg"] for h in state["history"])

