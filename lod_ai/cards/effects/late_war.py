"""
late_war.py – Event handlers for 1779-1780 cards
------------------------------------------------
IDs: 1 7 16 18 19 21 22 23 25 31 36 37 39 40
     45 48 52 57 62 64 65 66 67 70 73 79
     81 85 87 94 95 96
"""

from lod_ai.cards import register
from .shared import add_resource, shift_support, push_history

# --------------------------------------------------------------------------- #
# helper for un-implemented, piece-heavy events
# --------------------------------------------------------------------------- #
def _todo(state):
    push_history(state, "TODO: late-war event not yet implemented")


# 1  WAXHAWS MASSACRE
from lod_ai.rules_consts import (
    REGULAR_BRI,          # British Regular cube tag
    CONTINENTAL_PAT,      # Patriot Continental cube tag
    PROP                  # Propaganda marker tag
)
from lod_ai.util.history import push_history
from lod_ai.util.free_ops import queue_free_op
from lod_ai.board.pieces import remove_piece, place_marker
from lod_ai.util.support import shift_support
from lod_ai.events import register


@register(1)
def evt_001_waxhaws(state, shaded=False):
    """
    Unshaded – In any 1 space with British pieces,
               • remove 2 Continentals to Casualties
               • shift Support 1 toward Active Support
               • place 2 Propaganda
    Shaded   – Patriots free March to and free Battle in any 1 space;
               then place 2 Propaganda and shift 1 toward Neutral.
    """
    # choose the first eligible space (deterministic placeholder)
    eligible = [
        sid for sid, sp in state["spaces"].items()
        if sp.get(REGULAR_BRI)      # has British pieces
    ]
    if not eligible:
        push_history(state, "Waxhaws: no space with British pieces — no effect")
        return
    target = eligible[0]

    if shaded:
        queue_free_op(state, "PATRIOTS", "march_battle", target)
        place_marker(state, PROP, target, 2)
        shift_support(state, target, -1)     # toward Neutral
        push_history(state, f"Waxhaws (shaded): March/Battle in {target}, +2 PROP, Support −1")
    else:
        remove_piece(state, CONTINENTAL_PAT, target, 2, to="casualties")
        shift_support(state, target, +1)     # toward Active Support
        place_marker(state, PROP, target, 2)
        push_history(state, f"Waxhaws (unshaded): −2 Continentals in {target}, Support +1, +2 PROP")

# 7  JOHN PAUL JONES
@register(7)
def evt_007_john_paul_jones(state, shaded=False):
    if shaded:
        add_resource(state, "Patriots", +5)
        state["fni_level"] = min(4, state.get("fni_level", 0) + 1)
    else:
        add_resource(state, "British",  +3)
        state["fni_level"] = max(0, state.get("fni_level", 0) - 1)
    # TODO: move Regulars between pools & West Indies


# 16  MERCY WARREN’S “THE MOTLEY ASSEMBLY”
@register(16)
def evt_016_mercy_warren(state, shaded=False):
    if shaded:
        city = "Boston"              # placeholder selection
        shift_support(state, city, -1)
    else:
        _todo(state)                 # place 2 Tories anywhere


# 18  “IF IT HADN’T BEEN SO STORMY…”
@register(18)
def evt_018_if_not_stormy(state, shaded=False):
    affected = "PATRIOTS" if shaded else "BRITISH"
    state.setdefault("ineligible_next", set()).add(affected)


# 19  LEGEND OF NATHAN HALE
@register(19)
def evt_019_nathan_hale(state, shaded=False):
    if shaded:
        _todo(state)                 # place 3 Militia
        add_resource(state, "Patriots", +3)
    else:
        add_resource(state, "Patriots", -4)


# 21  THE GAMECOCK THOMAS SUMTER
@register(21)
def evt_021_sumter(state, shaded=False):
    """
    Unshaded – Shift SC or GA 2 levels toward Active Support.
    Shaded   – Patriots free March to and free Battle in SC or GA.
    """
    from lod_ai.util.free_ops import queue_free_op
    colony = "South_Carolina"

    if shaded:
        queue_free_op(state, "PATRIOTS", "march_battle", colony)
    else:
        shift_support(state, colony, +2)


