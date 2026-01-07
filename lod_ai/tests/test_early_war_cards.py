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
    PROPAGANDA,
)


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

    assert state["casualties"].get(REGULAR_PAT) == 2
    assert state["available"].get(MILITIA_U) == 1
    assert state["available"].get(MILITIA_A) == 1
    assert state["casualties"].get(FORT_PAT) == 1


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
        "Boston": {"type": "City", "British_Control": True},
        "New_York_City": {"type": "City", "British_Control": True},
    }
    state["available"] = {REGULAR_BRI: 1, TORY: 1}
    state["unavailable"] = {REGULAR_BRI: 2, TORY: 2}

    state["rule_britannia_colony"] = "Georgia"
    early_war.evt_032_rule_britannia(state, shaded=False)

    assert state["spaces"]["Georgia"].get(REGULAR_BRI) == 2
    assert state["spaces"]["Georgia"].get(TORY) == 2

    state = copy.deepcopy(state)
    state["rule_britannia_recipient"] = "INDIANS"
    early_war.evt_032_rule_britannia(state, shaded=True)

    assert state["resources"]["INDIANS"] == 1
