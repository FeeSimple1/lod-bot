from __future__ import annotations
"""lod_ai.commands.muster
=====================================================
British and French **Muster** Command implementation (§3.2.1, §3.5.3).
This version includes a complete *Reward Loyalty* routine **and** now
adheres strictly to the canonical vocabulary in ``lod_ai.rules_consts``.

Public API
----------
``execute(state, faction, ctx, selected, regular_plan=None,
          tory_plan=None, build_fort=False, reward_levels=0)``
* ``selected`` – list[str] of all spaces paid for (British) or the single
  space (French) that the caller wants to Muster in.
* ``regular_plan`` – dict  ``{"space": <id>, "n": <1‑6>}``  indicating the
  one space that will get British Regulars (ignored for French).
* ``tory_plan`` – mapping  ``{space_id: n}`` where *n* is 1‑2 (or 1 if the
  space sits at Passive Opposition). Ignored for French.
* ``build_fort`` – ``True`` if the British will swap 3 cubes for a Fort in
  *one* selected space (mutually exclusive with ``reward_levels``).
* ``reward_levels`` – ``int ≥1`` levels to shift via Reward Loyalty in one
  selected space. This costs the British *levels* **plus** 1 for a Propaganda
  or Raid marker present. Mutually exclusive with ``build_fort``.

The function always returns the *unchanged* ``ctx`` object (for parity with
other Commands such as :pymod:`lod_ai.commands.march`).
"""

from typing import Dict, List, Optional

from lod_ai.util.history   import push_history
from lod_ai.board.control  import refresh_control
from lod_ai.util.caps      import enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.leaders        import apply_leader_modifiers
from lod_ai.rules_consts import (
    # pieces
    REGULAR_BRI, REGULAR_FRE, TORY, FORT_BRI, FORT_PAT, VILLAGE,
    # support levels
    ACTIVE_SUPPORT, PASSIVE_SUPPORT, NEUTRAL,
    PASSIVE_OPPOSITION, ACTIVE_OPPOSITION,
    # markers
    PROPAGANDA, RAID,
    # space IDs
    WEST_INDIES_ID,
    # factions
    BRITISH, PATRIOTS, FRENCH,
)
from lod_ai.board.pieces      import add_piece, remove_piece
from lod_ai.economy.resources import spend, can_afford

COMMAND_NAME = "MUSTER"

# ---------------------------------------------------------------------------
# Support helpers (local – could migrate to util.support later)
# ---------------------------------------------------------------------------
SUPPORT_ENUM = [ACTIVE_OPPOSITION, PASSIVE_OPPOSITION, NEUTRAL,
                PASSIVE_SUPPORT, ACTIVE_SUPPORT]

SUPPORT_TO_IDX = {lvl: i for i, lvl in enumerate(SUPPORT_ENUM)}


def _support_value(state: Dict, sid: str) -> int:
    """Return the integer support level stored for *sid* (default NEUTRAL)."""
    return state.get("support", {}).get(sid, NEUTRAL)


def _set_support(state: Dict, sid: str, val: int) -> None:
    """Write *val* back clamped to the enum range."""
    lo, hi = SUPPORT_ENUM[0], SUPPORT_ENUM[-1]
    state.setdefault("support", {})[sid] = max(min(val, hi), lo)


# ---------------------------------------------------------------------------
# Pool utilities
# ---------------------------------------------------------------------------

def _draw_from_pool(state: Dict, tag: str, n: int) -> int:
    """Return min(n, available), letting add_piece() pull from the pool."""
    avail = state["available"].get(tag, 0)
    return min(avail, n)

# ---------------------------------------------------------------------------
# In‑space helpers
# ---------------------------------------------------------------------------

def _make_fort(state: Dict, space_id: str) -> None:
    """Swap any three British cubes for 1 Fort using centralized helpers."""
    space = state["spaces"][space_id]
    base_total = space.get(FORT_BRI, 0) + space.get(FORT_PAT, 0) + space.get(VILLAGE, 0)
    if base_total >= 2:
        raise ValueError("Cannot build a Fort; stacking limit reached.")

    tags = (REGULAR_BRI, TORY)
    removed = 0
    for tag in tags:
        avail = space.get(tag, 0)
        take  = min(3 - removed, avail)
        if take:
            remove_piece(state, tag, space_id, take)
            removed += take
        if removed == 3:
            break
    if removed < 3:
        raise ValueError("Need at least 3 British cubes here to build a Fort.")
    add_piece(state, FORT_BRI, space_id, 1)

