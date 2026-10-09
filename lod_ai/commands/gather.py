"""
lod_ai.commands.gather
======================
Indian **Gather** Command (§3.4.1).

* Faction: INDIANS only.
* Select Provinces at NEUTRAL, PASSIVE SUPPORT or PASSIVE OPPOSITION
  (not Active Support/Opposition).
* Cost: 1 Resource per selected Province **except** the *first* Indian-Reserve
  Province, which is free.
* Per selected Province, caller must choose **exactly one** of:
    1. place_one            – add 1 War-Party (Underground).
    2. build_village        – replace 2 War-Parties with 1 Village.
    3. bulk_place[n]        – add n War-Parties, n ≤ villages + 1.
    4. move_plan            – move WP in from adjacencies, then flip ALL WP
                              there Underground.  No WP may move twice.
If `limited=True`, every action must target the single Province in *selected*.

The function returns the unchanged *ctx* dict so caller chaining stays uniform.
"""

from __future__ import annotations
from typing import Dict, List, Set, Tuple

from lod_ai.rules_consts import (
    # piece & marker tags
    WARPARTY_U, WARPARTY_A, VILLAGE, FORT_BRI, FORT_PAT,
    # support enums
    ACTIVE_SUPPORT, ACTIVE_OPPOSITION,
    PASSIVE_SUPPORT, PASSIVE_OPPOSITION, NEUTRAL,
    # factions
    INDIANS,
)
from lod_ai.util.command_checkpoint import command_checkpoint
from lod_ai.util.movement_provenance import MovementProvenance
from lod_ai.util.history import push_history
from lod_ai.util.caps import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.map.adjacency    import space_type as _space_type
from lod_ai.board.pieces      import add_piece, remove_piece
from lod_ai.economy.resources import spend, can_afford
from lod_ai.leaders          import leader_location

COMMAND_NAME = "GATHER"      # auto-registered by commands/__init__.py

SUPPORT_OK = {NEUTRAL, PASSIVE_SUPPORT, PASSIVE_OPPOSITION}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _is_indian_reserve(space_id: str) -> bool:
    """Return True if this Province is an Indian Reserve."""
    return _space_type(space_id) == "Reserve"

