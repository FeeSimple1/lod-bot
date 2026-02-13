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
from lod_ai.rules_consts import (
    WEST_INDIES_ID,
    VILLAGE,
    WARPARTY_A, WARPARTY_U,
    MILITIA_A, MILITIA_U,
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY,
    FORT_BRI, FORT_PAT,
    PROPAGANDA,
    RAID,
    BRITISH, PATRIOTS, FRENCH, INDIANS,
)
from lod_ai.map import adjacency as map_adj
from lod_ai.board import control


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get_space(state, sid):
    return state.get("spaces", {}).get(sid, {})


def _pick_first_existing(state, candidates):
    for sid in candidates:
        if sid in state.get("spaces", {}):
            return sid
    return None


def _neighbors(space_id):
    meta = map_adj.space_meta(space_id) or {}
    neighbors = set()
    for token in meta.get("adj", []):
        neighbors.update(token.split("|"))
    return sorted(neighbors)


def _is_city(space_id):
    return map_adj.space_type(space_id) == "City"


def _is_colony(space_id):
    return map_adj.space_type(space_id) == "Colony"


def _is_reserve(space_id):
    return map_adj.space_type(space_id) == "Reserve"


def _ensure_control(state):
    control.refresh_control(state)


def _faction_piece_tags(faction):
    if faction == BRITISH:
        return [REGULAR_BRI, TORY, FORT_BRI]
    if faction == PATRIOTS:
        return [REGULAR_PAT, MILITIA_U, MILITIA_A, FORT_PAT]
    if faction == FRENCH:
        return [REGULAR_FRE]
    if faction == INDIANS:
        return [WARPARTY_U, WARPARTY_A, VILLAGE]
    return []


def _faction_unit_tags(faction):
    if faction == BRITISH:
        return [REGULAR_BRI, TORY]
    if faction == PATRIOTS:
        return [REGULAR_PAT, MILITIA_U, MILITIA_A]
    if faction == FRENCH:
        return [REGULAR_FRE]
    if faction == INDIANS:
        return [WARPARTY_U, WARPARTY_A]
    return []


def _space_has_any(state, sid, tags):
    sp = _safe_get_space(state, sid)
    return any(sp.get(tag, 0) > 0 for tag in tags)


def _remove_from_tags(state, sid, tags, qty, *, to="available"):
    removed = 0
    for tag in tags:
        if removed >= qty:
            break
        count = _safe_get_space(state, sid).get(tag, 0)
        if count:
            n = min(count, qty - removed)
            removed += remove_piece(state, tag, sid, n, to=to)
    return removed


def _place_from_pools(state, tag, space_id, qty):
    moved = move_piece(state, tag, "unavailable", space_id, qty)
    if moved < qty:
        move_piece(state, tag, "available", space_id, qty - moved)


# 3  GEORGE ROGERS CLARK’S ILLINOIS CAMPAIGN
@register(3)
def evt_003_illinois_campaign(state, shaded=False):
    """
    Unshaded – Remove all Patriot pieces in Northwest and Southwest.
    Shaded   – Patriots place 2 Militia **and free Partisans**
               in *both* Northwest and Southwest.
    """
    from lod_ai.special_activities import partisans

    for prov in ("Northwest", "Southwest"):
        if prov not in state.get("spaces", {}):
            continue
        if shaded:
            place_piece(state, MILITIA_U, prov, 2)
            sp = _safe_get_space(state, prov)
            if sp.get(MILITIA_U, 0) and _space_has_any(
                state,
                prov,
                [REGULAR_BRI, TORY, WARPARTY_A, WARPARTY_U, VILLAGE, FORT_BRI],
            ):
                partisans.execute(state, PATRIOTS, ctx={}, space_id=prov, option=1)
        else:
            for tag in (MILITIA_A, MILITIA_U, REGULAR_PAT, FORT_PAT):
                remove_piece(state, tag, prov, 99, to="available")
    push_history(state, f"Card 3 {'shaded' if shaded else 'unshaded'} resolved")


# 5  WILLIAM ALEXANDER, LORD STIRLING
@register(5)
def evt_005_lord_stirling(state, shaded=False):
    """
    Unshaded – Patriots Ineligible through next card.
    Shaded   – Patriots free March + Battle in one space.
    """
    from lod_ai.commands import march, battle

    if not shaded:
        state.setdefault("ineligible_through_next", set()).add(PATRIOTS)
        push_history(state, "Card 5 unshaded: Patriots ineligible through next")
        return

    dest_override = state.get("card5_dest")
    src_override = state.get("card5_src")

    def _pick_move():
        if dest_override in state.get("spaces", {}):
            dests = [dest_override]
        else:
            dests = list(state.get("spaces", {}).keys())
        for dest in dests:
            neighbors = _neighbors(dest)
            if src_override:
                if src_override in neighbors and src_override in state.get("spaces", {}):
                    sp_src = _safe_get_space(state, src_override)
                    if _space_has_any(state, src_override, _faction_unit_tags(PATRIOTS)):
                        return src_override, dest
            for src in neighbors:
                if src not in state.get("spaces", {}):
                    continue
                if _space_has_any(state, src, _faction_unit_tags(PATRIOTS)):
                    return src, dest
        return None, None

    src, dest = _pick_move()
    if not src or not dest:
        push_history(state, "Card 5 shaded: no legal Patriot March/Battle")
        return

    sp_src = _safe_get_space(state, src)
    piece_tag = None
    for tag in (REGULAR_PAT, MILITIA_U, MILITIA_A):
        if sp_src.get(tag, 0):
            piece_tag = tag
            break
    if not piece_tag:
        push_history(state, "Card 5 shaded: no Patriot units to March")
        return

    move_plan = [{"src": src, "dst": dest, "pieces": {piece_tag: 1}}]
    march.execute(
        state,
        PATRIOTS,
        ctx={},
        sources=[src],
        destinations=[dest],
        move_plan=move_plan,
        free=True,
    )
    battle.execute(state, PATRIOTS, ctx={}, spaces=[dest], free=True)
    push_history(state, f"Card 5 shaded: Patriot March/Battle in {dest}")


