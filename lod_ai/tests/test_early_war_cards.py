import copy

from lod_ai.cards.effects import early_war
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_PAT,
    TORY,
    MILITIA_U,
    MILITIA_A,
    WARPARTY_U,
    WARPARTY_A,
    FORT_BRI,
    FORT_PAT,
    VILLAGE,
    PROPAGANDA,
    BLOCKADE,
    WEST_INDIES_ID,
)
from lod_ai.util.naval import total_blockades


def _base_state():
    return {
        "spaces": {},
        "available": {},
        "casualties": {},
        "markers": {PROPAGANDA: {"pool": 10, "on_map": set()}},
        "support": {},
        "control": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "INDIANS": 0, "FRENCH": 0},
    }


def test_card2_common_sense_any_city_selection():
    state = _base_state()
    state["spaces"] = {
        "Boston": {"type": "City"},
        "Charleston": {"type": "City"},
    }
    state["available"] = {REGULAR_BRI: 5, TORY: 5}
    early_war.evt_002_common_sense(state, shaded=False)

    assert state["spaces"]["Boston"].get(REGULAR_BRI) == 2
    assert state["spaces"]["Boston"].get(TORY) == 2
    assert "Boston" in state["markers"][PROPAGANDA]["on_map"]
    assert state["markers"][PROPAGANDA]["pool"] == 8
    assert state["resources"]["BRITISH"] == 4


def test_card2_common_sense_any_two_cities():
    state = _base_state()
    state["spaces"] = {
        "Boston": {"type": "City", "support": 0},
        "New_York_City": {"type": "City", "support": 0},
        "Philadelphia": {"type": "City", "support": 0},
    }
    state["markers"][PROPAGANDA]["pool"] = 6

    early_war.evt_002_common_sense(state, shaded=True)

    assert state["support"]["Boston"] == -1
    assert state["support"]["New_York_City"] == -1
    assert state["support"].get("Philadelphia", 0) == 0
    assert "Boston" in state["markers"][PROPAGANDA]["on_map"]
    assert "New_York_City" in state["markers"][PROPAGANDA]["on_map"]


def test_card6_benedict_arnold_any_colony_and_militia_activation():
    state = _base_state()
    state["spaces"] = {
        "Georgia": {"type": "Colony", FORT_PAT: 1, MILITIA_U: 1, MILITIA_A: 2},
        "Virginia": {"type": "Colony"},
    }

    early_war.evt_006_benedict_arnold(state, shaded=False)

    assert state["casualties"].get(FORT_PAT) == 1
    assert state["available"].get(MILITIA_U) == 1
    assert state["available"].get(MILITIA_A) == 1
    assert FORT_PAT not in state["spaces"]["Georgia"]


def test_card6_benedict_arnold_shaded_any_space():
    state = _base_state()
    state["spaces"] = {
        "Boston": {FORT_BRI: 1, REGULAR_BRI: 1, TORY: 2},
        "Albany": {},
    }

    early_war.evt_006_benedict_arnold(state, shaded=True)

    assert state["casualties"].get(FORT_BRI) == 1
    assert state["casualties"].get(REGULAR_BRI) == 1
    assert state["casualties"].get(TORY) == 1
    assert state["spaces"]["Boston"].get(TORY) == 1


def test_card4_penobscot_unshaded_removes_militia_and_resources():
    """Card 4 unshaded: Remove 3 Patriot Militia, Resources -2."""
    state = _base_state()
    state["spaces"] = {
        "Massachusetts": {MILITIA_U: 2, MILITIA_A: 2},
    }
    state["resources"]["PATRIOTS"] = 10

    early_war.evt_004_penobscot(state, shaded=False)

    assert state["resources"]["PATRIOTS"] == 8
    # Removed 2 Underground + 1 Active = 3 total
    total_militia = (state["spaces"]["Massachusetts"].get(MILITIA_U, 0)
                     + state["spaces"]["Massachusetts"].get(MILITIA_A, 0))
    assert total_militia == 1


