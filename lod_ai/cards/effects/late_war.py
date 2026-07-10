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
    select_support_shift_spaces,
    pick_random_spaces,
)

def _remove_four_patriot_units(state):
    """Remove up to 4 Patriot Militia/Continentals from one Colony.

    Sheet I22: "First in Village spaces."  Otherwise most removable
    units (§8.1.1 max extent), §8.2 seeded ties (Session 47: was the
    first Colony in dict order).
    """
    rng = state.get("rng")
    executor = str(state.get("active", "")).upper()
    cands = []
    for name, sp in state["spaces"].items():
        if not _is_colony_late(name):
            continue
        pat_total = (sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
                     + sp.get(REGULAR_PAT, 0))
        if not pat_total:
            continue
        village_first = 1 if (executor == INDIANS and sp.get(VILLAGE, 0)) else 0
        cands.append(((-village_first, -min(pat_total, 4)), name))
    if not cands:
        return
    # Q22: substantive key only; equal-key ties via Random Spaces table.
    name = pick_by_priority(state, cands, count=1)[0]
    sp = state["spaces"][name]
    removed = 0
    # §8.1.2 enemy removal: cubes (Continentals) first, then Underground
    # before Active Militia.
    for tag in (REGULAR_PAT, MILITIA_U, MILITIA_A):
        while sp.get(tag, 0) and removed < 4:
            remove_piece(state, tag, name, 1, to="available")
            removed += 1
    push_history(state, f"Newburgh: removed {removed} Patriot units in {name}")


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
from lod_ai.bots.random_spaces import pick_by_priority
from lod_ai.util.target_order import first_harm_target, first_beneficiary
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
    """
    Unshaded – British Resources +3. Lower FNI one level. Move up to two
               British Regulars from Available to West Indies or any City.
    Shaded   – Patriot Resources +5. Raise FNI one level.
    """
    if shaded:
        add_resource(state, PATRIOTS, +5)
        adjust_fni(state, +1)
        return

    add_resource(state, BRITISH, +3)
    adjust_fni(state, -1)
    # Move up to 2 British Regulars from Available to West Indies or any City
    dest = state.get("card7_dest", WEST_INDIES_ID)
    if dest != WEST_INDIES_ID and not _is_city_late(dest):
        dest = WEST_INDIES_ID
    moved = move_piece(state, REGULAR_BRI, "available", dest, 2)
    if moved:
        push_history(state, f"John Paul Jones: {moved} Regulars to {dest}")


# 16  MERCY WARREN’S “THE MOTLEY ASSEMBLY”
@register(16)
def evt_016_mercy_warren(state, shaded=False):
    """
    Unshaded – Place two Tories anywhere.
    Shaded   – Shift one City to Passive Opposition.
    """
    rng = state.get("rng")
    if shaded:
        city = state.get("card16_city")
        if not city or not _is_city_late(city):
            # "Shift one City TO Passive Opposition" — rebel-favoring:
            # largest (level - (-1)) x Pop gain first (§8.3.6 semantics),
            # §8.2 seeded ties (Session 48/T9: was first-alphabetical).
            cands = []
            for sid in state.get("spaces", {}):
                if not _is_city_late(sid):
                    continue
                lvl = state.get("support", {}).get(sid, 0)
                gain = (lvl + 1) * map_adj.population(sid)
                cands.append(((-gain,), sid))
            picked = pick_by_priority(state, cands, count=1)  # Q22
            city = picked[0] if picked else None
        if city:
            # Passive Opposition = -1
            delta = -1 - state.get("support", {}).get(city, 0)
            if delta:
                shift_support(state, city, delta)
            push_history(state, f"Card 16 shaded: {city} to Passive Opposition")
    else:
        # "Place two Tories anywhere" — Royalist benefit: prefer a space
        # where +2 British pieces GAINS British Control (§8.3.8 "best
        # furthers ... victory"), §8.2 seeded ties (Session 48/T9: was
        # first-alphabetical).
        target = state.get("card16_target")
        if target not in state.get("spaces", {}):
            cands = []
            for sid, sp in state.get("spaces", {}).items():
                if sid == WEST_INDIES_ID:
                    continue
                rebels = sum(q for t, q in sp.items()
                             if isinstance(t, str) and isinstance(q, int)
                             and q > 0 and t.startswith(("Patriot_", "French_")))
                royal = sum(q for t, q in sp.items()
                            if isinstance(t, str) and isinstance(q, int)
                            and q > 0 and t.startswith(("British_", "Indian_")))
                bri = sum(q for t, q in sp.items()
                          if isinstance(t, str) and isinstance(q, int)
                          and q > 0 and t.startswith("British_"))
                already = royal > rebels and bri > 0
                gains = (not already) and (royal + 2 > rebels)
                cands.append(((0 if gains else 1,), sid))
            picked = pick_by_priority(state, cands, count=1)  # Q22
            target = picked[0] if picked else None
        if target:
            place_piece(state, TORY, target, 2)
            push_history(state, f"Card 16 unshaded: 2 Tories in {target}")


