"""
late_war.py – Event handlers for 1779-1780 cards
------------------------------------------------
IDs: 1 7 16 18 19 21 22 23 25 31 36 37 39 40
     45 48 52 57 62 64 65 66 67 70 73 79
     81 85 87 94 95 96
"""

from lod_ai.cards import register
from .shared import (
    add_resource,
    shift_support,
    push_history,
    adjust_fni,
)

def _remove_four_patriot_units(state):
    """Remove up to 4 Patriot Militia/Continentals from one Colony."""
    for name, sp in state["spaces"].items():
        pat_total = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
        pat_total += sp.get(REGULAR_PAT, 0)
        if pat_total:
            removed = 0
            for tag in (
                MILITIA_A,
                MILITIA_U,
                REGULAR_PAT,
            ):
                while sp.get(tag, 0) and removed < 4:
                    remove_piece(state, tag, name, 1, to="available")
                    removed += 1
            push_history(state, f"Newburgh: removed {removed} Patriot units in {name}")
            break


# 1  WAXHAWS MASSACRE
from lod_ai.rules_consts import (
    REGULAR_BRI,          # British Regular cube tag
    REGULAR_PAT,          # Patriot Continental cube tag
    REGULAR_FRE,
    PROPAGANDA,           # Propaganda marker tag
    TORY,
    FORT_BRI,
    FORT_PAT,
    MILITIA_A,
    MILITIA_U,
    RAID,
    WARPARTY_U,
    WARPARTY_A,
    WEST_INDIES_ID,
    VILLAGE,
    PATRIOTS,
    FRENCH,
    BRITISH,
    INDIANS,
)
from lod_ai.util.history import push_history
from lod_ai.util.free_ops import queue_free_op
from lod_ai.board.pieces import (
    remove_piece,
    place_marker,
    move_piece,
    place_piece,
    place_with_caps,
)
from lod_ai.map import adjacency as map_adj


def _is_city_late(space_id):
    return map_adj.space_type(space_id) == "City"


def _is_colony_late(space_id):
    return map_adj.space_type(space_id) == "Colony"


def _is_reserve_late(space_id):
    return map_adj.space_type(space_id) == "Reserve"


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
        queue_free_op(state, PATRIOTS, "march",  target)
        queue_free_op(state, PATRIOTS, "battle", target)
        place_marker(state, PROPAGANDA, target, 2)
        # Shift one level toward Neutral (toward 0)
        cur = state.get("support", {}).get(target, 0)
        if cur > 0:
            shift_support(state, target, -1)
        elif cur < 0:
            shift_support(state, target, +1)
        push_history(state, f"Waxhaws (shaded): March/Battle in {target}, +2 PROPAGANDA, shift toward Neutral")
    else:
        remove_piece(state, REGULAR_PAT, target, 2, to="casualties")
        shift_support(state, target, +1)     # toward Active Support
        place_marker(state, PROPAGANDA, target, 2)
        push_history(state, f"Waxhaws (unshaded): −2 Continentals in {target}, Support +1, +2 PROPAGANDA")

# 7  JOHN PAUL JONES
@register(7)
def evt_007_john_paul_jones(state, shaded=False):
    if shaded:
        add_resource(state, PATRIOTS, +5)
        adjust_fni(state, +1)
        return

    add_resource(state, BRITISH, +3)
    adjust_fni(state, -1)
    moved = move_piece(state, REGULAR_BRI, "available", WEST_INDIES_ID, 2)
    if moved:
        push_history(state, f"John Paul Jones: {moved} Regulars to West Indies")


# 16  MERCY WARREN’S “THE MOTLEY ASSEMBLY”
@register(16)
def evt_016_mercy_warren(state, shaded=False):
    if shaded:
        city = "Boston"  # deterministic choice
        # set support to Passive Opposition
        delta = -1 - state["support"].get(city, 0)
        shift_support(state, city, delta)
    else:
        place_piece(state, TORY, "New_York_City", 2)


