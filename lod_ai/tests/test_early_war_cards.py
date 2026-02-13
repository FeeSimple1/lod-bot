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


def test_card29_bancroft_activates_both_factions():
    """Card 29: Both Patriots (Militia) and Indians (WP) should activate."""
    state = _base_state()
    state["spaces"] = {
        "A": {MILITIA_U: 6, MILITIA_A: 0, WARPARTY_U: 4, WARPARTY_A: 0},
    }
    early_war.evt_029_bancroft(state, shaded=False)

    # 6 total Militia → target 3 Active
    assert state["spaces"]["A"].get(MILITIA_A, 0) == 3
    assert state["spaces"]["A"].get(MILITIA_U, 0) == 3
    # 4 total WP → target 2 Active
    assert state["spaces"]["A"].get(WARPARTY_A, 0) == 2
    assert state["spaces"]["A"].get(WARPARTY_U, 0) == 2
