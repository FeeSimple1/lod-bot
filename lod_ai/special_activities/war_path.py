"""
lod_ai.special_activities.war_path
==================================
Indian **War Path**  (§4.4.2).

* May accompany any Command.
* Eligible space: contains ≥ 1 Underground War-Party **and** at least
  one *Rebellion* piece (Patriot/French cube, Active Militia, Fort).
* Three mutually-exclusive options (choose with *option* arg):

    option 1  →  Activate 1 WP-U → WP-A, remove 1 Rebellion unit.
    option 2  →  Activate 2 WP-U → WP-A, remove *one* of them,
                 and remove 2 Rebellion units.
    option 3  →  If NO Rebellion cubes present:
                 Activate 2 WP-U → WP-A, remove one of them,
                 and remove 1 Patriot Fort.

All removed pieces go to casualties / pool per their type.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import (
    # Indian pieces
    WARPARTY_U, WARPARTY_A, VILLAGE,
    # Rebellion pieces
    REGULAR_PAT, REGULAR_FRE, MILITIA_A, MILITIA_U,
    FORT_PAT,
    # factions
    INDIANS,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece, flip_pieces
from lod_ai.leaders          import apply_leader_modifiers, leader_location

REB_CUBE_TAGS = (MILITIA_A, MILITIA_U, REGULAR_PAT, REGULAR_FRE)

SA_NAME = "WAR_PATH"       # auto-registered by special_activities/__init__.py


# ---------------------------------------------------------------------------
# helper utilities
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    space_id: str,
    *,
    option: int = 1,        # 1, 2, or 3
) -> Dict:

    if faction != INDIANS:
        raise ValueError("War Path is Indian-only.")

    if option not in (1, 2, 3):
        raise ValueError("option must be 1, 2, or 3.")

    state["_turn_used_special"] = True
    ctx = apply_leader_modifiers(state, faction, "pre_war_path", ctx)
    sp = state["spaces"][space_id]

    if sp.get(WARPARTY_U, 0) == 0:
        raise ValueError("War Path needs an Underground War-Party.")

    rebel_units = sum(sp.get(t, 0) for t in REB_CUBE_TAGS)
    if option in (1, 2) and rebel_units == 0:
        raise ValueError("Options 1/2 require Rebellion units (cubes/Militia) present.")
    if option != 3 and rebel_units == 0 and sp.get(FORT_PAT, 0) == 0:
        raise ValueError("No Rebellion pieces here for War Path.")

    if option == 3 and rebel_units > 0:
        raise ValueError("Option 3 only when no Rebellion units are present.")
    if option == 3 and sp.get(FORT_PAT, 0) == 0:
        raise ValueError("Option 3 requires a Patriot Fort present.")

    push_history(state, f"INDIANS WAR_PATH begins in {space_id} (opt {option})")

    # ---- execute chosen option ---------------------------------------------
    if option == 1:
        # flip 1 WP-U → WP-A
        flip_pieces(state, WARPARTY_U, WARPARTY_A, space_id, 1)

        # remove 1 Rebellion unit (§4.4.2: cubes and Forts → Casualties;
        # Militia are not cubes → Available; Forts handled by option 3 only)
        _REB_UNIT_TAGS = (REGULAR_PAT, REGULAR_FRE, MILITIA_A, MILITIA_U)
        for tag in _REB_UNIT_TAGS:
            if sp.get(tag, 0):
                box = "casualties" if tag in (REGULAR_PAT, REGULAR_FRE) else "available"
                remove_piece(state, tag, space_id, 1, to=box)
                break

    elif option == 2:
        # flip 2 WP-U → WP-A
        flip_pieces(state, WARPARTY_U, WARPARTY_A, space_id, 2)

        # remove one of the freshly-activated WP-A to Available
        remove_piece(state, WARPARTY_A, space_id, 1, to="available")

        # remove 2 Rebellion units (cubes → Casualties, Militia → Available)
        removed = 0
        _REB_UNIT_TAGS = (REGULAR_PAT, REGULAR_FRE, MILITIA_A, MILITIA_U)
        for tag in _REB_UNIT_TAGS:
            while sp.get(tag, 0) and removed < 2:
                box = "casualties" if tag in (REGULAR_PAT, REGULAR_FRE) else "available"
                remove_piece(state, tag, space_id, 1, to=box)
                removed += 1

    else:   # option 3
        # flip 2 WP-U → WP-A
        flip_pieces(state, WARPARTY_U, WARPARTY_A, space_id, 2)

        remove_piece(state, WARPARTY_A, space_id, 1, to="available")
        # §4.4.2: "cubes and Forts are removed to Casualties"
        remove_piece(state, FORT_PAT,        space_id, 1, to="casualties")

    # Brant capability (leader_capabilities.txt):
    # "War Path removes 1 additional Militia in the space."
    brant_here = leader_location(state, "LEADER_BRANT") == space_id
    extra_militia = ctx.get("war_path_extra_militia", 0)
    if brant_here:
        extra_militia += 1

    removed_bonus = 0
    while extra_militia and (sp.get(MILITIA_A, 0) or sp.get(MILITIA_U, 0)):
        # Militia are not cubes → Available
        if sp.get(MILITIA_A, 0):
            remove_piece(state, MILITIA_A, space_id, 1, to="available")
        else:
            remove_piece(state, MILITIA_U, space_id, 1, to="available")
        extra_militia -= 1
        removed_bonus += 1

    if brant_here and removed_bonus:
        push_history(state, "Brant present - War Path removes an additional Militia.")

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"INDIANS WAR_PATH {space_id} opt {option}"
    )
    return ctx
