"""Session 46 — Piece 2 (Ch 1-7 traceability) fixes C1/C2.

§1.9: "The population of that City is considered 0 for purposes of
calculating Support and during the Resource Phase of the Winter
Quarters Round."
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai import rules_consts as C
from lod_ai.rules_consts import BLOCKADE
from lod_ai.util.naval import effective_population
from lod_ai.victory import _summarize_board
from lod_ai.bots.base_bot import BaseBot
from lod_ai.util.year_end import _resource_income


def _blockaded(state, city):
    state.setdefault("markers", {})[BLOCKADE] = {"pool": 0, "on_map": {city}}


def test_effective_population_zeroes_blockaded_city():
    st = {"markers": {BLOCKADE: {"pool": 0, "on_map": {"Boston"}}}}
    assert effective_population(st, "Boston", 1) == 0
    assert effective_population(st, "New_York_City", 2) == 2


def test_total_support_ignores_blockaded_city():
    """§1.9/§1.6.3 (C1): a Blockaded City at Active Support adds 0."""
    st = {
        "spaces": {"Boston": {}, "Massachusetts": {}},
        "support": {"Boston": C.ACTIVE_SUPPORT, "Massachusetts": 1},
    }
    t = _summarize_board(st)
    assert t["support"] == 4          # Boston Active 2×1 + Mass. Passive 1×2
    _blockaded(st, "Boston")
    t = _summarize_board(st)
    assert t["support"] == 2          # Boston now contributes 0

    sup, opp = BaseBot._support_opposition_totals(st)
    assert sup == 2 and opp == 0


def test_french_wq_income_skips_blockaded_city_pop():
    """§1.9/§6.3.4 (C2): Blockaded-City pop is 0 in the Resource Phase."""
    def mk(blockade):
        st = {
            "spaces": {"New_York_City": {}, "Boston": {}},
            "support": {},
            "control": {},
            "resources": {C.BRITISH: 0, C.PATRIOTS: 0,
                          C.FRENCH: 0, C.INDIANS: 0},
            "treaty_of_alliance": True,
            "fni_level": 0,
            "history": [],
        }
        if blockade:
            _blockaded(st, "New_York_City")
        return st

    st = mk(False)
    _resource_income(st)
    base = st["resources"][C.FRENCH]        # NYC (2) + Boston (1) = 3

    st = mk(True)
    _resource_income(st)
    assert st["resources"][C.FRENCH] == base - 2   # NYC pop no longer counts
