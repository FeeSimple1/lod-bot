"""
middle_war.py – Event handlers for 1777-1778 cards
--------------------------------------------------
IDs covered (32): 3 5 8 9 11 12 14 17 26 27 34 38 42 44 47 50
                  55 58 59 60 61 63 69 71 74 76 77 78 80 88 89 93
"""

from lod_ai.cards import register
from .shared import (
    add_resource,
    shift_support,
    push_history,
    place_piece,
    remove_piece,
    move_piece,
    place_with_caps,
    place_marker,
    adjust_fni,
)
from lod_ai.rules_consts import WEST_INDIES_ID, VILLAGE  # canonical constants
from lod_ai.util.free_ops import queue_free_op


# 3  GEORGE ROGERS CLARK’S ILLINOIS CAMPAIGN
@register(3)
def evt_003_illinois_campaign(state, shaded=False):
    """
    Unshaded – Remove all Patriot pieces in Northwest and Southwest.
    Shaded   – Patriots place 2 Militia **and free Partisans**
               in *both* Northwest and Southwest.
    """
    from lod_ai.util.free_ops import queue_free_op

    for prov in ("Northwest", "Southwest"):
        if shaded:
            place_piece(state, "Patriot_Militia_U", prov, 2)
            queue_free_op(state, "PATRIOTS", "partisans", prov)
        else:
            # Remove all Patriot pieces: Militia (A/U), Continentals, and Forts.
            for tag in ("Patriot_Militia_A", "Patriot_Militia_U", "Patriot_Continental", "Patriot_Fort"):
                remove_piece(state, tag, prov, 99, to="available")

