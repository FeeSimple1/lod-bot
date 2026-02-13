from lod_ai.cards import register
from .shared import add_resource, shift_support, adjust_fni, pick_cities, pick_colonies, pick_two_cities
from lod_ai.util.free_ops import queue_free_op
from lod_ai.board.pieces import (
    move_piece,
    place_piece,
    remove_piece,
    place_marker,
    place_with_caps,
)
from lod_ai.util.history import push_history

from lod_ai.rules_consts import (
    REGULAR_BRI, REGULAR_PAT, REGULAR_FRE, TORY,
    MILITIA_A, MILITIA_U, WARPARTY_A, WARPARTY_U,
    FORT_BRI, FORT_PAT, VILLAGE,
    PROPAGANDA, RAID, WEST_INDIES_ID,
    BRITISH, PATRIOTS, FRENCH, INDIANS,
    ACTIVE_SUPPORT,
)
from lod_ai.util.naval import move_blockades_to_unavailable, move_blockades_to_west_indies

def _pick_spaces_with_militia(state, max_spaces=4):
    """Return up to *max_spaces* IDs that contain Patriot Militia."""
    spaces = [
        name
        for name, sp in state["spaces"].items()
        if sp.get(MILITIA_U, 0) or sp.get(MILITIA_A, 0)
    ]
    spaces.sort()
    return spaces[:max_spaces]

_RESERVE_PROVINCES = ("Northwest", "Southwest", "Quebec", "Florida")


def _reserve_provinces(state):
    return [name for name in _RESERVE_PROVINCES if name in state.get("spaces", {})]


def _available_base_slots(state, space_id: str) -> int:
    sp = state.get("spaces", {}).get(space_id, {})
    total = sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0) + sp.get(VILLAGE, 0)
    return max(0, 2 - total)


def _shift_support_toward(state, space_id: str, target: int, steps: int = 1) -> None:
    for _ in range(steps):
        cur = state.get("support", {}).get(space_id, 0)
        if cur == target:
            return
        delta = 1 if cur < target else -1
        shift_support(state, space_id, delta)


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
        for city in pick_cities(state, 2):
            shift_support(state, city, -1)
            place_marker(state, PROPAGANDA, city, 2)
    else:
        cities = pick_cities(state, 1)
        if not cities:
            return
        city = cities[0]
        place_piece(state, REGULAR_BRI, city, 2)
        place_piece(state, TORY,   city, 2)
        place_marker(state, PROPAGANDA, city, 2)
        add_resource(state, BRITISH, +4)

# 4  THE PENOBSCOT EXPEDITION
@register(4)                       # Penobscot Expedition
def evt_004_penobscot(state, shaded=False):
    """
    Unshaded – Expedition fails: Patriot Resources –2; remove 3 Patriot Militia.
    Shaded   – Expedition succeeds: place 1 Patriot Fort and 3 Patriot Militia
               in Massachusetts (respecting Fort cap).
    """
    if shaded:
        executor = str(state.get("active", "")).upper()
        target = "Massachusetts"
        if executor in (PATRIOTS, FRENCH):
            place_with_caps(state, FORT_PAT, target)
            place_piece(state, MILITIA_U, target, 3)
        elif executor in (BRITISH, INDIANS):
            place_with_caps(state, VILLAGE, target)
            place_piece(state, WARPARTY_U, target, 3)
        else:
            push_history(state, "Penobscot shaded: no executing faction; no pieces placed")
    else:
        add_resource(state, PATRIOTS, -2)
        # Remove 3 Militia anywhere on the map, preferring Underground
        removed = remove_piece(state, MILITIA_U, None, 3, to="available")
        if removed < 3:
            remove_piece(state, MILITIA_A, None, 3 - removed, to="available")

