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
    """Return up to *count* City IDs in sorted order.

    ONLY for gathering the full candidate list (pass a count >= number of
    spaces), where order is irrelevant. Do NOT use to select a subset: event
    space selection must follow §8.3.5/§8.3.6 priorities with §8.2 random
    tie-breaks (see select_support_shift_spaces / pick_random_spaces).
    """
    # Session 48: real game states carry no "type" key in the space
    # dicts — use the map metadata (dict "type" kept as a fallback for
    # bare test fixtures).  Before this, pick_cities returned [] in
    # every real game (e.g. card 32 shaded always paid 0 Resources).
    cities = [n for n, info in state["spaces"].items()
              if (_madj.space_type(n) or info.get("type")) == "City"]
    cities.sort()
    return cities[:count]


def pick_colonies(state, count: int = 1):
    """Return up to *count* Colony IDs in sorted order.

    Same caveat as pick_cities: full-list use only, never subset selection.
    """
    colonies = [n for n, info in state["spaces"].items()
                if (_madj.space_type(n) or info.get("type")) == "Colony"]
    colonies.sort()
    return colonies[:count]


# --------------------------------------------------------------------------- #
# Non-player Event space selection (§8.3.5 / §8.3.6 / §8.2)
# --------------------------------------------------------------------------- #
# §8.2 tie-break picks for candidates of EQUAL priority (re-exported so card
# modules have a single import site).
from lod_ai.bots.random_spaces import pick_random_spaces  # noqa: E402


def _walk_toward(cur: int, target: int, steps: int) -> int:
    """Result of shifting *cur* up to *steps* levels toward *target*."""
    new = cur
    for _ in range(steps):
        if new == target:
            break
        new += 1 if new < target else -1
    return max(MIN_SUPPORT, min(MAX_SUPPORT, new))


def select_support_shift_spaces(state, candidates, count, *, target: int,
                                steps: int = 1, shaded=None):
    """Select *count* spaces for an Event Support/Opposition shift.

    §8.3.5 routes Event shift-space selection to §8.3.6: Royalist factions
    select "for the highest gain in Support, then the highest loss in
    Opposition"; Rebellion factions the reverse. Gain/loss is Population-
    weighted (§8.1.1: level times Population), with Active counting double
    Passive (§1.6.2) — both fall out of the ±2/±1 support encoding times
    Population. Candidates tied on the §8.3.6 key are resolved by the §8.2
    Random Spaces table (per §8.1/§8.2, random selection applies only among
    candidates of EQUAL priority).

    The executing side comes from state["active"] when set (base_bot sets it
    during event execution), else from *shaded* per §8.3.2 (Non-player
    Patriot/French execute the shaded text, British/Indian the unshaded).
    Zero-gain candidates outrank negative-gain ones, so an event forced to
    select spaces never shifts a space against the executing side while a
    harmless space exists. The §8.3.3 net-shift guard (base_bot) keeps bots
    from playing an event whose net shift favors the enemy at all.
    """
    active = state.get("active")
    if active is not None:
        royalist = _canon_faction(str(active)) in (BRITISH, INDIANS)
    elif shaded is not None:
        royalist = not shaded
    else:
        royalist = True

    support = state.get("support", {})

    def gain_key(sid):
        pop = _madj.population(sid)
        cur = support.get(sid, 0)
        new = _walk_toward(cur, target, steps)
        support_gain = (max(new, 0) - max(cur, 0)) * pop
        opposition_gain = (max(-new, 0) - max(-cur, 0)) * pop
        if royalist:
            return (support_gain, -opposition_gain)
        return (opposition_gain, -support_gain)

    chosen: list = []
    remaining = list(dict.fromkeys(candidates))
    while remaining and len(chosen) < count:
        best = max(gain_key(s) for s in remaining)
        ties = [s for s in remaining if gain_key(s) == best]
        pick = ties[0] if len(ties) == 1 else pick_random_spaces(state, ties, 1)[0]
        chosen.append(pick)
        remaining.remove(pick)
    return chosen
