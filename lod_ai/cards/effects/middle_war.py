"""
middle_war.py – Event handlers for 1777-1778 cards
--------------------------------------------------
IDs covered (32): 3 5 8 9 11 12 14 17 26 27 34 38 42 44 47 50
                  55 58 59 60 61 69 71 74 76 77 78 80 88 89 93
Replace each _todo with real logic once piece / marker helpers exist.
"""

from lod_ai.cards import register
from .shared import add_resource, shift_support, push_history
from lod_ai.util.free_ops import queue_free_op


# ---------------------------------------------------- helpers ------------ #

def _todo(_state):
    """Placeholder while piece-placement helpers are under construction."""
    push_history(_state, "TODO: card effect not implemented yet")


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
            remove_piece(state, None, prov, 999, to="available")  # any Patriot piece

# 5  WILLIAM ALEXANDER, LORD STIRLING
@register(5)
def evt_005_lord_stirling(state, shaded=False):
    """
    Unshaded – Patriots Ineligible next card.
    Shaded   – Patriots free March + Battle.
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        queue_free_op(state, "PATRIOTS", "march_battle")
    else:
        state.setdefault("ineligible_next", set()).add("PATRIOTS")
    push_history(state, "Lord Stirling event resolved")

# 8  CULPEPER SPY RING
@register(8)
def evt_008_culpeper_ring(state, shaded=False):
    return _todo(state)          # needs place_piece / activate helpers


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
    return _todo(state)


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
        queue_free_op(state, "PATRIOTS", "march_battle", target)
    else:
        # simple bot choice: Indian March then War Path
        queue_free_op(state, "INDIANS", "march",    target)
        queue_free_op(state, "INDIANS", "war_path", target)

# 17  JANE MCCREA MURDERED
@register(17)
def evt_017_jane_mccrea(state, shaded=False):
    return _todo(state)


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
        queue_free_op(state, "PATRIOTS", "march_battle", province)
    else:
        place_piece(state, "British_Tories", province, 2)    # Fort helper not ready yet

# 27  QUEEN’S RANGERS
@register(27)
def evt_027_queens_rangers(state, shaded=False):
    return _todo(state)


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
    return _todo(state)


# 42  BRITISH ATTACK DANBURY
@register(42)
def evt_042_attack_danbury(state, shaded=False):
    if shaded:
        return _todo(state)      # needs piece helpers
    add_resource(state, "Patriots", -3)
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
            move_piece(state, "French_Regulars", "west_indies", target, 2 - moved)
        place_piece(state, "Patriot_Continentals", target, 2)
        return

    # unshaded ---------------------------------------------------------------
    removed = move_piece(state, "French_Regulars", "west_indies", "available", 2)
    if removed < 2:
        remove_piece(state, "French_Regulars", None, 2 - removed, to="available")
    state.setdefault("ineligible_next", set()).add("FRENCH")

# 54  ANTOINE de SARTINE
@register(54)
def evt_054_antoine_sartine(state, shaded=False):
    """
    Unshaded – move 1 French Squadron from West Indies → Unavailable.
    Shaded   – move 2 Squadrons/Blockades from Unavailable → West Indies.
    """
    tag = "French_Squadron"
    if shaded:
        move_piece(state, tag, "unavailable", "west_indies", 2)
    else:
        move_piece(state, tag, "west_indies", "unavailable", 1)

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
                move_piece(state, "British_Regulars", n, "west_indies", min(qty, 4 - moved))
                moved += min(qty, 4 - moved)
        queue_free_op(state, "BRITISH", "battle", "west_indies")
    else:
        moved = 0
        for n, sp in state["spaces"].items():
            if moved == 3:
                break
            qty = sp.get("French_Regulars", 0)
            if qty:
                move_piece(state, "French_Regulars", n, "west_indies", min(qty, 3 - moved))
                moved += min(qty, 3 - moved)
        queue_free_op(state, "FRENCH", "battle", "west_indies")
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
    move_piece(state, "British_Regulars", "west_indies", "available", 2)

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
    else:
        # population-based helper not ready → stub for now
        return _todo(state)


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
        villages = sum(sp.get("Indian_Village", 0) for sp in state["spaces"].values())
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
        removed += remove_piece(state, "Patriot_Militia_U", name, 1, to="available") \
                or remove_piece(state, "Patriot_Militia_A", name, 1, to="available")

        # if that failed, try Militia-heavy combo
        if removed < 3:
            remove_piece(state, "_WP_A", name, 1, to="available") \
                or remove_piece(state, "_WP_U", name, 1, to="available")
            remove_piece(state, "Patriot_Militia_U", name, 2, to="available") \
                or remove_piece(state, "Patriot_Militia_A", name, 2, to="available")

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
        remove_piece(state, "Indian_Village", None, 2, to_pool=False)
        return

    # pick first Province with ≥3 Militia
    target = next((n for n,sp in state["spaces"].items()
                   if sp.get("Patriot_Militia_U",0)+sp.get("Patriot_Militia_A",0) >= 3), None)
    if not target:
        return

    replaced = 0
    for tag in ("Patriot_Militia_A", "Patriot_Militia_U"):
        while state["spaces"][target].get(tag, 0) and replaced < 3:
            remove_piece(state, tag, target, 1, to="available")
            replaced += 1
    place_piece(state, "British_Tories", target, replaced)
    push_history(state, f"Edward Hand: {replaced} Militia → Tories in {target}")

# 77  GENERAL BURGOYNE CRACKS DOWN
@register(77)
def evt_077_burgoyne(state, shaded=False):
    return _todo(state)


# 78  CHERRY VALLEY DESTROYED
@register(78)
def evt_078_cherry_valley(state, shaded=False):
    return _todo(state)


# 80  CONFUSION ALLOWS SLAVES TO ESCAPE
@register(80)
def evt_080_confusion_slaves(state, shaded=False):
    return _todo(state)


# 88  “IF IT HADN’T BEEN SO FOGGY…”
@register(88)
def evt_088_foggy(state, shaded=False):
    return _todo(state)


# 89  WAR DAMAGES COLONIES’ ECONOMY
@register(89)
def evt_089_war_damages(state, shaded=False):
    return _todo(state)


# 93  WYOMING MASSACRE
@register(93)
def evt_093_wyoming(state, shaded=False):
    return _todo(state)