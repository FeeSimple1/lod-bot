"""Session 43: Winter Quarters Leader Redeploy fallbacks (§6.5.2).

"Each Faction may redeploy its Leader marker to a space with same
Faction's pieces or Available" — every bot's redeploy pick previously
fell back to an arbitrary dict-order space (with NO friendly pieces)
when its primary metric was zero everywhere; the caller then treated
that as a legal destination instead of sending the Leader to Available.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.french import FrenchBot
from lod_ai.bots.indians import IndianBot
from lod_ai import rules_consts as C


def _state(spaces):
    return {
        "spaces": spaces,
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {}, "unavailable": {}, "casualties": {},
        "support": {}, "control": {}, "markers": {}, "leaders": {},
        "rng": random.Random(5), "history": [], "fni_level": 0,
    }


def test_washington_zero_continentals_needs_patriot_pieces():
    """§8.5.6 at 0 Continentals: fall back to a Patriot-piece space;
    never a Patriot-less one; Available (None) when no Patriot pieces."""
    bot = PatriotBot()
    st = _state({
        "Boston": {C.REGULAR_BRI: 3},          # no Patriot pieces
        "Virginia": {C.MILITIA_U: 2},          # Patriot pieces, 0 Continentals
    })
    assert bot.ops_redeploy_washington(st) == "Virginia"
    st2 = _state({"Boston": {C.REGULAR_BRI: 3}})
    assert bot.ops_redeploy_washington(st2) is None


def test_washington_prefers_most_continentals():
    bot = PatriotBot()
    st = _state({
        "Virginia": {C.REGULAR_PAT: 1},
        "Boston": {C.REGULAR_PAT: 4},
    })
    assert bot.ops_redeploy_washington(st) == "Boston"


def test_british_leader_zero_regulars_needs_british_pieces():
    bot = BritishBot()
    st = _state({
        "Virginia": {C.REGULAR_PAT: 5},        # no British pieces
        "Georgia": {C.TORY: 1},                # British piece, 0 Regulars
    })
    assert bot.bot_redeploy_leader(st) == "Georgia"
    st2 = _state({"Virginia": {C.REGULAR_PAT: 5}})
    assert bot.bot_redeploy_leader(st2) is None


def test_french_leader_zero_regulars_goes_available():
    bot = FrenchBot()
    st = _state({
        "Virginia": {C.REGULAR_PAT: 5},        # no French pieces anywhere
        "Boston": {C.REGULAR_BRI: 2},
    })
    assert bot.ops_redeploy_leader(st) is None
    st["spaces"]["Georgia"] = {C.REGULAR_FRE: 2}
    assert bot.ops_redeploy_leader(st) == "Georgia"


def test_indian_leaders_zero_wp_fall_back_to_village_then_available():
    bot = IndianBot()
    st = _state({
        "Virginia": {C.REGULAR_PAT: 5},        # no Indian pieces
        "Southwest": {C.VILLAGE: 1},           # Indian piece, 0 WPs
    })
    res = bot.ops_redeploy(st)
    assert res["LEADER_BRANT"] == "Southwest"
    assert res["LEADER_DRAGGING_CANOE"] == "Southwest"
    st2 = _state({"Virginia": {C.REGULAR_PAT: 5}})
    res2 = bot.ops_redeploy(st2)
    assert res2["LEADER_BRANT"] is None, (
        "no Indian pieces anywhere → Available (None), not a dict-order space")


def test_indian_most_wp_still_wins():
    bot = IndianBot()
    st = _state({
        "Southwest": {C.WARPARTY_U: 1, C.VILLAGE: 1},
        "Northwest": {C.WARPARTY_U: 3},
    })
    res = bot.ops_redeploy(st)
    assert res["LEADER_BRANT"] == "Northwest"
