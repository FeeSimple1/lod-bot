"""T13: B51/P51 "March to set up Battle" force-conditions rebuilt on
battle.bot_battle_scores (the resolver's own Force-Level + Loss-modifier
maths) over a simulated all-origins March.  Session 41.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai.commands.battle import bot_march_sets_up_battle
from lod_ai import rules_consts as C


def _state(spaces, support=None):
    return {
        "spaces": spaces,
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {}, "unavailable": {}, "casualties": {},
        "support": support or {}, "control": {}, "markers": {},
        "leaders": {}, "rng": random.Random(3), "history": [],
        "fni_level": 0,
    }


def test_british_march_creates_winning_battle():
    """5 Regulars adjacent to a lone Active Militia: marching in gives a
    Royalist score that exceeds the defender's — condition met."""
    st = _state({
        "Massachusetts": {C.MILITIA_A: 1},
        "Boston": {C.REGULAR_BRI: 5},
    })
    assert bot_march_sets_up_battle(st, C.BRITISH) is True


def test_british_no_pieces_declines():
    """No British cubes anywhere — no March can set up a Battle."""
    st = _state({
        "Massachusetts": {C.MILITIA_A: 3},
        "Boston": {},
    })
    assert bot_march_sets_up_battle(st, C.BRITISH) is False


def test_british_insufficient_force_declines():
    """One Regular against a large defended stack: the faithful scores
    (Force Level + Loss-Level modifiers) say no — the old hand-rolled
    halved-Militia check is gone either way, this pins the negative."""
    st = _state({
        "Massachusetts": {C.REGULAR_PAT: 4, C.MILITIA_A: 4, C.FORT_PAT: 1},
        "Boston": {C.REGULAR_BRI: 1},
    })
    assert bot_march_sets_up_battle(st, C.BRITISH) is False


def test_patriot_march_creates_winning_battle():
    """Patriot side: Continentals + Militia from two adjacent origins
    mass against a lone Tory."""
    st = _state({
        "New_York_City": {C.TORY: 1},
        "New_York": {C.REGULAR_PAT: 3, C.MILITIA_A: 2},
        "New_Jersey": {C.REGULAR_PAT: 2},
    })
    assert bot_march_sets_up_battle(st, C.PATRIOTS) is True


def test_patriot_no_enemy_declines():
    st = _state({
        "New_York": {C.REGULAR_PAT: 5},
        "New_Jersey": {},
    })
    assert bot_march_sets_up_battle(st, C.PATRIOTS) is False


def test_simulation_restores_board():
    """The March simulation must leave the board untouched."""
    st = _state({
        "Massachusetts": {C.MILITIA_A: 1},
        "Boston": {C.REGULAR_BRI: 5},
    })
    import copy
    before = copy.deepcopy(st["spaces"])
    bot_march_sets_up_battle(st, C.BRITISH)
    bot_march_sets_up_battle(st, C.PATRIOTS)
    assert st["spaces"] == before
