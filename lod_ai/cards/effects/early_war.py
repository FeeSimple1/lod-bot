from lod_ai.cards import register
from .shared import (
    add_resource, shift_support, adjust_fni, pick_cities, pick_colonies,
    pick_random_spaces, select_support_shift_spaces,
)
from lod_ai.util.free_ops import queue_free_op
from lod_ai.bots.random_spaces import pick_by_priority
from lod_ai.board.pieces import (
    move_piece,
    place_piece,
    remove_piece,
    place_marker,
    place_with_caps,
    flip_pieces,
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
from lod_ai.util.target_order import first_harm_target
from lod_ai.board.control import refresh_control
from lod_ai.map.adjacency import space_meta, space_type as _sptype
from lod_ai.util.nonplayer_pieces import (
    ROYALIST, remove_enemy_cubes, pull_to_map,
)

def _pick_spaces_with_militia(state, max_spaces=4):
    """Return up to *max_spaces* IDs that contain Patriot Militia."""
    spaces = [
        name
        for name, sp in state["spaces"].items()
        if sp.get(MILITIA_U, 0) or sp.get(MILITIA_A, 0)
    ]
    # §8.2 table (Q22, S76): equal-candidate Militia spaces, no substantive
    # key (was sorted()[:max_spaces]).
    return pick_random_spaces(state, spaces, max_spaces)

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
    cities = [n for n, info in state["spaces"].items()
              if (_sptype(n) or info.get("type")) == "City"]
    if shaded:
        # §8.3.5 → §8.3.6: highest gain in Opposition (pop-weighted, §8.1.1);
        # §8.2 random only among equal-priority Cities.
        for city in select_support_shift_spaces(state, cities, 2,
                                                target=-2, steps=1,
                                                shaded=True):
            shift_support(state, city, -1)
            place_marker(state, PROPAGANDA, city, 2)
    else:
        # Placement counts are equal in every City → equal priority → §8.2.
        picked = pick_random_spaces(state, cities, 1)
        if not picked:
            return
        city = picked[0]
        place_piece(state, REGULAR_BRI, city, 2)
        place_piece(state, TORY,   city, 2)
        place_marker(state, PROPAGANDA, city, 2)
        add_resource(state, BRITISH, +4)

# 4  THE PENOBSCOT EXPEDITION
@register(4)                       # Penobscot Expedition
def evt_004_penobscot(state, shaded=False):
    """
    Unshaded – Expedition fails: Patriot Resources -2; remove 3 Patriot Militia.
    Shaded   – Expedition succeeds: place 1 Fort or Village and 3 Militia or
               War Parties in Massachusetts.  Player chooses piece type freely.
    """
    if shaded:
        target = "Massachusetts"
        # "Fort or Village" — player chooses freely via state override
        base_choice = state.get("card4_base", "").upper()
        if base_choice == "VILLAGE":
            place_with_caps(state, VILLAGE, target)
        elif base_choice == "FORT_BRI":
            place_with_caps(state, FORT_BRI, target)
        elif base_choice == "FORT_PAT":
            place_with_caps(state, FORT_PAT, target)
        else:
            # Default: faction-aligned base
            executor = str(state.get("active", "")).upper()
            if executor in (BRITISH, INDIANS):
                placed = place_with_caps(state, VILLAGE, target)
                if placed == 0:
                    place_with_caps(state, FORT_BRI, target)
            else:
                place_with_caps(state, FORT_PAT, target)

        # "Militia or War Parties" — player chooses freely via state override
        unit_choice = state.get("card4_units", "").upper()
        if unit_choice == "WARPARTY":
            place_piece(state, WARPARTY_U, target, 3)
        elif unit_choice == "MILITIA":
            place_piece(state, MILITIA_U, target, 3)
        else:
            # Default: faction-aligned units
            executor = str(state.get("active", "")).upper()
            if executor in (BRITISH, INDIANS):
                place_piece(state, WARPARTY_U, target, 3)
            else:
                place_piece(state, MILITIA_U, target, 3)
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
    spaces = state["spaces"]

    def _pick_removal_space(fort_tag, other_tags, colony_only):
        """§8.3.5: maximise Forts removed, then other pieces; §8.2 ties."""
        def key(sid):
            sp = spaces[sid]
            return (min(1, sp.get(fort_tag, 0)),
                    min(2, sum(sp.get(t, 0) for t in other_tags)))
        cands = [sid for sid in spaces
                 if (not colony_only
                     or (_sptype(sid) or spaces[sid].get("type")) == "Colony")
                 and key(sid) > (0, 0)]
        if not cands:
            return None
        best = max(key(s) for s in cands)
        ties = [s for s in cands if key(s) == best]
        return ties[0] if len(ties) == 1 else pick_random_spaces(state, ties, 1)[0]

    if shaded:
        target = _pick_removal_space(FORT_BRI, (REGULAR_BRI, TORY),
                                     colony_only=False)
        if not target:
            return
        remove_piece(state, FORT_BRI, target, 1, to="casualties")
        # §8.1.2 ENEMY bullet (via §8.3.5): British pieces are enemy to the
        # Rebellion executor — alternate cubes beginning with whichever is
        # FEWEST (Regulars if even); the last-Tory protection applies only
        # to friendly removal. (Corrects Session 23, which used the
        # friendly-removal order here.)
        remove_enemy_cubes(state, target, 2, ROYALIST, to="casualties")
        return

    target = _pick_removal_space(FORT_PAT, (MILITIA_A, MILITIA_U),
                                 colony_only=True)
    if not target:
        return
    remove_piece(state, FORT_PAT,     target, 1, to="casualties")
    # §8.1.2 ENEMY bullet: "target enemy Underground Militia or War Parties
    # before Active ones" — Patriot Militia are enemy to the British
    # executor. (Corrects Session 21, which applied the FRIENDLY-removal
    # order, Active-first, to an enemy removal.)
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
        cities = [n for n, info in state["spaces"].items()
                  if (_sptype(n) or info.get("type")) == "City"]
        # §8.3.5 → §8.3.6: highest gain in Support (pop-weighted); §8.2 ties.
        for city in select_support_shift_spaces(state, cities, 2,
                                                target=+2, steps=1,
                                                shaded=False):
            shift_support(state, city, +1)

# 13  "…THE ORIGIN OF ALL OUR MISFORTUNES"
@register(13)
def evt_013_origin_misfortunes(state, shaded=False):
    """
    Unshaded – Execute Patriot Desertion as per Winter Quarters Round (§6.6.1).
    Shaded   – In up to 4 spaces with Militia, Patriots add 1 Active Militia.
    """
    if shaded:
        for space in _pick_spaces_with_militia(state, max_spaces=4):
            place_piece(state, MILITIA_A, space, 1)
    else:
        from lod_ai.util.year_end import _patriot_desertion
        _patriot_desertion(state)
        push_history(state, "Card 13 unshaded: Patriot Desertion executed immediately")

# 15  MORGAN’S RIFLES
@register(15)
def evt_015_morgans_rifles(state, shaded=False):
    """
    Unshaded – Shift Virginia two levels toward Active Support. Place two Tories there.
    Shaded   – Patriots free March to any one Colony, then free Battle, then Partisans there.
    """
    if shaded:
        colony = state.get("card15_colony", "Virginia")
        if colony not in state.get("spaces", {}):
            colony = "Virginia"
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
        # "Place up to three Militia anywhere, one Propaganda with each.
        #  Place one Fort anywhere."
        # Cities then highest Pop, §8.2 seeded ties (Session 48/T9: ties
        # fell to dict order); West Indies excluded (§1.4.2).
        rng = state.get("rng")
        scored = [
            ((-(1 if (space_meta(sid) or {}).get("type") == "City" else 0),
              -((space_meta(sid) or {}).get("population", 0))), sid)
            for sid in state["spaces"] if sid != WEST_INDIES_ID
        ]
        candidates = pick_by_priority(state, scored)  # Q22 (full order)
        targets = candidates[:3]
        for sid in targets:
            place_piece(state, MILITIA_U, sid, 1)
            place_marker(state, PROPAGANDA, sid, 1)
        # "Place one Fort anywhere" — an independent space choice: the
        # first selected space WITH base room (§1.4.2), else any
        # (Session 48/T9: a full targets[0] silently lost the Fort).
        for sid in targets + [s for s in candidates if s not in targets]:
            sp = state["spaces"].get(sid, {})
            if (sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0)
                    + sp.get(VILLAGE, 0)) < 2:
                place_with_caps(state, FORT_PAT, sid)
                break
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
    _rng28 = state.get("rng")
    if shaded:
        # Most Tories for maximum replacement (§8.1.1); §8.2 seeded ties
        # (Session 48/T9: ties fell to dict order).
        target_list = pick_by_priority(  # Q22
            state,
            [((-targets[sid].get(TORY, 0),), sid)
             for sid in (preferred or list(targets.keys()))],
        )
    else:
        # Most Militia for maximum replacement (§8.1.1); §8.2 seeded ties.
        target_list = pick_by_priority(  # Q22
            state,
            [((-(targets[sid].get(MILITIA_U, 0) + targets[sid].get(MILITIA_A, 0)),), sid)
             for sid in (preferred or list(targets.keys()))],
        )
    target = target_list[0]
    sp = state["spaces"].get(target, {})

    if shaded:
        # Replace every Tory with twice as many Underground Militia
        tories = sp.get(TORY, 0)
        if tories:
            remove_piece(state, TORY, target, tories, to="available")
            place_piece(state, MILITIA_U, target, 2 * tories)
    else:
        # Replace every Militia (U and A) with twice as many Tories
        mu = sp.get(MILITIA_U, 0)
        ma = sp.get(MILITIA_A, 0)
        total = mu + ma
        if total:
            if mu:
                remove_piece(state, MILITIA_U, target, mu, to="available")
            if ma:
                remove_piece(state, MILITIA_A, target, ma, to="available")
            place_piece(state, TORY, target, 2 * total)

