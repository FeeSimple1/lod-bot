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
from lod_ai.util.naval import unavailable_blockades, total_blockades
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
    """French Preparations = Available French Regulars + Squadrons/Blockades
    + Cumulative British Casualties (§2.3.9)."""
    available = state.get("available", {})
    fre_regs = available.get(REGULAR_FRE, 0)
    naval = total_blockades(state)
    cbc = state.get("cbc", 0)
    return fre_regs + naval + cbc


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


# ------------------------------------------------ piece thresholds ---------- #
# The bot-trigger conditions for each faction's BS card.
_LEADER_PIECE_THRESHOLD = {
    C.BRITISH:  ({"LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"},
                 (C.REGULAR_BRI,), 4),
    C.PATRIOTS: ({"LEADER_WASHINGTON"},
                 (C.REGULAR_PAT,), 4),
    C.FRENCH:   ({"LEADER_ROCHAMBEAU", "LEADER_LAUZUN"},
                 (C.REGULAR_FRE,), 4),
    C.INDIANS:  ({"LEADER_BRANT", "LEADER_CORNPLANTER", "LEADER_DRAGGING_CANOE"},
                 (C.WARPARTY_A, C.WARPARTY_U), 3),
}

REBELLION_FACTIONS = {C.PATRIOTS, C.FRENCH}


def _leader_with_pieces(state, faction: str) -> bool:
    """Return True if *faction* has a Leader in a space meeting its piece threshold."""
    entry = _LEADER_PIECE_THRESHOLD.get(faction)
    if not entry:
        return False
    leaders, piece_tags, threshold = entry
    for leader in leaders:
        loc = leader_location(state, leader)
        if not loc:
            continue
        sp = state.get("spaces", {}).get(loc, {})
        total = sum(sp.get(tag, 0) for tag in piece_tags)
        if total >= threshold:
            return True
    return False


def bot_wants_bs(
    state,
    faction: str,
    first_eligible: str | None = None,
    human_factions: set | None = None,
    other_bs_faction: str | None = None,
) -> bool:
    """Evaluate whether a bot faction wants to play its Brilliant Stroke.

    Per §8.3.7, §8.4.11, §8.5.8, §8.6.11, §8.7.8:
    - All bot BS triggers require Treaty of Alliance to have been played.
    - Each faction has Leader+piece threshold AND a situational trigger.

    Parameters
    ----------
    first_eligible : str or None
        The 1st-eligible faction for this card.
    human_factions : set
        Factions controlled by human players.
    other_bs_faction : str or None
        If another faction is currently playing a BS, this is their faction.
        Used for trumping triggers ("OR Patriots play their BS", etc.).
    """
    if human_factions is None:
        human_factions = set()

    # Prerequisite: ToA must have been played already
    if not state.get("toa_played", False):
        return False

    # Must still hold the BS card
    if not bs_available(state, faction):
        return False

    # Must be eligible
    if not state.get("eligible", {}).get(faction, True):
        return False

    # Must have leader + pieces
    if not _leader_with_pieces(state, faction):
        return False

    # ---- Faction-specific situational trigger ----
    is_player = lambda f: f in human_factions

    if faction == C.BRITISH:
        # "a Rebellion player Faction is 1st Eligible OR Patriots play their BS"
        rebellion_player_1st = (
            first_eligible in REBELLION_FACTIONS and is_player(first_eligible)
        )
        pat_plays_bs = (other_bs_faction == C.PATRIOTS)
        return rebellion_player_1st or pat_plays_bs

    if faction == C.PATRIOTS:
        # "a player Faction is 1st Eligible"
        return first_eligible is not None and is_player(first_eligible)

    if faction == C.FRENCH:
        # "any player Faction is 1st Eligible OR the British play their BS"
        player_1st = first_eligible is not None and is_player(first_eligible)
        brit_plays_bs = (other_bs_faction == C.BRITISH)
        return player_1st or brit_plays_bs

    if faction == C.INDIANS:
        # "any player Faction is 1st Eligible OR a Rebellion Faction plays
        #  a BS card other than Treaty of Alliance"
        player_1st = first_eligible is not None and is_player(first_eligible)
        reb_plays_bs = (other_bs_faction in REBELLION_FACTIONS)
        return player_1st or reb_plays_bs

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
# Each BS card event:
#   1. Records a declaration (for the engine's interrupt/trump system)
#   2. Resets all factions to Eligible (per card text)
#   3. Logs the play
# NOTE: The engine marks the card as played during trump resolution
# (not here) because _bs_is_legal checks bs_available.
# Actual execution of 2 LimComs + 1 SA is handled by the engine
# (bot: _execute_bot_brilliant_stroke; human: _execute_human_bs_plan).

def _bs_event(state, faction):
    """Common BS event handler for cards 105-108.

    Records a declaration for the engine's interrupt/trump system to pick up.
    The engine handles marking the card as played and executing the 2 LimCom +
    1 SA per S8.3.7.  Eligibility is reset here per the card text; the engine
    also resets it independently so the order does not matter.
    """
    if not bs_available(state, faction):
        push_history(state, f"{faction} Brilliant Stroke already played")
        return
    state.setdefault("bs_declarations", []).append(faction)
    # All Factions to Eligible (per card text)
    state["eligible"] = {
        C.BRITISH: True, C.PATRIOTS: True,
        C.FRENCH: True, C.INDIANS: True,
    }
    push_history(state, f"{faction} plays Brilliant Stroke")


@register(105)
def evt_105_bs_patriots(state, shaded=False):
    """Brilliant Stroke! (Patriots) -- card #105.
    Execute two free Limited Commands and one Special Activity.
    Leader must be involved in at least one LimCom.
    All Factions to Eligible."""
    _bs_event(state, C.PATRIOTS)


@register(106)
def evt_106_bs_british(state, shaded=False):
    """Brilliant Stroke! (British) -- card #106.
    Execute two free Limited Commands and one Special Activity.
    Leader must be involved in at least one LimCom.
    Note: Reward Loyalty is NOT free.
    British may Trump Patriot Brilliant Stroke.
    All Factions to Eligible."""
    _bs_event(state, C.BRITISH)


@register(107)
def evt_107_bs_french(state, shaded=False):
    """Brilliant Stroke! (French) -- card #107.
    Execute two free Limited Commands and one Special Activity.
    Leader must be involved in at least one LimCom.
    French may Trump Patriot or British Brilliant Stroke.
    All Factions to Eligible."""
    _bs_event(state, C.FRENCH)


@register(108)
def evt_108_bs_indians(state, shaded=False):
    """Brilliant Stroke! (Indians) -- card #108.
    Execute two free Limited Commands and one Special Activity.
    Leader must be involved in at least one LimCom.
    Indians may Trump Patriot, British or French Brilliant Stroke.
    All Factions to Eligible."""
    _bs_event(state, C.INDIANS)


# ------------------------------------------------ 109  Treaty ------------- #
@register(109)
def evt_109_treaty_of_alliance(state, shaded=False):
    """Treaty of Alliance -- special Brilliant Stroke (card #109).
    If French Preparations > 15, French enter the war:
    - French free Muster and place Rochambeau in West Indies
    - Raise FNI one level
    - Place 3 French and 3 British Regulars in West Indies
    - May Trump any Brilliant Stroke
    - All Factions to Eligible."""
    if apply_treaty_of_alliance(state):
        state.setdefault("bs_declarations", []).append(TOA_KEY)
        state["eligible"] = {
            C.BRITISH: True, C.PATRIOTS: True,
            C.FRENCH: True, C.INDIANS: True,
        }
        push_history(state, "Treaty of Alliance played")