# 8  CULPEPER SPY RING
@register(8)
def evt_008_culpeper_ring(state, shaded=False):
    """Handle Culpeper Spy Ring event."""
    if shaded:
        removed = remove_piece(state, REGULAR_BRI, None, 3, to="casualties")
        if removed < 3:
            remove_piece(state, TORY, None, 3 - removed, to="casualties")
        push_history(state, "Card 8 shaded: removed British cubes")
    else:
        flipped = 0
        for name, sp in state.get("spaces", {}).items():
            if flipped == 3:
                break
            if sp.get(MILITIA_U, 0):
                sp[MILITIA_U] -= 1
                sp[MILITIA_A] = sp.get(MILITIA_A, 0) + 1
                push_history(state, f"Card 8 unshaded: activated Militia in {name}")
                flipped += 1


# 9  FRIEDRICH WILHELM VON STEUBEN
@register(9)
def evt_009_von_steuben(state, shaded=False):
    """
    Unshaded – British may Skirmish in up to 3 spaces.
    Shaded   – Patriots may Skirmish in up to 3 spaces.
    """
    from lod_ai.special_activities import skirmish

    actor = PATRIOTS if shaded else BRITISH
    override_spaces = state.get("card9_spaces")

    def _can_skirmish(space_id):
        sp = _safe_get_space(state, space_id)
        if actor == BRITISH:
            if sp.get(REGULAR_BRI, 0) == 0:
                return False
            enemy = sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
            enemy += sp.get(MILITIA_A, 0)
            return enemy > 0
        if actor == PATRIOTS:
            if sp.get(REGULAR_PAT, 0) == 0:
                return False
            enemy = sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)
            return enemy > 0
        return False

    if isinstance(override_spaces, list):
        candidates = [sid for sid in override_spaces if sid in state.get("spaces", {})]
    else:
        candidates = [sid for sid in state.get("spaces", {}) if _can_skirmish(sid)]

    chosen = []
    for sid in candidates:
        if len(chosen) == 3:
            break
        if _can_skirmish(sid):
            chosen.append(sid)

    for sid in chosen:
        if _can_skirmish(sid):
            skirmish.execute(state, actor, ctx={}, space_id=sid, option=1)

    push_history(state, f"Card 9 {'shaded' if shaded else 'unshaded'}: skirmish in {len(chosen)} spaces")


# 11  KOSCIUSZKO
@register(11)
def evt_011_kosciuszko(state, shaded=False):
    """Implement Kosciuszko event."""
    if not shaded:
        removed = remove_piece(state, FORT_PAT, None, 2, to="available")
        push_history(state, f"Card 11 unshaded: removed {removed} Patriot Forts")
        return

    _ensure_control(state)
    candidates = []
    override = state.get("card11_spaces")
    if isinstance(override, list):
        candidates = [sid for sid in override if sid in state.get("spaces", {})]
    else:
        for sid, sp in state.get("spaces", {}).items():
            if state.get("control", {}).get(sid) != "REBELLION":
                continue
            if _space_has_any(state, sid, _faction_piece_tags(PATRIOTS)):
                candidates.append(sid)

    done = 0
    for sid in candidates:
        if done == 2:
            break
        sp = _safe_get_space(state, sid)
        if not _space_has_any(state, sid, _faction_piece_tags(PATRIOTS)):
            continue
        for tag in (MILITIA_U, MILITIA_A, REGULAR_PAT, FORT_PAT):
            if sp.get(tag, 0):
                remove_piece(state, tag, sid, 1, to="available")
                break
        place_with_caps(state, FORT_PAT, sid)
        done += 1
    push_history(state, f"Card 11 shaded: fortified {done} spaces")


# 12  MARTHA WASHINGTON TO VALLEY FORGE
@register(12)
def evt_012_martha_to_valley_forge(state, shaded=False):
    """
    Unshaded – Patriot desertion this Winter.
    Shaded   – Patriot Resources +5.
    """
    if shaded:
        add_resource(state, PATRIOTS, +5)
        push_history(state, "Card 12 shaded: Patriots +5 Resources")
    else:
        state["winter_flag"] = "PAT_DESERTION"
        push_history(state, "Card 12 unshaded: Patriot desertion this Winter")