def _pay_cost(state: Dict, selected: List[str], free_one_reserve: bool) -> None:
    cost = len(selected) - (1 if free_one_reserve else 0)
    spend(state, INDIANS, cost)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    selected: List[str],
    *,
    place_one: Set[str] | None = None,
    build_village: Set[str] | None = None,
    bulk_place: Dict[str, int] | None = None,
    move_plan: List[Tuple[str, str, int]] | None = None,
    move_active_first: bool = False,
    limited: bool = False,
) -> Dict:
    """
    Perform the Gather Command for INDIANS.

    ``move_active_first`` selects Active War Parties before Underground
    among eligible unmoved units, as required by non-player regrouping.

    Parameters
    ----------
    selected
        List of Province IDs chosen for the Command.
    place_one
        Provinces (subset of *selected*) receiving exactly 1 War-Party.
    build_village
        Provinces where 2 War-Parties will be swapped for 1 Village.
    bulk_place
        Mapping {province: n} to place *n* War-Parties (requires ≥1 Village
        and n ≤ villages + 1).
    move_plan
        List of (src_id, dst_id, n) movements.  Each dst must be in *selected*
        and inside *move_plan* only one per src→dst pair.  After moves, ALL
        War-Parties in each dst are flipped Underground.
    limited
        True = Limited Command; every action must pertain to the single
        Province in *selected*.
    """
    if faction != INDIANS:
        raise ValueError("Only INDIANS may execute Gather.")

    if limited and len(set(selected)) != 1:
        raise ValueError("Limited Gather must target exactly one Province.")

    # Default empty containers so later membership tests work
    place_one = place_one or set()
    build_village = build_village or set()
    bulk_place = bulk_place or {}
    move_plan = move_plan or []

    # ---- Validation on each selected Province --------------------------------
    free_reserve_granted = False
    for prov in selected:
        if _space_type(prov) not in ("Colony", "Reserve"):
            raise ValueError(f"{prov} is not a Province; Gather selects Provinces only.")
        sp = state["spaces"][prov]

        # Support level gate
        support_level = state.get("support", {}).get(prov, NEUTRAL)
        if support_level not in SUPPORT_OK:
            raise ValueError(f"{prov} not at an eligible support level.")

        # One free reserve detection
        if _is_indian_reserve(prov) and not free_reserve_granted:
            free_reserve_granted = True

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(selected)

    ctx["_planned_command"] = COMMAND_NAME
    ctx["_command_selected_spaces"] = set(selected)
    interleaved = callable(ctx.get("_command_checkpoint"))
    if not interleaved:
        _pay_cost(state, selected, free_one_reserve=free_reserve_granted)
    push_history(state, f"INDIANS GATHER selected={selected}")

    moves_by_dest: dict[str, list[tuple[str, int]]] = {}
    for src, dst, n in move_plan:
        if dst not in selected:
            raise ValueError(f"Move destination {dst} not in selected Provinces.")
        if src != dst and not is_adjacent(src, dst):
            raise ValueError(f"{src} is not adjacent to {dst}.")
        if src == dst and n:
            raise ValueError("War Parties may only move from adjacent Provinces.")
        moves_by_dest.setdefault(dst, []).append((src, n))
    provenance = MovementProvenance(WARPARTY_U, WARPARTY_A)
    reserve_used = False
    for prov in selected:
        before_special = provenance.snapshot(state)
        command_checkpoint(state, ctx, "Before resolving Gather", prov)
        provenance.reconcile_special(before_special, state)
        if interleaved:
            free_here = _is_indian_reserve(prov) and not reserve_used
            spend(state, INDIANS, 0 if free_here else 1)
            reserve_used = reserve_used or free_here
        sp = state["spaces"][prov]
        if prov in build_village:
            village_cost = 1 if leader_location(state, "LEADER_CORNPLANTER") == prov else 2
            if sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0) < village_cost:
                raise ValueError(f"{prov}: need {village_cost} WP to build a Village.")
            if sp.get(VILLAGE, 0) + sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0) >= 2:
                raise ValueError(f"{prov}: stacking limit reached for bases.")
            take_u = min(village_cost, sp.get(WARPARTY_U, 0))
            if take_u:
                remove_piece(state, WARPARTY_U, prov, take_u)
            if village_cost > take_u:
                remove_piece(state, WARPARTY_A, prov, village_cost - take_u)
            add_piece(state, VILLAGE, prov, 1)
        elif prov in moves_by_dest:
            # Move-and-hide is an ALTERNATIVE to placement (§3.4.1).
            if not sp.get(VILLAGE, 0):
                raise ValueError(f"{prov} has no Village; move action requires one.")
            for src, n in moves_by_dest[prov]:
                if n < 0:
                    raise ValueError("Cannot move a negative number of War Parties.")
                if src == prov:
                    continue  # zero movers still permits hiding in place
                source = state["spaces"][src]
                movable = provenance.movable(state, src)
                # Bots may have budgeted against an earlier placement phase.
                if interleaved and n > movable:
                    raise ValueError(f"{src}: not enough unmoved War Parties.")
                n = min(n, movable)
                take_u, take_a = provenance.take(
                    state, src, n, active_first=move_active_first)
                if take_u:
                    remove_piece(state, WARPARTY_U, src, take_u)
                if n > take_u:
                    remove_piece(state, WARPARTY_A, src, n - take_u)
                if n:
                    add_piece(state, WARPARTY_U, prov, n)
                provenance.arrive_and_hide(prov, n)
            provenance.arrive_and_hide(prov, 0)
            sp[WARPARTY_U] = sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0)
            sp[WARPARTY_A] = 0
        elif prov in bulk_place:
            n = bulk_place[prov]
            villages = sp.get(VILLAGE, 0)
            if not villages:
                raise ValueError(f"{prov} has no Village for bulk placement.")
            if not 0 <= n <= villages + 1:
                raise ValueError(f"{prov}: may place at most villages+1 WP.")
            add_piece(state, WARPARTY_U, prov, n)
        else:
            add_piece(state, WARPARTY_U, prov, 1)

    # ---- Final bookkeeping ----------------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(f"INDIANS GATHER {selected}")
    return ctx
