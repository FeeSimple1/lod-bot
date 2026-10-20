"""§6.3 counts Fort pieces, including legal two-Fort stacks (§1.4.2)."""

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.util.year_end import _resource_income


def _state(spaces):
    state = {
        "spaces": spaces,
        "resources": {f: 0 for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": set()}},
        "history": [],
    }
    refresh_control(state)
    return state


@pytest.mark.parametrize("faction,fort", [(C.BRITISH, C.FORT_BRI),
                                         (C.PATRIOTS, C.FORT_PAT)])
@pytest.mark.parametrize("stacked", [False, True])
def test_income_counts_each_fort_instead_of_each_fort_space(faction, fort, stacked):
    # Both layouts have two Forts. Separate Patriot spaces additionally
    # earn 1 for two Rebellion-Controlled spaces, per §6.3.3.
    spaces = ({"Georgia": {fort: 2}} if stacked else
              {"Georgia": {fort: 1}, "Virginia": {fort: 1}})
    state = _state(spaces)

    _resource_income(state)

    control_income = int(faction == C.PATRIOTS and not stacked)
    assert state["resources"][faction] == 2 + control_income
    assert state["spaces"]["Georgia"][fort] == (2 if stacked else 1)


def test_stacked_british_forts_add_to_city_income_and_respect_resource_cap():
    # §6.3.1: two Forts plus Boston's 1 Population yield 3, capped at 50.
    state = _state({"Boston": {C.FORT_BRI: 2}})
    state["resources"][C.BRITISH] = 48

    _resource_income(state)

    assert state["resources"][C.BRITISH] == 50
    assert any("British earn +3 Resources" in entry["msg"] for entry in state["history"])


def test_blockade_suppresses_city_income_without_suppressing_stacked_fort_income():
    state = _state({"Boston": {C.FORT_BRI: 2}})
    state["markers"][C.BLOCKADE]["on_map"] = {"Boston"}

    _resource_income(state)

    assert state["resources"][C.BRITISH] == 2
