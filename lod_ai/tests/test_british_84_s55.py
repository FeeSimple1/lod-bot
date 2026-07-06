"""Session 55 — §8.1 "Paying Resource Costs" (pay-as-you-select) and the
§8.4.4/§8.4.1 audit fixes.

The headline defect: the British Muster/March planners built up-to-4-space
plans with no reference to the purse, then aborted the WHOLE Command when
the plan was unaffordable — so with 1-3 Resources the Non-player British
passed outright (~half their passes were this, every game).  §8.1: "If it
has sufficient Resources to execute at least some instructions of the
selected Command, it pays the appropriate Resource cost when it selects
each space."
"""
import lod_ai.rules_consts as C
from lod_ai.bots.british_bot import BritishBot
from lod_ai.state.setup_state import build_state
from lod_ai.board.control import refresh_control


def _fresh(scenario="1775", seed=7):
    return build_state(scenario, seed=seed)


def test_muster_with_one_resource_executes_one_space():
    """§8.1: with 1 Resource and Available Regulars, Muster in 1 space
    instead of aborting a multi-space plan (S55)."""
    state = _fresh()
    bot = BritishBot()
    state["resources"][C.BRITISH] = 1
    state["available"][C.REGULAR_BRI] = max(6, state["available"].get(C.REGULAR_BRI, 0))
    state["_muster_die_cached"] = 1  # force B6 gate open deterministically
    ok = bot._muster(state, tried_march=True)
    assert ok, "Muster must execute with 1 Resource (§8.1 pay-as-you-select)"
    assert state["resources"][C.BRITISH] >= 0


def test_march_with_one_resource_keeps_highest_priority_destination():
    """§8.1: with 1 Resource, March trims to 1 destination (plan order =
    §8.4.3 priority order) instead of aborting (S55)."""
    state = _fresh(seed=11)
    bot = BritishBot()
    state["resources"][C.BRITISH] = 1
    # tried_muster=True prevents the Muster fallback from masking a failure
    ok = bot._march(state, tried_muster=True)
    if ok:
        # March executed and paid within budget
        assert state["resources"][C.BRITISH] >= 0
    else:
        # Only acceptable if there is genuinely no movable British group
        assert not any(
            sp.get(C.REGULAR_BRI, 0) > 0 for sp in state["spaces"].values()
        ), "March aborted despite movable Regulars and 1 Resource (§8.1)"


def test_garrison_gate_requires_two_resources():
    """§8.1 + §3.2.2 (two Resources total): an unaffordable Garrison is
    skipped at the gate — without burning the SA first (S55)."""
    state = _fresh()
    bot = BritishBot()
    state["resources"][C.BRITISH] = 1
    assert bot._can_garrison(state) is False


def test_garrison_ten_regular_count_excludes_west_indies():
    """§8.4.1: '10 or more Regulars in all Cities and Provinces on the map
    combined' — the West Indies box is neither (S55)."""
    state = _fresh()
    bot = BritishBot()
    state["resources"][C.BRITISH] = 5
    # Strip Regulars everywhere, then stack 10 in the West Indies box and
    # 9 on the map: the gate must NOT count the WI Regulars.
    for sid, sp in state["spaces"].items():
        sp[C.REGULAR_BRI] = 0
    state["spaces"][C.WEST_INDIES_ID][C.REGULAR_BRI] = 10
    state["spaces"]["Boston"][C.REGULAR_BRI] = 9
    # Ensure a Rebellion-controlled City without a Patriot Fort exists so
    # only the Regular count decides the gate.
    ny = state["spaces"]["New_York_City"]
    ny[C.FORT_PAT] = 0
    ny[C.MILITIA_A] = 5
    refresh_control(state)
    assert bot._can_garrison(state) is False
    state["spaces"]["Boston"][C.REGULAR_BRI] = 10
    refresh_control(state)
    assert bot._can_garrison(state) is True


