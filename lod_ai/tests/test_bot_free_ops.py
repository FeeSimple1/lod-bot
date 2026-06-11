"""Regressions for the external free-operation audit (June 2026).

Card-granted free operations handed to BOTS were dispatched raw (space=None,
no plan) and without the free-cost waiver, so bots forfeited granted ops,
Marched from the wrong side of a 'March to X' target, or paid Resources for
actions the card grants free. These tests use REAL dispatch (no mocks), per
the audit's recommendation.
"""
import contextlib
import io

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai.util.free_ops import queue_free_op


def _drain(eng):
    with contextlib.redirect_stdout(io.StringIO()):
        eng._drain_free_ops(eng.state)


def test_locationless_bot_free_battle_selects_a_target():
    """A locationless free Battle must pick a legal space, not forfeit."""
    st = build_state("1778", seed=1)
    st["toa_played"] = True
    for k in list(st["spaces"]["Boston"]):
        if isinstance(st["spaces"]["Boston"][k], int):
            st["spaces"]["Boston"][k] = 0
    st["spaces"]["Boston"][C.REGULAR_FRE] = 4
    st["spaces"]["Boston"][C.REGULAR_BRI] = 2
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.FRENCH, "battle_plus2", None)
    _drain(eng)
    hist = " | ".join(h.get("msg", "") if isinstance(h, dict) else str(h)
                      for h in eng.state["history"])
    assert "FREE BATTLE_PLUS2 by FRENCH in" in hist
    assert "skipped (no valid target)" not in hist.split("BATTLE_PLUS2")[-1]


def test_free_march_to_target_routes_target_as_destination():
    """'Free March to Florida' must March INTO Florida from adjacent own
    pieces -- not treat Florida as the source (which forfeited the op)."""
    st = build_state("1778", seed=1)
    st["toa_played"] = True
    for r in ("Georgia", "Florida"):
        for k in list(st["spaces"][r]):
            if isinstance(st["spaces"][r][k], int):
                st["spaces"][r][k] = 0
    st["spaces"]["Georgia"][C.REGULAR_FRE] = 3
    st["spaces"]["Florida"][C.REGULAR_BRI] = 1
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.FRENCH, "march", "Florida")
    _drain(eng)
    assert eng.state["spaces"]["Florida"].get(C.REGULAR_FRE, 0) == 3, \
        "French Regulars should have Marched into Florida"


def test_free_march_does_not_charge_resources():
    st = build_state("1778", seed=1)
    st["toa_played"] = True
    for r in ("Georgia", "Florida"):
        for k in list(st["spaces"][r]):
            if isinstance(st["spaces"][r][k], int):
                st["spaces"][r][k] = 0
    st["spaces"]["Georgia"][C.REGULAR_FRE] = 3
    st["resources"][C.FRENCH] = 10
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.FRENCH, "march", "Florida")
    _drain(eng)
    assert eng.state["resources"][C.FRENCH] == 10, \
        "a card-granted free March must not cost Resources"


def test_toa_free_french_muster_is_free_for_bots():
    st = build_state("1775", seed=1)
    st["toa_played"] = True
    st["resources"][C.FRENCH] = 10
    st["available"][C.REGULAR_FRE] = max(8, st["available"].get(C.REGULAR_FRE, 0))
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.FRENCH, "muster", C.WEST_INDIES_ID)
    _drain(eng)
    assert eng.state["resources"][C.FRENCH] == 10
    assert eng.state["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_FRE, 0) > 0


def test_card94_tory_muster_places_tories_for_free():
    """Card 94: free Indian Gather + free Tory Muster in New York. Both must
    cost zero and the Muster must actually place Tories."""
    from lod_ai.cards.effects import late_war

    st = build_state("1775", seed=1)
    st["resources"][C.BRITISH] = 10
    st["resources"][C.INDIANS] = 10
    st["support"]["New_York"] = C.NEUTRAL
    for k in list(st["spaces"]["New_York"]):
        if isinstance(st["spaces"]["New_York"][k], int):
            st["spaces"]["New_York"][k] = 0
    st["available"][C.WARPARTY_U] = max(10, st["available"].get(C.WARPARTY_U, 0))
    st["available"][C.TORY] = max(10, st["available"].get(C.TORY, 0))
    eng = Engine(initial_state=st)
    with contextlib.redirect_stdout(io.StringIO()):
        late_war.evt_094_herkimer(eng.state, shaded=False)
        eng._drain_free_ops(eng.state)
    assert eng.state["resources"][C.BRITISH] == 10, "Tory Muster must be free"
    assert eng.state["resources"][C.INDIANS] == 10, "Indian Gather must be free"
    assert eng.state["spaces"]["New_York"].get(C.TORY, 0) >= 1, \
        "free Tory Muster must place Tories"