# 18  “IF IT HADN’T BEEN SO STORMY…”
@register(18)
def evt_018_if_not_stormy(state, shaded=False):
    """
    Unshaded – Any one Faction Ineligible through the next card.
    Shaded   – (none)
    """
    if shaded:
        return
    target = state.get("card18_target_faction", BRITISH)
    if target not in {BRITISH, PATRIOTS, FRENCH, INDIANS}:
        target = BRITISH
    state.setdefault("ineligible_through_next", set()).add(target)
    push_history(state, f"Card 18 unshaded: {target} ineligible through next")


# 19  LEGEND OF NATHAN HALE
@register(19)
def evt_019_nathan_hale(state, shaded=False):
    if shaded:
        place_piece(state, MILITIA_U, "Pennsylvania", 3)
        add_resource(state, PATRIOTS, +3)
    else:
        add_resource(state, PATRIOTS, -4)


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
        queue_free_op(state, PATRIOTS, "march",  colony)
        queue_free_op(state, PATRIOTS, "battle", colony)
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
        # "Immediately execute Tory Desertion as per Winter Quarters Round."
        state["winter_flag"] = "TORY_DESERTION_IMMEDIATE"
        push_history(state, "Card 22 shaded: immediate Tory Desertion")
    else:
        _remove_four_patriot_units(state)

# 23  FRANCIS MARION
@register(23)
def evt_023_francis_marion(state, shaded=False):
    if shaded:
        target = "South_Carolina"
        mil = state["spaces"].get(target, {}).get(MILITIA_U, 0) + \
              state["spaces"].get(target, {}).get(MILITIA_A, 0)
        if mil:
            removed = 0
            removed += remove_piece(state, REGULAR_BRI, target, 4)
            if removed < 4:
                remove_piece(state, TORY, target, 4 - removed)
    else:
        src = "South_Carolina"
        dst = "Georgia"
        for tag in (MILITIA_A, MILITIA_U, REGULAR_PAT):
            qty = state["spaces"].get(src, {}).get(tag, 0)
            if qty:
                move_piece(state, tag, src, dst, qty)


# 25  BRITISH PRISON SHIPS
@register(25)
def evt_025_prison_ships(state, shaded=False):
    if shaded:
        for city in ("New_York_City", "Charles_Town"):
            place_piece(state, MILITIA_U, city, 1)
            shift_support(state, city, -1)
            place_marker(state, PROPAGANDA, city)
    else:
        for city in ("New_York_City", "Charles_Town"):
            shift_support(state, city, +1)


# 31  THOMAS BROWN & KING’S RANGERS
@register(31)
def evt_031_kings_rangers(state, shaded=False):
    space = "South_Carolina"
    if shaded:
        place_piece(state, MILITIA_U, space, 2)
        queue_free_op(state, PATRIOTS, "partisans", space)
    else:
        place_with_caps(state, FORT_BRI, space)
        place_piece(state, TORY, space, 2)


# 36  NAVAL BATTLE IN WEST INDIES
@register(36)
def evt_036_naval_battle_wi(state, shaded=False):
    if shaded:
        move_piece(state, REGULAR_BRI, WEST_INDIES_ID, "available", 4)
    else:
        remove_piece(state, REGULAR_FRE, None, 3, to="available")
        adjust_fni(state, -1)


# 37  THE ARMADA OF 1779
@register(37)
def evt_037_armada(state, shaded=False):
    if shaded:
        remove_piece(state, REGULAR_BRI, None, 4, to="available")
        adjust_fni(state, +1)
    else:
        add_resource(state, PATRIOTS, -2)
        add_resource(state, FRENCH, -3)
        adjust_fni(state, -1)


# 39  “HIS MAJESTY, KING MOB” PROTESTS
@register(39)
def evt_039_king_mob(state, shaded=False):
    """
    Unshaded – Shift three Cities one level toward Neutral.
    Shaded   – (none)
    """
    if shaded:
        return
    cities = [sid for sid in state.get("spaces", {})
              if _is_city_late(sid)]
    shifted = 0
    for name in cities:
        if shifted >= 3:
            break
        cur = state.get("support", {}).get(name, 0)
        if cur > 0:
            shift_support(state, name, -1)
            shifted += 1
        elif cur < 0:
            shift_support(state, name, +1)
            shifted += 1
    push_history(state, f"Card 39 unshaded: shifted {shifted} Cities toward Neutral")