# 14  OVERMOUNTAIN MEN FIGHT FOR NORTH CAROLINA
@register(14)
def evt_014_overmountain_men(state, shaded=False):
    """
    Unshaded – Indians free Scout/March to NC or SW, **then** Indians War Path
               *or* British free Battle in that space.
    Shaded   – Patriots free March to and free Battle in NC or SW.
    """
    from lod_ai.commands import march, battle, scout
    from lod_ai.special_activities import war_path

    dest = state.get("card14_dest")
    if dest not in state.get("spaces", {}):
        dest = _pick_first_existing(state, ["North_Carolina", "Southwest"])
    if not dest:
        push_history(state, "Card 14: no valid destination")
        return

    if shaded:
        src_override = state.get("card14_src")
        src = None
        if src_override in _neighbors(dest) and src_override in state.get("spaces", {}):
            if _space_has_any(state, src_override, _faction_unit_tags(PATRIOTS)):
                src = src_override
        if not src:
            for sid in _neighbors(dest):
                if sid in state.get("spaces", {}) and _space_has_any(
                    state, sid, _faction_unit_tags(PATRIOTS)
                ):
                    src = sid
                    break
        if not src:
            push_history(state, "Card 14 shaded: no legal Patriot March")
            return
        sp_src = _safe_get_space(state, src)
        piece_tag = REGULAR_PAT if sp_src.get(REGULAR_PAT, 0) else MILITIA_U
        if not sp_src.get(piece_tag, 0):
            piece_tag = MILITIA_A if sp_src.get(MILITIA_A, 0) else None
        if not piece_tag:
            push_history(state, "Card 14 shaded: no Patriot units to March")
            return
        move_plan = [{"src": src, "dst": dest, "pieces": {piece_tag: 1}}]
        march.execute(
            state,
            PATRIOTS,
            ctx={},
            sources=[src],
            destinations=[dest],
            move_plan=move_plan,
            free=True,
        )
        battle.execute(state, PATRIOTS, ctx={}, spaces=[dest], free=True)
        push_history(state, f"Card 14 shaded: Patriot March/Battle in {dest}")
        return

    op_choice = state.get("card14_op")
    if op_choice not in {"SCOUT", "MARCH"}:
        op_choice = None

    followup_override = state.get("card14_followup")
    if followup_override not in {"WAR_PATH", "BRITISH_BATTLE"}:
        followup_override = None

    if not op_choice:
        if followup_override == "WAR_PATH":
            op_choice = "SCOUT"
        else:
            op_choice = "MARCH"

    op_done = False
    if op_choice == "SCOUT":
        src_override = state.get("card14_src")
        src = None
        if src_override in _neighbors(dest) and src_override in state.get("spaces", {}):
            sp_src = _safe_get_space(state, src_override)
            if sp_src.get(REGULAR_BRI, 0) and _space_has_any(
                state, src_override, [WARPARTY_U, WARPARTY_A]
            ):
                src = src_override
        if not src:
            for sid in _neighbors(dest):
                if sid not in state.get("spaces", {}):
                    continue
                if _is_city(sid):
                    continue
                sp_src = _safe_get_space(state, sid)
                if sp_src.get(REGULAR_BRI, 0) and _space_has_any(
                    state, sid, [WARPARTY_U, WARPARTY_A]
                ):
                    src = sid
                    break
        if src:
            scout.execute(
                state,
                INDIANS,
                ctx={},
                src=src,
                dst=dest,
                n_warparties=1,
                n_regulars=1,
                n_tories=0,
                free=True,
            )
            op_done = True
    else:
        src_override = state.get("card14_src")
        src = None
        if src_override in _neighbors(dest) and src_override in state.get("spaces", {}):
            if _space_has_any(state, src_override, [WARPARTY_U, WARPARTY_A]):
                src = src_override
        if not src:
            for sid in _neighbors(dest):
                if sid in state.get("spaces", {}) and _space_has_any(
                    state, sid, [WARPARTY_U, WARPARTY_A]
                ):
                    src = sid
                    break
        if src:
            sp_src = _safe_get_space(state, src)
            wp_tag = WARPARTY_U if sp_src.get(WARPARTY_U, 0) else WARPARTY_A
            if sp_src.get(wp_tag, 0):
                move_plan = [{"src": src, "dst": dest, "pieces": {wp_tag: 1}}]
                march.execute(
                    state,
                    INDIANS,
                    ctx={},
                    sources=[src],
                    destinations=[dest],
                    move_plan=move_plan,
                    free=True,
                )
                op_done = True

    if not op_done:
        push_history(state, "Card 14 unshaded: no legal Indian Scout/March")
        return

    sp_dest = _safe_get_space(state, dest)
    if followup_override:
        followup = followup_override
    else:
        rebellion_tags = [MILITIA_A, MILITIA_U, REGULAR_PAT, REGULAR_FRE, FORT_PAT]
        if sp_dest.get(WARPARTY_U, 0) and _space_has_any(state, dest, rebellion_tags):
            followup = "WAR_PATH"
        else:
            followup = "BRITISH_BATTLE"

    if followup == "WAR_PATH":
        if sp_dest.get(WARPARTY_U, 0) and _space_has_any(
            state, dest, [MILITIA_A, MILITIA_U, REGULAR_PAT, REGULAR_FRE, FORT_PAT]
        ):
            war_path.execute(state, INDIANS, ctx={}, space_id=dest, option=1)
    else:
        battle.execute(state, BRITISH, ctx={}, spaces=[dest], free=True)

    push_history(state, f"Card 14 unshaded: {op_choice} then {followup} in {dest}")


