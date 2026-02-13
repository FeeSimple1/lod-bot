"""
brilliant_stroke.py  –  cards 105-109
------------------------------------
• 105  Patriots  – Brilliant Stroke!
• 106  British   – Brilliant Stroke!
• 107  French    – Brilliant Stroke!
• 108  Indians   – Brilliant Stroke!
• 109  Treaty of Alliance (special Brilliant Stroke)
"""

from lod_ai.cards import register
from lod_ai.util.history import push_history
from lod_ai.util.free_ops import queue_free_op
from lod_ai.cards.effects.shared import adjust_fni
from lod_ai.board.pieces import move_piece, place_piece
from lod_ai import rules_consts as C
from lod_ai.leaders import leader_location
from lod_ai.util.naval import unavailable_blockades
from lod_ai.rules_consts import (
    REGULAR_BRI,
    REGULAR_FRE,
    WEST_INDIES_ID,
    LEADER_ROCHAMBEAU,
)

# ------------------------------------------------ helpers ------------------ #
BS_CARD_BY_FACTION = {
    105: C.PATRIOTS,
    106: C.BRITISH,
    107: C.FRENCH,
    108: C.INDIANS,
}


FACTION_BY_BS_CARD = {fac: cid for cid, fac in BS_CARD_BY_FACTION.items()}
TOA_CARD_ID = 109
TOA_KEY = "TOA"

FACTION_LEADERS = {
    C.BRITISH: {"LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"},
    C.PATRIOTS: {"LEADER_WASHINGTON"},
    C.FRENCH: {"LEADER_ROCHAMBEAU", "LEADER_LAUZUN"},
    C.INDIANS: {"LEADER_BRANT", "LEADER_CORNPLANTER", "LEADER_DRAGGING_CANOE"},
}

FACTION_PIECES = {
    C.BRITISH: (C.REGULAR_BRI, C.TORY, C.FORT_BRI),
    C.PATRIOTS: (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT),
    C.FRENCH: (C.REGULAR_FRE,),
    C.INDIANS: (C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE),
}


def bs_played_map(state) -> dict:
    return state.setdefault("bs_played", {})


def bs_available(state, faction: str) -> bool:
    return not bs_played_map(state).get(faction, False)


def toa_available(state) -> bool:
    return not state.get("toa_played", False) and not bs_played_map(state).get(TOA_KEY, False)


def mark_bs_played(state, key: str, played: bool) -> None:
    bs_played_map(state)[key] = played


def preparations_total(state) -> int:
    available = state.get("available", {})
    return available.get(REGULAR_FRE, 0) + unavailable_blockades(state) + state.get("cbc", 0)


def leader_can_involve(state, faction: str) -> bool:
    """Return True if any leader for *faction* can be involved in a Limited Command."""
    leaders = FACTION_LEADERS.get(faction, set())
    pieces = FACTION_PIECES.get(faction, ())
    for leader in leaders:
        loc = leader_location(state, leader)
        if not loc:
            continue
        sp = state.get("spaces", {}).get(loc, {})
        if any(sp.get(tag, 0) for tag in pieces):
            return True
    return False


def apply_treaty_of_alliance(state) -> bool:
    """Apply Treaty of Alliance effects. Return True if resolved."""
    if not toa_available(state):
        push_history(state, "Treaty of Alliance already played")
        return False
    if preparations_total(state) <= 15:
        push_history(state, "Treaty of Alliance not legal (preparations ≤ 15)")
        return False

    state["toa_played"] = True
    state["treaty_of_alliance"] = True

    # French free Muster in the West Indies and Rochambeau arrives there
    queue_free_op(state, C.FRENCH, "muster", WEST_INDIES_ID)
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

    return True

# ------------------------------------------------ 105-108 ------------------ #
for _cid, _fac in BS_CARD_BY_FACTION.items():
    @register(_cid)                       # closure captures _cid/_fac
    def _make_bs(state, shaded=False, _f=_fac):
        """
        Record a Brilliant-Stroke declaration for *_f*.
        """
        state.setdefault("bs_declarations", []).append(_f)

# ------------------------------------------------ 109  Treaty ------------- #
@register(109)
def evt_109_treaty_of_alliance(state, shaded=False):
    """
    Treaty of Alliance – special Brilliant Stroke (card #109)
    """
    if apply_treaty_of_alliance(state):
        state.setdefault("bs_declarations", []).append(TOA_KEY)