# 40  BATTLE OF THE CHESAPEAKE
@register(40)
def evt_040_chesapeake(state, shaded=False):
    if shaded:
        adjust_fni(state, 3 - state.get("fni_level", 0))
    else:
        adjust_fni(state, -state.get("fni_level", 0))
        add_resource(state, BRITISH, +2)


# 45  ADAM SMITH – WEALTH OF NATIONS
@register(45)
def evt_045_adam_smith(state, shaded=False):
    add_resource(state, BRITISH, +6 if not shaded else -4)


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
        queue_free_op(state, BRITISH, "march",  target)
        queue_free_op(state, BRITISH, "battle", target)
    else:
        # A non-British Faction moves units from three spaces containing
        # British Regulars into any adjacent spaces.
        non_brit_tags = [REGULAR_PAT, REGULAR_FRE, MILITIA_U, MILITIA_A,
                         WARPARTY_U, WARPARTY_A, TORY]
        moved_spaces = 0
        for name in list(state.get("spaces", {})):
            if moved_spaces == 3:
                break
            sp = state["spaces"].get(name, {})
            if not sp.get(REGULAR_BRI, 0):
                continue
            has_non_brit = any(sp.get(tag, 0) for tag in non_brit_tags)
            if not has_non_brit:
                continue
            # Find an adjacent space to move into
            neighbors = map_adj.space_meta(name) or {}
            adj_list = []
            for token in neighbors.get("adj", []):
                adj_list.extend(token.split("|"))
            dest = None
            for nbr in adj_list:
                if nbr in state.get("spaces", {}):
                    dest = nbr
                    break
            if not dest:
                continue
            for tag in non_brit_tags:
                qty = sp.get(tag, 0)
                if qty:
                    move_piece(state, tag, name, dest, qty)
            moved_spaces += 1
            push_history(state, f"Card 48 shaded: non-British units move from {name} to {dest}")


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
        here = sp.get(REGULAR_FRE, 0)
        if here:
            move_piece(state, REGULAR_FRE, name, "available", min(here, 4 - removed))
            removed += min(here, 4 - removed)

    queue_free_op(state, FRENCH, "battle_plus2")     # anywhere

# 57  FRENCH FLEET SAILS FOR THE CARIBBEAN
@register(57)
def evt_057_french_caribbean(state, shaded=False):
    if shaded:
        # Move 2 British Regulars from map to West Indies
        moved = 0
        for n, sp in state.get("spaces", {}).items():
            if n == WEST_INDIES_ID:
                continue
            if moved >= 2:
                break
            qty = sp.get(REGULAR_BRI, 0)
            if qty:
                m = move_piece(state, REGULAR_BRI, n, WEST_INDIES_ID, min(qty, 2 - moved))
                moved += m
        state.setdefault("ineligible_through_next", set()).add(BRITISH)
        push_history(state, "Card 57 shaded: British ineligible through next")
    else:
        move_piece(state, REGULAR_FRE, "available", WEST_INDIES_ID, 2)
        state.setdefault("ineligible_through_next", set()).add(FRENCH)
        adjust_fni(state, -1)
        push_history(state, "Card 57 unshaded: French ineligible through next")


# 62  CHARLES MICHEL DE LANGLADE
@register(62)
def evt_062_langlade(state, shaded=False):
    """
    Unshaded – Place three War Parties or three Tories in New York, Quebec or Northwest.
    Shaded   – Place three French Regulars in Quebec or three Militia in Northwest.
    """
    if shaded:
        choice = state.get("card62_shaded_choice", "FRENCH_QUEBEC")
        if choice == "MILITIA_NORTHWEST":
            place_piece(state, MILITIA_U, "Northwest", 3)
            push_history(state, "Card 62 shaded: 3 Militia in Northwest")
        else:
            place_piece(state, REGULAR_FRE, "Quebec", 3)
            push_history(state, "Card 62 shaded: 3 French Regulars in Quebec")
    else:
        target = state.get("card62_target")
        if target not in ("New_York", "Quebec", "Northwest"):
            target = "New_York"
        choice = state.get("card62_unshaded_choice", "WARPARTY")
        if choice == "TORIES":
            place_piece(state, TORY, target, 3)
            push_history(state, f"Card 62 unshaded: 3 Tories in {target}")
        else:
            place_piece(state, WARPARTY_U, target, 3)
            push_history(state, f"Card 62 unshaded: 3 War Parties in {target}")




