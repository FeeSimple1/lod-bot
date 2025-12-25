from __future__ import annotations

"""
State validation helpers.

`validate_state` raises `ValueError`/`TypeError` when the in-memory state
violates the canonical schema:
    • state["spaces"][sid]    – integer piece counts only
    • state["support"][sid]   – signed int (−2..+2)
    • state["control"][sid]   – "BRITISH" | "REBELLION" | None
    • state["markers"][tag]   – {"pool": int >=0, "on_map": set[str]}
    • state["leaders"][name]  – space id or None
"""

from typing import Dict, Iterable

from lod_ai import rules_consts as C
from lod_ai.map import adjacency as map_adj


_MARKER_TAGS = (C.PROPAGANDA, C.RAID, C.BLOCKADE)


def _require_keys(state: Dict, keys: Iterable[str]) -> None:
    missing = [k for k in keys if k not in state]
    if missing:
        raise KeyError(f"state missing required keys: {missing}")


def _validate_spaces(state: Dict, valid_spaces: set[str]) -> None:
    for sid, sp in state["spaces"].items():
        if sid not in valid_spaces:
            raise ValueError(f"Unknown space id in state.spaces: {sid}")
        for tag, qty in sp.items():
            if not isinstance(qty, int):
                raise TypeError(f"state['spaces']['{sid}']['{tag}'] must be int")
            if qty < 0:
                raise ValueError(f"Negative count for {tag} in {sid}")


def _validate_support(state: Dict, valid_spaces: set[str]) -> None:
    for sid, lvl in state.get("support", {}).items():
        if sid not in valid_spaces:
            raise ValueError(f"Unknown space in support map: {sid}")
        if not isinstance(lvl, int):
            raise TypeError(f"Support level for {sid} must be int")
        if lvl < -2 or lvl > 2:
            raise ValueError(f"Support level for {sid} out of range: {lvl}")


def _validate_control(state: Dict, valid_spaces: set[str]) -> None:
    for sid, ctrl in state.get("control", {}).items():
        if sid not in valid_spaces:
            raise ValueError(f"Unknown space in control map: {sid}")
        if ctrl not in ("BRITISH", "REBELLION", None):
            raise ValueError(f"Invalid control value for {sid}: {ctrl}")


def _validate_markers(state: Dict, valid_spaces: set[str]) -> None:
    markers = state.get("markers", {})
    for tag in _MARKER_TAGS:
        if tag not in markers:
            raise KeyError(f"Missing marker entry for {tag}")
        entry = markers[tag]
        if not isinstance(entry, dict):
            raise TypeError(f"state['markers']['{tag}'] must be a dict")
        pool = entry.get("pool", 0)
        if not isinstance(pool, int) or pool < 0:
            raise ValueError(f"Marker pool for {tag} must be non-negative int")
        on_map = entry.get("on_map", set())
        if not isinstance(on_map, (set, frozenset)):
            raise TypeError(f"state['markers']['{tag}']['on_map'] must be a set")
        for sid in on_map:
            if sid not in valid_spaces:
                raise ValueError(f"Marker {tag} placed in unknown space {sid}")
            if state["spaces"].get(sid, {}).get(tag, 0) not in (0, ):
                raise ValueError(f"Marker {tag} should not be stored in spaces[{sid}]")


def _validate_leaders(state: Dict, valid_spaces: set[str]) -> None:
    for name, loc in state.get("leaders", {}).items():
        if loc is None:
            continue
        if not isinstance(loc, str):
            raise TypeError(f"Leader {name} location must be str or None")
        if loc not in valid_spaces:
            raise ValueError(f"Leader {name} in unknown space {loc}")


def validate_state(state: Dict) -> None:
    """Raise if *state* violates the canonical schema."""
    _require_keys(state, ["spaces", "support", "control", "markers", "leaders", "resources"])

    valid_spaces = set(map_adj.all_space_ids())
    _validate_spaces(state, valid_spaces)
    _validate_support(state, valid_spaces)
    _validate_control(state, valid_spaces)
    _validate_markers(state, valid_spaces)
    _validate_leaders(state, valid_spaces)

    if "fni_level" in state and state["fni_level"] is not None:
        if not isinstance(state["fni_level"], int) or state["fni_level"] < 0:
            raise ValueError("state['fni_level'] must be a non-negative int")
