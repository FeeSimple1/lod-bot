"""
lod_ai.special_activities.partisans
===================================
Patriot-only Partisans SA  (§4.3.2).

* May accompany **any** Command except if the chosen space is already a
  Battle space chosen for this card sequence.
* Eligible space: contains ≥1 Underground Militia **and** any Royalist
  pieces (British cubes/Tories, Active War Parties, Villages, Forts, …).

Options (choose exactly one):
  ─ option=1  →  Activate 1 Underground Militia; remove 1 Royalist unit.
  ─ option=2  →  Activate 2 Underground Militia; remove **one** of them
                 (i.e., 1 Militia casualty) *and* remove 2 Royalist units.
  ─ option=3  →  If **no War Parties** present: Activate 2 Underground
                 Militia; remove one of them *and* remove 1 Village.

§4.3.2 parenthetical: "cubes are removed to Casualties" — only cubes
(REGULAR_BRI, TORY) go to Casualties; all other pieces (War Parties,
Villages, Forts, Militia) go to Available.
"""

from __future__ import annotations
from typing import Dict

from lod_ai.rules_consts import (
    REGULAR_BRI, TORY,
    WARPARTY_A, WARPARTY_U,
    VILLAGE, MILITIA_U, MILITIA_A, FORT_BRI,
    PATRIOTS,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.board.pieces      import remove_piece, add_piece, flip_pieces

SA_NAME = "PARTISANS"      # auto-registered by special_activities/__init__.py


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
ROYALIST_TAGS = (
    REGULAR_BRI, TORY, WARPARTY_A, WARPARTY_U, VILLAGE, FORT_BRI
)

# §4.3.2: "cubes are removed to Casualties" — only cubes.
_CUBE_TAGS = frozenset((REGULAR_BRI, TORY))

# Glossary §1.4: units = Regulars, Tories, War Parties (not Forts or
# Villages).  Options 1/2 may remove only these.
_UNIT_TAGS = (TORY, WARPARTY_A, REGULAR_BRI, WARPARTY_U)


def _removal_dest(tag: str) -> str:
    """Return 'casualties' for cubes, 'available' for everything else."""
    return "casualties" if tag in _CUBE_TAGS else "available"


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------
def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    space_id: str,
    *,
    option: int = 1,          # 1, 2, or 3 (see docstring)
) -> Dict:

    if faction != PATRIOTS:
        raise ValueError("Partisans is a Patriot-only Special Activity.")

    if option not in (1, 2, 3):
        raise ValueError("option must be 1, 2, or 3.")

    # §4.3.2: Partisans "may accompany any Command but not in a Battle
    # space".  Battle spaces for the current turn are recorded by
    # battle.execute.  EXEMPT card-granted free ops and Brilliant Stroke
    # actions (bs_free): §5.1.1 Event text takes precedence (e.g. card
    # 15 scripts free March → free Battle → "then Partisans THERE"), and
    # §2.3.8 BS actions are "not limited by other actions on this card"
    # (Session 51 — the S47 enforcement broke card 15's own sequence,
    # gate 1778:14).
    if (space_id in state.get("_turn_battle_spaces", set())
            and not state.get("bs_free")):
        raise ValueError(f"Partisans cannot occur in Battle space {space_id}.")

    state["_turn_used_special"] = True
    state["_turn_special_type"] = "PARTISANS"  # coverage (Piece 5, S67)
    sp = state["spaces"][space_id]

    if sp.get(MILITIA_U, 0) == 0:
        raise ValueError("Partisans requires at least one Underground Militia.")
    if option in (2, 3) and sp.get(MILITIA_U, 0) < 2:
        raise ValueError("Options 2/3 require at least two Underground Militia (§4.3.2).")

    roy_pieces = sum(sp.get(tag, 0) for tag in ROYALIST_TAGS)
    if roy_pieces == 0:
        raise ValueError("No Royalist pieces present for Partisans strike.")

    # §4.3.2 options 1/2 remove Royalist UNITS — Glossary §1.4: "Units:
    # Regulars, Tories, War Parties, Continentals and Militia but not
    # Forts or Villages."  (Session 45: options 1/2 could previously
    # remove a Village or Fort.)
    roy_units = sum(sp.get(tag, 0) for tag in _UNIT_TAGS)
    if option in (1, 2) and roy_units == 0:
        raise ValueError(
            "Options 1/2 remove a Royalist unit; none present (§4.3.2).")

    wp_present = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0) > 0
    if option == 3 and wp_present:
        raise ValueError("Option 3 only if no War Parties are present.")

    push_history(state, f"PATRIOTS PARTISANS begins in {space_id} (opt {option})")

    # ---- Perform chosen option ---------------------------------------------
    if option == 1:
        # Activate 1 Militia U → A
        flip_pieces(state, MILITIA_U, MILITIA_A, space_id, 1)
        # Remove 1 Royalist unit (cubes → Casualties, others → Available)
        for tag in _UNIT_TAGS:
            if sp.get(tag, 0):
                remove_piece(state, tag, space_id, 1, to=_removal_dest(tag))
                break

    elif option == 2:
        # Activate 2 Militia U → A
        flip_pieces(state, MILITIA_U, MILITIA_A, space_id, 2)
        # Remove 1 of those Militia A (Militia not cubes → Available)
        remove_piece(state, MILITIA_A, space_id, 1, to="available")
        # Remove 2 Royalist units (cubes → Casualties, others → Available)
        removed = 0
        for tag in _UNIT_TAGS:
            while sp.get(tag, 0) and removed < 2:
                remove_piece(state, tag, space_id, 1, to=_removal_dest(tag))
                removed += 1

    else:  # option 3
        # Activate 2 Militia U → A
        flip_pieces(state, MILITIA_U, MILITIA_A, space_id, 2)

        # Remove 1 of those newly-activated Militia A (Militia not cubes → Available)
        remove_piece(state, MILITIA_A, space_id, 1, to="available")

        # Remove 1 Village
        if sp.get(VILLAGE, 0) == 0:
            raise ValueError("Option 3 requires a Village present.")
        remove_piece(state, VILLAGE, space_id, 1, to="available")

    refresh_control(state)
    enforce_global_caps(state)

    state.setdefault("log", []).append(f"PATRIOTS PARTISANS {space_id} opt {option}")
    return ctx
