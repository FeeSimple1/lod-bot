from lod_ai.cards import register
from .shared import add_resource, shift_support
from lod_ai.util.free_ops import queue_free_op
from lod_ai.board.pieces import (
    move_piece,
    place_piece,
    remove_piece,
    place_marker,
    place_with_caps,
)


def _pick_spaces_with_militia(state, max_spaces=4):
    """Return up to *max_spaces* IDs that contain Patriot Militia."""
    spaces = [
        name
        for name, sp in state["spaces"].items()
        if sp.get("Patriot_Militia_U", 0) or sp.get("Patriot_Militia_A", 0)
    ]
    spaces.sort()
    return spaces[:max_spaces]


# 2  COMMON SENSE
@register(2)
def evt_002_common_sense(state, shaded=False):
    """
    Unshaded – British may place 2 Regulars + 2 Tories and 2 Propaganda markers
               in any one City, then Resources +4.
    Shaded   – Shift 2 Cities 1 level toward Active Opposition and place
               2 Propaganda in each.
    """
    if shaded:
        for city in ("New_York_City", "Philadelphia"):
            shift_support(state, city, -1)
            place_marker(state, "Propaganda", city, 2)
    else:
        city = "Boston"                         # deterministic pick for now
        place_piece(state, "British_Regulars", city, 2)
        place_piece(state, "British_Tories",   city, 2)
        place_marker(state, "Propaganda", city, 2)
        add_resource(state, "British", +4)

# 4  THE PENOBSCOT EXPEDITION
@register(4)                       # Penobscot Expedition
def evt_004_penobscot(state, shaded=False):
    """
    Unshaded – Expedition fails: Patriot Resources –2; remove 3 Patriot Militia.
    Shaded   – Expedition succeeds: place 1 Patriot Fort and 3 Patriot Militia
               in Massachusetts (respecting Fort cap).
    """
    if shaded:
        place_with_caps(state, "Patriot_Fort", "Massachusetts")
        place_piece(state, "Patriot_Militia_U", "Massachusetts", 3)
    else:
        add_resource(state, "Patriots", -2)
        remove_piece(state, "Patriot_Militia_U", "Massachusetts", 3, to="available")

# 6  BENEDICT ARNOLD
@register(6)                       # Benedict Arnold
def evt_006_benedict_arnold(state, shaded=False):
    """
    Unshaded – Treachery: remove 1 Patriot Fort + 2 Patriot Militia from *one*
               Colony (to Casualties/Available).
    Shaded   – Heroic: remove 1 British Fort + 2 British cubes from *one* space
               (to Casualties).
    (For now we deterministically pick Virginia; later the bot/engine can choose.)
    """
    target = "Virginia"
    if shaded:
        remove_piece(state, "British_Fort",     target, 1, to="casualties")
        removed = remove_piece(state, "British_Regulars", target, 2, to="casualties")
        if removed < 2:
            # top up with Tories if Regulars insufficient
            remove_piece(state, "British_Tories", target, 2-removed, to="casualties")
    else:
        remove_piece(state, "Patriot_Fort",     target, 1, to="casualties")
        remove_piece(state, "Patriot_Militia_U", target, 2, to="available")

# 10  BENJAMIN FRANKLIN TRAVELS TO FRANCE
@register(10)   # Benjamin Franklin Travels to France
def evt_010_franklin_to_france(state, shaded=False):
    if shaded:
        add_resource(state, "French",   3)
        add_resource(state, "Patriots", 2)
    else:
        c1, c2 = pick_two_cities(state)
        shift_support(state, c1, +1)
        shift_support(state, c2, +1)

# 13  “…THE ORIGIN OF ALL OUR MISFORTUNES”
@register(13)
def evt_013_origin_misfortunes(state, shaded=False):
    """
    Unshaded – Patriot desertion this Winter.
    Shaded   – In up to 4 spaces with Militia, Patriots add 1 Active Militia.
    """
    if shaded:
        for space in _pick_spaces_with_militia(state, max_spaces=4):
            place_piece(state, "Patriot_Militia_A", space, 1)
    else:
        state["winter_flag"] = "PAT_DESERTION"

