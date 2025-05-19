# tests/test_integration.py
from collections import defaultdict
import random

from lod_ai.engine import Engine
from lod_ai.util.free_ops import queue_free_op
from lod_ai.util.year_end import resolve as resolve_year_end


def bare_state() -> dict:
    return {
        "spaces": {},
        "resources":  defaultdict(int),
        "casualties": defaultdict(int),
        "pool":       defaultdict(int),
        "history":    [],
        "rng":        random.Random(0),      # deterministic d3 rolls
    }


# ---------------------------------------------------------------------------
# 1) French free Battle with +2 Force-Level bonus
# ---------------------------------------------------------------------------
def test_free_battle_plus2():
    st = bare_state()
    st["toa_played"] = True
    st["resources"]["FRENCH"] = 3            # pay Battle cost
    st["spaces"]["Pensacola"] = {
        "French_Regular":   3,
        "British_Regular":  2,
    }
    queue_free_op(st, "FRENCH", "battle_plus2", "Pensacola")

    Engine(st).play_turn("FRENCH")
    assert "FREE BATTLE_PLUS2" in st["history"][-1]["msg"]


# ---------------------------------------------------------------------------
# 2) Indians free War Path removes enemy Militia
# ---------------------------------------------------------------------------
def test_free_war_path():
    st = bare_state()
    st["resources"]["INDIANS"] = 5
    st["spaces"]["Northwest"] = {
        "Indian_War_Party_U": 2,    # tag matches WARPARTY_U constant
        "Patriot_Militia_A":  1,
    }
    queue_free_op(st, "INDIANS", "war_path", "Northwest")

    Engine(st).play_turn("INDIANS")
    assert st["casualties"]["Patriot_Militia_A"] == 1


# ---------------------------------------------------------------------------
# 3) Winter-Quarters Patriot-desertion flag is consumed
# ---------------------------------------------------------------------------
class _SpaceStub(str):
    def is_colony(self) -> bool:   # every stub space is a Colony
        return True
    def is_support(self) -> bool:  # no Support present in test
        return False


def test_winter_quarters_desertion():
    st = bare_state()
    st["spaces"]["Virginia"] = {"Patriot_Militia_A": 1}
    st["winter_flag"] = "PAT_DESERTION"

    # stub immutable map object with .spaces() returning stub objects
    st["map"] = type(
        "MapStub",
        (),
        {"spaces": lambda self=None: [_SpaceStub(s) for s in st["spaces"]]},
    )()

    resolve_year_end(st)

    assert "winter_flag" not in st
    assert any("Winter-Quarters routine complete" in h["msg"] for h in st["history"])