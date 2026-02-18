"""
lod_ai.special_activities.persuasion
====================================
Patriot-only Persuasion Special Activity  (§4.3.1).

• May accompany *any* Command.
• Patriots choose 1-3 Colonies/Cities that:
      – are Rebellion-controlled  (space["control"] == "REBELLION"),
      – contain ≥ 1 Underground Militia.

Procedure for each space:
   1. Flip 1 Underground Militia → Active.
   2. Add 1 Patriot Resource.
   3. Place a Propaganda marker (if cap < MAX_PROPAGANDA).

All bookkeeping (history, caps, control) handled here.
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.rules_consts import (
    MILITIA_U, MILITIA_A,
    PROPAGANDA, MAX_PROPAGANDA,
    PATRIOTS,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece, flip_pieces
from lod_ai.economy.resources import add as add_res
from lod_ai.map import adjacency as map_adj

SA_NAME = "PERSUASION"      # auto-registered by special_activities/__init__.py


# ────────────────────────────────────────────────────────────────────
# public entry
# ────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    *,
    spaces: List[str],
) -> Dict:
    """
    Parameters
    ----------
    spaces : list[str]
        1-3 Colony/City IDs meeting the eligibility criteria.
    """
    if faction != PATRIOTS:
        raise ValueError("Persuasion is a Patriot-only Special Activity.")
    if not 1 <= len(spaces) <= 3:
        raise ValueError("Persuasion must target 1-3 spaces.")

    state["_turn_used_special"] = True
    push_history(state, f"PATRIOTS PERSUASION {spaces}")

    marker_state = state.setdefault("markers", {}).setdefault(PROPAGANDA, {"pool": 0, "on_map": set()})
    marks_pool: set[str] = marker_state.setdefault("on_map", set())
    added_resources = 0
    added_markers   = 0

    for sid in spaces:
        sp = state["spaces"][sid]

        # ---- Eligibility checks -----------------------------------------
        if state.get("control", {}).get(sid) != "REBELLION":
            raise ValueError(f"{sid}: not Rebellion-controlled.")
        if sp.get(MILITIA_U, 0) == 0:
            raise ValueError(f"{sid}: no Underground Militia to Activate.")
        if map_adj.space_type(sid) not in ("Colony", "City"):
            raise ValueError(f"{sid}: Persuasion only in Colonies/Cities.")

        # ---- Flip exactly one Underground Militia ----------------------
        flip_pieces(state, MILITIA_U, MILITIA_A, sid, 1)

        # ---- Add Patriot Resource --------------------------------------
        add_res(state, PATRIOTS, 1)
        added_resources += 1


        # ---- Place Propaganda marker if pool available -----------------
        if marker_state.get("pool", 0) > 0 and len(marks_pool) < MAX_PROPAGANDA and sid not in marks_pool:
            marker_state["pool"] -= 1
            marker_state["on_map"].add(sid)
            added_markers += 1

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"PATRIOTS PERSUASION {spaces} +{added_resources}£, "
        f"{added_markers} Propaganda"
    )
    return ctx