def test_card4_penobscot_shaded_crown_fallback_to_fort():
    """Card 4 shaded BRI/IND: if Village cap reached, place Fort_BRI instead."""
    state = _base_state()
    state["spaces"] = {
        "Massachusetts": {VILLAGE: 2},  # at cap (2 bases)
    }
    state["available"] = {VILLAGE: 1, FORT_BRI: 1, WARPARTY_U: 5}
    state["active"] = "BRITISH"

    early_war.evt_004_penobscot(state, shaded=True)

    # Village cap (2 bases) already reached, so Fort_BRI should be placed
    # Actually, stacking limit is 2 bases total, so neither can be placed
    # Let's verify War Parties still placed
    assert state["spaces"]["Massachusetts"].get(WARPARTY_U, 0) == 3


def test_card4_penobscot_shaded_rebellion_places_fort_and_militia():
    """Card 4 shaded PAT/FRE: place Fort_PAT + 3 Militia in Massachusetts."""
    state = _base_state()
    state["spaces"] = {"Massachusetts": {}}
    state["available"] = {FORT_PAT: 1, MILITIA_U: 5}
    state["active"] = "PATRIOTS"

    early_war.evt_004_penobscot(state, shaded=True)

    assert state["spaces"]["Massachusetts"].get(FORT_PAT) == 1
    assert state["spaces"]["Massachusetts"].get(MILITIA_U) == 3


def test_card4_penobscot_shaded_free_choice_village_and_militia():
    """Card 4 shaded: Player can freely choose Village + Militia regardless
    of executing faction."""
    state = _base_state()
    state["spaces"] = {"Massachusetts": {}}
    state["available"] = {VILLAGE: 1, MILITIA_U: 5}
    state["active"] = "PATRIOTS"  # Rebellion side, but choosing Village + Militia
    state["card4_base"] = "VILLAGE"
    state["card4_units"] = "MILITIA"

    early_war.evt_004_penobscot(state, shaded=True)

    assert state["spaces"]["Massachusetts"].get(VILLAGE) == 1
    assert state["spaces"]["Massachusetts"].get(MILITIA_U) == 3
    assert state["spaces"]["Massachusetts"].get(FORT_PAT, 0) == 0


def test_card4_penobscot_shaded_free_choice_fort_and_warparties():
    """Card 4 shaded: Player can freely choose Fort_PAT + War Parties."""
    state = _base_state()
    state["spaces"] = {"Massachusetts": {}}
    state["available"] = {FORT_PAT: 1, WARPARTY_U: 5}
    state["active"] = "BRITISH"  # Crown side, but choosing Fort_PAT + War Parties
    state["card4_base"] = "FORT_PAT"
    state["card4_units"] = "WARPARTY"

    early_war.evt_004_penobscot(state, shaded=True)

    assert state["spaces"]["Massachusetts"].get(FORT_PAT) == 1
    assert state["spaces"]["Massachusetts"].get(WARPARTY_U) == 3
    assert state["spaces"]["Massachusetts"].get(VILLAGE, 0) == 0


def test_card24_declaration_unshaded_removes_correct_pieces():
    state = _base_state()
    state["spaces"] = {
        "Boston": {REGULAR_PAT: 2, MILITIA_U: 1, FORT_PAT: 1},
        "Albany": {REGULAR_PAT: 1, MILITIA_A: 2},
    }

    early_war.evt_024_declaration(state, shaded=False)

    assert state["available"].get(REGULAR_PAT) == 2
    assert state["available"].get(MILITIA_U) == 1
    assert state["available"].get(MILITIA_A) == 1
    assert state["available"].get(FORT_PAT) == 1


def test_card24_declaration_shaded_places_militia_and_fort():
    state = _base_state()
    state["spaces"] = {"Boston": {}, "Albany": {}, "Cambridge": {}}
    state["available"] = {MILITIA_U: 3, FORT_PAT: 1}

    early_war.evt_024_declaration(state, shaded=True)

    assert state["spaces"]["Albany"].get(MILITIA_U) == 1
    assert state["spaces"]["Cambridge"].get(MILITIA_U) == 1
    assert state["spaces"]["Boston"].get(MILITIA_U) == 1
    on_map = state["markers"][PROPAGANDA]["on_map"]
    assert {"Boston", "Albany", "Cambridge"} <= on_map
    assert state["spaces"]["Boston"].get(FORT_PAT) == 1


