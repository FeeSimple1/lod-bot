from __future__ import annotations
"""lod_ai.commands.hortelez
===================================================================
French **Roderigue Hortalez et Cie** Command (rules §3.5.2).

* **Faction**: FRENCH only.
* **When** : Any time (before *or* after Treaty of Alliance).
* **Procedure**: French pay *N* Resources → Patriot Resources += *N + 1*.
"""

from typing import Dict
from lod_ai.util.history import push_history
from lod_ai.economy.resources import spend, add

COMMAND_NAME = "HORTELEZ"          # auto-registered by commands/__init__.py


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    pay: int,
) -> Dict:
    """Perform the Hortelez Command.

    Parameters
    ----------
    pay : int
        Resources the French will spend (must be ≥ 1 and ≤ current French
        Resources).
    """
    if faction != "FRENCH":
        raise ValueError("Only FRENCH may execute the Hortelez command.")

    if pay < 1:
        raise ValueError("Must pay at least 1 Resource.")
    french_res = state["resources"].get("FRENCH", 0)
    if french_res < pay:
        raise ValueError(f"FRENCH have only {french_res} Resources, cannot pay {pay}.")

    state["_turn_command"] = COMMAND_NAME
    state["_turn_command_meta"] = {"pay": pay}
    state.setdefault("_turn_affected_spaces", set())
    # Record state before mutation
    push_history(state, f"FRENCH HORTELEZ pay {pay}")

    # Transfer Resources
    spend(state, "FRENCH", pay)
    add(state,   "PATRIOTS", pay + 1)

    # Log
    state.setdefault("log", []).append(
        f"FRENCH HORTELEZ pay {pay} → PATRIOTS +{pay + 1}"
    )

    return ctx
