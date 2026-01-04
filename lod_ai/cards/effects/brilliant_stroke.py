"""
brilliant_strokes.py  –  cards 105-109
--------------------------------------
• 105  Patriots  – Brilliant Stroke!
• 106  British   – Brilliant Stroke!
• 107  French    – Brilliant Stroke!
• 108  Indians   – Brilliant Stroke!
• 109  Treaty of Alliance (special)

Each Brilliant-Stroke lets its faction execute **two free Limited Commands
+ one Special Activity** and immediately resets all Eligibility.  Instead of
trying to drive the engine right here, we just **queue** the request in
state["bs_queue"] so the turn loop can resolve it cleanly.

Treaty of Alliance (#109) queues a different key and sets
state["toa_played"] = True.  Flesh out the real engine logic later.
"""

from lod_ai.cards import register
from lod_ai.util.history import push_history
from lod_ai.util.free_ops import queue_free_op
from lod_ai.cards.effects.shared import adjust_fni
from lod_ai.board.pieces import move_piece, place_piece
from lod_ai import rules_consts as C
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_FRE,
    WEST_INDIES_ID,
    LEADER_ROCHAMBEAU,
    BLOCKADE,
)

# ------------------------------------------------ helper ------------------ #
def _queue_bs(state, faction: str | None):
    """
    Append a tuple to state['bs_queue']:
      ('BS', faction)   or   ('TOA', None)
    """
    key = "bs_queue"
    state.setdefault(key, []).append(("BS", faction))
    push_history(state, f"Brilliant Stroke queued for {faction or 'Treaty'}")


def maybe_play_brilliant_stroke(state, faction_has_card: dict[str, bool], faction: str) -> str | None:
    """
    Return the faction that should play Brilliant Stroke after checking trump order.
    Mutates *faction_has_card* to clear the trumped faction if another supersedes it.
    """
    priority = {
        C.PATRIOTS: 1,
        C.BRITISH: 2,
        C.FRENCH: 3,
        C.INDIANS: 4,
    }
    fac = faction.upper()
    if not faction_has_card.get(fac):
        return None

    for other, has_card in faction_has_card.items():
        other_fac = str(other).upper()
        if other_fac == fac or not has_card:
            continue
        if priority.get(other_fac, 0) > priority.get(fac, 0):
            push_history(state, f"{other_fac} trump {fac}'s Brilliant Stroke!")
            faction_has_card[fac] = False
            return other_fac
    return fac


def apply_reward_loyalty_cost(state, faction: str, loyalty_shift_levels: int) -> None:
    """
    Deduct Resources for Reward Loyalty executed inside a Brilliant Stroke sequence.
    Costs are not waived during BS; clamp at zero if insufficient Resources.
    """
    if loyalty_shift_levels <= 0:
        return
    fac = faction.upper()
    if fac not in (C.BRITISH, C.FRENCH):
        return
    current = state.setdefault("resources", {}).get(fac, 0)
    cost = max(0, loyalty_shift_levels)
    state["resources"][fac] = max(C.MIN_RESOURCES, current - cost)
    push_history(state, f"{fac} Reward Loyalty during Brilliant Stroke - paid {cost} Resources")

# ------------------------------------------------ 105-108 ------------------ #
_BS_FACTION = {
    105: "PATRIOTS",
    106: "BRITISH",
    107: "FRENCH",
    108: "INDIANS",
}

for _cid, _fac in _BS_FACTION.items():
    @register(_cid)                       # closure captures _cid/_fac
    def _make_bs(state, shaded=False, _f=_fac):
        """
        Queue a normal Brilliant-Stroke for *_f*.
        Engine will pop state['bs_queue'] and execute it.
        """
        _queue_bs(state, _f)
        # All factions become Eligible immediately
        state["ineligible_next"] = set()

# ------------------------------------------------ 109  Treaty ------------- #
@register(109)
def evt_109_treaty_of_alliance(state, shaded=False):
    """
    Treaty of Alliance – special Brilliant Stroke (card #109)
    Queues a 'TOA' entry and marks treaty as played.
    """
    available = state.get("available", {})
    blockade_pool = state.get("spaces", {}).get(WEST_INDIES_ID, {}).get(BLOCKADE, 0)
    blockade_pool += state.get("markers", {}).get(BLOCKADE, {}).get("pool", 0)
    preparations = available.get(REGULAR_FRE, 0) + blockade_pool + state.get("cbc", 0)

    if preparations <= 15:
        push_history(state, "Treaty of Alliance not legal (preparations ≤ 15)")
        return

    state["toa_played"] = True
    state["treaty_of_alliance"] = True

    # French free Muster in the West Indies and Rochambeau arrives there
    queue_free_op(state, "FRENCH", "muster", WEST_INDIES_ID)
    place_piece(state, LEADER_ROCHAMBEAU, WEST_INDIES_ID)
    state.setdefault("leaders", {})[LEADER_ROCHAMBEAU] = WEST_INDIES_ID

    # Shift FNI toward war (after TOA flag so Rule 1.9 does not block)
    adjust_fni(state, +1)

    # Reinforcements to West Indies: draw from Unavailable first
    moved_fre = move_piece(state, REGULAR_FRE, "unavailable", WEST_INDIES_ID, 3)
    if moved_fre < 3:
        place_piece(state, REGULAR_FRE, WEST_INDIES_ID, 3 - moved_fre)

    moved_bri = move_piece(state, REGULAR_BRI, "unavailable", WEST_INDIES_ID, 3)
    if moved_bri < 3:
        place_piece(state, REGULAR_BRI, WEST_INDIES_ID, 3 - moved_bri)

    # Queue the special Brilliant Stroke so engine can finish resolution
    state.setdefault("bs_queue", []).append(("TOA", None))
    push_history(state, "Treaty of Alliance queued")
    state["ineligible_next"] = set()
    state.setdefault("eligible_next", set()).clear()
    state["eligible"] = {fac: True for fac in ("BRITISH", "PATRIOTS", "INDIANS", "FRENCH")}
