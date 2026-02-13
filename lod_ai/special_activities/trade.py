"""
lod_ai.special_activities.trade
===============================
Indian **Trade** SA (§4.4.1).

* May accompany any Command.
* Eligible space: **one Province** containing BOTH
      – ≥1 Underground War-Party, and
      – ≥1 Village.

Procedure
---------
• Caller supplies `transfer` ≥ 0.
    – If transfer > 0 → move that many Resources from BRITISH to INDIANS.
    – If transfer == 0 → INDIANS gain 1 Resource (British pay nothing).
• Then: **Activate** exactly ONE Underground War-Party in the chosen
  Province (flip WARPARTY_U → WARPARTY_A).

All bookkeeping (history, caps, control) is handled here.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import WARPARTY_U, WARPARTY_A, VILLAGE, MAX_RESOURCES, INDIANS, BRITISH
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece
from lod_ai.economy.resources import spend, add as add_res

SA_NAME = "TRADE"          # auto-registered by special_activities/__init__.py


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    space_id: str,
    *,
    transfer: int = 0,           # Resources British → Indians
) -> Dict:
    """
    Parameters
    ----------
    space_id : str
        Province ID that hosts the Trade.
    transfer : int, default 0
        Amount of Resources the British will give the Indians.
        If 0, Indians instead gain 1 Resource at no British cost.
    """

    if faction != INDIANS:
        raise ValueError("Trade is an Indian-only Special Activity.")
    if transfer < 0:
        raise ValueError("transfer cannot be negative.")

    state["_turn_used_special"] = True
    sp = state["spaces"][space_id]

    # Eligibility checks
    if sp.get(WARPARTY_U, 0) == 0:
        raise ValueError("Trade requires at least one Underground War-Party.")
    if sp.get(VILLAGE, 0) == 0:
        raise ValueError("Trade requires a Village in the Province.")

    # Resource availability
    if transfer > state["resources"][BRITISH]:
        raise ValueError("BRITISH lack Resources to transfer.")

    push_history(state, f"INDIANS TRADE in {space_id} (transfer={transfer})")

    # Resource transfer
    if transfer > 0:
        spend(state, BRITISH, transfer)
        add_res(state, INDIANS, transfer)
    else:           # transfer == 0
        gain = state["rng"].randint(1, 3)
        state.setdefault("rng_log", []).append(("Trade D3", gain))
        state["resources"][INDIANS] = min(MAX_RESOURCES, state["resources"][INDIANS] + gain)
        push_history(state, f"Indians Trade: +{gain} Resources (to {state['resources'][INDIANS]})")

    # Activate exactly one WP
    remove_piece(state, WARPARTY_U, space_id, 1)
    add_piece(state, WARPARTY_A, space_id, 1)

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"INDIANS TRADE {space_id} transfer={transfer}"
    )
    return ctx
