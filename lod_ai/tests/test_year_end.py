import pytest
from lod_ai.util import year_end
from lod_ai import rules_consts as C


def basic_state():
    return {
        "spaces": {C.WEST_INDIES_ID: {"type": "Island"}},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "history": [],
        "support": {"A": 0, C.WEST_INDIES_ID: 0},
    }


def test_supply_phase_pay_or_remove(monkeypatch):
    state = basic_state()
    state["spaces"]["A"] = {"type": "Colony", C.REGULAR_BRI: 1, C.TORY: 1}

    # insufficient resources -> remove cubes
    monkeypatch.setattr(
        year_end.board_control, "shift_support", lambda s, i, d: False, raising=False
    )
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None)
    year_end._supply_phase(state)
    assert C.REGULAR_BRI not in state["spaces"]["A"]
    assert state["available"][C.REGULAR_BRI] == 1
    assert state["resources"][C.BRITISH] == 0

    # cubes remain when paying
    state = basic_state()
    state["spaces"]["A"] = {"type": "Colony", C.REGULAR_BRI: 1, C.TORY: 1}
    state["resources"][C.BRITISH] = 1
    monkeypatch.setattr(
        year_end.board_control, "shift_support", lambda s, i, d: False, raising=False
    )
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None)
    year_end._supply_phase(state)
    assert state["spaces"]["A"][C.REGULAR_BRI] == 1
    assert state["resources"][C.BRITISH] == 0


def test_resource_income_calculation():
    state = basic_state()
    state["spaces"].update({
        "CityA": {"type": "City", "pop": 2, "British_Control": True, C.FORT_BRI: 1},
        "CityB": {"type": "City", "pop": 3, "Patriot_Control": True, "British_Control": False, C.FORT_PAT: 1},
        "Colony": {"type": "Colony", "Patriot_Control": True},
        "VillageLoc": {C.VILLAGE: 2},
    })
    state["spaces"][C.WEST_INDIES_ID].update({"British_Control": True, C.BLOCKADE: 1})
    year_end._resource_income(state)
    assert state["resources"][C.BRITISH] == 8
    assert state["resources"][C.PATRIOTS] == 2
    assert state["resources"][C.FRENCH] == 2
    assert state["resources"][C.INDIANS] == 1


def test_support_phase_shifts():
    state = basic_state()
    state["spaces"]["A"] = {
        "type": "City", "British_Control": True,
        C.REGULAR_BRI: 1, C.TORY: 1,
    }
    state["spaces"]["B"] = {
        "type": "Colony", "Patriot_Control": True,
        C.MILITIA_U: 1,
    }
    state["resources"].update({C.BRITISH: 1, C.PATRIOTS: 1})
    state["support"].update({"A": 0, "B": 0})

    year_end._support_phase(state)
    assert state["support"]["A"] == 1
    assert state["support"]["B"] == -1
    assert state["resources"][C.BRITISH] == 0
    assert state["resources"][C.PATRIOTS] == 0


def test_leader_redeploy_selects_biggest_stack():
    state = basic_state()
    state["spaces"].update({
        "A": {C.REGULAR_BRI: 2},
        "B": {C.REGULAR_BRI: 1},
    })
    state["leaders"] = {C.BRITISH: "LEADER_GAGE"}
    year_end._leader_redeploy(state)
    assert state["leader_locs"]["LEADER_GAGE"] == "A"


def test_reset_phase_cleans_up(monkeypatch):
    state = basic_state()
    state["spaces"]["A"] = {
        C.RAID: 1, C.PROPAGANDA: 1,
        C.MILITIA_A: 1, C.WARPARTY_A: 1,
    }
    state["deck"] = [{"title": "Next"}]
    state["winter_card_event"] = lambda s: s.update({"event_called": True})

    def fake_lift(s):
        s["lifted"] = True
    monkeypatch.setattr(year_end, "lift_casualties", fake_lift)

    year_end._reset_phase(state)
    sp = state["spaces"]["A"]
    assert C.RAID not in sp and C.PROPAGANDA not in sp
    assert sp[C.MILITIA_U] == 1 and sp.get(C.MILITIA_A, 0) == 0
    assert sp[C.WARPARTY_U] == 1 and sp.get(C.WARPARTY_A, 0) == 0
    assert state["upcoming_card"]["title"] == "Next"
    assert state["event_called"] is True
    assert state["lifted"]
    assert all(state["eligible"].values())