# 17  JANE MCCREA MURDERED
@register(17)
def evt_017_jane_mccrea(state, shaded=False):
    if shaded:
        remove_piece(state, VILLAGE, None, 1, to="available")
        push_history(state, "Card 17 shaded: removed one Village")
        return

    target = state.get("card17_space")
    if target in state.get("spaces", {}) and _is_reserve(target):
        if _safe_get_space(state, target).get(FORT_PAT, 0):
            remove_piece(state, FORT_PAT, target, 1, to="available")
            push_history(state, f"Card 17 unshaded: Fort removed in {target}")
            return
    for name, sp in state.get("spaces", {}).items():
        if _is_reserve(name) and sp.get(FORT_PAT, 0):
            remove_piece(state, FORT_PAT, name, 1, to="available")
            push_history(state, f"Card 17 unshaded: Fort removed in {name}")
            break


# 26  JOSIAH MARTIN, NC ROYAL GOVERNOR, PLOTS
@register(26)
def evt_026_josiah_martin(state, shaded=False):
    """
    Unshaded – Place 1 British Fort *or* 2 Tories in North Carolina.
    Shaded   – Patriots may free March **then** free Battle in North Carolina.
    """
    from lod_ai.commands import march, battle

    province = "North_Carolina"
    if province not in state.get("spaces", {}):
        push_history(state, "Card 26: North Carolina not in play")
        return

    if shaded:
        src_override = state.get("card26_src")
        src = None
        if src_override in _neighbors(province) and src_override in state.get("spaces", {}):
            if _space_has_any(state, src_override, _faction_unit_tags(PATRIOTS)):
                src = src_override
        if not src:
            for sid in _neighbors(province):
                if sid in state.get("spaces", {}) and _space_has_any(
                    state, sid, _faction_unit_tags(PATRIOTS)
                ):
                    src = sid
                    break
        if not src:
            push_history(state, "Card 26 shaded: no legal Patriot March")
            return
        sp_src = _safe_get_space(state, src)
        piece_tag = REGULAR_PAT if sp_src.get(REGULAR_PAT, 0) else MILITIA_U
        if not sp_src.get(piece_tag, 0):
            piece_tag = MILITIA_A if sp_src.get(MILITIA_A, 0) else None
        if not piece_tag:
            push_history(state, "Card 26 shaded: no Patriot units to March")
            return
        move_plan = [{"src": src, "dst": province, "pieces": {piece_tag: 1}}]
        march.execute(
            state,
            PATRIOTS,
            ctx={},
            sources=[src],
            destinations=[province],
            move_plan=move_plan,
            free=True,
        )
        battle.execute(state, PATRIOTS, ctx={}, spaces=[province], free=True)
        push_history(state, "Card 26 shaded: Patriot March/Battle in North Carolina")
    else:
        choice = state.get("card26_choice", "FORT")
        if choice == "TORIES":
            place_piece(state, TORY, province, 2)
            push_history(state, "Card 26 unshaded: placed 2 Tories in North Carolina")
        else:
            place_with_caps(state, FORT_BRI, province)
            push_history(state, "Card 26 unshaded: placed British Fort in North Carolina")


# 27  QUEEN’S RANGERS
@register(27)
def evt_027_queens_rangers(state, shaded=False):
    if shaded:
        override = state.get("card27_cities")
        if isinstance(override, list):
            cities = [sid for sid in override if sid in state.get("spaces", {})]
        else:
            cities = [sid for sid in state.get("spaces", {}) if _is_city(sid)]
        for name in cities[:2]:
            shift_support(state, name, -1)
            place_piece(state, MILITIA_U, name, 1)
        push_history(state, "Card 27 shaded: shifted two Cities and placed Militia")
        return

    _ensure_control(state)
    override = state.get("card27_colonies")
    if isinstance(override, list):
        targets = [sid for sid in override if sid in state.get("spaces", {})]
    else:
        targets = [sid for sid in state.get("spaces", {}) if _is_colony(sid)]
    targets = [sid for sid in targets if state.get("control", {}).get(sid) == BRITISH]

    for name in targets[:2]:
        _place_from_pools(state, TORY, name, 2)
    push_history(state, "Card 27 unshaded: placed Tories in two British colonies")


# 34  LORD SANDWICH
@register(34)
def evt_034_lord_sandwich(state, shaded=False):
    if shaded:
        state.setdefault("ineligible_through_next", set()).add(BRITISH)
        shift = +1
        push_history(state, "Card 34 shaded: British ineligible through next")
    else:
        add_resource(state, BRITISH, +6)
        shift = -1
    adjust_fni(state, shift)


