from lod_ai.cards.effects import middle_war
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_PAT,
    TORY,
    MILITIA_A,
    MILITIA_U,
    FORT_PAT,
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
    state = _base_state()
    state["spaces"] = {
        "Boston": {MILITIA_A: 2, "population": 6},
        "Philadelphia": {MILITIA_U: 1, "population": 3},
        "New_York_City": {REGULAR_BRI: 1, "population": 6},
    }

    middle_war.evt_071_treaty_amity(state, shaded=False)

    assert state["resources"][PATRIOTS] == 3
    assert state["resources"][FRENCH] == 3
