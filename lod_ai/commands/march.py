"""
lod_ai.commands.march
=====================
Implements the March Command for every faction:

• BRITISH  (§3.2.3)
• PATRIOTS (§3.3.2)
• INDIANS  (§3.4.2)
• FRENCH   (§3.5.4 — Treaty-gated)

Common-Cause integration
------------------------
When `ctx["common_cause"]` is present (set by the Special-Activity
lod_ai.special_activities.common_cause), British may treat the recorded
number of War Parties in each space *as if they were Tories* for the
escort rule. These War Parties:

    • Count toward the 1-for-1 escort cap with Regulars.
    • May **not** move into a City (rule §4.2.1).
    • Arrive Active (WARPARTY_A).

Everything else remains deterministic: resource costs, adjacency
validation, history push, and global-cap checks.
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.rules_consts import (
    # cube tags
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY, MILITIA_A, MILITIA_U,
    WARPARTY_A, WARPARTY_U,
    INDIANS,
)
from lod_ai.util.history     import push_history
from lod_ai.util.caps        import refresh_control, enforce_global_caps
from lod_ai.util.adjacency   import is_adjacent
from lod_ai.map import adjacency as map_adj
from lod_ai.leaders          import apply_leader_modifiers
from lod_ai.board.pieces      import remove_piece, add_piece          # NEW
from lod_ai.economy.resources import spend, can_afford               # NEW

COMMAND_NAME = "MARCH"            # auto-registered by commands/__init__.py


# ──────────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────────
def _pay_cost(state: Dict, faction: str, n: int, first_free: bool = False) -> None:
    cost = n - (1 if first_free else 0)
    spend(state, faction, cost)

def _move(state: Dict,
          tag: str, n: int,
          src_id: str, dst_id: str) -> None:
    remove_piece(state, tag, src_id, n)
    add_piece(state,    tag, dst_id, n)

def _is_city(space_id: str) -> bool:
    return map_adj.space_type(space_id) == "City"


# ──────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    sources: List[str],
    destinations: List[str],
    *,
    bring_escorts: bool = False,
    limited: bool = False,
) -> Dict:
    """
    Perform a March.

    Parameters
    ----------
    sources / destinations
        List of source spaces and destination spaces.  If *limited*,
        exactly 1 source and 1 (matching) destination is required.
    bring_escorts
        If True, British/French may escort Tories/Continentals
        (plus Common-Cause WP for British) 1-for-1 with Regulars.
    """
    # Treaty gate for French
    if faction == "FRENCH" and not state.get("toa_played"):
        raise ValueError("FRENCH cannot March before Treaty of Alliance.")

    # Limited-command constraints
    if limited:
        if len(set(destinations)) != 1 or len(destinations) != 1:
            raise ValueError("Limited March must end in a single destination.")
        if len(sources) != 1:
            raise ValueError("Limited March must originate from one space.")

    state["_turn_command"] = COMMAND_NAME
    state.setdefault("_turn_affected_spaces", set()).update(destinations)
    # Resource payment
    first_free = (faction == "INDIANS") and ctx.get("all_reserve_origin", False)
    _pay_cost(state, faction, len(destinations), first_free=first_free)

    # Escort ally-fee: French escorting Continentals → Patriots pay the fee
    if faction == "FRENCH" and bring_escorts:
        fee = len(destinations)
        spend(state, "PATRIOTS", fee)

    # Leader hooks (placeholder for future modifiers)
    ctx = apply_leader_modifiers(state, faction, "pre_march", ctx)

    push_history(
        state,
        f"{faction} MARCH begins: {sources} ➜ {destinations} (escorts={bring_escorts})"
    )

    for src in sources:
        sp_src = state["spaces"][src]

        for dst in destinations:
            if not is_adjacent(src, dst):
                raise ValueError(f"{src} is not adjacent to {dst}.")
            sp_dst = state["spaces"][dst]

            if faction == INDIANS and _is_city(dst):
                raise ValueError("Indians cannot occupy a City space.")

            if faction == "BRITISH":
                # ── Move Regulars ───────────────────────────────────────────
                reg = sp_src.get(REGULAR_BRI, 0)
                if reg == 0:
                    continue
                _move(state, REGULAR_BRI, reg, src, dst)

                # ── Escorts: first Tories, then Common-Cause WP ───────────
                if bring_escorts:
                    # Calculate availability
                    tory_avail = sp_src.get(TORY, 0)
                    cc_avail   = ctx.get("common_cause", {}).get(src, 0)
                    max_escort = reg

                    tory_take = min(tory_avail, max_escort)
                    wp_take   = min(cc_avail, max_escort - tory_take)

                    # WP may not enter a City
                    if wp_take and _is_city(dst):
                        raise ValueError("Common-Cause War Parties may not move into Cities.")

                    if tory_take:
                        _move(state, TORY, tory_take, src, dst)
                    if wp_take:
                        _move(state, WARPARTY_A, wp_take, src, dst)
                else:
                    tory_take = 0
                    wp_take = 0

                # Activate one Militia-U per three cubes moved into a Colony
                if sp_dst.get("type") == "Colony":
                    moved_total = reg + tory_take + wp_take
                    flip = min(moved_total // 3, sp_dst.get(MILITIA_U, 0))
                    if flip:
                        sp_dst[MILITIA_U] -= flip
                        sp_dst[MILITIA_A] = sp_dst.get(MILITIA_A, 0) + flip

            elif faction == "PATRIOTS":
                # ── Move Continentals ──────────────────────────────────────
                reg = sp_src.get(REGULAR_PAT, 0)
                if reg:
                    _move(state, REGULAR_PAT, reg, src, dst)

                # ── Move Militia (all) ─────────────────────────────────────
                mil_u = sp_src.pop(MILITIA_U, 0)
                mil_a = sp_src.pop(MILITIA_A, 0)
                if mil_u or mil_a:
                    sp_dst[MILITIA_A] = sp_dst.get(MILITIA_A, 0) + mil_u + mil_a

                # ── French escort 1-for-1 with Regulars ───────────────────
                if bring_escorts:
                    fr_take = min(reg, sp_src.get(REGULAR_FRE, 0))
                    if fr_take:
                        _move(state, REGULAR_FRE, fr_take, src, dst)

                # War Parties moving with Patriots become Active on arrival
                if sp_src.get(WARPARTY_U, 0) or sp_src.get(WARPARTY_A, 0):
                    wp_u = sp_src.pop(WARPARTY_U, 0)
                    wp_a = sp_src.pop(WARPARTY_A, 0)
                    total_wp = wp_u + wp_a
                    if total_wp:
                        sp_dst[WARPARTY_A] = sp_dst.get(WARPARTY_A, 0) + total_wp

                # Militia obey stacking and city restrictions via enforce_global_caps

            elif faction == "INDIANS":
                # ── Move War Parties (all) and flip Active ────────────────
                wp_u = sp_src.pop(WARPARTY_U, 0)
                wp_a = sp_src.pop(WARPARTY_A, 0)
                total = wp_u + wp_a
                if total:
                    sp_dst[WARPARTY_A] = sp_dst.get(WARPARTY_A, 0) + total
                # City control from Indian pieces handled by refresh_control

            elif faction == "FRENCH":
                # ── Move French Regulars ───────────────────────────────────
                reg = sp_src.get(REGULAR_FRE, 0)
                if reg == 0:
                    continue
                _move(state, REGULAR_FRE, reg, src, dst)

                # ── Continental escort 1-for-1 ────────────────────────────
                if bring_escorts:
                    pat_take = min(reg, sp_src.get(REGULAR_PAT, 0))
                    if pat_take:
                        _move(state, REGULAR_PAT, pat_take, src, dst)

    refresh_control(state)
    enforce_global_caps(state)

    # Log summary
    state.setdefault("log", []).append(
        f"{faction} MARCH {sources} ➜ {destinations} (escorts={bring_escorts})"
    )
    return ctx
