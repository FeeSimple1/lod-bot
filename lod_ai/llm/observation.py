"""Render a Liberty or Death game state into compact text for an LLM player."""
from __future__ import annotations

from typing import Dict, Optional

from lod_ai import rules_consts as C

# Short, readable labels for each piece tag.
_PIECE_LABELS = [
    (C.REGULAR_BRI, "BritReg"),
    (C.TORY, "Tory"),
    (C.FORT_BRI, "BritFort"),
    (C.REGULAR_PAT, "Continental"),
    (C.MILITIA_U, "Militia(U)"),
    (C.MILITIA_A, "Militia(A)"),
    (C.FORT_PAT, "PatFort"),
    (C.REGULAR_FRE, "FrenchReg"),
    (C.WARPARTY_U, "WarParty(U)"),
    (C.WARPARTY_A, "WarParty(A)"),
    (C.VILLAGE, "Village"),
]

_SUPPORT_NAMES = {
    C.ACTIVE_SUPPORT: "Active Support",
    C.PASSIVE_SUPPORT: "Passive Support",
    C.NEUTRAL: "Neutral",
    C.PASSIVE_OPPOSITION: "Passive Opposition",
    C.ACTIVE_OPPOSITION: "Active Opposition",
}

_FACTION_GOALS = {
    C.BRITISH: ("Support - Opposition > 10  AND  CRC > CBC "
                "(crush the rebellion and bleed it)."),
    C.PATRIOTS: ("Opposition - Support > 10  AND  Patriot Forts + 3 > Villages "
                 "(turn the colonies against the Crown)."),
    C.FRENCH: ("Opposition - Support > 10  AND  CBC > CRC, Treaty of Alliance "
               "played (humble Britain at sea and on land)."),
    C.INDIANS: ("Support - Opposition > 10  AND  Villages - 3 > Patriot Forts "
                "(keep colonists loyal-ish and your villages standing)."),
}


def _card_line(card: Optional[dict]) -> str:
    if not card:
        return "(none)"
    cid = card.get("id", card.get("number", "?"))
    title = card.get("title", card.get("name", "?"))
    order = card.get("order") or card.get("order_icons") or ""
    if isinstance(order, (list, tuple)):
        order = "".join(str(o)[0] for o in order)
    return f"#{cid} {title}" + (f"  [order {order}]" if order else "")


def _faction_summary(state: dict) -> str:
    res = state.get("resources", {})
    lines = ["Resources:  " + "  ".join(
        f"{f}={res.get(f, 0)}" for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)
    )]
    fni = state.get("fni_level", state.get("fni", 0))
    cbc = state.get("cbc", 0)
    crc = state.get("crc", 0)
    toa = bool(state.get("toa_played", state.get("treaty_of_alliance", False)))
    lines.append(f"French Navy Index={fni}   CBC={cbc}   CRC={crc}   "
                 f"Treaty of Alliance={'played' if toa else 'NOT played'}")
    return "\n".join(lines)


def _victory_summary(state: dict) -> str:
    try:
        from lod_ai import victory
        t = victory._summarize_board(state)
        rows = [
            ("BRITISH", victory._british_margin(t)),
            ("PATRIOTS", victory._patriot_margin(t)),
            ("FRENCH", victory._french_margin(t)),
            ("INDIANS", victory._indian_margin(t)),
        ]
        out = ["Victory margins (both must be > 0 to win at a check):"]
        for name, (m1, m2) in rows:
            out.append(f"  {name:<9} cond1={m1:+d}  cond2={m2:+d}")
        return "\n".join(out)
    except Exception:
        return "(victory margins unavailable)"


def _control_of(state: dict, sid: str) -> str:
    ctrl = state.get("control", {}).get(sid)
    if ctrl == "BRITISH":
        return "British Control"
    if ctrl == "REBELLION":
        return "Rebellion Control"
    return "no Control"


def _space_line(state: dict, sid: str, sp: dict) -> Optional[str]:
    pieces = []
    for tag, label in _PIECE_LABELS:
        n = sp.get(tag, 0)
        if n:
            pieces.append(f"{n} {label}")
    # Leaders located here
    leaders = [lid.replace("LEADER_", "").title()
               for lid, loc in state.get("leaders", {}).items() if loc == sid]
    # Blockade marker
    markers = state.get("markers", {})
    blk = markers.get(C.BLOCKADE, {})
    if isinstance(blk, dict) and sid in blk.get("on_map", set()):
        pieces.append("BLOCKADE")
    if not pieces and not leaders:
        return None
    sup = state.get("support", {}).get(sid, 0)
    sup_txt = _SUPPORT_NAMES.get(sup, str(sup))
    bits = ", ".join(pieces) if pieces else "-"
    if leaders:
        bits += f"  | Leaders: {', '.join(leaders)}"
    return f"  {sid:<22} {sup_txt:<18} {_control_of(state, sid):<17} {bits}"


def serialize_state(state: dict, faction: Optional[str] = None) -> str:
    """Return a human-readable board summary for the LLM."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"CURRENT CARD : {_card_line(state.get('current_card'))}")
    lines.append(f"UPCOMING CARD: {_card_line(state.get('upcoming_card'))}")
    elig = state.get("eligible", {})
    if elig:
        elig_txt = ", ".join(f"{k}:{'elig' if v else 'inelig'}"
                             for k, v in elig.items())
        lines.append(f"Eligibility  : {elig_txt}")
    lines.append("-" * 70)
    lines.append(_faction_summary(state))
    lines.append(_victory_summary(state))
    lines.append("-" * 70)
    lines.append("BOARD (only non-empty spaces):")
    lines.append(f"  {'Space':<22} {'Support/Opp':<18} {'Control':<17} Pieces")
    for sid in sorted(state.get("spaces", {})):
        line = _space_line(state, sid, state["spaces"][sid])
        if line:
            lines.append(line)
    if faction:
        lines.append("-" * 70)
        lines.append(f"YOU ARE PLAYING: {faction}")
        goal = _FACTION_GOALS.get(faction)
        if goal:
            lines.append(f"Your victory objective: {goal}")
    lines.append("=" * 70)
    return "\n".join(lines)
