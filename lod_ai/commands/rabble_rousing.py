from __future__ import annotations
"""lod_ai.commands.rabble_rousing
==============================================================
Patriot **Rabble‑Rousing** Command implementation (§3.3.4, Aug‑2016 rules).

Only the *PATRIOTS* faction may execute this Command.  It costs **1 Resource
per selected space**, shifts Support 1 step toward Active Opposition, and—if
Propaganda markers are still available—adds one Propaganda marker (global cap
12).  If the space is *not* Rebellion‑controlled **with** a Patriot piece, the
Command also Activates **one** Underground Militia there.

This file keeps the logic deterministic and history‑logged so that test
replays are stable.  It depends only on the canonical constant names defined
in ``lod_ai.rules_consts``.
"""

from typing import Dict, List

from lod_ai.rules_consts import (
    # Support track enums (ordered Low→High Opposition)
    ACTIVE_SUPPORT,
    PASSIVE_SUPPORT,
    NEUTRAL,
    PASSIVE_OPPOSITION,
    ACTIVE_OPPOSITION,
    # Piece tags
    REGULAR_PAT,
    MILITIA_A,
    MILITIA_U,
    FORT_PAT,
    # Marker
    PROPAGANDA,
)

from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent  # potentially used by callers
from lod_ai.board.pieces      import remove_piece, add_piece
from lod_ai.economy.resources import spend

COMMAND_NAME = "RABBLE_ROUSING"  # auto‑registered by commands/__init__.py

# Order matters: index==support level on the track
_SUPPORT_ORDER = [
    ACTIVE_SUPPORT,
    PASSIVE_SUPPORT,
    NEUTRAL,
    PASSIVE_OPPOSITION,
    ACTIVE_OPPOSITION,
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pay_cost(state: Dict, n_spaces: int):
    spend(state, "PATRIOTS", n_spaces)


def _shift_toward_active_opposition(state: Dict, space_id: str):
    """Move support marker one step toward *Active Opposition*."""
    cur = state.get("support", {}).get(space_id, NEUTRAL)
    try:
        idx = _SUPPORT_ORDER.index(cur)
    except ValueError:
        idx = 2  # treat unknown as NEUTRAL
    if idx < len(_SUPPORT_ORDER) - 1:
        state.setdefault("support", {})[space_id] = _SUPPORT_ORDER[idx + 1]


def _has_patriot_piece(sp: Dict) -> bool:
    return any(
        sp.get(tag, 0) > 0
        for tag in (REGULAR_PAT, MILITIA_A, MILITIA_U, FORT_PAT)
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    selected: List[str],
    *,
    limited: bool = False,
) -> Dict:
    """Perform the Rabble‑Rousing Command.

    Parameters
    ----------
    selected : list[str]
        Space IDs chosen by the Patriot player.  They **must each** satisfy at
        least one of:
        • Rebellion Control **and** any Patriot piece; or
        • ≥1 Underground Militia.
    limited : bool, default False
        If *True*, the list *selected* must contain exactly **one** space.
    """
    if faction != "PATRIOTS":
        raise ValueError("Only PATRIOTS may Rabble‑Rouse.")

    if limited and len(selected) != 1:
        raise ValueError("Limited Rabble‑Rousing must select exactly one space.")

    # Resource cost
    _pay_cost(state, len(selected))

    # Ensure Propaganda pool exists in state
    prop_state = state.setdefault("markers", {}).setdefault(PROPAGANDA, {"pool": 0, "on_map": set()})
    prop_state.setdefault("on_map", set())

    push_history(state, f"PATRIOTS RABBLE_ROUSING {selected}")

    for space_id in selected:
        sp = state["spaces"][space_id]

        # Validate selection criteria
        rebellion_control = state.get("control", {}).get(space_id) == "REBELLION"
        has_underground = sp.get(MILITIA_U, 0) > 0
        if not (rebellion_control and _has_patriot_piece(sp) or has_underground):
            raise ValueError(f"{space_id} is not eligible for Rabble‑Rousing.")

        # Place a Propaganda marker if any remain
        if prop_state.get("pool", 0) > 0:
            prop_state["pool"] -= 1
            prop_state["on_map"].add(space_id)

        # Shift support one level toward Active Opposition
        before_support = state.get("support", {}).get(space_id, NEUTRAL)
        _shift_toward_active_opposition(state, space_id)
        after_support = state.get("support", {}).get(space_id, NEUTRAL)

        # Activate 1 Underground Militia unless Rebellion Control w/ Patriot piece
        if not (rebellion_control and _has_patriot_piece(sp)) and sp.get(MILITIA_U, 0) > 0:
            remove_piece(state, MILITIA_U, space_id, 1)
            add_piece(state, MILITIA_A, space_id, 1)
        # Log per‑space details (optional)
        state.setdefault("log", []).append(
            f" PAT Rabble ({space_id})  support: {before_support}→{after_support}  "
            f"prop: {'yes' if space_id in prop_state.get('on_map', set()) else 'no'}  "
            f"militia_flip: {('yes' if not (rebellion_control and _has_patriot_piece(sp)) else 'no')}"
        )

    refresh_control(state)  # may change due to support shift
    enforce_global_caps(state)

    state.setdefault("log", []).append(
        f"PATRIOTS RABBLE‑ROUSING {selected} (limited={limited})"
    )
    return ctx
