"""
Control helpers (canonical location).

`refresh_control(state)` computes controller for every space and writes the result to:
- state["control"]
- state["control_map"]  (backwards-compatibility alias)

Control values:
- "REBELLION" if Patriot+French pieces strictly exceed Royalist pieces.
- "BRITISH" if Royalist pieces strictly exceed Rebellion pieces AND at least one British piece is present.
- None otherwise (ties, or only Indians exceed Rebels).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


REB_PREFIXES: tuple[str, ...] = ("Patriot_", "French_")
BRI_PREFIXES: tuple[str, ...] = ("British_",)
IND_PREFIXES: tuple[str, ...] = ("Indian_",)


def _tally(space: Mapping[str, Any], prefixes: tuple[str, ...]) -> int:
    total = 0
    for tag, qty in space.items():
        if not isinstance(tag, str):
            continue
        if not isinstance(qty, int):
            continue
        if qty <= 0:
            continue
        if tag.startswith(prefixes):
            total += qty
    return total


def refresh_control(state: Dict[str, Any]) -> None:
    """Populate state['control'] with the controller for every space."""
    ctrl_map: Dict[str, str | None] = {}

    spaces = state.get("spaces", {})
    if not isinstance(spaces, dict):
        state["control"] = {}
        state["control_map"] = {}
        return

    for sid, sp in spaces.items():
        if not isinstance(sp, dict):
            continue

        rebels = _tally(sp, REB_PREFIXES)
        bri = _tally(sp, BRI_PREFIXES)
        ind = _tally(sp, IND_PREFIXES)
        royalist = bri + ind

        control: str | None = None
        if rebels > royalist:
            control = "REBELLION"
        elif royalist > rebels and bri > 0:
            control = "BRITISH"

        ctrl_map[str(sid)] = control

        # Also store per-space for callers/tests that expect it.
        sp["control"] = control
        sp["British_Control"] = (control == "BRITISH")
        sp["Patriot_Control"] = (control == "REBELLION")
        # Keep legacy synonym if other code uses it
        sp["Rebellion_Control"] = (control == "REBELLION")

    state["control"] = ctrl_map
    state["control_map"] = ctrl_map
