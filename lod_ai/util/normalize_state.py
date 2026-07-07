from __future__ import annotations

"""
State normalisation helpers.

`normalize_state(state)` coerces older schema variants into the canonical
shape, refreshes control, and enforces caps.  Call after any mutation.
"""

from typing import Dict, Iterable

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.map import adjacency as map_adj
from lod_ai.util.caps import enforce_global_caps
from lod_ai.economy import resources
from lod_ai.leaders import leader_location

_MARKER_TAGS = (C.PROPAGANDA, C.RAID, C.BLOCKADE)


def _clamp_int(val: int) -> int:
    return max(0, int(val))


def _ensure_core(state: Dict) -> None:
    state.setdefault("spaces", {})
    state.setdefault("support", {})
    state.setdefault("control", {})
    state.setdefault("leaders", {})
    state.setdefault("resources", {})
    state.setdefault("markers", {})
    state.setdefault("available", {})
    state.setdefault("unavailable", {})
    state.setdefault("casualties", {})
    state.setdefault("history", [])
    state.setdefault("rng_log", [])
    state.setdefault("eligible", {})
    state.setdefault("fni_level", 0)


def _sync_treaty_flags(state: Dict) -> None:
    """Keep Treaty of Alliance flags in sync across legacy keys."""
    toa = bool(state.get("toa_played", state.get("treaty_of_alliance", False)))
    state["toa_played"] = toa
    state["treaty_of_alliance"] = toa


def _normalize_support(state: Dict, valid_spaces: Iterable[str]) -> None:
    support = state.setdefault("support", {})
    for sid in valid_spaces:
        sp = state["spaces"].get(sid, {})
        if sid not in support:
            if "Support" in sp:
                support[sid] = int(sp.pop("Support"))
            elif "Opposition" in sp:
                support[sid] = -int(sp.pop("Opposition"))
            elif "support" in sp:
                support[sid] = int(sp.pop("support"))
            else:
                support[sid] = 0
        support[sid] = max(-2, min(2, int(support[sid])))


def _normalize_markers(state: Dict) -> None:
    markers = state.setdefault("markers", {})
    normalized: Dict[str, Dict] = {}

    # seed defaults
    for tag in _MARKER_TAGS:
        normalized[tag] = {"pool": 0, "on_map": set()}

    # adapt legacy marker structures
    for tag, entry in markers.items():
        if tag not in normalized:
            normalized[tag] = {"pool": 0, "on_map": set()}
        pool = 0
        on_map = set()
        if isinstance(entry, dict):
            pool = entry.get("pool", 0) or 0
            om = entry.get("on_map", set())
            if isinstance(om, dict):
                om = om.keys()
            if isinstance(om, (list, tuple, set, frozenset)):
                on_map.update(om)
        elif isinstance(entry, (set, list, tuple)):
            on_map.update(entry)
        elif isinstance(entry, int):
            pool = entry
        normalized[tag]["pool"] = _clamp_int(normalized[tag]["pool"] + pool)
        normalized[tag]["on_map"].update(on_map)

    # fold in any per-space counters and remove them from spaces
    for sid, sp in state.get("spaces", {}).items():
        for tag in list(sp.keys()):
            if tag not in normalized:
                continue
            count = sp.pop(tag, 0)
            if not isinstance(count, int):
                continue
            if tag == C.BLOCKADE and sid == C.WEST_INDIES_ID:
                normalized[tag]["pool"] += _clamp_int(count)
            elif count > 0:
                normalized[tag]["on_map"].add(sid)

        # legacy lowercase blockade key
        if C.BLOCKADE_KEY in sp:
            count = _clamp_int(sp.pop(C.BLOCKADE_KEY))
            if sid == C.WEST_INDIES_ID:
                normalized[C.BLOCKADE]["pool"] += count
            elif count > 0:
                normalized[C.BLOCKADE]["on_map"].add(sid)

        # legacy Squadron counters (treat as Squadron/Blockade markers)
        if C.SQUADRON in sp:
            count = _clamp_int(sp.pop(C.SQUADRON))
            if sid == C.WEST_INDIES_ID:
                normalized[C.BLOCKADE]["pool"] += count
            elif count > 0:
                normalized[C.BLOCKADE]["on_map"].add(sid)

    for tag, entry in normalized.items():
        entry["on_map"] = set(entry["on_map"])
        normalized[tag] = entry

    state["markers"] = normalized


def _sanitize_spaces(state: Dict, valid_spaces: Iterable[str]) -> None:
    valid_set = set(valid_spaces)
    for sid in list(state["spaces"].keys()):
        if sid not in valid_set:
            state["spaces"].pop(sid)
            continue
        sp = state["spaces"][sid]
        for tag, qty in list(sp.items()):
            if not isinstance(qty, int):
                sp.pop(tag)
                continue
            sp[tag] = _clamp_int(qty)


