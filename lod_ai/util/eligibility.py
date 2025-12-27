"""
lod_ai.util.eligibility
=======================
Helpers for manipulating Sequence-of-Play eligibility flags.

Two convenience sets are stored on ``state``:
    • ``state["remain_eligible"]`` – factions that should *not* flip to
      Ineligible after completing their current Event/Command.
    • ``state["ineligible_through_next"]`` – factions forced to skip the
      next card’s Sequence of Play (in addition to the current one).
"""

from __future__ import annotations

from typing import Dict, Iterable

def mark_remain_eligible(state: Dict, faction: str) -> None:
    state.setdefault("remain_eligible", set()).add(faction.upper())

def clear_remain_eligible(state: Dict, faction: str) -> None:
    state.setdefault("remain_eligible", set()).discard(faction.upper())

def mark_ineligible_through_next(state: Dict, faction: str) -> None:
    state.setdefault("ineligible_through_next", set()).add(faction.upper())

def consume_ineligible_through_next(state: Dict) -> Iterable[str]:
    """Pop and return any factions marked through-next-card ineligibility."""
    return state.pop("ineligible_through_next", set())