def test_skirmish_prefers_cube_removal_space():
    """§8.4.1 bullet 1 (S55): among same-tier spaces, Skirmish picks where
    the most Rebellion CUBES can be removed (Glossary: Militia are not
    cubes), not the space with fewest total rebels."""
    state = _fresh()
    bot = BritishBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.REGULAR_BRI, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.MILITIA_A, C.MILITIA_U, C.FORT_PAT, C.TORY):
            sp[tag] = 0
    # Space A: 1 lone Active Militia (old code's favourite: fewest rebels)
    state["spaces"]["Georgia"][C.REGULAR_BRI] = 2
    state["spaces"]["Georgia"][C.MILITIA_A] = 1
    # Space B: 2 Continentals — 2 cubes removable via option 2
    state["spaces"]["Virginia"][C.REGULAR_BRI] = 2
    state["spaces"]["Virginia"][C.REGULAR_PAT] = 2
    state["_turn_affected_spaces"] = set()
    refresh_control(state)
    crc_before = state.get("crc", 0)
    assert bot._try_skirmish(state) is True
    assert state["spaces"]["Virginia"].get(C.REGULAR_PAT, 0) == 0, (
        "Skirmish should remove the 2 Continentals (cubes → Casualties), "
        "not the lone Militia"
    )
    assert state.get("crc", 0) >= crc_before + 2


def test_skirmish_executor_removes_cubes_before_militia():
    """§8.4.1 (S55): option 1 removes a cube (→ Casualties) before Active
    Militia (→ Available); among cube types, the least-represented first."""
    from lod_ai.special_activities import skirmish
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 2,
                C.REGULAR_PAT: 2,
                C.REGULAR_FRE: 1,
                C.MILITIA_A: 3,
            },
        },
        "resources": {C.BRITISH: 5},
        "available": {},
        "support": {"Boston": 0},
        "control": {},
        "history": [],
        "casualties": {},
        "leaders": {},
        "leader_locs": {},
    }
    skirmish.execute(state, C.BRITISH, {}, "Boston", option=1)
    sp = state["spaces"]["Boston"]
    assert sp.get(C.REGULAR_FRE, 0) == 0, (
        "Least-represented cube type (1 French Regular) removed first "
        "(§8.4.1 'first whichever type is least in the space')"
    )
    assert sp.get(C.MILITIA_A, 0) == 3


def test_battle_spaces_excluded_from_pre_battle_skirmish():
    """§4.2.2/§8.4.4 (S55): the Skirmish that accompanies a Battle may not
    take place in a space selected for Battle, even though it resolves
    before battle.execute registers the spaces."""
    state = _fresh()
    bot = BritishBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.REGULAR_BRI, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.MILITIA_A, C.MILITIA_U, C.FORT_PAT, C.TORY,
                    C.WARPARTY_A, C.WARPARTY_U):
            sp[tag] = 0
    # One overwhelming battle space; no other skirmishable space exists.
    state["spaces"]["Virginia"][C.REGULAR_BRI] = 8
    state["spaces"]["Virginia"][C.REGULAR_PAT] = 2
    state["resources"][C.BRITISH] = 5
    state["_turn_affected_spaces"] = set()
    refresh_control(state)
    assert bot._can_battle(state) is True
    ok = bot._battle(state)
    assert ok is True
    hist = " | ".join(h["msg"] if isinstance(h, dict) else str(h)
                      for h in state.get("history", []))
    assert "SKIRMISH begins in Virginia" not in hist, (
        "Skirmish must not fire in the space selected for Battle (§4.2.2)"
    )


def test_battle_resolver_receives_common_cause_ctx():
    """§4.2.1 (S55): the resolver must count utilized War Parties as
    Tories in the ACTUAL Force Level, not only in the B12 selection
    score — _try_common_cause returns the ctx and _battle forwards it."""
    state = _fresh()
    bot = BritishBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.REGULAR_BRI, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.MILITIA_A, C.MILITIA_U, C.FORT_PAT, C.TORY,
                    C.WARPARTY_A, C.WARPARTY_U, C.FORT_BRI, C.VILLAGE):
            sp[tag] = 0
    # 4 Regulars + 3 War Parties vs 5 Continentals: without CC the
    # attack force is 4 + floor(3/2) = 5 (+1 half-regs mod) and loses
    # the selection; WITH CC (3 WP as Tories) it is 4 + 3 = 7 and wins.
    sp = state["spaces"]["Virginia"]
    sp[C.REGULAR_BRI] = 4
    sp[C.WARPARTY_A] = 2
    sp[C.WARPARTY_U] = 2   # one must stay Underground (B13)
    sp[C.REGULAR_PAT] = 5
    state["resources"][C.BRITISH] = 5
    state["_turn_affected_spaces"] = set()
    refresh_control(state)
    ok = bot._battle(state)
    assert ok is True
    hist = [h["msg"] if isinstance(h, dict) else str(h)
            for h in state.get("history", [])]
    assert any("COMMON CAUSE" in m.upper() or "COMMON_CAUSE" in m.upper()
               for m in hist), "Common Cause should have been executed"
    # The Continentals must take real losses — with the pre-S55 empty
    # ctx the resolution force collapsed to 4 + half-WP and the defender
    # often out-hit the attacker.
    assert state["spaces"]["Virginia"].get(C.REGULAR_PAT, 0) < 5


