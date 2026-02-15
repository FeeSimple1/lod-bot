"""
lod_ai.commands.battle
======================
Universal Battle Command (S3.6).

Supported factions
------------------
British, Patriots, French (after Treaty of Alliance).

Common-Cause
------------
If ``ctx["common_cause"][space_id] == n`` War Parties, treat those WP as
Tory cubes for *both* force and casualties; they never count against the
"half Active War Parties" rule (prevents double-counting).

Loss modifiers
--------------
All modifiers per S3.6.5 (Defender Loss Level) and S3.6.6 (Attacker
Loss Level) are computed per-space based on actual state: piece counts,
leader locations, terrain, blockade markers, and fortifications.

---------------------------------------------------------------------------
Win the Day (§3.6.8) includes:
* Support overflow to adjacent spaces (sorted by population for bots)
* Free Rally for Rebellion winner (caller provides space/kwargs)
* Blockade move from Battle City to another City (caller provides dest)
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.rules_consts import (
    # Pieces
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY,
    MILITIA_A, MILITIA_U,
    WARPARTY_A, WARPARTY_U,
    FORT_BRI, FORT_PAT,
    VILLAGE,
    # Support indices
    ACTIVE_SUPPORT, PASSIVE_SUPPORT, NEUTRAL,
    PASSIVE_OPPOSITION, ACTIVE_OPPOSITION,
    WEST_INDIES_ID,
    # Factions
    BRITISH, PATRIOTS, FRENCH, INDIANS,
)
from lod_ai.leaders        import apply_leader_modifiers, leader_location
from lod_ai.util.piece_kinds import is_cube, loss_value
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces   import remove_piece, add_piece
from lod_ai.economy.resources import spend, can_afford
from lod_ai.util.loss_mod  import pop_loss_mod
from lod_ai.util.naval     import has_blockade, move_blockade_city_to_city
from lod_ai.map             import adjacency as map_adj

COMMAND_NAME = "BATTLE"

# Leaders grouped by side for modifier checks (S3.6.5, S3.6.6)
_ROYALIST_LEADERS = [
    "LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON",
    "LEADER_BRANT", "LEADER_CORNPLANTER", "LEADER_DRAGGING_CANOE",
]
_REBELLION_LEADERS = [
    "LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN",
]


# -------- Public entry --------
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    spaces: List[str],
    *,
    choices: Dict | None = None,
    free: bool = False,
    win_rally_space: str | None = None,
    win_rally_kwargs: Dict | None = None,
    win_blockade_dest: str | None = None,
) -> Dict:
    faction = faction.upper()
    if faction not in (BRITISH, PATRIOTS, FRENCH):
        raise ValueError("Only BRITISH, PATRIOTS or FRENCH may initiate Battle")
    if faction == FRENCH and not state.get("toa_played"):
        raise ValueError("French cannot Battle before Treaty of Alliance")
    if not spaces:
        raise ValueError("Need >= 1 battle space")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(spaces)
    # Pay Resources (actor only); allied fees handled below
    if not free:
        spend(state, faction, len(spaces))

    # §3.3.3 / §3.5.5: Allied fee is 1 Resource per space where the ally's
    # pieces are involved, NOT per piece.
    if faction == PATRIOTS:
        fee = sum(1 for s in spaces if state["spaces"][s].get(REGULAR_FRE, 0) > 0)
        if fee:
            spend(state, FRENCH, fee)
    elif faction == FRENCH:
        fee = sum(1 for s in spaces if state["spaces"][s].get(REGULAR_PAT, 0) > 0)
        if fee:
            spend(state, PATRIOTS, fee)

    ctx = apply_leader_modifiers(state, faction, "pre_battle", ctx)
    push_history(state, f"{faction} BATTLE in {', '.join(spaces)}")

    attacker_bonus = (choices or {}).get("force_bonus", 0)

    rebellion_won_in: list[str] = []
    for sid in spaces:
        winner = _resolve_space(state, ctx, faction, sid, attacker_bonus)
        if winner == "REBELLION":
            rebellion_won_in.append(sid)

    # §3.6.8: Post-win actions for Rebellion winner
    if rebellion_won_in:
        # Free Rally in any one eligible space
        if win_rally_space:
            from lod_ai.commands import rally
            pre_res = state["resources"].get(PATRIOTS, 0)
            rally.execute(
                state, PATRIOTS, {},
                [win_rally_space],
                **(win_rally_kwargs or {}),
            )
            # Restore resources — this Rally is free (§3.6.8)
            state["resources"][PATRIOTS] = pre_res

        # Move Blockades from any Battle City to another City
        if win_blockade_dest:
            for battle_sid in rebellion_won_in:
                if map_adj.is_city(battle_sid):
                    move_blockade_city_to_city(state, battle_sid, win_blockade_dest)

    refresh_control(state)
    enforce_global_caps(state)
    return ctx


# -------- Internal helpers --------
def _roll_d3(state: Dict) -> int:
    val = state["rng"].randint(1, 3)
    state.setdefault("rng_log", []).append(("D3", val))
    return val


def _half(n: int) -> int:
    return n >> 1


def _side_has_leader(state: Dict, sid: str, side: str) -> bool:
    """Return True if any leader for *side* is in space *sid*."""
    leaders = _ROYALIST_LEADERS if side == "ROYALIST" else _REBELLION_LEADERS
    return any(leader_location(state, lid) == sid for lid in leaders)


# -------- S3.6.5 Defender Loss Level modifiers (cumulative) --------
def _defender_loss_mods(
    state: Dict, sp: Dict, sid: str,
    att_side: str, def_side: str, cc_wp: int,
) -> int:
    """Compute modifiers applied to the attacker's roll to determine
    how many losses the *defender* takes."""
    mods = 0

    # +1 if at least half Attacking Cubes are Regulars (if any)
    if att_side == "ROYALIST":
        att_regs = sp.get(REGULAR_BRI, 0)
        att_cubes = att_regs + sp.get(TORY, 0) + cc_wp
    else:
        att_regs = sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
        att_cubes = att_regs  # all Rebellion cubes are Regulars/Continentals
    if att_cubes > 0 and att_regs * 2 >= att_cubes:
        mods += 1

    # +1 if at least one Attacking side piece Underground
    if att_side == "ROYALIST":
        if sp.get(WARPARTY_U, 0) > 0:
            mods += 1
    else:
        if sp.get(MILITIA_U, 0) > 0:
            mods += 1

    # +1 if at least one Attacking Leader
    if _side_has_leader(state, sid, att_side):
        mods += 1

    # +1 if Attacking includes French with Lauzun
    if att_side == "REBELLION" and sp.get(REGULAR_FRE, 0) > 0:
        if leader_location(state, "LEADER_LAUZUN") == sid:
            mods += 1

    # -1 if British Attacking in Blockaded City
    if att_side == "ROYALIST" and map_adj.is_city(sid) and has_blockade(state, sid):
        mods -= 1

    # -1 if British Attacking in West Indies and at least one Squadron
    if att_side == "ROYALIST" and sid == WEST_INDIES_ID and has_blockade(state, sid):
        mods -= 1

    # -1 per Defending Fort
    def_fort_tag = FORT_BRI if def_side == "ROYALIST" else FORT_PAT
    mods -= sp.get(def_fort_tag, 0)

    # -1 if Indians Defending in Indian Reserve
    if def_side == "ROYALIST" and map_adj.space_type(sid) == "Reserve":
        if sp.get(WARPARTY_A, 0) > 0 or sp.get(WARPARTY_U, 0) > 0:
            mods -= 1

    # -1 if Patriots/French Defending with Washington
    if def_side == "REBELLION":
        if leader_location(state, "LEADER_WASHINGTON") == sid:
            mods -= 1

    return mods


# -------- S3.6.6 Attacker Loss Level modifiers (cumulative) --------
def _attacker_loss_mods(
    state: Dict, sp: Dict, sid: str,
    att_side: str, def_side: str, cc_wp: int,
) -> int:
    """Compute modifiers applied to the defender's roll to determine
    how many losses the *attacker* takes."""
    mods = 0

    # +1 if at least half Defending Cubes are Regulars (if any)
    if def_side == "ROYALIST":
        def_regs = sp.get(REGULAR_BRI, 0)
        def_cubes = def_regs + sp.get(TORY, 0) + cc_wp
    else:
        def_regs = sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
        def_cubes = def_regs
    if def_cubes > 0 and def_regs * 2 >= def_cubes:
        mods += 1

    # +1 if at least one Defending side piece Underground
    if def_side == "ROYALIST":
        if sp.get(WARPARTY_U, 0) > 0:
            mods += 1
    else:
        if sp.get(MILITIA_U, 0) > 0:
            mods += 1

    # +1 if at least one Defending Leader
    if _side_has_leader(state, sid, def_side):
        mods += 1

    # -1 if British Defending in Blockaded City
    if def_side == "ROYALIST" and map_adj.is_city(sid) and has_blockade(state, sid):
        mods -= 1

    # -1 if British Defending in West Indies and at least one Squadron
    if def_side == "ROYALIST" and sid == WEST_INDIES_ID and has_blockade(state, sid):
        mods -= 1

    # +1 per Defending Fort
    def_fort_tag = FORT_BRI if def_side == "ROYALIST" else FORT_PAT
    mods += sp.get(def_fort_tag, 0)

    return mods


# -------- Support shift helper (§3.6.8) --------
def _apply_shifts_to(
    state: Dict, space_id: str, winner: str, remaining: int,
) -> int:
    """Apply up to *remaining* support shifts in *space_id* toward the
    *winner*'s preferred direction.  Return the number of shifts still unused."""
    for i in range(remaining):
        cur = state.get("support", {}).get(space_id, NEUTRAL)
        if winner == "ROYALIST" and cur > ACTIVE_OPPOSITION:
            state.setdefault("support", {})[space_id] = cur - 1
        elif winner == "REBELLION" and cur < ACTIVE_SUPPORT:
            state.setdefault("support", {})[space_id] = cur + 1
        else:
            return remaining - i
    return 0


