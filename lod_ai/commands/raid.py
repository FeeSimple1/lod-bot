"""
lod_ai.commands.raid
====================
Indian **Raid** Command  (§3.4.4).

• Faction…… INDIANS only.
• Select…… up to 3 Provinces that
      – are at ACTIVE_OPPOSITION or PASSIVE_OPPOSITION, and
      – either contain ≥ 1 Underground War-Party **or** are adjacent to a
        Province that does.
• Cost……    1 Indian Resource per selected Province.
• Procedure
   1. For each selected Province you *may* move **one** adjacent
      Underground War-Party in (optional, max 1 per Province).
   2. In every selected Province, *activate* one Underground War-Party
      (newly moved-in or already there) ⇒ place a **Raid** marker (if cap
      allows) and shift Opposition 1 step toward Neutral.
   3. Update totals, Control, caps.

Markers are pooled in `state["markers"][RAID]` with a hard cap of 12.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Set

from lod_ai.rules_consts import (
    # pieces
    WARPARTY_U, WARPARTY_A,
    # markers & caps
    RAID, MAX_RAID,
    # support enums
    ACTIVE_OPPOSITION, PASSIVE_OPPOSITION, NEUTRAL,
)
from lod_ai.leaders import leader_location
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.map.adjacency import shortest_path
from lod_ai.board.pieces      import remove_piece, add_piece      # NEW
from lod_ai.economy.resources import spend                       # NEW

COMMAND_NAME = "RAID"      # auto-registered by commands/__init__.py
OPPOSITION_ONLY = {ACTIVE_OPPOSITION, PASSIVE_OPPOSITION}


# ────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────
def _shift_one_toward_neutral(state: Dict, space_id: str) -> None:
    """Increase support value by +1, but never above Neutral (0)."""
    cur = state.get("support", {}).get(space_id, NEUTRAL)
    if cur < NEUTRAL:
        state.setdefault("support", {})[space_id] = cur + 1


def _move_one_wp(state: Dict, src: Dict, dst: Dict, src_id: str, dst_id: str) -> None:
    if src.get(WARPARTY_U, 0) == 0:
        raise ValueError("Source has no Underground War-Party to move.")
    remove_piece(state, WARPARTY_U, src_id, 1)
    add_piece(state,    WARPARTY_U, dst_id, 1)

# ────────────────────────────────────────────────────────────────────
# public entry
# ────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    selected: List[str],
    *,
    move_plan: List[Tuple[str, str]] | None = None,   # (src, dst) per WP, each dst in selected
) -> Dict:
    """
    Parameters
    ----------
    selected : list[str]
        1-3 Provinces to Raid.
    move_plan : list[(src, dst)]
        Optional movements of ONE WP each.  Each *dst* must be in *selected*,
        each *src* adjacent to its *dst*, and max 1 move per *dst*.
    """
    if faction != "INDIANS":
        raise ValueError("Only INDIANS may execute Raid.")

    if not (1 <= len(selected) <= 3):
        raise ValueError("Raid selects 1-3 Provinces.")

    move_plan = move_plan or []
    dragging_canoe_loc = leader_location(state, "LEADER_DRAGGING_CANOE") or leader_location(state, "DRAGGING_CANOE")
    initial_wp = {sid: sp.get(WARPARTY_U, 0) for sid, sp in state["spaces"].items()}
    dc_pool = initial_wp.get(dragging_canoe_loc, 0) if dragging_canoe_loc else 0
    dc_used = 0

    # ═══ validation ════════════════════════════════════════════════════════
    selected_set = set(selected)
    dst_seen: Set[str] = set()

    for space_id in selected:
        sp = state["spaces"][space_id]
        support_level = state.get("support", {}).get(space_id, NEUTRAL)
        if support_level not in OPPOSITION_ONLY:
            raise ValueError(f"{space_id} not at Opposition.")
        # must have an Underground WP locally or adjacent
        local_u = sp.get(WARPARTY_U, 0)
        adj_u = any(
            state["spaces"][nbr].get(WARPARTY_U, 0) > 0
            for nbr in state["spaces"] if is_adjacent(space_id, nbr)
        )
        dc_reach = False
        if dragging_canoe_loc and initial_wp.get(dragging_canoe_loc, 0) > 0:
            path = shortest_path(dragging_canoe_loc, space_id)
            dc_reach = bool(path) and (len(path) - 1) <= 2
        if (local_u == 0) and not adj_u and not dc_reach:
            raise ValueError(f"{space_id} lacks access to an Underground War-Party.")

    for src, dst in move_plan:
        if dst not in selected_set:
            raise ValueError(f"Move destination {dst} not among selected Provinces.")
        if dst in dst_seen:
            raise ValueError(f"Only one WP may move into {dst}.")
        path = shortest_path(src, dst)
        distance = len(path) - 1 if path else None
        started_in_dc = dragging_canoe_loc and src == dragging_canoe_loc and dc_pool > dc_used
        if started_in_dc and distance is not None and distance <= 2:
            dc_used += 1
        elif distance != 1:
            raise ValueError(f"{src} not within Raid move range of {dst}.")
        dst_seen.add(dst)

    # ═══ resource payment ══════════════════════════════════════════════════
    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(selected)
    cost = len(selected)
    spend(state, "INDIANS", cost)

    # ═══ execute ═══════════════════════════════════════════════════════════
    push_history(state, f"INDIANS RAID {selected}")

    # optional moves (kept Underground)
    for src, dst in move_plan:
        _move_one_wp(state,
                     state["spaces"][src], state["spaces"][dst],
                     src, dst)

    raids_state = state.setdefault("markers", {}).setdefault(RAID, {"pool": 0, "on_map": set()})

    for prov in selected:
        sp = state["spaces"][prov]

        # Activate one Underground WP (must exist after optional move)
        if sp.get(WARPARTY_U, 0) == 0:
            raise ValueError(f"{prov}: no Underground WP to Activate.")
        sp[WARPARTY_U] -= 1
        sp[WARPARTY_A] = sp.get(WARPARTY_A, 0) + 1

        # Place marker if pool available
        if raids_state.get("pool", 0) > 0:
            raids_state["pool"] -= 1
            raids_state.setdefault("on_map", set()).add(prov)
        # shift Opposition one step toward Neutral
        _shift_one_toward_neutral(state, prov)

    # bookkeeping
    refresh_control(state)
    enforce_global_caps(state)
    state.setdefault("log", []).append(f"INDIANS RAID {selected}")
    return ctx