def test_indian_reserve_defense_modifier_counts_villages():
    """§3.6.5 'Indians Defending in Indian Reserve -1' (S55): Villages
    are Indian pieces — a Village-only defense still gets the modifier."""
    from lod_ai.commands.battle import _defender_loss_mods
    from lod_ai.map import adjacency as map_adj
    # find a Reserve space
    reserve = None
    state = _fresh()
    for sid in state["spaces"]:
        if map_adj.space_type(sid) == "Reserve":
            reserve = sid
            break
    assert reserve, "no Reserve space found"
    sp = state["spaces"][reserve]
    for tag in (C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE, C.REGULAR_BRI,
                C.TORY, C.FORT_BRI):
        sp[tag] = 0
    # §3.6.5 is the DEFENDER Loss Level table: "Indians Defending in
    # Indian Reserve -1" lowers the DEFENDER's losses.
    sp[C.VILLAGE] = 1
    with_village = _defender_loss_mods(state, sp, reserve,
                                       "REBELLION", "ROYALIST", 0)
    sp[C.VILLAGE] = 0
    without = _defender_loss_mods(state, sp, reserve,
                                  "REBELLION", "ROYALIST", 0)
    assert with_village == without - 1, (
        "Village-only Reserve defense must apply the -1 modifier"
    )


def test_cc_war_parties_absorb_losses_in_tory_slot():
    """Q19 (Playbook p.~850): CC War Parties absorb Battle losses "as a
    Tory" — the §3.6.7 alternation takes Regular, then a CC WP (to
    Available, no CBC) before more Regulars, sparing British cubes."""
    from lod_ai.commands import battle
    state = _fresh()
    for sid, sp in state["spaces"].items():
        for tag in (C.REGULAR_BRI, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.MILITIA_A, C.MILITIA_U, C.FORT_PAT, C.TORY,
                    C.WARPARTY_A, C.WARPARTY_U, C.FORT_BRI, C.VILLAGE):
            sp[tag] = 0
    sp = state["spaces"]["Virginia"]
    sp[C.REGULAR_BRI] = 4
    sp[C.WARPARTY_A] = 2
    sp[C.REGULAR_PAT] = 6
    sp[C.MILITIA_U] = 1     # +1 attacker-loss mod -> ODD loss level, so
    #                         the Tory-slot absorption visibly spares a
    #                         Regular (even losses hide it: the mandated
    #                         alternation overshoots to the same Regulars)
    state["resources"][C.BRITISH] = 5
    refresh_control(state)
    import copy
    base = copy.deepcopy(state)

    cbc0 = state.get("cbc", 0)
    battle.execute(state, C.BRITISH,
                   {"common_cause": {"Virginia": 2}}, ["Virginia"])
    with_cc_regs_lost = 4 - state["spaces"]["Virginia"].get(C.REGULAR_BRI, 0)
    with_cc_wp_lost = 2 - state["spaces"]["Virginia"].get(C.WARPARTY_A, 0)
    with_cc_cbc = state.get("cbc", 0) - cbc0

    battle.execute(base, C.BRITISH, {}, ["Virginia"])
    no_cc_regs_lost = 4 - base["spaces"]["Virginia"].get(C.REGULAR_BRI, 0)

    total_with_cc = with_cc_regs_lost + with_cc_wp_lost
    assert total_with_cc >= 3, "setup should force 3+ attacker removals"
    # Q19: the WPs absorb in the Tory slot, so strictly fewer Regulars
    # die than in the same battle without CC.
    assert with_cc_wp_lost >= 1, "a CC WP must have absorbed a loss"
    assert with_cc_regs_lost < no_cc_regs_lost, (
        "CC absorption must spare British Regulars (Q19 / Playbook)"
    )
    # CBC counts cubes/forts only — the absorbed WPs add nothing.
    assert with_cc_cbc == with_cc_regs_lost
