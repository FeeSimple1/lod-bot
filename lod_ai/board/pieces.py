"""
lod_ai.board.pieces
===================

Generic helpers that mutate the passed-in `state` in a deterministic,
undo-friendly way.
"""

from typing import Dict, Any
from lod_ai.util.history import push_history
from lod_ai import rules_consts as C
from lod_ai.rules_consts import LEADERS, WEST_INDIES_ID, PROPAGANDA, RAID, BLOCKADE

def _norm(tag: str) -> str:
    return tag

_MARKERS = {PROPAGANDA, RAID, BLOCKADE}
_BASE_TAGS = {C.FORT_BRI, C.FORT_PAT, C.VILLAGE}

_POOL_FAMILY = {
    C.MILITIA_A: C.MILITIA_U,
    C.WARPARTY_A: C.WARPARTY_U,
}

_POOL_VARIANTS = {
    C.MILITIA_U: (C.MILITIA_U, C.MILITIA_A),
    C.MILITIA_A: (C.MILITIA_A, C.MILITIA_U),
    C.WARPARTY_U: (C.WARPARTY_U, C.WARPARTY_A),
    C.WARPARTY_A: (C.WARPARTY_A, C.WARPARTY_U),
}

_RECLAIM_ELIGIBLE = {
    C.TORY,
    C.TORY_UNAVAIL,
    C.FORT_BRI,
    C.FORT_PAT,
    C.VILLAGE,
    C.MILITIA_U,
    C.MILITIA_A,
    C.WARPARTY_U,
    C.WARPARTY_A,
}

# §1.6.4 Cumulative Casualties tracking
# CBC: British Regular, Tory, British Fort casualties (entire game)
# CRC: French Regular, Patriot Continental, Patriot Fort casualties (entire game)
_CBC_PIECES = {C.REGULAR_BRI, C.TORY, C.FORT_BRI}
_CRC_PIECES = {C.REGULAR_PAT, C.REGULAR_FRE, C.FORT_PAT}


def increment_casualties(state: Dict[str, Any], tag: str, qty: int) -> None:
    """Increment CBC or CRC cumulative counter per §1.6.4.

    Called whenever a piece enters the Casualties box, or when a Fort
    is removed as a battle casualty (Forts return to Available immediately
    but still count toward cumulative casualties).
    These counters never decrement.
    """
    if qty <= 0:
        return
    if tag in _CBC_PIECES:
        state["cbc"] = state.get("cbc", 0) + qty
    elif tag in _CRC_PIECES:
        state["crc"] = state.get("crc", 0) + qty

# --------------------------------------------------------------------------- #
# internal utils
# --------------------------------------------------------------------------- #
def _space_dict(state: Dict[str, Any], loc: str) -> Dict[str, int]:
    if loc in state["spaces"]:
        return state["spaces"][loc]
    if loc in ("available", "unavailable", "casualties"):
        return state[loc]
    if loc == WEST_INDIES_ID or str(loc).lower() == WEST_INDIES_ID.lower():
        return state["spaces"][WEST_INDIES_ID]
    raise ValueError(f"Unknown location '{loc}'")


def _pool_tag(tag: str) -> str:
    """Return the Available-pool tag family for *tag* (Militia/WP share pools)."""
    return _POOL_FAMILY.get(tag, tag)


def _pool_variants(tag: str) -> tuple[str, ...]:
    """Return variant tags that draw from the same pool as *tag*."""
    base = _pool_tag(tag)
    return _POOL_VARIANTS.get(base, (base,))


def _normalize_available_entry(state: Dict[str, Any], tag: str) -> None:
    """Merge any variant tags in Available back to their pool tag."""
    pool_tag = _pool_tag(tag)
    if pool_tag == tag:
        return
    pool = state.setdefault("available", {})
    qty = pool.pop(tag, 0)
    if qty:
        pool[pool_tag] = pool.get(pool_tag, 0) + qty


def _reclaim_one_from_map(state: Dict[str, Any], pool_tag: str) -> bool:
    """Remove one on-map piece of *pool_tag* (or its variants) to Available."""
    variants = _pool_variants(pool_tag)
    candidates: list[tuple[int, str, str]] = []
    for sid, sp in state.get("spaces", {}).items():
        for vtag in variants:
            qty = sp.get(vtag, 0)
            if qty:
                candidates.append((qty, sid, vtag))
    if not candidates:
        return False
    candidates.sort(key=lambda t: (-t[0], t[1], variants.index(t[2]) if t[2] in variants else 0))
    _, sid, chosen_tag = candidates[0]
    remove_piece(state, chosen_tag, sid, 1, to="available")
    _normalize_available_entry(state, chosen_tag)
    push_history(state, f"Removed one {pool_tag} from {sid} to Available to fulfill placement")
    return True


