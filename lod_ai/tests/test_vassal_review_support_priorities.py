"""§§8.4.5/8.5.9 rank net political changes, with §1.9 Blockades."""

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.util.year_end import _support_phase


def _state(faction, levels, *, resources=2):
    tags = ({C.REGULAR_BRI: 1, C.TORY: 1} if faction == C.BRITISH else
            {C.REGULAR_PAT: 1})
    state = {
        "spaces": {sid: dict(tags) for sid in levels},
        "support": dict(levels),
        "resources": {f: resources if f == faction else 0
                      for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": {"New_York_City"}},
                    C.RAID: {"pool": C.MAX_RAID, "on_map": {}},
                    C.PROPAGANDA: {"pool": C.MAX_PROPAGANDA, "on_map": {}}},
        "history": [],
    }
    refresh_control(state)
    return state


@pytest.mark.parametrize("start,end", [(C.ACTIVE_OPPOSITION, C.NEUTRAL),
                                       (C.PASSIVE_OPPOSITION, C.PASSIVE_SUPPORT)])
def test_reward_loyalty_values_opposition_loss_in_blockaded_city(start, end):
    # NYC Pop 2: removing Opposition gains 4 or 2, even while Blockaded.
    # Georgia gains only 1. The two-Resource purse must go to NYC first.
    state = _state(C.BRITISH, {"New_York_City": start, "Georgia": C.PASSIVE_SUPPORT})

    _support_phase(state)

    assert state["support"] == {"New_York_City": end, "Georgia": C.PASSIVE_SUPPORT}
    assert state["resources"][C.BRITISH] == 0


@pytest.mark.parametrize("start", [C.NEUTRAL, C.PASSIVE_SUPPORT])
def test_committees_values_opposition_gain_in_blockaded_city(start):
    # From Neutral, two shifts gain 4 Opposition; across Neutral they
    # gain 2. Georgia can gain only 1, so NYC takes the full purse.
    state = _state(C.PATRIOTS, {"New_York_City": start, "Georgia": C.PASSIVE_OPPOSITION})

    _support_phase(state)

    assert state["support"] == {"New_York_City": start - 2, "Georgia": C.PASSIVE_OPPOSITION}
    assert state["resources"][C.PATRIOTS] == 0


@pytest.mark.parametrize("faction,city_level,other_level,other_end", [
    (C.BRITISH, C.NEUTRAL, C.NEUTRAL, C.ACTIVE_SUPPORT),
    (C.PATRIOTS, C.ACTIVE_SUPPORT, C.NEUTRAL, C.ACTIVE_OPPOSITION),
])
def test_blockaded_support_changes_do_not_invent_a_political_gain(faction, city_level, other_level, other_end):
    # NYC's two shifts stay at Support or reach Neutral: neither changes
    # its suppressed Support total. Unblocked Georgia has a real gain.
    state = _state(faction, {"New_York_City": city_level, "Georgia": other_level})

    _support_phase(state)

    assert state["support"] == {"New_York_City": city_level, "Georgia": other_end}


def test_fewest_markers_still_precedes_largest_political_gain():
    state = _state(C.PATRIOTS, {"New_York_City": C.NEUTRAL, "Georgia": C.NEUTRAL})
    state["markers"][C.RAID] = {"pool": C.MAX_RAID - 1, "on_map": {"New_York_City": 1}}

    _support_phase(state)

    assert state["support"]["Georgia"] == C.ACTIVE_OPPOSITION
    assert state["support"]["New_York_City"] == C.NEUTRAL
    assert state["markers"][C.RAID]["on_map"] == {"New_York_City": 1}