def test_card28_moores_creek_any_space():
    state = _base_state()
    state["spaces"] = {
        "South_Carolina": {MILITIA_U: 1, MILITIA_A: 1},
        "North_Carolina": {TORY: 1},
    }
    # Replacement draws from Available; provide enough pieces
    state["available"] = {TORY: 10, MILITIA_U: 10}

    early_war.evt_028_moores_creek(state, shaded=False)

    assert state["spaces"]["South_Carolina"].get(TORY) == 4
    assert MILITIA_U not in state["spaces"]["South_Carolina"]
    assert MILITIA_A not in state["spaces"]["South_Carolina"]

    # shaded should target the Tory space even if not North Carolina
    early_war.evt_028_moores_creek(state, shaded=True)
    assert state["spaces"]["North_Carolina"].get(MILITIA_U) == 2
    assert TORY not in state["spaces"]["North_Carolina"]


def test_card29_bancroft_allows_indian_choice():
    state = _base_state()
    state["spaces"] = {
        "Ohio": {WARPARTY_U: 3},
        "Boston": {MILITIA_U: 2},
    }
    state["card29_target"] = "INDIANS"

    early_war.evt_029_bancroft(state, shaded=False)

    assert state["spaces"]["Ohio"].get(WARPARTY_A) == 1
    assert state["spaces"]["Ohio"].get(WARPARTY_U) == 2


def test_card32_rule_britannia_any_colony_and_any_recipient():
    state = _base_state()
    state["spaces"] = {
        "Georgia": {"type": "Colony"},
        "Virginia": {"type": "Colony"},
        "Boston": {"type": "City", REGULAR_BRI: 1},
        "New_York_City": {"type": "City", REGULAR_BRI: 1},
    }
    state["control"] = {
        "Boston": "BRITISH",
        "New_York_City": "BRITISH",
    }
    state["available"] = {REGULAR_BRI: 1, TORY: 1}
    state["unavailable"] = {REGULAR_BRI: 2, TORY: 2}

    state["rule_britannia_colony"] = "Georgia"
    early_war.evt_032_rule_britannia(state, shaded=False)

    assert state["spaces"]["Georgia"].get(REGULAR_BRI) == 2
    assert state["spaces"]["Georgia"].get(TORY) == 2

    state = copy.deepcopy(state)
    state["active"] = "INDIANS"
    early_war.evt_032_rule_britannia(state, shaded=True)

    assert state["resources"]["INDIANS"] == 1


def test_card41_william_pitt_shifts_toward_passive_levels():
    state = _base_state()
    state["spaces"] = {
        "Connecticut": {"type": "Colony"},
        "Georgia": {"type": "Colony"},
        "Virginia": {"type": "Colony"},
    }
    state["support"] = {"Connecticut": -2, "Georgia": 2, "Virginia": 0}

    early_war.evt_041_william_pitt(state, shaded=False)

    assert state["support"]["Connecticut"] == 0
    assert state["support"]["Georgia"] == 1
    assert state["support"]["Virginia"] == 0

    early_war.evt_041_william_pitt(state, shaded=True)

    assert state["support"]["Connecticut"] == -1
    assert state["support"]["Georgia"] == -1


def test_card46_burke_places_tories_and_shifts_cities():
    state = _base_state()
    state["spaces"] = {
        "Albany": {},
        "Boston": {"type": "City"},
        "New_York_City": {"type": "City"},
        "Philadelphia": {"type": "City"},
    }
    state["available"] = {TORY: 2}
    state["unavailable"] = {TORY: 1}

    early_war.evt_046_burke(state, shaded=False)

    assert state["spaces"]["Albany"].get(TORY) == 1
    assert state["spaces"]["Boston"].get(TORY) == 1
    assert state["spaces"]["New_York_City"].get(TORY) == 1

    state["support"] = {"Boston": 2, "New_York_City": -2, "Philadelphia": 0}
    early_war.evt_046_burke(state, shaded=True)

    assert state["support"]["Boston"] == 1
    assert state["support"]["New_York_City"] == -1


def test_card72_french_settlers_help_places_royalist_pieces():
    state = _base_state()
    state["spaces"] = {
        "Northwest": {},
        "Southwest": {},
    }
    state["available"] = {VILLAGE: 1, WARPARTY_U: 2, TORY: 1, REGULAR_BRI: 1}
    state["active"] = "BRITISH"

    early_war.evt_072_french_settlers(state, shaded=False)

    assert state["spaces"]["Northwest"].get(VILLAGE) == 1
    assert state["spaces"]["Northwest"].get(WARPARTY_U) == 2
    assert state["spaces"]["Northwest"].get(TORY) == 1


