"""
lod_ai.bots.free_op_planner
===========================

Planning for card-granted FREE Commands and FREE Special Activities
executed by Non-player Factions (called from ``Engine._drain_free_ops``).

Why this exists: the dispatcher cannot invent a plan from ``space=None``,
and Manual §8.3.5 directs that any choices made while executing a free
Command or Special Activity use the executing Faction's priorities
(8.4-8.7), with pieces per 8.1.2 and spaces randomly per 8.2 where those
priorities are not applicable.  For "March then Battle" pairs the
priorities of the first Command (March) apply.

Transcribed sources (Reference Documents are the source of truth):

* Manual Ch 8 §8.3.5 — free-op choice rules (see above).
* British flowchart node B10 / §8.4.3 — British March movement
  restrictions and destination priorities.
* Patriot flowchart node P5 / §8.5.4 — Patriot March.
* French flowchart node F14 / §8.6.5 — French March.
* Indian flowchart node I10 / §8.7.3 — Indian March.
* §8.5.2 — Patriot Rally space priorities (Rally is Patriot-only, §3.3).
* Manual Ch 3 §3.2.3 / §3.3.2 / §3.4.2 / §3.5.4 — March piece legality:
  only Regulars March for Britain/France, with Tories/Continentals/French
  Regulars accompanying 1-for-1; Indians may never enter a City.
* Indian flowchart node I8 + §4.4.2 — free War Path target and option.
* Patriot flowchart node P8 + §4.3.2 — free Partisans target and option.

The movement-restriction logic intentionally mirrors the audited bot
implementations (british_bot._march's ``_movable_from``,
patriot._movable_from_simulated, indians._march's ``_can_remove``,
french._march), specialised to the single destination that a
card-granted free Command selects.  Free Commands include only the
Command itself, so no Common Cause (a Special Activity) is used to
augment a free British March.

A return value of ``None`` always means a genuine "no legal plan"
decline, never a planner gap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lod_ai import rules_consts as C
from lod_ai.map import adjacency as map_adj
from lod_ai.board.control import refresh_control

_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)

# Tag groups (control-style tallies; Villages are Indian pieces, §1.6.5)
_REBEL_TAGS = (C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U,
               C.FORT_PAT)
_ROYALIST_TAGS = (C.REGULAR_BRI, C.TORY, C.WARPARTY_A, C.WARPARTY_U,
                  C.FORT_BRI, C.VILLAGE)
_REBEL_UNIT_TAGS = (C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U)


def _stype(sid: str) -> str:
    return _MAP_DATA.get(sid, {}).get("type", "")


def _pop(sid: str) -> int:
    return _MAP_DATA.get(sid, {}).get("population", 0)


def _support(state: Dict, sid: str) -> int:
    return state.get("support", {}).get(sid, 0)


def _rebels(sp: Dict) -> int:
    return sum(sp.get(t, 0) for t in _REBEL_TAGS)


def _royalists(sp: Dict) -> int:
    return sum(sp.get(t, 0) for t in _ROYALIST_TAGS)


def _rand_choice(state: Dict, items):
    """Uniform random pick among candidates (8.2 stand-in, as used by
    the audited bot planners)."""
    items = sorted(items)
    rng = state.get("rng")
    if len(items) > 1 and rng is not None:
        return items[rng.randrange(len(items))]
    return items[0]


def _reachable(state: Dict, faction: str, src: str, dst: str) -> bool:
    """March route legality for one src→dst leg (§3.2.3/3.4.2/3.5.4)."""
    if src == dst:
        return False
    if map_adj.is_adjacent(src, dst):
        return True
    # British/French Regulars may use the City network (3.2.3 / 3.5.4).
    from lod_ai.commands.march import _city_network_legal
    return _city_network_legal(state, faction, src, dst)


# =====================================================================
#  March — movable pieces per origin (faction movement restrictions)
# =====================================================================

def _brit_movable(state: Dict, sid: str) -> Dict[str, int]:
    """B10/§8.4.3 bullets, mirroring british_bot._march._movable_from:
    lose no British Control of the origin; leave the last Tory in each
    space; leave the last Regular if British Control but no Active
    Support.  §3.2.3: Tories may only accompany Regulars 1-for-1."""
    sp = state["spaces"][sid]
    regs = sp.get(C.REGULAR_BRI, 0)
    tories = sp.get(C.TORY, 0)
    if regs <= 0:
        return {}
    ctrl = state.get("control", {}).get(sid)
    at_as = _support(state, sid) >= C.ACTIVE_SUPPORT
    min_tories = min(1, tories)
    min_regs = 1 if (ctrl == "BRITISH" and not at_as) else 0
    avail_regs = max(0, regs - min_regs)
    avail_tories = max(0, tories - min_tories)
    if ctrl == "BRITISH":
        rebel = _rebels(sp)
        static_roy = _royalists(sp) - regs - tories  # Forts/WPs/Villages stay
        cubes_must_stay = max(0, rebel + 1 - static_roy)
        max_leave = max(0, regs + tories - cubes_must_stay)
        if avail_regs + avail_tories > max_leave:
            cut = avail_regs + avail_tories - max_leave
            cut_t = min(cut, avail_tories)
            avail_tories -= cut_t
            avail_regs -= (cut - cut_t)
    avail_tories = min(avail_tories, avail_regs)   # 1-for-1 escort cap
    if avail_regs <= 0:
        return {}
    out = {C.REGULAR_BRI: avail_regs}
    if avail_tories > 0:
        out[C.TORY] = avail_tories
    return out


def _pat_movable(state: Dict, sid: str) -> Dict[str, int]:
    """P5/§8.5.4 bullets, mirroring patriot._movable_from_simulated:
    lose no Rebellion Control; leave an Active Patriot unit with each
    Patriot Fort; leave a Patriot unit (Underground Militia preferred)
    in each space not at Active Opposition.  §3.3.2: French Regulars
    accompany Continentals 1-for-1."""
    sp = state["spaces"][sid]
    avail = {
        C.REGULAR_PAT: max(0, sp.get(C.REGULAR_PAT, 0)),
        C.MILITIA_A: max(0, sp.get(C.MILITIA_A, 0)),
        C.MILITIA_U: max(0, sp.get(C.MILITIA_U, 0)),
        C.REGULAR_FRE: max(0, sp.get(C.REGULAR_FRE, 0)),
    }
    total = sum(avail.values())
    if total == 0:
        return {}
    retain = 0
    has_fort = sp.get(C.FORT_PAT, 0) > 0
    if has_fort:
        retain = max(retain, 1)
    if _support(state, sid) > C.ACTIVE_OPPOSITION:
        retain = max(retain, 1)
    if state.get("control", {}).get(sid) == "REBELLION":
        max_can_move = max(0, _rebels(sp) - _royalists(sp) - 1)
        retain = max(retain, total - max_can_move)
    if retain >= total:
        return {}
    can_move = total - retain
    if has_fort:
        move_order = [C.MILITIA_U, C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE]
    else:
        move_order = [C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE, C.MILITIA_U]
    result: Dict[str, int] = {}
    remaining = can_move
    for tag in move_order:
        take = min(remaining, avail.get(tag, 0))
        if take > 0:
            result[tag] = take
            remaining -= take
        if remaining <= 0:
            break
    # §3.3.2: French Regulars only accompany Continentals 1-for-1.
    if result.get(C.REGULAR_FRE, 0) > result.get(C.REGULAR_PAT, 0):
        result[C.REGULAR_FRE] = result.get(C.REGULAR_PAT, 0)
        if result[C.REGULAR_FRE] == 0:
            del result[C.REGULAR_FRE]
    return result


def _village_room(sp: Dict) -> bool:
    """Room for a Village (bases < 2), mirroring indians._village_room."""
    bases = sp.get(C.VILLAGE, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.FORT_PAT, 0)
    return bases < 2


def _ind_movable(state: Dict, sid: str) -> Dict[str, int]:
    """I10/§8.7.3 bullets, mirroring indians._march._can_remove:
    March Underground then Active War Parties; never move the last WP
    from a Village space, nor the last 3 WPs from a space where Gather
    could place a Village, nor add any Rebellion Control."""
    sp = state["spaces"][sid]
    u = sp.get(C.WARPARTY_U, 0)
    a = sp.get(C.WARPARTY_A, 0)
    total = u + a
    if total == 0:
        return {}
    keep = 0
    if sp.get(C.VILLAGE, 0) > 0:
        keep = max(keep, 1)
    if (_stype(sid) != "City" and sp.get(C.VILLAGE, 0) == 0
            and _village_room(sp)):
        keep = max(keep, 3)
    if state.get("control", {}).get(sid) != "REBELLION":
        reb = _rebels(sp)
        bri = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) + sp.get(C.FORT_BRI, 0)
        keep = max(keep, reb - bri)        # keep royalist_after >= rebels
    movable = max(0, total - keep)
    if movable <= 0:
        return {}
    out: Dict[str, int] = {}
    take_u = min(u, movable)               # Underground first
    if take_u:
        out[C.WARPARTY_U] = take_u
    take_a = min(a, movable - take_u)
    if take_a:
        out[C.WARPARTY_A] = take_a
    return out


def _fre_movable(state: Dict, sid: str) -> Dict[str, int]:
    """F14/§8.6.5 bullet (lose no Rebellion Control), mirroring
    french._march.  §3.5.4: Continentals accompany French Regulars
    1-for-1 (at the French's option)."""
    sp = state["spaces"][sid]
    fre = sp.get(C.REGULAR_FRE, 0)
    if fre <= 0:
        return {}
    max_move = fre
    if state.get("control", {}).get(sid) == "REBELLION":
        max_move = min(max_move, max(0, _rebels(sp) - _royalists(sp) - 1))
    if max_move <= 0:
        return {}
    out = {C.REGULAR_FRE: max_move}
    escorts = min(max_move, sp.get(C.REGULAR_PAT, 0))
    if escorts > 0:
        out[C.REGULAR_PAT] = escorts
    return out


_MOVABLE = {
    C.BRITISH: _brit_movable,
    C.PATRIOTS: _pat_movable,
    C.INDIANS: _ind_movable,
    C.FRENCH: _fre_movable,
}


# =====================================================================
#  March — destination priorities per faction (single destination)
# =====================================================================

def _march_dest_candidates(state: Dict, faction: str,
                           movable: Dict[str, Dict[str, int]]) -> List[str]:
    """Ordered destination candidates for a one-space free March, per
    the faction's March priorities.  Ends with the random-space
    fallback (§8.3.5: where the priorities are not applicable, choose
    spaces randomly per 8.2)."""
    spaces = state["spaces"]
    ctrl = state.get("control", {})

    def reach_sources(dst):
        return [s for s in movable if _reachable(state, faction, s, dst)]

    reachable_dests = [d for d in spaces if reach_sources(d)]
    if faction == C.INDIANS:                      # §3.4.2 executor rule
        reachable_dests = [d for d in reachable_dests if _stype(d) != "City"]
    if not reachable_dests:
        return []

    ordered: List[str] = []

    def _push(cands_with_keys):
        """Append best-first by sort key with random tie-break (8.2)."""
        by_key: Dict[tuple, List[str]] = {}
        for key, d in cands_with_keys:
            by_key.setdefault(key, []).append(d)
        for key in sorted(by_key):
            group = by_key[key]
            while group:
                pick = _rand_choice(state, group)
                group.remove(pick)
                if pick not in ordered:
                    ordered.append(pick)

    def incoming(dst):
        return sum(sum(movable[s].values()) for s in reach_sources(dst))

    if faction == C.BRITISH:
        # B10: add British Control to Cities then Colonies, first where
        # Rebel cubes, then highest Pop.
        tier1 = []
        for d in reachable_dests:
            if ctrl.get(d) == "BRITISH" or _stype(d) not in ("City", "Colony"):
                continue
            dsp = spaces[d]
            if _royalists(dsp) + incoming(d) <= _rebels(dsp):
                continue                          # cannot establish Control
            rebel_cubes = sum(dsp.get(t, 0) for t in _REBEL_UNIT_TAGS)
            tier1.append(((0 if _stype(d) == "City" else 1,
                           -rebel_cubes, -_pop(d)), d))
        _push(tier1)
        # B10: then Pop 1+ spaces not at Active Support, first to add
        # Tories where Regulars are the only British units, then to add
        # Regulars where Tories are the only British units.
        tier2 = []
        for d in reachable_dests:
            if _pop(d) < 1 or _support(state, d) >= C.ACTIVE_SUPPORT:
                continue
            dsp = spaces[d]
            regs_only = (dsp.get(C.REGULAR_BRI, 0) > 0
                         and dsp.get(C.TORY, 0) == 0
                         and dsp.get(C.FORT_BRI, 0) == 0)
            tories_only = (dsp.get(C.TORY, 0) > 0
                           and dsp.get(C.REGULAR_BRI, 0) == 0
                           and dsp.get(C.FORT_BRI, 0) == 0)
            tier = 0 if regs_only else (1 if tories_only else 2)
            tier2.append(((tier, -_pop(d)), d))
        _push(tier2)

    elif faction == C.PATRIOTS:
        # P5: add Rebellion Control, first where Villages, then Cities,
        # then elsewhere, within that highest Pop.
        tier1 = []
        for d in reachable_dests:
            if ctrl.get(d) == "REBELLION":
                continue
            dsp = spaces[d]
            if _rebels(dsp) + incoming(d) <= _royalists(dsp):
                continue
            has_village = 1 if dsp.get(C.VILLAGE, 0) else 0
            is_city = 1 if _stype(d) == "City" else 0
            tier1.append(((-has_village, -is_city, -_pop(d)), d))
        _push(tier1)
        # P5: then get one Militia into each space with none, first to
        # change Control of the most Population.
        tier2 = []
        for d in reachable_dests:
            dsp = spaces[d]
            if any(dsp.get(t, 0) for t in
                   (C.MILITIA_U, C.MILITIA_A, C.REGULAR_PAT)):
                continue
            changes_ctrl = 1 if (_rebels(dsp) + 1 > _royalists(dsp)
                                 and ctrl.get(d) != "REBELLION") else 0
            tier2.append(((-changes_ctrl, -(changes_ctrl * _pop(d))), d))
        _push(tier2)

    elif faction == C.FRENCH:
        # F14: add Rebellion Control, first Cities then Colonies, within
        # each first where most British pieces.
        tier1 = []
        for d in reachable_dests:
            if ctrl.get(d) == "REBELLION":
                continue
            dsp = spaces[d]
            if _rebels(dsp) + incoming(d) <= _royalists(dsp):
                continue
            is_city = 0 if _stype(d) == "City" else 1
            british = dsp.get(C.REGULAR_BRI, 0) + dsp.get(C.TORY, 0)
            tier1.append(((is_city, -british), d))
        _push(tier1)
        # F14: else toward the nearest British / a space with both
        # Patriot and British pieces.
        tier2 = []
        for d in reachable_dests:
            dsp = spaces[d]
            british = dsp.get(C.REGULAR_BRI, 0) + dsp.get(C.TORY, 0)
            patriots = dsp.get(C.REGULAR_PAT, 0) + dsp.get(C.MILITIA_A, 0) \
                + dsp.get(C.MILITIA_U, 0)
            if british and patriots:
                tier2.append(((0,), d))
            elif british:
                tier2.append(((1,), d))
        _push(tier2)

    elif faction == C.INDIANS:
        # I10: if a Village is Available, get 3+ WPs into a Neutral or
        # Passive space with room for a Village.
        village_avail = state.get("available", {}).get(C.VILLAGE, 0) > 0
        tier1 = []
        if village_avail:
            for d in reachable_dests:
                dsp = spaces[d]
                if not _village_room(dsp) or dsp.get(C.VILLAGE, 0):
                    continue
                if _support(state, d) not in (C.NEUTRAL, C.PASSIVE_SUPPORT,
                                              C.PASSIVE_OPPOSITION):
                    continue
                wp_now = dsp.get(C.WARPARTY_U, 0) + dsp.get(C.WARPARTY_A, 0)
                if wp_now + incoming(d) >= 3:
                    tier1.append(((0,), d))
        _push(tier1)
        # I10: then to remove the most Rebellion Control, first in
        # spaces with no Active Support.
        tier2 = []
        for d in reachable_dests:
            dsp = spaces[d]
            if ctrl.get(d) != "REBELLION":
                continue
            removes = 1 if (_royalists(dsp) + incoming(d)
                            >= _rebels(dsp)) else 0
            if not removes:
                continue
            no_as = 0 if _support(state, d) < C.ACTIVE_SUPPORT else 1
            tier2.append(((no_as, -_pop(d)), d))
        _push(tier2)

    # §8.3.5 fallback: priorities not applicable → random space (8.2).
    remaining = [d for d in reachable_dests if d not in ordered]
    while remaining:
        pick = _rand_choice(state, remaining)
        remaining.remove(pick)
        ordered.append(pick)
    return ordered


def plan_free_march(state: Dict, faction: str,
                    dest: Optional[str]) -> Optional[Dict]:
    """Build march.execute kwargs for a card-granted free March, or
    None when no legal plan exists (a genuine decline)."""
    refresh_control(state)
    movable_fn = _MOVABLE.get(faction)
    if movable_fn is None:
        return None
    movable = {}
    for sid in state["spaces"]:
        m = movable_fn(state, sid)
        if m:
            movable[sid] = m
    if not movable:
        return None

    if dest is not None:
        if faction == C.INDIANS and _stype(dest) == "City":
            return None                            # §3.4.2
        dest_order = [dest]
    else:
        dest_order = _march_dest_candidates(state, faction, movable)

    for d in dest_order:
        sources = [s for s in movable
                   if _reachable(state, faction, s, d)]
        if not sources:
            continue
        # 8.1.2 "move the most pieces": commit every movable piece from
        # every legal source toward the single granted destination.
        plan = [{"src": s, "dst": d, "pieces": dict(movable[s])}
                for s in sources]
        if sum(sum(p["pieces"].values()) for p in plan) <= 0:
            continue
        return {"space": None,
                "sources": sources,
                "destinations": [d],
                "move_plan": plan,
                "bring_escorts": True}
    return None


# =====================================================================
#  Rally — Patriot-only (§3.3.1), space priorities per §8.5.2
# =====================================================================

def plan_free_rally(state: Dict, faction: str,
                    loc: Optional[str]) -> Optional[Dict]:
    """Build rally.execute kwargs for a card-granted free Rally.
    Rally is a Patriot Command (§3.3); any other faction declines."""
    if faction != C.PATRIOTS:
        return None
    refresh_control(state)
    from lod_ai.commands.rally import (_support_value, _is_indian_reserve,
                                       _is_west_indies)

    def _legal(sid):
        return (_support_value(state, sid) != C.ACTIVE_SUPPORT
                and not _is_indian_reserve(sid)
                and not _is_west_indies(sid))

    avail = state.get("available", {})
    fort_avail = avail.get(C.FORT_PAT, 0) > 0
    militia_avail = avail.get(C.MILITIA_U, 0)

    def _kwargs_for(sid) -> Optional[Dict]:
        sp = state["spaces"][sid]
        units = sum(sp.get(t, 0) for t in
                    (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U))
        bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) \
            + sp.get(C.VILLAGE, 0)
        # §8.5.2: place a Fort in a space with 4+ Patriot units and room.
        if (fort_avail and units >= 4 and bases < 2
                and sp.get(C.FORT_PAT, 0) == 0):
            return {"space": None, "selected": [sid], "build_fort": {sid}}
        if militia_avail <= 0:
            return None
        # §8.5.2 / 3.3.1: at a Fort, place up to Fort + Population
        # Militia (8.1.2: to the maximum extent); otherwise place one.
        if sp.get(C.FORT_PAT, 0) > 0:
            n = min(sp.get(C.FORT_PAT, 0) + _pop(sid), militia_avail)
            if n <= 0:
                return None
            return {"space": None, "selected": [sid],
                    "bulk_place": {sid: n}}
        return {"space": None, "selected": [sid], "place_one": {sid}}

    if loc is not None:
        return _kwargs_for(loc) if _legal(loc) else None

    cands = [sid for sid in state["spaces"] if _legal(sid)]
    if not cands:
        return None
    ctrl = state.get("control", {})

    def _key(sid):
        sp = state["spaces"][sid]
        units = sum(sp.get(t, 0) for t in
                    (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U))
        bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) \
            + sp.get(C.VILLAGE, 0)
        fort_build = 1 if (fort_avail and units >= 4 and bases < 2
                           and sp.get(C.FORT_PAT, 0) == 0) else 0
        lone_fort = 1 if (sp.get(C.FORT_PAT, 0) > 0 and units == 0) else 0
        changes_ctrl = 1 if (ctrl.get(sid) != "REBELLION"
                             and _rebels(sp) + 1 > _royalists(sp)) else 0
        no_active_opp = 1 if _support(state, sid) > C.ACTIVE_OPPOSITION else 0
        is_city = 1 if _stype(sid) == "City" else 0
        # §8.5.2 bullet order: Fort builds, Militia at lone Forts, then
        # Militia first to change Control, then where no Active
        # Opposition, within each first Cities then highest Pop.
        return (-fort_build, -lone_fort, -changes_ctrl, no_active_opp,
                -is_city, -_pop(sid))

    best_key = min(_key(s) for s in cands)
    pick = _rand_choice(state, [s for s in cands if _key(s) == best_key])
    return _kwargs_for(pick)


