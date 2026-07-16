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
# Q23 (Eric's ruling, July 10 2026): Propaganda and Raid markers STACK —
# on_map is a {space_id: count} dict for these tags, capped only by the
# global pool (cards 1/2/47 place two; §6.4.1/6.4.2 price removals per
# marker).  Blockades keep the Q21 set model (one per City).
_COUNT_MARKERS = {PROPAGANDA, RAID}


def _marker_entry(state, tag):
    """Return state["markers"][tag], coercing legacy set/list on_map to
    the Q23 count model for stacking marker types."""
    count_model = tag in _COUNT_MARKERS
    entry = state.setdefault("markers", {}).setdefault(
        tag, {"pool": 0, "on_map": {} if count_model else set()})
    om = entry.setdefault("on_map", {} if count_model else set())
    if count_model and not isinstance(om, dict):
        entry["on_map"] = {sid: 1 for sid in om}
    return entry
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


def _reclaim_one_from_map(state: Dict[str, Any], pool_tag: str,
                          exclude_loc: str | None = None) -> bool:
    """Remove one on-map piece of *pool_tag* (or its variants) to Available.

    *exclude_loc*: never reclaim from the space the placement targets —
    taking a piece out of the destination to place it straight back is a
    null action that still consumes the placement (Session 47).
    """
    variants = _pool_variants(pool_tag)
    candidates: list[tuple[int, str, str]] = []
    for sid, sp in state.get("spaces", {}).items():
        if exclude_loc is not None and sid == exclude_loc:
            continue
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


_FORCE_OWNER_PREFIX = (("British_", C.BRITISH), ("Patriot_", C.PATRIOTS),
                       ("French_", C.FRENCH), ("Indian_", C.INDIANS))


def _force_owner(tag: str) -> str | None:
    if tag == C.VILLAGE:
        return C.INDIANS
    for pre, fac in _FORCE_OWNER_PREFIX:
        if tag.startswith(pre):
            return fac
    return None


def _ensure_available(state: Dict[str, Any], tag: str, qty: int,
                      exclude_loc: str | None = None) -> None:
    """§1.4.1 voluntary map-pull: while executing a Command, Special
    Activity or Event to place its OWN forces, a faction MAY take them
    from the map into Available iff the type is not Available
    (B/F Regulars excepted — not in _RECLAIM_ELIGIBLE).

    C6 (Session 76): this used to run UNCONDITIONALLY on every
    placement — but Manual §8 ("No voluntary removal") says Non-player
    Factions NEVER use the 1.4.1 option, and the rule's own scope is
    the owner executing its own placement.  Now gated: the force's
    owner must be a HUMAN seat and must be the active (executing)
    faction.  For human seats the pull is auto-exercised as an interim
    (it maximises their placement); offering the decline/which-piece
    choice in the CLI is the logged residual."""
    if qty <= 0:
        return
    pool_tag = _pool_tag(tag)
    if pool_tag not in _RECLAIM_ELIGIBLE:
        return
    owner = _force_owner(pool_tag)
    humans = state.get("human_factions") or set()
    if owner is None or owner not in humans:
        return                      # §8: bots never voluntarily remove
    if str(state.get("active", "")).upper() != owner:
        return                      # §1.4.1 scope: own placement only
    pool = state.setdefault("available", {})
    while pool.get(pool_tag, 0) < qty:
        if not _reclaim_one_from_map(state, pool_tag, exclude_loc):
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

    # The Available box holds Militia/War Parties undifferentiated (the
    # Underground pool tag; A/U facing is an on-map state, S1.4.3): draws
    # from Available come out of the family entry regardless of requested
    # variant, and arrivals fold into it.  Before Session 67 a variant tag
    # parked in Available by one helper and debited under the family tag by
    # another destroyed a piece (S1.2 conservation).
    src_tag = tag
    if src == "available":
        _normalize_available_entry(state, tag)
        src_tag = _pool_tag(tag)
    dst_tag = _pool_tag(tag) if dst == "available" else tag

    moved = min(qty, src_dict.get(src_tag, 0))
    if moved:
        src_dict[src_tag] -= moved
        if src_dict[src_tag] == 0:
            del src_dict[src_tag]
        dst_dict[dst_tag] = dst_dict.get(dst_tag, 0) + moved
        push_history(state, f"{moved}×{tag}  {src} → {dst}")
    return moved

