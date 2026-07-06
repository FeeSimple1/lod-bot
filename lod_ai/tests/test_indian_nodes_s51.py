"""Session 51 — Indian Gather/March/Supply node deviations (§8.7.2/§8.7.3/§3.4.1/§3.4.2)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.indians import IndianBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai import rules_consts as C


def _st(spaces, *, resources=None, available=None, support=None, **extra):
    st = {
        "spaces": spaces,
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5,
                      C.INDIANS: 5, **(resources or {})},
        "available": available if available is not None else {},
        "unavailable": {},
        "casualties": {},
        "markers": {},
        "support": support or {},
        "control": {},
        "rng": random.Random(9),
        "history": [],
        "leaders": {},
    }
    st.update(extra)
    return st


def test_gather_places_second_village_where_room():
    """§8.7.2 bullet 1 + §1.4.2: a 1-Village Reserve with base room and
    3+ War Parties takes a SECOND Village (was excluded)."""
    bot = IndianBot()
    st = _st({"Northwest": {C.VILLAGE: 1, C.WARPARTY_U: 4}},
             available={C.VILLAGE: 3, C.WARPARTY_U: 0},
             support={"Northwest": 0})
    assert bot._gather(st) is True
    assert st["spaces"]["Northwest"].get(C.VILLAGE, 0) == 2


def test_gather_free_reserve_at_zero_resources():
    """§3.4.1: "Pay 0 for the first Indian Reserve Province" — a single-
    Reserve Gather must proceed at 0 Resources (was refused)."""
    bot = IndianBot()
    st = _st({"Northwest": {C.WARPARTY_U: 4}},
             resources={C.INDIANS: 0},
             available={C.VILLAGE: 3, C.WARPARTY_U: 2},
             support={"Northwest": 0})
    assert bot._gather(st) is True
    assert st["resources"][C.INDIANS] == 0          # free Reserve
    assert st["spaces"]["Northwest"].get(C.VILLAGE, 0) == 1


def test_march_phase2_no_overshoot():
    """§8.7.3/§1.7: Control flips at equality — exactly (reb - royal)
    War Parties suffice (the old +1 demanded more supply than needed)."""
    bot = IndianBot()
    st = _st({
        # Virginia: 3 rebels, 0 royalists, REBELLION-controlled.
        "Virginia": {C.MILITIA_U: 3},
        # Northwest supplies exactly 3 WPs (4 present; must keep... no
        # village, Reserve with room → keep 3? Northwest has village →
        # keep 1).
        "Northwest": {C.VILLAGE: 1, C.WARPARTY_U: 4},
    }, support={"Virginia": 0, "Northwest": 0})
    # Village available would trigger Phase 1 elsewhere; empty pool.
    st["available"] = {C.VILLAGE: 0}
    assert bot._march(st) is True
    sp = st["spaces"]["Virginia"]
    moved = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
    assert moved == 3                    # equality, not 4


def test_march_free_all_reserve_destination_at_zero_resources():
    """§3.4.2: first destination fed entirely from Reserves is free —
    a 0-Resource March must still plan it (was refused up front)."""
    bot = IndianBot()
    st = _st({
        "Virginia": {C.MILITIA_U: 2},
        "Northwest": {C.VILLAGE: 1, C.WARPARTY_U: 5},
    }, resources={C.INDIANS: 0}, support={"Virginia": 0, "Northwest": 0})
    st["available"] = {C.VILLAGE: 0}
    assert bot._march(st) is True
    assert st["resources"][C.INDIANS] == 0


def test_wq_auto_village_prefers_war_party_reserve():
    """§8.7 note: the Supply-Phase auto-Village lands with War Parties."""
    from lod_ai.util.year_end import _supply_phase
    st = _st({
        "Northwest": {},
        "Southwest": {C.WARPARTY_U: 2},
        C.WEST_INDIES_ID: {},
    }, available={C.VILLAGE: 2}, support={})
    _supply_phase(st)
    assert st["spaces"]["Southwest"].get(C.VILLAGE, 0) == 1
    assert st["spaces"]["Northwest"].get(C.VILLAGE, 0) == 0


def test_british_supply_coc_proxy_simulates_control():
    """§8.4.7: pay only where the cubes' removal would actually allow
    Committees (§6.4.2 needs Rebellion Control + Patriot pieces) — a
    lone rebel piece under a big garrison is no longer enough."""
    bot = BritishBot()
    st = _st({
        # 6 Tories leaving still leave... removal leaves WPs 4 > militia 1
        # → no Rebellion control → no pay.
        "Virginia": {C.TORY: 6, C.WARPARTY_U: 4, C.MILITIA_U: 1},
        # Here removal flips it: militia 2 > village 1 → pay.
        "Pennsylvania": {C.TORY: 2, C.VILLAGE: 1, C.MILITIA_U: 2},
    }, support={"Virginia": 0, "Pennsylvania": 0})
    st["control"] = {}
    priority = bot.bot_supply_priority(st)
    assert "Pennsylvania" in priority
    assert "Virginia" not in priority
