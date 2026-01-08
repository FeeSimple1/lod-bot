


"""
lod_ai.util.caps
================
Enforce BOTH global caps (§1.2) and local stacking rules (§1.4.2).

Global caps (from rules_consts.py)
    • MAX_FORT_BRI
    • MAX_FORT_PAT
    • MAX_VILLAGE

Local stacking
    • ≤ 2 combined Fort + Village pieces in any single space.
    • West Indies may contain ONLY:
          - British_Regular, French_Regular,
          - British_Fort,   Squadron
    • Indian pieces may NOT occupy a City space.
"""

from collections import defaultdict
from typing import Dict, List
from lod_ai.board.control import refresh_control
from lod_ai.map import adjacency as map_adj

from lod_ai.rules_consts import (
    MAX_FORT_BRI,
    MAX_FORT_PAT,
    MAX_VILLAGE,
    REGULAR_BRI,
    REGULAR_FRE,
    FORT_BRI,
    FORT_PAT,
    VILLAGE,
    SQUADRON,
    WEST_INDIES_ID,
)

from lod_ai.board.pieces import remove_piece
from lod_ai.util.history import push_history


# ----------------------------------------------------------------------
# 1. GLOBAL-LIMIT ENFORCEMENT
# ----------------------------------------------------------------------
CAP_TABLE = {
    FORT_BRI: MAX_FORT_BRI,
    FORT_PAT: MAX_FORT_PAT,
    VILLAGE:  MAX_VILLAGE,  # WP or converted Village
}

def _matches(tag: str, key: str) -> bool:
    return tag == key


# ----------------------------------------------------------------------
# 2. LOCAL STACKING ENFORCEMENT
# ----------------------------------------------------------------------
MAX_FORT_VIL_PER_SPACE = 2

WEST_INDIES_ALLOWED = {
    REGULAR_BRI,
    REGULAR_FRE,
    FORT_BRI,
    SQUADRON,
}

def _fort_vil_tags(space: Dict) -> List[str]:
    """Return list of Fort/Village tags present in *space*."""
    return [t for t in space if t.endswith("_Fort") or t == VILLAGE]

def _indian_tag(tag: str) -> bool:
    return tag.startswith("Indian_")


# ----------------------------------------------------------------------
# 3. MAIN ROUTINE
# ----------------------------------------------------------------------
def enforce_global_caps(state: Dict) -> None:
    """
    • Trim ANY global-cap excess to Available.
    • THEN enforce stacking & space-specific restrictions.
    Every removal is logged.
    """
    # 3.1 — GLOBAL CAPS --------------------------------------------------
    live = defaultdict(int)
    for sp in state["spaces"].values():
        for tag, qty in sp.items():
            for key in CAP_TABLE:
                if _matches(tag, key):
                    live[key] += qty

    for key, limit in CAP_TABLE.items():
        extra = live[key] - limit
        if extra <= 0:
            continue
        for sid, sp in state["spaces"].items():
            if extra == 0:
                break
            for tag, qty in list(sp.items()):
                if not _matches(tag, key):
                    continue
                take = min(qty, extra)
                remove_piece(state, tag, sid, take, to="available")
                push_history(state, f"Cap enforced – removed {take} {tag} from {sid} (>{limit})")
                extra -= take
                if extra == 0:
                    break

    # 3.2 — LOCAL STACKING ----------------------------------------------
    for sid, sp in state["spaces"].items():
        # A. Fort/Village stacking ≤ 2
        fort_vil_tags = _fort_vil_tags(sp)
        total_fv = sum(sp[t] for t in fort_vil_tags)
        while total_fv > MAX_FORT_VIL_PER_SPACE:
            removable = next((t for t in fort_vil_tags if sp.get(t, 0) > 0), None)
            if not removable:
                break
            remove_piece(state, removable, sid, 1, to="available")
            push_history(state, f"Stacking – removed 1 {removable} from {sid} (>2 Fort/Village)")
            total_fv -= 1

        # B. West Indies restrictions
        if sid == WEST_INDIES_ID:
            for tag, qty in list(sp.items()):
                if not isinstance(qty, int):
                    continue
                if tag not in WEST_INDIES_ALLOWED:
                    remove_piece(state, tag, sid, qty, to="available")
                    push_history(state, f"Stacking – removed {qty} {tag} from West Indies (not allowed)")

        # C. Indians may not occupy a City space (assuming space meta flag)
        if map_adj.is_city(sid):
            for tag, qty in list(sp.items()):
                if not isinstance(qty, int):
                    continue
                if _indian_tag(tag):
                    remove_piece(state, tag, sid, qty, to="available")
                    push_history(state, f"Stacking – removed {qty} {tag} from City {sid} (Indians not allowed)")
