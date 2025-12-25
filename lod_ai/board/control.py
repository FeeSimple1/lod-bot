"""
Control helpers (canonical location).

`refresh_control(state)` computes controller for every space and writes
the result to ``state["control"]`` only.  No control metadata is stored
inside ``state["spaces"]``.
"""

from typing import Dict

REB_TAGS = ("Patriot_", "French_")
ROY_BRI = ("British_",)
ROY_IND = ("Indian_",)


def _tally(space: Dict, prefixes: tuple[str, ...]) -> int:
    return sum(qty for tag, qty in space.items() if tag.startswith(prefixes))


def refresh_control(state: Dict) -> None:
    """Populate ``state['control']`` with the controller for every space."""
    ctrl_map = {}
    for sid, sp in state.get("spaces", {}).items():
        rebels = _tally(sp, REB_TAGS)
        roy_brit = _tally(sp, ROY_BRI)
        roy_ind = _tally(sp, ROY_IND)
        royalist = roy_brit + roy_ind

        control = None
        if rebels > royalist:
            control = "REBELLION"
        elif royalist > rebels and roy_brit > 0:
            control = "BRITISH"

        ctrl_map[sid] = control

    state["control"] = ctrl_map
    # Backwards compatibility for any older callers
    state["control_map"] = ctrl_map