# 5  WILLIAM ALEXANDER, LORD STIRLING
@register(5)
def evt_005_lord_stirling(state, shaded=False):
    """
    Unshaded – Patriots Ineligible next card.
    Shaded   – Patriots free March + Battle.
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        queue_free_op(state, "PATRIOTS", "march")
        queue_free_op(state, "PATRIOTS", "battle")
    else:
        state.setdefault("ineligible_next", set()).add("PATRIOTS")
    push_history(state, "Lord Stirling event resolved")

# 8  CULPEPER SPY RING
@register(8)
def evt_008_culpeper_ring(state, shaded=False):
    """Handle Culpeper Spy Ring event."""
    if shaded:
        removed = remove_piece(state, "British_Regular", None, 3, to="casualties")
        if removed < 3:
            remove_piece(state, "British_Tory", None, 3 - removed, to="casualties")
    else:
        # Activate three Patriot Militia anywhere
        flipped = 0
        for name, sp in state["spaces"].items():
            if flipped == 3:
                break
            if sp.get("Patriot_Militia_U", 0):
                sp["Patriot_Militia_U"] -= 1
                sp["Patriot_Militia_A"] = sp.get("Patriot_Militia_A", 0) + 1
                push_history(state, f"Activated Militia in {name}")
                flipped += 1


# 9  FRIEDRICH WILHELM VON STEUBEN
@register(9)
def evt_009_von_steuben(state, shaded=False):
    """
    Unshaded – British may Skirmish in up to 3 spaces.
    Shaded   – Patriots may Skirmish in up to 3 spaces.
    """
    from lod_ai.util.free_ops import queue_free_op
    actor = "PATRIOTS" if shaded else "BRITISH"

    for _ in range(3):                       # queue three separate Skirmishes
        queue_free_op(state, actor, "skirmish")


# 11  KOSCIUSZKO
@register(11)
def evt_011_kosciuszko(state, shaded=False):
    """Implement Kosciuszko event."""
    if shaded:
        done = 0
        for name, sp in state["spaces"].items():
            if done == 2:
                break
            if not sp.get("Patriot_Control"):
                continue
            # remove one Patriot piece if present
            for tag in list(sp.keys()):
                if tag.startswith("Patriot_") and sp.get(tag, 0) > 0:
                    remove_piece(state, tag, name, 1, to="available")
                    break
            place_with_caps(state, "Patriot_Fort", name)
            done += 1
        push_history(state, "Kosciuszko fortified controlled spaces")
    else:
        removed = remove_piece(state, "Patriot_Fort", None, 2, to="available")
        push_history(state, f"Kosciuszko unshaded: removed {removed} Forts")


# 12  MARTHA WASHINGTON TO VALLEY FORGE
@register(12)
def evt_012_martha_to_valley_forge(state, shaded=False):
    """
    Unshaded – Patriot desertion this Winter.
    Shaded   – Patriot Resources +5.
    """
    if shaded:
        add_resource(state, "Patriots", +5)
    else:
        state["winter_flag"] = "PAT_DESERTION"

# 14  OVERMOUNTAIN MEN FIGHT FOR NORTH CAROLINA
@register(14)
def evt_014_overmountain_men(state, shaded=False):
    """
    Unshaded – Indians free Scout/March to NC or SW, **then** Indians War Path
               *or* British free Battle in that space.  (Bot chooses War Path.)
    Shaded   – Patriots free March to and free Battle in NC or SW.
    """
    from lod_ai.util.free_ops import queue_free_op
    target = "North_Carolina"

    if shaded:
        queue_free_op(state, "PATRIOTS", "march",  target)
        queue_free_op(state, "PATRIOTS", "battle", target)
    else:
        # simple bot choice: Indian March then War Path
        queue_free_op(state, "INDIANS", "march",    target)
        queue_free_op(state, "INDIANS", "war_path", target)

# 17  JANE MCCREA MURDERED
@register(17)
def evt_017_jane_mccrea(state, shaded=False):
    if shaded:
        remove_piece(state, "Indian_Village", None, 1, to_pool=False)
        push_history(state, "Jane McCrea backlash removes a Village")
    else:
        for name, sp in state["spaces"].items():
            if "Reserve" in name and sp.get("Patriot_Fort", 0):
                remove_piece(state, "Patriot_Fort", name, 1, to="available")
                push_history(state, f"Jane McCrea: Fort removed in {name}")
                break


# 26  JOSIAH MARTIN, NC ROYAL GOVERNOR, PLOTS
@register(26)
def evt_026_josiah_martin(state, shaded=False):
    """
    Unshaded – Place 1 British Fort *or* 2 Tories in North Carolina.
    Shaded   – Patriots may free March **then** free Battle in North Carolina.
    """
    from lod_ai.util.free_ops import queue_free_op
    province = "North_Carolina"

    if shaded:
        queue_free_op(state, "PATRIOTS", "march",  province)
        queue_free_op(state, "PATRIOTS", "battle", province)
    else:
        place_piece(state, "British_Tories", province, 2)    # Fort helper not ready yet

# 27  QUEEN’S RANGERS
@register(27)
def evt_027_queens_rangers(state, shaded=False):
    if shaded:
        cities = [n for n, sp in state["spaces"].items() if sp.get("type") == "City"]
        for name in cities[:2]:
            shift_support(state, name, -1)
            place_piece(state, "Patriot_Militia_U", name, 1)
        push_history(state, "Queen's Rangers suppressed by Patriot rallies")
    else:
        targets = [n for n, sp in state["spaces"].items()
                   if sp.get("type") == "Colony" and sp.get("British_Control")]
        for name in targets[:2]:
            moved = move_piece(state, "British_Tories", "available", name, 2)
            if moved < 2:
                move_piece(state, "British_Tories", "unavailable", name, 2 - moved)
        push_history(state, "Queen's Rangers deployed")


# 34  LORD SANDWICH
@register(34)
def evt_034_lord_sandwich(state, shaded=False):
    if shaded:
        state["ineligible_next"].add("BRITISH")
        shift = +1
    else:
        add_resource(state, "British", +6)
        shift = -1
    state["fni_level"] = max(0, min(4, state.get("fni_level", 0) + shift))


# 38  JOHNSON’S ROYAL GREENS
@register(38)
def evt_038_johnsons_royal_greens(state, shaded=False):
    if shaded:
        place_piece(state, "Patriot_Militia_U", "New_York", 3)
        push_history(state, "Johnson's Royal Greens countered by local militia")
        return

    target = "Quebec"

    def _pull(tag, qty):
        moved = move_piece(state, tag, "available", target, qty)
        if moved < qty:
            move_piece(state, tag, "unavailable", target, qty - moved)

    _pull("British_Regulars", 2)
    _pull("British_Tories", 2)
    state.setdefault("ineligible_next", set()).discard("BRITISH")
    push_history(state, f"Royal Greens reinforce {target}")


# 42  BRITISH ATTACK DANBURY
@register(42)
def evt_042_attack_danbury(state, shaded=False):
    if shaded:
        place_piece(state, "Patriot_Militia_U", "Connecticut", 3)
        place_piece(state, "Patriot_Continentals", "Connecticut", 1)
        push_history(state, "Battle of Ridgefield bolsters Connecticut")
    else:
        add_resource(state, "Patriots", -3)
        place_piece(state, "British_Tories", "Connecticut", 1)
        push_history(state, "Danbury raid: PAT -3 Resources")


# 44  EARL OF MANSFIELD RECALLED FROM PARIS
@register(44)
def evt_044_mansfield_recalled(state, shaded=False):
    if not shaded:
        state.setdefault("ineligible_next", set()).add("PATRIOTS")


# 47  TORIES TESTED
@register(47)
def evt_047_tories_tested(state, shaded=False):
    """
    Unshaded – Place 3 Tories in 1 Colony with British Control (pick Virginia).
    Shaded   – Replace all Tories in 1 Colony with Militia; place 2 Propaganda.
    """
    target = "Virginia"

    if shaded:
        tories = state["spaces"][target].get("British_Tories", 0)
        if tories:
            remove_piece(state, "British_Tories", target, tories, to="available")
            place_piece(state, "Patriot_Militia_U", target, tories)
        place_marker(state, "Propaganda", target, 2)
    else:
        place_piece(state, "British_Tories", target, 3)

# 50  ADMIRAL D’ESTAING — FRENCH FLEET ARRIVES
@register(50)
def evt_050_destaing_arrives(state, shaded=False):
    """
    Unshaded – French Ineligible through next card; remove 2 French Regulars
               from West Indies *or* map to Available.
    Shaded   – Place 2 Continentals & 2 French Regulars (Avail/WI) in 1 Colony.
    """
    if shaded:
        target = "Virginia"      # deterministic for now
        moved = move_piece(state, "French_Regulars", "available", target, 2)
        if moved < 2:
            move_piece(state, "French_Regulars", "West_Indies", target, 2 - moved)
        place_piece(state, "Patriot_Continentals", target, 2)
        return

    # unshaded ---------------------------------------------------------------
    removed = move_piece(state, "French_Regulars", WEST_INDIES_ID, "available", 2)
    if removed < 2:
        remove_piece(state, "French_Regulars", None, 2 - removed, to="available")
    state.setdefault("ineligible_next", set()).add("FRENCH")

# 55  FRENCH NAVY DOMINATES CARIBBEAN
@register(55)
def evt_055_french_navy(state, shaded=False):
    """
    Unshaded – Move 3 French Regulars to West Indies; French *may* free
               Battle there; Lower FNI 1.
    Shaded   – Move any 4 British Regulars to West Indies; British *must*
               free Battle there.
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        moved = 0
        for n, sp in state["spaces"].items():
            if moved == 4:
                break
            qty = sp.get("British_Regulars", 0)
            if qty:
                move_piece(state, "British_Regulars", n, WEST_INDIES_ID, min(qty, 4 - moved))
                moved += min(qty, 4 - moved)
        queue_free_op(state, "BRITISH", "battle", WEST_INDIES_ID)
    else:
        moved = 0
        for n, sp in state["spaces"].items():
            if moved == 3:
                break
            qty = sp.get("French_Regulars", 0)
            if qty:
                move_piece(state, "French_Regulars", n, WEST_INDIES_ID, min(qty, 3 - moved))
                moved += min(qty, 3 - moved)
        queue_free_op(state, "FRENCH", "battle", WEST_INDIES_ID)
        adjust_fni(state, -1)

