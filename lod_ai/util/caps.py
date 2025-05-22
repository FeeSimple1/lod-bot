


"""
lod_ai.util.caps
================
Enforce BOTH global caps (§1.2) and local stacking rules (§1.4.2).

Global caps (from rules_consts.py)
    • MAX_BRI_FORTS
    • MAX_PAT_FORTS
    • MAX_IND_VILLAGES

Local stacking
    • ≤ 2 combined Fort + Village pieces in any single space.
    • West Indies may contain ONLY:
          - British_Regular, French_Regular,
          - British_Fort,   French_Squadron
    • Indian pieces may NOT occupy a City space.
"""

from collections import defaultdict
from typing import Dict, List

from lod_ai.rules_consts import (
    MAX_BRI_FORTS,
    MAX_PAT_FORTS,
    MAX_IND_VILLAGES,
)

from lod_ai.board.pieces import remove_piece
from lod_ai.util.history import push_history


# ----------------------------------------------------------------------
# 1. GLOBAL-LIMIT ENFORCEMENT
# ----------------------------------------------------------------------
CAP_TABLE = {
    "British_Fort":   MAX_BRI_FORTS,
    "Patriot_Fort":   MAX_PAT_FORTS,
    "Indian_Village": MAX_IND_VILLAGES,   # WP or converted Village
}

def _matches(tag: str, key: str) -> bool:
    if key.endswith("Village"):
        return tag.startswith(key)     # match both A & U sides
    return tag == key


# ----------------------------------------------------------------------
# 2. LOCAL STACKING ENFORCEMENT
# ----------------------------------------------------------------------
MAX_FORT_VIL_PER_SPACE = 2

WEST_INDIES_ALLOWED = {
    "British_Regular",
    "French_Regular",
    "British_Fort",
    "French_Squadron",
}

def _fort_vil_tags(space: Dict) -> List[str]:
    """Return list of Fort/Village tags present in *space*."""
    return [t for t in space if t.endswith("_Fort") or t.startswith("Indian_Village")]

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
            tag = fort_vil_tags.pop()    # remove last counted tag
            remove_piece(state, tag, sid, 1, to="available")
            push_history(state, f"Stacking – removed 1 {tag} from {sid} (>2 Fort/Village)")
            total_fv -= 1

        # B. West Indies restrictions
        if sid == "West_Indies":
            for tag, qty in list(sp.items()):
                if tag not in WEST_INDIES_ALLOWED:
                    remove_piece(state, tag, sid, qty, to="available")
                    push_history(state, f"Stacking – removed {qty} {tag} from West Indies (not allowed)")

        # C. Indians may not occupy a City space (assuming space meta flag)
        if sp.get("is_city"):
            for tag, qty in list(sp.items()):
                if _indian_tag(tag):
                    remove_piece(state, tag, sid, qty, to="available")
                    push_history(state, f"Stacking – removed {qty} {tag} from City {sid} (Indians not allowed)")