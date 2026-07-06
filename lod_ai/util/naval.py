"""
Naval & FNI helpers.

Includes:
    • adjust_fni(state, delta)
    • Squadron/Blockade pool helpers (West Indies + ports + Unavailable)
"""

from lod_ai.util.history import push_history
from lod_ai.rules_consts import BLOCKADE, MAX_FNI, MAX_WI_SQUADRONS, WEST_INDIES_ID


def adjust_fni(state, delta: int) -> None:
    """Add *delta* (±) to the French Navy Index (FNI), clamped to 0..MAX_FNI.

    Single source of truth for FNI changes -- the card effects, the Naval
    Pressure SA, and year-end resolution all route through here (the
    `cards.effects.shared` module re-exports this function).

    Rules enforced:
      * §1.9: FNI stays 0 until the Treaty of Alliance is played.
      * §1.9 / §4.5.3: on a *raise*, FNI may never exceed the number of
        Blockade markers Available (in play) -- see `fni_ceiling`. Lowering
        is always allowed, and FNI is never forced below its current level.
    """
    before = state.get("fni_level", 0)

    if not state.get("toa_played", False):
        state["fni_level"] = 0
        push_history(state, "FNI remains 0 (Treaty of Alliance not yet played)")
        return

    new = max(0, min(MAX_FNI, before + delta))
    if delta > 0:
        new = min(new, max(before, fni_ceiling(state)))
    state["fni_level"] = new
    push_history(state, f"FNI {before} → {state['fni_level']}")


# ──────────────────────────────────────────────────────────────
#  Squadron/Blockade pool helpers
# ──────────────────────────────────────────────────────────────
def _blockade_markers(state) -> dict:
    return state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})


def west_indies_blockades(state) -> int:
    """Return the number of Squadron/Blockade counters in West Indies."""
    return int(_blockade_markers(state).get("pool", 0) or 0)


def fni_ceiling(state) -> int:
    """§1.9 / §4.5.3: "FNI may never exceed the number of Blockades that are
    Available." The available markers are those in play -- the West Indies
    pool plus those already on Cities -- since markers still in Unavailable
    cannot back an FNI level. Capped at MAX_FNI."""
    bloc = _blockade_markers(state)
    in_play = int(bloc.get("pool", 0) or 0) + len(bloc.get("on_map", set()))
    return min(MAX_FNI, in_play)


def unavailable_blockades(state) -> int:
    """Return the number of unused Squadron/Blockade counters in Unavailable."""
    return int(state.setdefault("unavailable", {}).get(BLOCKADE, 0) or 0)


def total_blockades(state) -> int:
    """Return total Squadron/Blockade counters across West Indies, ports, and Unavailable."""
    bloc = _blockade_markers(state)
    return west_indies_blockades(state) + len(bloc.get("on_map", set())) + unavailable_blockades(state)


def effective_population(state, space_id: str, raw_pop: int) -> int:
    """§1.9: "The population of that City is considered 0 for purposes
    of calculating Support and during the Resource Phase of the Winter
    Quarters Round."  Returns *raw_pop*, zeroed while the City is
    Blockaded.  Non-City spaces pass through unchanged (only Cities can
    hold Blockades)."""
    if raw_pop and space_id in _blockade_markers(state).get("on_map", set()):
        return 0
    return raw_pop


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


# auto_place_blockade stub deleted (Session 48, ROADMAP Piece 3):
# no caller existed and its premise was false — §1.9 has no automatic
# Blockade placement; the FRENCH place Blockades on Cities of their
# choice as FNI rises (Naval Pressure §4.5.3, WQ §6.5.4), which
# special_activities/naval_pressure.py implements.
