"""
Event space selection per §8.2 / §8.3.5 / §8.3.6 and the §8.3.3 net-shift
guard. These transcribe Manual Ch 8 (see docstrings per test).
"""
import random

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots.random_spaces import choose_random_space, pick_random_spaces
from lod_ai.cards.effects.shared import select_support_shift_spaces
from lod_ai.rules_consts import PROPAGANDA


def _state(spaces=None, support=None, rng_seed=None):
    st = {
        "spaces": spaces or {},
        "available": {},
        "unavailable": {},
        "casualties": {},
        "markers": {PROPAGANDA: {"pool": 10, "on_map": set()}},
        "support": support or {},
        "control": {},
        "resources": {"BRITISH": 20, "PATRIOTS": 20,
                      "INDIANS": 20, "FRENCH": 20},
    }
    if rng_seed is not None:
        st["rng"] = random.Random(rng_seed)
    return st


# ---------------------------------------------------------------- §8.2 ----

def test_choose_random_space_is_reproducible_from_rng():
    cands = ["Boston", "Georgia", "Virginia", "New_York_City"]
    picks_a = [choose_random_space(cands, random.Random(s)) for s in range(30)]
    picks_b = [choose_random_space(cands, random.Random(s)) for s in range(30)]
    assert picks_a == picks_b
    assert set(picks_a) <= set(cands)
    assert len(set(picks_a)) > 1   # varies with the roll, not pinned


def test_pick_random_spaces_rerolls_per_selection_and_is_distinct():
    st = _state(rng_seed=11)
    cands = ["Boston", "Georgia", "Virginia", "New_York_City", "Norfolk"]
    picked = pick_random_spaces(st, cands, 3)
    assert len(picked) == len(set(picked)) == 3
    assert all(p in cands for p in picked)
    #

    st2 = _state(rng_seed=11)
    assert pick_random_spaces(st2, cands, 3) == picked  # seed-reproducible


def test_pick_random_spaces_without_rng_is_deterministic():
    """Bare unit-test states (no rng) fall back to sorted order, matching
    the free_op_planner._rand_choice stand-in convention."""
    assert pick_random_spaces({}, ["B", "A", "C"], 2) == ["A", "B"]


def test_walk_follows_arrows_to_next_column():
    """§8.2: from the bottom of a column continue at the TOP of the next.
    A forced roll of column 1, row 6 (box: New Jersey) with New Jersey not
    a candidate must reach column 2's top boxes before wrapping back to
    column 1's own top."""

    class FixedRolls:
        def __init__(self, d3, d6):
            self._rolls = [d3, d6]

        def randint(self, a, b):
            return self._rolls.pop(0)

    # Candidates: Quebec_City (col 1, row 1) vs Philadelphia (col 2, row 2).
    # Correct arrow order from (row 6, col 1): rows below are exhausted →
    # top of column 2 → Philadelphia comes before wrapping to Quebec_City.
    pick = choose_random_space(["Quebec_City", "Philadelphia"],
                               FixedRolls(1, 6))
    assert pick == "Philadelphia"


# -------------------------------------------------------------- §8.3.6 ----

def test_royalist_selection_prefers_pop_weighted_support_gain():
    st = _state(support={"Boston": 0, "New_York_City": 0})
    # Both Neutral → Passive Support; NYC pop 2 outweighs Boston pop 1.
    picked = select_support_shift_spaces(
        st, ["Boston", "New_York_City"], 1, target=+2, steps=1, shaded=False)
    assert picked == ["New_York_City"]


def test_rebel_selection_prefers_opposition_gain_then_support_loss():
    st = _state(support={"Philadelphia": 0, "Boston": 2,
                         "New_York_City": -2})
    # Toward Passive Opposition: Philadelphia gains Opposition (first key),
    # Boston only loses Support (second key), NYC would LOSE Opposition.
    picked = select_support_shift_spaces(
        st, ["Philadelphia", "Boston", "New_York_City"], 2,
        target=-1, steps=1, shaded=True)
    assert picked == ["Philadelphia", "Boston"]


def test_zero_gain_candidate_outranks_negative_gain():
    st = _state(support={"Boston": -2, "New_York_City": 2})
    # Royalist toward Passive Support (steps 2): Boston -2→0 is zero
    # Support gain but positive Opposition loss; NYC +2→+1 is a Support
    # LOSS. Boston must win.
    picked = select_support_shift_spaces(
        st, ["Boston", "New_York_City"], 1, target=+1, steps=2, shaded=False)
    assert picked == ["Boston"]


def test_selection_side_from_state_active_overrides_shaded():
    st = _state(support={"Boston": 0, "New_York_City": -2})
    st["active"] = "BRITISH"
    # shaded=True would imply Rebellion, but active BRITISH (Royalist)
    # wins: NYC -2→-1 is an Opposition loss (good for Royalists).
    picked = select_support_shift_spaces(
        st, ["Boston", "New_York_City"], 1, target=-1, steps=1, shaded=True)
    assert picked == ["New_York_City"]


def test_equal_priority_ties_break_by_8_2_not_alphabet():
    """Cities of equal priority must be selected via §8.2 (seeded), and the
    seed must be able to produce a non-alphabetical pick."""
    cands = ["Boston", "Charles_Town", "Norfolk", "Philadelphia"]  # all pop 1
    results = set()
    for seed in range(40):
        st = _state(support={c: 0 for c in cands}, rng_seed=seed)
        picked = select_support_shift_spaces(
            st, cands, 1, target=-2, steps=1, shaded=True)
        results.add(picked[0])
    assert len(results) > 1  # not pinned to sorted()[0]


# -------------------------------------------------------------- §8.3.3 ----

def _bot(faction):
    bot = BaseBot()
    bot.faction = faction
    return bot


def test_ineffective_event_net_shift_favoring_enemy_card41():
    """§8.3.3: an Event that shifts the Support/Opposition difference in
    favor of the enemy side is Ineffective. With every Colony at Active
    Support, card 41 unshaded could only pull Support DOWN toward Passive,
    so the British bot must refuse it."""
    spaces = {c: {"type": "Colony"} for c in
              ("Virginia", "Georgia", "Connecticut_Rhode_Island")}
    st = _state(spaces=spaces,
                support={c: 2 for c in spaces}, rng_seed=5)
    card = {"id": 41, "dual": True}
    assert _bot(C.BRITISH)._is_ineffective_event(card, st) is True

    # With a Neutral Colony available the shift favors the British → play.
    st["support"]["Virginia"] = 0
    assert _bot(C.BRITISH)._is_ineffective_event(card, st) is False


def test_ineffective_event_rebel_side_mirror_card46():
    """Rebellion mirror: all Cities at Active Opposition would only soften
    toward Passive Opposition under card 46 shaded → Patriots refuse."""
    spaces = {c: {"type": "City"} for c in
              ("Boston", "New_York_City", "Philadelphia")}
    st = _state(spaces=spaces,
                support={c: -2 for c in spaces}, rng_seed=5)
    card = {"id": 46, "dual": True}
    assert _bot(C.PATRIOTS)._is_ineffective_event(card, st) is True

    st["support"]["Boston"] = 0
    assert _bot(C.PATRIOTS)._is_ineffective_event(card, st) is False