# 38  JOHNSON’S ROYAL GREENS
@register(38)
def evt_038_johnsons_royal_greens(state, shaded=False):
    if shaded:
        if "New_York" not in state.get("spaces", {}):
            push_history(state, "Card 38 shaded: New York not in play")
            return
        choice = state.get("card38_shaded_choice")
        if choice not in {"MILITIA", "WARPARTY"}:
            available_militia = state.get("available", {}).get(MILITIA_U, 0)
            choice = "MILITIA" if available_militia >= 3 else "WARPARTY"
        if choice == "WARPARTY":
            place_piece(state, WARPARTY_U, "New_York", 3)
            push_history(state, "Card 38 shaded: placed 3 War Parties in New York")
        else:
            place_piece(state, MILITIA_U, "New_York", 3)
            push_history(state, "Card 38 shaded: placed 3 Militia in New York")
        return

    target = state.get("card38_unshaded_space")
    if target not in state.get("spaces", {}):
        target = _pick_first_existing(state, ["Quebec", "New_York"])
    if not target:
        push_history(state, "Card 38 unshaded: no valid target")
        return

    mix = state.get("card38_unshaded_mix")
    reg_count = tory_count = None
    if isinstance(mix, dict):
        reg_count = int(mix.get(REGULAR_BRI, 0))
        tory_count = int(mix.get(TORY, 0))
        if reg_count + tory_count != 4:
            reg_count = tory_count = None

    if reg_count is None:
        reg_available = state.get("available", {}).get(REGULAR_BRI, 0) + state.get("unavailable", {}).get(REGULAR_BRI, 0)
        tory_available = state.get("available", {}).get(TORY, 0) + state.get("unavailable", {}).get(TORY, 0)
        reg_count = min(4, reg_available)
        tory_count = min(4 - reg_count, tory_available)

    if reg_count:
        _place_from_pools(state, REGULAR_BRI, target, reg_count)
    if tory_count:
        _place_from_pools(state, TORY, target, tory_count)

    state.setdefault("ineligible_next", set()).discard(BRITISH)
    state.setdefault("ineligible_through_next", set()).discard(BRITISH)
    state.setdefault("remain_eligible", set()).add(BRITISH)
    push_history(state, f"Card 38 unshaded: Royal Greens reinforce {target}")


# 42  BRITISH ATTACK DANBURY
@register(42)
def evt_042_attack_danbury(state, shaded=False):
    target = "Connecticut_Rhode_Island"
    if shaded:
        place_piece(state, MILITIA_U, target, 3)
        place_piece(state, REGULAR_PAT, target, 1)
        push_history(state, "Card 42 shaded: Patriots rally in Connecticut/Rhode Island")
    else:
        add_resource(state, PATRIOTS, -3)
        place_piece(state, TORY, target, 1)
        push_history(state, "Card 42 unshaded: Patriots -3 Resources")


# 44  EARL OF MANSFIELD RECALLED FROM PARIS
@register(44)
def evt_044_mansfield_recalled(state, shaded=False):
    if not shaded:
        target = state.get("card44_target_faction", PATRIOTS)
        state.setdefault("ineligible_through_next", set()).add(target)
        push_history(state, f"Card 44 unshaded: {target} ineligible through next")


# 47  TORIES TESTED
@register(47)
def evt_047_tories_tested(state, shaded=False):
    """
    Unshaded – Place 3 Tories in 1 Colony with British Control.
    Shaded   – Replace all Tories in 1 Colony with Militia; place 2 Propaganda.
    """
    target = state.get("card47_colony")

    if shaded:
        if target not in state.get("spaces", {}):
            for sid in state.get("spaces", {}):
                if _is_colony(sid) and _safe_get_space(state, sid).get(TORY, 0):
                    target = sid
                    break
        if target not in state.get("spaces", {}):
            target = _pick_first_existing(state, [sid for sid in state.get("spaces", {}) if _is_colony(sid)])
        if target:
            tories = _safe_get_space(state, target).get(TORY, 0)
            if tories:
                remove_piece(state, TORY, target, tories, to="available")
                place_piece(state, MILITIA_U, target, tories)
            place_marker(state, PROPAGANDA, target, 2)
            push_history(state, f"Card 47 shaded: replaced Tories in {target}")
        return

    _ensure_control(state)
    if target not in state.get("spaces", {}):
        for sid in state.get("spaces", {}):
            if _is_colony(sid) and state.get("control", {}).get(sid) == BRITISH:
                target = sid
                break
    if target and state.get("control", {}).get(target) == BRITISH:
        place_piece(state, TORY, target, 3)
        push_history(state, f"Card 47 unshaded: placed 3 Tories in {target}")


# 50  ADMIRAL D’ESTAING — FRENCH FLEET ARRIVES
@register(50)
def evt_050_destaing_arrives(state, shaded=False):
    """
    Unshaded – French Ineligible through next card; remove 2 French Regulars
               from West Indies *or* map to Available.
    Shaded   – Place 2 Continentals & 2 French Regulars in 1 Colony.
    """
    if shaded:
        target = state.get("card50_colony")
        if target not in state.get("spaces", {}):
            for sid in state.get("spaces", {}):
                if _is_colony(sid):
                    target = sid
                    break
        if target:
            place_piece(state, REGULAR_PAT, target, 2)
            place_piece(state, REGULAR_FRE, target, 2)
            push_history(state, f"Card 50 shaded: placed Patriot/French in {target}")
        return

    removed = move_piece(state, REGULAR_FRE, WEST_INDIES_ID, "available", 2)
    if removed < 2:
        remove_piece(state, REGULAR_FRE, None, 2 - removed, to="available")
    state.setdefault("ineligible_through_next", set()).add(FRENCH)
    push_history(state, "Card 50 unshaded: French ineligible through next")