def _reward_loyalty(state: Dict, sp: Dict, space_id: str, levels: int) -> None:
    """Shift *levels* toward Active Support in *sp* paying Resources.

    Preconditions checked per §3.2.1:
      * ≥1 British Regular and ≥1 Tory present
      * British Control in the space
    """
    if levels <= 0:
        return
    levels = min(2, levels)

    # Checks – Regulars, Tories, Control
    if (sp.get(REGULAR_BRI, 0) == 0) or (sp.get(TORY, 0) == 0):
        raise ValueError("Reward Loyalty requires ≥1 British Regular and ≥1 Tory in space.")
    if state.get("control", {}).get(space_id) != BRITISH:
        raise ValueError("British must Control the space to Reward Loyalty.")

    # Determine marker removals and potential shift
    marker_state = state.setdefault("markers", {})
    markers_here = []
    for marker in (PROPAGANDA, RAID):
        entry = marker_state.setdefault(marker, {"pool": 0, "on_map": set()})
        if space_id in entry.get("on_map", set()):
            markers_here.append(marker)

    current = _support_value(state, space_id)
    shift_levels = min(levels, ACTIVE_SUPPORT - current)
    if shift_levels <= 0:
        # Skip Reward Loyalty if it would only clear markers
        return

    cost = len(markers_here) + shift_levels
    if state["resources"][BRITISH] < cost:
        raise ValueError("Not enough Resources to Reward Loyalty.")

    spend(state, BRITISH, cost, ignore_free=True)

    # Remove markers first (each already included in cost)
    for marker in markers_here:
        entry = marker_state.setdefault(marker, {"pool": 0, "on_map": set()})
        if space_id in entry.get("on_map", set()):
            entry["on_map"].discard(space_id)
            entry["pool"] = entry.get("pool", 0) + 1

    # Apply shift
    target  = current + shift_levels
    _set_support(state, space_id, target)

    # Log
    state.setdefault("log", []).append(
        f"BRITISH reward loyalty in {space_id}: {current} → {_support_value(state, space_id)} (cost={cost})"
    )


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def _brit_cost(state: Dict, n_spaces: int):
    spend(state, BRITISH, n_spaces)

def _french_cost(state: Dict):
    spend(state, FRENCH, 2)

# ---------------------------------------------------------------------------
# Adjacency helper
# ---------------------------------------------------------------------------

def _is_adjacent_to_brit_power(state: Dict, space_id: str) -> bool:
    """Return True if *space_id* either contains or is adjacent to British Regulars/Forts."""
    sp = state["spaces"][space_id]
    if sp.get(REGULAR_BRI, 0) > 0 or sp.get(FORT_BRI, 0) > 0:
        return True
    return any(
        state["spaces"][nbr].get(REGULAR_BRI, 0) > 0 or state["spaces"][nbr].get(FORT_BRI, 0) > 0
        for nbr in state["spaces"]
        if is_adjacent(space_id, nbr)
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(state: Dict, faction: str, ctx: Dict, selected: List[str], *,
            regular_plan: Optional[Dict] = None,
            tory_plan: Optional[Dict[str, int]] = None,
            build_fort: bool = False,
            reward_levels: int = 0) -> Dict:
    """Perform the Muster Command for *faction* in *selected* spaces."""
    # Treaty gate
    if faction == FRENCH and not state.get("toa_played"):
        raise ValueError("FRENCH cannot Muster before Treaty of Alliance.")

    # Mutual‑exclusion checks
    if build_fort and reward_levels:
        raise ValueError("Cannot both build a Fort and Reward Loyalty in the same Muster.")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(selected)
    # Leader hooks – none defined yet, keep pattern
    ctx = apply_leader_modifiers(state, faction, "pre_muster", ctx)

    push_history(state, f"{faction} MUSTER starts in {selected}")

    # -------------------------------------------------------------------
    # BRITISH flow
    # -------------------------------------------------------------------
    if faction == BRITISH:
        # Pay cost (1 Resource per selected space)
        _brit_cost(state, len(selected))

        # 1) Regular placement (in exactly ONE City/Colony/WI)
        if not regular_plan:
            raise ValueError("regular_plan required for British Muster.")
        dest = regular_plan["space"]
        if dest not in selected:
            raise ValueError("Regular placement space must be among selected.")
        n_reg = min(regular_plan.get("n", 0), 6)
        n_reg = _draw_from_pool(state, REGULAR_BRI, n_reg)
        add_piece(state, REGULAR_BRI, dest, n_reg)

        # 2) Tory placement – loop over tory_plan dict
        if tory_plan:
            for sp_id, n in tory_plan.items():
                if sp_id not in selected or sp_id == WEST_INDIES_ID:
                    continue
                support_level = state.get("support", {}).get(sp_id, NEUTRAL)
                if support_level == ACTIVE_OPPOSITION:
                    continue  # skip Active Opp
                if not _is_adjacent_to_brit_power(state, sp_id):
                    continue
                max_tories = 1 if support_level == PASSIVE_OPPOSITION else 2
                place = min(n, max_tories)
                place = _draw_from_pool(state, TORY, place)
                add_piece(state, TORY, sp_id, place)

        # 3) Fort or Reward Loyalty in ONE selected space
        if build_fort or reward_levels:
            target = dest  # default to Regular destination if caller didn't say
            if build_fort:
                _make_fort(state, target)
            else:
                _reward_loyalty(state, state["spaces"][target], target, reward_levels)

    # -------------------------------------------------------------------
    # FRENCH flow
    # -------------------------------------------------------------------
    else:  # faction == "FRENCH"
        _french_cost(state)
        if len(selected) != 1:
            raise ValueError("French Muster selects exactly one space.")
        sp_id = selected[0]
        n_reg = _draw_from_pool(state, REGULAR_FRE, 4)
        add_piece(state, REGULAR_FRE, sp_id, n_reg)

        # Optional Patriot Fort substitution if Patriots have Resources
        sp = state["spaces"][sp_id]
        if sp.get(REGULAR_FRE, 0) >= 2 and can_afford(state, PATRIOTS, 1):
            remove_piece(state, REGULAR_FRE, sp_id, 2)
            add_piece(state, FORT_PAT,       sp_id, 1)          # Patriot Fort
            spend(state, PATRIOTS, 1)

    # -------------------------------------------------------------------
    # Wrap‑up bookkeeping
    # -------------------------------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"{faction} MUSTER {selected} (fort={build_fort}, loyalty+={reward_levels})"
    )
    return ctx
