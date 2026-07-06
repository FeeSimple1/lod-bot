"""Session 47 — T14 execution-guidance sweep regressions.

Each test pins a handler to the per-faction Special Instructions on the
card sheets (the four `* bot flowchart and reference.txt` files).
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.cards.effects import early_war, middle_war, late_war
from lod_ai import rules_consts as C
from lod_ai.rules_consts import (
    REGULAR_BRI, REGULAR_PAT, REGULAR_FRE, TORY,
    MILITIA_U, MILITIA_A, WARPARTY_U, WARPARTY_A,
    FORT_BRI, FORT_PAT, VILLAGE, PROPAGANDA,
    BRITISH, PATRIOTS, FRENCH, INDIANS,
)


def _st(spaces, active=BRITISH, **extra):
    st = {
        "spaces": spaces,
        "available": {},
        "unavailable": {},
        "casualties": {},
        "markers": {PROPAGANDA: {"pool": 10, "on_map": set()}},
        "support": {},
        "control": {},
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "INDIANS": 5, "FRENCH": 5},
        "rng": random.Random(7),
        "history": [],
        "active": active,
    }
    st.update(extra)
    return st


# ── Card 80: never self-target; §8.1.2 own-piece removal ─────────

def test_card80_british_executor_targets_rebels_not_self():
    st = _st({
        "Boston": {REGULAR_BRI: 3, MILITIA_U: 2},
        "Virginia": {MILITIA_U: 2},
    }, active=BRITISH)
    middle_war.evt_080_confusion_slaves(st, shaded=False)
    # British pieces untouched; Patriot pieces removed
    assert st["spaces"]["Boston"][REGULAR_BRI] == 3
    total_militia = sum(sp.get(MILITIA_U, 0) for sp in st["spaces"].values())
    assert total_militia == 0     # 2 spaces x 2 removals


def test_card80_target_removes_fort_only_when_reached():
    """§8.1.2: the target removes units first, Forts last."""
    st = _st({
        "Virginia": {FORT_PAT: 1, MILITIA_U: 1},        # fort reached
        "Pennsylvania": {FORT_PAT: 1, MILITIA_U: 2},    # fort survives
    }, active=INDIANS,
       card80_faction=PATRIOTS,
       card80_spaces=["Virginia", "Pennsylvania"])
    middle_war.evt_080_confusion_slaves(st, shaded=False)
    assert st["spaces"]["Virginia"].get(FORT_PAT, 0) == 0
    assert st["spaces"]["Pennsylvania"].get(FORT_PAT, 0) == 1
    assert st["spaces"]["Pennsylvania"].get(MILITIA_U, 0) == 0


# ── Card 83: target selection ────────────────────────────────────

def test_card83_french_preset_respected():
    st = _st({
        "Quebec": {},
        "Quebec_City": {REGULAR_BRI: 5},
    }, active=FRENCH, card83_target="Quebec_City")
    st["available"] = {REGULAR_FRE: 3, FORT_PAT: 1, MILITIA_U: 3}
    early_war.evt_083_carleton_negotiates(st, shaded=True)
    placed = sum(q for t, q in st["spaces"]["Quebec_City"].items()
                 if t.startswith(("French_", "Patriot_")) and isinstance(q, int))
    assert placed == 3            # min-piece scan would have picked Quebec


def test_card83_patriot_prefers_control_change_in_quebec_city():
    # 2 British in Quebec City: +3 rebel pieces flips it to REBELLION
    st = _st({
        "Quebec": {},
        "Quebec_City": {REGULAR_BRI: 2},
    }, active=PATRIOTS)
    st["available"] = {FORT_PAT: 1, MILITIA_U: 5, REGULAR_PAT: 5}
    early_war.evt_083_carleton_negotiates(st, shaded=True)
    placed = sum(q for t, q in st["spaces"]["Quebec_City"].items()
                 if t.startswith("Patriot_") and isinstance(q, int))
    assert placed == 3

    # 6 British there: no control change possible → Quebec instead
    st = _st({
        "Quebec": {},
        "Quebec_City": {REGULAR_BRI: 6},
    }, active=PATRIOTS)
    st["available"] = {FORT_PAT: 1, MILITIA_U: 5, REGULAR_PAT: 5}
    early_war.evt_083_carleton_negotiates(st, shaded=True)
    placed_q = sum(q for t, q in st["spaces"]["Quebec"].items()
                   if t.startswith("Patriot_") and isinstance(q, int))
    assert placed_q == 3


# ── Card 86: Village space first ─────────────────────────────────

def test_card86_selects_village_space():
    st = _st({
        "Massachusetts": {MILITIA_U: 2},
        "Northwest": {VILLAGE: 1, MILITIA_U: 3},
    }, active=PATRIOTS)
    early_war.evt_086_stockbridge(st, shaded=False)
    # Village space activated, Massachusetts untouched
    assert st["spaces"]["Northwest"].get(MILITIA_A, 0) == 3
    assert st["spaces"]["Massachusetts"].get(MILITIA_A, 0) == 0


# ── Card 89: sheet orderings ─────────────────────────────────────

def test_card89_indians_replace_in_village_spaces_first():
    st = _st({
        "Virginia": {MILITIA_U: 4},
        "Northwest": {MILITIA_U: 4, VILLAGE: 1},
    }, active=INDIANS)
    st["available"] = {TORY: 10}
    middle_war.evt_089_war_damages(st, shaded=False)
    assert st["spaces"]["Northwest"].get(MILITIA_U, 0) == 0     # 4 replaced here
    assert st["spaces"]["Virginia"].get(MILITIA_U, 0) == 4


def test_card89_french_replace_tories_at_active_support_first():
    st = _st({
        "Virginia": {TORY: 3},
        "Pennsylvania": {TORY: 3},
    }, active=FRENCH)
    st["support"] = {"Pennsylvania": C.ACTIVE_SUPPORT, "Virginia": 0}
    st["available"] = {MILITIA_U: 10}
    middle_war.evt_089_war_damages(st, shaded=True)
    assert st["spaces"]["Pennsylvania"].get(TORY, 0) == 0       # 3 replaced here
    assert st["spaces"]["Virginia"].get(TORY, 0) == 3


# ── Card 95: British executor places War Parties first ───────────

def test_card95_british_places_war_parties_first():
    st = _st({"Northwest": {FORT_PAT: 1}}, active=BRITISH)
    st["available"] = {WARPARTY_U: 2, REGULAR_BRI: 5, TORY: 5}
    late_war.evt_095_ohio_frontier(st, shaded=False)
    sp = st["spaces"]["Northwest"]
    assert sp.get(FORT_PAT, 0) == 0                  # enemy Fort removed
    assert sp.get(WARPARTY_U, 0) == 2                # WPs first (sheet B95)
    assert sp.get(REGULAR_BRI, 0) == 1               # then British units


# ── Card 30: leave 1 Regular per space; Unavailable first ────────

def test_card30_shaded_leaves_one_regular_per_space():
    st = _st({
        "Boston": {REGULAR_BRI: 6},
        "Virginia": {REGULAR_BRI: 4},
    }, active=PATRIOTS)
    middle = early_war.evt_030_hessians(st, shaded=True)   # 10//5 = 2 removed
    assert st["spaces"]["Boston"][REGULAR_BRI] >= 1
    assert st["spaces"]["Virginia"][REGULAR_BRI] >= 1
    total = sum(sp.get(REGULAR_BRI, 0) for sp in st["spaces"].values())
    assert total == 8


def test_card30_unshaded_pulls_unavailable_first():
    st = _st({"Boston": {REGULAR_BRI: 1}}, active=BRITISH)
    st["control"] = {"Boston": BRITISH}
    st["unavailable"] = {REGULAR_BRI: 5}
    st["available"] = {REGULAR_BRI: 5}
    early_war.evt_030_hessians(st, shaded=False)
    # §8.1.2: the two placed Regulars come from Unavailable first
    assert st["unavailable"][REGULAR_BRI] == 3


# ── Card 52: executor-aware removals ─────────────────────────────

def test_card52_patriot_executor_removes_no_french():
    st = _st({"Virginia": {REGULAR_FRE: 3}}, active=PATRIOTS)
    late_war.evt_052_fleet_wrong_spot(st, shaded=False)
    assert st["spaces"]["Virginia"][REGULAR_FRE] == 3


def test_card52_british_prefers_rebel_outnumbered_spaces():
    st = _st({
        # Rebels outnumber British here → preferred removal site
        "Virginia": {REGULAR_FRE: 2, MILITIA_U: 3, REGULAR_BRI: 1},
        # British outnumber rebels here → lower priority
        "Pennsylvania": {REGULAR_FRE: 4, REGULAR_BRI: 9},
    }, active=BRITISH)
    late_war.evt_052_fleet_wrong_spot(st, shaded=False)
    assert st["spaces"]["Virginia"].get(REGULAR_FRE, 0) == 0   # both taken first
    assert st["spaces"]["Pennsylvania"].get(REGULAR_FRE, 0) == 2   # 4 - remaining 2


# ── Card 23: destination must be a Province; Support origin ─────

def test_card23_moves_from_support_to_nonsupport_province():
    st = _st({
        "North_Carolina": {MILITIA_U: 2},
        "South_Carolina": {MILITIA_U: 2},
        "Virginia": {},
    }, active=BRITISH)
    st["support"] = {"South_Carolina": 1, "North_Carolina": 0, "Virginia": 0}
    late_war.evt_023_francis_marion(st, shaded=False)
    # Sheet B23: origin at Support (South_Carolina) was preferred; the
    # 2 units went to ONE adjacent non-Support Province (NC or Virginia
    # both qualify — §8.2 seeded).
    assert st["spaces"]["South_Carolina"].get(MILITIA_U, 0) == 0
    total = sum(st["spaces"][s].get(MILITIA_U, 0)
                for s in ("North_Carolina", "Virginia"))
    assert total == 4


# ── Card 88: one origin only ─────────────────────────────────────

def test_card88_moves_from_single_origin():
    st = _st({
        "Virginia": {REGULAR_BRI: 2, MILITIA_U: 1},
        "Pennsylvania": {REGULAR_BRI: 2, MILITIA_U: 1},
        "New_Jersey": {},
    }, active=BRITISH)
    middle_war.evt_088_foggy(st, shaded=False)
    still_shared = sum(
        1 for sid in ("Virginia", "Pennsylvania")
        if st["spaces"][sid].get(REGULAR_BRI, 0)
    )
    assert still_shared == 1      # sheet: ONE origin moves, not all


# ── Card 73: Royalist executor removes the Patriot Fort first ────

def test_card73_british_removes_patriot_fort_first():
    st = _st({
        "New_York": {FORT_BRI: 1},
        "Northwest": {FORT_PAT: 1},
    }, active=BRITISH)
    late_war.evt_073_sullivan(st, shaded=False)
    assert st["spaces"]["Northwest"].get(FORT_PAT, 0) == 0
    assert st["spaces"]["New_York"].get(FORT_BRI, 0) == 1