# 15  MORGAN’S RIFLES
@register(15)
def evt_015_morgans_rifles(state, shaded=False):
    """
    Unshaded – Shift Virginia 2 → Active Support; place 2 Tories there.
    Shaded   – Patriots free March, free Battle, then Partisans in any 1 Colony.
    """
    target = "Virginia"
    if shaded:
        # Patriots will get a free March and immediately Battle,
        # then may run a Partisans SA in any 1 Colony (Virginia by rule text).
        queue_free_op(state, "PATRIOTS", "march_battle")
        queue_free_op(state, "PATRIOTS", "partisans")    
    else:
        shift_support(state, target, +2)
        place_piece(state, "British_Tories", target, 2)

# 20  CONTINENTAL MARINES
@register(20)
def evt_020_continental_marines(state, shaded=False):
    """
    Unshaded – Patriots remove 4 Continentals → Available (anywhere on map).
    Shaded   – Patriots place 4 Continentals in New Jersey.
    """
    if shaded:
        place_piece(state, "Patriot_Continentals", "New_Jersey", 4)
        return

    removed = 0
    for space in list(state["spaces"]):
        removed += move_piece(state, "Patriot_Continentals", space, "available", 4 - removed)
        if removed == 4:
            break

# 24  DECLARATION OF INDEPENDENCE
@register(24)
def evt_024_declaration(state, shaded=False):
    """Declaration of Independence."""
    if shaded:
        targets = list(state["spaces"])[:3]
        for sid in targets:
            place_piece(state, "Patriot_Militia_U", sid)
            place_marker(state, "Propaganda", sid)
        place_with_caps(state, "Patriot_Fort", targets[0])
    else:
        remove_piece(state, "Patriot_Continentals", None, 2, to="available")
        remaining = 2
        remaining -= remove_piece(state, "Patriot_Militia_U", None, remaining, to="available")
        if remaining:
            remove_piece(state, "Patriot_Militia_A", None, remaining, to="available")
        remove_piece(state, "Patriot_Fort", None, 1, to="casualties")


# 28  BATTLE OF MOORE’S CREEK BRIDGE
@register(28)
def evt_028_moores_creek(state, shaded=False):
    """
    Unshaded – “Tories win”:  In any one space, replace **every Patriot Militia**
                (U or A) with **two Tories** each.
    Shaded   – “Patriots win”: In any one space, replace **every Tory** with
                **two Patriot Militia** each.
    """
    target = "North_Carolina"          # deterministic; swap later if desired

    if shaded:
        from_tag_u, from_tag_a = "British_Tories", None          # Tories have no U/A split
        to_tag                   = "Patriot_Militia_U"
    else:
        from_tag_u, from_tag_a = "Patriot_Militia_U", "Patriot_Militia_A"
        to_tag                  = "British_Tories"

    sp   = state["spaces"][target]
    qty  = sp.pop(from_tag_u, 0)
    qty += sp.pop(from_tag_a, 0) if from_tag_a else 0

    if qty:
        remove_piece(state, from_tag_u, target, qty, to="available")   # removed go to pool
        place_piece(state, to_tag, target, 2 * qty)
        push_history(state, f"Moore’s Creek: {qty}×{from_tag_u} → {2*qty}×{to_tag}")

