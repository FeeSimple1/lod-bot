"""
lod_ai.commands.scout
=====================
Indian **Scout** Command  (§3.4.3).

* **Faction** : INDIANS only.
* **Cost**    : Indians pay 1 Resource **and** British pay 1 Resource.
* **From**    : One *Province* (not City) containing ≥ 1 War Party **and**
                ≥ 1 British Regular.
* **To**      : One adjacent *Province* (not City).  All chosen pieces move
                together as a single group.

Pieces that may move (Indian choice):
    • ≥ 1 War Party  (all moving WP become **Active** on arrival)
    • ≥ 1 British Regular (mandatory)
    • Up to the same number of Tory cubes as Regulars (optional)

After movement:
    • Flip **all** Militia in the destination space to Active.
    • Indians may, at their option, immediately Skirmish there using the
      British Regulars via the Skirmish Special Activity.

This module enforces adjacency, province-only restriction, piece counts,
resource payments, and global caps.  Randomness is not used.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import (
    # piece tags
    WARPARTY_U, WARPARTY_A,
    REGULAR_BRI, TORY,
    MILITIA_U, MILITIA_A,
)
from lod_ai.util.history import push_history
from lod_ai.util.caps import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.board.pieces      import remove_piece, add_piece        # NEW
from lod_ai.economy.resources import spend                          # NEW

COMMAND_NAME = "SCOUT"          # auto-registered by commands/__init__.py


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _is_city(space: Dict) -> bool:
    """Return True if the map space is a City (heuristic)."""
    return space.get("city", False) or space.get("type") == "City"


def _move(state: Dict, tag: str, n: int, src_id: str, dst_id: str) -> None:
    """Move *n* pieces of *tag* from src_id → dst_id via gate-keepers."""
    remove_piece(state, tag, src_id, n)
    add_piece(state,    tag, dst_id, n)

# --------------------------------------------------------------------------- #
# Public entry                                                                
# --------------------------------------------------------------------------- #
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    src: str,
    dst: str,
    *,
    n_warparties: int,
    n_regulars: int,
    n_tories: int = 0,
    skirmish: bool = False,
) -> Dict:
    """
    Perform the Scout Command.

    Parameters
    ----------
    src, dst
        Province IDs (src → dst must be adjacent; both must *not* be Cities).
    n_warparties
        Number of War Parties to move (≥ 1).
    n_regulars
        Number of British Regulars to move (≥ 1).
    n_tories
        Number of Tory cubes to move (0 … n_regulars).
    skirmish
        If True, immediately Skirmish in *dst* after movement using
        the British Regulars that moved.
    """
    if faction != "INDIANS":
        raise ValueError("Only INDIANS may execute the Scout command.")

    # -------- Basic spatial checks ------------------------------------------
    if _is_city(state["spaces"][src]):  raise ValueError("Source must be a Province.")
    if _is_city(state["spaces"][dst]):  raise ValueError("Destination must be a Province.")
    if not is_adjacent(src, dst):
        raise ValueError(f"{src} is not adjacent to {dst}.")

    sp_src = state["spaces"][src]
    sp_dst = state["spaces"][dst]

    # -------- Piece availability checks -------------------------------------
    if n_warparties < 1 or n_regulars < 1:
        raise ValueError("Must move at least 1 War Party and 1 British Regular.")
    if n_tories > n_regulars:
        raise ValueError("Tories moved may not exceed number of Regulars.")

    def _avail(tag): return sp_src.get(tag, 0)

    if n_warparties > (_avail(WARPARTY_U) + _avail(WARPARTY_A)):
        raise ValueError(f"Not enough War Parties in {src}.")
    if n_regulars > _avail(REGULAR_BRI):
        raise ValueError(f"Not enough British Regulars in {src}.")
    if n_tories   > _avail(TORY):
        raise ValueError(f"Not enough Tories in {src}.")

    # -------- Resource payments ---------------------------------------------
    spend(state, "INDIANS", 1)
    spend(state, "BRITISH", 1)

    # -------- Execute move ---------------------------------------------------
    push_history(state, f"INDIANS SCOUT {src} → {dst}")

    # War Parties: prefer Underground first, all arrive Active
    wp_to_move = n_warparties
    take_u = min(wp_to_move, sp_src.get(WARPARTY_U, 0))
    if take_u:
        _move(state, WARPARTY_U, take_u, src, dst)    # still Underground for a moment
        wp_to_move -= take_u
    if wp_to_move:
        _move(state, WARPARTY_A, wp_to_move, src, dst)  # already Active
    # Now flip ALL moved WP Active
    sp_dst[WARPARTY_A] = sp_dst.get(WARPARTY_A, 0) + n_warparties
    sp_dst[WARPARTY_U] = sp_dst.get(WARPARTY_U, 0) - take_u  # remove leftovers Underground

    # British pieces
    _move(state, REGULAR_BRI, n_regulars, src, dst)
    if n_tories:
        _move(state, TORY, n_tories, src, dst)

    # Flip all Militia in destination Active
    mil_u = sp_dst.pop(MILITIA_U, 0)
    if mil_u:
        sp_dst[MILITIA_A] = sp_dst.get(MILITIA_A, 0) + mil_u

    # -------- Optional Skirmish ---------------------------------------------
    if skirmish:
        from lod_ai.special_activities import skirmish as sa_skirmish
        ctx = sa_skirmish.execute(state, "BRITISH", ctx, dst)

    # -------- Final housekeeping --------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"INDIANS SCOUT {src} ➜ {dst}  "
        f"WP={n_warparties}, REG={n_regulars}, TORY={n_tories}"
    )
    return ctx
