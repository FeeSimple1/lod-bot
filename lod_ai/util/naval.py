"""
Naval & FNI helpers  ·  stripped-down version.

Only the two routines already referenced by card code are provided:
    • adjust_fni(state, delta)
    • auto_place_blockade(state)  (stub for future use)
"""

from lod_ai.util.history import push_history


def adjust_fni(state, delta: int) -> None:
    """
    Move the French Navy Influence (FNI) marker <delta> boxes
    toward peace (negative) or war (positive). Track is 1 ↔ 6.

    Cards #55, year_end.resolve, and Naval Pressure SA will call this.
    """
    box = state.setdefault("fni_box", 3)       # default to center space 3
    new_box = max(1, min(6, box + delta))
    state["fni_box"] = new_box
    if delta:
        direction = "up" if delta > 0 else "down"
        push_history(state, f"FNI shifts {direction} to box {new_box}")


# ──────────────────────────────────────────────────────────────
#  Placeholder – full blockade logic not yet needed
# ──────────────────────────────────────────────────────────────
def auto_place_blockade(state) -> None:
    """
    Stub: In the full rules, certain FNI levels auto-place Blockade markers
    in South Carolina and Massachusetts Ports.  Implement when Commands/
    SAs reference Naval Pressure.  For now it only logs.
    """
    push_history(state, "[Blockade auto-placement not yet implemented]")