# 29  EDWARD BANCROFT, BRITISH SPY
@register(29)
def evt_029_bancroft(state, shaded=False):
    """
    Unshaded – Reveal half of all hidden Patriot Militia on the map
               (rounded down), then British Resources +2.
    Shaded   – Bancroft's cover blown: Patriot Resources +3.
    """
    if shaded:
        add_resource(state, "Patriots", +3)
        return

    hidden_tag = "Patriot_Militia_U"
    active_tag = "Patriot_Militia_A"

    # --- count total hidden -------------------------------------------------
    total_hidden = sum(sp.get(hidden_tag, 0) for sp in state["spaces"].values())
    to_flip = total_hidden // 2
    flipped = 0

    # --- flip until quota reached ------------------------------------------
    for name, sp in state["spaces"].items():
        if flipped == to_flip:
            break
        n_here = sp.get(hidden_tag, 0)
        if not n_here:
            continue
        flip_now = min(n_here, to_flip - flipped)
        sp[hidden_tag] -= flip_now
        if sp[hidden_tag] == 0:
            del sp[hidden_tag]
        sp[active_tag] = sp.get(active_tag, 0) + flip_now
        flipped += flip_now

    add_resource(state, "British", +2)
    push_history(state, f"Bancroft flips {flipped} Militia (half of {total_hidden})")

# 30  HESSIANS
@register(30)
def evt_030_hessians(state, shaded=False):
    """Hessians deployment or settlement."""
    def _pull_regulars(loc: str, qty: int = 2) -> None:
        moved = move_piece(state, "British_Regulars", "available", loc, qty)
        if moved < qty:
            move_piece(state, "British_Regulars", "unavailable", loc, qty - moved)

    if shaded:
        total = sum(sp.get("British_Regulars", 0) for sp in state["spaces"].values())
        remove_qty = total // 5
        if remove_qty:
            remove_piece(state, "British_Regulars", None, remove_qty, to="available")
    else:
        eligible = [n for n, sp in state["spaces"].items() if sp.get("British_Regulars")]
        for loc in eligible[:3]:
            _pull_regulars(loc, 2)
        add_resource(state, "British", +2)


