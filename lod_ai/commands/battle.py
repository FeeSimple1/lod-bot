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
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces   import remove_piece, add_piece
from lod_ai.economy.resources import spend, can_afford
from lod_ai.leaders        import apply_leader_modifiers
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
    bonus: int,
) -> None:
    sp = state["spaces"][sid]

    att_side = "ROYALIST" if attacker_faction == "BRITISH" else "REBELLION"
    def_side = "REBELLION" if att_side == "ROYALIST" else "ROYALIST"

    # Common‑Cause War‑Parties loaned as Tory cubes
    cc_wp = ctx.get("common_cause", {}).get(sid, 0)

    # ── Force calc helper ----------------------------------------------------
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
            if attacker_faction == "BRITISH" and sp.get("blockade", 0) and sid != "West_Indies":
                mods -= 1
            if attacker_faction == "BRITISH" and sid == "West_Indies" and sp.get("blockade", 0):
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
    def _remove(side: str, loss: int) -> int:
        if loss <= 0:
            return 0

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
        for tag in order:
            avail = sp.get(tag, 0)
            if avail == 0:
                continue
            n = min(avail, loss - removed)
            remove_piece(state, tag, sid, n, to="casualties")
            removed += n
            if removed == loss:
                break
        return removed

    pieces_def_lost = _remove(def_side, defender_loss)
    pieces_att_lost = _remove(att_side, attacker_loss)

    # ── Win‑the‑Day support shift -------------------------------------------
    def _shift(winner: str, loser_removed: int):
        shifts = min(3, loser_removed // 2)
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

    if winner and sid != "West_Indies":
        loser_removed = pieces_def_lost if winner == att_side else pieces_att_lost
        _shift(winner, loser_removed)

    # ── Log ------------------------------------------------------------------
    msg = (
        f"BATTLE {sid}: "
        f"{att_side}‑loss={pieces_att_lost}, "
        f"{def_side}‑loss={pieces_def_lost}, "
        f"winner={winner or 'DEFENDER'}"
    )
    push_history(state, msg)
