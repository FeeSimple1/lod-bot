"""B13 / §4.2.1 fidelity for Common Cause: use Active War Parties first,
and only loan in the spaces actually being battled."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lod_ai import rules_consts as C
from lod_ai.special_activities import common_cause
from lod_ai.bots.british_bot import BritishBot


def _sp(reg_bri=0, tory=0, wp_a=0, wp_u=0):
    return {C.REGULAR_BRI: reg_bri, C.TORY: tory,
            C.WARPARTY_A: wp_a, C.WARPARTY_U: wp_u}


def test_active_war_parties_used_first_no_underground_exposed():
    # 3 Active + 2 Underground; loan 2 -> the two Active ones suffice, so NO
    # Underground War Party is flipped (B13 "Active first").
    state = {
        "spaces": {"Boston": _sp(reg_bri=4, wp_a=3, wp_u=2)},
        "resources": {C.BRITISH: 5}, "available": {}, "history": [],
    }
    common_cause.execute(state, C.BRITISH, {}, ["Boston"],
                         wp_counts={"Boston": 2}, mode="BATTLE", preserve_wp=True)
    sp = state["spaces"]["Boston"]
    assert sp[C.WARPARTY_U] == 2, "no Underground WP should be exposed"
    assert sp[C.WARPARTY_A] == 3


def test_underground_flipped_only_when_active_insufficient():
    # 1 Active + 3 Underground; loan 2 -> 1 Active + must flip 1 Underground.
    state = {
        "spaces": {"Boston": _sp(reg_bri=4, wp_a=1, wp_u=3)},
        "resources": {C.BRITISH: 5}, "available": {}, "history": [],
    }
    common_cause.execute(state, C.BRITISH, {}, ["Boston"],
                         wp_counts={"Boston": 2}, mode="BATTLE", preserve_wp=True)
    sp = state["spaces"]["Boston"]
    assert sp[C.WARPARTY_U] == 2, "exactly one Underground flipped"
    assert sp[C.WARPARTY_A] == 2


def test_battle_keeps_last_underground():
    # 0 Active + 1 Underground -> cannot use the sole Underground WP.
    state = {
        "spaces": {"Boston": _sp(reg_bri=3, wp_u=1)},
        "resources": {C.BRITISH: 5}, "available": {}, "history": [],
    }
    common_cause.execute(state, C.BRITISH, {}, ["Boston"],
                         mode="BATTLE", preserve_wp=True)
    assert state["spaces"]["Boston"][C.WARPARTY_U] == 1


def test_try_common_cause_restricted_to_chosen_spaces():
    bot = BritishBot()
    state = {
        "spaces": {
            "Boston": _sp(reg_bri=3, wp_a=2),     # being battled
            "New_York": _sp(reg_bri=3, wp_a=2),   # NOT battled
        },
        "resources": {C.BRITISH: 5}, "available": {}, "history": [],
    }
    bot._try_common_cause(state, spaces=["Boston"])
    # New_York's War Parties must be untouched (not loaned/exposed).
    assert state["spaces"]["New_York"][C.WARPARTY_A] == 2
