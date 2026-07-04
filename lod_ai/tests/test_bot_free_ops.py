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
    # 8.6.5 "lose no Rebellion Control": Georgia is Rebellion-controlled
    # (3 French Regulars, no Royalists), so one Regular stays behind to
    # hold it and the other two March into the pinned destination.
    assert eng.state["spaces"]["Florida"].get(C.REGULAR_FRE, 0) == 2, \
        "French Regulars should have Marched into Florida"
    assert eng.state["spaces"]["Georgia"].get(C.REGULAR_FRE, 0) == 1, \
        "one Regular must stay to keep Rebellion Control of Georgia (8.6.5)"


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


def test_free_french_muster_planner_respects_3_5_3():
    """§3.5.3: French Muster selects "any one Colony or City with
    Rebellion Control or the West Indies."  The planner previously used
    the BRITISH destination rule (non-Blockaded City / adjacent Colony),
    so a locationless free French Muster could pick a City without
    Rebellion Control — muster.execute then raised and the free op was
    logged as an execution skip (clean-sweep gate, 1778 seed 5)."""
    st = build_state("1775", seed=1)
    st["toa_played"] = True
    eng = Engine(initial_state=st)
    eng.set_human_factions(set())
    from lod_ai.board.control import refresh_control
    refresh_control(eng.state)
    plan = eng._plan_bot_free_op(eng.state, C.FRENCH, "muster", None)
    if plan is not None:
        dest = plan["selected"][0]
        from lod_ai.map import adjacency as map_adj
        assert (dest == C.WEST_INDIES_ID
                or (map_adj.is_city(dest)
                    or map_adj.space_type(dest) == "Colony")
                and eng.state["control"].get(dest) == "REBELLION")


def test_free_french_muster_pinned_illegal_location_declines():
    """A card-pinned location the executor would reject must be a
    genuine decline (None), not a plan that skips at execution."""
    st = build_state("1775", seed=1)
    st["toa_played"] = True
    eng = Engine(initial_state=st)
    eng.set_human_factions(set())
    from lod_ai.board.control import refresh_control
    refresh_control(eng.state)
    # Find a City that is NOT Rebellion-Controlled
    from lod_ai.map import adjacency as map_adj
    pinned = next(sid for sid in eng.state["spaces"]
                  if map_adj.is_city(sid)
                  and eng.state["control"].get(sid) != "REBELLION")
    assert eng._plan_bot_free_op(eng.state, C.FRENCH, "muster", pinned) is None


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


# ---------------------------------------------------------------------------
# Per-faction free-Command planners + free-SA planners (transcribed from
# the bot flowcharts: B10/P5/F14/I10, 8.5.2 Rally, I8 War Path, P8
# Partisans). These replaced the generic mass-toward-enemy planner whose
# space choices could miss faction Command prerequisites.
# ---------------------------------------------------------------------------

def _hist(eng):
    return " | ".join(h.get("msg", "") if isinstance(h, dict) else str(h)
                      for h in eng.state["history"])


def _clear(st, sid):
    for k in list(st["spaces"][sid]):
        if isinstance(st["spaces"][sid][k], int):
            st["spaces"][sid][k] = 0


def test_free_british_march_tory_only_sources_cannot_strand_the_op():
    """3.2.3: Tories may only accompany Regulars 1-for-1, so a Tory-only
    space is not a March source. Regression for the residual 'skipped
    (no valid target)' British free Marches: the planner must either use
    Regulars or decline -- never hand the executor a zero-piece plan."""
    st = build_state("1775", seed=1)
    _clear(st, "Boston")
    _clear(st, "Massachusetts")
    st["spaces"]["Boston"][C.TORY] = 3          # Tory-only: not a source
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.BRITISH, "march", "Massachusetts")
    _drain(eng)
    hist = _hist(eng)
    assert "skipped (no valid target)" not in hist
    assert eng.state["spaces"]["Boston"].get(C.TORY, 0) == 3, \
        "Tories may not March without Regulars (3.2.3)"


