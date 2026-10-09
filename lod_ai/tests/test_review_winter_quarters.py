"""Real-state regressions for §6 human decisions and current leaders."""
from unittest.mock import Mock

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.cli_utils import get_input_provider, set_input_provider
from lod_ai.leaders import leader_location
from lod_ai.state.setup_state import build_state, _CARD_REGISTRY
from lod_ai.util import year_end as wq, year_end_choices as choices, leader_state as leaders


@pytest.fixture
def state():
    state = build_state("1778")
    state["spaces"] = {sid: {} for sid in state["spaces"]}
    state["support"] = {sid: 0 for sid in state["spaces"]}
    state["leaders"] = {}
    state["spaces"]["Northwest"][C.VILLAGE] = 1
    state["human_factions"] = set()
    state["history"] = []
    return state


def install_picker(monkeypatch, decisions):
    decisions = iter(decisions)
    def pick(state, faction, prompt, options):
        wanted = next(decisions)
        assert any(value == wanted for _, value in options), (prompt, wanted, options)
        return wanted
    monkeypatch.setattr(choices, "pick", pick)


def test_real_card_changes_gage_then_howe_and_retires_old_location():
    state = build_state("1775")
    state["upcoming_card"] = _CARD_REGISTRY[25]
    wq._leader_change(state)
    assert leader_location(state, leaders.GAGE) is None
    assert leader_location(state, leaders.HOWE) == "Boston"
    leaders.set_location(state, leaders.HOWE, None)
    wq._leader_change(state)
    assert state["active_leaders"][C.BRITISH] == leaders.CLINTON
    assert leader_location(state, leaders.HOWE) is None


def test_real_scenario_redeployment_calls_each_current_bot():
    state = build_state("1778")
    bots = {f: Mock() for f in (C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH)}
    bots[C.BRITISH].bot_redeploy_leader.return_value = "Quebec"
    bots[C.PATRIOTS].ops_redeploy_washington.return_value = "Boston"
    bots[C.FRENCH].ops_redeploy_leader.return_value = "West_Indies"
    bots[C.INDIANS].ops_redeploy.return_value = {leaders.CORNPLANTER: "Southwest"}
    wq._leader_redeploy(state, bots=bots)
    assert leader_location(state, leaders.CLINTON) == "Quebec"
    assert leader_location(state, leaders.WASHINGTON) == "Boston"
    assert leader_location(state, leaders.ROCHAMBEAU) == "West_Indies"
    assert leader_location(state, leaders.CORNPLANTER) == "Southwest"


def test_human_support_can_decline_using_real_input_provider(state):
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1, C.TORY: 1}
    state["human_factions"] = {C.BRITISH}
    refresh_control(state)
    before = state["resources"][C.BRITISH]
    provider = Mock()
    provider.prompt.return_value = "1"  # Done — keep resources
    old = get_input_provider()
    set_input_provider(provider)
    try:
        wq._support_phase(state)
    finally:
        set_input_provider(old)
    assert provider.prompt.call_count == 1
    assert state["resources"][C.BRITISH] == before
    assert state["support"]["Boston"] == 0


def test_human_can_remove_marker_only_and_stop(state, monkeypatch):
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1, C.TORY: 1}
    state["markers"][C.RAID]["on_map"] = {"Boston": 2}
    state["human_factions"] = {C.BRITISH}
    refresh_control(state)
    before = state["resources"][C.BRITISH]
    install_picker(monkeypatch, [("Boston", C.RAID), None])
    wq._support_phase(state)
    assert state["markers"][C.RAID]["on_map"]["Boston"] == 1
    assert state["resources"][C.BRITISH] == before - 1
    assert state["support"]["Boston"] == 0


def test_human_support_cap_is_two_shifts(state, monkeypatch):
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1, C.TORY: 1}
    state["support"]["Boston"] = -2
    state["human_factions"] = {C.BRITISH}
    refresh_control(state)
    install_picker(monkeypatch, [("Boston", None), ("Boston", None)])
    wq._support_phase(state)
    assert state["support"]["Boston"] == 0


@pytest.mark.parametrize("choice,remaining,support,spent", [
    ("pay", 2, 0, 1), ("shift", 2, -1, 0), ("remove", 0, 0, 0)])
def test_human_british_supply_options(state, monkeypatch, choice, remaining, support, spent):
    state["spaces"]["Pennsylvania"] = {C.REGULAR_BRI: 2}
    refresh_control(state)
    before = state["resources"][C.BRITISH]
    install_picker(monkeypatch, [choice])
    wq._supply_phase(state, human_factions={C.BRITISH})
    assert state["spaces"]["Pennsylvania"].get(C.REGULAR_BRI, 0) == remaining
    assert state["support"]["Pennsylvania"] == support
    assert state["resources"][C.BRITISH] == before - spent