# 18  “IF IT HADN’T BEEN SO STORMY…”
@register(18)
def evt_018_if_not_stormy(state, shaded=False):
    """
    Unshaded – Any one Faction Ineligible through the next card.
    Shaded   – (none)
    """
    if shaded:
        return
    target = state.get("card18_target_faction")
    if target not in {BRITISH, PATRIOTS, FRENCH, INDIANS}:
        # §8.3.5 harmful choice (make an enemy ineligible): a random enemy,
        # player first (T7).  No explicit CLI/bot target → select here.
        active = str(state.get("active", PATRIOTS)).upper()
        target = first_harm_target(
            state, active,
            default=(PATRIOTS if active in (BRITISH, INDIANS) else BRITISH))
    state.setdefault("ineligible_through_next", set()).add(target)
    push_history(state, f"Card 18 unshaded: {target} ineligible through next")


# 19  LEGEND OF NATHAN HALE
@register(19)
def evt_019_nathan_hale(state, shaded=False):
    """
    Unshaded – Patriot Resources –4.
    Shaded   – Place three Patriot Militia anywhere. Patriot Resources +3.
    """
    if shaded:
        # "anywhere" — bot/player decides; default to first 3 spaces
        targets = state.get("card19_targets")
        if isinstance(targets, list):
            for sid in targets[:3]:
                if sid in state.get("spaces", {}):
                    place_piece(state, MILITIA_U, sid, 1)
        else:
            # "Place three Patriot Militia anywhere" — Patriot militia
            # placement shape (§8.5.2 bullet 6): first to change Control,
            # then not at Active Opposition, Cities first, highest Pop;
            # §8.2 seeded ties (Session 48/T9: was first-3 alphabetical).
            # West Indies excluded (§1.4.2).
            rng = state.get("rng")
            cands = []
            for sid, sp in state.get("spaces", {}).items():
                if sid == WEST_INDIES_ID:
                    continue
                rebels = sum(q for t, q in sp.items()
                             if isinstance(t, str) and isinstance(q, int)
                             and q > 0 and t.startswith(("Patriot_", "French_")))
                royal = sum(q for t, q in sp.items()
                            if isinstance(t, str) and isinstance(q, int)
                            and q > 0 and t.startswith(("British_", "Indian_")))
                changes = 1 if (rebels <= royal and rebels + 1 > royal) else 0
                no_ao = 1 if state.get("support", {}).get(sid, 0) > -2 else 0
                is_city = 1 if _is_city_late(sid) else 0
                pop = map_adj.population(sid)
                cands.append(((-changes, -no_ao, -is_city, -pop), sid))
            for sid in pick_by_priority(state, cands, count=3):  # Q22
                place_piece(state, MILITIA_U, sid, 1)
        add_resource(state, PATRIOTS, +3)
    else:
        add_resource(state, PATRIOTS, -4)