# 55  FRENCH NAVY DOMINATES CARIBBEAN
@register(55)
def evt_055_french_navy(state, shaded=False):
    """
    Unshaded – Move 3 French Regulars to West Indies; French *may* free
               Battle there; Lower FNI 1.
    Shaded   – Move any 4 British Regulars to West Indies; British *must*
               free Battle there.
    """
    from lod_ai.commands import battle

    if shaded:
        moved = 0
        for n, sp in state.get("spaces", {}).items():
            if n == WEST_INDIES_ID:
                continue
            if moved == 4:
                break
            qty = sp.get(REGULAR_BRI, 0)
            if qty:
                move_piece(state, REGULAR_BRI, n, WEST_INDIES_ID, min(qty, 4 - moved))
                moved += min(qty, 4 - moved)
        battle.execute(state, BRITISH, ctx={}, spaces=[WEST_INDIES_ID], free=True)
        push_history(state, "Card 55 shaded: British battle in West Indies")
    else:
        moved = 0
        for n, sp in state.get("spaces", {}).items():
            if n == WEST_INDIES_ID:
                continue
            if moved == 3:
                break
            qty = sp.get(REGULAR_FRE, 0)
            if qty:
                move_piece(state, REGULAR_FRE, n, WEST_INDIES_ID, min(qty, 3 - moved))
                moved += min(qty, 3 - moved)
        adjust_fni(state, -1)
        if state.get("card55_do_battle", True):
            battle.execute(state, FRENCH, ctx={}, spaces=[WEST_INDIES_ID], free=True)
        push_history(state, "Card 55 unshaded: French may battle in West Indies")


# 58  BEN FRANKLIN’S OLD AIDE
@register(58)
def evt_058_lafayette(state, shaded=False):
    if shaded:
        for sid in ("New_York", "Quebec", "Northwest"):
            if sid not in state.get("spaces", {}):
                continue
            tories = _safe_get_space(state, sid).get(TORY, 0)
            if tories:
                remove_piece(state, TORY, sid, tories, to="available")
                place_piece(state, MILITIA_U, sid, tories)
        push_history(state, "Card 58 shaded: replaced Tories with Militia")
    else:
        add_resource(state, PATRIOTS, -4)
        push_history(state, "Card 58 unshaded: Patriots -4 Resources")


# 59  TRONSON DE COUDRAY
@register(59)
def evt_059_coudray(state, shaded=False):
    """
    Unshaded – Remove 2 Continentals and 2 French Regulars from one space.
    Shaded   – Patriot Resources +3.
    """
    if shaded:
        add_resource(state, PATRIOTS, +3)
        push_history(state, "Card 59 shaded: Patriots +3 Resources")
        return

    target = state.get("card59_space")
    if target not in state.get("spaces", {}):
        # Prefer a space with both Continentals and French Regulars
        for sid, sp in state.get("spaces", {}).items():
            if sp.get(REGULAR_PAT, 0) and sp.get(REGULAR_FRE, 0):
                target = sid
                break
        # Fall back to any space with either piece type
        if target not in state.get("spaces", {}):
            for sid, sp in state.get("spaces", {}).items():
                if sp.get(REGULAR_PAT, 0) or sp.get(REGULAR_FRE, 0):
                    target = sid
                    break
    if target:
        remove_piece(state, REGULAR_PAT, target, 2, to="available")
        remove_piece(state, REGULAR_FRE, target, 2, to="available")
        push_history(state, f"Card 59 unshaded: removed pieces in {target}")


# 60  COMTE D’ORVILLIERS BUILDS A FLEET
@register(60)
def evt_060_orvilliers(state, shaded=False):
    if shaded:
        adjust_fni(state, +1)
        add_resource(state, BRITISH, -3)
    else:
        adjust_fni(state, -2)
        add_resource(state, FRENCH, -4)


# 61  VERGENNES
@register(61)
def evt_061_vergennes(state, shaded=False):
    if shaded:
        add_resource(state, PATRIOTS, +3)
        add_resource(state, FRENCH, +2)
        push_history(state, "Card 61 shaded: Patriots +3, French +2")
    else:
        state.setdefault("ineligible_through_next", set()).add(PATRIOTS)
        push_history(state, "Card 61 unshaded: Patriots ineligible through next")


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
        add_resource(state, BRITISH, -5)
        return

    add_resource(state, BRITISH, +1)
    adjust_fni(state, -1)
    move_piece(state, REGULAR_BRI, WEST_INDIES_ID, "available", 2)


# 69  ADMIRAL SUFFREN
@register(69)
def evt_069_suffren(state, shaded=False):
    if shaded:
        adjust_fni(state, +1)
        add_resource(state, FRENCH, +3)
    else:
        adjust_fni(state, -2)
        add_resource(state, BRITISH, +2)


# 71  TREATY OF AMITY & COMMERCE
@register(71)
def evt_071_treaty_amity(state, shaded=False):
    """
    Unshaded – Add population of Cities under Rebellion Control to Patriot Resources.
    Shaded   – French Resources +5.
    """
    if shaded:
        add_resource(state, FRENCH, +5)
        push_history(state, "Card 71 shaded: French +5 Resources")
        return

    _ensure_control(state)
    pop = 0
    for sid, sp in state.get("spaces", {}).items():
        if _is_city(sid) and state.get("control", {}).get(sid) == "REBELLION":
            # Population from map metadata, falling back to space dict
            meta = map_adj.space_meta(sid) or {}
            pop += meta.get("population", sp.get("population", 0))
    add_resource(state, PATRIOTS, pop)
    push_history(state, f"Card 71 unshaded: Patriots +{pop} (Rebellion cities pop)")


