"""
lod_ai.board.pieces
===================

Generic helpers that mutate the passed-in `state` in a deterministic,
undo-friendly way.
"""

from typing import Dict, Any
from lod_ai.util.history import push_history
from lod_ai.rules_consts import LEADERS, WEST_INDIES_ID

# --------------------------------------------------------------------------- #
# internal utils
# --------------------------------------------------------------------------- #
def _space_dict(state: Dict[str, Any], loc: str) -> Dict[str, int]:
    if loc in state["spaces"]:
        return state["spaces"][loc]
    if loc in ("available", "unavailable", "casualties"):
        return state[loc]
    if loc == WEST_INDIES_ID:
        return state["spaces"][WEST_INDIES_ID]
    raise ValueError(f"Unknown location '{loc}'")

# --------------------------------------------------------------------------- #
# public primitive movers
# --------------------------------------------------------------------------- #
def move_piece(state: Dict[str, Any], tag: str, src: str, dst: str, qty: int = 1) -> int:
    if qty <= 0:
        return 0
    src_dict = _space_dict(state, src)
    dst_dict = _space_dict(state, dst)

    moved = min(qty, src_dict.get(tag, 0))
    if moved:
        src_dict[tag] -= moved
        if src_dict[tag] == 0:
            del src_dict[tag]
        dst_dict[tag] = dst_dict.get(tag, 0) + moved
        push_history(state, f"{moved}×{tag}  {src} → {dst}")
    return moved


def place_piece(state: Dict[str, Any], tag: str, loc: str, qty: int = 1) -> int:
    return move_piece(state, tag, "available", loc, qty)


def remove_piece(state: Dict[str, Any], tag: str, loc: str | None,
                 qty: int = 1, to: str = "available") -> int:
    if loc:
        return move_piece(state, tag, loc, to, qty)

    remaining = qty
    for name in list(state["spaces"]):
        if remaining == 0:
            break
        remaining -= move_piece(state, tag, name, to, remaining)
    return qty - remaining

# --------------------------------------------------------------------------- #
# Add from Available pool respecting caps
# --------------------------------------------------------------------------- #
def add_piece(state: Dict[str, Any], tag: str, loc: str, qty: int = 1) -> int:
    """Place up to *qty* pieces from the Available pool into *loc*.

    The helper withdraws pieces from ``state['available']`` and delegates
    placement to :func:`place_with_caps` so global limits are enforced.
    Returns the number of pieces actually added.
    """

    if qty <= 0:
        return 0

    pool = state.setdefault("available", {})
    available = pool.get(tag, 0)
    if available <= 0:
        push_history(state, f"(⛔ no {tag} available)")
        return 0

    to_place = min(qty, available)
    placed = place_with_caps(state, tag, loc, to_place)
    if placed:
        pool[tag] = available - placed
        if pool[tag] == 0:
            del pool[tag]
    if placed < qty:
        push_history(state, f"(⛔ only {placed}/{qty} {tag} placed)")
    return placed

# --------------------------------------------------------------------------- #
# cap-aware placement
# --------------------------------------------------------------------------- #
from lod_ai.rules_consts import (
    MAX_BRI_FORTS, MAX_PAT_FORTS, MAX_IND_VILLAGES,
    PROPAGANDA, MAX_PROPAGANDA,
)

_CAPS = {
    "British_Fort":   MAX_BRI_FORTS,
    "Patriot_Fort":   MAX_PAT_FORTS,
    "Indian_Village": MAX_IND_VILLAGES,
    PROPAGANDA:       MAX_PROPAGANDA,
}

def place_with_caps(state: Dict[str, Any], tag: str, loc: str, qty: int = 1) -> int:
    cap = _CAPS.get(tag)
    if cap is None:
        return place_piece(state, tag, loc, qty)

    current_total = sum(sp.get(tag, 0) for sp in state["spaces"].values())
    needed = max(0, cap - current_total)
    to_place = min(qty, needed)
    if to_place == 0:
        push_history(state, f"(⛔ cap reached: {tag} {cap})")
        return 0
    return place_piece(state, tag, loc, to_place)

# --------------------------------------------------------------------------- #
# Simple marker placement (Propaganda, Raid, Blockade)
# --------------------------------------------------------------------------- #
def place_marker(state, marker_tag: str, loc: str, qty: int = 1) -> int:
    """
    Place up to *qty* markers in *loc* respecting caps.
    Assumes markers are unlimited on-map but drawn from a pool in state["markers"].
    """
    pool = state.setdefault("markers", {}).setdefault(marker_tag, {"pool": 0})
    on_map = _space_dict(state, loc)

    available = pool["pool"]
    placed = min(qty, available)
    if placed:
        pool["pool"] -= placed
        on_map[marker_tag] = on_map.get(marker_tag, 0) + placed
        push_history(state, f"{placed} {marker_tag} placed in {loc}")
    return placed

def return_leaders(state) -> None:
    """
    Rule 6.1 – move *all* Leader pieces on the map to Available.
    """
    moved = 0
    for sid, space in state["spaces"].items():
        for lid in LEADERS:
            cnt = space.get(lid, 0)
            if cnt:
                remove_piece(state, lid, sid, cnt, to="available")
                moved += cnt
    if moved:
        push_history(state, f"Leaders returned to Available ({moved})")


def lift_casualties(state) -> None:
    """
    Rule 6.2 – move every piece in state['casualties'] to Available, then clear the box.
    """
    dead_box = state.get("casualties", {})
    if not dead_box:
        return

    moved = 0
    for pid, cnt in list(dead_box.items()):
        if cnt:
            state["available"][pid] = state["available"].get(pid, 0) + cnt
            moved += cnt
    dead_box.clear()

    if moved:
        push_history(state, f"Casualties lifted – {moved} pieces now Available")