def test_human_patriot_selects_supply_piece_types(state, monkeypatch):
    state["spaces"]["Quebec"] = {C.REGULAR_PAT: 2, C.MILITIA_U: 2}
    refresh_control(state)
    install_picker(monkeypatch, ["remove", C.MILITIA_U, C.MILITIA_U])
    wq._supply_phase(state, human_factions={C.PATRIOTS})
    assert state["spaces"]["Quebec"].get(C.MILITIA_U, 0) == 0
    assert state["spaces"]["Quebec"][C.REGULAR_PAT] == 2


def test_human_french_moves_to_chosen_nearest_fort(state, monkeypatch):
    state["spaces"]["Quebec"] = {C.REGULAR_FRE: 2}
    state["spaces"]["Quebec_City"] = {C.FORT_PAT: 1}
    refresh_control(state)
    install_picker(monkeypatch, [("move", "Quebec_City")])
    wq._supply_phase(state, human_factions={C.FRENCH})
    assert state["spaces"]["Quebec_City"][C.REGULAR_FRE] == 2


def test_human_indian_can_pay_without_bot_priority(state, monkeypatch):
    state["spaces"]["Pennsylvania"] = {C.WARPARTY_U: 1}
    refresh_control(state)
    install_picker(monkeypatch, [("pay", None)])
    before = state["resources"][C.INDIANS]
    wq._supply_phase(state, human_factions={C.INDIANS})
    assert state["spaces"]["Pennsylvania"][C.WARPARTY_U] == 1
    assert state["resources"][C.INDIANS] == before - 1


def test_human_west_indies_can_keep_some_units(state, monkeypatch):
    state["spaces"][C.WEST_INDIES_ID] = {C.REGULAR_FRE: 3}
    refresh_control(state)
    monkeypatch.setattr(choices, "count", lambda *args: 1)
    before = state["resources"][C.FRENCH]
    wq._supply_phase(state, human_factions={C.FRENCH})
    assert state["spaces"][C.WEST_INDIES_ID][C.REGULAR_FRE] == 1
    assert state["resources"][C.FRENCH] == before - 1


def test_human_desertion_deciders_choose_their_pieces(state, monkeypatch):
    state["spaces"]["Boston"] = {C.MILITIA_A: 5, C.REGULAR_PAT: 5, C.TORY: 5}
    state["spaces"]["New_York"] = {C.MILITIA_U: 5, C.REGULAR_PAT: 5, C.TORY: 5}
    install_picker(monkeypatch, [
        ("Boston", C.MILITIA_A), ("New_York", C.REGULAR_PAT),
        ("New_York", C.MILITIA_U), ("Boston", C.REGULAR_PAT),
        ("Boston", C.TORY), ("New_York", C.TORY)])
    wq._patriot_desertion(state, human_factions={C.INDIANS, C.PATRIOTS})
    wq._tory_desertion(state, human_factions={C.FRENCH, C.BRITISH})
    assert all(n == 4 for n in state["spaces"]["Boston"].values())
    assert all(n == 4 for n in state["spaces"]["New_York"].values())


def test_human_leader_can_stay_available_then_redeploy(state, monkeypatch):
    state["leaders"] = {leaders.CLINTON: "Boston"}
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1}
    install_picker(monkeypatch, [None, "Boston"])
    wq._leader_redeploy(state, human_factions={C.BRITISH})
    assert leader_location(state, leaders.CLINTON) is None
    wq._leader_redeploy(state, human_factions={C.BRITISH})
    assert leader_location(state, leaders.CLINTON) == "Boston"


def test_human_blockade_removal_and_rearrangement(state, monkeypatch):
    state["fni_level"] = 2
    state["markers"][C.BLOCKADE] = {"pool": 1, "on_map": {"Boston", "Norfolk"}}
    install_picker(monkeypatch, ["Boston", True, "New_York_City"])
    wq._fni_drift(state, human_factions={C.FRENCH})
    assert state["fni_level"] == 1
    assert state["markers"][C.BLOCKADE] == {"pool": 2, "on_map": {"New_York_City"}}


@pytest.mark.parametrize("human", [False, True])
def test_gage_first_wq_support_shift_costs_zero(state, monkeypatch, human):
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1, C.TORY: 1}
    state["leaders"] = {leaders.GAGE: "Boston"}
    state["resources"][C.BRITISH] = 0
    state["human_factions"] = {C.BRITISH} if human else set()
    refresh_control(state)
    install_picker(monkeypatch, [("Boston", None)])
    wq._support_phase(state)
    assert state["resources"][C.BRITISH] == 0
    assert state["support"]["Boston"] == 1


@pytest.mark.parametrize("card", [102, 103])
def test_wq_removal_event_belongs_to_affected_human(state, monkeypatch, card):
    from lod_ai.cards import CARD_HANDLERS
    state["human_factions"] = {C.PATRIOTS}
    state["spaces"]["Boston"] = {C.FORT_PAT: 1}
    state["spaces"]["Pennsylvania"] = {C.FORT_PAT: 1}
    install_picker(monkeypatch, ["Pennsylvania"])
    CARD_HANDLERS[card](state)
    state.pop("winter_card_event")(state)
    assert state["spaces"]["Boston"][C.FORT_PAT] == 1
    assert state["spaces"]["Pennsylvania"].get(C.FORT_PAT, 0) == 0