# 32  RULE BRITANNIA!
@register(32)
def evt_032_rule_britannia(state, shaded=False):
    """
    Unshaded – “Rule, Britannia! rule the waves”:
        Place up to 2 British Regulars *and* 2 Tories from Unavailable or
        Available into any one Colony (we choose Virginia).
    Shaded   – “Thy cities shall with commerce shine”:
        Any faction gains Resources equal to half the number of Cities that
        are under British Control (rounded down).  We grant them to Patriots.
    """
    # ---- helper to grab from available first, then unavailable -------------
    def _pull_from_pools(tag, qty):
        moved = move_piece(state, tag, "available", target, qty)
        if moved < qty:
            move_piece(state, tag, "unavailable", target, qty - moved)

    if shaded:
        british_cities = [
            n for n, sp in state["spaces"].items()
            if sp.get("British_Control") and sp.get("type") == "City"
        ]
        add_resource(state, "Patriots", len(british_cities) // 2)
        return

    # ---- unshaded: place pieces in one Colony ------------------------------
    target = "Virginia"                    # deterministic choice for now
    _pull_from_pools("British_Regulars", 2)
    _pull_from_pools("British_Tories",   2)

# 33  THE BURNING OF FALMOUTH
@register(33)
def evt_033_burning_falmouth(state, shaded=False):
    """
    Unshaded – Patriot Resources –3; Patriots remove any 2 Militia.
    Shaded   – Patriots free Rally in 2 spaces adjacent to Massachusetts;
               Patriot Resources +3.
    """
    from lod_ai.util.free_ops import queue_free_op

    if shaded:
        for prov in ("New_Hampshire", "Rhode_Island"):      # example picks
            queue_free_op(state, "PATRIOTS", "rally", prov)
        add_resource(state, "Patriots", +3)

    else:
        add_resource(state, "Patriots", -3)

        # Patriots choose any two Militia cubes (Active or Underground)
        cubes_needed = 2
        for space in state["spaces"].values():
            for militia_type in ("Patriot_Militia_U", "Patriot_Militia_A"):
                here = space.get(militia_type, 0)
                if here:
                    taken = min(here, cubes_needed)
                    remove_piece(state, militia_type, space.id, taken, to="available")
                    cubes_needed -= taken
                    if cubes_needed == 0:
                        return

# 35  TRYON PLOT
@register(35)
def evt_035_tryon_plot(state, shaded=False):
    """
    Unshaded – Governor Tryon’s work destroys magazines:
               • Remove two Patriot *pieces* (any type) in New York or New York City.
               • *All* Militia in that same space are Activated.
    Shaded   – Plot foiled:
               • Remove all Tories in New York or in one adjacent space.
    """
    target_space = "New_York"        # deterministic choice; bots or UI may vary

    if shaded:
        # Remove EVERY Tory Militia cube in target or an adjacent space.
        remove_piece(state, "British_Tories_U", target_space, 999, to="available")
        remove_piece(state, "British_Tories_A", target_space, 999, to="available")
    else:
        # 1. Remove any two Patriot pieces in the space (cubes or blocks).
        removed = 0
        for piece_id in list(state["spaces"][target_space].pieces):
            if removed == 2:
                break
            if piece_id.startswith("Patriot_"):
                remove_piece(state, piece_id, target_space, 1, to="casualties")
                removed += 1

        # 2. Activate every Militia there (flip U-side to A-side)
        for piece_id in list(state["spaces"][target_space].pieces):
            if piece_id.endswith("_Militia_U"):
                flip_piece(state, piece_id, target_space)  # becomes _Militia_A


# 41  WILLIAM PITT – AMERICA CAN’T BE CONQUERED
@register(41)
def evt_041_william_pitt(state, shaded=False):
    """
    Unshaded – Shift 2 Colonies 2 levels each toward Active Support.
    Shaded   – Shift 2 Colonies 2 levels each toward Active Opposition.
    """
    delta = +2 if not shaded else -2
    for col in ("Virginia", "North_Carolina"):
        shift_support(state, col, delta)

# 43  HMS RUSSIAN MERCHANT WITH 4 000 MUSKETS
@register(43)
def evt_043_russian_muskets(state, shaded=False):
    """
    #43 HMS Russian Merchant with 4 000 Muskets
    Unshaded – In up to three spaces that contain a British Regular,
               British may add up to two Tories / space (from Available
               or Unavailable).
    Shaded   – Ship sinks: British remove one in three Tories on map,
               rounding down (to Available).
    """
    if shaded:
        total = sum(sp.get("British_Tories", 0) for sp in state["spaces"].values())
        remove_qty = total // 3
        if remove_qty:
            remove_piece(state, "British_Tories", None, remove_qty, to="available")
    else:
        eligible = [n for n, sp in state["spaces"].items() if sp.get("British_Regulars", 0)]
        for loc in eligible[:3]:
            moved = move_piece(state, "British_Tories", "available", loc, 2)
            if moved < 2:
                move_piece(state, "British_Tories", "unavailable", loc, 2 - moved)


# 46  EDMUND BURKE ON CONCILIATION
@register(46)
def evt_046_burke(state, shaded=False):
    """
    Unshaded – Place 1 Tory in each of 3 spaces (we pick 3 Cities).
    Shaded   – Shift 2 Cities 1 level toward Passive Opposition.
    """
    cities = ("Boston", "New_York_City", "Charleston")
    if shaded:
        shift_support(state, "New_York_City", -1)
        shift_support(state, "Philadelphia",  -1)
    else:
        for city in cities:
            place_piece(state, "British_Tories", city)


# 49 CLAUDE LOUIS, COMTE de SAINT-GERMAIN
@register(49)
def evt_049_st_germain(state, shaded=False):
    """
    Unshaded – *Remove* up to 5 French Regulars to Unavailable.
    Shaded   – *Return* up to 5 French Regulars from Unavailable to Pool.
    """
    move = 5
    tag  = "French_Regulars"
    if shaded:
        avail = min(move, state["unavailable"].get(tag, 0))
        state["unavailable"][tag] -= avail
        state["pool"][tag] = state["pool"].get(tag, 0) + avail
    else:
        avail = min(move, state["pool"].get(tag, 0))
        state["pool"][tag] -= avail
        state["unavailable"][tag] = state["unavailable"].get(tag, 0) + avail


# 51  BERMUDA GUNPOWDER PLOT
@register(51)
def evt_051_bermuda_gunpowder(state, shaded=False):
    """
    Unshaded – British free March → Battle in 1 space; Attacker −2 losses.
    Shaded   – Patriots free March → Battle in 1 space; Defender +2 losses.
    """
    from lod_ai.util.free_ops import queue_free_op
    from lod_ai.util.loss_mod import queue_loss_mod

    if shaded:
        queue_loss_mod(state, def_delta=+2)
        queue_free_op(state, "PATRIOTS", "march_battle")
    else:
        queue_loss_mod(state, att_delta=-2)
        queue_free_op(state, "BRITISH", "march_battle")

# 53 FRENCH PORTS ACCEPT PATRIOT SHIPS  (already discussed)
@register(53)
def evt_053_french_ports_accept(state, shaded=False):
    if shaded:
        add_resource(state, "British",  -2)
        add_resource(state, "Patriots", +2)
        state["fni_level"] = max(0, min(4, state.get("fni_level", 0) + 1))
    else:
        add_resource(state, "British", +3)
        state["fni_level"] = max(0, min(4, state.get("fni_level", 0) - 2))


# 54  ANTOINE de SARTINE, SECRETARY OF THE NAVY
@register(54)
def evt_054_antoine_sartine(state, shaded=False):
    """
    Unshaded – Move 1 French Squadron/Blockade from West Indies → Unavailable.
    Shaded   – Move 2 Squadrons/Blockades from Unavailable → West Indies.
    """
    tag = "French_Squadron"
    if shaded:
        move_piece(state, tag, "unavailable", "west_indies", 2)
    else:
        move_piece(state, tag, "west_indies", "unavailable", 1)

# 56  TURGOT’S ECONOMIC LIBERALISM
@register(56)
def evt_056_turgot(state, shaded=False):
    add_resource(state, "Patriots", +3 if shaded else -3)

# 68  “FRENCH WANT CANADA”  –  TAKE QUÉBEC!
@register(68)
def evt_068_take_quebec(state, shaded=False):
    """
    Unshaded – Executing faction may move up to 6 of its cubes to Québec,
               then place one of its Forts there from Available.
    Shaded   – No effect.
    """
    if shaded:
        return
    fac = state.get("active", "FRENCH").title()   # default to French
    tag = f"{fac}_Regulars"
    moved = 0
    for name in list(state["spaces"]):
        if moved == 6:
            break
        moved += move_piece(state, tag, name, "Quebec", 6 - moved)
    place_with_caps(state, f"{fac}_Fort", "Quebec")

# 72  FRENCH SETTLERS HELP
@register(72)
def evt_072_french_settlers(state, shaded=False):
    """
    Unshaded – Place 1 friendly Fort/Village and 3 friendly Militia/War Parties
               in any one Indian Reserve Province (we pick Northwest if present).
    Shaded   – No effect.
    """
    if shaded:
        return
    target = ("Northwest" if "Northwest" in state["spaces"]
              else next(n for n in state["spaces"] if "Reserve" in n))
    place_with_caps(state, "Indian_Village", target)
    place_piece(state, "Indian_WarParties", target, 3)

# 75  CONGRESS’ SPEECH TO SIX NATIONS
@register(75)
def evt_075_speech_six_nations(state, shaded=False):
    """
    Unshaded – Indians free Gather in 3 spaces, then free War Path.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        return
    for _ in range(3):
        queue_free_op(state, "INDIANS", "gather")
    queue_free_op(state, "INDIANS", "war_path")

# 82  FRUSTRATED SHAWNEE WARRIORS ATTACK
@register(82)
def evt_082_shawnee(state, shaded=False):
    provs = ("Virginia", "Georgia", "North_Carolina", "South_Carolina")
    if shaded:
        removed = 3
        for p in provs:
            removed -= remove_piece(state, "Indian_WarParties", p, removed, to="casualties")
            if removed == 0:
                break
    else:
        for p in provs:
            place_piece(state, "Indian_WarParties", p)
            place_marker(state, "Raid", p)

# 83  GUY CARLETON & INDIANS NEGOTIATE
@register(83)
def evt_083_carleton_negotiates(state, shaded=False):
    if shaded:
        loc = "Quebec"
        place_piece(state, "Patriot_Militia_U", loc, 2)
        place_with_caps(state, "Patriot_Fort", loc)
    else:
        city = "Quebec_City"
        delta = 2 - state["support"].get(city, 0)
        shift_support(state, city, delta)
        place_piece(state, "Indian_WarParties", "Quebec", 2)


# 84  SIX NATIONS AID THE WAR
@register(84)
def evt_084_six_nations(state, shaded=False):
    """
    Unshaded – Indians free Gather in 2 Colonies.
    Shaded   – (no free ops)
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        return
    queue_free_op(state, "INDIANS", "gather")
    queue_free_op(state, "INDIANS", "gather")


# 86  STOCKBRIDGE INDIANS
@register(86)
def evt_086_stockbridge(state, shaded=False):
    """
    Unshaded – Activate all Militia in Massachusetts *or* a space with
               an Indian piece (we choose Massachusetts).
    Shaded   – Add 3 Militia in the same space.
    """
    target = "Massachusetts"
    sp = state["spaces"][target]
    if shaded:
        place_piece(state, "Patriot_Militia_U", target, 3)
    else:
        flip = sp.pop("Patriot_Militia_U", 0)
        sp["Patriot_Militia_A"] = sp.get("Patriot_Militia_A", 0) + flip
        push_history(state, f"Stockbridge flip {flip} Militia in {target}")


# 90  “THE WORLD TURNED UPSIDE DOWN”
@register(90)
def evt_090_world_turned_upside_down(state, shaded=False):
    """Handle card #90, “The World Turned Upside Down.”"""

    if shaded:
        # Remove 2 British Regulars anywhere to Casualties.
        remove_piece(state, "British_Regulars", None, 2, to="casualties")
        return

    # --- unshaded ---------------------------------------------------------
    # Prefer to place an Indian Village in the first Reserve province.
    reserve = next(
        (
            name
            for name, info in state["spaces"].items()
            if info.get("type") == "Reserve" or "Reserve" in name
        ),
        None,
    )

    placed = 0
    if reserve:
        placed = place_with_caps(state, "Indian_Village", reserve)

    if placed == 0:
        # No Village available/cap reached – place a Fort in Virginia instead.
        place_with_caps(state, "British_Fort", "Virginia")

# 91  INDIANS HELP BRITISH OUTSIDE COLONIES
@register(91)
def evt_091_indians_help(state, shaded=False):
    """Handle card #91, Indians Help British Outside Colonies."""

    # Identify the first Reserve province on the map.
    reserve = next(
        (
            name
            for name, info in state["spaces"].items()
            if info.get("type") == "Reserve" or "Reserve" in name
        ),
        None,
    )

    if not reserve:
        return

    if shaded:
        sp = state["spaces"][reserve]
        for tag in ("Indian_Village", "Indian_WarParties"):
            if sp.get(tag, 0):
                remove_piece(state, tag, reserve, 1)
                break
    else:
        place_with_caps(state, "Indian_Village", reserve)


# 92  CHEROKEES SUPPLIED BY THE BRITISH
@register(92)
def evt_092_cherokees_supplied(state, shaded=False):
    """
    Unshaded – Add a second Fort/Village where you already have exactly one.
    Shaded   – No effect.
    """
    if shaded:
        return
    for name, sp in state["spaces"].items():
        if sp.get("British_Fort", 0) == 1:
            place_with_caps(state, "British_Fort", name)
            return
        if sp.get("Indian_Village", 0) == 1:
            place_with_caps(state, "Indian_Village", name)
            return