# 58  MARQUIS DE LAFAYETTE ARRIVES
@register(58)
def evt_058_lafayette(state, shaded=False):
    add_resource(state, "Patriots", +3 if shaded else -4)

# 59  TRONSON DE COUDRAY
@register(59)
def evt_059_coudray(state, shaded=False):
    """
    Unshaded – “Arrogance damages coordination”:
        Remove 2 Continentals **and** 2 French Regulars from *one* space
        to Available.
    Shaded   – “Drowns in the Schuylkill River”:
        Patriot Resources +3.
    """
    if shaded:
        add_resource(state, "Patriots", +3)
        return

    # pick first space that has the required pieces
    for name, sp in state["spaces"].items():
        if sp.get("Patriot_Continentals", 0) >= 2 and sp.get("French_Regulars", 0) >= 2:
            remove_piece(state, "Patriot_Continentals", name, 2, to="available")
            remove_piece(state, "French_Regulars",     name, 2, to="available")
            push_history(state, f"Coudray: −2 CONT, −2 FR REG from {name}")
            break

# 60  COMTE D’ORVILLIERS BUILDS A FLEET
@register(60)
def evt_060_orvilliers(state, shaded=False):
    if shaded:
        adjust_fni(state, +1)
        add_resource(state, "British", -3)
    else:
        adjust_fni(state, -2)
        add_resource(state, "French",  -4)

