from __future__ import annotations
"""lod_ai.commands.french_agent_mobilization
===================================================================
French **Agent Mobilization** Command implementation (rules §3.5.1).

* **Faction**: FRENCH only.
* **When**: *Before* the Treaty of Alliance is played (``state.get("toa_played")``
  must be ``False`` or absent).
* **Cost**: 1 French Resource total.
* **Valid province**: exactly one of ``{"Quebec", "New_York", "New_Hampshire", "Massachusetts"}``.
* **Effect**: Place **2 Patriot Militia (Underground)** *or* **1 Continental** in
  the selected space.  The caller chooses via the boolean ``place_continental``
  kw‑arg.

The code is deterministic, history‑logged, and keeps global caps in sync.
It deliberately exposes no AI: the solo flowchart (in ``bots/``) decides
whether to place Militia or Continentals.
"""

from typing import Dict

from lod_ai.rules_consts import (
    ACTIVE_SUPPORT, NEUTRAL,
    REGULAR_PAT,    # Continentals
    MILITIA_U,      # Patriot Militia (Underground)
    FRENCH,
)
from lod_ai.util.history  import push_history
from lod_ai.util.caps     import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import add_piece
from lod_ai.economy.resources import spend, can_afford

COMMAND_NAME = "FRENCH_AGENT_MOBILIZATION"   # auto‑registered

_VALID_PROVINCES = {"Quebec", "New_York", "New_Hampshire", "Massachusetts"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _take_from_pool(state: Dict, tag: str, n: int):
    """Remove *n* pieces of *tag* from the pool, raising if unavailable."""
    pool = state["pool"]
    available = pool.get(tag, 0)
    if available < n:
        raise ValueError(f"Pool exhausted: need {n} {tag}, only {available} left.")
    pool[tag] = available - n


def _add_to_space(sp: Dict, tag: str, n: int, underground: bool = False):
    """Add *n* pieces to a space dict.  Militia/War‑party underground flag is the
    caller's concern (pass MILITIA_U for underground militia)."""
    sp[tag] = sp.get(tag, 0) + n


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    province: str,
    *,
    place_continental: bool = False,
) -> Dict:
    """Perform the French Agent Mobilization Command.

    Parameters
    ----------
    province : str
        One of the four allowed provinces.  Provinces at Active Support are
        invalid.
    place_continental : bool, optional
        If *True*, place 1 Continental; otherwise place 2 Underground Militia.
    """
    if faction != FRENCH:
        raise ValueError("Only FRENCH may execute Agent Mobilization.")

    # Treaty gate ------------------------------------------------------------
    if state.get("toa_played"):
        raise ValueError("Agent Mobilization unavailable after Treaty of Alliance.")

    # Province validation ----------------------------------------------------
    if province not in _VALID_PROVINCES:
        raise ValueError(f"{province} is not a valid province for Agent Mobilization.")

    sp = state["spaces"].get(province)
    if sp is None:
        raise KeyError(f"Space {province} not found in state['spaces'].")

    if state.get("support", {}).get(province, NEUTRAL) == ACTIVE_SUPPORT:
        raise ValueError("Cannot mobilize agents in a province at Active Support.")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).add(province)
    # Resource cost ----------------------------------------------------------
    spend(state, FRENCH, 1)

    # All validations passed – record history before mutating ---------------
    push_history(state, f"FRENCH AGENT MOBILIZATION in {province}")

    if place_continental:
        add_piece(state, REGULAR_PAT, province, 1)
    else:
        add_piece(state, MILITIA_U, province, 2)

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        (
            f"FRENCH AGENT_MOBILIZATION {province} -> "
            f"{'1 Continental' if place_continental else '2 Militia'}"
        )
    )
    return ctx
