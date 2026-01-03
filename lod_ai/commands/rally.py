from __future__ import annotations
"""lod_ai.commands.rally
========================================================
Patriot **Rally** Command implementation (§3.3.1, Living Rules Aug‑2016).
Only available to the PATRIOTS faction.

This module follows the same deterministic‑procedural design as *march.py*
and *muster.py*.  All constants come from ``lod_ai.rules_consts`` and no web
lookup occurs.  The caller specifies *exactly* which sub‑action each selected
space performs; no AI decisions are made here.

Public API
----------
``execute(state, faction, ctx, selected, *,
         place_one: set[str] | None = None,
         build_fort: set[str] | None = None,
         bulk_place: dict[str, int] | None = None,
         move_plan: list[tuple[str, str, int]] | None = None,
         promote_space: str | None = None,
         limited: bool = False) -> dict``

Parameters
~~~~~~~~~~
* **selected** – list of Rally spaces (IDs). Must not have *Active Support*.
* **place_one** – subset of *selected* where exactly 1 Militia is added.
  (Defaults to every selected space not referenced elsewhere.)
* **build_fort** – subset of *selected* where 2 Patriot units are replaced
  by 1 Fort (space must *not* already have a Patriot Fort).
* **bulk_place** – mapping ``space_id ↦ n`` for spaces that *already have* ≥1
  Patriot Fort. Ensures ``n ≤ (#Fort + population)``.
* **move_plan** – list of ``(src, dst, n)`` moves of Militia between *adjacent*
  spaces. Every *dst* must be in *selected* and have ≥1 Patriot Fort. After
  all moves, **every** Militia in each destination Rally space flips
  *Underground*.
* **promote_space** – optional space (must be in *selected* and have ≥1 Fort)
  where any number of Militia are replaced 1‑for‑1 with Continentals.
* **limited** – If *True*, the Command is Limited (§2.3.5): all effects must
  involve the **same destination space**. Enforcement mirrors *march.py*.

Notes & Guarantees
------------------
* A single Militia cube never moves more than once (tracked in `moved` set).
* Militia cannot be placed in the West Indies nor in *Indian Reserve* spaces.
* Resource cost is ``1 × len(selected)``, paid up‑front.
* The routine calls `push_history` **once**, before any mutation.
* Finishes with `refresh_control` and `enforce_global_caps` like other
  commands, and appends a log entry to ``state["log"]``.

Example
~~~~~~~
```python
rally.execute(
    state, "PATRIOTS", {},
    ["Boston", "Lexington"],
    build_fort={"Lexington"},
    bulk_place={"Boston": 3},
    move_plan=[("Concord", "Boston", 2)],
    promote_space="Boston",
)
```
"""
from typing import Dict, List, Set, Tuple

