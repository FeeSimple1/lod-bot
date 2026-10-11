"""Event selection counts Blockades for Support only (§§1.9, 8.3.6)."""

import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.cards.effects.late_war import evt_039_king_mob
from lod_ai.cards.effects.shared import select_support_shift_spaces
from lod_ai.victory import _summarize_board


def _state(faction, support, blockaded, seed=0):
    return {
        "active": faction,
        "spaces": {sid: {} for sid in support},
        "support": dict(support),
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": set(blockaded)}},
        "rng": random.Random(seed),
        "history": [],
    }


@pytest.mark.parametrize("faction", [C.BRITISH, C.INDIANS])
def test_royalist_support_gain_ignores_blockaded_city_population(faction):
    state = _state(faction,
                   {"New_York_City": C.NEUTRAL, "Boston": C.NEUTRAL},
                   {"New_York_City"})

    assert select_support_shift_spaces(
        state, state["spaces"], 1, target=C.ACTIVE_SUPPORT,
    ) == ["Boston"]


@pytest.mark.parametrize("faction", [C.BRITISH, C.INDIANS])
def test_royalist_prefers_harmless_blockaded_support_loss(faction):
    state = _state(faction,
                   {"New_York_City": C.ACTIVE_SUPPORT,
                    "Boston": C.ACTIVE_SUPPORT}, {"New_York_City"})

    assert select_support_shift_spaces(
        state, state["spaces"], 1, target=C.NEUTRAL,
    ) == ["New_York_City"]


@pytest.mark.parametrize("faction", [C.PATRIOTS, C.FRENCH])
def test_rebellion_prefers_actual_support_loss_over_blockaded_marker(faction):
    state = _state(faction,
                   {"New_York_City": C.ACTIVE_SUPPORT,
                    "Boston": C.ACTIVE_SUPPORT}, {"New_York_City"})

    assert select_support_shift_spaces(
        state, state["spaces"], 1, target=C.NEUTRAL,
    ) == ["Boston"]


@pytest.mark.parametrize("faction,level,target", [
    (C.BRITISH, C.ACTIVE_OPPOSITION, C.NEUTRAL),
    (C.INDIANS, C.ACTIVE_OPPOSITION, C.NEUTRAL),
    (C.PATRIOTS, C.NEUTRAL, C.ACTIVE_OPPOSITION),
    (C.FRENCH, C.NEUTRAL, C.ACTIVE_OPPOSITION),
])
def test_opposition_still_uses_blockaded_city_printed_population(faction, level, target):
    state = _state(faction, {"New_York_City": level, "Boston": level},
                   {"New_York_City"})

    assert select_support_shift_spaces(
        state, state["spaces"], 1, target=target,
    ) == ["New_York_City"]


def test_question_space_precedes_larger_gain_and_other_candidates_follow():
    """§8.3.5 question matches precede the §8.3.6 gain priorities."""
    state = _state(C.BRITISH, {
        "Boston": C.NEUTRAL,
        "New_York_City": C.NEUTRAL,
        "Quebec_City": C.NEUTRAL,
    }, set())
    state["_event_q_spaces"] = {"Boston"}

    assert select_support_shift_spaces(
        state, state["spaces"], 2, target=C.ACTIVE_SUPPORT,
    ) == ["Boston", "New_York_City"]


@pytest.mark.parametrize("seed", range(20))
def test_card39_keeps_blockaded_boston_despite_tie_rolls(seed):
    """Both 1775/10301 and 1775/10322 must keep the harmless Boston shift.

    One Opposition City and Blockaded Boston rank ahead of the two
    unblocked Support Cities; only the latter pair may be a random tie.
    """
    state = _state(C.BRITISH, {
        "Boston": C.ACTIVE_SUPPORT,
        "Norfolk": C.ACTIVE_OPPOSITION,
        "Quebec_City": C.PASSIVE_SUPPORT,
        "Charles_Town": C.ACTIVE_SUPPORT,
    }, {"Boston"}, seed)
    before = _summarize_board(state)

    evt_039_king_mob(state)

    after = _summarize_board(state)
    assert state["support"]["Boston"] == C.PASSIVE_SUPPORT
    assert state["support"]["Norfolk"] == C.PASSIVE_OPPOSITION
    assert sum(state["support"][sid] != level for sid, level in (
        ("Quebec_City", C.PASSIVE_SUPPORT),
        ("Charles_Town", C.ACTIVE_SUPPORT),
    )) == 1
    assert after["support"] == before["support"] - 1
    assert after["opposition"] == before["opposition"] - 1
