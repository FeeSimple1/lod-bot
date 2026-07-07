"""T7 (§8.3.5): Non-player "who gets benefits / who is harmed" faction
ordering — benefits go executing → ally → random enemy (NP first); harm
goes to a random enemy (player first).  Factions are not on the Random
Spaces table, so equal-rank faction ties use a seeded roll (Q22).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai import rules_consts as C
from lod_ai.util.target_order import (
    beneficiary_order, harm_target_order, first_beneficiary, first_harm_target,
)


def _st(humans=None, seed=1):
    return {"rng": random.Random(seed),
            "human_factions": set(humans or ())}


def test_benefit_executing_then_ally_then_enemies():
    order = beneficiary_order(_st(), C.BRITISH)
    assert order[0] == C.BRITISH          # executing Faction
    assert order[1] == C.INDIANS          # the other friendly Faction
    assert set(order[2:]) == {C.PATRIOTS, C.FRENCH}   # then enemies


def test_benefit_candidates_restrict_to_friendly_pair():
    # Card 66: benefit to French OR Patriots — executing first.
    assert first_beneficiary(_st(), C.PATRIOTS,
                             candidates=(C.FRENCH, C.PATRIOTS)) == C.PATRIOTS
    assert first_beneficiary(_st(), C.FRENCH,
                             candidates=(C.FRENCH, C.PATRIOTS)) == C.FRENCH


def test_harm_only_enemies():
    order = harm_target_order(_st(), C.BRITISH)
    assert set(order) == {C.PATRIOTS, C.FRENCH}   # never self/ally


def test_harm_player_first():
    # Patriots human → a British executor harms the human Patriot first.
    assert first_harm_target(_st(humans={C.PATRIOTS}), C.BRITISH) == C.PATRIOTS
    # French human, Patriots not → French first.
    assert first_harm_target(_st(humans={C.FRENCH}), C.BRITISH) == C.FRENCH


def test_benefit_enemy_np_before_human():
    # British executor, French is human: among enemies the NP (Patriots)
    # is ordered before the human (French).
    order = beneficiary_order(_st(humans={C.FRENCH}), C.BRITISH)
    assert order.index(C.PATRIOTS) < order.index(C.FRENCH)


def test_seeded_tie_is_deterministic_but_not_constant():
    # All-bot: both enemies are NP, so order is a seeded roll — stable per
    # seed, and not always the same faction across seeds.
    firsts = {first_harm_target(_st(seed=s), C.BRITISH) for s in range(1, 12)}
    assert firsts == {C.PATRIOTS, C.FRENCH}       # both occur across seeds


def test_candidates_filter_harm_to_pieces_present():
    # Card 80 style: only enemies with pieces are candidates.
    assert first_harm_target(_st(), C.BRITISH, candidates=[C.FRENCH]) == C.FRENCH
    assert first_harm_target(_st(), C.BRITISH, candidates=[]) is None