# 22  THE NEWBURGH CONSPIRACY
@register(22)
def evt_022_newburgh_conspiracy(state, shaded=False):
    """
    Unshaded – Remove 4 Patriot Militia/Continentals in 1 Colony.
    Shaded   – **Immediate** Tory desertion this Winter.
    """
    if shaded:
        state["winter_flag"] = "TORY_DESERTION"
    else:
        _remove_four_patriot_units(state)

# 23  FRANCIS MARION
@register(23)
def evt_023_francis_marion(state, shaded=False):
    _todo(state)


# 25  BRITISH PRISON SHIPS
@register(25)
def evt_025_prison_ships(state, shaded=False):
    if shaded:
        _todo(state)                 # Militia + shift + propaganda
    else:
        for city in ("New_York_City", "Charleston"):
            shift_support(state, city, +1)


# 31  THOMAS BROWN & KING’S RANGERS
@register(31)
def evt_031_kings_rangers(state, shaded=False):
    _todo(state)


# 36  NAVAL BATTLE IN WEST INDIES
@register(36)
def evt_036_naval_battle_wi(state, shaded=False):
    _todo(state)                     # Regular moves & FNI shift


# 37  THE ARMADA OF 1779
@register(37)
def evt_037_armada(state, shaded=False):
    if shaded:
        _todo(state)                 # remove Regulars, FNI +1
    else:
        add_resource(state, "Patriots", -2)
        add_resource(state, "French",   -3)
        state["fni_level"] = max(0, state.get("fni_level", 0) - 1)


# 39  “HIS MAJESTY, KING MOB” PROTESTS
@register(39)
def evt_039_king_mob(state, shaded=False):
    if shaded:
        return
    # shift 3 cities one step toward Neutral – sample implementation
    for name in ("Boston", "New_York_City", "Charleston"):
        shift_support(state, name, -1)   # toward Neutral


# 40  BATTLE OF THE CHESAPEAKE
@register(40)
def evt_040_chesapeake(state, shaded=False):
    if shaded:
        state["fni_level"] = 3
    else:
        state["fni_level"] = 0
        add_resource(state, "British", +2)


# 45  ADAM SMITH – WEALTH OF NATIONS
@register(45)
def evt_045_adam_smith(state, shaded=False):
    add_resource(state, "British", +6 if not shaded else -4)


# 48  GOD SAVE THE KING
@register(48)
def evt_048_god_save_king(state, shaded=False):
    """
    Unshaded – British free March to 1 space and *may* free Battle there.
    Shaded   – Non-British units relocate (no free ops here).
    """
    from lod_ai.util.free_ops import queue_free_op

    if not shaded:
        target = None                # let the bot/AI select
        queue_free_op(state, "BRITISH", "march",  target)
        queue_free_op(state, "BRITISH", "battle", target)
    else:
        _todo(state)                 # relocation logic still pending


