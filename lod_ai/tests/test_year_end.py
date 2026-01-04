import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Tests for util.year_end phases
import pytest

from lod_ai.util import year_end
from lod_ai import rules_consts as C


# --------------------
# Fixtures
# --------------------

def basic_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "support": {},
        "control": {},
        "available": {},
        "markers": {
            C.RAID: {"pool": 0, "on_map": set()},
            C.PROPAGANDA: {"pool": 0, "on_map": set()},
            C.BLOCKADE: {"pool": 0, "on_map": set()},
        },
        "history": [],
        "leaders": {},
        "deck": [],
    }

def test_supply_pays_when_affordable(monkeypatch):
    state = basic_state()
    state["resources"][C.BRITISH] = 2
    state["spaces"] = {"A": {C.REGULAR_BRI: 1}}
    state["spaces"][C.WEST_INDIES_ID] = {}

    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(year_end.board_control, "shift_support", lambda *a, **k: False, raising=False)
    year_end._supply_phase(state)

    assert state["resources"][C.BRITISH] == 1
    assert state["spaces"]["A"][C.REGULAR_BRI] == 1

def test_supply_removes_if_cannot_pay(monkeypatch):
    state = basic_state()
    state["spaces"] = {"A": {C.REGULAR_BRI: 1}}
    # no resources, so can't pay
    state["spaces"][C.WEST_INDIES_ID] = {}
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)

    monkeypatch.setattr(year_end.board_control, "shift_support", lambda *a, **k: False, raising=False)
    year_end._supply_phase(state)

    assert C.REGULAR_BRI not in state["spaces"]["A"]

def test_resource_income_simple():
    state = basic_state()
    state["spaces"] = {
        "A": {"type": "City", "pop": 3, C.FORT_BRI: 1},
        "B": {"type": "Colony", C.FORT_PAT: 1},
        "C": {C.VILLAGE: 3},
        C.WEST_INDIES_ID: {},
    }
    state["control"] = {"A": "BRITISH", "B": "REBELLION", "C": None, C.WEST_INDIES_ID: None}
    state["markers"][C.BLOCKADE]["pool"] = 1
    year_end._resource_income(state)

    assert state["resources"][C.BRITISH] == 4
    assert state["resources"][C.PATRIOTS] == 1
    assert state["resources"][C.INDIANS] == 1
    assert state["resources"][C.FRENCH] == 2

def test_support_phase_shifts_levels():
    state = basic_state()
    state["resources"][C.BRITISH] = 1
    state["resources"][C.PATRIOTS] = 1
    state["spaces"] = {
        "CityA": {
            C.REGULAR_BRI: 1,
            C.TORY: 1,
        },
        "ColB": {
            C.MILITIA_A: 1,
        },
    }
    state["support"] = {"CityA": 0, "ColB": 0}
    state["control"] = {"CityA": "BRITISH", "ColB": "REBELLION"}

    year_end._support_phase(state)

    assert state["resources"][C.BRITISH] == 0
    assert state["resources"][C.PATRIOTS] == 0
    assert state["support"]["CityA"] == 1
    assert state["support"]["ColB"] == -1

def test_leader_redeploy_assigns_destinations():
    state = basic_state()
    state["leaders"] = {
        C.BRITISH: "LEADER_HOWE",
        C.PATRIOTS: "LEADER_WASHINGTON",
    }
    state["spaces"] = {
        "X": {C.REGULAR_BRI: 2},
        "Y": {C.MILITIA_A: 1},
    }

    year_end._leader_redeploy(state)

    assert state["leader_locs"]["LEADER_HOWE"] == "X"
    assert state["leader_locs"]["LEADER_WASHINGTON"] == "Y"

def test_reset_phase_cleans_up(monkeypatch):
    state = basic_state()
    state["spaces"] = {
        "S": {
            C.MILITIA_A: 1,
            C.WARPARTY_A: 1,
        }
    }
    state["markers"] = {
        C.RAID: {"pool": 0, "on_map": {"S"}},
        C.PROPAGANDA: {"pool": 0, "on_map": {"S"}},
    }
    state["deck"] = [{"title": "Next"}]
    state["winter_card_event"] = lambda s: s.setdefault("event", True)
    lifted = {}
    def fake_lift(s):
        lifted["done"] = True
    monkeypatch.setattr(year_end, "lift_casualties", fake_lift)

    year_end._reset_phase(state)

    sp = state["spaces"]["S"]
    assert sp.get(C.MILITIA_U) == 1 and sp.get(C.MILITIA_A, 0) == 0
    assert sp.get(C.WARPARTY_U) == 1 and sp.get(C.WARPARTY_A, 0) == 0
    assert not state["markers"][C.RAID]["on_map"]
    assert not state["markers"][C.PROPAGANDA]["on_map"]
    assert state["markers"][C.RAID]["pool"] == 1
    assert state["markers"][C.PROPAGANDA]["pool"] == 1
    assert state["eligible"][C.BRITISH]
    assert state.get("upcoming_card", {}).get("title") == "Next"
    assert state.get("event") is True
    assert lifted.get("done") is True


def test_reset_phase_keeps_existing_upcoming(monkeypatch):
    state = basic_state()
    state["spaces"][C.WEST_INDIES_ID] = {}
    state["upcoming_card"] = {"title": "Keep"}
    state["deck"] = [{"title": "Next"}]

    monkeypatch.setattr(year_end, "lift_casualties", lambda s: None)

    year_end._reset_phase(state)

    assert state["upcoming_card"]["title"] == "Keep"
    assert state["deck"] == [{"title": "Next"}]