def test_free_british_march_brings_tory_escorts_with_regulars():
    """3.2.3 escorts: Regulars March and Tories accompany 1-for-1,
    leaving the last Tory behind (B10)."""
    st = build_state("1775", seed=1)
    _clear(st, "Boston")
    _clear(st, "Massachusetts")
    st["spaces"]["Boston"][C.REGULAR_BRI] = 4
    st["spaces"]["Boston"][C.TORY] = 3
    st["spaces"]["Massachusetts"][C.MILITIA_A] = 1
    st["support"]["Boston"] = C.NEUTRAL
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.BRITISH, "march", "Massachusetts")
    _drain(eng)
    ma = eng.state["spaces"]["Massachusetts"]
    assert ma.get(C.REGULAR_BRI, 0) >= 1
    assert eng.state["spaces"]["Boston"].get(C.TORY, 0) >= 1, \
        "B10: never March the last Tory out of a space"


def test_free_french_rally_is_a_genuine_decline():
    """Rally is a Patriot Command (3.3); a free 'rally' queued for any
    other faction must decline cleanly rather than crash the executor."""
    st = build_state("1778", seed=1)
    st["toa_played"] = True
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.FRENCH, "rally", None)
    _drain(eng)
    hist = _hist(eng)
    assert "declined (no legal plan)" in hist
    assert "skipped (no valid target)" not in hist


def test_card67_pairs_faction_with_its_legal_command():
    """Card 67 shaded: Rally is Patriot-only (3.3) and French Muster
    needs the Treaty (3.5.2), so French->muster and, before the ToA,
    the benefit passes to the Patriots (8.3.5)."""
    from lod_ai.cards.effects import late_war

    st = {"spaces": {"Virginia": {}}, "available": {}, "support": {},
          "control": {}, "resources": {f: 0 for f in
                                       (C.BRITISH, C.PATRIOTS,
                                        C.INDIANS, C.FRENCH)},
          "remain_eligible": set(), "free_ops": [], "toa_played": True}
    late_war.evt_067_de_grasse(st, shaded=True)
    assert st["free_ops"] == [(C.FRENCH, "muster", None)]

    st_pre = dict(st, toa_played=False, free_ops=[],
                  remain_eligible=set())
    late_war.evt_067_de_grasse(st_pre, shaded=True)
    assert st_pre["free_ops"] == [(C.PATRIOTS, "rally", None)], \
        "pre-ToA the French can neither Rally nor Muster"


def test_free_war_path_executes_with_option_per_4_4_2():
    """I8/4.4.2: a pinned free War Path with a Patriot Fort, no Rebellion
    units and 2+ Underground WPs uses option 3 (Fort removal)."""
    st = build_state("1775", seed=1)
    _clear(st, "Northwest")
    st["spaces"]["Northwest"][C.WARPARTY_U] = 2
    st["spaces"]["Northwest"][C.FORT_PAT] = 1
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.INDIANS, "war_path", "Northwest")
    _drain(eng)
    nw = eng.state["spaces"]["Northwest"]
    assert nw.get(C.FORT_PAT, 0) == 0, "option 3 removes the Patriot Fort"
    assert "FREE WAR_PATH by INDIANS in Northwest" in _hist(eng)


def test_free_war_path_declines_without_rebellion_pieces():
    """4.4.2 needs a Rebellion piece in the space; a card pinning an
    empty Reserve is a genuine decline, not a planner gap."""
    st = build_state("1775", seed=1)
    _clear(st, "Northwest")
    st["spaces"]["Northwest"][C.WARPARTY_U] = 2
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.INDIANS, "war_path", "Northwest")
    _drain(eng)
    hist = _hist(eng)
    assert "declined (no legal plan)" in hist
    assert "no bot planner" not in hist


def test_free_partisans_removes_village_with_option3():
    """P8 'first to remove a Village' / 4.3.2 option 3 (no War Parties
    present, 2+ Underground Militia)."""
    st = build_state("1775", seed=1)
    _clear(st, "Virginia")
    st["spaces"]["Virginia"][C.MILITIA_U] = 2
    st["spaces"]["Virginia"][C.VILLAGE] = 1
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.PATRIOTS, "partisans", "Virginia")
    _drain(eng)
    va = eng.state["spaces"]["Virginia"]
    assert va.get(C.VILLAGE, 0) == 0, "option 3 removes the Village"
    assert "FREE PARTISANS by PATRIOTS in Virginia" in _hist(eng)