# 21  THE GAMECOCK THOMAS SUMTER
@register(21)
def evt_021_sumter(state, shaded=False):
    """
    Unshaded – Shift South Carolina or Georgia two levels toward Active Support.
    Shaded   – Patriots free March to and free Battle in South Carolina or Georgia.
    """
    from lod_ai.util.free_ops import queue_free_op
    colony = state.get("card21_target")
    if colony not in ("South_Carolina", "Georgia"):
        if shaded:
            colony = "South_Carolina"
        else:
            # Sheet I21: "First in non-Village spaces."  Within that the
            # larger possible shift x Pop (§8.3.6), §8.2 seeded ties
            # (Session 47: was always South_Carolina).
            executor = str(state.get("active", "")).upper()
            scored = []
            for sid in ("South_Carolina", "Georgia"):
                if sid not in state.get("spaces", {}):
                    continue
                sp = state["spaces"][sid]
                nonvillage = (1 if (executor == INDIANS
                                    and not sp.get(VILLAGE, 0)) else 0)
                lvl = state.get("support", {}).get(sid, 0)
                gain = max(0, min(2, 2 - lvl))
                pop = map_adj.population(sid)
                # Q22: substantive key only (non-Village, then shift x Pop);
                # equal-key ties resolved by the Random Spaces table.
                scored.append(((-nonvillage, -(gain * pop)), sid))
            picked = pick_by_priority(state, scored, count=1)
            colony = picked[0] if picked else "South_Carolina"

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
    """
    Unshaded – British or Indians move all Patriot units in North Carolina or
               South Carolina into an adjacent Province.
    Shaded   – If Militia occupy North Carolina or South Carolina, remove four
               British units from that space.
    """
    if shaded:
        # "If Militia occupy North Carolina or South Carolina, remove four
        #  British units from that space."
        target = state.get("card23_target")
        if target not in ("North_Carolina", "South_Carolina"):
            # Default: pick whichever has Militia (NC first alphabetically)
            for cand in ("North_Carolina", "South_Carolina"):
                sp = state["spaces"].get(cand, {})
                if sp.get(MILITIA_U, 0) or sp.get(MILITIA_A, 0):
                    target = cand
                    break
        if not target:
            push_history(state, "Card 23 shaded: no Militia in NC or SC")
            return
        sp = state["spaces"].get(target, {})
        mil = sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0)
        if mil:
            removed = remove_piece(state, REGULAR_BRI, target, 4, to="available")
            if removed < 4:
                remove_piece(state, TORY, target, 4 - removed, to="available")
            push_history(state, f"Card 23 shaded: removed British units in {target}")
        else:
            push_history(state, f"Card 23 shaded: no Militia in {target}")
    else:
        # "British or Indians move all Patriot units in North Carolina or
        #  South Carolina into an adjacent Province."
        rng = state.get("rng")
        src = state.get("card23_src")
        if src not in ("North_Carolina", "South_Carolina"):
            # Sheet B23: "If possible, move Patriots from Support to
            # non-Support spaces" — prefer an origin at Support; §8.2
            # seeded ties (Session 47: was NC-first).
            s_cands = []
            for cand in ("North_Carolina", "South_Carolina"):
                sp = state["spaces"].get(cand, {})
                if not any(sp.get(t, 0) for t in (MILITIA_A, MILITIA_U, REGULAR_PAT)):
                    continue
                at_support = 1 if state.get("support", {}).get(cand, 0) > 0 else 0
                s_cands.append(((-at_support,), cand))
            picked = pick_by_priority(state, s_cands, count=1)  # Q22
            src = picked[0] if picked else None
        if not src:
            push_history(state, "Card 23 unshaded: no Patriot units in NC or SC")
            return

        # Destination: an adjacent PROVINCE (card text — Cities excluded;
        # Reserves only when no Militia move, §3.3.1 note).  Sheet B23:
        # prefer non-Support destinations; §8.2 seeded ties (Session 47:
        # was the first adjacent space of any type).
        src_sp = state["spaces"].get(src, {})
        moving_militia = bool(src_sp.get(MILITIA_A, 0) or src_sp.get(MILITIA_U, 0))
        dst = state.get("card23_dst")
        if dst not in state.get("spaces", {}):
            meta = map_adj.space_meta(src) or {}
            adj = []
            for token in meta.get("adj", []):
                adj.extend(token.split("|"))
            d_cands = []
            for s in adj:
                if s not in state.get("spaces", {}):
                    continue
                stype = map_adj.space_type(s)
                if stype == "City":
                    continue
                if stype == "Reserve" and moving_militia:
                    continue
                non_support = 1 if state.get("support", {}).get(s, 0) <= 0 else 0
                d_cands.append(((-non_support,), s))
            picked = pick_by_priority(state, d_cands, count=1)  # Q22
            dst = picked[0] if picked else None
        if not dst:
            push_history(state, f"Card 23 unshaded: no adjacent Province for {src}")
            return

        # Move all Patriot *units* (cubes only, not Forts/bases)
        for tag in (MILITIA_A, MILITIA_U, REGULAR_PAT):
            qty = state["spaces"].get(src, {}).get(tag, 0)
            if qty:
                move_piece(state, tag, src, dst, qty)
        push_history(state, f"Card 23 unshaded: Patriot units {src} → {dst}")