def _sanitize_pools(state: Dict) -> None:
    for box in ("available", "unavailable", "casualties"):
        pool = state.setdefault(box, {})
        for tag, qty in list(pool.items()):
            pool[tag] = _clamp_int(qty)
            if pool[tag] == 0:
                pool.pop(tag, None)
    unavail = state.setdefault("unavailable", {})
    if C.SQUADRON in unavail:
        unavail[C.BLOCKADE] = _clamp_int(unavail.get(C.BLOCKADE, 0)) + _clamp_int(unavail.pop(C.SQUADRON))



_FACTION_OF_LEADER = {
    "LEADER_WASHINGTON": C.PATRIOTS,
    "LEADER_ROCHAMBEAU": C.FRENCH,
    "LEADER_LAUZUN": C.FRENCH,
    "LEADER_GAGE": C.BRITISH,
    "LEADER_HOWE": C.BRITISH,
    "LEADER_CLINTON": C.BRITISH,
    "LEADER_BRANT": C.INDIANS,
    "LEADER_CORNPLANTER": C.INDIANS,
    "LEADER_DRAGGING_CANOE": C.INDIANS,
}

_FACTION_PIECE_TAGS = {
    C.BRITISH: (C.REGULAR_BRI, C.TORY, C.FORT_BRI),
    C.PATRIOTS: (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT),
    C.FRENCH: (C.REGULAR_FRE,),
    C.INDIANS: (C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE),
}


def _relocate_leader(state: Dict, leader: str, dst) -> None:
    """Write *leader*'s location to *dst* (a space id or "Available")
    across the tolerated leader-state shapes."""
    leaders = state.setdefault("leaders", {})
    locs = state.setdefault("leader_locs", {})
    # leader_locs is the preferred shape
    locs[leader] = dst if isinstance(dst, str) else None
    # keep the leaders dict consistent if it uses the {leader: loc} shape
    if leader in leaders and isinstance(leaders.get(leader), (str, type(None))):
        leaders[leader] = dst if dst != "Available" else None
    else:
        # reverse {space: leader} shape — drop stale entries
        for k in [k for k, v in list(leaders.items()) if v == leader]:
            leaders.pop(k, None)
        if dst != "Available":
            leaders[dst] = leader


def _enforce_leader_orphan(state: Dict) -> None:
    """§1.10 (C5): "If at any time the current Leader is in a space with
    no pieces of its Faction, the owning Faction moves that Leader to
    any space with the same Faction's pieces or to its Available Forces
    box."  Deterministic for solitaire/bot play: relocate to the space
    with the MOST of that Faction's pieces (ties by sorted space id — no
    rng, so normalize_state stays pure), else Available.  Runs after
    every mutation, so orphaning by casualty/removal self-heals."""
    spaces = state.get("spaces", {})
    # Cheap first pass: read on-map leaders from the canonical shapes
    # (avoid 9× leader_location scans on this hot path).  Build the
    # {leader: loc} view once.
    on_map = {}
    locs = state.get("leader_locs", {})
    leaders_dict = state.get("leaders", {})
    valid = set(spaces)
    for ldr in _FACTION_OF_LEADER:
        loc = locs.get(ldr)
        if not (isinstance(loc, str) and loc in valid):
            loc = leaders_dict.get(ldr)
        if not (isinstance(loc, str) and loc in valid):
            loc = None
        if loc is not None:
            on_map[ldr] = loc
    if not on_map:
        return
    # Only leaders that are actually orphaned trigger the scan.
    per_faction_best = {}  # faction -> (best_sid or None)
    for leader, loc in on_map.items():
        faction = _FACTION_OF_LEADER[leader]
        tags = _FACTION_PIECE_TAGS[faction]
        if any(spaces.get(loc, {}).get(t, 0) for t in tags):
            continue  # not orphaned (common case)
        if faction not in per_faction_best:
            best, best_n = None, 0
            for sid in sorted(spaces):
                sp = spaces[sid]
                n = sum(sp.get(t, 0) for t in tags)
                if n > best_n:
                    best, best_n = sid, n
            per_faction_best[faction] = best
        _relocate_leader(state, leader,
                         per_faction_best[faction] or "Available")


def normalize_state(state: Dict) -> None:
    """Coerce *state* into canonical shape and enforce invariants."""
    _ensure_core(state)
    _sync_treaty_flags(state)
    valid_spaces = list(map_adj.all_space_ids())
    _sanitize_spaces(state, valid_spaces)
    _normalize_support(state, valid_spaces)
    _normalize_markers(state)
    _sanitize_pools(state)
    resources.clamp_all(state)
    refresh_control(state)
    _enforce_leader_orphan(state)  # §1.10 (C5)
    enforce_global_caps(state)