# 64  AFFAIR OF FIELDING & BYLANDT
@register(64)
def evt_064_fielding(state, shaded=False):
    """
    Unshaded – British seize Dutch contraband: British Resources +3. Lower FNI one level.
    Shaded   – Dutch provide resources to Patriots: Patriot Resources +5.
    """
    if shaded:
        add_resource(state, PATRIOTS, +5)
    else:
        add_resource(state, BRITISH, +3)
        adjust_fni(state, -1)

# 65  JACQUES NECKER
@register(65)
def evt_065_necker(state, shaded=False):
    add_resource(state, FRENCH, +3 if shaded else -4)

# 66  DON BERNARDO TAKES PENSACOLA
@register(66)
def evt_066_don_bernardo(state, shaded=False):
    """
    Shaded – French (or Patriots if no Treaty) free March to and free
             Battle in Florida with +2 Force Level.
    (Card’s unshaded side has no free ops.)
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        fac = FRENCH if state.get("toa_played") else PATRIOTS
        queue_free_op(state, fac, "march", "Florida")
        queue_free_op(state, fac, "battle_plus2", "Florida")
    else:
        place_piece(state, REGULAR_BRI, "Florida", 6)


# 67  DE GRASSE ARRIVES
@register(67)
def evt_067_de_grasse(state, shaded=False):
    """
    Unshaded – Lower FNI 1; move 3 French Regulars from West Indies to Available.
    Shaded   – French (or Patriots) free Rally or Muster in 1 space and remain Eligible.
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        fac = FRENCH if state.get("toa_played") else PATRIOTS
        queue_free_op(state, fac, "rally")
        state.setdefault("eligible_next", set()).add(fac)
    else:
        move_piece(state, REGULAR_FRE, WEST_INDIES_ID, "available", 3)
        adjust_fni(state, -1)


# 70  BRITISH GAIN FROM FRENCH IN INDIA
@register(70)
def evt_070_french_india(state, shaded=False):
    """
    Unshaded – Remove 3 Regulars from map or West Indies to Available.
    Shaded   – (none)
    """
    if shaded:
        return
    removed = remove_piece(state, REGULAR_BRI, None, 3, to="available")
    if removed < 3:
        remove_piece(state, REGULAR_FRE, None, 3 - removed, to="available")

# 73  SULLIVAN EXPEDITION VS IROQUOIS
@register(73)
def evt_073_sullivan(state, shaded=False):
    """
    Unshaded – Remove one Fort or Village in New York, Northwest or Quebec.
    Shaded   – (none)
    """
    if shaded:
        return
    target = state.get("card73_space")
    candidates = ["New_York", "Northwest", "Quebec"]
    if target not in candidates:
        target = None
    # Try to find a space with a Fort or Village to remove
    for loc in ([target] if target else candidates):
        for tag in (FORT_BRI, FORT_PAT, VILLAGE):
            sp = state.get("spaces", {}).get(loc, {})
            if sp.get(tag, 0):
                remove_piece(state, tag, loc, 1, to="available")
                push_history(state, f"Card 73 unshaded: removed 1 {tag} in {loc}")
                return


# 79  TUSCARORA & ONEIDA COME TO WASHINGTON
@register(79)
def evt_079_tuscarora_oneida(state, shaded=False):
    loc = "Pennsylvania"
    if shaded:
        remove_piece(state, VILLAGE, loc, 1, to="available")
        remove_piece(state, WARPARTY_U, loc, 2, to="available")
    else:
        place_piece(state, VILLAGE, loc, 1)
        place_piece(state, WARPARTY_U, loc, 2)


# 81  CREEK & SEMINOLE ACTIVE IN SOUTH
@register(81)
def evt_081_creek_seminole(state, shaded=False):
    loc = "South_Carolina"
    if shaded:
        removed = remove_piece(state, WARPARTY_U, loc, 2, to="available")
        if removed < 2:
            remove_piece(state, WARPARTY_U, "Georgia", 2 - removed, to="available")
    else:
        place_piece(state, WARPARTY_U, loc, 2)
        place_marker(state, RAID, loc)
        place_piece(state, VILLAGE, loc, 1)


