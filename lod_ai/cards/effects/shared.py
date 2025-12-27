"""
lod_ai.cards.effects.shared
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tiny, deterministic helpers that ALL card‐effect modules can call.

* They mutate ONLY the passed-in ``state`` object.
* Every change is logged via ``push_history`` so undo/redo works.
* No randomness here — call ``state["rng"]`` in the handler itself
  if a card effect needs shuffling or choice.

Feel free to extend this file whenever another one-liner proves handy.
"""

from lod_ai.util.history import push_history  # adjust if your path differs
from lod_ai.board.pieces import (
    move_piece, place_piece, remove_piece, place_with_caps, place_marker
)
from lod_ai.rules_consts import MAX_FNI, MIN_RESOURCES, MAX_RESOURCES
from lod_ai.util.loss_mod import queue_loss_mod
from lod_ai.util.free_ops import queue_free_op
from lod_ai.economy import resources

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
MAX_SUPPORT   = 2     # active Support
MIN_SUPPORT   = -2    # active Opposition

# --------------------------------------------------------------------------- #
# Resource helpers
# --------------------------------------------------------------------------- #
def clamp_resources(state):
    """
    Clamp every faction’s Resources to the official 0-50 range.
    Call this once after you change *any* resource value.
    """
    resources.clamp_all(state)

_ALIAS = {
    "British": "BRITISH",  "BRITISH": "BRITISH",
    "Patriot": "PATRIOTS", "Patriots": "PATRIOTS", "PATRIOTS": "PATRIOTS",
    "French": "FRENCH",    "FRENCH": "FRENCH",
    "Indian": "INDIANS",   "Indians": "INDIANS",   "INDIAN": "INDIANS", "INDIANS": "INDIANS",
}
def _canon_faction(f: str) -> str:
    return _ALIAS.get(f, f).upper()

def add_resource(state, faction: str, amount: int) -> None:
    fac = _canon_faction(faction)
    state["resources"][fac] = state["resources"].get(fac, 0) + amount
    clamp_resources(state)
    push_history(state, f"{fac} Resources {'+' if amount >= 0 else ''}{amount}")

# --------------------------------------------------------------------------- #
# Support / Opposition helpers
# --------------------------------------------------------------------------- #
def shift_support(state, space_id: str, delta: int) -> None:
    """
    Shift Support in *space_id* by *delta* steps (+ = toward Patriots,
    – = toward Opposition).  Result is clamped to ±2.
    """
    cur0 = state.get("support", {}).get(space_id, 0)
    new = max(MIN_SUPPORT, min(MAX_SUPPORT, cur0 + delta))
    if new != cur0:
        state.setdefault("support", {})[space_id] = new
        push_history(state, f"Support shift in {space_id}: {cur0:+d} → {new:+d}")

# --------------------------------------------------------------------------- #
# French Navy Index clamp
# --------------------------------------------------------------------------- #
def adjust_fni(state, delta: int) -> None:
    """
    Add *delta* (±) to French Navy Index and clamp to 0-MAX_FNI.

    Rule 1.9: Ignore any FNI change before Treaty of Alliance (FNI stays 0).
    """
    before = state.get("fni_level", 0)

    if not state.get("toa_played", False):
        state["fni_level"] = 0
        push_history(state, "FNI remains 0 (Treaty of Alliance not yet played)")
        return

    state["fni_level"] = max(0, min(MAX_FNI, before + delta))
    push_history(state, f"FNI {before} → {state['fni_level']}")

def pick_cities(state, count: int = 1):
    """Return up to *count* City IDs sorted alphabetically."""
    cities = [n for n, info in state["spaces"].items() if info.get("type") == "City"]
    cities.sort()
    return cities[:count]


def pick_two_cities(state):
    """Return two City IDs; for now pick the first two alphabetically."""
    return pick_cities(state, 2)            # deterministic for tests


def pick_colonies(state, count: int = 1):
    """Return up to *count* Colony IDs sorted alphabetically."""
    colonies = [n for n, info in state["spaces"].items() if info.get("type") == "Colony"]
    colonies.sort()
    return colonies[:count]