# 25  BRITISH PRISON SHIPS
@register(25)
def evt_025_prison_ships(state, shaded=False):
    """
    Unshaded – Shift two Cities one level each toward Passive Support.
    Shaded   – In two Cities place one Militia and shift each one level
               toward Passive Opposition. Place one Propaganda in each.
    """
    override = state.get("card25_cities")
    if isinstance(override, list):
        cities = [sid for sid in override if sid in state.get("spaces", {})]
    else:
        all_cities = [sid for sid in state.get("spaces", {})
                      if _is_city_late(sid)]
        # §8.3.5 → §8.3.6: pop-weighted Support/Opposition gain; §8.2 ties.
        cities = select_support_shift_spaces(state, all_cities, 2,
                                             target=(-1 if shaded else +1),
                                             steps=1, shaded=shaded)

    if shaded:
        for city in cities[:2]:
            place_piece(state, MILITIA_U, city, 1)
            # One level toward Passive Opposition (-1)
            cur = state.get("support", {}).get(city, 0)
            if cur > -1:
                shift_support(state, city, -1)
            elif cur < -1:
                shift_support(state, city, +1)
            place_marker(state, PROPAGANDA, city, 1)
        push_history(state, "Card 25 shaded: Militia + Propaganda in 2 Cities")
    else:
        for city in cities[:2]:
            # One level toward Passive Support (+1)
            cur = state.get("support", {}).get(city, 0)
            if cur < 1:
                shift_support(state, city, +1)
            elif cur > 1:
                shift_support(state, city, -1)
        push_history(state, "Card 25 unshaded: 2 Cities toward Passive Support")


