# tests/test_integration.py
from collections import defaultdict

from lod_ai.engine import Engine
from lod_ai.util.free_ops import queue_free_op
from lod_ai.util.year_end import resolve as resolve_year_end


# ---------------------------------------------------------------------------
# Helper: minimal but valid game tree
# ---------------------------------------------------------------------------
def bare_state() -> dict:
    return {
        "spaces": {},
        "resources": defaultdict(int),
        "casualties": defaultdict(int),
        "pool": defaultdict(int),
        "history": [],
    }


# ---------------------------------------------------------------------------
# 1) French free Battle with +2 Force-Level
# ---------------------------------------------------------------------------
def test_free_battle_plus2():
    st = bare_state()
    st["spaces"]["Pensacola"] = {
        "French_Regular":   3,
        "British_Regular":  2,
    }
    queue_free_op(st, "FRENCH", "battle_plus2", "Pensacola")
    eng = Engine(st)
    eng.play_turn("FRENCH")

    # history entry proves the wrapper, dispatcher, and +2 hook fired
    assert "FREE BATTLE_PLUS2" in st["history"][-1]["msg"]


# ---------------------------------------------------------------------------
# 2) Indians free War Path removes one Active Militia
# ---------------------------------------------------------------------------
def test_free_war_path():
    st = bare_state()
    st["spaces"]["Northwest"] = {
        "Indian_War_Party_A": 2,
        "Patriot_Militia_A":  1,
    }
    st["resources"]["INDIANS"] = 5
    queue_free_op(st, "INDIANS", "war_path", "Northwest")
    eng = Engine(st)
    eng.play_turn("INDIANS")

    # Militia cube should now be in casualties
    assert st["casualties"]["Patriot_Militia_A"] == 1


# ---------------------------------------------------------------------------
# 3) Winter-Quarters Patriot desertion flag is consumed
# ---------------------------------------------------------------------------
def test_winter_quarters_desertion():
    st = bare_state()
    st["spaces"]["Virginia"] = {"Patriot_Militia_A": 1}
    st["winter_flag"] = "PAT_DESERTION"

    # resolve manually to isolate year_end logic
    resolve_year_end(st)

    # flag cleared and routine logged
    assert "winter_flag" not in st
    assert any("Winter-Quarters routine complete" in h["msg"] for h in st["history"])