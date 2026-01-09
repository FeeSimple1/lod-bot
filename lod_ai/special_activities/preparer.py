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
• `state["markers"]["Blockade"]["pool"]`   – counters in West Indies (Squadrons).
• `state["markers"]["Blockade"]["on_map"]` – set of City IDs with Blockades.
• `state["unavailable"]["Blockade"]`       – unused Squadron/Blockade counters.
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
from lod_ai.util.naval import move_blockades_to_west_indies, total_blockades, unavailable_blockades

SA_NAME = "PREPARER"        # auto-discovered by special_activities/__init__.py

_BLOCKADE_CAP = 3           # total markers that exist in the game


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _count_all_blockades(state: Dict) -> int:
    return total_blockades(state)

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

    state["_turn_used_special"] = True
    push_history(state, f"FRENCH PREPARER choice={choice}")

    if choice == "BLOCKADE":
        total = _count_all_blockades(state)
        if total >= _BLOCKADE_CAP:
            raise ValueError("No unused Blockade markers remain to add.")
        if unavailable_blockades(state) <= 0:
            raise ValueError("No unused Blockade markers remain to add.")
        moved = move_blockades_to_west_indies(state, 1)
        if moved == 0:
            raise ValueError("West Indies Blockade pool is at capacity.")
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
