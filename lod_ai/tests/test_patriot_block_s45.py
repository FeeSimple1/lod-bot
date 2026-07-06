"""Session 45 — Patriot block regressions.

Covers the §8.5.4 March fixes (French-Regulars 0-Resource gate,
purse-based destination budget, Militia-only Phase 2), the §8.5.2 Rally
fixes ("4+ Patriot units" excludes French Regulars, lonely-Fort
max-extent placement, bullet-6 no-benefit filter), §4.3.2 Partisans
(option 3 with enemy cubes present; units-only removal), the
§4.3.2/§4.3.3 Battle-space exclusion, §6.4.2/§8.5.9 Committees of
Correspondence (Fort-only eligibility, 2-level + purse-capped
potential), and §8.5.7 Desertion piece-at-a-time re-scoring.
"""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.patriot import PatriotBot
from lod_ai import rules_consts as C
from lod_ai.special_activities import partisans, skirmish
from lod_ai.util.year_end import _support_phase, _patriot_desertion


def _state(spaces, *, resources=None, available=None, support=None,
           seed=42, **extra):
    st = {
        "spaces": spaces,
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5,
                      C.INDIANS: 5, **(resources or {})},
        "available": available if available is not None else {},
        "support": support or {},
        "control": {},
        "rng": random.Random(seed),
        "history": [],
        "casualties": {},
    }
    st.update(extra)
    return st


# ────────────────────────────────────────────────────────────────
# §8.5.4 March
# ────────────────────────────────────────────────────────────────

def test_march_excludes_french_at_zero_french_resources():
    """§8.5.4: "If French Resources exceed 0, include as many French
    Regulars as possible" — at 0 French Resources the March proceeds
    WITHOUT the French instead of aborting entirely (march.execute's
    escort-fee validation used to raise and the bot declined March)."""
    bot = PatriotBot()
    st = _state(
        {
            # 5 Continentals + 2 French; the old planner tried to fill
            # Massachusetts' need of 6 with 1 French Regular.
            "New_York": {C.REGULAR_PAT: 5, C.REGULAR_FRE: 2},
            "Massachusetts": {C.REGULAR_BRI: 5},
            "Pennsylvania": {C.REGULAR_BRI: 2},
            "New_Jersey": {C.MILITIA_U: 4},
        },
        resources={C.FRENCH: 0},
        support={"New_York": 0, "Massachusetts": 0,
                 "Pennsylvania": 0, "New_Jersey": 0},
    )
    assert bot._execute_march(st) is True
    # French never moved and never charged
    assert st["spaces"]["New_York"][C.REGULAR_FRE] == 2
    assert st["resources"][C.FRENCH] == 0
    # The affordable destination was still taken (3 Continentals beat
    # Pennsylvania's 2 British Regulars)
    assert st["spaces"]["Pennsylvania"].get(C.REGULAR_PAT, 0) == 3


def test_march_phase2_moves_militia_only():
    """§8.5.4 Phase 2: "get one Militia (Underground if possible) into
    each space with none" — Continentals are not a fallback."""
    bot = PatriotBot()
    st = _state(
        {
            "New_York": {C.REGULAR_PAT: 3},
            "Massachusetts": {C.REGULAR_BRI: 4},
        },
        support={"New_York": 0, "Massachusetts": 0},
    )
    assert bot._execute_march(st) is False
    assert st["spaces"]["New_York"][C.REGULAR_PAT] == 3
    assert st["spaces"]["Massachusetts"].get(C.REGULAR_PAT, 0) == 0


def test_march_destinations_budgeted_by_patriot_purse():
    """§3.3.2: 1 Resource per destination.  The planner keeps within
    the purse instead of over-planning and aborting on the engine's
    affordability check (and the artificial 4-destination cap is
    gone — the budget is the only limit)."""
    bot = PatriotBot()
    st = _state(
        {
            "New_York": {C.MILITIA_U: 9},
            "Massachusetts": {}, "Pennsylvania": {},
            "New_Hampshire": {}, "New_Jersey": {},
            "Connecticut_Rhode_Island": {},
        },
        resources={C.PATRIOTS: 3},
        support={"New_York": 0, "Massachusetts": 0, "Pennsylvania": 0,
                 "New_Hampshire": 0, "New_Jersey": 0,
                 "Connecticut_Rhode_Island": 0},
    )
    assert bot._execute_march(st) is True
    assert st["resources"][C.PATRIOTS] == 0        # exactly 3 destinations
    reached = [s for s in ("Massachusetts", "Pennsylvania",
                           "New_Hampshire", "New_Jersey",
                           "Connecticut_Rhode_Island")
               if st["spaces"][s].get(C.MILITIA_U, 0)
               + st["spaces"][s].get(C.MILITIA_A, 0)]
    assert len(reached) == 3