# 61  VERGENNES
@register(61)
def evt_061_vergennes(state, shaded=False):
    if shaded:
        add_resource(state, "Patriots", +3)
        add_resource(state, "French",   +2)
    else:
        state.setdefault("ineligible_next", set()).add("PATRIOTS")


# 63  FRENCH AND SPANISH BESIEGE GIBRALTAR
@register(63)
def evt_063_gibraltar(state, shaded=False):
    """
    Unshaded – “British weather the storm”:
        • British Resources +1
        • French Navy Index –1 level
        • Remove 2 British Regulars from West Indies → Available
    Shaded   – “British struggle to defend”:
        • British Resources –5
    """
    if shaded:
        add_resource(state, "British", -5)
        return

    # --- unshaded -----------------------------------------------------------
    add_resource(state, "British", +1)
    adjust_fni(state, -1)
    move_piece(state, "British_Regulars", WEST_INDIES_ID, "available", 2)

# 69  ADMIRAL SUFFREN
@register(69)
def evt_069_suffren(state, shaded=False):
    if shaded:
        state["fni_level"] = min(4, state.get("fni_level", 0) + 1)
        add_resource(state, "French", +3)
    else:
        state["fni_level"] = max(0, state.get("fni_level", 0) - 2)
        add_resource(state, "British", +2)


# 71  TREATY OF AMITY & COMMERCE
@register(71)
def evt_071_treaty_amity(state, shaded=False):
    if shaded:
        add_resource(state, "French", +5)
        return

    pop = 0
    for sp in state["spaces"].values():
        if sp.get("type") == "City" and sp.get("Patriot_Control"):
            pop += sp.get("population", 0)
    add_resource(state, "Patriots", pop)
    push_history(state, f"Treaty of Amity: Patriots gain {pop} Resources")


