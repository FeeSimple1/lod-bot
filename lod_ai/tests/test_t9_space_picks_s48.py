"""Session 48 — T9 dict-order space-pick regressions (§8.3.5/§8.3.6/§8.2)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.cards.effects import early_war, late_war, middle_war
from lod_ai.rules_consts import (
    REGULAR_BRI, REGULAR_PAT, TORY, MILITIA_U, MILITIA_A,
    WARPARTY_U, WARPARTY_A, FORT_BRI, FORT_PAT, VILLAGE, PROPAGANDA,
    BRITISH, PATRIOTS, FRENCH, INDIANS,
)


def _st(spaces, active=BRITISH, **extra):
    st = {
        "spaces": spaces,
        "available": {MILITIA_U: 10, TORY: 10, VILLAGE: 5, FORT_PAT: 3,
                      FORT_BRI: 3, WARPARTY_U: 6},
        "unavailable": {},
        "casualties": {},
        "markers": {PROPAGANDA: {"pool": 10, "on_map": set()}},
        "support": {},
        "control": {},
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "INDIANS": 5, "FRENCH": 5},
        "rng": random.Random(3),
        "history": [],
        "active": active,
    }
    st.update(extra)
    return st


def test_card16_shaded_prefers_largest_opposition_gain():
    """§8.3.6: Support-2 pop-2 city (gain 6) beats Neutral pop-1 (gain 2)."""
    st = _st({"Boston": {}, "New_York_City": {}}, active=PATRIOTS)
    st["support"] = {"Boston": 0, "New_York_City": 2}   # NYC pop 2 at AS
    late_war.evt_016_mercy_warren(st, shaded=True)
    assert st["support"]["New_York_City"] == -1
    assert st["support"]["Boston"] == 0


def test_card16_unshaded_prefers_control_gain():
    st = _st({
        "Virginia": {MILITIA_U: 5},               # +2 Tories cannot flip
        "Pennsylvania": {MILITIA_U: 1},           # +2 Tories gains control
    }, active=BRITISH)
    late_war.evt_016_mercy_warren(st, shaded=False)
    assert st["spaces"]["Pennsylvania"].get(TORY, 0) == 2
    assert st["spaces"]["Virginia"].get(TORY, 0) == 0


def test_card24_fort_goes_to_space_with_room():
    """§1.4.2: the Fort lands in a selected space WITH base room
    (previously silently lost if the top pick was full)."""
    st = _st({
        "Boston": {FORT_BRI: 1, VILLAGE: 1},      # City, pop 1 — but FULL
        "New_York_City": {},                      # City, pop 2
        "Virginia": {},
    }, active=PATRIOTS)
    early_war.evt_024_declaration(st, shaded=True)
    forts = {sid: sp.get(FORT_PAT, 0) for sid, sp in st["spaces"].items()}
    assert forts["Boston"] == 0
    assert sum(forts.values()) == 1


def test_card79_shaded_needs_removable_pieces():
    """§5.1.3: the removal Colony must actually hold a Village/WP
    (previously the first alphabetical Colony no-opped)."""
    st = _st({
        "Georgia": {},                            # alphabetically first
        "Virginia": {VILLAGE: 1, WARPARTY_U: 2},
    }, active=PATRIOTS)
    late_war.evt_079_tuscarora_oneida(st, shaded=True)
    assert st["spaces"]["Virginia"].get(VILLAGE, 0) == 0
    assert st["spaces"]["Virginia"].get(WARPARTY_U, 0) == 0


def test_card90_patriot_fort_avoids_reserves():
    """The Patriot Fort goes to a Colony with own pieces, not the
    first Reserve in dict order."""
    st = _st({
        "Northwest": {},                          # Reserve — old pick
        "Virginia": {MILITIA_U: 2},
    }, active=PATRIOTS)
    early_war.evt_090_world_turned_upside_down(st, shaded=False)
    assert st["spaces"]["Virginia"].get(FORT_PAT, 0) == 1
    assert st["spaces"]["Northwest"].get(FORT_PAT, 0) == 0


def test_card27_shaded_picks_best_two_cities():
    """§8.3.6 city pick for the two shifts (was first-two dict order)."""
    st = _st({
        "Boston": {}, "New_York_City": {}, "Philadelphia": {},
    }, active=PATRIOTS)
    st["support"] = {"Boston": 2, "New_York_City": 2, "Philadelphia": -2}
    middle_war.evt_027_queens_rangers(st, shaded=True)
    # Philadelphia already at Active Opposition — the two Support
    # cities were shifted instead
    assert st["support"]["Boston"] == 1
    assert st["support"]["New_York_City"] == 1
