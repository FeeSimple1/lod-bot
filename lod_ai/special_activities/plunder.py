"""
lod_ai.special_activities.plunder
=================================
Indian **Plunder** (§4.4.3).

* May accompany a Raid **only** (caller sets ctx["raid_active"]=True).
* Province must be part of that Raid, with War-Parties > Rebellion pieces.

Procedure
---------
1. Transfer Resources equal to the Province’s population
   (but not more than Patriots actually have) from PATRIOTS → INDIANS.
2. Flip & remove **one** War-Party from the Province.
   – Prefer an Underground WP; if none, take an Active WP.
   – The removed WP returns to the Indians’ *Available* pool.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import (
    WARPARTY_U, WARPARTY_A,
    REGULAR_PAT, REGULAR_FRE, MILITIA_A, MILITIA_U, FORT_PAT,
    INDIANS, PATRIOTS,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece
from lod_ai.economy.resources import spend, add as add_res
from lod_ai.map             import adjacency as map_adj

SA_NAME = "PLUNDER"   # auto-registered by special_activities/__init__.py

# §4.4.3: "Rebellion pieces" includes all Patriot/French pieces
REB_TAGS = (REGULAR_PAT, REGULAR_FRE, MILITIA_A, MILITIA_U, FORT_PAT)


def _remove_one_wp(state: Dict, province: str) -> None:
    """Remove one War-Party from *province* (pref Underground) to Available."""
    sp = state["spaces"][province]
    if sp.get(WARPARTY_U, 0):
        remove_piece(state, WARPARTY_U, province, 1, to="available")
    elif sp.get(WARPARTY_A, 0):
        remove_piece(state, WARPARTY_A, province, 1, to="available")
    else:
        raise ValueError("No War Parties remaining to remove.")

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    province: str,
) -> Dict:

    if faction != INDIANS:
        raise ValueError("Plunder is Indian-only.")

    if not ctx.get("raid_active"):
        raise ValueError("Plunder can only follow a Raid Command this turn.")

    state["_turn_used_special"] = True
    sp = state["spaces"][province]

    wp_total  = sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0)
    reb_total = sum(sp.get(t, 0) for t in REB_TAGS)
    if wp_total <= reb_total:
        raise ValueError("War Parties do not exceed Rebellion pieces here.")

    meta = map_adj.space_meta(province) or {}
    pop = meta.get("population", 0)
    if pop <= 0:
        raise ValueError("Province has no population to plunder.")

    push_history(state, f"INDIANS PLUNDER begins in {province} (pop={pop})")

    # Resource transfer
    stolen = min(pop, state["resources"][PATRIOTS])
    spend(state, PATRIOTS, stolen)
    add_res(state,  INDIANS,  stolen)

    # Remove one War-Party (returns to pool)
    _remove_one_wp(state, province)

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"INDIANS PLUNDER {province} pop={pop} → transfer {stolen}£"
    )
    return ctx