# 52  FRENCH FLEET ARRIVES IN THE WRONG SPOT
@register(52)
def evt_052_fleet_wrong_spot(state, shaded=False):
    """
    Unshaded – Remove up to 4 French Regulars to Available; then
               French free Battle anywhere with +2 Force Level.
    (Card has no shaded side.)
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        return

    removed = 0
    for name, sp in state["spaces"].items():
        if removed == 4:
            break
        here = sp.get("French_Regulars", 0)
        if here:
            move_piece(state, "French_Regulars", name, "available", min(here, 4 - removed))
            removed += min(here, 4 - removed)

    queue_free_op(state, "FRENCH", "battle_plus2")     # anywhere

# 57  FRENCH FLEET SAILS FOR THE CARIBBEAN
@register(57)
def evt_057_french_caribbean(state, shaded=False):
    _todo(state)


# 62  CHARLES MICHEL DE LANGLADE
@register(62)
def evt_062_langlade(state, shaded=False):
    _todo(state)


# 45  ADAM SMITH – WEALTH OF NATIONS
@register(45)
def evt_045_adam_smith(state, shaded=False):
    add_resource(state, "British", +6 if not shaded else -4)
# 45  ADAM SMITH – WEALTH OF NATIONS
@register(45)
def evt_045_adam_smith(state, shaded=False):
    add_resource(state, "British", +6 if not shaded else -4)

# 64  AFFAIR OF FIELDING & BYLANDT
@register(64)
def evt_064_fielding(state, shaded=False):
    if shaded:
        add_resource(state, "British", -3)
        adjust_fni(state, +1)
    else:
        add_resource(state, "British", +3)
        adjust_fni(state, -1)

# 65  JACQUES NECKER
@register(65)
def evt_065_necker(state, shaded=False):
    add_resource(state, "French", +3 if shaded else -4)

# 66  DON BERNARDO TAKES PENSACOLA
@register(66)
def evt_066_don_bernardo(state, shaded=False):
    """
    Shaded – French (or Patriots if no Treaty) free March to and free
             Battle in Florida with +2 Force Level.
    (Card’s unshaded side has no free ops.)
    """
    from lod_ai.util.free_ops import queue_free_op

    if not shaded:
        return

    fac = "FRENCH" if state.get("toa_played") else "PATRIOTS"
    queue_free_op(state, fac, "march",       "Florida")
    queue_free_op(state, fac, "battle_plus2","Florida")


# 67  DE GRASSE ARRIVES
@register(67)
def evt_067_de_grasse(state, shaded=False):
    """
    Unshaded – French (or Patriots) free Rally *or* Muster in any 1 space.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        _todo(state)
        return

    fac = "FRENCH" if state.get("toa_played") else "PATRIOTS"
    queue_free_op(state, fac, "rally")     # bot will choose Rally over Muster


# 70  BRITISH GAIN FROM FRENCH IN INDIA
@register(70)
def evt_070_french_india(state, shaded=False):
    """
    Unshaded – Executing Faction free Battle anywhere with +2 Force Level.
    Shaded   – (none)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        return
    queue_free_op(state, state["executing_faction"], "battle_plus2")

# 73  SULLIVAN EXPEDITION VS IROQUOIS
@register(73)
def evt_073_sullivan(state, shaded=False):
    _todo(state)


# 79  TUSCARORA & ONEIDA COME TO WASHINGTON
@register(79)
def evt_079_tuscarora_oneida(state, shaded=False):
    _todo(state)


# 81  CREEK & SEMINOLE ACTIVE IN SOUTH
@register(81)
def evt_081_creek_seminole(state, shaded=False):
    _todo(state)


# 85  INDIANS HELP BRITISH RAIDS ON MISSISSIPPI
@register(85)
def evt_085_mississippi_raids(state, shaded=False):
    _todo(state)


# 87  PATRIOTS MASSACRE LENAPE INDIANS
@register(87)
def evt_087_lenape(state, shaded=False):
    _todo(state)


# 94  HERKIMER’S RELIEF COLUMN
@register(94)
def evt_094_herkimer(state, shaded=False):
    """
    Unshaded – Indians free Gather *and* Tories free Muster in New York.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        return
    queue_free_op(state, "INDIANS",  "gather", "New_York")
    queue_free_op(state, "BRITISH",  "muster", "New_York")


# 95  OHIO COUNTRY FRONTIER ERUPTS
@register(95)
def evt_095_ohio_frontier(state, shaded=False):
    _todo(state)


# 96  IROQUOIS CONFEDERACY
@register(96)
def evt_096_iroquois_confederacy(state, shaded=False):
    """
    Unshaded – Indians free Gather *and* War Path in 2 Provinces.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        return
    for _ in range(2):
        queue_free_op(state, "INDIANS", "gather")
        queue_free_op(state, "INDIANS", "war_path")
