from lod_ai.cards.effects import middle_war
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_FRE,
    REGULAR_PAT,
    TORY,
    MILITIA_A,
    MILITIA_U,
    FORT_PAT,
    WEST_INDIES_ID,
    PATRIOTS,
    BRITISH,
    FRENCH,
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
    }


def test_card3_unshaded_removes_patriot_pieces():
    state = _base_state()
    state["spaces"] = {
        "Northwest": {MILITIA_A: 1, MILITIA_U: 2, REGULAR_PAT: 1, FORT_PAT: 1},
        "Southwest": {MILITIA_U: 1},
    }

    middle_war.evt_003_illinois_campaign(state, shaded=False)

    assert not state["spaces"]["Northwest"]
    assert not state["spaces"]["Southwest"]
    assert state["available"].get(MILITIA_A) == 1
    assert state["available"].get(MILITIA_U) == 3
    assert state["available"].get(REGULAR_PAT) == 1
    assert state["available"].get(FORT_PAT) == 1


def test_card5_unshaded_sets_ineligible_through_next():
    state = _base_state()

    middle_war.evt_005_lord_stirling(state, shaded=False)

    assert PATRIOTS in state["ineligible_through_next"]


def test_card38_unshaded_places_royal_greens_and_keeps_eligible():
    state = _base_state()
    state["spaces"] = {"Quebec": {}}
    state["available"] = {REGULAR_BRI: 1, TORY: 2}
    state["unavailable"] = {REGULAR_BRI: 3, TORY: 2}
    state["ineligible_next"].add(BRITISH)
    state["ineligible_through_next"].add(BRITISH)

    middle_war.evt_038_johnsons_royal_greens(state, shaded=False)

    assert state["spaces"]["Quebec"].get(REGULAR_BRI) == 4
    assert state["spaces"]["Quebec"].get(TORY, 0) == 0
    assert BRITISH not in state["ineligible_next"]
    assert BRITISH not in state["ineligible_through_next"]
    assert BRITISH in state["remain_eligible"]


def test_card71_unshaded_resources_from_rebellion_cities():
    """Per card reference: 'Add population of Cities under Rebellion Control
    to Patriot Resources.'  Only Patriots receive, not French."""
    state = _base_state()
    state["spaces"] = {
        "Boston": {MILITIA_A: 2},
        "Philadelphia": {MILITIA_U: 1},
        "New_York_City": {REGULAR_BRI: 1},
    }
    # Pre-set control so test does not depend on refresh_control details
    state["control"] = {
        "Boston": "REBELLION",
        "Philadelphia": "REBELLION",
        "New_York_City": BRITISH,
    }

    middle_war.evt_071_treaty_amity(state, shaded=False)

    # Boston (pop 1) + Philadelphia (pop 1) = 2 per map_base.csv
    assert state["resources"][PATRIOTS] == 2
    assert state["resources"][FRENCH] == 0


def test_card71_shaded_french_resources():
    """Per card reference: 'French Resources +5.'"""
    state = _base_state()
    middle_war.evt_071_treaty_amity(state, shaded=True)
    assert state["resources"][FRENCH] == 5


def test_card50_shaded_draws_french_regulars_from_west_indies():
    """Card 50 shaded: French Regulars come from Available or West Indies."""
    state = _base_state()
    state["spaces"] = {
        "Georgia": {"type": "Colony"},
        WEST_INDIES_ID: {REGULAR_FRE: 2},
    }
    # No French Regulars in Available — must draw from West Indies
    state["available"] = {REGULAR_PAT: 5, REGULAR_FRE: 0}
    state["card50_colony"] = "Georgia"

    middle_war.evt_050_destaing_arrives(state, shaded=True)

    assert state["spaces"]["Georgia"].get(REGULAR_PAT) == 2
    assert state["spaces"]["Georgia"].get(REGULAR_FRE) == 2
    assert state["spaces"][WEST_INDIES_ID].get(REGULAR_FRE, 0) == 0


def test_card50_shaded_prefers_available_before_west_indies():
    """Card 50 shaded: draw from Available first, then West Indies."""
    state = _base_state()
    state["spaces"] = {
        "Georgia": {"type": "Colony"},
        WEST_INDIES_ID: {REGULAR_FRE: 3},
    }
    state["available"] = {REGULAR_PAT: 5, REGULAR_FRE: 1}
    state["card50_colony"] = "Georgia"

    middle_war.evt_050_destaing_arrives(state, shaded=True)

    assert state["spaces"]["Georgia"].get(REGULAR_PAT) == 2
    assert state["spaces"]["Georgia"].get(REGULAR_FRE) == 2
    # 1 came from Available, 1 from West Indies
    assert state["spaces"][WEST_INDIES_ID].get(REGULAR_FRE) == 2


def test_card50_unshaded_ineligible_through_next():
    """Card 50 unshaded: French ineligible through next card, remove 2 FRE regs."""
    state = _base_state()
    state["spaces"] = {WEST_INDIES_ID: {REGULAR_FRE: 3}}

    middle_war.evt_050_destaing_arrives(state, shaded=False)

    assert state["spaces"][WEST_INDIES_ID].get(REGULAR_FRE) == 1
    assert state["available"].get(REGULAR_FRE) == 2
    assert FRENCH in state["ineligible_through_next"]


