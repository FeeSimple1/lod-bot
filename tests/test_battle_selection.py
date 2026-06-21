"""Tests for the shared Force-Level helper and the British B12 selection
using the resolver's exact modifiers (no approximation)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lod_ai.commands import battle as B
from lod_ai import rules_consts as C


def _state(space):
    return {"spaces": {"X": space}, "leaders": {}, "markers": {},
            "control": {}, "support": {}}


def test_force_level_royalist_attacker_caps_tories():
    # 3.6.3: attacking British Tories capped at number of Regulars.
    sp = {C.REGULAR_BRI: 2, C.TORY: 5, C.WARPARTY_A: 4}
    # attacking: 2 regs + min(5,2) tories + half(4) wp = 2+2+2 = 6
    assert B.force_level(sp, "ROYALIST", False) == 6
    # defending: tories not capped: 2 + 5 + half(4) = 9
    assert B.force_level(sp, "ROYALIST", True) == 9


def test_force_level_rebellion_defending_includes_fort_and_half_militia():
    sp = {C.REGULAR_PAT: 1, C.REGULAR_FRE: 1, C.MILITIA_A: 3, C.FORT_PAT: 1}
    # 1 + 1 + half(3)=1 + fort 1 = 4
    assert B.force_level(sp, "REBELLION", True) == 4


def test_bot_scores_decline_regulars_into_fort_and_continental():
    # 2 British Regulars attacking 1 Continental behind a Fort -> not selected.
    st = _state({C.REGULAR_BRI: 2, C.REGULAR_PAT: 1, C.FORT_PAT: 1})
    att, dfn = B.bot_battle_scores(st, "X", "ROYALIST")
    assert att <= dfn, (att, dfn)


def test_bot_scores_select_regulars_vs_militia():
    # 3 British Regulars vs 2 Active Militia, no fort -> selected.
    st = _state({C.REGULAR_BRI: 3, C.MILITIA_A: 2})
    att, dfn = B.bot_battle_scores(st, "X", "ROYALIST")
    assert att > dfn, (att, dfn)


def test_old_half_regs_bug_is_gone():
    # Rebel cubes = 1 Continental + 4 Militia. Continentals are NOT Regulars
    # (Glossary 1.4), so the +1 'half defending cubes are regulars' must NOT
    # apply. The old code's `def_regs*2 >= rebel_cubes` (def_regs==rebel_cubes)
    # always fired +1 here; the resolver-based scorer must not.
    st = _state({C.REGULAR_BRI: 4, C.REGULAR_PAT: 1, C.MILITIA_A: 4})
    # attacker-loss half-regs modifier should be 0 (no French Regulars).
    mods = B._attacker_loss_mods(st, st["spaces"]["X"], "X",
                                 "ROYALIST", "REBELLION", 0)
    assert mods == 0, mods


# --- Common Cause folded into B12 selection (B13 / 4.2.1) -----------------
from lod_ai.bots.british_bot import BritishBot


def test_cc_battle_wp_caps_at_regulars_minus_tories():
    # 3 Regulars, 0 Tories, 4 Active WP -> loan capped at 3 (= Regulars).
    assert BritishBot._cc_battle_wp({C.REGULAR_BRI: 3, C.WARPARTY_A: 4}) == 3
    # 3 Regulars, 1 Tory, 1 Active + 2 Underground -> need 2; usable =
    # 1 + (2-1) = 2 -> 2.
    assert BritishBot._cc_battle_wp(
        {C.REGULAR_BRI: 3, C.TORY: 1, C.WARPARTY_A: 1, C.WARPARTY_U: 2}) == 2
    # Regulars <= Tories -> no Common Cause benefit.
    assert BritishBot._cc_battle_wp({C.REGULAR_BRI: 2, C.TORY: 3, C.WARPARTY_A: 4}) == 0
    # Sole Underground WP must be kept (B13 Battle) -> 0.
    assert BritishBot._cc_battle_wp({C.REGULAR_BRI: 2, C.WARPARTY_U: 1}) == 0


def test_common_cause_can_tip_selection_over_the_threshold():
    # Without CC the British do not exceed; with CC (War Parties as Tories)
    # they do -- exactly what B12 "Use Common Cause to increase British Force
    # Level" intends.
    sp = {C.REGULAR_BRI: 3, C.WARPARTY_A: 3, C.REGULAR_PAT: 3, C.FORT_PAT: 1}
    st = _state(sp)
    cc = BritishBot._cc_battle_wp(sp)
    assert cc == 3
    att0, dfn0 = B.bot_battle_scores(st, "X", "ROYALIST", cc_wp=0)
    attc, dfnc = B.bot_battle_scores(st, "X", "ROYALIST", cc_wp=cc)
    assert att0 <= dfn0, (att0, dfn0)      # declined without Common Cause
    assert attc > dfnc, (attc, dfnc)       # selected with Common Cause