# 74  CHICKASAW ALLY WITH THE BRITISH
@register(74)
def evt_074_chickasaw(state, shaded=False):
    """
    Unshaded – Indians or British add 1 Resource per 2 Indian Villages.
    Shaded   – In each of 2 spaces, remove either
               1 War Party + 2 Militia OR 2 War Parties + 1 Militia.
    """
    if not shaded:
        villages = sum(sp.get(VILLAGE, 0) for sp in state.get("spaces", {}).values())
        recipient = state.get("card74_recipient", INDIANS)
        if recipient not in {INDIANS, BRITISH}:
            recipient = INDIANS
        add_resource(state, recipient, villages // 2)
        push_history(state, f"Card 74 unshaded: {recipient} +{villages // 2}")
        return

    override = state.get("card74_spaces")
    if isinstance(override, list):
        candidates = [sid for sid in override if sid in state.get("spaces", {})]
    else:
        candidates = []
        for sid, sp in state.get("spaces", {}).items():
            wp = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
            mil = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
            if wp >= 1 and mil >= 1 and wp + mil >= 3:
                candidates.append(sid)
    done = 0
    for sid in candidates:
        if done == 2:
            break
        sp = _safe_get_space(state, sid)
        wp = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
        mil = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
        if wp < 1 or mil < 1:
            continue
        if mil >= 2:
            _remove_from_tags(state, sid, [WARPARTY_U, WARPARTY_A], 1)
            _remove_from_tags(state, sid, [MILITIA_U, MILITIA_A], 2)
        elif wp >= 2:
            _remove_from_tags(state, sid, [WARPARTY_U, WARPARTY_A], 2)
            _remove_from_tags(state, sid, [MILITIA_U, MILITIA_A], 1)
        else:
            continue
        push_history(state, f"Card 74 shaded: removals in {sid}")
        done += 1


# 76  EDWARD HAND RAIDS
@register(76)
def evt_076_edward_hand(state, shaded=False):
    """
    Unshaded – British replace 3 Militia with 3 Tories in one Province.
    Shaded   – British remove 2 Indian Villages anywhere.
    """
    if shaded:
        remove_piece(state, VILLAGE, None, 2, to="available")
        push_history(state, "Card 76 shaded: removed 2 Villages")
        return

    target = state.get("card76_space")
    if target not in state.get("spaces", {}):
        for n, sp in state.get("spaces", {}).items():
            if n == WEST_INDIES_ID or _is_city(n):
                continue
            if sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0) >= 3:
                target = n
                break
    if not target:
        push_history(state, "Card 76 unshaded: no Province with 3 Militia")
        return

    _remove_from_tags(state, target, [MILITIA_U, MILITIA_A], 3)
    place_piece(state, TORY, target, 3)
    push_history(state, f"Card 76 unshaded: Militia replaced in {target}")


# 77  GENERAL BURGOYNE CRACKS DOWN
@register(77)
def evt_077_burgoyne(state, shaded=False):
    if shaded:
        affected = 0
        for name, sp in state.get("spaces", {}).items():
            if affected == 3:
                break
            if _is_city(name):
                continue
            if not _space_has_any(state, name, [WARPARTY_A, WARPARTY_U, VILLAGE]):
                continue
            if not _space_has_any(state, name, [REGULAR_BRI, TORY, FORT_BRI]):
                continue
            if remove_piece(state, REGULAR_BRI, name, 1, to="available"):
                pass
            elif remove_piece(state, TORY, name, 1, to="available"):
                pass
            else:
                remove_piece(state, FORT_BRI, name, 1, to="available")
            place_marker(state, RAID, name, 1)
            affected += 1
        push_history(state, "Card 77 shaded: removed British pieces in provinces")
    else:
        target = state.get("card77_space")
        if target not in state.get("spaces", {}):
            for n, sp in state.get("spaces", {}).items():
                if _space_has_any(state, n, [REGULAR_BRI, TORY, FORT_BRI]) and _space_has_any(
                    state, n, [WARPARTY_A, WARPARTY_U, VILLAGE]
                ):
                    target = n
                    break
        if target:
            place_with_caps(state, VILLAGE, target)
        for name, sp in state.get("spaces", {}).items():
            count = sp.get(WARPARTY_A, 0)
            if count:
                remove_piece(state, WARPARTY_A, name, count, to="available")
                place_piece(state, WARPARTY_U, name, count)
        push_history(state, "Card 77 unshaded: Village placed, War Parties underground")


# 78  CHERRY VALLEY DESTROYED
@register(78)
def evt_078_cherry_valley(state, shaded=False):
    if shaded:
        added = 0
        for name, sp in state.get("spaces", {}).items():
            if added == 4:
                break
            if sp.get(TORY) or sp.get(WARPARTY_A) or sp.get(WARPARTY_U) or sp.get(VILLAGE):
                place_piece(state, MILITIA_U, name, 1)
                added += 1
        push_history(state, "Card 78 shaded: militia rally")
    else:
        pat_tags = (REGULAR_PAT, MILITIA_U, MILITIA_A)
        total_pieces = sum(sp.get(t, 0) for sp in state.get("spaces", {}).values() for t in pat_tags)
        to_remove = total_pieces // 4
        removed_total = 0
        for name, sp in state.get("spaces", {}).items():
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
        push_history(state, f"Card 78 unshaded: removed {removed_total} Patriot pieces")


