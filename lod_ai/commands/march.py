"""
lod_ai.commands.march
=====================
Implements the March Command for every faction:

• BRITISH  (§3.2.3)
• PATRIOTS (§3.3.2)
• INDIANS  (§3.4.2)
• FRENCH   (§3.5.4 — Treaty-gated)

Common-Cause integration
------------------------
When `ctx["common_cause"]` is present (set by the Special-Activity
lod_ai.special_activities.common_cause), British may treat the recorded
number of War Parties in each space *as if they were Tories* for the
escort rule. These War Parties:

    • Count toward the 1-for-1 escort cap with Regulars.
    • May **not** move into a City (rule §4.2.1).
    • Arrive Active (WARPARTY_A).

Everything else remains deterministic: resource costs, adjacency
validation, history push, and global-cap checks.
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.rules_consts import (
    # cube tags
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY, MILITIA_A, MILITIA_U,
    WARPARTY_A, WARPARTY_U,
    # factions
    BRITISH, PATRIOTS, INDIANS, FRENCH,
)
from lod_ai.util.history     import push_history
from lod_ai.util.caps        import refresh_control, enforce_global_caps
from lod_ai.util.adjacency   import is_adjacent
from lod_ai.map import adjacency as map_adj
from lod_ai.leaders          import leader_location
from lod_ai.board.pieces      import remove_piece, add_piece, move_piece
from lod_ai.economy.resources import spend, can_afford               # NEW
from lod_ai.util.naval        import has_blockade
from lod_ai.util.command_checkpoint import command_checkpoint
from lod_ai.util.movement_provenance import MovementProvenance

COMMAND_NAME = "MARCH"            # auto-registered by commands/__init__.py


# ──────────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────────
def _pay_cost(
    state: Dict,
    faction: str,
    n: int,
    *,
    first_free: bool = False,
    free: bool = False,
) -> None:
    if free:
        return
    cost = n - (1 if first_free else 0)
    spend(state, faction, cost)

def _move(state: Dict,
          tag: str, n: int,
          src_id: str, dst_id: str) -> None:
    move_piece(state, tag, src_id, dst_id, n)

def _is_city(space_id: str) -> bool:
    return map_adj.space_type(space_id) == "City"


def _city_network_legal(state: Dict, faction: str, src: str, dst: str) -> bool:
    """3.2.3 / 3.5.4: British or French Regulars in or adjacent to a
    qualifying City (not Blockaded; Rebellion-Controlled for the French) may
    March to another such City, or to a Province adjacent to one.
    (British/French strategic "naval" movement between Cities.)"""
    if faction not in (BRITISH, FRENCH):
        return False

    def _qual_city(c: str) -> bool:
        if not _is_city(c) or has_blockade(state, c):
            return False
        if faction == FRENCH and state.get("control", {}).get(c) != "REBELLION":
            return False
        return True

    src_ok = _qual_city(src) or any(
        _qual_city(n) for n in map_adj.adjacent_spaces(src)
    )
    if not src_ok:
        return False
    if _qual_city(dst):
        return True
    # a Province (Colony or Reserve) adjacent to a qualifying City
    if map_adj.space_type(dst) in ("Colony", "Reserve"):
        return any(_qual_city(n) for n in map_adj.adjacent_spaces(dst))
    return False


# ──────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    sources: List[str],
    destinations: List[str],
    *,
    bring_escorts: bool = False,
    limited: bool = False,
    move_plan: List[Dict] | None = None,
    plan: List[Dict] | None = None,
    free: bool = False,
) -> Dict:
    """
    Perform a March.

    Parameters
    ----------
    sources / destinations
        List of source spaces and destination spaces.  If *limited*,
        exactly 1 destination is required.
    bring_escorts
        If True, British/French may escort Tories/Continentals
        (plus Common-Cause WP for British) 1-for-1 with Regulars.
    move_plan
        Optional structured plan `[{"src": str, "dst": str, "pieces": {tag: n}}]`
        limiting movement to exactly the counts chosen by the caller.
    plan
        Alias for *move_plan* (backwards compatibility).
    """
    if move_plan is None and plan is not None:
        move_plan = plan

    faction = faction.upper()
    # Treaty gate for French
    if faction == FRENCH and not state.get("toa_played"):
        raise ValueError("FRENCH cannot March before Treaty of Alliance.")

    def _norm_plan(plan: List[Dict]) -> List[Dict]:
        norm = []
        for entry in plan:
            if isinstance(entry, dict):
                src = entry.get("src") or entry.get("source")
                dst = entry.get("dst") or entry.get("destination")
                pieces = entry.get("pieces") or {}
            elif isinstance(entry, (list, tuple)) and len(entry) == 3:
                src, dst, pieces = entry
            else:
                raise ValueError("Invalid move_plan entry.")
            if not src or not dst or not isinstance(pieces, dict):
                raise ValueError("Move plan entries need src, dst, and pieces dict.")
            pieces = {k: int(v) for k, v in pieces.items() if int(v) > 0}
            if not pieces:
                raise ValueError("Move plan entries must move at least one piece.")
            norm.append({"src": src, "dst": dst, "pieces": pieces})
        return norm

    # §3.3.2 / §3.4.2: capture pre-move control for activation conditions
    _pre_control = dict(state.get("control", {}))
    common_cause_used: Dict[str, int] = {}
    militia_provenance = MovementProvenance(MILITIA_U, MILITIA_A)
    warparty_provenance = MovementProvenance(WARPARTY_U, WARPARTY_A)
    provenance = {MILITIA_U: militia_provenance, MILITIA_A: militia_provenance,
                  WARPARTY_U: warparty_provenance, WARPARTY_A: warparty_provenance}
    moved_cubes: Dict[str, Dict[str, int]] = {}

    def _checkpoint(label, sid):
        if not callable(ctx.get("_command_checkpoint")):
            return
        snapshots = [(p, p.snapshot(state)) for p in (militia_provenance, warparty_provenance)]
        cubes = {s: {tag: sp.get(tag, 0) for tag in (REGULAR_BRI, REGULAR_PAT, REGULAR_FRE, TORY)}
                 for s, sp in state["spaces"].items()}
        command_checkpoint(state, ctx, label, sid)
        for tracker, before in snapshots:
            tracker.reconcile_special(before, state)
        for space, tags in cubes.items():
            for tag, before in tags.items():
                removed = max(0, before - state["spaces"][space].get(tag, 0))
                if removed:
                    moved = moved_cubes.setdefault(space, {})
                    # Counters of the same type are interchangeable: removing
                    # already-moved counters preserves every legal later move.
                    moved[tag] = max(0, moved.get(tag, 0) - removed)

    def _apply_move(src: str, dst: str, pieces: Dict[str, int]) -> Dict:
        """Move pieces src→dst.  Returns tracking dict for post-move effects."""
        if not is_adjacent(src, dst) and not _city_network_legal(
            state, faction, src, dst
        ):
            raise ValueError(
                f"{src} to {dst} is not a legal March move "
                "(not adjacent and no City-network route)."
            )
        sp_src = state["spaces"][src]
        pieces = dict(pieces)
        flipped = ctx.get("_march_sa_flips", {}).get(src, {})
        for ug, active in ((MILITIA_U, MILITIA_A), (WARPARTY_U, WARPARTY_A)):
            if faction == BRITISH:  # Common Cause uses its explicit authorization below.
                break
            missing = max(0, pieces.get(ug, 0) - sp_src.get(ug, 0))
            substitute = min(missing, flipped.get(ug, 0))
            if substitute:
                pieces[ug] -= substitute
                pieces[active] = pieces.get(active, 0) + substitute
                flipped[ug] -= substitute

        sp_dst = state["spaces"][dst]

        moved_total = 0
        militia_u_moved = 0
        wp_u_moved = 0
        french_entered = False

        def _take(tag: str, count: int) -> int:
            nonlocal moved_total
            if count <= 0:
                return 0
            if sp_src.get(tag, 0) < count:
                raise ValueError(f"Not enough {tag} in {src}.")
            tracker = provenance.get(tag)
            if tracker:
                tracker.take_exact(state, src,
                                   count if tag == tracker.underground else 0,
                                   count if tag == tracker.active else 0)
            elif sp_src.get(tag, 0) - moved_cubes.get(src, {}).get(tag, 0) < count:
                raise ValueError(f"{src}: a unit cannot March more than once.")
            move_piece(state, tag, src, dst, count)
            if tracker:
                tracker.arrive(dst, count if tag == tracker.underground else 0,
                               count if tag == tracker.active else 0)
            else:
                moved = moved_cubes.setdefault(dst, {})
                moved[tag] = moved.get(tag, 0) + count
            moved_total += count
            return count

        if faction == INDIANS and _is_city(dst):
            raise ValueError("Indians cannot occupy a City space.")

        if faction == BRITISH:
            tory = pieces.get(TORY, 0)
            wp_u = pieces.get(WARPARTY_U, 0)
            wp_a = pieces.get(WARPARTY_A, 0)
            authorized = ctx.get("common_cause", {}).get(src, 0)
            if wp_u + wp_a > authorized - common_cause_used.get(src, 0):
                raise ValueError("War Parties require Common Cause authorization in their origin.")
            reg = _take(REGULAR_BRI, pieces.get(REGULAR_BRI, 0))
            if (tory or wp_u or wp_a) and not bring_escorts:
                raise ValueError("Escorts required to move Tories or War Parties.")
            escort_cap = reg
            if tory + wp_u + wp_a > escort_cap:
                raise ValueError("Escort cap exceeded for British March.")
            if tory:
                _take(TORY, tory)
            if wp_u or wp_a:
                if _is_city(dst):
                    raise ValueError("Common-Cause War Parties may not move into Cities.")
                # Common Cause already Activates its selected War Parties.
                # A during-Command SA can have flipped them since the human
                # wrote the movement plan, so use the authorized Active pool.
                _take(WARPARTY_A, wp_u + wp_a)
                common_cause_used[src] = common_cause_used.get(src, 0) + wp_u + wp_a

        elif faction == PATRIOTS:
            # §3.3.2: move Militia, Continentals and French Regulars.
            # Militia keep their Active/Underground status during movement;
            # activation is conditional (see post-move effects).
            reg = _take(REGULAR_PAT, pieces.get(REGULAR_PAT, 0))
            mil_u = pieces.get(MILITIA_U, 0)
            mil_a = pieces.get(MILITIA_A, 0)
            if mil_u:
                _take(MILITIA_U, mil_u)
                militia_u_moved += mil_u
            if mil_a:
                _take(MILITIA_A, mil_a)
            # §3.3.2: French Regulars may accompany Continentals 1 for 1
            if bring_escorts:
                fr = pieces.get(REGULAR_FRE, 0)
                if fr > reg:
                    raise ValueError("French escort exceeds Continental column.")
                if fr:
                    _take(REGULAR_FRE, fr)
                    french_entered = True

        elif faction == INDIANS:
            # §3.4.2: War Parties keep Underground/Active status during
            # movement; activation is conditional (see post-move effects).
            wp_u = pieces.get(WARPARTY_U, 0)
            wp_a = pieces.get(WARPARTY_A, 0)
            if wp_u:
                _take(WARPARTY_U, wp_u)
                wp_u_moved += wp_u
            if wp_a:
                _take(WARPARTY_A, wp_a)

        elif faction == FRENCH:
            reg = _take(REGULAR_FRE, pieces.get(REGULAR_FRE, 0))
            if bring_escorts:
                pat = pieces.get(REGULAR_PAT, 0)
                if pat > reg:
                    raise ValueError("Continental escort exceeds French column.")
                if pat:
                    _take(REGULAR_PAT, pat)

        return {
            "total": moved_total,
            "militia_u": militia_u_moved,
            "wp_u": wp_u_moved,
            "french_entered": french_entered,
        }

    if move_plan:
        plan = _norm_plan(move_plan)
        destinations_set = {p["dst"] for p in plan}
        sources_set = {p["src"] for p in plan}
    else:
        destinations_set = set(destinations)
        sources_set = set(sources)
        plan = []
        for src in sources:
            sp_src = state["spaces"][src]
            base_pieces = {}
            if faction == BRITISH:
                base_pieces[REGULAR_BRI] = sp_src.get(REGULAR_BRI, 0)
                if bring_escorts:
                    base_pieces[TORY] = min(base_pieces[REGULAR_BRI], sp_src.get(TORY, 0))
                    cc_avail = ctx.get("common_cause", {}).get(src, 0)
                    base_pieces[WARPARTY_A] = min(base_pieces[REGULAR_BRI] - base_pieces.get(TORY, 0), cc_avail)
            elif faction == PATRIOTS:
                # §3.3.2: Patriot March moves Militia, Continentals and
                # French Regulars.  War Parties are NOT part of Patriot March.
                base_pieces[REGULAR_PAT] = sp_src.get(REGULAR_PAT, 0)
                base_pieces[MILITIA_U] = sp_src.get(MILITIA_U, 0)
                base_pieces[MILITIA_A] = sp_src.get(MILITIA_A, 0)
                if bring_escorts:
                    base_pieces[REGULAR_FRE] = min(base_pieces.get(REGULAR_PAT, 0), sp_src.get(REGULAR_FRE, 0))
            elif faction == INDIANS:
                base_pieces[WARPARTY_U] = sp_src.get(WARPARTY_U, 0)
                base_pieces[WARPARTY_A] = sp_src.get(WARPARTY_A, 0)
            elif faction == FRENCH:
                base_pieces[REGULAR_FRE] = sp_src.get(REGULAR_FRE, 0)
                if bring_escorts:
                    base_pieces[REGULAR_PAT] = min(base_pieces.get(REGULAR_FRE, 0), sp_src.get(REGULAR_PAT, 0))
            cleaned = {k: v for k, v in base_pieces.items() if v > 0}
            if not cleaned:
                continue
            for dst in destinations:
                plan.append({"src": src, "dst": dst, "pieces": cleaned})

    # Limited-command constraints
    if limited and len(destinations_set) != 1:
        raise ValueError("Limited March must end in a single destination.")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(destinations_set)
    state["_turn_march_sources"] = set(sources_set)
    ctx["_planned_command"] = COMMAND_NAME
    ctx["_command_selected_spaces"] = set(destinations_set)
    interactive = callable(ctx.get("_command_checkpoint"))

    # §3.3.2 / §3.5.4: Escorts (French Regulars accompanying a Patriot March,
    # or Continentals accompanying a French March) are optional and require the
    # ally to pay 1 Resource per destination entered. Validate affordability
    # BEFORE any pieces move so an escort can never happen for free and so the
    # command never mutates state and then fails.
    if not free and not interactive:
        if faction == FRENCH:
            cont_dsts = {p["dst"] for p in plan
                         if p["pieces"].get(REGULAR_PAT, 0) > 0}
            if cont_dsts and not can_afford(state, PATRIOTS, len(cont_dsts)):
                raise ValueError(
                    "Patriots cannot pay the Continental escort fee "
                    f"({len(cont_dsts)} Resource(s) required)."
                )
        elif faction == PATRIOTS:
            _roch = leader_location(state, "LEADER_ROCHAMBEAU")
            fre_dsts = {p["dst"] for p in plan
                        if p["pieces"].get(REGULAR_FRE, 0) > 0 and p["dst"] != _roch}
            if fre_dsts and not can_afford(state, FRENCH, len(fre_dsts)):
                raise ValueError(
                    "French cannot pay the escort fee "
                    f"({len(fre_dsts)} Resource(s) required)."
                )
    # Resource payment
    first_free = (faction == INDIANS) and ctx.get("all_reserve_origin", False)
    if not interactive:
        _pay_cost(state, faction, len(destinations_set), first_free=first_free, free=free)

    # §3.5.4: French March escort billing deferred to after moves execute
    # (see post-move section below)

    # Leader hooks (placeholder for future modifiers)

    push_history(
        state,
        f"{faction} MARCH begins: {sources} ➜ {destinations} (escorts={bring_escorts})"
    )

    def _flip(sp: Dict, from_tag: str, to_tag: str, n: int) -> int:
        actual = min(n, sp.get(from_tag, 0))
        if actual:
            sp[from_tag] = sp.get(from_tag, 0) - actual
            sp[to_tag] = sp.get(to_tag, 0) + actual
        return actual

    def _finish_destination(dst: str, groups: list) -> None:
        """Apply mandatory moving-group facing before another SA decision."""
        sp = state["spaces"][dst]
        if faction == PATRIOTS:
            _flip(sp, WARPARTY_U, WARPARTY_A, sp.get(REGULAR_PAT, 0) // 2)
            if _is_city(dst) and _pre_control.get(dst) == BRITISH:
                cubes = sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)
                for group in groups:
                    if group["total"] + cubes > 3:
                        n = _flip(sp, MILITIA_U, MILITIA_A, group["militia_u"])
                        militia_provenance.activate_moved(dst, n)
        elif faction == INDIANS:
            if map_adj.space_type(dst) == "Colony" and _pre_control.get(dst) == "REBELLION":
                militia = sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0)
                for group in groups:
                    if group["total"] + militia > 3:
                        n = _flip(sp, WARPARTY_U, WARPARTY_A, group["wp_u"])
                        warparty_provenance.activate_moved(dst, n)

    # ── Execute moves and collect tracking data ──────────────────────────
    moved_overall = 0
    # Per-destination tracking for post-move effects
    dst_groups: Dict[str, list] = {}   # dst → list of tracking dicts
    french_entered_dsts: set = set()

    continental_entered_dsts: set = set()

    for index, dst in enumerate(dict.fromkeys(entry["dst"] for entry in plan)):
        _checkpoint("Before March destination", dst)
        entries = [entry for entry in plan if entry["dst"] == dst]
        if interactive:
            _pre_control[dst] = state.get("control", {}).get(dst)
            _pay_cost(state, faction, 1, first_free=first_free and index == 0, free=free)
            if faction == FRENCH and not free and any(
                    p["pieces"].get(REGULAR_PAT, 0) for p in entries):
                spend(state, PATRIOTS, 1)
            if faction == PATRIOTS and not free and any(
                    p["pieces"].get(REGULAR_FRE, 0) for p in entries):
                if dst != leader_location(state, "LEADER_ROCHAMBEAU"):
                    spend(state, FRENCH, 1)
        for entry in entries:
            info = _apply_move(entry["src"], entry["dst"], entry["pieces"])
            moved_overall += info["total"]
            dst_groups.setdefault(entry["dst"], []).append(info)
            if info.get("french_entered"):
                french_entered_dsts.add(entry["dst"])
            if faction == FRENCH and entry["pieces"].get(REGULAR_PAT, 0) > 0:
                continental_entered_dsts.add(entry["dst"])
        _finish_destination(dst, dst_groups.get(dst, []))
        _checkpoint("After moving to March destination", dst)

    if moved_overall <= 0:
        raise ValueError("March must move at least one piece.")

    # §3.5.4: French March — Patriots also pay 1 Resource per destination
    # that Continental escorts enter.
    if faction == FRENCH and continental_entered_dsts and not free and not interactive:
        # Affordability pre-validated above; escorts never move for free.
        spend(state, PATRIOTS, len(continental_entered_dsts))

    # §3.3.2: Patriot March — French also pay 1 Resource per destination
    # that French Regulars enter.
    # Rochambeau capability (leader_capabilities.txt): "French may March
    # and Battle with a Patriot Command at no Resource cost."  Waive the
    # French fee for any destination where Rochambeau is present.
    if faction == PATRIOTS and french_entered_dsts and not free and not interactive:
        rochambeau_loc = leader_location(state, "LEADER_ROCHAMBEAU")
        chargeable = [d for d in french_entered_dsts if d != rochambeau_loc]
        if chargeable:
            spend(state, FRENCH, len(chargeable))

    if faction == BRITISH:
        # British locating is a separate "Then" step after all movements.
        for dst in dict.fromkeys(entry["dst"] for entry in plan):
            _checkpoint("Before March Militia activation", dst)
            sp = state["spaces"][dst]
            _flip(sp, MILITIA_U, MILITIA_A,
                  (sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)) // 3)

    refresh_control(state)
    enforce_global_caps(state)

    # Log summary
    state.setdefault("log", []).append(
        f"{faction} MARCH {sources} ➜ {destinations_set} (escorts={bring_escorts})"
    )
    return ctx