# =====================================================================
#  Free Special Activities
# =====================================================================

def plan_free_war_path(state: Dict, faction: str,
                       loc: Optional[str]) -> Optional[Dict]:
    """I8 + §4.4.2, mirroring IndianBot._war_path: target first to
    remove a Patriot Fort, then most Rebel pieces, within that first in
    a Province with 1+ Villages, then random; option per §4.4.2."""
    if faction != C.INDIANS:
        return None

    def _option_for(sid) -> Optional[int]:
        sp = state["spaces"][sid]
        if sp.get(C.WARPARTY_U, 0) == 0:
            return None
        rebel_units = sum(sp.get(t, 0) for t in _REBEL_UNIT_TAGS)
        if (sp.get(C.FORT_PAT, 0) and rebel_units == 0
                and sp.get(C.WARPARTY_U, 0) >= 2):
            return 3
        if rebel_units >= 2 and sp.get(C.WARPARTY_U, 0) >= 2:
            return 2
        if rebel_units >= 1:
            return 1
        return None

    if loc is not None:
        opt = _option_for(loc)
        return {"space": loc, "option": opt} if opt else None

    choices = []
    for sid, sp in state["spaces"].items():
        if _option_for(sid) is None:
            continue
        fort = 1 if sp.get(C.FORT_PAT, 0) else 0
        enemy = sp.get(C.FORT_PAT, 0) + sum(sp.get(t, 0)
                                            for t in _REBEL_UNIT_TAGS)
        # "Province" = Colony or Reserve (any non-City land space).
        prov_vill = 1 if (_stype(sid) in ("Colony", "Reserve")
                          and sp.get(C.VILLAGE, 0) >= 1) else 0
        choices.append(((-fort, -enemy, -prov_vill), sid))
    if not choices:
        return None
    best = min(k for k, _ in choices)
    pick = _rand_choice(state, [s for k, s in choices if k == best])
    return {"space": pick, "option": _option_for(pick)}


