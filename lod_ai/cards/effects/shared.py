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
    move_piece, place_piece, remove_piece, place_with_caps, place_marker,
    flip_pieces,
)
from lod_ai.rules_consts import MAX_FNI, MIN_RESOURCES, MAX_RESOURCES, BRITISH, PATRIOTS, FRENCH, INDIANS
from lod_ai.util.loss_mod import queue_loss_mod
from lod_ai.map import adjacency as _madj
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
    "British": BRITISH,  BRITISH: BRITISH,
    "Patriots": PATRIOTS, PATRIOTS: PATRIOTS,
    "French": FRENCH,    FRENCH: FRENCH,
    "Indians": INDIANS,   INDIANS: INDIANS,
}
def _canon_faction(f: str) -> str:
    return _ALIAS.get(f, f).upper()

def add_resource(state, faction: str, amount: int) -> None:
    fac = _canon_faction(faction)
    resources_map = state.setdefault("resources", {})
    resources_map[fac] = resources_map.get(fac, 0) + amount
    clamp_resources(state)
    push_history(state, f"{fac} Resources {'+' if amount >= 0 else ''}{amount}")

# --------------------------------------------------------------------------- #
# Support / Opposition helpers
# --------------------------------------------------------------------------- #
def shift_support(state, space_id: str, delta: int) -> None:
    """
    Shift Support/Opposition in *space_id* by *delta* steps.

    +delta shifts toward Support (up to +2 / Active Support).
    -delta shifts toward Opposition (down to -2 / Active Opposition).

    Result is clamped to [-2, +2].
    """
    # §1.6.1: spaces with 0 Population (the four Indian Reserves and the West
    # Indies) are always Neutral and never hold Support/Opposition markers.
    if _madj.space_type(space_id) in ("Reserve", "Special"):
        return
    cur0 = state.get("support", {}).get(space_id, 0)
    new = max(MIN_SUPPORT, min(MAX_SUPPORT, cur0 + delta))
    if new != cur0:
        state.setdefault("support", {})[space_id] = new
        push_history(state, f"Support shift in {space_id}: {cur0:+d} → {new:+d}")

# --------------------------------------------------------------------------- #
# French Navy Index clamp
# --------------------------------------------------------------------------- #
# adjust_fni lives in lod_ai.util.naval (its natural home, alongside the
# Blockade / FNI helpers and the §1.9 / §4.5.3 ceiling). Re-exported here so
# the card-effect modules and the Naval Pressure SA that import it from this
# module keep working through a single implementation.
from lod_ai.util.naval import adjust_fni  # noqa: F401

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