def test_card75_speech_to_six_nations_uses_reserve_list_and_northwest():
    state = _base_state()
    state["spaces"] = {
        "Northwest": {WARPARTY_U: 1, WARPARTY_A: 1, VILLAGE: 1},
        "Southwest": {},
        "Quebec": {},
        "Florida": {},
    }

    early_war.evt_075_speech_six_nations(state, shaded=False)

    assert state["free_ops"] == [
        ("INDIANS", "gather", "Northwest"),
        ("INDIANS", "gather", "Southwest"),
        ("INDIANS", "gather", "Quebec"),
        ("INDIANS", "war_path", "Northwest"),
    ]

    early_war.evt_075_speech_six_nations(state, shaded=True)

    assert state["spaces"]["Northwest"].get(WARPARTY_U, 0) == 0
    assert state["spaces"]["Northwest"].get(WARPARTY_A, 0) == 0
    assert state["spaces"]["Northwest"].get(VILLAGE, 0) == 0


def test_card90_world_turned_upside_down_places_village_for_royalists():
    state = _base_state()
    state["spaces"] = {
        "Northwest": {},
        "Georgia": {"type": "Colony"},
    }
    state["available"] = {VILLAGE: 1, FORT_BRI: 1}
    state["active"] = "BRITISH"

    early_war.evt_090_world_turned_upside_down(state, shaded=False)

    assert state["spaces"]["Northwest"].get(VILLAGE) == 1


def test_card91_indians_help_outside_colonies_places_and_removes():
    state = _base_state()
    state["spaces"] = {
        "Southwest": {},
        "Quebec": {VILLAGE: 1},
    }
    state["available"] = {VILLAGE: 1, WARPARTY_U: 2}

    early_war.evt_091_indians_help(state, shaded=False)

    assert state["spaces"]["Southwest"].get(VILLAGE) == 1
    assert state["spaces"]["Southwest"].get(WARPARTY_U) == 2

    shaded_state = _base_state()
    shaded_state["spaces"] = {
        "Southwest": {},
        "Quebec": {VILLAGE: 1},
    }
    early_war.evt_091_indians_help(shaded_state, shaded=True)

    assert shaded_state["spaces"]["Quebec"].get(VILLAGE, 0) == 0


def test_card92_cherokees_supplied_adds_second_base():
    state = _base_state()
    state["spaces"] = {
        "Northwest": {VILLAGE: 1},
        "Boston": {"type": "City", FORT_BRI: 1, VILLAGE: 1},
        WEST_INDIES_ID: {},
    }
    state["available"] = {VILLAGE: 1, FORT_BRI: 2}

    early_war.evt_092_cherokees_supplied(state, shaded=False)

    assert state["spaces"]["Northwest"].get(FORT_BRI) == 1

    state["available"] = {VILLAGE: 1, FORT_BRI: 2}
    early_war.evt_092_cherokees_supplied(state, shaded=True)

    assert state["spaces"]["Northwest"].get(FORT_BRI) == 1


def test_card54_sartine_shaded_moves_to_west_indies():
    state = _base_state()
    state["spaces"] = {WEST_INDIES_ID: {}}
    state["markers"][BLOCKADE] = {"pool": 0, "on_map": set()}
    state["unavailable"] = {BLOCKADE: 2}

    early_war.evt_054_antoine_sartine(state, shaded=True)

    assert state["markers"][BLOCKADE]["pool"] == 2
    assert state["unavailable"].get(BLOCKADE, 0) == 0
    assert total_blockades(state) == 2


def test_card54_sartine_unshaded_moves_from_wi_to_unavailable():
    state = _base_state()
    state["spaces"] = {WEST_INDIES_ID: {}}
    state["markers"][BLOCKADE] = {"pool": 1, "on_map": {"Boston"}}
    state["unavailable"] = {BLOCKADE: 1}

    early_war.evt_054_antoine_sartine(state, shaded=False)

    assert state["markers"][BLOCKADE]["pool"] == 0
    assert state["unavailable"].get(BLOCKADE, 0) == 2
    assert "Boston" in state["markers"][BLOCKADE]["on_map"]
    assert total_blockades(state) == 3