def place_piece(state: Dict[str, Any], tag: str, loc: str, qty: int = 1) -> int:
    if tag in _BASE_TAGS:
        slots = _available_base_slots(state, loc)
        if slots <= 0:
            push_history(state, f"(⛔ stacking limit: cannot add base to {loc})")
            return 0
        qty = min(qty, slots)

    _ensure_available(state, tag, qty, exclude_loc=loc)
    return move_piece(state, tag, "available", loc, qty)


def remove_piece(state: Dict[str, Any], tag: str, loc: str | None,
                 qty: int = 1, to: str = "available") -> int:
    tag = _norm(tag)
    if tag in _MARKERS:
        markers = _marker_entry(state, tag)
        removed = 0
        on_map = markers["on_map"]
        if tag in _COUNT_MARKERS:
            # Q23 count model: remove up to qty markers.
            if loc:
                take = min(qty, on_map.get(loc, 0))
                if take:
                    if on_map[loc] - take:
                        on_map[loc] -= take
                    else:
                        del on_map[loc]
                    markers["pool"] = markers.get("pool", 0) + take
                    push_history(state, f"{take} {tag} removed from {loc}")
                return take
            while removed < qty and on_map:
                sid = next(iter(on_map))
                take = min(qty - removed, on_map[sid])
                if on_map[sid] - take:
                    on_map[sid] -= take
                else:
                    del on_map[sid]
                markers["pool"] = markers.get("pool", 0) + take
                removed += take
                push_history(state, f"{take} {tag} removed from {sid}")
            return removed
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
    _normalize_available_entry(state, tag)
    pool_tag = _pool_tag(tag)
    available = pool.get(pool_tag, 0)
    if available <= 0:
        push_history(state, f"(⛔ no {tag} available)")
        return 0

    to_place = min(qty, available)
    # move_piece (via place_piece) debits the Available family entry
    # itself; the pre-Session-67 re-debit here double-charged the pool
    # whenever a variant tag had been parked in Available (S1.2).
    placed = place_with_caps(state, tag, loc, to_place)
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
    Place up to *qty* markers in *loc*, drawn from the marker's pool.

    Q23 (July 10 2026): Propaganda and Raid markers STACK — the only cap
    is the global pool, so multi-placements (cards 1/2/47's "two
    Propaganda") and re-Raids of a marked Province each add a marker.
    Blockades keep the Q21 one-per-space set model.  Both models
    conserve markers exactly (the pre-S67 code destroyed one per
    already-marked placement).
    """
    markers = _marker_entry(state, marker_tag)
    on_map = markers["on_map"]
    pool = markers.get("pool", 0)
    if marker_tag in _COUNT_MARKERS:
        n = min(qty, pool)
        if n <= 0:
            return 0
        markers["pool"] = pool - n
        on_map[loc] = on_map.get(loc, 0) + n
        push_history(state, f"{n} {marker_tag} placed in {loc}")
        return n
    if loc in on_map or pool <= 0:
        return 0
    markers["pool"] = pool - 1
    on_map.add(loc)
    push_history(state, f"1 {marker_tag} placed in {loc}")
    return 1


def marker_count(state, marker_tag: str, loc: str) -> int:
    """Markers of *marker_tag* currently in *loc* (0/1 for set-model)."""
    om = (state.get("markers", {}).get(marker_tag, {}) or {}).get("on_map")
    if isinstance(om, dict):
        return int(om.get(loc, 0))
    return 1 if om and loc in om else 0

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
            pool_tag = _pool_tag(pid)  # Available holds A/U variants folded (S1.4.3)
            state["available"][pool_tag] = state["available"].get(pool_tag, 0) + cnt
            moved += cnt
    dead_box.clear()

    if moved:
        push_history(state, f"Casualties lifted – {moved} pieces now Available")