def plan_free_partisans(state: Dict, faction: str,
                        loc: Optional[str]) -> Optional[Dict]:
    """P8 + §4.3.2, mirroring PatriotBot._try_partisans: a space with
    Underground Militia and enemy, first to remove a Village, then most
    War Parties, then British; within each first to add most Rebel
    Control, then to remove most British Control, then random."""
    if faction != C.PATRIOTS:
        return None
    refresh_control(state)
    ctrl = state.get("control", {})

    def _option_for(sid) -> Optional[int]:
        sp = state["spaces"][sid]
        mu = sp.get(C.MILITIA_U, 0)
        if not mu:
            return None
        village = sp.get(C.VILLAGE, 0)
        wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
        # Options 1/2 remove a Royalist UNIT (Glossary §1.4 — Regulars,
        # Tories, War Parties; NOT Forts or Villages).  Counting a Fort
        # as removable made the planner pick option 1 in a Fort-only
        # space, which partisans.execute rejects (planner/executor
        # divergence, gate 1775:12).
        roy_units = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                     + sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0))
        # P8 "first to remove a Village" → option 3 where legal
        # (§4.3.2: no War Parties present, 2+ Underground Militia).
        if village and not wp and mu >= 2:
            return 3
        if roy_units == 0:
            return None                      # nothing options 1/2 can remove
        # §8.1.2 maximum extent: option 2 removes a second unit when 2+
        # Royalist units are present and 2+ Underground Militia can pay.
        if roy_units >= 2 and mu >= 2:
            return 2
        return 1

    if loc is not None:
        opt = _option_for(loc)
        return {"space": loc, "option": opt} if opt else None

    candidates = []
    for sid, sp in state["spaces"].items():
        if _option_for(sid) is None:
            continue
        has_village = sp.get(C.VILLAGE, 0)
        wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
        british = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
        adds_rebel = 1 if ctrl.get(sid) != "REBELLION" else 0
        removes_brit = 1 if ctrl.get(sid) == "BRITISH" else 0
        candidates.append(((-has_village, -wp, -british,
                            -adds_rebel, -removes_brit), sid))
    if not candidates:
        return None
    best = min(k for k, _ in candidates)
    pick = _rand_choice(state, [s for k, s in candidates if k == best])
    return {"space": pick, "option": _option_for(pick)}


# =====================================================================
#  Entry point used by Engine._drain_free_ops
# =====================================================================

_SA_PLANNERS = {
    "war_path": plan_free_war_path,
    "partisans": plan_free_partisans,
}


def plan_free_special_activity(state: Dict, faction: str, op: str,
                               loc: Optional[str]):
    """Return dispatcher kwargs for a free SA, None for a genuine
    decline, or the string 'NO_PLANNER' when the SA's selection rules
    have not been transcribed (the drain logs those distinctly)."""
    fn = _SA_PLANNERS.get(op)
    if fn is None:
        return "NO_PLANNER"
    return fn(state, faction, loc)