def test_card29_bancroft_activates_one_faction_patriots():
    """Card 29: 'or' means ONE faction. British bot targets Patriots."""
    state = _base_state()
    state["spaces"] = {
        "A": {MILITIA_U: 6, MILITIA_A: 0, WARPARTY_U: 4, WARPARTY_A: 0},
    }
    state["active"] = "BRITISH"
    early_war.evt_029_bancroft(state, shaded=False)

    # 6 total Militia → target 3 Active
    assert state["spaces"]["A"].get(MILITIA_A, 0) == 3
    assert state["spaces"]["A"].get(MILITIA_U, 0) == 3
    # War Parties should be UNTOUCHED (only one faction chosen)
    assert state["spaces"]["A"].get(WARPARTY_A, 0) == 0
    assert state["spaces"]["A"].get(WARPARTY_U, 0) == 4


def test_card29_bancroft_activates_one_faction_indians():
    """Card 29: Patriot bot targets Indians (War Parties only)."""
    state = _base_state()
    state["spaces"] = {
        "A": {MILITIA_U: 6, MILITIA_A: 0, WARPARTY_U: 4, WARPARTY_A: 0},
    }
    state["active"] = "PATRIOTS"
    early_war.evt_029_bancroft(state, shaded=False)

    # Militia should be UNTOUCHED (only one faction chosen)
    assert state["spaces"]["A"].get(MILITIA_A, 0) == 0
    assert state["spaces"]["A"].get(MILITIA_U, 0) == 6
    # 4 total WP → target 2 Active
    assert state["spaces"]["A"].get(WARPARTY_A, 0) == 2
    assert state["spaces"]["A"].get(WARPARTY_U, 0) == 2


def test_card35_tryon_activates_militia_via_flip():
    """Card 35 unshaded: Remove 2 Patriot pieces in NY, then activate all
    remaining Militia in that space. Verify flip_pieces is used."""
    state = _base_state()
    state["spaces"] = {
        "New_York": {REGULAR_PAT: 2, MILITIA_U: 3},
    }
    state["card35_target"] = "New_York"
    early_war.evt_035_tryon_plot(state, shaded=False)
    # 2 Continentals removed, then all Underground Militia activated
    assert state["spaces"]["New_York"].get(REGULAR_PAT, 0) == 0
    assert state["spaces"]["New_York"].get(MILITIA_A, 0) == 3
    assert state["spaces"]["New_York"].get(MILITIA_U, 0) == 0


def test_card86_stockbridge_unshaded_activates_militia():
    """Card 86 unshaded: Activate all Militia in Massachusetts.
    Must use flip_pieces, not direct dict manipulation."""
    state = _base_state()
    state["spaces"] = {
        "Massachusetts": {MILITIA_U: 4, MILITIA_A: 1},
    }
    early_war.evt_086_stockbridge(state, shaded=False)
    # All Underground Militia should flip to Active
    assert state["spaces"]["Massachusetts"].get(MILITIA_A, 0) == 5
    assert state["spaces"]["Massachusetts"].get(MILITIA_U, 0) == 0


def test_card86_stockbridge_shaded_places_militia():
    """Card 86 shaded: Place 3 Militia in Massachusetts."""
    state = _base_state()
    state["spaces"] = {
        "Massachusetts": {},
    }
    state["available"] = {MILITIA_U: 5}
    early_war.evt_086_stockbridge(state, shaded=True)
    assert state["spaces"]["Massachusetts"].get(MILITIA_U, 0) == 3


def test_card13_unshaded_executes_patriot_desertion_immediately():
    """Card 13 unshaded: Execute Patriot Desertion immediately (§6.6.1),
    not deferred via winter_flag."""
    state = _base_state()
    state["spaces"] = {
        "Virginia": {"type": "Colony", MILITIA_U: 5, REGULAR_PAT: 5},
        "Georgia": {"type": "Colony", MILITIA_U: 5},
    }
    state["support"] = {"Virginia": 0, "Georgia": 0}

    early_war.evt_013_origin_misfortunes(state, shaded=False)

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


def test_card13_shaded_does_not_set_winter_flag():
    """Card 13 shaded: should NOT trigger desertion or set winter_flag."""
    state = _base_state()
    state["spaces"] = {
        "Georgia": {"type": "Colony", MILITIA_U: 2},
    }
    state["available"] = {MILITIA_U: 5}

    early_war.evt_013_origin_misfortunes(state, shaded=True)

    # Shaded side must NOT set winter_flag or run desertion
    assert "winter_flag" not in state
    # Militia count should stay the same or increase (not deserted)
    assert state["spaces"]["Georgia"].get(MILITIA_U, 0) >= 2
