"""
lod_ai.commands.battle
======================
Universal Battle Command scaffold covering
§3.2.4 (British), §3.3.3 (Patriots), §3.5.5 (French) and procedure §3.6.

Add-on: Common Cause
--------------------
When ctx["common_cause"][space_id] is present (set by the Common-Cause
Special Activity), those War Parties are counted as Tory cubes for *both*
attack and defence. They never count toward the “half Active War Parties”
rule, preventing double-counting.

TODO tags still mark advanced nuances (Washington double, Lauzun, etc.).
"""

from __future__ import annotations
from typing import Dict, List, Tuple

from lod_ai.rules_consts import (
    # Pieces
    REGULAR_BRI, TORY, REGULAR_FRE, REGULAR_PAT,
    MILITIA_A, MILITIA_U, WARPARTY_A, WARPARTY_U,
    VILLAGE, FORT_BRI, FORT_PAT,
    # Support indices
    ACTIVE_SUPPORT, PASSIVE_SUPPORT, NEUTRAL,
    PASSIVE_OPPOSITION, ACTIVE_OPPOSITION,
)
from lod_ai.util.history import push_history
from lod_ai.util.caps    import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece      # NEW
from lod_ai.economy.resources import spend, can_afford            # NEW

COMMAND_NAME = "BATTLE"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    spaces: List[str],
    *,
    choices: Dict | None = None,   # reserved for future manual overrides
) -> Dict:
    if faction not in ("BRITISH", "PATRIOTS", "FRENCH"):
        raise ValueError("Only BRITISH, PATRIOTS, or FRENCH may initiate Battle.")
    if faction == "FRENCH" and not state.get("toa_played"):
        raise ValueError("FRENCH cannot Battle before Treaty of Alliance.")
    if not spaces:
        raise ValueError("Must specify at least one Battle space.")

    # ── Resource costs ──────────────────────────────────────────────
    spend(state, faction, len(spaces))

    ally_fee = {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0}
    if faction == "PATRIOTS":
        ally_fee["FRENCH"] = sum(
            1 for s in spaces if state["spaces"][s].get(REGULAR_FRE, 0)
        )
    elif faction == "FRENCH":
        ally_fee["PATRIOTS"] = sum(
            1 for s in spaces if state["spaces"][s].get(REGULAR_PAT, 0)
        )
    for ally, fee in ally_fee.items():
        if fee:
            spend(state, ally, fee)

    push_history(
        state,
        f"{faction} BATTLE begins in {', '.join(spaces)}"
    )
    # Card bonus (e.g., Don Bernardo +2 Force) – ignored if choices is None
    force_bonus = (choices or {}).get("force_bonus", 0)

    # ── Resolve each space ─────────────────────────────────────────
    for space_id in spaces:
        _resolve_space(
            state,
            ctx,
            attacker_faction=faction,
            space_id=space_id,
            force_bonus=force_bonus,            # ← pass NEW argument
        )

    refresh_control(state)
    enforce_global_caps(state)
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _roll_d3(state: Dict) -> int:
    val = state["rng"].randint(1, 3)
    state.setdefault("rng_log", []).append(("D3", val))
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Single-space resolution (core §3.6 procedure)
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_space(state: Dict, ctx: Dict,
                   attacker_faction: str, space_id: str,
                   force_bonus: int = 0) -> None:
    sp = state["spaces"][space_id]

    # Identify sides
    att_side = "ROYALIST" if attacker_faction == "BRITISH" else "REBELLION"
    def_side = "REBELLION" if att_side == "ROYALIST" else "ROYALIST"

    # Common-Cause WP in this space (0 if key absent)
    cc_wp = ctx.get("common_cause", {}).get(space_id, 0)

    # ---- Force-level builder -----------------------------------------------
    def build_force(side: str, acting_attacker: bool) -> Dict:
        force = {"regulars": 0, "other": 0, "forts": 0}

        if side == "ROYALIST":
            force["regulars"] = sp.get(REGULAR_BRI, 0)

            # Tories include Common-Cause WP
            tory_total = sp.get(TORY, 0) + cc_wp
            if acting_attacker:
                tory_total = min(tory_total, force["regulars"])

            # Active WP *excluding* those loaned via Common Cause
            wp_active = max(0, sp.get(WARPARTY_A, 0) - cc_wp)
            militia_half = wp_active // 2

            force["other"] = tory_total if acting_attacker else militia_half
            if not acting_attacker:
                force["forts"] = sp.get(FORT_BRI, 0)

        else:  # REBELLION
            force["regulars"] = sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
            militia_half = sp.get(MILITIA_A, 0) // 2
            force["other"] = militia_half
            if not acting_attacker:
                force["forts"] = sp.get(FORT_PAT, 0)

        force["total"] = force["regulars"] + force["other"] + force["forts"]
        return force

    att_force = build_force(att_side, acting_attacker=True)
    def_force = build_force(def_side, acting_attacker=False)
    # Apply card-granted bonus (e.g., Don Bernardo +2 Force)
    if force_bonus:
        att_force["total"] += force_bonus
        push_history(
            state,
            f"{attacker_faction} gains +{force_bonus} Force in {space_id} (card bonus)"
        )

    # ---- Dice pools and base rolls ------------------------------------------
    def dice_and_roll(force: Dict) -> int:
        dice = min(3, force["total"] // 3)
        return sum(_roll_d3(state) for _ in range(dice)) if dice else 0

    att_roll = dice_and_roll(att_force)  # becomes Defender’s loss
    def_roll = dice_and_roll(def_force)  # becomes Attacker’s loss

    # ---- Basic modifiers (partial set) --------------------------------------
    def mods(acting_attacker: bool) -> int:
        m = 0
        force = att_force if acting_attacker else def_force

        # +1 if ≥½ cubes Regulars
        if force["regulars"] >= force["total"] / 2 and force["total"]:
            m += 1

        # +1 if at least one Underground piece on corresponding side
        if acting_attacker:
            if sp.get(WARPARTY_U, 0) + sp.get(MILITIA_U, 0) > 0:
                m += 1
        else:
            if sp.get(WARPARTY_U, 0) + sp.get(MILITIA_U, 0) > 0:
                m += 1

        # TODO: leaders, Fort ±, Squadron/Blockade, Washington, Lauzun…
        return m

    defender_loss = att_roll + mods(True)
    attacker_loss = def_roll + mods(False)

    from lod_ai.util.loss_mod import pop_loss_mod          # ← import inside fn

    att_mod, def_mod = pop_loss_mod(state, space_id)       # fetch first matching entry
    attacker_loss += att_mod
    defender_loss += def_mod
    attacker_loss = max(0, attacker_loss)                  # clamp to ≥0
    defender_loss = max(0, defender_loss)

    # ---- Removal priorities §3.6.7 ------------------------------------------
    def remove(side: str, loss: int) -> int:
        """
        Remove exactly <loss> combat pieces of <side> from this space
        and send them to the Casualties box.  Returns the number
        actually removed (should always equal <loss>).
        """
        if loss <= 0:
            return 0

        # priority order by side
        if side == "ROYALIST":
            tags = (REGULAR_BRI, TORY)
        else:  # "REBELLION"
            tags = (REGULAR_PAT, MILITIA_A, MILITIA_U)

        removed = 0
        for tag in tags:
            avail = sp.get(tag, 0)
            if avail == 0:
                continue

            n = min(loss - removed, avail)
            remove_piece(state, tag, space_id, n, to="casualties")
            removed += n

            if removed == loss:
                break

        return removed

    pieces_def_lost = remove(def_side, defender_loss)
    pieces_att_lost = remove(att_side, attacker_loss)

    # ---- Win-the-Day support shift (no adj overflow yet) --------------------
    def apply_shifts(winner: str, loser_removed: int) -> None:
        shifts = min(3, loser_removed // 2)
        for _ in range(shifts):
            if winner == "ROYALIST" and sp["support"] > ACTIVE_OPPOSITION:
                sp["support"] -= 1
            elif winner == "REBELLION" and sp["support"] < ACTIVE_SUPPORT:
                sp["support"] += 1

    winner = None
    if pieces_att_lost or pieces_def_lost:
        if pieces_att_lost == 0 and pieces_def_lost:
            winner = att_side
        elif pieces_def_lost == 0 and pieces_att_lost:
            winner = def_side
        else:
            if pieces_att_lost < pieces_def_lost:
                winner = att_side
            elif pieces_def_lost < pieces_att_lost:
                winner = def_side
            else:
                winner = def_side  # tie ⇒ Defender wins

    if winner and space_id != "West_Indies":
        loser_removed = pieces_def_lost if winner == att_side else pieces_att_lost
        apply_shifts(winner, loser_removed)

    # ---- Log -----------------------------------------------------------------
    state.setdefault("log", []).append(
        f"BATTLE {space_id}: "
        f"{att_side} lost {pieces_att_lost}, {def_side} lost {pieces_def_lost}, "
        f"winner={winner or 'none'}"
    )