from lod_ai.rules_consts import (
    ACTIVE_SUPPORT, PASSIVE_SUPPORT, NEUTRAL, PASSIVE_OPPOSITION,
    REGULAR_PAT, MILITIA_A, MILITIA_U, FORT_PAT, FORT_BRI, VILLAGE,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.board.pieces      import add_piece, remove_piece          # NEW
from lod_ai.economy.resources import spend, can_afford               # NEW

COMMAND_NAME = "RALLY"  # auto‑registered by commands/__init__.py

# ---------------------------------------------------------------------------
# Internal helpers                                                            
# ---------------------------------------------------------------------------

def _support_value(state: Dict, space_id: str) -> int:
    """Return numeric support level using constants from rules_consts."""
    return state.get("support", {}).get(space_id, NEUTRAL)


def _is_indian_reserve(sp: Dict) -> bool:
    return sp.get("indian_reserve", False)


def _is_west_indies(space_id: str) -> bool:
    return space_id == "West_Indies"  # canonical ID in map.json


def _place_militia(state: Dict, space_id: str, n: int = 1) -> None:
    """
    Add *n* Underground Militia to *space_id* using the centralized
    add_piece helper (which pulls from the pool and checks caps).
    """
    add_piece(state, MILITIA_U, space_id, n)

def _replace_with_fort(state: Dict, space_id: str):
    """
    Replace any 2 Patriot pieces in *space_id* with 1 Fort,
    using centralized helpers.
    Priority for removal: Underground → Active → Continentals.
    """
    sp = state["spaces"][space_id]
    base_total = sp.get(FORT_PAT, 0) + sp.get(FORT_BRI, 0) + sp.get(VILLAGE, 0)
    if base_total >= 2:
        raise ValueError("Cannot build Fort; stacking limit reached.")

    tags_priority = (MILITIA_U, MILITIA_A, REGULAR_PAT)
    removed = 0
    for tag in tags_priority:
        avail = sp.get(tag, 0)
        if avail == 0:
            continue
        take = min(2 - removed, avail)
        remove_piece(state, tag, space_id, take)
        removed += take
        if removed == 2:
            break

    if removed < 2:
        raise ValueError("Need at least 2 Patriot units to build Fort.")

    add_piece(state, FORT_PAT, space_id, 1)

def _move_militia(state: Dict,
                  src_id: str, dst_id: str,
                  n: int) -> None:
    """
    Move *n* Militia (any mix, prioritise Underground) from src to dst.
    All arrive Underground.
    """
    src = state["spaces"][src_id]

    n_u = min(n, src.get(MILITIA_U, 0))
    n_a = n - n_u
    if src.get(MILITIA_A, 0) < n_a:
        raise ValueError("Not enough Militia to move from src.")

    if n_u:
        remove_piece(state, MILITIA_U, src_id, n_u)
        add_piece(state,    MILITIA_U, dst_id, n_u)
    if n_a:
        remove_piece(state, MILITIA_A, src_id, n_a)
        add_piece(state,    MILITIA_U, dst_id, n_a)   # Active flip Underground

def _mid_rally_persuasion(state: Dict) -> None:
    """
    If Patriot Resources hit 0 during Rally, trigger Persuasion in up to
    three eligible spaces (Rebellion Control + Underground Militia).
    Preference: Patriot Fort present, then higher population.
    """
    from lod_ai.special_activities import persuasion

    candidates = []
    for sid, sp in state.get("spaces", {}).items():
        if state.get("control", {}).get(sid) != "REBELLION":
            continue
        if sp.get(MILITIA_U, 0) <= 0:
            continue
        has_fort = sp.get(FORT_PAT, 0) > 0
        pop = sp.get("population", 0)
        candidates.append((-int(has_fort), -pop, sid))

    if not candidates:
        return

    candidates.sort()
    spaces = [sid for *_, sid in candidates[:3]]
    persuasion.execute(state, "PATRIOTS", {}, spaces=spaces)


# ---------------------------------------------------------------------------
# Public entry point                                                          
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    selected: List[str],
    *,
    place_one: Set[str] | None = None,
    build_fort: Set[str] | None = None,
    bulk_place: Dict[str, int] | None = None,
    move_plan: List[Tuple[str, str, int]] | None = None,
    promote_space: str | None = None,
    limited: bool = False,
) -> Dict:
    """Perform the Patriot Rally command as directed by the caller."""
    if faction != "PATRIOTS":
        raise ValueError("Only PATRIOTS may Rally.")

    # Default buckets
    place_one = place_one or set()
    build_fort = build_fort or set()
    bulk_place = bulk_place or {}
    move_plan = move_plan or []

    # --- Limited‑command constraint ----------------------------------
    if limited:
        if not selected:
            raise ValueError("Limited Rally needs at least one selected space.")
        dest = selected[0]
        if any(sp != dest for sp in selected):
            raise ValueError("All selected spaces must be the same in Limited Rally.")
        if any(dst != dest for _, dst, _ in move_plan):
            raise ValueError("All moves must end in the destination space for Limited Rally.")
        if promote_space and promote_space != dest:
            raise ValueError("Promotion must occur in the destination space for Limited Rally.")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(selected)
    # --- Cost payment -------------------------------------------------
    cost = len(selected)
    spend(state, "PATRIOTS", cost)
    if state["resources"].get("PATRIOTS", 0) == 0:
        _mid_rally_persuasion(state)

    push_history(state, f"PATRIOTS RALLY selected={selected}")

    moved_militia: Set[Tuple[str, str]] = set()  # (src_id, dst_id)

    # Preload West Indies / reserve flags for validation
    for space_id in selected:
        if _support_value(state, space_id) == ACTIVE_SUPPORT:
            raise ValueError(f"{space_id} has Active Support; cannot Rally there.")

    # --- Phase 1: apply per‑space actions -----------------------------------
    for space_id in selected:
        sp = state["spaces"][space_id]
        pop = sp.get("population", 0)
        forts = sp.get(FORT_PAT, 0)

        if space_id in build_fort:
            if forts > 0:
                raise ValueError("Cannot build Fort where one already exists.")
            _replace_with_fort(state, space_id)
            forts += 1  # update local var so next checks see it
            continue  # no militia placement after fort‑build

        if forts == 0:
            # No fort yet → either place 1 militia or error
            if space_id not in place_one and space_id not in bulk_place:
                place_one.add(space_id)  # default action

        # If space has ≥1 Fort, branch between bulk_place or move action

    # Place‑one actions (after possible auto‑fill)
    for space_id in place_one:
        if space_id in build_fort or space_id in bulk_place:
            continue
        sp = state["spaces"][space_id]
        if _is_indian_reserve(sp) or _is_west_indies(space_id):
            raise ValueError("Cannot place Militia in Indian Reserve or West Indies.")
        _place_militia(state, space_id, 1)

    # Bulk placement in fort spaces
    for space_id, n in bulk_place.items():
        sp = state["spaces"][space_id]
        forts = sp.get(FORT_PAT, 0)
        if forts == 0:
            raise ValueError("Bulk placement requires an existing Fort.")
        max_n = forts + sp.get("population", 0)
        if n > max_n:
            raise ValueError(f"Cannot place {n} Militia in {space_id}; limit is {max_n}.")
        if _is_indian_reserve(sp) or _is_west_indies(space_id):
            raise ValueError("Cannot place Militia in Indian Reserve or West Indies.")
        _place_militia(state, space_id, n)

    # Move‑plan execution
    for src_id, dst_id, n in move_plan:
        if n <= 0:
            continue
        if (src_id, dst_id) in moved_militia:
            raise ValueError("Cannot move from the same src to dst twice.")
        if dst_id not in selected:
            raise ValueError("Destination must be one of the Rally spaces selected.")
        dst_sp = state["spaces"][dst_id]
        if dst_sp.get(FORT_PAT, 0) == 0:
            raise ValueError("Destination must have a Fort for move action.")
        if not is_adjacent(src_id, dst_id):
            raise ValueError(f"{src_id} not adjacent to {dst_id}.")
        src_sp = state["spaces"][src_id]
        _move_militia(state, src_id, dst_id, n)
        moved_militia.add((src_id, dst_id))

    # Flip all militia in destinations of move_plan Underground
    for _, dst_id, _ in move_plan:
        dst = state["spaces"][dst_id]
        moved = dst.get(MILITIA_A, 0)
        if moved:
            dst[MILITIA_U] = dst.get(MILITIA_U, 0) + moved
            dst[MILITIA_A] = 0

    # --- Promotion (Continentals) -----------------------------------------
    if promote_space:
        if promote_space not in selected:
            raise ValueError("Promote space must be among Rally spaces.")
        sp  = state["spaces"][promote_space]
        if sp.get(FORT_PAT, 0) == 0:
            raise ValueError("Promotion space must have a Fort.")

        avail_cont = state["available"].get(REGULAR_PAT, 0)
        militia_tot = sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0)
        promote_n = min(militia_tot, avail_cont)
        if promote_n == 0:
            raise ValueError("No Militia to promote or no Continentals available.")

        # Remove Militia (Active first), add Continentals
        remove_first = min(promote_n, sp.get(MILITIA_A, 0))
        remove_second = promote_n - remove_first
        if remove_first:
            remove_piece(state, MILITIA_A, promote_space, remove_first)
        if remove_second:
            remove_piece(state, MILITIA_U, promote_space, remove_second)
        add_piece(state, REGULAR_PAT, promote_space, promote_n)

    # --- Post book‑keeping --------------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"PATRIOTS RALLY {selected} (fort={bool(build_fort)}, promote={promote_space})"
    )
    return ctx
