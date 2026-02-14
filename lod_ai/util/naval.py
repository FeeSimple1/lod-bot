"""
Naval & FNI helpers.

Includes:
    • adjust_fni(state, delta)
    • Squadron/Blockade pool helpers (West Indies + ports + Unavailable)
    • auto_place_blockade(state)  (stub for future use)
"""

from lod_ai.util.history import push_history
from lod_ai.rules_consts import BLOCKADE, MAX_FNI, MAX_WI_SQUADRONS, WEST_INDIES_ID


def adjust_fni(state, delta: int) -> None:
    """
    Move the French Navy Influence (FNI) marker <delta> boxes
    toward peace (negative) or war (positive). Track is 0 ↔ MAX_FNI.

    Cards #55, year_end.resolve, and Naval Pressure SA will call this.
    """
    before = state.get("fni_level", 0)
    state["fni_level"] = max(0, min(MAX_FNI, before + delta))
    if delta:
        direction = "up" if delta > 0 else "down"
        push_history(state, f"FNI shifts {direction} to level {state['fni_level']}")


# ──────────────────────────────────────────────────────────────
#  Squadron/Blockade pool helpers
# ──────────────────────────────────────────────────────────────
def _blockade_markers(state) -> dict:
    return state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})


def west_indies_blockades(state) -> int:
    """Return the number of Squadron/Blockade counters in West Indies."""
    return int(_blockade_markers(state).get("pool", 0) or 0)


def unavailable_blockades(state) -> int:
    """Return the number of unused Squadron/Blockade counters in Unavailable."""
    return int(state.setdefault("unavailable", {}).get(BLOCKADE, 0) or 0)


def total_blockades(state) -> int:
    """Return total Squadron/Blockade counters across West Indies, ports, and Unavailable."""
    bloc = _blockade_markers(state)
    return west_indies_blockades(state) + len(bloc.get("on_map", set())) + unavailable_blockades(state)


def has_blockade(state, space_id: str) -> bool:
    """Return True if *space_id* is blockaded (ports) or has squadrons (West Indies)."""
    bloc = _blockade_markers(state)
    if space_id == WEST_INDIES_ID:
        return bloc.get("pool", 0) > 0
    return space_id in bloc.get("on_map", set())


def move_blockades_to_unavailable(state, qty: int) -> int:
    """Move up to *qty* counters from West Indies to Unavailable."""
    bloc = _blockade_markers(state)
    pool = int(bloc.get("pool", 0) or 0)
    moved = min(qty, pool)
    if moved:
        bloc["pool"] = pool - moved
        unavail = state.setdefault("unavailable", {})
        unavail[BLOCKADE] = int(unavail.get(BLOCKADE, 0) or 0) + moved
    return moved


def move_blockades_to_west_indies(state, qty: int) -> int:
    """Move up to *qty* counters from Unavailable to West Indies, respecting cap."""
    bloc = _blockade_markers(state)
    pool = int(bloc.get("pool", 0) or 0)
    unavail = state.setdefault("unavailable", {})
    available = int(unavail.get(BLOCKADE, 0) or 0)
    space_left = max(0, MAX_WI_SQUADRONS - pool)
    moved = min(qty, available, space_left)
    if moved:
        unavail[BLOCKADE] = available - moved
        if unavail[BLOCKADE] == 0:
            unavail.pop(BLOCKADE, None)
        bloc["pool"] = pool + moved
    return moved


# ──────────────────────────────────────────────────────────────
#  City-to-city Blockade movement (§3.6.8 Win the Day)
# ──────────────────────────────────────────────────────────────
def move_blockade_city_to_city(state, src_city: str, dst_city: str) -> bool:
    """Move a Blockade marker from *src_city* to *dst_city*.

    Returns True if a Blockade was actually moved, False if *src_city*
    had no Blockade to move.
    """
    bloc = _blockade_markers(state)
    on_map = bloc.setdefault("on_map", set())
    if src_city not in on_map:
        return False
    on_map.discard(src_city)
    on_map.add(dst_city)
    push_history(state, f"Blockade moved from {src_city} to {dst_city}")
    return True


# ──────────────────────────────────────────────────────────────
#  Placeholder – full blockade logic not yet needed
# ──────────────────────────────────────────────────────────────
def auto_place_blockade(state) -> None:
    """
    Stub: In the full rules, certain FNI levels auto-place Blockade markers
    in South Carolina and Massachusetts Ports.  Implement when Commands/
    SAs reference Naval Pressure.  For now it only logs.
    """
    push_history(state, "[Blockade auto-placement not yet implemented]")
