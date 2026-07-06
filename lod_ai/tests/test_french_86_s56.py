"""Session 56 — F-node inventory fixes (§8.6, §3.5, §4.5.3)."""
import lod_ai.rules_consts as C
from lod_ai.bots.french import FrenchBot
from lod_ai.state.setup_state import build_state
from lod_ai.board.control import refresh_control


def _fresh(scenario="1775", seed=7):
    return build_state(scenario, seed=seed)


def test_fam_prefers_control_flip_over_patriot_pile():
    """§8.6.2 (S56): "first to add most Rebellion Control" is a
    lexicographic tier ABOVE "most Patriot units", and the control add
    is simulated — a Rebellion-held province stuffed with Patriots must
    not outrank a flippable empty one."""
    state = _fresh()
    bot = FrenchBot()
    for prov in ("Quebec", "New_York", "New_Hampshire", "Massachusetts"):
        sp = state["spaces"][prov]
        for tag in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_BRI,
                    C.TORY, C.FORT_BRI, C.FORT_PAT, C.REGULAR_FRE,
                    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE):
            sp[tag] = 0
        state["support"][prov] = 0
    # New_York: already Rebellion-controlled, 15 Patriot units
    state["spaces"]["New_York"][C.MILITIA_U] = 15
    # New_Hampshire: empty — placing 2 Militia flips it to Rebellion
    state.setdefault("available", {})[C.MILITIA_U] = max(
        2, state["available"].get(C.MILITIA_U, 0))
    state["resources"][C.FRENCH] = 5
    refresh_control(state)
    assert state["control"].get("New_York") == "REBELLION"
    ok = bot._agent_mobilization(state)
    assert ok
    # Quebec / New_Hampshire / Massachusetts tie on (flip, 0 patriots) —
    # any is legal (§8.2 seeded ties); the Rebellion-held pile is not.
    assert state["spaces"]["New_York"].get(C.MILITIA_U, 0) == 15, (
        "FAM must not stack the Rebellion-held Patriot pile"
    )
    placed = [p for p in ("Quebec", "New_Hampshire", "Massachusetts")
              if state["spaces"][p].get(C.MILITIA_U, 0) == 2]
    assert len(placed) == 1, (
        "FAM must pick a flippable province (control tier) over the "
        "Rebellion-held Patriot pile (§8.6.2 lexicographic priority)"
    )


def test_french_muster_fallback_excludes_reserves():
    """§8.6.4/§3.5.3 (S56): Muster destinations are Cities/Colonies (or
    WI via the fewer-than-four branch) — never Reserves/Provinces, even
    in the fallback tier."""
    state = _fresh()
    bot = FrenchBot()
    # Make exactly one Rebellion-controlled space: the Quebec Reserve.
    for sid, sp in state["spaces"].items():
        for tag in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.REGULAR_BRI, C.TORY, C.FORT_PAT, C.FORT_BRI,
                    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE):
            sp[tag] = 0
    state["spaces"]["Quebec"][C.MILITIA_A] = 3
    state["resources"][C.FRENCH] = 5
    # 4+ Available Regulars => second branch (not the WI branch)
    state["available"][C.REGULAR_FRE] = 6
    refresh_control(state)
    assert state["control"].get("Quebec") == "REBELLION"
    ok = bot._muster(state)
    assert ok is False, (
        "No City/Colony has Rebellion Control — Muster must fail to the "
        "Hortalez fallback, not place Regulars in a Reserve (§3.5.3)"
    )


def test_naval_pressure_skips_blockaded_city_and_conserves_markers():
    """§4.5.3/Q21 (S56): the NP target scan must skip already-blockaded
    Cities; a duplicate placement must not silently destroy a marker."""
    from lod_ai.special_activities import naval_pressure
    state = _fresh()
    bot = FrenchBot()
    state["toa_played"] = True
    state["treaty_of_alliance"] = True
    state["fni_level"] = 0
    bloc = state.setdefault("markers", {}).setdefault(
        C.BLOCKADE, {"pool": 0, "on_map": set()})
    bloc["pool"] = 2
    bloc["on_map"] = set()
    # Boston: highest support city
    state["support"]["Boston"] = 2
    state["support"]["New_York_City"] = 1
    state["_turn_affected_spaces"] = set()
    assert bot._try_naval_pressure(state) is True
    assert "Boston" in bloc["on_map"]
    pool_after_first = bloc["pool"]
    # Second NP: Boston is blockaded now — must pick another city, and
    # the marker count must be conserved.
    assert bot._try_naval_pressure(state) is True
    assert len(bloc["on_map"]) == 2, (
        "second Blockade must land on a DIFFERENT city (no-benefit "
        "filter), not vanish on Boston"
    )
    assert bloc["pool"] == pool_after_first - 1
    # Executor guard: direct duplicate placement raises, pool intact.
    bloc["pool"] = 1
    try:
        naval_pressure.execute(state, C.FRENCH, {}, city_choice="Boston")
        raised = False
    except ValueError:
        raised = True
    assert raised, "duplicate placement must fail loudly (Q21 guard)"
    assert bloc["pool"] == 1, "the marker must NOT be destroyed"


def test_wtd_blockade_move_refuses_occupied_destination():
    """S56/Q21: moving a Blockade onto an occupied City would delete a
    marker under the set model — move_blockade_city_to_city refuses."""
    from lod_ai.util.naval import move_blockade_city_to_city
    state = _fresh()
    bloc = state.setdefault("markers", {}).setdefault(
        C.BLOCKADE, {"pool": 0, "on_map": set()})
    bloc["on_map"] = {"Boston", "New_York_City"}
    ok = move_blockade_city_to_city(state, "Boston", "New_York_City")
    assert ok is False
    assert bloc["on_map"] == {"Boston", "New_York_City"}, "markers conserved"


def test_french_battle_keeps_ally_free_space_when_patriots_broke():
    """§3.5.5 (S56): when the Patriots cannot pay the allied fee, a space
    that still passes the Force-Level test WITHOUT Patriot pieces stays
    selected (battle.execute resolves it ally-free)."""
    state = _fresh()
    bot = FrenchBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.REGULAR_BRI, C.TORY, C.FORT_PAT, C.FORT_BRI,
                    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE):
            sp[tag] = 0
    sp = state["spaces"]["Virginia"]
    sp[C.REGULAR_FRE] = 6       # French crush alone
    sp[C.REGULAR_PAT] = 1       # Patriot piece present -> fee would apply
    sp[C.REGULAR_BRI] = 2
    state["resources"][C.FRENCH] = 5
    state["resources"][C.PATRIOTS] = 0   # broke — fee unpayable
    state["toa_played"] = True
    state["treaty_of_alliance"] = True
    refresh_control(state)
    ok = bot._battle(state)
    assert ok is True, (
        "space passes ally-free; Patriots' empty purse must not cancel "
        "the Battle (§3.5.5 fee is optional)"
    )