# -------- Single-space battle --------
def _resolve_space(
    state: Dict,
    ctx: Dict,
    attacker_faction: str,
    sid: str,
    attacker_bonus: int,
) -> str | None:
    sp = state["spaces"][sid]

    att_side = "ROYALIST" if attacker_faction == BRITISH else "REBELLION"
    def_side = "REBELLION" if att_side == "ROYALIST" else "ROYALIST"

    cc_wp = ctx.get("common_cause", {}).get(sid, 0)

    # §8.7.9 Indian bot defending activation:
    # If Village in Battle space, Activate all but 1 Underground WP.
    # Otherwise, Activate no Underground WP.
    if def_side == "ROYALIST" and sp.get(WARPARTY_U, 0) > 0:
        if INDIANS not in state.get("human_factions", set()):
            if sp.get(VILLAGE, 0) > 0:
                activate_n = sp.get(WARPARTY_U, 0) - 1
                if activate_n > 0:
                    sp[WARPARTY_U] -= activate_n
                    sp[WARPARTY_A] = sp.get(WARPARTY_A, 0) + activate_n
            # else: Activate no Underground WP (leave them as-is)

    def _force(side: str, is_defending: bool) -> int:
        """S3.6.2-3.6.3: cubes + half Active guerrillas + Forts if Defending."""
        if side == "ROYALIST":
            regs = sp.get(REGULAR_BRI, 0)
            tories = sp.get(TORY, 0) + cc_wp
            if not is_defending:
                tories = min(tories, regs)
            active_wp = max(0, sp.get(WARPARTY_A, 0) - cc_wp)
            cubes = regs + tories + _half(active_wp)
        else:
            # §3.6.3: "If Rebellion Attack, if that Faction paid, add French
            # Regulars or Continentals up to the number of own Faction's cubes."
            pat_cubes = sp.get(REGULAR_PAT, 0)
            fre_cubes = sp.get(REGULAR_FRE, 0)
            if not is_defending:
                if attacker_faction == PATRIOTS:
                    fre_cubes = min(fre_cubes, pat_cubes)
                elif attacker_faction == FRENCH:
                    pat_cubes = min(pat_cubes, fre_cubes)
            regs = pat_cubes + fre_cubes
            active_mil = sp.get(MILITIA_A, 0)
            cubes = regs + _half(active_mil)
        if is_defending:
            forts = sp.get(FORT_BRI if side == "ROYALIST" else FORT_PAT, 0)
            return cubes + forts
        return cubes

    att_force = _force(att_side, False) + attacker_bonus
    def_force = _force(def_side, True)

    # S3.6.4 Roll dice: Force / 3 D3s, max 3 dice; 0 if Force <= 2
    def _base_roll(force: int) -> int:
        dice = min(3, force // 3)
        return sum(_roll_d3(state) for _ in range(dice))

    # S3.6.5 Defender Loss Level = attacker roll + defender loss modifiers
    def_loss_roll = _base_roll(att_force)
    def_loss_mods = _defender_loss_mods(state, sp, sid, att_side, def_side, cc_wp)
    defender_loss = max(0, def_loss_roll + def_loss_mods)

    # S3.6.6 Attacker Loss Level = defender roll + attacker loss modifiers
    att_loss_roll = _base_roll(def_force)
    att_loss_mods = _attacker_loss_mods(state, sp, sid, att_side, def_side, cc_wp)
    attacker_loss = max(0, att_loss_roll + att_loss_mods)

    # Additional event/card modifiers (loss_mod queue)
    att_mod, def_mod = pop_loss_mod(state, sid)
    attacker_loss += att_mod
    defender_loss += def_mod

    # -- Casualty removal (S3.6.7) --
    def _remove(side: str, loss: int) -> tuple[int, bool]:
        """Alternate removal per S3.6.7. Underground pieces ignored."""
        if loss <= 0:
            return 0, False

        is_defending = (side == def_side)
        removed = 0
        removed_cube_or_fort = False
        remaining_loss = loss

        def _take_one(tag: str) -> bool:
            nonlocal removed, remaining_loss, removed_cube_or_fort
            if sp.get(tag, 0) <= 0 or remaining_loss <= 0:
                return False
            # Cubes to Casualties; guerrillas/villages to Available
            dest = "casualties" if is_cube(tag) else "available"
            remove_piece(state, tag, sid, 1, to=dest)
            removed += 1
            remaining_loss -= loss_value(tag)
            if is_cube(tag) or tag in (FORT_BRI, FORT_PAT):
                removed_cube_or_fort = True
            return True

        if side == "ROYALIST":
            # Phase 1: Alternate Regulars and Tories
            while remaining_loss > 0:
                took_reg = _take_one(REGULAR_BRI)
                if remaining_loss > 0:
                    took_tory = _take_one(TORY)
                else:
                    break
                if not took_reg and not took_tory:
                    break
            # Phase 2: Active War Parties (to Available)
            while remaining_loss > 0 and sp.get(WARPARTY_A, 0) > 0:
                _take_one(WARPARTY_A)
            # Phase 3: If Defending only -- Villages then Forts
            if is_defending:
                while remaining_loss > 0 and sp.get(VILLAGE, 0) > 0:
                    remove_piece(state, VILLAGE, sid, 1, to="available")
                    removed += 1
                    remaining_loss -= 1
                while remaining_loss > 0 and sp.get(FORT_BRI, 0) > 0:
                    # §3.6.7: "Forts also count as Casualties but return to
                    # Available immediately."
                    remove_piece(state, FORT_BRI, sid, 1, to="available")
                    removed += 1
                    remaining_loss -= loss_value(FORT_BRI)
                    removed_cube_or_fort = True
        else:
            # Phase 1: Alternate French Regulars, Continentals, Active Militia
            while remaining_loss > 0:
                took_fre = _take_one(REGULAR_FRE)
                took_pat = _take_one(REGULAR_PAT) if remaining_loss > 0 else False
                took_mil = _take_one(MILITIA_A) if remaining_loss > 0 else False
                if not took_fre and not took_pat and not took_mil:
                    break
            # Phase 2: If Defending only -- Forts
            if is_defending:
                while remaining_loss > 0 and sp.get(FORT_PAT, 0) > 0:
                    # §3.6.7: "Forts also count as Casualties but return to
                    # Available immediately."
                    remove_piece(state, FORT_PAT, sid, 1, to="available")
                    removed += 1
                    remaining_loss -= loss_value(FORT_PAT)
                    removed_cube_or_fort = True

        return removed, removed_cube_or_fort

    pieces_def_lost, def_lost_cube_or_fort = _remove(def_side, defender_loss)
    pieces_att_lost, att_lost_cube_or_fort = _remove(att_side, attacker_loss)

    # -- Win-the-Day support shift (S3.6.8) --
    def _shift(winner: str, loser_removed: int, loser_lost_cube_or_fort: bool):
        if sid == WEST_INDIES_ID:
            return
        if loser_removed < 2 or not loser_lost_cube_or_fort:
            return

        shifts = min(3, loser_removed // 2)
        if winner == "REBELLION":
            if leader_location(state, "LEADER_WASHINGTON") == sid:
                shifts = min(6, shifts * 2)

        if shifts == 0:
            return

        remaining = _apply_shifts_to(state, sid, winner, shifts)

        # §3.6.8: "If all shifts are not possible in the Battle space,
        # British (if Royalist winner) or Patriots (if Rebellion winner)
        # may use remaining shifts in adjacent spaces."
        if remaining > 0:
            adj_list = sorted(
                map_adj.adjacent_spaces(sid),
                key=lambda s: (map_adj.space_meta(s) or {}).get("population", 0),
                reverse=True,
            )
            for adj_sid in adj_list:
                if remaining <= 0:
                    break
                if adj_sid == WEST_INDIES_ID:
                    continue
                remaining = _apply_shifts_to(state, adj_sid, winner, remaining)

    # §3.6.8 Winner determination.
    # Check for elimination (excluding Underground pieces).
    def _side_alive(side: str) -> bool:
        if side == "ROYALIST":
            return (sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)
                    + sp.get(WARPARTY_A, 0) + sp.get(VILLAGE, 0)
                    + sp.get(FORT_BRI, 0)) > 0
        else:
            return (sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
                    + sp.get(MILITIA_A, 0) + sp.get(FORT_PAT, 0)) > 0

    att_alive = _side_alive(att_side)
    def_alive = _side_alive(def_side)

    winner = None
    if not att_alive and not def_alive:
        # §3.6.8: "If both sides are eliminated … there is no winner or loser."
        winner = None
    elif not att_alive:
        winner = def_side
    elif not def_alive:
        winner = att_side
    elif pieces_att_lost < pieces_def_lost:
        # Attacker lost fewer → attacker wins
        winner = att_side
    elif pieces_def_lost < pieces_att_lost:
        # Defender lost fewer → defender wins
        winner = def_side
    else:
        # §3.6.8: "Defender is the winner if equal."
        winner = def_side

    if winner:
        loser_removed = pieces_def_lost if winner == att_side else pieces_att_lost
        loser_lost_cube_or_fort = def_lost_cube_or_fort if winner == att_side else att_lost_cube_or_fort
        _shift(winner, loser_removed, loser_lost_cube_or_fort)

    # -- Log --
    msg = (
        f"BATTLE {sid}: "
        f"{att_side}-loss={pieces_att_lost}, "
        f"{def_side}-loss={pieces_def_lost}, "
        f"winner={winner or 'NONE'}"
    )
    push_history(state, msg)
    return winner