# 6  BENEDICT ARNOLD
@register(6)                       # Benedict Arnold
def evt_006_benedict_arnold(state, shaded=False):
    """
    Unshaded – Treachery: remove 1 Patriot Fort + 2 Patriot Militia from *one*
               Colony (to Casualties/Available).
    Shaded   – Heroic: remove 1 British Fort + 2 British cubes from *one* space
               (to Casualties).
    """
    spaces_sorted = sorted(state["spaces"])

    if shaded:
        candidates = [
            sid for sid in spaces_sorted
            if state["spaces"][sid].get(FORT_BRI)
            or state["spaces"][sid].get(REGULAR_BRI)
            or state["spaces"][sid].get(TORY)
        ]
        target = candidates[0] if candidates else (spaces_sorted[0] if spaces_sorted else None)
        if not target:
            return
        remove_piece(state, FORT_BRI,     target, 1, to="casualties")
        removed = remove_piece(state, REGULAR_BRI, target, 2, to="casualties")
        if removed < 2:
            # top up with Tories if Regulars insufficient
            remove_piece(state, TORY, target, 2-removed, to="casualties")
        return

    colony_choices = pick_colonies(state, 1)
    if not colony_choices:
        return

    target = colony_choices[0]
    remove_piece(state, FORT_PAT,     target, 1, to="casualties")
    removed = remove_piece(state, MILITIA_U, target, 2, to="available")
    if removed < 2:
        remove_piece(state, MILITIA_A, target, 2 - removed, to="available")

# 10  BENJAMIN FRANKLIN TRAVELS TO FRANCE
@register(10)   # Benjamin Franklin Travels to France
def evt_010_franklin_to_france(state, shaded=False):
    if shaded:
        add_resource(state, FRENCH,   3)
        add_resource(state, PATRIOTS, 2)
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
            place_piece(state, MILITIA_A, space, 1)
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
        colony = "Virginia"  # deterministic for now; keep all three in same space
        queue_free_op(state, PATRIOTS, "march",    colony)
        queue_free_op(state, PATRIOTS, "battle",   colony)
        queue_free_op(state, PATRIOTS, "partisans", colony)
    else:
        shift_support(state, "Virginia", +2)
        place_piece(state, TORY, "Virginia", 2)

# 20  CONTINENTAL MARINES
@register(20)
def evt_020_continental_marines(state, shaded=False):
    """
    Unshaded – Patriots remove 4 Continentals → Available (anywhere on map).
    Shaded   – Patriots place 4 Continentals in New Jersey.
    """
    if shaded:
        place_piece(state, REGULAR_PAT, "New_Jersey", 4)
        return

    removed = 0
    for space in list(state["spaces"]):
        removed += move_piece(state, REGULAR_PAT, space, "available", 4 - removed)
        if removed == 4:
            break

# 24  DECLARATION OF INDEPENDENCE
@register(24)
def evt_024_declaration(state, shaded=False):
    """Declaration of Independence."""
    if shaded:
        targets = list(state["spaces"])[:3]
        pool = state.setdefault("available", {})
        pool[MILITIA_U] = max(pool.get(MILITIA_U, 0), 3)
        pool[FORT_PAT] = max(pool.get(FORT_PAT, 0), 1)
        for sid in targets:
            place_piece(state, MILITIA_U, sid, 1)
            place_marker(state, PROPAGANDA, sid, 1)
        if targets:
            place_with_caps(state, FORT_PAT, targets[0])
        return

    removed_continentals = remove_piece(state, REGULAR_PAT, None, 2)
    removed_militia = remove_piece(state, MILITIA_U, None, 2, to="available")
    if removed_militia < 2:
        remove_piece(state, MILITIA_A, None, 2 - removed_militia, to="available")
    remove_piece(state, FORT_PAT, None, 1)

