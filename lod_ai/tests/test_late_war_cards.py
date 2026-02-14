"""Tests for late_war.py card handlers."""

from lod_ai.cards.effects import late_war
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_FRE,
    REGULAR_PAT,
    TORY,
    MILITIA_A,
    MILITIA_U,
    WARPARTY_U,
    WARPARTY_A,
    FORT_BRI,
    FORT_PAT,
    VILLAGE,
    PROPAGANDA,
    WEST_INDIES_ID,
    PATRIOTS,
    BRITISH,
    FRENCH,
    INDIANS,
)


def _base_state():
    return {
        "spaces": {},
        "available": {},
        "unavailable": {},
        "casualties": {},
        "markers": {},
        "support": {},
        "control": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "INDIANS": 0, "FRENCH": 0},
        "ineligible_next": set(),
        "ineligible_through_next": set(),
        "remain_eligible": set(),
        "free_ops": [],
    }


# ---- Card 23: Francis Marion ----

def test_card23_unshaded_moves_patriot_units_from_nc():
    """Card 23 unshaded: Move all Patriot units in NC to adjacent Province."""
    state = _base_state()
    state["spaces"] = {
        "North_Carolina": {MILITIA_U: 2, REGULAR_PAT: 1},
        "South_Carolina": {TORY: 1},
        "Virginia": {},
    }
    state["card23_src"] = "North_Carolina"
    state["card23_dst"] = "Virginia"

    late_war.evt_023_francis_marion(state, shaded=False)

    # All Patriot units should have moved from NC to Virginia
    assert state["spaces"]["North_Carolina"].get(MILITIA_U, 0) == 0
    assert state["spaces"]["North_Carolina"].get(REGULAR_PAT, 0) == 0
    assert state["spaces"]["Virginia"].get(MILITIA_U, 0) == 2
    assert state["spaces"]["Virginia"].get(REGULAR_PAT, 0) == 1


def test_card23_unshaded_auto_selects_sc_if_nc_empty():
    """Card 23 unshaded: If NC has no Patriots, should auto-select SC."""
    state = _base_state()
    state["spaces"] = {
        "North_Carolina": {},
        "South_Carolina": {MILITIA_A: 2},
        "Georgia": {},
    }
    state["card23_dst"] = "Georgia"

    late_war.evt_023_francis_marion(state, shaded=False)

    assert state["spaces"]["South_Carolina"].get(MILITIA_A, 0) == 0
    assert state["spaces"]["Georgia"].get(MILITIA_A, 0) == 2


def test_card23_shaded_removes_british_from_nc():
    """Card 23 shaded: If Militia in NC, remove 4 British units."""
    state = _base_state()
    state["spaces"] = {
        "North_Carolina": {MILITIA_U: 1, REGULAR_BRI: 3, TORY: 2},
        "South_Carolina": {},
    }
    state["card23_target"] = "North_Carolina"

    late_war.evt_023_francis_marion(state, shaded=True)

    # Should remove 3 Regulars + 1 Tory (Regulars first, up to 4 total)
    assert state["spaces"]["North_Carolina"].get(REGULAR_BRI, 0) == 0
    assert state["spaces"]["North_Carolina"].get(TORY, 0) == 1


def test_card23_shaded_auto_selects_colony_with_militia():
    """Card 23 shaded: Auto-selects whichever colony has Militia."""
    state = _base_state()
    state["spaces"] = {
        "North_Carolina": {},
        "South_Carolina": {MILITIA_A: 1, REGULAR_BRI: 2},
    }

    late_war.evt_023_francis_marion(state, shaded=True)

    assert state["spaces"]["South_Carolina"].get(REGULAR_BRI, 0) == 0


def test_card23_shaded_no_militia_no_effect():
    """Card 23 shaded: No Militia in either colony → no effect."""
    state = _base_state()
    state["spaces"] = {
        "North_Carolina": {REGULAR_BRI: 2},
        "South_Carolina": {REGULAR_BRI: 1},
    }

    late_war.evt_023_francis_marion(state, shaded=True)

    # Nothing removed because no Militia present
    assert state["spaces"]["North_Carolina"].get(REGULAR_BRI, 0) == 2
    assert state["spaces"]["South_Carolina"].get(REGULAR_BRI, 0) == 1


# ---- Card 67: De Grasse ----

def test_card67_unshaded_lowers_fni_and_removes_fre():
    """Card 67 unshaded: Lower FNI 1 and remove 3 French Regulars from WI."""
    state = _base_state()
    state["spaces"] = {WEST_INDIES_ID: {REGULAR_FRE: 5}}
    state["toa_played"] = True
    state["fni_level"] = 2

    late_war.evt_067_de_grasse(state, shaded=False)

    assert state["spaces"][WEST_INDIES_ID].get(REGULAR_FRE, 0) == 2
    assert state["available"].get(REGULAR_FRE, 0) == 3
    assert state["fni_level"] == 1


def test_card67_shaded_queues_rally_and_remain_eligible():
    """Card 67 shaded: Queue free Rally, faction remains Eligible."""
    state = _base_state()
    state["spaces"] = {"Virginia": {}}
    state["toa_played"] = True

    late_war.evt_067_de_grasse(state, shaded=True)

    # French should be in remain_eligible (not eligible_next)
    assert FRENCH in state["remain_eligible"]
    # Free op should be queued
    assert len(state["free_ops"]) >= 1


