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
from lod_ai.util.history import push_history
from lod_ai.util.caps import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.board.pieces      import add_piece, remove_piece
from lod_ai.economy.resources import spend, can_afford

COMMAND_NAME = "GATHER"      # auto-registered by commands/__init__.py

SUPPORT_OK = {NEUTRAL, PASSIVE_SUPPORT, PASSIVE_OPPOSITION}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _is_indian_reserve(space: Dict) -> bool:
    """Return True if this Province is an Indian Reserve."""
    # Map loader should set a boolean; adapt here if your schema differs.
    return space.get("indian_reserve", False)

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
    limited: bool = False,
) -> Dict:
    """
    Perform the Gather Command for INDIANS.

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

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(selected)
    # Default empty containers so later membership tests work
    place_one = place_one or set()
    build_village = build_village or set()
    bulk_place = bulk_place or {}
    move_plan = move_plan or []

    # ---- Validation on each selected Province --------------------------------
    free_reserve_granted = False
    for prov in selected:
        sp = state["spaces"][prov]

        # Support level gate
        support_level = state.get("support", {}).get(prov, NEUTRAL)
        if support_level not in SUPPORT_OK:
            raise ValueError(f"{prov} not at an eligible support level.")

        # One free reserve detection
        if _is_indian_reserve(sp) and not free_reserve_granted:
            free_reserve_granted = True

    # ---- Pay Resources (1 each, first reserve free) --------------------------
    _pay_cost(state, selected, free_one_reserve=free_reserve_granted)

    # ---- Track pieces that have moved this command ---------------------------
    moved_ids: Set[int] = set()

    # Push history once before any mutation
    push_history(state, f"INDIANS GATHER selected={selected}")

    # ---- Helper to access WP counts ------------------------------------------
    def _wp_total(space: Dict) -> int:
        return space.get(WARPARTY_U, 0) + space.get(WARPARTY_A, 0)

    # ---- Process each Province ------------------------------------------------
    for prov in selected:
        sp = state["spaces"][prov]

        # Action dispatch -------------------------------------------------------
        if prov in build_village:
            if _wp_total(sp) < 2:
                raise ValueError(f"{prov}: need 2 WP to build a Village.")

            base_total = sp.get(VILLAGE, 0) + sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0)
            if base_total >= 2:
                raise ValueError(f"{prov}: stacking limit reached for bases.")

            # Remove 2 War-Parties (Underground preferred)
            take_u = min(2, sp.get(WARPARTY_U, 0))
            if take_u:
                remove_piece(state, WARPARTY_U, prov, take_u)
            take_a = 2 - take_u
            if take_a:
                remove_piece(state, WARPARTY_A, prov, take_a)

            add_piece(state, VILLAGE, prov, 1)
            continue

        if prov in bulk_place:
            n = bulk_place[prov]
            villages = sp.get(VILLAGE, 0)
            if villages == 0:
                raise ValueError(f"{prov} has no Village for bulk placement.")
            if n > villages + 1:
                raise ValueError(f"{prov}: may place ≤ villages+1 WP.")
            add_piece(state, WARPARTY_U, prov, n)
            continue

        # place_one by default if in place_one or if no directive given
        if (prov in place_one) or (prov not in bulk_place and prov not in build_village):
            add_piece(state, WARPARTY_U, prov, 1)

    # ---- Handle moves (separate so we can validate duplicates) ---------------
    # Group moves by destination for later flipping
    dst_to_moves: Dict[str, List[Tuple[str, int]]] = {}
    for src, dst, n in move_plan:
        if dst not in selected:
            raise ValueError(f"Move destination {dst} not in selected Provinces.")
        if limited and dst != selected[0]:
            raise ValueError("Limited Gather: all moves must end in the single Province.")
        if not is_adjacent(src, dst):
            raise ValueError(f"{src} is not adjacent to {dst}.")
        # §3.4.1: Move-and-flip is only available "If the Province already
        # has at least one Village."
        if state["spaces"][dst].get(VILLAGE, 0) == 0:
            raise ValueError(f"{dst} has no Village; move action requires one.")
        dst_to_moves.setdefault(dst, []).append((src, n))

    # Perform movements
    for dst, moves in dst_to_moves.items():
        sp_dst = state["spaces"][dst]
        for src, n in moves:
            sp_src = state["spaces"][src]

            # Available WP in src — cap to what's actually there since
            # bot planning snapshots may over-count after village builds
            # or multi-phase interactions.
            available = sp_src.get(WARPARTY_U, 0) + sp_src.get(WARPARTY_A, 0)
            if n > available:
                n = available
            if n <= 0:
                continue

            # Move WP one by one and mark each as moved
            for _ in range(n):
                uid = id(sp_src) ^ available          # unique per remaining WP
                if uid in moved_ids:
                    raise ValueError("A War-Party is attempting to move twice.")
                moved_ids.add(uid)

                # Prefer Underground first
                if sp_src.get(WARPARTY_U, 0):
                    remove_piece(state, WARPARTY_U, src, 1)
                else:
                    remove_piece(state, WARPARTY_A, src, 1)

                add_piece(state, WARPARTY_U, dst, 1)
                available -= 1                        # update remaining count

        # After all moves into dst, flip ALL WP Underground
        sp_dst[WARPARTY_U] = _wp_total(sp_dst)
        sp_dst[WARPARTY_A] = 0

    # ---- Final bookkeeping ----------------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(f"INDIANS GATHER {selected}")
    return ctx