# 85  INDIANS HELP BRITISH RAIDS ON MISSISSIPPI
@register(85)
def evt_085_mississippi_raids(state, shaded=False):
    loc = "Southwest"
    if shaded:
        place_piece(state, MILITIA_U, loc, 2)
        place_piece(state, REGULAR_FRE, loc, 2)
    else:
        place_piece(state, REGULAR_BRI, loc, 3)


# 87  PATRIOTS MASSACRE LENAPE INDIANS
@register(87)
def evt_087_lenape(state, shaded=False):
    """
    Unshaded – Remove one piece in Pennsylvania. Remain Eligible.
    Shaded   – (none)
    """
    if shaded:
        return
    loc = "Pennsylvania"
    sp = state.get("spaces", {}).get(loc, {})
    # Remove one piece of any type (prioritise units before bases)
    for tag in (WARPARTY_U, WARPARTY_A, MILITIA_U, MILITIA_A, REGULAR_PAT,
                REGULAR_BRI, REGULAR_FRE, TORY, FORT_BRI, FORT_PAT, VILLAGE):
        if sp.get(tag, 0):
            remove_piece(state, tag, loc, 1, to="available")
            push_history(state, f"Card 87 unshaded: removed 1 {tag} in {loc}")
            break
    # Remain Eligible
    executor = state.get("active")
    if executor:
        state.setdefault("remain_eligible", set()).add(str(executor).upper())


# 94  HERKIMER’S RELIEF COLUMN
@register(94)
def evt_094_herkimer(state, shaded=False):
    """
    Unshaded – Indians free Gather *and* Tories free Muster in New York.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        remove_piece(state, WARPARTY_U, "Pennsylvania", 4, to="available")
        return
    queue_free_op(state, INDIANS, "gather", "New_York")
    queue_free_op(state, BRITISH, "muster", "New_York")
    remove_piece(state, MILITIA_U, "New_York", 99, to="available")
    remove_piece(state, MILITIA_A, "New_York", 99, to="available")


# 95  OHIO COUNTRY FRONTIER ERUPTS
@register(95)
def evt_095_ohio_frontier(state, shaded=False):
    """
    Unshaded – In Northwest, remove any one enemy Fort or Village
               and place three friendly units.
    Shaded   – (none)
    """
    if shaded:
        return
    loc = "Northwest"
    executor = str(state.get("active", "")).upper()
    patriot_side = executor in (PATRIOTS, FRENCH)

    enemy_fort = FORT_BRI if patriot_side else FORT_PAT
    enemy_alt = VILLAGE if patriot_side else None

    removed = remove_piece(state, enemy_fort, loc, 1, to="available")
    if removed == 0 and enemy_alt:
        remove_piece(state, enemy_alt, loc, 1, to="available")

    ally_map = {
        PATRIOTS: FRENCH,
        FRENCH: PATRIOTS,
        BRITISH: INDIANS,
        INDIANS: BRITISH,
    }
    coalition_units = {
        PATRIOTS: (MILITIA_U, MILITIA_A, REGULAR_PAT),
        FRENCH: (REGULAR_FRE,),
        BRITISH: (REGULAR_BRI, TORY),
        INDIANS: (WARPARTY_U, WARPARTY_A),
    }

    ordered_factions = [executor]
    ally = ally_map.get(executor)
    if ally:
        ordered_factions.append(ally)

    friendly_order = tuple(tag for fac in ordered_factions for tag in coalition_units.get(fac, ()))

    placed = 0
    while placed < 3:
        added_any = False
        for tag in friendly_order:
            if placed >= 3:
                break
            added = place_piece(state, tag, loc, 1)
            if added:
                placed += added
                added_any = True
                break
        if not added_any:
            break


# 96  IROQUOIS CONFEDERACY
@register(96)
def evt_096_iroquois_confederacy(state, shaded=False):
    """
    Unshaded – Indians free Gather *and* War Path in 2 Provinces.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        remove_piece(state, VILLAGE, None, 1, to="available")
    else:
        for _ in range(2):
            queue_free_op(state, INDIANS, "gather")
            queue_free_op(state, INDIANS, "war_path")