# 28  BATTLE OF MOORE’S CREEK BRIDGE
@register(28)
def evt_028_moores_creek(state, shaded=False):
    """
    Unshaded – “Tories win”:  In any one space, replace **every Patriot Militia**
                (U or A) with **two Tories** each.
    Shaded   – “Patriots win”: In any one space, replace **every Tory** with
                **two Patriot Militia** each.
    """
    targets = state.get("spaces", {})
    if not targets:
        return
    preferred = [
        sid for sid, sp in targets.items()
        if (sp.get(TORY) and shaded) or ((sp.get(MILITIA_U) or sp.get(MILITIA_A)) and not shaded)
    ]
    target_list = sorted(preferred or targets)
    target = target_list[0]
    sp = state["spaces"].get(target, {})

    if shaded:
        # Replace every Tory with twice as many Underground Militia
        tories = sp.get(TORY, 0)
        if tories:
            pool = state.setdefault("available", {})
            pool[MILITIA_U] = max(pool.get(MILITIA_U, 0), 2 * tories)
            remove_piece(state, TORY, target, tories, to="available")
            place_piece(state, MILITIA_U, target, 2 * tories)
    else:
        # Replace every Militia (U and A) with twice as many Tories
        mu = sp.get(MILITIA_U, 0)
        ma = sp.get(MILITIA_A, 0)
        total = mu + ma
        if total:
            pool = state.setdefault("available", {})
            pool[TORY] = max(pool.get(TORY, 0), 2 * total)
            if mu:
                remove_piece(state, MILITIA_U, target, mu, to="available")
            if ma:
                remove_piece(state, MILITIA_A, target, ma, to="available")
            place_piece(state, TORY, target, 2 * total)

# 29  EDWARD BANCROFT, BRITISH SPY
@register(29)
def evt_029_bancroft(state, shaded=False):
    """
    Unshaded only – Patriots or Indians must Activate their Militia or
    War Parties until 1/2 of them are Active (rounded down).
    """
    if shaded:
        return

    def _pick_target_faction() -> str:
        explicit = state.get("card29_target") or state.get("bancroft_target")
        if explicit:
            choice = str(explicit).upper()
            if choice in {PATRIOTS, INDIANS}:
                return choice

        militia_total = sum(
            sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0)
            for sp in state["spaces"].values()
        )
        warparty_total = sum(
            sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0)
            for sp in state["spaces"].values()
        )
        return INDIANS if warparty_total > militia_total else PATRIOTS

    target_faction = _pick_target_faction()
    hidden_tag, active_tag = (
        (MILITIA_U, MILITIA_A)
        if target_faction == PATRIOTS
        else (WARPARTY_U, WARPARTY_A)
    )

    total = sum(sp.get(hidden_tag, 0) + sp.get(active_tag, 0)
                for sp in state["spaces"].values())
    if total == 0:
        return

    target_active = total // 2
    cur_active = sum(sp.get(active_tag, 0) for sp in state["spaces"].values())
    need = max(0, target_active - cur_active)
    if need == 0:
        return

    flipped = 0
    for _, sp in state["spaces"].items():
        if flipped == need:
            break
        here = sp.get(hidden_tag, 0)
        if here:
            take = min(here, need - flipped)
            sp[hidden_tag] -= take
            if sp[hidden_tag] == 0:
                del sp[hidden_tag]
            sp[active_tag] = sp.get(active_tag, 0) + take
            flipped += take

    push_history(
        state,
        f"Bancroft activates {flipped} for {target_faction} (to reach {target_active} Active)",
    )

# 30  HESSIANS
@register(30)
def evt_030_hessians(state, shaded=False):
    """Hessians deployment or settlement."""
    def _pull_regulars(loc: str, qty: int = 2) -> None:
        moved = move_piece(state, REGULAR_BRI, "available", loc, qty)
        if moved < qty:
            move_piece(state, REGULAR_BRI, "unavailable", loc, qty - moved)

    if shaded:
        total = sum(sp.get(REGULAR_BRI, 0) for sp in state["spaces"].values())
        remove_qty = total // 5
        if remove_qty:
            remove_piece(state, REGULAR_BRI, None, remove_qty, to="available")
    else:
        eligible = [n for n, sp in state["spaces"].items()
                    if sp.get(REGULAR_BRI) and sp.get("British_Control")]
        for loc in eligible[:3]:
            _pull_regulars(loc, 2)
        add_resource(state, BRITISH, +2)