# 80  CONFUSION ALLOWS SLAVES TO ESCAPE
@register(80)
def evt_080_confusion_slaves(state, shaded=False):
    if shaded:
        push_history(state, "Card 80 shaded: no effect")
        return

    target = state.get("card80_faction", state.get("active", BRITISH))
    if target not in {BRITISH, PATRIOTS, FRENCH, INDIANS}:
        target = state.get("active", BRITISH)

    pieces = _faction_piece_tags(target)
    candidates = [
        sid for sid in state.get("spaces", {}) if sum(_safe_get_space(state, sid).get(t, 0) for t in pieces) >= 2
    ]
    spaces = state.get("card80_spaces")
    if isinstance(spaces, list):
        candidates = [sid for sid in spaces if sid in state.get("spaces", {})]
    chosen = candidates[:2]

    for sid in chosen:
        _remove_from_tags(state, sid, pieces, 2)
        push_history(state, f"Card 80 unshaded: {target} removes 2 pieces in {sid}")


# 88  “IF IT HADN’T BEEN SO FOGGY…”
@register(88)
def evt_088_foggy(state, shaded=False):
    if shaded:
        push_history(state, "Card 88 shaded: no effect")
        return

    mover = state.get("active", BRITISH)
    if mover not in {BRITISH, PATRIOTS, FRENCH, INDIANS}:
        mover = BRITISH

    target = state.get("card88_target_faction")
    targets = [BRITISH, PATRIOTS, FRENCH, INDIANS]

    def _shares_space(target_faction):
        for sid in state.get("spaces", {}):
            if not _space_has_any(state, sid, _faction_unit_tags(mover)):
                continue
            if _space_has_any(state, sid, _faction_piece_tags(target_faction)):
                return True
        return False

    if target not in targets or not _shares_space(target):
        target = None
        for fac in targets:
            if fac != mover and _shares_space(fac):
                target = fac
                break

    if not target:
        push_history(state, "Card 88 unshaded: no shared spaces")
        return

    destinations = state.get("card88_destinations", {})

    for src in list(state.get("spaces", {})):
        if not _space_has_any(state, src, _faction_unit_tags(mover)):
            continue
        if not _space_has_any(state, src, _faction_piece_tags(target)):
            continue
        dest = None
        if isinstance(destinations, dict):
            candidate = destinations.get(src)
            if candidate in state.get("spaces", {}) and candidate in _neighbors(src):
                dest = candidate
        if not dest:
            for nbr in _neighbors(src):
                if nbr in state.get("spaces", {}):
                    dest = nbr
                    break
        if not dest:
            continue
        for tag in _faction_unit_tags(mover):
            qty = _safe_get_space(state, src).get(tag, 0)
            if qty:
                move_piece(state, tag, src, dest, qty)
        push_history(state, f"Card 88 unshaded: {mover} units move from {src} to {dest}")


# 89  WAR DAMAGES COLONIES’ ECONOMY
@register(89)
def evt_089_war_damages(state, shaded=False):
    if shaded:
        replaced = 0
        for name, sp in state.get("spaces", {}).items():
            if replaced == 3:
                break
            qty = sp.get(TORY, 0)
            if qty:
                n = min(qty, 3 - replaced)
                remove_piece(state, TORY, name, n, to="available")
                place_piece(state, MILITIA_U, name, n)
                replaced += n
        push_history(state, f"Card 89 shaded: replaced {replaced} Tories with militia")
    else:
        replaced = 0
        for name, sp in state.get("spaces", {}).items():
            if replaced == 4:
                break
            for tag in (MILITIA_U, MILITIA_A, REGULAR_PAT):
                qty = sp.get(tag, 0)
                if qty:
                    n = min(qty, 4 - replaced)
                    remove_piece(state, tag, name, n, to="available")
                    place_piece(state, TORY, name, n)
                    replaced += n
                if replaced == 4:
                    break
        push_history(state, f"Card 89 unshaded: replaced {replaced} Patriot units with Tories")


# 93  WYOMING MASSACRE
@register(93)
def evt_093_wyoming(state, shaded=False):
    if shaded:
        push_history(state, "Card 93 shaded: no effect")
        return

    override = state.get("card93_targets")
    if isinstance(override, list):
        cols = [sid for sid in override if sid in state.get("spaces", {})]
    else:
        cols = [sid for sid in state.get("spaces", {}) if _is_colony(sid)]

    def _adjacent_to_reserve(col_id):
        for nbr in _neighbors(col_id):
            if _is_reserve(nbr):
                return True
        return False

    affected = 0
    for name in cols:
        if affected == 3:
            break
        if not _adjacent_to_reserve(name):
            continue
        support = state.get("support", {}).get(name, 0)
        if support > 0:
            shift_support(state, name, -1)
        elif support < 0:
            shift_support(state, name, +1)
        place_marker(state, RAID, name, 1)
        affected += 1
    push_history(state, f"Card 93 unshaded: affected {affected} Colonies")