# 74  CHICKASAW ALLY WITH THE BRITISH
@register(74)
def evt_074_chickasaw(state, shaded=False):
    """
    Unshaded – “Benefit from the alliance”:
        Indians *or* British add 1 Resource per 2 Indian Villages on map.
        (bot: give them to Indians.)
    Shaded   – “Battles in the back country”:
        In each of 2 spaces, remove either
          • 1 War Party + 2 Militia  OR
          • 2 War Parties + 1 Militia
        (bot: simply try WP-preferred first, then the other combo).
    """
    if not shaded:
        villages = sum(sp.get(VILLAGE, 0) for sp in state["spaces"].values())
        add_resource(state, "Indians", villages // 2)
        return

    # shaded ------------------------------------------------------------
    done = 0
    for name, sp in state["spaces"].items():
        if done == 2:
            break
        wp = sp.get("_WP_A", 0) + sp.get("_WP_U", 0)
        mil = sp.get("_Militia_A", 0) + sp.get("_Militia_U", 0)
        if wp + mil < 3:
            continue

        # try WP-heavy combo first
        removed = 0
        removed += remove_piece(state, "_WP_A", name, 2, to="available") \
                or remove_piece(state, "_WP_U", name, 2, to="available")
        removed += remove_piece(state, "MILITIA_U", name, 1, to="available") \
                or remove_piece(state, "MILITIA_A", name, 1, to="available")

        # if that failed, try Militia-heavy combo
        if removed < 3:
            remove_piece(state, "_WP_A", name, 1, to="available") \
                or remove_piece(state, "_WP_U", name, 1, to="available")
            remove_piece(state, "MILITIA_U", name, 2, to="available") \
                or remove_piece(state, "MILITIA_A", name, 2, to="available")

        push_history(state, f"Chickasaw back-country removals in {name}")
        done += 1

# 76  EDWARD HAND RAIDS
@register(76)
def evt_076_edward_hand(state, shaded=False):
    """
    Unshaded – “Three key lieutenants defect”:
        British replace 3 Militia with 3 Tories in one Province.
    Shaded   – “Squaw Campaign intimidates Indians”:
        British remove 2 Indian Villages anywhere.
    """
    if shaded:
        remove_piece(state, "VILLAGE", None, 2, to_pool=False)
        return

    # pick first Province with ≥3 Militia
    target = next((n for n,sp in state["spaces"].items()
                   if sp.get("Patriot_Militia_U",0)+sp.get("Patriot_Militia_A",0) >= 3), None)
    if not target:
        return

    replaced = 0
    for tag in ("MILITIA_A", "MILITIA_U"):
        while state["spaces"][target].get(tag, 0) and replaced < 3:
            remove_piece(state, tag, target, 1, to="available")
            replaced += 1
    place_piece(state, "TORY", target, replaced)
    push_history(state, f"Edward Hand: {replaced} Militia → Tories in {target}")

# 77  GENERAL BURGOYNE CRACKS DOWN
@register(77)
def evt_077_burgoyne(state, shaded=False):
    if shaded:
        affected = 0
        for name, sp in state["spaces"].items():
            if affected == 3:
                break
            if not any(tag.startswith("Indian_") for tag in sp):
                continue
            # remove a British piece, forts last
            if remove_piece(state, "REGULAR_BRI", name, 1, to="casualties"):
                pass
            elif remove_piece(state, "TORY", name, 1, to="casualties"):
                pass
            else:
                remove_piece(state, "FORT_BRI", name, 1, to="available")
            place_marker(state, "Raid", name)
            affected += 1
        push_history(state, "Burgoyne crackdown provokes raids")
    else:
        target = next((n for n, sp in state["spaces"].items()
                       if sp.get("British_Regulars") and
                          (sp.get("Indian_WP") or sp.get("VILLAGE"))), None)
        if target:
            place_with_caps(state, "Indian_Village", target)
        for sp in state["spaces"].values():
            if sp.get("Indian_WP_A", 0):
                sp["Indian_WP_U"] = sp.get("Indian_WP_U", 0) + sp.pop("Indian_WP_A")
        push_history(state, "Burgoyne encourages cooperation")


# 78  CHERRY VALLEY DESTROYED
@register(78)
def evt_078_cherry_valley(state, shaded=False):
    if shaded:
        added = 0
        for name, sp in state["spaces"].items():
            if added == 4:
                break
            if sp.get("British_Tories") or sp.get("Indian_WP"):
                place_piece(state, "Patriot_Militia_U", name, 1)
                added += 1
        push_history(state, "Cherry Valley: militia rally")
    else:
        total = 0
        for sp in list(state["spaces"].keys()):
            for tag in ("Patriot_Continentals", "Patriot_Militia_U", "Patriot_Militia_A"):
                count = state["spaces"][sp].get(tag, 0)
                if count and total < 1e9:  # just ensure iteration
                    pass
        removed_total = 0
        pat_tags = ("Patriot_Continentals", "Patriot_Militia_U", "Patriot_Militia_A")
        total_pieces = sum(sp.get(t, 0) for sp in state["spaces"].values() for t in pat_tags)
        to_remove = total_pieces // 4
        for name, sp in state["spaces"].items():
            for tag in pat_tags:
                if removed_total == to_remove:
                    break
                here = sp.get(tag, 0)
                if here:
                    n = min(here, to_remove - removed_total)
                    remove_piece(state, tag, name, n, to="available")
                    removed_total += n
            if removed_total == to_remove:
                break
        push_history(state, f"Cherry Valley intimidation removes {removed_total} Patriot pieces")


# 80  CONFUSION ALLOWS SLAVES TO ESCAPE
@register(80)
def evt_080_confusion_slaves(state, shaded=False):
    if shaded:
        push_history(state, "Confusion slaves shaded side has no effect")
        return

    fac = "BRITISH"
    spaces = [n for n, sp in state["spaces"].items() if sp.get("British_Regulars") or sp.get("British_Tories")]
    for name in spaces[:2]:
        removed = 0
        removed += remove_piece(state, "British_Regulars", name, 2 - removed, to="available")
        if removed < 2:
            remove_piece(state, "British_Tories", name, 2 - removed, to="available")
        push_history(state, f"Confusion: {fac} remove pieces in {name}")


# 88  “IF IT HADN’T BEEN SO FOGGY…”
@register(88)
def evt_088_foggy(state, shaded=False):
    fac = "PATRIOTS"
    moved = 0
    for name, sp in list(state["spaces"].items()):
        if moved == 2:
            break
        if sp.get("British_Regulars") and (sp.get("Patriot_Militia_U") or sp.get("Patriot_Militia_A") or sp.get("Patriot_Continentals")):
            total = move_piece(state, "Patriot_Continentals", name, "available", sp.get("Patriot_Continentals", 0))
            total += move_piece(state, "Patriot_Militia_U", name, "available", sp.get("Patriot_Militia_U", 0))
            total += move_piece(state, "Patriot_Militia_A", name, "available", sp.get("Patriot_Militia_A", 0))
            push_history(state, f"Foggy withdrawal from {name} ({total} pieces)")
            moved += 1


# 89  WAR DAMAGES COLONIES’ ECONOMY
@register(89)
def evt_089_war_damages(state, shaded=False):
    if shaded:
        replaced = 0
        for name, sp in state["spaces"].items():
            if replaced == 3:
                break
            qty = sp.get("British_Tories", 0)
            if qty:
                n = min(qty, 3 - replaced)
                remove_piece(state, "British_Tories", name, n, to="available")
                place_piece(state, "Patriot_Militia_U", name, n)
                replaced += n
        push_history(state, f"War damages: replaced {replaced} Tories with militia")
    else:
        replaced = 0
        for name, sp in state["spaces"].items():
            if replaced == 4:
                break
            for tag in ("Patriot_Militia_U", "Patriot_Militia_A", "Patriot_Continentals"):
                qty = sp.get(tag, 0)
                if qty:
                    n = min(qty, 4 - replaced)
                    remove_piece(state, tag, name, n, to="available")
                    place_piece(state, "British_Tories", name, n)
                    replaced += n
                if replaced == 4:
                    break
        push_history(state, f"War damages: replaced {replaced} Patriot units with Tories")


# 93  WYOMING MASSACRE
@register(93)
def evt_093_wyoming(state, shaded=False):
    if shaded:
        push_history(state, "Wyoming Massacre shaded: no effect")
        return

    cols = [n for n, sp in state["spaces"].items() if sp.get("type") == "Colony"]
    affected = 0
    for name in cols:
        if affected == 3:
            break
        shift_support(state, name, -1 if state["support"].get(name, 0) > 0 else +1)
        place_marker(state, "Raid", name)
        affected += 1
    push_history(state, f"Wyoming Massacre affects {affected} Colonies")