def _ensure_available(state: Dict[str, Any], tag: str, qty: int) -> None:
    """Ensure at least *qty* of *tag* exist in Available, reclaiming from map if needed."""
    if qty <= 0:
        return
    pool_tag = _pool_tag(tag)
    if pool_tag not in _RECLAIM_ELIGIBLE:
        return
    pool = state.setdefault("available", {})
    while pool.get(pool_tag, 0) < qty:
        if not _reclaim_one_from_map(state, pool_tag):
            break
        pool = state.setdefault("available", {})


def _available_base_slots(state: Dict[str, Any], loc: str) -> int:
    """Return remaining Fort/Village slots in *loc* respecting the global stack limit (2)."""
    if loc in ("available", "unavailable", "casualties"):
        return 2
    sp = _space_dict(state, loc)
    total_bases = sum(sp.get(tag, 0) for tag in _BASE_TAGS)
    return max(0, 2 - total_bases)

# --------------------------------------------------------------------------- #
# public primitive movers
# --------------------------------------------------------------------------- #
def flip_pieces(state: Dict[str, Any], from_tag: str, to_tag: str,
                loc: str, qty: int = 1) -> int:
    """Flip pieces in-place from *from_tag* to *to_tag* at *loc*.

    Used for activation/deactivation (e.g., Militia_U → Militia_A) where
    pieces stay in the same space but change variant.  Does **not** route
    through the Available pool, so it cannot corrupt pool state.

    Returns the number of pieces actually flipped.
    """
    if qty <= 0 or from_tag == to_tag:
        return 0
    sp = _space_dict(state, loc)
    actual = min(qty, sp.get(from_tag, 0))
    if actual:
        sp[from_tag] -= actual
        if sp[from_tag] == 0:
            del sp[from_tag]
        sp[to_tag] = sp.get(to_tag, 0) + actual
        push_history(state, f"Flipped {actual}×{from_tag}→{to_tag} in {loc}")
    return actual


def move_piece(state: Dict[str, Any], tag: str, src: str, dst: str, qty: int = 1) -> int:
    if qty <= 0:
        return 0
    tag = _norm(tag)
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
    if tag in _BASE_TAGS:
        slots = _available_base_slots(state, loc)
        if slots <= 0:
            push_history(state, f"(⛔ stacking limit: cannot add base to {loc})")
            return 0
        qty = min(qty, slots)

    _ensure_available(state, tag, qty)
    return move_piece(state, tag, "available", loc, qty)


def remove_piece(state: Dict[str, Any], tag: str, loc: str | None,
                 qty: int = 1, to: str = "available") -> int:
    tag = _norm(tag)
    if tag in _MARKERS:
        markers = state.setdefault("markers", {}).setdefault(tag, {"pool": 0, "on_map": set()})
        removed = 0
        on_map = markers.setdefault("on_map", set())
        if loc:
            if loc in on_map and removed < qty:
                on_map.discard(loc)
                markers["pool"] = markers.get("pool", 0) + 1
                removed = 1
                push_history(state, f"{tag} removed from {loc}")
            return removed
        while removed < qty and on_map:
            sid = on_map.pop()
            markers["pool"] = markers.get("pool", 0) + 1
            removed += 1
            push_history(state, f"{tag} removed from {sid}")
        return removed

    if loc:
        actual = move_piece(state, tag, loc, to, qty)
        if to == "casualties":
            increment_casualties(state, tag, actual)
        return actual

    remaining = qty
    for name in list(state["spaces"]):
        if remaining == 0:
            break
        moved = move_piece(state, tag, name, to, remaining)
        if to == "casualties":
            increment_casualties(state, tag, moved)
        remaining -= moved
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
    _ensure_available(state, tag, qty)
    pool_tag = _pool_tag(tag)
    available = pool.get(pool_tag, 0)
    if available <= 0:
        push_history(state, f"(⛔ no {tag} available)")
        return 0

    to_place = min(qty, available)
    placed = place_with_caps(state, tag, loc, to_place)
    if placed:
        pool[pool_tag] = available - placed
        if pool[pool_tag] == 0:
            del pool[pool_tag]
    if placed < qty:
        push_history(state, f"(⛔ only {placed}/{qty} {tag} placed)")
    return placed

# --------------------------------------------------------------------------- #
# cap-aware placement
# --------------------------------------------------------------------------- #
from lod_ai.rules_consts import (
    MAX_FORT_BRI, MAX_FORT_PAT, MAX_VILLAGE,
    PROPAGANDA, MAX_PROPAGANDA,
    VILLAGE,
)

_CAPS = {
    C.FORT_BRI:  MAX_FORT_BRI,
    C.FORT_PAT:  MAX_FORT_PAT,
    VILLAGE:     MAX_VILLAGE,
    PROPAGANDA:  MAX_PROPAGANDA,
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
    markers = state.setdefault("markers", {}).setdefault(marker_tag, {"pool": 0, "on_map": set()})
    available = markers.get("pool", 0)
    placed = min(qty, available)
    if placed:
        markers["pool"] = available - placed
        markers.setdefault("on_map", set()).add(loc)
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
