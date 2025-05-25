"""
Compute Control markers exactly per Rule 1.7.

• Rebellion pieces = Patriot + French (any type, incl. Forts).
• Royalist pieces  = British + Indians   (incl. Forts & Villages).
• British control only if Royalist > Rebellion AND at least one British piece.
• If Royalist pieces are Indians only, nobody controls even if they exceed.
"""

from typing import Dict


REB_TAGS   = ("Patriot_", "French_")
ROY_BRI    = ("British_",)
ROY_IND    = ("Indian_",)

# count every piece regardless of Underground/Active suffix
def _tally(space: Dict, prefixes: tuple[str, ...]) -> int:
    return sum(qty for tag, qty in space.items() if tag.startswith(prefixes))


def refresh_control(state: Dict) -> None:
    ctrl_map = {}

    for sid, sp in state["spaces"].items():
        rebels   = _tally(sp, REB_TAGS)
        roy_brit = _tally(sp, ROY_BRI)
        roy_ind  = _tally(sp, ROY_IND)
        royalist = roy_brit + roy_ind

        control = None
        if rebels > royalist:
            control = "REBELLION"
        elif royalist > rebels and roy_brit > 0:
            control = "BRITISH"
        # else None (no control: equal pieces OR Indians-only > rebels)

        sp["control"] = control
        sp["British_Control"]  = (control == "BRITISH")
        sp["Patriot_Control"]  = (control == "REBELLION")
        ctrl_map[sid] = control

    state["control_map"] = ctrl_map
