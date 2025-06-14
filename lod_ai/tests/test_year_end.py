import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.util import year_end
from lod_ai import rules_consts as C


def base_state():
    return {
        "spaces": {C.WEST_INDIES_ID: {}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "history": [],
    }


def patch_helpers(monkeypatch):
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None)
    monkeypatch.setattr(year_end.map_adj, "shortest_path", lambda s, a, b: [a, b], raising=False)
    monkeypatch.setattr(year_end.board_control, "shift_support", lambda *a, **k: False, raising=False)


def test_supply_removal(monkeypatch):
    patch_helpers(monkeypatch)
    state = base_state()
    state["spaces"]["A"] = {C.REGULAR_BRI: 1}
    year_end._supply_phase(state)
    assert state["available"][C.REGULAR_BRI] == 1
    assert C.REGULAR_BRI not in state["spaces"]["A"]


def test_supply_payment(monkeypatch):
    patch_helpers(monkeypatch)
    state = base_state()
    state["spaces"]["A"] = {C.REGULAR_BRI: 1}
    state["resources"][C.BRITISH] = 1
    year_end._supply_phase(state)
    assert state["resources"][C.BRITISH] == 0
    assert state["spaces"]["A"][C.REGULAR_BRI] == 1


def test_resource_income_calculation(monkeypatch):
    patch_helpers(monkeypatch)
    state = base_state()
    state["spaces"].update({
        "A": {"type": "City", "British_Control": True, "pop": 2, C.FORT_BRI: 1, C.VILLAGE: 1},
        "B": {"type": "Colony", "Patriot_Control": True, C.FORT_PAT: 1, C.VILLAGE: 1},
        "C": {"type": "City", "Patriot_Control": True, "pop": 3},
    })
    state["spaces"][C.WEST_INDIES_ID]["British_Control"] = True
    state["spaces"][C.WEST_INDIES_ID][C.BLOCKADE] = 1
    year_end._resource_income(state)
    assert state["resources"][C.BRITISH] == 8
    assert state["resources"][C.INDIANS] == 1
    assert state["resources"][C.PATRIOTS] == 2
    assert state["resources"][C.FRENCH] == 2


def test_support_phase_shifts(monkeypatch):
    patch_helpers(monkeypatch)
    state = base_state()
    state["resources"][C.BRITISH] = 1
    state["resources"][C.PATRIOTS] = 1
    state["spaces"].update({
        "A": {"British_Control": True, C.REGULAR_BRI: 1, C.TORY: 1},
        "B": {"Patriot_Control": True, C.MILITIA_U: 1},
    })
    state["support"] = {"A": 0, "B": 0}
    year_end._support_phase(state)
    assert state["support"]["A"] == 1
    assert state["resources"][C.BRITISH] == 0
    assert state["support"]["B"] == -1
    assert state["resources"][C.PATRIOTS] == 0


def test_leader_redeploy(monkeypatch):
    patch_helpers(monkeypatch)
    state = base_state()
    state["spaces"].update({
        "A": {C.REGULAR_BRI: 2, C.TORY: 1},
        "B": {C.REGULAR_PAT: 2},
        "C": {C.WARPARTY_U: 3},
        "D": {C.REGULAR_FRE: 1},
    })
    state["leaders"] = {
        C.BRITISH: "LEADER_GAGE",
        C.PATRIOTS: "LEADER_WASHINGTON",
        C.FRENCH: "LEADER_ROCHAMBEAU",
        C.INDIANS: "LEADER_BRANT",
    }
    year_end._leader_redeploy(state)
    locs = state["leader_locs"]
    assert locs["LEADER_GAGE"] == "A"
    assert locs["LEADER_WASHINGTON"] == "B"
    assert locs["LEADER_ROCHAMBEAU"] == "D"
    assert locs["LEADER_BRANT"] == "C"


def test_reset_phase(monkeypatch):
    monkeypatch.setattr(year_end, "lift_casualties", lambda s: s.update({"lift": True}))
    patch_helpers(monkeypatch)
    state = base_state()
    state["spaces"].update({
        "A": {C.RAID: 1, C.PROPAGANDA: 1, C.MILITIA_A: 1, C.WARPARTY_A: 1},
    })
    state["eligible"] = {C.BRITISH: False}
    state["deck"] = [{"title": "Next"}]
    state["winter_card_event"] = lambda s: s.update({"event": True})
    state["casualties"] = {C.REGULAR_BRI: 1}
    year_end._reset_phase(state)
    sp = state["spaces"]["A"]
    assert C.RAID not in sp and C.PROPAGANDA not in sp
    assert sp[C.MILITIA_U] == 1 and sp.get(C.MILITIA_A, 0) == 0
    assert sp[C.WARPARTY_U] == 1 and sp.get(C.WARPARTY_A, 0) == 0
    assert state["eligible"] == {
        C.BRITISH: True,
        C.PATRIOTS: True,
        C.FRENCH: True,
        C.INDIANS: True,
    }
    assert state["upcoming_card"]["title"] == "Next"
    assert state.get("event")
    assert state.get("lift")

