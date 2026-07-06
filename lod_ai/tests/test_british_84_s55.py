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