# 29  EDWARD BANCROFT, BRITISH SPY
@register(29)
def evt_029_bancroft(state, shaded=False):
    """
    Unshaded – Patriots OR Indians must Activate their Militia or
    War Parties until 1/2 of them are Active (rounded down).
    Card says "or" — choose ONE faction (not both).
    Bot: British/Indian bot targets Patriots; Patriot/French bot targets Indians.
    """
    if shaded:
        return

    # "Patriots or Indians" — choose ONE faction
    target_fac = state.get("card29_target", "").upper()
    if target_fac not in (PATRIOTS, INDIANS):
        # §8.3.5 harm choice (Activating pieces), restricted to the two
        # named candidates (T7).  For every executor exactly one of
        # {PATRIOTS, INDIANS} is an enemy, so this reproduces the prior
        # default (British/Indian -> Patriots, Patriot/French -> Indians)
        # with the rule as the citation rather than a hardcoded table.
        active = str(state.get("active", "")).upper()
        target_fac = first_harm_target(state, active,
                                       candidates=(PATRIOTS, INDIANS),
                                       default=INDIANS)

    if target_fac == PATRIOTS:
        hidden_tag, active_tag, label = MILITIA_U, MILITIA_A, "Militia"
    else:
        hidden_tag, active_tag, label = WARPARTY_U, WARPARTY_A, "War Parties"

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
    # The TARGET Faction picks which of its pieces Activate (§5.1); no
    # sheet priority exists, so §8.2/§8.3.8 seeded-random space order
    # (Session 47: was dict order).
    # Q22: §8.2 random order over all spaces via the Random Spaces table.
    order = pick_random_spaces(state, list(state["spaces"]),
                               count=len(state["spaces"]))
    for name in order:
        if flipped >= need:
            break
        here = state["spaces"][name].get(hidden_tag, 0)
        if here:
            take = min(here, need - flipped)
            flipped += flip_pieces(state, hidden_tag, active_tag, name, take)
    push_history(state, f"Bancroft activates {flipped} {label} (to {target_active} Active)")