# ────────────────────────────────────────────────────────────────
# §8.5.2 Rally
# ────────────────────────────────────────────────────────────────

def test_rally_fort_needs_4_patriot_units_not_french():
    """§8.5.2: "Place a Fort in each space with 4+ Patriot units" —
    Glossary §1.4 units; French Regulars are French pieces and no
    longer count (2 Militia + 2 French Regulars must NOT fort)."""
    bot = PatriotBot()
    st = _state(
        {"Virginia": {C.MILITIA_U: 2, C.REGULAR_FRE: 2}},
        available={C.FORT_PAT: 2, C.MILITIA_U: 0},
        support={"Virginia": 0},
    )
    bot._execute_rally(st)
    assert st["spaces"]["Virginia"].get(C.FORT_PAT, 0) == 0
    assert st["spaces"]["Virginia"][C.MILITIA_U] == 2


def test_rally_lonely_fort_places_max_extent():
    """§3.3.1: a Fort space may take up to (#Patriot Forts +
    Population) Militia; §8.1.1 executes to the maximum extent.
    Massachusetts (Pop 2, 1 Fort) takes 3 Militia, not 1."""
    bot = PatriotBot()
    st = _state(
        {"Massachusetts": {C.FORT_PAT: 1}},
        available={C.MILITIA_U: 5, C.FORT_PAT: 0, C.REGULAR_PAT: 0},
        support={"Massachusetts": 0},
    )
    assert bot._execute_rally(st) is True
    assert st["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 3


def test_rally_bullet6_skips_no_benefit_spaces():
    """§8.5.2 bullet 6 places "first to change Control, then in spaces
    not at Active Opposition" — a space at Active Opposition where 1
    Militia cannot change Control is not worth a Rally slot."""
    bot = PatriotBot()
    st = _state(
        {
            "Virginia": {C.REGULAR_BRI: 3},
            "Pennsylvania": {C.REGULAR_BRI: 4},
        },
        available={C.MILITIA_U: 5, C.FORT_PAT: 0, C.REGULAR_PAT: 0},
        support={"Virginia": C.ACTIVE_OPPOSITION,
                 "Pennsylvania": C.ACTIVE_OPPOSITION},
    )
    assert bot._execute_rally(st) is False
    assert st["resources"][C.PATRIOTS] == 5       # nothing was paid


# ────────────────────────────────────────────────────────────────
# §4.3.2 Partisans / §4.3.3 Skirmish
# ────────────────────────────────────────────────────────────────

def test_partisans_option3_allowed_with_enemy_cubes():
    """§4.3.2 option 3 requires only "If no War Parties there" (plus a
    Village and two Underground Militia) — enemy cubes MAY be present.
    Session 45: the old bot gate wrongly required no enemy cubes."""
    bot = PatriotBot()
    st = _state(
        {"Northwest": {C.MILITIA_U: 2, C.VILLAGE: 1, C.REGULAR_BRI: 2}},
        support={"Northwest": 0},
    )
    assert bot._try_partisans(st) is True
    sp = st["spaces"]["Northwest"]
    assert sp.get(C.VILLAGE, 0) == 0              # Village removed
    assert sp.get(C.REGULAR_BRI, 0) == 2          # cubes untouched
    assert sp.get(C.MILITIA_A, 0) == 1            # 2 activated, 1 removed
    assert sp.get(C.MILITIA_U, 0) == 0


def test_partisans_options12_cannot_remove_fort_or_village():
    """Glossary §1.4: Forts and Villages are not units; §4.3.2 options
    1/2 remove Royalist UNITS only."""
    st = _state({"Virginia": {C.MILITIA_U: 2, C.FORT_BRI: 1}},
                support={"Virginia": 0})
    with pytest.raises(ValueError):
        partisans.execute(st, C.PATRIOTS, {}, "Virginia", option=1)
    assert st["spaces"]["Virginia"][C.FORT_BRI] == 1


def test_partisans_refused_in_battle_space():
    """§4.3.2: Partisans "may accompany any Command but not in a
    Battle space"."""
    st = _state({"Virginia": {C.MILITIA_U: 2, C.TORY: 1}},
                support={"Virginia": 0})
    st["_turn_battle_spaces"] = {"Virginia"}
    with pytest.raises(ValueError):
        partisans.execute(st, C.PATRIOTS, {}, "Virginia", option=1)


def test_skirmish_refused_in_battle_space():
    """§4.2.2/§4.3.3/§4.5.2: no Skirmish in a Battle space."""
    st = _state({"Virginia": {C.REGULAR_PAT: 1, C.REGULAR_BRI: 1}},
                support={"Virginia": 0})
    st["_turn_battle_spaces"] = {"Virginia"}
    with pytest.raises(ValueError):
        skirmish.execute(st, C.PATRIOTS, {}, "Virginia", option=1)


def test_bot_partisans_skips_battle_space():
    st = _state({"Virginia": {C.MILITIA_U: 2, C.TORY: 1}},
                support={"Virginia": 0})
    st["_turn_battle_spaces"] = {"Virginia"}
    assert PatriotBot()._try_partisans(st) is False


# ────────────────────────────────────────────────────────────────
# §6.4.2 / §8.5.9 Committees of Correspondence
# ────────────────────────────────────────────────────────────────

def test_coc_fort_only_space_is_eligible():
    """§6.4.2: "Rebellion Controlled spaces with Patriot pieces" — a
    Patriot Fort is a Patriot piece (Session 45: Fort-only spaces
    were excluded)."""
    st = _state({"Virginia": {C.FORT_PAT: 1}},
                resources={C.PATRIOTS: 5, C.BRITISH: 0},
                support={"Virginia": 0})
    st["control"] = {"Virginia": "REBELLION"}
    _support_phase(st)
    assert st["support"]["Virginia"] == C.ACTIVE_OPPOSITION


def test_coc_potential_capped_at_two_levels():
    """§8.5.9 "largest change in (Opposition - Support) possible":
    §6.4.2 caps shifts at two levels per space, so a Pop-2 space two
    levels out beats a Pop-1 space four levels out (the raw distance
    used to win)."""
    st = _state(
        {
            "Georgia": {C.MILITIA_U: 1},         # Pop 1, Support +2
            "Massachusetts": {C.MILITIA_U: 1},   # Pop 2, Neutral
        },
        resources={C.PATRIOTS: 2, C.BRITISH: 0},
        support={"Georgia": 2, "Massachusetts": 0},
    )
    st["control"] = {"Georgia": "REBELLION", "Massachusetts": "REBELLION"}
    _support_phase(st)
    assert st["support"]["Massachusetts"] == C.ACTIVE_OPPOSITION
    assert st["support"]["Georgia"] == 2          # purse spent on Mass.


# ────────────────────────────────────────────────────────────────
# §8.5.7 Patriot Desertion
# ────────────────────────────────────────────────────────────────

def test_desertion_rescores_after_each_removal():
    """§8.5.7: change as little Control as possible, without removing
    the last Patriot unit — scored per piece.  The old bulk removal
    could strip a small stack bare (losing Control and its last
    units) because it only scored the first piece."""
    st = _state(
        {
            "Massachusetts": {C.MILITIA_U: 13},
            "Connecticut_Rhode_Island": {C.MILITIA_U: 2},
        },
        support={"Massachusetts": 1, "Connecticut_Rhode_Island": 0},
    )
    _patriot_desertion(st, bots={C.PATRIOTS: PatriotBot()})
    # 15 Militia → 3 desert; the 2-Militia stack must keep at least 1
    assert st["spaces"]["Connecticut_Rhode_Island"][C.MILITIA_U] >= 1
    total = (st["spaces"]["Massachusetts"][C.MILITIA_U]
             + st["spaces"]["Connecticut_Rhode_Island"][C.MILITIA_U])
    assert total == 12