# 32  RULE BRITANNIA!
@register(32)
def evt_032_rule_britannia(state, shaded=False):
    """
    Unshaded – “Rule, Britannia! rule the waves”:
        Place up to 2 British Regulars *and* 2 Tories from Unavailable or
        Available into any one Colony.
    Shaded   – “Thy cities shall with commerce shine”:
        Any faction gains Resources equal to half the number of Cities that
        are under British Control (rounded down).
    """
    # ---- helper to grab from available first, then unavailable -------------
    def _pull_from_pools(tag, qty):
        moved = move_piece(state, tag, "available", target, qty)
        if moved < qty:
            move_piece(state, tag, "unavailable", target, qty - moved)

    if shaded:
        cities = pick_cities(state, len(state.get("spaces", {})))
        british_cities = [city for city in cities if state["spaces"][city].get("British_Control")]
        recipient = str(state.get("active", BRITISH)).upper()
        add_resource(state, recipient, len(british_cities) // 2)
        return

    # ---- unshaded: place pieces in one Colony ------------------------------
    colony_choices = state.get("rule_britannia_colony")
    if colony_choices:
        target = str(colony_choices)
    else:
        colonies = pick_colonies(state, 1)
        if not colonies:
            return
        target = colonies[0]
    _pull_from_pools(REGULAR_BRI, 2)
    _pull_from_pools(TORY,   2)

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
        for prov in ("Boston", "Connecticut_Rhode_Island"):  # both adjacent to Massachusetts
            queue_free_op(state, PATRIOTS, "rally", prov)
        add_resource(state, PATRIOTS, +3)

    else:
        add_resource(state, PATRIOTS, -3)

        # Patriots choose any two Militia cubes (Active or Underground)
        cubes_needed = 2
        for sid, sp in state["spaces"].items():
            for militia_type in (MILITIA_U, MILITIA_A):
                here = sp.get(militia_type, 0)
                if here:
                    taken = min(here, cubes_needed)
                    remove_piece(state, militia_type, sid, taken, to="available")
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
    target_space = "New_York"  # deterministic choice

    if shaded:
        # Remove all Tories in New York (adjacent space variant omitted deterministically)
        remove_piece(state, TORY, target_space, 999, to="available")
    else:
        # Remove two Patriot pieces in the target, then Activate all Militia there
        removed = 0
        # Prioritise cubes before Forts per general removal guidance
        for tag in (REGULAR_PAT, MILITIA_A, MILITIA_U, FORT_PAT):
            if removed == 2:
                break
            avail = state["spaces"][target_space].get(tag, 0)
            if avail:
                take = min(avail, 2 - removed)
                remove_piece(state, tag, target_space, take, to="available")
                removed += take
        # Flip any Underground Militia Active
        sp = state["spaces"][target_space]
        mu = sp.get(MILITIA_U, 0)
        if mu:
            sp[MILITIA_U] = 0
            sp[MILITIA_A] = sp.get(MILITIA_A, 0) + mu

# 41  WILLIAM PITT – AMERICA CAN’T BE CONQUERED
@register(41)
def evt_041_william_pitt(state, shaded=False):
    """
    Unshaded – Shift 2 Colonies 2 levels each toward Passive Support.
    Shaded   – Shift 2 Colonies 2 levels each toward Passive Opposition.
    """
    target = +1 if not shaded else -1
    colonies = pick_colonies(state, 2)
    for col in colonies:
        _shift_support_toward(state, col, target, steps=2)

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
        total = sum(sp.get(TORY, 0) for sp in state["spaces"].values())
        remove_qty = total // 3
        if remove_qty:
            remove_piece(state, TORY, None, remove_qty, to="available")
    else:
        eligible = [n for n, sp in state["spaces"].items() if sp.get(REGULAR_BRI, 0)]
        for loc in eligible[:3]:
            moved = move_piece(state, TORY, "available", loc, 2)
            if moved < 2:
                move_piece(state, TORY, "unavailable", loc, 2 - moved)


# 46  EDMUND BURKE ON CONCILIATION
@register(46)
def evt_046_burke(state, shaded=False):
    """
    Unshaded – Place 1 Tory in each of 3 spaces.
    Shaded   – Shift 2 Cities 1 level toward Passive Opposition.
    """
    if shaded:
        for city in pick_cities(state, 2):
            _shift_support_toward(state, city, -1, steps=1)
    else:
        targets = sorted(state.get("spaces", {}))[:3]
        for space in targets:
            moved = move_piece(state, TORY, "available", space, 1)
            if moved < 1:
                move_piece(state, TORY, "unavailable", space, 1 - moved)


# 49 CLAUDE LOUIS, COMTE de SAINT-GERMAIN
@register(49)
def evt_049_st_germain(state, shaded=False):
    """
    Unshaded – *Remove* up to 5 French Regulars to Unavailable.
    Shaded   – *Return* up to 5 French Regulars from Unavailable to Pool.
    """
    move = 5
    tag  = REGULAR_FRE
    if shaded:
        moved = move_piece(state, tag, "unavailable", "available", move)
    else:
        moved = move_piece(state, tag, "available",   "unavailable", move)



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
        queue_loss_mod(state, None, 0, +2)    # (space=None, att_delta, def_delta)
        queue_free_op(state, PATRIOTS, "march")
        queue_free_op(state, PATRIOTS, "battle")
    else:
        queue_loss_mod(state, None, -2, 0)
        queue_free_op(state, BRITISH, "march")
        queue_free_op(state, BRITISH, "battle")

# 53 FRENCH PORTS ACCEPT PATRIOT SHIPS  (already discussed)
@register(53)
def evt_053_french_ports_accept(state, shaded=False):
    if shaded:
        add_resource(state, BRITISH,  -2)
        add_resource(state, PATRIOTS, +2)
        adjust_fni(state, +1)
    else:
        add_resource(state, BRITISH, +3)
        adjust_fni(state, -2)

# 54  ANTOINE de SARTINE, SECRETARY OF THE NAVY
@register(54)
def evt_054_antoine_sartine(state, shaded=False):
    """
    Unshaded – Move 1 Blockade from West Indies to Unavailable (i.e., off-map).
    Shaded   – Move up to 2 Blockades from Unavailable to West Indies, up to cap.
    """
    if shaded:
        moved = move_blockades_to_west_indies(state, 2)
        if moved:
            push_history(state, f"Antoine de Sartine: {moved} Squadron/Blockade to West Indies")
    else:
        moved = move_blockades_to_unavailable(state, 1)
        if moved:
            push_history(state, "Antoine de Sartine: Squadron/Blockade to Unavailable")

# 56  TURGOT’S ECONOMIC LIBERALISM
@register(56)
def evt_056_turgot(state, shaded=False):
    add_resource(state, PATRIOTS, +3 if shaded else -3)

# 68  “FRENCH WANT CANADA”  –  TAKE QUÉBEC!
@register(68)
def evt_068_take_quebec(state, shaded=False):
    """
    Unshaded – Executing faction may move up to 6 of its cubes to Québec,
               then place 1 friendly Fort there from Available.
               (Cubes = Regulars/Continentals/Tories by faction.)
    Shaded   – No effect.
    """
    if shaded:
        return

    # Use canonical constants; keep import local so no other file edits are needed.
    from lod_ai.rules_consts import (
        REGULAR_BRI, REGULAR_PAT, REGULAR_FRE, TORY,
        FORT_BRI, FORT_PAT, WEST_INDIES_ID
    )

    fac  = str(state.get("active", FRENCH)).upper()
    dest = "Quebec"

    # Which "cubes" the executing faction may move
    cubes_by_faction = {
        BRITISH:  (REGULAR_BRI, TORY),
        PATRIOTS: (REGULAR_PAT,),
        FRENCH:   (REGULAR_FRE,),
        INDIANS:  (),  # Indians have no cubes
    }

    # Friendly Fort by coalition (FRENCH/PATRIOTS share PAT fort; BRITISH/INDIANS share BRI fort)
    friendly_fort = FORT_PAT if fac in (FRENCH, PATRIOTS) else FORT_BRI

    moved = 0
    for name in list(state["spaces"].keys()):
        if moved >= 6:
            break
        # Exclude destination and non‑map/pool areas
        if name in (dest, WEST_INDIES_ID, "available", "unavailable", "out_of_play"):
            continue
        for tag in cubes_by_faction.get(fac, ()):
            remain = 6 - moved
            if remain <= 0:
                break
            moved += move_piece(state, tag, name, dest, remain)
            if moved >= 6:
                break

    place_with_caps(state, friendly_fort, dest)

# 72  FRENCH SETTLERS HELP
@register(72)
def evt_072_french_settlers(state, shaded=False):
    """
    Unshaded – Place 1 friendly Fort/Village and 3 friendly Militia/War Parties
               in any one Indian Reserve Province (Northwest preferred).
    Shaded   – No effect.
    """
    if shaded:
        return

    # Canonical constants; local import keeps the change self‑contained.
    from lod_ai.rules_consts import (
        FORT_BRI, FORT_PAT, VILLAGE, REGULAR_BRI, REGULAR_PAT, REGULAR_FRE, TORY,
        MILITIA_U, WARPARTY_U,
    )

    fac = str(state.get("active", "")).upper()
    spaces = state["spaces"]
    pool = state.setdefault("available", {})

    reserve_candidates = _reserve_provinces(state)
    if not reserve_candidates:
        return
    target = reserve_candidates[0]

    def _available_count(tag: str) -> int:
        if tag in (MILITIA_U,):
            return pool.get(MILITIA_U, 0)
        if tag in (WARPARTY_U,):
            return pool.get(WARPARTY_U, 0)
        return pool.get(tag, 0)

    def _place_units(priorities: list[str], total: int) -> None:
        remaining = total
        for tag in priorities:
            if remaining <= 0:
                return
            available = _available_count(tag)
            if available <= 0:
                continue
            qty = min(remaining, available)
            if qty:
                place_piece(state, tag, target, qty)
                remaining -= qty

    # Friendly pieces by coalition:
    # • BRITISH/INDIANS: Village + 3 War Parties
    # • FRENCH/PATRIOTS: Fort (Patriot) + 3 Militia
    if fac in (BRITISH, INDIANS):
        placed = 0
        if pool.get(VILLAGE, 0) > 0:
            placed = place_with_caps(state, VILLAGE, target)
        if placed == 0:
            place_with_caps(state, FORT_BRI, target)
        _place_units([WARPARTY_U, TORY, REGULAR_BRI], 3)
    elif fac in (PATRIOTS, FRENCH):
        place_with_caps(state, FORT_PAT, target)
        _place_units([MILITIA_U, REGULAR_PAT, REGULAR_FRE], 3)
    else:
        push_history(state, "French Settlers Help: no executing faction; no placement")

# 75  CONGRESS’ SPEECH TO SIX NATIONS
@register(75)
def evt_075_speech_six_nations(state, shaded=False):
    """
    Unshaded – Indians free Gather in three Indian Reserve Provinces then free War Path in one of those spaces.
    Shaded   – Remove three Indian pieces from Northwest (Villages last).
    """
    reserve_spaces = _reserve_provinces(state)

    if shaded:
        if "Northwest" not in state.get("spaces", {}):
            return
        remaining = 3
        for tag in (WARPARTY_U, WARPARTY_A, VILLAGE):
            if remaining == 0:
                break
            removed = remove_piece(state, tag, "Northwest", remaining, to="available")
            remaining -= removed
        return

    from lod_ai.util.free_ops import queue_free_op

    if not reserve_spaces:
        return

    chosen = reserve_spaces[:3]
    for prov in chosen:
        queue_free_op(state, INDIANS, "gather", prov)

    queue_free_op(state, INDIANS, "war_path", chosen[0])

# 82  FRUSTRATED SHAWNEE WARRIORS ATTACK
@register(82)
def evt_082_shawnee(state, shaded=False):
    unshaded_provs = ("Virginia", "Georgia", "New_York", "South_Carolina")
    shaded_provs = ("Virginia", "Georgia", "North_Carolina", "South_Carolina")

    if shaded:
        # RULES: Indian pieces cannot go to Casualties (Manual 1.4.1).
        remaining = 3
        for p in shaded_provs:
            if remaining == 0:
                break

            removed = remove_piece(state, WARPARTY_U, p, remaining, to="available")
            remaining -= removed
            if remaining:
                removed = remove_piece(state, WARPARTY_A, p, remaining, to="available")
                remaining -= removed
            if remaining:
                removed = remove_piece(state, VILLAGE, p, remaining, to="available")
                remaining -= removed

        push_history(state, "Frustrated Shawnee Warriors Attack (shaded): removed 3 Indian pieces (Villages last)")
        return

    # Unshaded: place 1 War Party (must be Underground per 1.4.3) and 1 Raid marker in each space.
    for p in unshaded_provs:
        place_piece(state, WARPARTY_U, p, 1)
        place_marker(state, RAID, p, 1)

    push_history(state, "Frustrated Shawnee Warriors Attack (unshaded): placed War Parties + Raid markers")

# 83  GUY CARLETON & INDIANS NEGOTIATE
@register(83)
def evt_083_carleton_negotiates(state, shaded=False):
    def _fort_village_total(space: str) -> int:
        sp = state["spaces"].get(space, {})
        return sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0) + sp.get(VILLAGE, 0)

    def _space_piece_total(space: str) -> int:
        sp = state["spaces"].get(space, {})
        return sum(v for v in sp.values() if isinstance(v, int))

    def _pick_target() -> str | None:
        options = [sid for sid in ("Quebec", "Quebec_City") if sid in state.get("spaces", {})]
        if not options:
            return None
        options.sort()
        options.sort(key=_space_piece_total)
        return options[0]

    if shaded:
        executor = str(state.get("active", "")).upper()
        coalition = {
            BRITISH: (BRITISH, INDIANS),
            INDIANS: (INDIANS, BRITISH),
            PATRIOTS: (PATRIOTS, FRENCH),
            FRENCH: (FRENCH, PATRIOTS),
        }
        factions = coalition.get(executor, (executor,))

        target = _pick_target()
        if not target:
            push_history(state, "Carleton negotiates (shaded): no Quebec space found")
            return

        placed = 0

        # Optionally place one Fort/Village if none present yet
        if _fort_village_total(target) == 0:
            fort_choice = {
                BRITISH: FORT_BRI,
                INDIANS: VILLAGE,
                PATRIOTS: FORT_PAT,
                FRENCH: FORT_PAT,
            }
            for fac in factions:
                tag = fort_choice.get(fac)
                if not tag:
                    continue
                added = place_with_caps(state, tag, target)
                placed += added
                if added:
                    break

        # Fill remaining slots with units (no forts/villages)
        unit_priority = {
            BRITISH: (REGULAR_BRI, TORY),
            INDIANS: (WARPARTY_U, WARPARTY_A),
            PATRIOTS: (MILITIA_U, MILITIA_A, REGULAR_PAT),
            FRENCH: (REGULAR_FRE,),
        }

        while placed < 3:
            added_any = False
            for fac in factions:
                for tag in unit_priority.get(fac, ()): 
                    if placed >= 3:
                        break
                    added = place_piece(state, tag, target, 1)
                    if added:
                        placed += added
                        added_any = True
                        break
                if placed >= 3:
                    break
            if not added_any:
                break

        if placed == 0:
            push_history(state, f"Carleton negotiates (shaded): no pieces available for {target}")
        else:
            push_history(state, f"Carleton negotiates (shaded): placed {placed} pieces in {target}")
        return

    # Unshaded
    place_piece(state, WARPARTY_U, "Quebec", 2)
    qc = state.get("support", {}).get("Quebec_City", 0)
    delta = ACTIVE_SUPPORT - qc
    shift_support(state, "Quebec_City", delta)