# 31  THOMAS BROWN & KING’S RANGERS
@register(31)
def evt_031_kings_rangers(state, shaded=False):
    """
    Unshaded – Place one British Fort and two Tories in South Carolina or Georgia.
    Shaded   – Patriots place two Militia in South Carolina or Georgia
               and may Partisans there.
    """
    space = state.get("card31_target", "South_Carolina")
    if space not in ("South_Carolina", "Georgia"):
        space = "South_Carolina"
    if shaded:
        place_piece(state, MILITIA_U, space, 2)
        queue_free_op(state, PATRIOTS, "partisans", space)
        push_history(state, f"Card 31 shaded: 2 Militia + Partisans in {space}")
    else:
        place_with_caps(state, FORT_BRI, space)
        place_piece(state, TORY, space, 2)
        push_history(state, f"Card 31 unshaded: Fort + 2 Tories in {space}")


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
        # "A non-British Faction" (singular) moves its units from three
        # spaces containing British Regulars into any adjacent spaces.
        # Choose ONE non-British faction (player choice; bot: §8.3.8 random).
        faction_unit_map = {
            PATRIOTS: [REGULAR_PAT, MILITIA_U, MILITIA_A],
            FRENCH: [REGULAR_FRE],
            INDIANS: [WARPARTY_U, WARPARTY_A],
        }
        chosen_fac = state.get("card48_faction", "").upper()
        if chosen_fac not in faction_unit_map:
            # "A non-British Faction moves units..." — §8.3.5 benefit
            # order (executing Faction, then friendly, then a random
            # enemy NP first), restricted to non-British factions that
            # actually have units co-located with British Regulars (T7).
            # Was: first-fit dict order (PATRIOTS even when the
            # executing INDIANS qualified).
            qualifying = [
                fac for fac, tags in faction_unit_map.items()
                if any(sp.get(REGULAR_BRI, 0) and any(sp.get(t, 0) for t in tags)
                       for sp in state.get("spaces", {}).values())
            ]
            active = str(state.get("active", "")).upper()
            chosen_fac = first_beneficiary(state, active,
                                           candidates=qualifying)
        if not chosen_fac:
            push_history(state, "Card 48 shaded: no non-British faction present")
            return

        unit_tags = faction_unit_map[chosen_fac]
        moved_spaces = 0
        for name in list(state.get("spaces", {})):
            if moved_spaces == 3:
                break
            sp = state["spaces"].get(name, {})
            if not sp.get(REGULAR_BRI, 0):
                continue
            has_units = any(sp.get(tag, 0) for tag in unit_tags)
            if not has_units:
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
            for tag in unit_tags:
                qty = sp.get(tag, 0)
                if qty:
                    move_piece(state, tag, name, dest, qty)
            moved_spaces += 1
            push_history(state, f"Card 48 shaded: {chosen_fac} units move from {name} to {dest}")


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

    executor = str(state.get("active", "")).upper()
    # "Remove UP TO four" — the executing Faction chooses how many.
    # Sheets P52/F52: "Remove no French Regulars" (french.py also sets
    # card52_no_remove_french — now honored; Session 47: the flag was
    # never read and 4 Regulars were stripped in dict order for every
    # executor).  Sheet B52: "If possible, remove French Regulars from
    # spaces where Rebels outnumber present British."
    if executor == BRITISH and not state.get("card52_no_remove_french"):
        scored = []
        for name, sp in state["spaces"].items():
            here = sp.get(REGULAR_FRE, 0)
            if not here:
                continue
            rebels = sum(sp.get(t, 0) for t in
                         (REGULAR_FRE, REGULAR_PAT, MILITIA_A, MILITIA_U,
                          FORT_PAT))
            brits = sum(sp.get(t, 0) for t in (REGULAR_BRI, TORY, FORT_BRI))
            outnumber = 1 if rebels > brits else 0
            # Q22: substantive key only (Rebels-outnumber-British first);
            # equal-key ties resolved by the Random Spaces table.
            scored.append(((-outnumber,), name))
        removed = 0
        for name in pick_by_priority(state, scored):
            if removed == 4:
                break
            here = state["spaces"][name].get(REGULAR_FRE, 0)
            take = min(here, 4 - removed)
            if take:
                move_piece(state, REGULAR_FRE, name, "available", take)
                removed += take

    # "Free Battle anywhere with +2 Force Level" — the executing
    # Faction's Battle (sheets P52/F52 route it through the Battle
    # instructions; Session 47: was hardwired to FRENCH).
    battler = executor if executor in (BRITISH, PATRIOTS, FRENCH) else FRENCH
    queue_free_op(state, battler, "battle_plus2")     # anywhere

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
    Shaded – French or Patriots free March to and free Battle in
             Florida with +2 Force Level (player choice, regardless
             of Treaty of Alliance status).
    (Card's unshaded side has no free ops.)
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        # "French or Patriots" — player choice regardless of TOA
        fac = state.get("card66_shaded_faction", "").upper()
        if fac not in (FRENCH, PATRIOTS):
            # §8.3.5 benefit (free ops to French OR Patriots): the executing
            # Faction first, then the other friendly Faction (T7).
            active = str(state.get("active", "")).upper()
            fac = first_beneficiary(state, active,
                                    candidates=(FRENCH, PATRIOTS), default=FRENCH)
        queue_free_op(state, fac, "march", "Florida")
        queue_free_op(state, fac, "battle_plus2", "Florida")
    else:
        # "Place six British cubes in either Florida or Southwest."
        # British cubes = Regulars + Tories
        target = state.get("card66_target", "Florida")
        if target not in ("Florida", "Southwest"):
            target = "Florida"
        mix = state.get("card66_mix")
        if isinstance(mix, dict):
            reg = int(mix.get(REGULAR_BRI, 0))
            tory = int(mix.get(TORY, 0))
            if reg + tory == 6:
                if reg:
                    place_piece(state, REGULAR_BRI, target, reg)
                if tory:
                    place_piece(state, TORY, target, tory)
            else:
                place_piece(state, REGULAR_BRI, target, 6)
        else:
            place_piece(state, REGULAR_BRI, target, 6)
        push_history(state, f"Card 66 unshaded: 6 British cubes in {target}")


# 67  DE GRASSE ARRIVES
@register(67)
def evt_067_de_grasse(state, shaded=False):
    """
    Unshaded – Lower FNI 1; move 3 French Regulars from West Indies to Available.
    Shaded   – French or Patriots free Rally or Muster in 1 space and
               remain or become Eligible (player choice, regardless
               of Treaty of Alliance status).
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        # "French or Patriots free Rally or Muster in one space."
        # Rally is a Patriot Command (3.3) and Muster here is a French
        # Command that requires the Treaty of Alliance (3.5.2), so the
        # faction choice determines the legal op (a French "rally" can
        # never execute).  §8.3.5 benefit order via T7 (executing
        # Faction, then friendly, then a random enemy NP first) — a
        # Royalist executor previously hardwired FRENCH instead of the
        # seeded random-enemy pick its sibling card 66 uses.
        fac = state.get("card67_faction", "").upper()
        if fac not in (FRENCH, PATRIOTS):
            active = str(state.get("active", "")).upper()
            fac = first_beneficiary(state, active,
                                    candidates=(FRENCH, PATRIOTS),
                                    default=FRENCH)
        if fac == FRENCH and not state.get("toa_played"):
            # French cannot Muster before the Treaty (3.5.2) and may
            # never Rally (3.3): the benefit passes to the Patriots.
            fac = PATRIOTS
        op = "muster" if fac == FRENCH else "rally"
        queue_free_op(state, fac, op)
        # "remain or become Eligible"
        state.setdefault("remain_eligible", set()).add(fac)
        push_history(state, f"Card 67 shaded: {fac} free {op}, remains Eligible")
    else:
        move_piece(state, REGULAR_FRE, WEST_INDIES_ID, "available", 3)
        adjust_fni(state, -1)


# 70  BRITISH GAIN FROM FRENCH IN INDIA
@register(70)
def evt_070_french_india(state, shaded=False):
    """
    Unshaded – Remove 3 Regulars from map or West Indies to Available.
    Shaded   – (none)

    Bot-specific instructions (Q2):
      British: French Regulars from WI, then spaces with British pieces.
      French:  British Regulars from spaces with Rebels.
      Indian:  French Regulars from Village spaces first.
      Patriot: British Regulars from spaces with Patriot pieces.
    """
    if shaded:
        return

    active = state.get("active", "").upper()
    remaining = 3

    if active == BRITISH:
        # "Remove French Regulars from West Indies, then from spaces with British pieces."
        wi = state["spaces"].get(WEST_INDIES_ID, {})
        take = min(remaining, wi.get(REGULAR_FRE, 0))
        if take:
            remaining -= remove_piece(state, REGULAR_FRE, WEST_INDIES_ID, take, to="available")
        for sid, sp in state["spaces"].items():
            if remaining <= 0:
                break
            if sid == WEST_INDIES_ID:
                continue
            if sp.get(REGULAR_BRI, 0) > 0 or sp.get(TORY, 0) > 0:
                take = min(remaining, sp.get(REGULAR_FRE, 0))
                if take:
                    remaining -= remove_piece(state, REGULAR_FRE, sid, take, to="available")

    elif active == FRENCH:
        # "Remove British Regulars from spaces with Rebels."
        for sid, sp in state["spaces"].items():
            if remaining <= 0:
                break
            rebels = (sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
                      + sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0))
            if rebels > 0:
                take = min(remaining, sp.get(REGULAR_BRI, 0))
                if take:
                    remaining -= remove_piece(state, REGULAR_BRI, sid, take, to="available")

    elif active == INDIANS:
        # "Remove French Regulars from Village spaces first."
        village_spaces = [
            (sid, sp) for sid, sp in state["spaces"].items()
            if sp.get(VILLAGE, 0) > 0
        ]
        for sid, sp in village_spaces:
            if remaining <= 0:
                break
            take = min(remaining, sp.get(REGULAR_FRE, 0))
            if take:
                remaining -= remove_piece(state, REGULAR_FRE, sid, take, to="available")
        # Then other spaces
        for sid, sp in state["spaces"].items():
            if remaining <= 0:
                break
            take = min(remaining, sp.get(REGULAR_FRE, 0))
            if take:
                remaining -= remove_piece(state, REGULAR_FRE, sid, take, to="available")

    elif active == PATRIOTS:
        # "Remove British Regulars from spaces with Patriot pieces."
        for sid, sp in state["spaces"].items():
            if remaining <= 0:
                break
            pats = (sp.get(REGULAR_PAT, 0) + sp.get(MILITIA_A, 0)
                    + sp.get(MILITIA_U, 0) + sp.get(FORT_PAT, 0))
            if pats > 0:
                take = min(remaining, sp.get(REGULAR_BRI, 0))
                if take:
                    remaining -= remove_piece(state, REGULAR_BRI, sid, take, to="available")
    else:
        # Fallback: remove British then French (generic)
        removed = remove_piece(state, REGULAR_BRI, None, remaining, to="available")
        if removed < remaining:
            remove_piece(state, REGULAR_FRE, None, remaining - removed, to="available")

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
    # The executing Faction selects: remove an ENEMY Fort/Village first
    # (sheet F73 wants the British Fort; Session 47: the fixed
    # FORT_BRI-first order had Royalist executors removing their own
    # side's Fort).  Own-side pieces only when nothing enemy exists
    # (§5.1.3 implement-what-can).
    executor = str(state.get("active", "")).upper()
    if executor in (PATRIOTS, FRENCH):
        tag_order = (FORT_BRI, VILLAGE, FORT_PAT)
    elif executor == BRITISH:
        tag_order = (FORT_PAT, VILLAGE, FORT_BRI)
    else:                                   # INDIANS: Village last
        tag_order = (FORT_PAT, FORT_BRI, VILLAGE)
    locs = [target] if target else candidates
    for tag in tag_order:
        for loc in locs:
            sp = state.get("spaces", {}).get(loc, {})
            if sp.get(tag, 0):
                remove_piece(state, tag, loc, 1, to="available")
                push_history(state, f"Card 73 unshaded: removed 1 {tag} in {loc}")
                return


# 79  TUSCARORA & ONEIDA COME TO WASHINGTON
@register(79)
def evt_079_tuscarora_oneida(state, shaded=False):
    """
    Unshaded – Place one Village and two War Parties in one Colony.
    Shaded   – Remove one Village and two War Parties in one Colony.
    """
    loc = state.get("card79_colony")
    if not loc or not _is_colony_late(loc):
        # §5.1.3 implement-what-can + §8.2 seeded ties (Session 48/T9:
        # was first-alphabetical).  Shaded: a Colony where pieces exist
        # to remove, Village first (max effect); unshaded: a Colony with
        # Fort/Village room (§1.4.2).
        rng = state.get("rng")
        cands = []
        for sid, sp in state.get("spaces", {}).items():
            if not _is_colony_late(sid):
                continue
            if shaded:
                v = sp.get(VILLAGE, 0)
                wp = sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0)
                if v == 0 and wp == 0:
                    continue
                key = (-(1 if v else 0), -min(wp, 2))
            else:
                bases = (sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0)
                         + sp.get(VILLAGE, 0))
                if bases >= 2:
                    continue
                key = (0,)
            cands.append((key, sid))
        picked = pick_by_priority(state, cands, count=1)  # Q22
        loc = picked[0] if picked else "Pennsylvania"
    if shaded:
        remove_piece(state, VILLAGE, loc, 1, to="available")
        removed = remove_piece(state, WARPARTY_U, loc, 2, to="available")
        if removed < 2:
            remove_piece(state, WARPARTY_A, loc, 2 - removed, to="available")
        push_history(state, f"Card 79 shaded: removed Village + War Parties in {loc}")
    else:
        place_with_caps(state, VILLAGE, loc)
        place_piece(state, WARPARTY_U, loc, 2)
        push_history(state, f"Card 79 unshaded: placed Village + War Parties in {loc}")


# 81  CREEK & SEMINOLE ACTIVE IN SOUTH
@register(81)
def evt_081_creek_seminole(state, shaded=False):
    """
    Unshaded – Place two War Parties, one Raid marker, and one Village
               in South Carolina or Georgia.
    Shaded   – Remove two War Parties total in South Carolina and/or Georgia.
    """
    if shaded:
        remaining = 2
        for loc in ("South_Carolina", "Georgia"):
            if remaining <= 0:
                break
            removed = remove_piece(state, WARPARTY_U, loc, remaining, to="available")
            remaining -= removed
            if remaining > 0:
                removed = remove_piece(state, WARPARTY_A, loc, remaining, to="available")
                remaining -= removed
        push_history(state, f"Card 81 shaded: removed {2 - remaining} War Parties")
    else:
        loc = state.get("card81_target", "South_Carolina")
        if loc not in ("South_Carolina", "Georgia"):
            loc = "South_Carolina"
        place_piece(state, WARPARTY_U, loc, 2)
        place_marker(state, RAID, loc, 1)
        place_with_caps(state, VILLAGE, loc)
        push_history(state, f"Card 81 unshaded: War Parties + Raid + Village in {loc}")


# 85  INDIANS HELP BRITISH RAIDS ON MISSISSIPPI
@register(85)
def evt_085_mississippi_raids(state, shaded=False):
    """
    Unshaded – British place a total of three British Regulars and/or Tories in Southwest.
    Shaded   – Place two Militia or Continentals and two French Regulars in Southwest.
    """
    loc = "Southwest"
    if shaded:
        # "two Militia or Continentals" — default Militia; player can choose
        choice = state.get("card85_shaded_choice", "MILITIA")
        if choice == "CONTINENTAL":
            place_piece(state, REGULAR_PAT, loc, 2)
        else:
            place_piece(state, MILITIA_U, loc, 2)
        place_piece(state, REGULAR_FRE, loc, 2)
    else:
        # "three British Regulars and/or Tories" — allow mix
        mix = state.get("card85_mix")
        if isinstance(mix, dict):
            reg = int(mix.get(REGULAR_BRI, 0))
            tory = int(mix.get(TORY, 0))
            if reg + tory == 3:
                if reg:
                    place_piece(state, REGULAR_BRI, loc, reg)
                if tory:
                    place_piece(state, TORY, loc, tory)
            else:
                place_piece(state, REGULAR_BRI, loc, 3)
        else:
            place_piece(state, REGULAR_BRI, loc, 3)


# 87  PATRIOTS MASSACRE LENAPE INDIANS
@register(87)
def evt_087_lenape(state, shaded=False):
    """
    Unshaded – Remove one piece in Pennsylvania. Remain Eligible.
               Player chooses which piece (bot: §8.3.8 or card instruction).
    Shaded   – (none)
    """
    if shaded:
        return
    loc = "Pennsylvania"
    sp = state.get("spaces", {}).get(loc, {})

    # Player chooses which piece to remove via state override
    chosen = state.get("card87_piece", "").strip()
    if chosen and sp.get(chosen, 0):
        remove_piece(state, chosen, loc, 1, to="available")
        push_history(state, f"Card 87 unshaded: removed 1 {chosen} in {loc}")
    else:
        # "Remove one piece" (any faction's) — implicitly a §8.3.5 harm
        # choice of WHOSE piece: a random enemy, player first (T7), the
        # ally then own pieces only when no enemy piece is present
        # (§5.1.3 implement-what-can).  Within a faction keep the
        # units-before-bases order.  (Was a fixed executor-blind tag
        # order that removed friendly Indian War Parties first for a
        # Royalist executor.)
        from lod_ai.util.target_order import harm_target_order
        faction_tags = {
            INDIANS: (WARPARTY_U, WARPARTY_A, VILLAGE),
            PATRIOTS: (MILITIA_U, MILITIA_A, REGULAR_PAT, FORT_PAT),
            BRITISH: (REGULAR_BRI, TORY, FORT_BRI),
            FRENCH: (REGULAR_FRE,),
        }
        executor = str(state.get("active", "")).upper()
        _ALLY = {BRITISH: INDIANS, INDIANS: BRITISH,
                 PATRIOTS: FRENCH, FRENCH: PATRIOTS}
        order = list(harm_target_order(state, executor))
        if executor in _ALLY:
            order += [_ALLY[executor], executor]
        else:
            order += [BRITISH, PATRIOTS, FRENCH, INDIANS]
        done = False
        for fac in order:
            for tag in faction_tags.get(fac, ()):
                if sp.get(tag, 0):
                    remove_piece(state, tag, loc, 1, to="available")
                    push_history(
                        state, f"Card 87 unshaded: removed 1 {tag} in {loc}")
                    done = True
                    break
            if done:
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
        # "Remove four War Parties in or adjacent to Pennsylvania."
        remaining = 4
        candidates = ["Pennsylvania"]
        meta = map_adj.space_meta("Pennsylvania") or {}
        for token in meta.get("adj", []):
            candidates.extend(token.split("|"))
        for loc in candidates:
            if remaining <= 0:
                break
            if loc not in state.get("spaces", {}):
                continue
            removed = remove_piece(state, WARPARTY_U, loc, remaining, to="available")
            remaining -= removed
            if remaining > 0:
                removed = remove_piece(state, WARPARTY_A, loc, remaining, to="available")
                remaining -= removed
        push_history(state, f"Card 94 shaded: removed {4 - remaining} War Parties")
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
    # §1.4.3: new Militia and War Parties are always placed Underground.
    coalition_units = {
        PATRIOTS: (MILITIA_U, REGULAR_PAT),
        FRENCH: (REGULAR_FRE,),
        BRITISH: (REGULAR_BRI, TORY),
        INDIANS: (WARPARTY_U,),
    }

    ordered_factions = [executor]
    ally = ally_map.get(executor)
    if ally:
        ordered_factions.append(ally)

    friendly_order = tuple(tag for fac in ordered_factions for tag in coalition_units.get(fac, ()))
    if executor == BRITISH:
        # Sheet B95: "Place War Parties first."
        friendly_order = (WARPARTY_U, REGULAR_BRI, TORY)

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
    Unshaded – Indians free Gather and War Path in two Indian Reserve Provinces.
    Shaded   – Remove one Indian Village.
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        remove_piece(state, VILLAGE, None, 1, to="available")
        push_history(state, "Card 96 shaded: removed one Indian Village")
    else:
        # Free Gather and War Path in 2 Indian Reserve Provinces —
        # equal priority → §8.2 seeded pick (Session 48/T9: was the
        # first two alphabetically).
        reserves = [sid for sid in state.get("spaces", {})
                    if _is_reserve_late(sid)]
        chosen = pick_random_spaces(state, reserves, min(2, len(reserves)))
        for prov in chosen:
            queue_free_op(state, INDIANS, "gather", prov)
            queue_free_op(state, INDIANS, "war_path", prov)
        push_history(state, f"Card 96 unshaded: Gather + War Path in {chosen}")