def test_free_partisans_option2_removes_two_royalist_units():
    """P8 + 8.1.2 maximum extent: with 2+ enemy cubes and 2+ Underground
    Militia, option 2 trades one Militia for two Royalist removals."""
    st = build_state("1775", seed=1)
    _clear(st, "Virginia")
    st["spaces"]["Virginia"][C.MILITIA_U] = 3
    st["spaces"]["Virginia"][C.TORY] = 2
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.PATRIOTS, "partisans", "Virginia")
    _drain(eng)
    va = eng.state["spaces"]["Virginia"]
    assert va.get(C.TORY, 0) == 0, "option 2 removes two Royalist units"


def test_free_patriot_rally_places_at_empty_legal_space_when_pinned():
    """3.3.1 Rally does not require friendly pieces in the space; a
    pinned free Rally in an empty legal Colony places a Militia."""
    st = build_state("1775", seed=1)
    _clear(st, "Virginia")
    st["support"]["Virginia"] = C.NEUTRAL
    st["available"][C.MILITIA_U] = max(5, st["available"].get(C.MILITIA_U, 0))
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.PATRIOTS, "rally", "Virginia")
    _drain(eng)
    assert eng.state["spaces"]["Virginia"].get(C.MILITIA_U, 0) >= 1


def test_free_patriot_rally_bulk_places_at_fort():
    """8.5.2 / 8.1.2 maximum extent: at a Patriot Fort the free Rally
    places up to Fort + Population Militia, not just one."""
    st = build_state("1775", seed=1)
    _clear(st, "Virginia")
    st["spaces"]["Virginia"][C.FORT_PAT] = 1
    st["support"]["Virginia"] = C.NEUTRAL
    st["available"][C.MILITIA_U] = max(8, st["available"].get(C.MILITIA_U, 0))
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.PATRIOTS, "rally", "Virginia")
    _drain(eng)
    placed = eng.state["spaces"]["Virginia"].get(C.MILITIA_U, 0)
    assert placed >= 2, f"expected Fort+Pop bulk placement, got {placed}"


def test_free_indian_march_never_targets_a_city():
    """3.4.2: Indians may not occupy a City; an unpinned free Indian
    March must not pick one even when a City holds the most enemies."""
    st = build_state("1775", seed=1)
    eng = Engine(initial_state=st)
    queue_free_op(eng.state, C.INDIANS, "march", None)
    _drain(eng)
    hist = _hist(eng)
    assert "skipped (no valid target)" not in hist
    if "FREE MARCH by INDIANS in" in hist:
        from lod_ai.map import adjacency as map_adj
        dest = hist.split("FREE MARCH by INDIANS in ")[1].split(" |")[0].strip()
        assert map_adj.space_type(dest) != "City"


def test_french_free_battle_pre_toa_is_genuine_decline():
    """§3.5: French cannot Battle before the Treaty of Alliance. A card
    granting French a free Battle pre-ToA must be a planner decline
    ('no legal plan'), not an execution skip — battle.execute raises on
    the ToA gate that the planner previously did not check."""
    from lod_ai.engine import Engine
    from lod_ai import rules_consts as C

    eng = Engine(initial_state={
        "spaces": {"Boston": {C.REGULAR_FRE: 2, C.REGULAR_BRI: 2}},
        "resources": {C.BRITISH: 9, C.PATRIOTS: 9, C.FRENCH: 9, C.INDIANS: 9},
        "available": {}, "unavailable": {}, "markers": {}, "support": {},
    })
    eng.set_human_factions(set())
    assert not eng.state.get("toa_played")
    plan = eng._plan_bot_free_op(eng.state, C.FRENCH, "battle_plus2", None)
    assert plan is None  # genuine decline

    eng.state["toa_played"] = True
    plan = eng._plan_bot_free_op(eng.state, C.FRENCH, "battle_plus2", None)
    assert plan == {"space": "Boston"}