# 84  SIX NATIONS AID THE WAR
@register(84)
def evt_084_six_nations(state, shaded=False):
    """
    Unshaded – Indians free Gather in two Colonies.
    Shaded   – Patriots remove one Village.
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        target = next(
            (name for name in sorted(state["spaces"]) if state["spaces"][name].get(VILLAGE, 0)),
            None,
        )
        removed = remove_piece(state, VILLAGE, target, 1, to="available") if target else 0
        push_history(
            state,
            f"Merciless Indian Savages (shaded): removed {removed} Village" + (f" in {target}" if target else ""),
        )
        return
    queue_free_op(state, INDIANS, "gather")
    queue_free_op(state, INDIANS, "gather")


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
        place_piece(state, MILITIA_U, target, 3)
    else:
        flip = sp.pop(MILITIA_U, 0)
        sp[MILITIA_A] = sp.get(MILITIA_A, 0) + flip
        push_history(state, f"Stockbridge flip {flip} Militia in {target}")


# 90  “THE WORLD TURNED UPSIDE DOWN”
@register(90)
def evt_090_world_turned_upside_down(state, shaded=False):
    """Handle card #90, “The World Turned Upside Down.”"""

    if shaded:
        # Remove 2 British Regulars anywhere to Casualties.
        remove_piece(state, REGULAR_BRI, None, 2, to="casualties")
        return

    # --- unshaded ---------------------------------------------------------
    executor = str(state.get("active", "")).upper()
    patriot_side = executor in (PATRIOTS, FRENCH)

    reserve_candidates = [name for name in _reserve_provinces(state) if _available_base_slots(state, name) > 0]
    colonies = [name for name in pick_colonies(state, len(state.get("spaces", {}))) if _available_base_slots(state, name) > 0]
    target = (reserve_candidates + colonies)[0] if (reserve_candidates or colonies) else None
    if not target:
        return

    if patriot_side:
        place_with_caps(state, FORT_PAT, target)
        return

    pool = state.setdefault("available", {})
    placed = 0
    if pool.get(VILLAGE, 0) > 0:
        placed = place_with_caps(state, VILLAGE, target)
    if placed == 0:
        place_with_caps(state, FORT_BRI, target)