def test_card67_shaded_muster_option():
    """Card 67 shaded: card67_op='muster' should queue Muster instead of Rally."""
    state = _base_state()
    state["spaces"] = {"Virginia": {}}
    state["toa_played"] = True
    state["card67_op"] = "muster"

    late_war.evt_067_de_grasse(state, shaded=True)

    # Verify the queued op is muster
    ops = state.get("free_ops", [])
    assert any("muster" in str(op).lower() for op in ops)
    assert FRENCH in state["remain_eligible"]


def test_card67_shaded_patriots_by_player_choice():
    """Card 67 shaded: Player can choose Patriots regardless of TOA status."""
    state = _base_state()
    state["spaces"] = {"Virginia": {}}
    state["toa_played"] = True  # TOA played, but player still chooses Patriots
    state["card67_faction"] = "PATRIOTS"

    late_war.evt_067_de_grasse(state, shaded=True)

    assert PATRIOTS in state["remain_eligible"]
    ops = state.get("free_ops", [])
    assert any(op[0] == PATRIOTS for op in ops)


def test_card66_shaded_patriots_by_player_choice():
    """Card 66 shaded: Player can choose Patriots regardless of TOA status."""
    state = _base_state()
    state["spaces"] = {"Florida": {}}
    state["toa_played"] = True  # TOA played, but player still chooses Patriots
    state["card66_shaded_faction"] = "PATRIOTS"

    late_war.evt_066_don_bernardo(state, shaded=True)

    ops = state.get("free_ops", [])
    assert any(op[0] == PATRIOTS for op in ops)


def test_card66_shaded_french_by_player_choice():
    """Card 66 shaded: Player can choose French regardless of TOA status."""
    state = _base_state()
    state["spaces"] = {"Florida": {}}
    state["toa_played"] = False  # TOA NOT played, but player still chooses French
    state["card66_shaded_faction"] = "FRENCH"

    late_war.evt_066_don_bernardo(state, shaded=True)

    ops = state.get("free_ops", [])
    assert any(op[0] == FRENCH for op in ops)


# ---- Card 22: Newburgh Conspiracy ----

def test_card22_unshaded_removes_from_colony_only():
    """Card 22 unshaded: Must remove Patriot units from a Colony, not a City."""
    state = _base_state()
    state["spaces"] = {
        "Boston": {MILITIA_U: 5},      # City — should be skipped
        "Virginia": {MILITIA_A: 3},    # Colony — should be selected
    }

    late_war.evt_022_newburgh_conspiracy(state, shaded=False)

    # Boston (City) should be untouched; Virginia (Colony) should lose units
    assert state["spaces"]["Boston"].get(MILITIA_U, 0) == 5
    removed = 3 - state["spaces"]["Virginia"].get(MILITIA_A, 0)
    assert removed == 3  # only 3 available, not 4


def test_card23_unshaded_does_not_move_forts():
    """Card 23 unshaded: Moves Patriot *units* (cubes) only, not Forts (bases)."""
    state = _base_state()
    state["spaces"] = {
        "South_Carolina": {MILITIA_U: 1, FORT_PAT: 1},
        "Georgia": {},
    }
    state["card23_src"] = "South_Carolina"
    state["card23_dst"] = "Georgia"

    late_war.evt_023_francis_marion(state, shaded=False)

    # Fort should stay in SC; only Militia moves to GA
    assert state["spaces"]["South_Carolina"].get(FORT_PAT, 0) == 1
    assert state["spaces"]["Georgia"].get(MILITIA_U, 0) == 1
    assert state["spaces"]["Georgia"].get(FORT_PAT, 0) == 0


# ---- Card 48: God Save the King ----

def test_card48_shaded_moves_one_faction_only():
    """Card 48 shaded: 'A non-British Faction' (singular) moves units from
    spaces with British Regulars. Only the chosen faction's units move."""
    state = _base_state()
    # Virginia adj: Norfolk, Maryland-Delaware, Northwest, Southwest, North_Carolina
    state["spaces"] = {
        "Virginia": {REGULAR_BRI: 2, MILITIA_U: 3, WARPARTY_U: 2},
        "North_Carolina": {},
    }
    # Force choosing Patriots
    state["card48_faction"] = "PATRIOTS"

    late_war.evt_048_god_save_king(state, shaded=True)

    # Patriots (Militia) should have moved out; War Parties should stay
    assert state["spaces"]["Virginia"].get(MILITIA_U, 0) == 0
    assert state["spaces"]["Virginia"].get(WARPARTY_U, 0) == 2  # untouched
    assert state["spaces"]["North_Carolina"].get(MILITIA_U, 0) == 3


def test_card48_shaded_indians_only():
    """Card 48 shaded: If Indians chosen, only War Parties move."""
    state = _base_state()
    state["spaces"] = {
        "Virginia": {REGULAR_BRI: 2, MILITIA_U: 3, WARPARTY_U: 2},
        "North_Carolina": {},
    }
    state["card48_faction"] = "INDIANS"

    late_war.evt_048_god_save_king(state, shaded=True)

    # Only War Parties should have moved
    assert state["spaces"]["Virginia"].get(WARPARTY_U, 0) == 0
    assert state["spaces"]["Virginia"].get(MILITIA_U, 0) == 3  # untouched
    assert state["spaces"]["North_Carolina"].get(WARPARTY_U, 0) == 2