# 30  HESSIANS
@register(30)
def evt_030_hessians(state, shaded=False):
    """Hessians deployment or settlement."""
    if shaded:
        total = sum(sp.get(REGULAR_BRI, 0) for sp in state["spaces"].values())
        remove_qty = total // 5
        if remove_qty:
            # The British choose which Regulars settle.  Sheet B30: "If
            # the shaded text is played by an enemy Faction, leave 1
            # Regular per space if possible."  Largest stacks first,
            # §8.2 seeded ties (Session 47: dict-order removal emptied
            # the first spaces entirely).
            stacks = [(n, sp.get(REGULAR_BRI, 0))
                      for n, sp in state["spaces"].items()
                      if sp.get(REGULAR_BRI, 0)]
            # Q22: most Regulars first; equal-count ties via Random Spaces.
            _qmap = dict(stacks)
            stacks = [(n, _qmap[n]) for n in
                      pick_by_priority(state, [((-q,), n) for n, q in stacks])]
            remaining = remove_qty
            for name, qty in stacks:
                if remaining <= 0:
                    break
                take = min(qty - 1, remaining)      # spare 1 per space
                if take > 0:
                    remove_piece(state, REGULAR_BRI, name, take, to="available")
                    remaining -= take
            if remaining > 0:                       # forced past the spare
                for name, _q in stacks:
                    if remaining <= 0:
                        break
                    have = state["spaces"][name].get(REGULAR_BRI, 0)
                    take = min(have, remaining)
                    if take:
                        remove_piece(state, REGULAR_BRI, name, take, to="available")
                        remaining -= take
    else:
        refresh_control(state)
        eligible = [n for n, sp in state["spaces"].items()
                    if sp.get(REGULAR_BRI) and state.get("control", {}).get(n) == BRITISH]
        # No sheet priority for the unshaded spaces → §8.2 seeded pick
        # (Session 47: was the first three in dict order), and §8.1.2:
        # move from Unavailable first ("from Available or Unavailable").
        picked = pick_random_spaces(state, eligible, min(3, len(eligible)))
        for loc in picked:
            pull_to_map(state, REGULAR_BRI, loc, 2)
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
    # ---- helper: reference says "from Unavailable or Available" — Unavailable first
    def _pull_from_pools(tag, qty):
        # §8.1.2 / §8.3.4 via shared helper: Unavailable first.
        pull_to_map(state, tag, target, qty)

    if shaded:
        cities = pick_cities(state, len(state.get("spaces", {})))
        refresh_control(state)
        british_cities = [city for city in cities if state.get("control", {}).get(city) == BRITISH]
        recipient = str(state.get("active", BRITISH)).upper()
        add_resource(state, recipient, len(british_cities) // 2)
        return

    # ---- unshaded: place pieces in one Colony ------------------------------
    colony_choices = state.get("rule_britannia_colony")
    if colony_choices:
        target = str(colony_choices)
    else:
        # Any Colony takes the pieces equally → equal priority → §8.2.
        colonies = [n for n, info in state["spaces"].items()
                    if (_sptype(n) or info.get("type")) == "Colony"]
        picked = pick_random_spaces(state, colonies, 1)
        if not picked:
            return
        target = picked[0]
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
        # "Free Rally in two spaces adjacent to Massachusetts."
        from lod_ai.map import adjacency as map_adj
        meta = map_adj.space_meta("Massachusetts") or {}
        adj_spaces = []
        for token in meta.get("adj", []):
            adj_spaces.extend(token.split("|"))
        adj_valid = [sid for sid in adj_spaces if sid in state.get("spaces", {})]
        # Equal priority among qualifying adjacents → §8.2 seeded pick
        # (Session 48/T9: was the first two in adjacency-list order).
        chosen = pick_random_spaces(state, adj_valid, min(2, len(adj_valid)))
        for prov in chosen:
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
    target_space = state.get("card35_target", "New_York")
    if target_space not in ("New_York", "New_York_City"):
        target_space = "New_York"

    if shaded:
        # "Remove all Tories in New York or in one adjacent space."
        shaded_target = state.get("card35_shaded_target", target_space)
        if shaded_target not in state.get("spaces", {}):
            shaded_target = target_space
        remove_piece(state, TORY, shaded_target, 999, to="available")
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
        mu = state["spaces"][target_space].get(MILITIA_U, 0)
        if mu:
            flip_pieces(state, MILITIA_U, MILITIA_A, target_space, mu)

# 41  WILLIAM PITT – AMERICA CAN’T BE CONQUERED
@register(41)
def evt_041_william_pitt(state, shaded=False):
    """
    Unshaded – Shift 2 Colonies 2 levels each toward Passive Support.
    Shaded   – Shift 2 Colonies 2 levels each toward Passive Opposition.
    """
    target = +1 if not shaded else -1
    colonies = [n for n, info in state["spaces"].items()
                if (_sptype(n) or info.get("type")) == "Colony"]
    # §8.3.5 → §8.3.6 (pop-weighted gain; §8.2 ties). Note a Colony past the
    # target level would shift AGAINST the executing side; §8.3.6 ordering
    # ranks it below zero-gain candidates.
    for col in select_support_shift_spaces(state, colonies, 2,
                                           target=target, steps=2,
                                           shaded=shaded):
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
        # Equal placement in every qualifying space → §8.2 for the selection;
        # §8.3.4: place from Unavailable first, then Available.
        for loc in pick_random_spaces(state, eligible, 3):
            pull_to_map(state, TORY, loc, 2)


# 46  EDMUND BURKE ON CONCILIATION
@register(46)
def evt_046_burke(state, shaded=False):
    """
    Unshaded – Place 1 Tory in each of 3 spaces.
    Shaded   – Shift 2 Cities 1 level toward Passive Opposition.
    """
    if shaded:
        cities = [n for n, info in state["spaces"].items()
                  if (_sptype(n) or info.get("type")) == "City"]
        # §8.3.5 → §8.3.6 (pop-weighted gain; §8.2 ties).
        for city in select_support_shift_spaces(state, cities, 2,
                                                target=-1, steps=1,
                                                shaded=True):
            _shift_support_toward(state, city, -1, steps=1)
    else:
        candidates = [sid for sid in state.get("spaces", {})
                      if sid != WEST_INDIES_ID]
        # One Tory in each of three spaces — equal priority → §8.2.
        for space in pick_random_spaces(state, candidates, 3):
            # "from Unavailable or Available" — Unavailable first (§8.1.2).
            pull_to_map(state, TORY, space, 1)


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
    Unshaded – Place 1 friendly Fort/Village and 3 friendly Militia/War
               Parties or cubes in any one Indian Reserve Province.
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
    # "any one Indian Reserve Province" — prefer one with room for the
    # Fort/Village (§1.4.2 — the I72 play condition requires a
    # placeable Village), §8.2 seeded ties (Session 48/T9: was the
    # first Reserve in dict order).
    _rng72 = state.get("rng")
    _roy72 = fac in (BRITISH, INDIANS)
    def _k72(sid):
        room = 0 if (state["spaces"][sid].get(FORT_BRI, 0)
                     + state["spaces"][sid].get(FORT_PAT, 0)
                     + state["spaces"][sid].get(VILLAGE, 0)) < 2 else 1
        # §8.7 I2 note: prefer a space that already has War Parties.
        wp = -(state["spaces"][sid].get(WARPARTY_U, 0)
               + state["spaces"][sid].get(WARPARTY_A, 0)) if _roy72 else 0
        return (room, wp)
    reserve_candidates = pick_by_priority(  # Q22
        state, [(_k72(sid), sid) for sid in reserve_candidates])
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

    # Three of the four Reserves — equal priority → §8.2 seeded
    # (Session 48/T9: was the first three in dict order).
    chosen = pick_random_spaces(state, reserve_spaces, min(3, len(reserve_spaces)))
    for prov in chosen:
        queue_free_op(state, INDIANS, "gather", prov)

    # "free War Path in ONE of those spaces" — it strikes Rebellion
    # pieces (§4.4.2), so prefer a chosen Reserve holding any; §8.2 ties.
    _rng75 = state.get("rng")
    def _k75(sid):
        has = any(state["spaces"].get(sid, {}).get(t, 0)
                  for t in (MILITIA_A, MILITIA_U, REGULAR_PAT,
                            REGULAR_FRE, FORT_PAT))
        return (0 if has else 1,)
    wp_cands = pick_by_priority(  # Q22
        state, [(_k75(sid), sid) for sid in chosen])
    if wp_cands:
        queue_free_op(state, INDIANS, "war_path", wp_cands[0])

# 82  FRUSTRATED SHAWNEE WARRIORS ATTACK
@register(82)
def evt_082_shawnee(state, shaded=False):
    unshaded_provs = ("Virginia", "Georgia", "North_Carolina", "South_Carolina")
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

    def _control_of(space: str, extra_rebels: int = 0) -> str | None:
        """§1.7 tally as in board.control, with optional added Rebellion
        pieces (for the P83 'change Control there' test)."""
        sp = state["spaces"].get(space, {})
        rebels = sum(q for t, q in sp.items()
                     if isinstance(q, int) and isinstance(t, str)
                     and t.startswith(("Patriot_", "French_"))) + extra_rebels
        bri = sum(q for t, q in sp.items()
                  if isinstance(q, int) and isinstance(t, str)
                  and t.startswith("British_"))
        ind = sum(q for t, q in sp.items()
                  if isinstance(q, int) and isinstance(t, str)
                  and t.startswith("Indian_"))
        royal = bri + ind
        if rebels > royal:
            return "REBELLION"
        if royal > rebels and bri > 0:
            return "BRITISH"
        return None

    def _pick_target() -> str | None:
        options = [sid for sid in ("Quebec", "Quebec_City") if sid in state.get("spaces", {})]
        if not options:
            return None
        # Sheet F83: "Select Quebec City" — french.py presets
        # card83_target (Session 47: the preset was never read and a
        # min-piece scan could pick Quebec, the T14/Session-41 note).
        override = state.get("card83_target")
        if override in options:
            return override
        executor = str(state.get("active", "")).upper()
        if executor == PATRIOTS:
            # Sheet P83: "Play in Quebec City if possible to change
            # Control there, otherwise in Quebec."
            if ("Quebec_City" in options
                    and _control_of("Quebec_City", 3) != _control_of("Quebec_City")):
                return "Quebec_City"
            if "Quebec" in options:
                return "Quebec"
            return options[0]
        # No sheet guidance (British/Indian/human): fewest pieces,
        # §8.2 seeded ties.
        # Q22: fewest pieces; equal-count ties via the Random Spaces table.
        ordered = pick_by_priority(
            state, [((_space_piece_total(s),), s) for s in options])
        return ordered[0]

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

        # Card: at most ONE of the up-to-3 pieces may be a Fort/Village;
        # §1.4.2 allows it while the space holds < 2 bases (Session 47:
        # the old guard required an empty-base space).
        if _fort_village_total(target) < 2:
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
    Unshaded – Indians free Gather in two Colonies (Colony restriction).
    Shaded   – Patriots remove one Village.
    """
    from lod_ai.util.free_ops import queue_free_op
    if shaded:
        village_spaces = [name for name in state["spaces"]
                          if state["spaces"][name].get(VILLAGE, 0)]
        # One Village from any qualifying space → equal priority → §8.2.
        picked = pick_random_spaces(state, village_spaces, 1)
        target = picked[0] if picked else None
        removed = remove_piece(state, VILLAGE, target, 1, to="available") if target else 0
        push_history(
            state,
            f"Merciless Indian Savages (shaded): removed {removed} Village" + (f" in {target}" if target else ""),
        )
        return

    # "in two Colonies" — player/bot selects which Colonies
    override = state.get("card84_colonies")
    if isinstance(override, list) and len(override) >= 2:
        colonies = override[:2]
    else:
        # §8.3.5: choices inside a card-granted free Command use the
        # Faction's own priorities — Indian Gather legality (3.4.1: Support
        # among Neutral/Passive, War Party in or adjacent, never the West
        # Indies; mirrors the engine free-op planner) with the most-own-
        # force priority, restricted to Colonies per the card; §8.2 ties.
        from lod_ai.commands.gather import SUPPORT_OK
        from lod_ai.map import adjacency as _madj
        spaces = state["spaces"]

        def _wp(sid):
            sp = spaces.get(sid, {})
            return sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)

        def _legal(sid):
            if (_sptype(sid) or spaces.get(sid, {}).get("type")) != "Colony":
                return False
            if sid == WEST_INDIES_ID:
                return False
            if state.get("support", {}).get(sid, 0) not in SUPPORT_OK:
                return False
            if _wp(sid) > 0:
                return True
            return any(_wp(nbr) for nbr in _madj.adjacent_spaces(sid))

        cands = [sid for sid in spaces if _legal(sid)]
        colonies = []
        while cands and len(colonies) < 2:
            best = max(_wp(s) for s in cands)
            ties = [s for s in cands if _wp(s) == best]
            pick = (ties[0] if len(ties) == 1
                    else pick_random_spaces(state, ties, 1)[0])
            colonies.append(pick)
            cands.remove(pick)
    for col in colonies:
        queue_free_op(state, INDIANS, "gather", col)


# 86  STOCKBRIDGE INDIANS
@register(86)
def evt_086_stockbridge(state, shaded=False):
    """
    Unshaded – Activate all Militia in Massachusetts *or* a space with
               an Indian piece (we choose Massachusetts).
    Shaded   – Add 3 Militia in the same space.
    """
    # Card: "in Massachusetts or in any one space with an Indian piece".
    # Sheets I86/P86: "Select a Village space if possible" (a Village is
    # an Indian piece); §8.2 seeded ties (Session 47: was hardwired to
    # Massachusetts).  Unshaded needs Underground Militia present to
    # have any effect (§5.1.3).
    rng = state.get("rng")

    def _pick(require_militia: bool) -> str:
        cands = []
        for sid, sp in state["spaces"].items():
            if not sp.get(VILLAGE, 0):
                continue
            if require_militia and not sp.get(MILITIA_U, 0):
                continue
            cands.append(sid)
        if cands:
            # Q22: §8.2 random space via the Random Spaces table.
            return pick_random_spaces(state, cands, 1)[0]
        return "Massachusetts"

    if shaded:
        target = _pick(require_militia=False)
        place_piece(state, MILITIA_U, target, 3)
        push_history(state, f"Card 86 shaded: 3 Militia in {target}")
    else:
        target = _pick(require_militia=True)
        mu = state["spaces"].get(target, {}).get(MILITIA_U, 0)
        if mu:
            flip_pieces(state, MILITIA_U, MILITIA_A, target, mu)
            push_history(state, f"Card 86 unshaded: activated {mu} Militia in {target}")


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

    # "Place one friendly Fort or Village" — space choice follows the
    # piece (Session 48/T9: was Reserve-first dict order even for
    # Patriot Forts): a Village goes to a Reserve/Colony (most friendly
    # War Parties first); a Fort to a Colony/City-side space with own
    # pieces first.  §8.2 seeded ties; room per §1.4.2 throughout.
    rng = state.get("rng")
    reserve_candidates = [name for name in _reserve_provinces(state)
                          if _available_base_slots(state, name) > 0]
    colonies = [name for name in pick_colonies(state, len(state.get("spaces", {})))
                if _available_base_slots(state, name) > 0]

    def _fort_target(own_prefixes):
        cands = []
        for name in colonies + reserve_candidates:
            own = sum(q for t, q in state["spaces"].get(name, {}).items()
                      if isinstance(t, str) and isinstance(q, int) and q > 0
                      and t.startswith(own_prefixes))
            is_colony = 1 if name in colonies else 0
            cands.append(((-is_colony, -own), name))
        picked = pick_by_priority(state, cands, count=1)  # Q22
        return picked[0] if picked else None

    pool = state.setdefault("available", {})
    if patriot_side:
        target = _fort_target(("Patriot_", "French_"))
        if target:
            place_with_caps(state, FORT_PAT, target)
        return

    if pool.get(VILLAGE, 0) > 0:
        v_cands = []
        for name in reserve_candidates + colonies:
            wps = (state["spaces"].get(name, {}).get(WARPARTY_U, 0)
                   + state["spaces"].get(name, {}).get(WARPARTY_A, 0))
            is_reserve = 1 if name in reserve_candidates else 0
            v_cands.append(((-is_reserve, -wps), name))
        v_ordered = pick_by_priority(state, v_cands, count=1)  # Q22
        if v_ordered and place_with_caps(state, VILLAGE, v_ordered[0]):
            return
    target = _fort_target(("British_", "Indian_"))
    if target:
        place_with_caps(state, FORT_BRI, target)

# 91  INDIANS HELP BRITISH OUTSIDE COLONIES
@register(91)
def evt_091_indians_help(state, shaded=False):
    """Handle card #91, Indians Help British Outside Colonies."""

    reserve_spaces = _reserve_provinces(state)

    if shaded:
        # Shaded: Remove one Village in one Indian Reserve Province.
        # Equal-priority Villages → §8.2 seeded (Session 48/T9: was the
        # first Reserve in dict order).
        # Q22: equal-priority Villages resolved via the Random Spaces table.
        with_village = pick_random_spaces(
            state,
            [n for n in reserve_spaces if state["spaces"][n].get(VILLAGE, 0)],
            count=len(reserve_spaces) or 1,
        )
        target = with_village[0] if with_village else None
        if target:
            remove_piece(state, VILLAGE, target, 1, to="available")
            push_history(state, f"Indians Help British Outside Colonies (shaded): removed 1 Village in {target}")
        else:
            push_history(state, "Indians Help British Outside Colonies (shaded): no Reserve Province has a Village")
        return

    # Unshaded: Place one Village and two War Parties in one Indian Reserve Province.
    if not reserve_spaces:
        return

    # Room for the Village first (§1.4.2), most War Parties next (the
    # new Village lands with protection), §8.2 seeded ties (Session
    # 48/T9: was the first Reserve in dict order).
    def _k91u(n):
        room = 0 if (state["spaces"][n].get(FORT_BRI, 0)
                     + state["spaces"][n].get(FORT_PAT, 0)
                     + state["spaces"][n].get(VILLAGE, 0)) < 2 else 1
        wp = -(state["spaces"][n].get(WARPARTY_U, 0)
               + state["spaces"][n].get(WARPARTY_A, 0))
        return (room, wp)
    ordered = pick_by_priority(  # Q22
        state, [(_k91u(n), n) for n in reserve_spaces])
    target = ordered[0]
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
    cands = [
        name for name, sp in state.get("spaces", {}).items()
        if name != WEST_INDIES_ID
        and sp.get(FORT_BRI, 0) + sp.get(VILLAGE, 0) > 0
        and _available_base_slots(state, name) > 0
    ]
    # §8.2 table (Q22, S76): equal-candidate Fort/Village spaces with an
    # open base slot, no substantive key (was first sorted()).
    picked = pick_random_spaces(state, cands, 1)
    if not picked:
        return
    name = picked[0]
    sp = state["spaces"][name]
    if sp.get(VILLAGE, 0):
        place_with_caps(state, FORT_BRI, name)
        return
    if sp.get(FORT_BRI, 0):
        if name not in cities and pool.get(VILLAGE, 0) > 0:
            place_with_caps(state, VILLAGE, name)
        else:
            place_with_caps(state, FORT_BRI, name)
        return
