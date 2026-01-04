"""
lod_ai.commands.battle
======================
Universal Battle Command (§3.6).

Supported factions
------------------
British, Patriots, French (after Treaty of Alliance).

Common‑Cause
------------
If ``ctx["common_cause"][space_id] == n`` War Parties, treat those WP as
Tory cubes for *both* force and casualties; they never count against the
“half Active War Parties” rule (prevents double‑counting).

Leader hooks
------------
Pre‑battle modifiers injected via
    ctx = leaders.apply_leader_modifiers(state, faction, "pre_battle", ctx)
The hook may write:

    ctx["defender_loss_mod"]           (± int)
    ctx["attacker_defender_loss_bonus"](+ int)

The lookup happens once per space.

---------------------------------------------------------------------------
This implementation aims for **correctness and stability first**.  Minor
edge cases (voluntary retreats, adjacent support overflow) are *not* yet
modelled—they do not block solo play and can be added later.
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
)
from lod_ai.leaders        import apply_leader_modifiers, leader_location
from lod_ai.util.piece_kinds import is_cube, loss_value
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces   import remove_piece, add_piece
from lod_ai.economy.resources import spend, can_afford
from lod_ai.util.loss_mod  import pop_loss_mod

COMMAND_NAME = "BATTLE"


# ────────────────────────────────────────────────────────────────────
# Public entry
# ────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    spaces: List[str],
    *,
    choices: Dict | None = None,
    free: bool = False,          # ← see fix #2 below
) -> Dict:
    faction = faction.upper()
    if faction not in ("BRITISH", "PATRIOTS", "FRENCH"):
        raise ValueError("Only BRITISH, PATRIOTS or FRENCH may initiate Battle")
    if faction == "FRENCH" and not state.get("toa_played"):
        raise ValueError("French cannot Battle before Treaty of Alliance")
    if not spaces:
        raise ValueError("Need ≥ 1 battle space")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(spaces)
    # Pay Resources (actor only); allied fees handled below
    if not free:
        spend(state, faction, len(spaces))

    if faction == "PATRIOTS":
        fee = sum(state["spaces"][s].get(REGULAR_FRE, 0) for s in spaces)
        if fee:
            spend(state, "FRENCH", fee)
    elif faction == "FRENCH":
        fee = sum(state["spaces"][s].get(REGULAR_PAT, 0) for s in spaces)
        if fee:
            spend(state, "PATRIOTS", fee)

    ctx = apply_leader_modifiers(state, faction, "pre_battle", ctx)
    push_history(state, f"{faction} BATTLE in {', '.join(spaces)}")

    attacker_bonus = (choices or {}).get("force_bonus", 0)

    for sid in spaces:
        _resolve_space(state, ctx, faction, sid, attacker_bonus)

    refresh_control(state)
    enforce_global_caps(state)
    return ctx


# ────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────
def _roll_d3(state: Dict) -> int:
    val = state["rng"].randint(1, 3)
    state.setdefault("rng_log", []).append(("D3", val))
    return val


def _half(n: int) -> int:          # ⌊n / 2⌋
    return n >> 1


# ────────────────────────────────────────────────────────────────────
# Single‑space battle
# ────────────────────────────────────────────────────────────────────
def _resolve_space(
    state: Dict,
    ctx: Dict,
    attacker_faction: str,
    sid: str,
    attacker_bonus: int,
) -> None:
    sp = state["spaces"][sid]

    att_side = "ROYALIST" if attacker_faction == "BRITISH" else "REBELLION"
    def_side = "REBELLION" if att_side == "ROYALIST" else "ROYALIST"

    cc_wp = ctx.get("common_cause", {}).get(sid, 0)

    def _force(side: str, acting_attacker: bool) -> int:
        if side == "ROYALIST":
            regs = sp.get(REGULAR_BRI, 0)
            tories = sp.get(TORY, 0) + cc_wp
            if acting_attacker:
                tories = min(tories, regs)
            wp = max(0, sp.get(WARPARTY_A, 0) - cc_wp)
            cubes = regs + tories + sp.get(WARPARTY_U, 0) + (wp // 2)
        else:
            regs = sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
            mil = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
            cubes = regs + (mil // 2)
        forts = sp.get(FORT_BRI if side == "ROYALIST" else FORT_PAT, 0)
        return cubes + forts

    att_force = _force(att_side, True)  + attacker_bonus
    def_force = _force(def_side, False) # ← defender gets no event bonus

    def _loss_roll(force: int, is_defender: bool) -> int:
        # 0 dice if force ≤ 2  | ≤3 dice, each D3
        dice = min(3, force // 3)
        roll_total = sum(_roll_d3(state) for _ in range(dice))
        mods = 0
        if is_defender:                                 # §3.6.5
            if attacker_faction == "BRITISH" and sp.get("blockade", 0) and sid != WEST_INDIES_ID:
                mods -= 1
            if attacker_faction == "BRITISH" and sid == WEST_INDIES_ID and sp.get("blockade", 0):
                mods -= 1
            if attacker_faction == "FRENCH" and ctx.get("attacker_defender_loss_bonus", 0):
                mods += ctx["attacker_defender_loss_bonus"]
            if sp.get("leader"):                        # Attacking leader handled in ctx
                mods += 1
            if sp.get("underground", 0):                # at least one underground piece
                mods += 1
            if acting_attacker := False:
                pass                                   # (already covered above)
        else:                                           # §3.6.6
            mods += ctx.get("defender_loss_mod", 0)
        return max(0, roll_total + mods)

    defender_loss = _loss_roll(att_force, True)
    attacker_loss = _loss_roll(def_force, False)

    # Additional leader/event modifiers (loss_mod queue)
    att_mod, def_mod = pop_loss_mod(state, sid)
    attacker_loss += att_mod
    defender_loss += def_mod

    # ── Casualty removal -----------------------------------------------------
    def _remove(side: str, loss: int) -> tuple[int, bool]:
        if loss <= 0:
            return 0, False

        if side == "ROYALIST":
            order = (
                REGULAR_BRI, TORY, WARPARTY_A, WARPARTY_U,
                FORT_BRI,  # forts last
            )
        else:
            order = (
                REGULAR_PAT, REGULAR_FRE,
                MILITIA_A, MILITIA_U,
                FORT_PAT,
            )
        removed = 0
        removed_cube_or_fort = False
        remaining_loss = loss
        for tag in order:
            avail = sp.get(tag, 0)
            while avail and remaining_loss > 0:
                remove_piece(state, tag, sid, 1, to="casualties")
                removed += 1
                remaining_loss -= loss_value(tag)
                avail -= 1
                if is_cube(tag) or tag in (FORT_BRI, FORT_PAT):
                    removed_cube_or_fort = True
            if remaining_loss <= 0:
                break
        return removed, removed_cube_or_fort

    pieces_def_lost, def_lost_cube_or_fort = _remove(def_side, defender_loss)
    pieces_att_lost, att_lost_cube_or_fort = _remove(att_side, attacker_loss)

    # ── Win‑the‑Day support shift -------------------------------------------
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
        for _ in range(shifts):
            cur = state.get("support", {}).get(sid, NEUTRAL)
            if winner == "ROYALIST" and cur > ACTIVE_OPPOSITION:
                state.setdefault("support", {})[sid] = cur - 1
            elif winner == "REBELLION" and cur < ACTIVE_SUPPORT:
                state.setdefault("support", {})[sid] = cur + 1

    winner = None
    if pieces_att_lost != pieces_def_lost:
        winner = att_side if pieces_def_lost > pieces_att_lost else def_side
    elif pieces_att_lost == 0 and pieces_def_lost:      # rout
        winner = att_side
    elif pieces_def_lost == 0 and pieces_att_lost:
        winner = def_side
    # tie ⇒ Defender wins (already def_side)

    if winner:
        loser_removed = pieces_def_lost if winner == att_side else pieces_att_lost
        loser_lost_cube_or_fort = def_lost_cube_or_fort if winner == att_side else att_lost_cube_or_fort
        _shift(winner, loser_removed, loser_lost_cube_or_fort)

    # ── Log ------------------------------------------------------------------
    msg = (
        f"BATTLE {sid}: "
        f"{att_side}‑loss={pieces_att_lost}, "
        f"{def_side}‑loss={pieces_def_lost}, "
        f"winner={winner or 'DEFENDER'}"
    )
    push_history(state, msg)