def test_card8_culpeper_unshaded_activates_militia():
    """Card 8 unshaded: Activate three Patriot Militia anywhere.
    Must use flip_pieces, not direct dict manipulation."""
    from lod_ai.rules_consts import WARPARTY_U, WARPARTY_A, VILLAGE, FORT_BRI
    state = _base_state()
    state["spaces"] = {
        "Virginia": {MILITIA_U: 2},
        "New_York": {MILITIA_U: 1, MILITIA_A: 1},
        "Georgia": {MILITIA_U: 1},
    }
    middle_war.evt_008_culpeper_ring(state, shaded=False)
    # Should flip 3 Underground→Active across spaces (2 in Virginia, 1 in NY)
    total_active = sum(
        sp.get(MILITIA_A, 0) for sp in state["spaces"].values()
    )
    total_underground = sum(
        sp.get(MILITIA_U, 0) for sp in state["spaces"].values()
    )
    # Started with 4U + 1A, should flip 3 → 1U + 4A
    assert total_active == 4
    assert total_underground == 1


def test_card8_culpeper_unshaded_multi_flip_per_space():
    """Card 8 unshaded: Should flip multiple Militia in one space, not just 1."""
    state = _base_state()
    state["spaces"] = {
        "Virginia": {MILITIA_U: 3},
    }
    middle_war.evt_008_culpeper_ring(state, shaded=False)
    # All 3 should flip in Virginia (no need to look at other spaces)
    assert state["spaces"]["Virginia"].get(MILITIA_A, 0) == 3
    assert state["spaces"]["Virginia"].get(MILITIA_U, 0) == 0


def test_card8_culpeper_shaded_removes_british():
    """Card 8 shaded: Remove three British cubes to Casualties."""
    state = _base_state()
    state["spaces"] = {
        "Virginia": {REGULAR_BRI: 2, TORY: 3},
    }
    middle_war.evt_008_culpeper_ring(state, shaded=True)
    # Should remove 2 Regulars + 1 Tory to casualties (Regulars first)
    assert state["spaces"]["Virginia"].get(REGULAR_BRI, 0) == 0
    assert state["spaces"]["Virginia"].get(TORY, 0) == 2
    assert state["casualties"].get(REGULAR_BRI, 0) == 2
    assert state["casualties"].get(TORY, 0) == 1


def test_card77_burgoyne_unshaded_flips_warparties_underground():
    """Card 77 unshaded: All Active War Parties go Underground.
    Must use flip_pieces to avoid corrupting Available pool."""
    from lod_ai.rules_consts import WARPARTY_U, WARPARTY_A, VILLAGE, FORT_BRI
    state = _base_state()
    state["spaces"] = {
        "New_York": {REGULAR_BRI: 1, WARPARTY_A: 3, WARPARTY_U: 1, VILLAGE: 1},
        "Quebec": {WARPARTY_A: 2, REGULAR_BRI: 1},
    }
    state["available"] = {VILLAGE: 2, WARPARTY_U: 0}
    state["card77_space"] = "New_York"

    middle_war.evt_077_burgoyne(state, shaded=False)

    # All Active War Parties should be Underground
    assert state["spaces"]["New_York"].get(WARPARTY_A, 0) == 0
    assert state["spaces"]["New_York"].get(WARPARTY_U, 0) == 4  # 1 orig + 3 flipped
    assert state["spaces"]["Quebec"].get(WARPARTY_A, 0) == 0
    assert state["spaces"]["Quebec"].get(WARPARTY_U, 0) == 2
    # Available pool should NOT be corrupted (no WP stolen from map)
    assert state["available"].get(WARPARTY_U, 0) == 0


def test_card12_unshaded_executes_patriot_desertion_immediately():
    """Card 12 unshaded: Execute Patriot Desertion immediately (§6.6.1),
    not deferred via winter_flag."""
    state = _base_state()
    state["spaces"] = {
        "Virginia": {"type": "Colony", MILITIA_U: 5, REGULAR_PAT: 5},
        "Georgia": {"type": "Colony", MILITIA_U: 5},
    }
    state["support"] = {"Virginia": 0, "Georgia": 0}

    middle_war.evt_012_martha_to_valley_forge(state, shaded=False)

    # 10 total Militia → remove 2 (1-in-5).  5 Continentals → remove 1.
    total_mil = sum(
        sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0)
        for sp in state["spaces"].values()
    )
    total_con = sum(
        sp.get(REGULAR_PAT, 0)
        for sp in state["spaces"].values()
    )
    assert total_mil == 8   # 10 - 2
    assert total_con == 4   # 5 - 1
    # Must NOT set winter_flag
    assert "winter_flag" not in state


def test_card12_shaded_resources():
    """Card 12 shaded: Patriot Resources +5."""
    state = _base_state()
    middle_war.evt_012_martha_to_valley_forge(state, shaded=True)
    assert state["resources"][PATRIOTS] == 5
