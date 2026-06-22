"""§1.9 / §4.5.3: FNI may never exceed the number of Blockade markers
Available (in play). The Naval Pressure SA already enforced this; these
tests pin the card-driven path (shared.adjust_fni) to the same ceiling."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lod_ai.cards.effects.shared import adjust_fni
from lod_ai.util.naval import fni_ceiling
from lod_ai.rules_consts import BLOCKADE


def _state(pool=0, on_map=None, fni=0, toa=True):
    return {
        "fni_level": fni,
        "toa_played": toa,
        "markers": {BLOCKADE: {"pool": pool, "on_map": set(on_map or [])}},
        "history": [],
    }


def test_ceiling_counts_pool_plus_on_map_capped_at_max():
    assert fni_ceiling(_state(pool=1)) == 1
    assert fni_ceiling(_state(pool=0, on_map=["Boston", "New_York"])) == 2
    assert fni_ceiling(_state(pool=2, on_map=["Boston"])) == 3
    assert fni_ceiling(_state(pool=5, on_map=["Boston", "New_York"])) == 3  # MAX_FNI


def test_card_raise_capped_by_available_blockades():
    # Card 40 shaded effect is adjust_fni(state, 3 - fni); with only 1 marker
    # available, FNI must stop at 1, not 3.
    st = _state(pool=1, fni=0)
    adjust_fni(st, 3 - st["fni_level"])
    assert st["fni_level"] == 1


def test_card_raise_reaches_three_when_three_available():
    st = _state(pool=3, fni=0)
    adjust_fni(st, 3)
    assert st["fni_level"] == 3


def test_on_map_blockades_count_toward_ceiling():
    st = _state(pool=0, on_map=["Boston", "New_York"], fni=0)
    adjust_fni(st, +3)
    assert st["fni_level"] == 2


def test_lowering_is_not_blocked_by_ceiling():
    # FNI sitting above the current ceiling can still be lowered normally
    # (the ceiling only caps *raises*).
    st = _state(pool=0, fni=3)
    adjust_fni(st, -1)
    assert st["fni_level"] == 2


def test_pre_treaty_fni_stays_zero():
    st = _state(pool=3, fni=0, toa=False)
    adjust_fni(st, +2)
    assert st["fni_level"] == 0