# 91  INDIANS HELP BRITISH OUTSIDE COLONIES
@register(91)
def evt_091_indians_help(state, shaded=False):
    """Handle card #91, Indians Help British Outside Colonies."""

    reserve_spaces = _reserve_provinces(state)

    if shaded:
        # Shaded: Remove one Village in one Indian Reserve Province.
        target = next((n for n in reserve_spaces if state["spaces"][n].get(VILLAGE, 0)), None)
        if target:
            remove_piece(state, VILLAGE, target, 1, to="available")
            push_history(state, f"Indians Help British Outside Colonies (shaded): removed 1 Village in {target}")
        else:
            push_history(state, "Indians Help British Outside Colonies (shaded): no Reserve Province has a Village")
        return

    # Unshaded: Place one Village and two War Parties in one Indian Reserve Province.
    if not reserve_spaces:
        return

    target = reserve_spaces[0]
    place_with_caps(state, VILLAGE, target)

    # New War Parties must be placed Underground (Manual 1.4.3).
    place_piece(state, WARPARTY_U, target, 2)

    push_history(state, f"Indians Help British Outside Colonies (unshaded): placed 1 Village + 2 War Parties in {target}")


# 92  CHEROKEES SUPPLIED BY THE BRITISH
@register(92)
def evt_092_cherokees_supplied(state, shaded=False):
    """
    Unshaded – Add a second Fort/Village where you already have exactly one.
    Shaded   – No effect.
    """
    if shaded:
        return
    cities = set(pick_cities(state, len(state.get("spaces", {}))))
    pool = state.setdefault("available", {})
    for name in sorted(state.get("spaces", {})):
        if name == WEST_INDIES_ID:
            continue
        sp = state["spaces"][name]
        if sp.get(FORT_BRI, 0) + sp.get(VILLAGE, 0) == 0:
            continue
        if _available_base_slots(state, name) <= 0:
            continue
        if sp.get(VILLAGE, 0):
            place_with_caps(state, FORT_BRI, name)
            return
        if sp.get(FORT_BRI, 0):
            if name not in cities and pool.get(VILLAGE, 0) > 0:
                place_with_caps(state, VILLAGE, name)
            else:
                place_with_caps(state, FORT_BRI, name)
            return
