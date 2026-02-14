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
from lod_ai.leaders          import apply_leader_modifiers
from lod_ai.board.pieces      import remove_piece, add_piece          # NEW
from lod_ai.economy.resources import spend, can_afford               # NEW

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
    remove_piece(state, tag, src_id, n)
    add_piece(state,    tag, dst_id, n)

def _is_city(space_id: str) -> bool:
    return map_adj.space_type(space_id) == "City"


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

    def _apply_move(src: str, dst: str, pieces: Dict[str, int]) -> Dict:
        """Move pieces src→dst.  Returns tracking dict for post-move effects."""
        if not is_adjacent(src, dst):
            raise ValueError(f"{src} is not adjacent to {dst}.")
        sp_src = state["spaces"][src]
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
            remove_piece(state, tag, src, count)
            add_piece(state, tag, dst, count)
            moved_total += count
            return count

        if faction == INDIANS and _is_city(dst):
            raise ValueError("Indians cannot occupy a City space.")

        if faction == BRITISH:
            reg = _take(REGULAR_BRI, pieces.get(REGULAR_BRI, 0))
            tory = pieces.get(TORY, 0)
            wp_u = pieces.get(WARPARTY_U, 0)
            wp_a = pieces.get(WARPARTY_A, 0)
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
                if wp_u:
                    _take(WARPARTY_U, wp_u)
                    # Common-Cause WP arrive Active (§4.2.1)
                    sp_dst[WARPARTY_U] = sp_dst.get(WARPARTY_U, 0) - wp_u
                    sp_dst[WARPARTY_A] = sp_dst.get(WARPARTY_A, 0) + wp_u
                if wp_a:
                    _take(WARPARTY_A, wp_a)

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
                    base_pieces[WARPARTY_A] = min(base_pieces[REGULAR_BRI] - base_pieces.get(TORY, 0, 0), cc_avail)
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
    # Resource payment
    first_free = (faction == INDIANS) and ctx.get("all_reserve_origin", False)
    _pay_cost(state, faction, len(destinations_set), first_free=first_free, free=free)

    # §3.5.4: French March with Continental escorts → Patriots also pay per
    # destination that Continentals enter.
    if faction == FRENCH and bring_escorts:
        fee = len(destinations_set)
        spend(state, PATRIOTS, fee)

    # Leader hooks (placeholder for future modifiers)
    ctx = apply_leader_modifiers(state, faction, "pre_march", ctx)

    push_history(
        state,
        f"{faction} MARCH begins: {sources} ➜ {destinations} (escorts={bring_escorts})"
    )

    # ── Execute moves and collect tracking data ──────────────────────────
    moved_overall = 0
    # Per-destination tracking for post-move effects
    dst_groups: Dict[str, list] = {}   # dst → list of tracking dicts
    french_entered_dsts: set = set()

    for entry in plan:
        info = _apply_move(entry["src"], entry["dst"], entry["pieces"])
        moved_overall += info["total"]
        dst_groups.setdefault(entry["dst"], []).append(info)
        if info.get("french_entered"):
            french_entered_dsts.add(entry["dst"])

    if moved_overall <= 0:
        raise ValueError("March must move at least one piece.")

    # §3.3.2: Patriot March — French also pay 1 Resource per destination
    # that French Regulars enter.
    if faction == PATRIOTS and french_entered_dsts and not free:
        spend(state, FRENCH, len(french_entered_dsts))

    # ── Post-move activation effects ─────────────────────────────────────
    # NOTE: Flipping pieces between Active/Underground uses direct dict
    # manipulation because the pool system doesn't support tag changes.
    def _flip(sp: Dict, from_tag: str, to_tag: str, n: int) -> None:
        """Flip *n* pieces from *from_tag* to *to_tag* within a space."""
        actual = min(n, sp.get(from_tag, 0))
        if actual:
            sp[from_tag] = sp.get(from_tag, 0) - actual
            sp[to_tag] = sp.get(to_tag, 0) + actual

    if faction == BRITISH:
        # §3.2.3: "Activate one Militia for every three British cubes
        # there (whether they just moved or were already there)."
        for dst in destinations_set:
            sp_dst = state["spaces"][dst]
            brit_cubes = sp_dst.get(REGULAR_BRI, 0) + sp_dst.get(TORY, 0)
            flips = min(brit_cubes // 3, sp_dst.get(MILITIA_U, 0))
            _flip(sp_dst, MILITIA_U, MILITIA_A, flips)

    elif faction == PATRIOTS:
        for dst, groups in dst_groups.items():
            sp_dst = state["spaces"][dst]
            # §3.3.2: "Activate one War Party for every two Continentals
            # in the destination space."
            continentals = sp_dst.get(REGULAR_PAT, 0)
            wp_flips = min(continentals // 2, sp_dst.get(WARPARTY_U, 0))
            _flip(sp_dst, WARPARTY_U, WARPARTY_A, wp_flips)
            # §3.3.2: "Set Militia of a moving group to Active if:
            #   • The destination is a British Controlled City before the
            #     move, and
            #   • The moving group's number of units plus the number of
            #     British cubes in the destination space exceeds 3."
            is_brit_city = (
                _is_city(dst)
                and _pre_control.get(dst) == BRITISH
            )
            if is_brit_city:
                brit_cubes_in_dst = sp_dst.get(REGULAR_BRI, 0) + sp_dst.get(TORY, 0)
                for grp in groups:
                    if grp["total"] + brit_cubes_in_dst > 3:
                        mil_to_flip = min(grp["militia_u"], sp_dst.get(MILITIA_U, 0))
                        _flip(sp_dst, MILITIA_U, MILITIA_A, mil_to_flip)

    elif faction == INDIANS:
        for dst, groups in dst_groups.items():
            sp_dst = state["spaces"][dst]
            # §3.4.2: "Set Underground War Parties moving to Active if:
            #   • The destination space is a Colony Controlled by the
            #     Rebellion before the move, and
            #   • The moving group's number of pieces plus the number of
            #     Militia in the destination Province exceed 3."
            is_reb_colony = (
                sp_dst.get("type") == "Colony"
                and _pre_control.get(dst) == "REBELLION"
            )
            if is_reb_colony:
                mil_in_dst = sp_dst.get(MILITIA_U, 0) + sp_dst.get(MILITIA_A, 0)
                for grp in groups:
                    if grp["total"] + mil_in_dst > 3:
                        wp_to_flip = min(grp["wp_u"], sp_dst.get(WARPARTY_U, 0))
                        _flip(sp_dst, WARPARTY_U, WARPARTY_A, wp_to_flip)

    refresh_control(state)
    enforce_global_caps(state)

    # Log summary
    state.setdefault("log", []).append(
        f"{faction} MARCH {sources} ➜ {destinations_set} (escorts={bring_escorts})"
    )
    return ctx
