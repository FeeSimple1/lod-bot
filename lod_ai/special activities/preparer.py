"""
lod_ai.special_activities.preparer
==================================
French **Préparer la Guerre** SA  (§4.5.1).

* May accompany any Command **after the Treaty of Alliance**.
* Exactly ONE of the three effects must be chosen:

  1) "BLOCKADE"  – Move 1 Squadron/Blockade marker *to* the West Indies pool.
  2) "REGULARS"  – Move 3 French Regulars from *Unavailable* to *Available*.
  3) "RESOURCES" – Add 2 French Resources.

Assumptions about state schema
------------------------------
• `state["spaces"]["West_Indies"]["blockade"]`      – int count of markers in pool.
• Every City space has `space["blockade"]` (int, default 0).
• Global marker cap is 3 (physical game).
• Unavailable French Regulars are tracked in `state["unavailable"]["FRENCH"]`.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import REGULAR_FRE, FRENCH_UNAVAIL, BLOCKADE, WEST_INDIES_ID
from lod_ai.util.history  import push_history
from lod_ai.util.caps     import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece
from lod_ai.economy.resources import add as add_res

SA_NAME = "PREPARER"        # auto-discovered by special_activities/__init__.py

_BLOCKADE_CAP = 3           # total markers that exist in the game


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _count_all_blockades(state: Dict) -> int:
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    return bloc.get("pool", 0) + len(bloc.get("on_map", set()))

# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    *,
    choice: str,          # "BLOCKADE" | "REGULARS" | "RESOURCES"
) -> Dict:
    """
    Execute Préparer la Guerre.

    Parameters
    ----------
    choice
        "BLOCKADE", "REGULARS", or "RESOURCES".
    """

    if faction != "FRENCH":
        raise ValueError("Préparer la Guerre is French-only.")

    if not state.get("toa_played"):
        raise ValueError("Préparer la Guerre requires Treaty of Alliance.")

    choice = choice.upper()
    if choice not in ("BLOCKADE", "REGULARS", "RESOURCES"):
        raise ValueError("choice must be BLOCKADE, REGULARS, or RESOURCES.")

    push_history(state, f"FRENCH PREPARER choice={choice}")

    if choice == "BLOCKADE":
        markers = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
        total = _count_all_blockades(state)
        if total >= _BLOCKADE_CAP:
            raise ValueError("No unused Blockade markers remain to add.")
        markers["pool"] = markers.get("pool", 0) + 1
        state.setdefault("log", []).append("FRENCH Préparer: +1 Blockade to West Indies pool")

    elif choice == "REGULARS":
        # Move 3 Regulars from Unavailable → Available
        remove_piece(state, REGULAR_FRE, "unavailable", 3)

    else:  # RESOURCES
        add_res(state, "FRENCH", 2)
        state.setdefault("log", []).append("FRENCH Préparer: +2 £")

    refresh_control(state)
    enforce_global_caps(state)
    return ctx
