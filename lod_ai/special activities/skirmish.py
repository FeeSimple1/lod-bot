"""
lod_ai.special_activities.skirmish
==================================
British (§4.2.2), Patriot (§4.3.3), and French (§4.5.2) Skirmish.

Call signature
--------------
execute(state, faction, ctx, space_id, *, option)
    • faction  : "BRITISH", "PATRIOTS", or "FRENCH"
    • space_id : map space where Skirmish occurs
    • option   : 1, 2, or 3  (see rules below)

Rule recap
----------
BRITISH  – need British Regulars + Rebellion cubes/Militia (or Fort for opt 3)
PATRIOTS – need Continentals + British pieces (or Fort for opt 3)
FRENCH   – Treaty gate; need French Regulars + British pieces (or Fort)

Options (mutually exclusive):
    1. Remove 1 enemy cube (or Active Militia)              [cost to self: 0]
    2. Remove 2 enemy cubes/Active Militia **and** 1 own Reg/Cont/FreReg
    3. If no enemy cubes present, remove 1 enemy Fort **and** 1 own Reg/Cont/FreReg
All removed cubes/Forts go to Casualties (Forts bounce to pool immediately).
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import (
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY, MILITIA_A, MILITIA_U,
    FORT_BRI, FORT_PAT,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import enforce_global_caps, refresh_control
from lod_ai.board.pieces      import remove_piece, add_piece
from lod_ai.leaders          import apply_leader_modifiers

SA_NAME = "SKIRMISH"          # auto-registered by special_activities/__init__.py


# ─────────────────────────────────────────────────────────────────────
# helper utilities
# ─────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────
# public entry
# ─────────────────────────────────────────────────────────────────────
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    space_id: str,
    *,
    option: int = 1,         # 1, 2, or 3 as per rules text
) -> Dict:

    if faction not in ("BRITISH", "PATRIOTS", "FRENCH"):
        raise ValueError("Skirmish available only to BRITISH, PATRIOTS, or FRENCH.")

    if faction == "FRENCH" and not state.get("toa_played"):
        raise ValueError("FRENCH cannot Skirmish before Treaty of Alliance.")

    if option not in (1, 2, 3):
        raise ValueError("option must be 1, 2, or 3.")

    ctx = apply_leader_modifiers(state, faction, "pre_skirmish", ctx)
    sp = state["spaces"][space_id]

    # Determine own and enemy tags per faction
    if faction == "BRITISH":
        own_tag = REGULAR_BRI
        enemy_cubes = [REGULAR_PAT, REGULAR_FRE, TORY]  # Tories never present on Rebellion side but harmless
        enemy_militia_tag = MILITIA_A
        enemy_fort_side_tag = FORT_PAT        # Patriot Fort counts
    elif faction == "PATRIOTS":
        own_tag = REGULAR_PAT
        enemy_cubes = [REGULAR_BRI, TORY]
        enemy_militia_tag = None          # Militia not relevant to British side
        enemy_fort_side_tag = FORT_BRI        # British Fort
    else:  # FRENCH
        own_tag = REGULAR_FRE
        enemy_cubes = [REGULAR_BRI, TORY]
        enemy_militia_tag = None
        enemy_fort_side_tag = FORT_BRI        # British Fort

    # Presence checks -------------------------------------------------
    if sp.get(own_tag, 0) == 0:
        raise ValueError(f"No {own_tag} present to conduct Skirmish.")

    enemy_cube_count = sum(sp.get(tag, 0) for tag in enemy_cubes)
    if enemy_militia_tag:
        enemy_cube_count += sp.get(enemy_militia_tag, 0)

    if option == 1 and enemy_cube_count == 0:
        raise ValueError("Option 1 requires at least one enemy cube/Active Militia.")
    if option == 2 and enemy_cube_count < 2:
        raise ValueError("Option 2 requires at least two enemy cubes/Active Militia.")
    if option == 3:
        if enemy_cube_count != 0:
            raise ValueError("Option 3 can be chosen only when no enemy cubes/Active Militia remain.")
        if sp.get(enemy_fort_side_tag, 0) == 0:
            raise ValueError("Option 3 requires an enemy Fort present.")

    # -----------------------------------------------------------------
    push_history(state, f"{faction} SKIRMISH begins in {space_id} (option {option})")

    # Execute chosen option ------------------------------------------
    if option == 1:
        # remove 1 enemy cube (pref Active Militia if relevant)
        if enemy_militia_tag and sp.get(enemy_militia_tag, 0):
            remove_piece(state, enemy_militia_tag, space_id, 1, to="available")
        else:
            # pick first available cube tag
            for tag in enemy_cubes:
                if sp.get(tag, 0):
                    remove_piece(state, tag, space_id, 1, to="casualties")
                    break

    elif option == 2:
        # remove 2 enemy cubes/Active Militia
        removed = 0
        while removed < 2:
            if enemy_militia_tag and sp.get(enemy_militia_tag, 0):
                remove_piece(state, enemy_militia_tag, space_id, 1, to="available")
            else:
                for tag in enemy_cubes:
                    if sp.get(tag, 0):
                        remove_piece(state, tag, space_id, 1, to="casualties")
                        break
            removed += 1
        # plus 1 own regular
        remove_piece(state, own_tag, space_id, 1, to="casualties")

    else:  # option == 3
        # remove Fort + 1 own regular
        remove_piece(state, enemy_fort_side_tag, space_id, 1, to="available")
        remove_piece(state, own_tag,           space_id, 1, to="casualties")

    extra_militia = ctx.get("skirmish_extra_militia", 0) if faction == "BRITISH" else 0
    while extra_militia and (sp.get(MILITIA_A, 0) or sp.get(MILITIA_U, 0)):
        if sp.get(MILITIA_A, 0):
            remove_piece(state, MILITIA_A, space_id, 1, to="available")
        else:
            remove_piece(state, MILITIA_U, space_id, 1, to="available")
        extra_militia -= 1
        push_history(state, "Clinton present - removed one additional Patriot Militia in Skirmish")

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"{faction} SKIRMISH {space_id} opt {option}"
    )
    return ctx
