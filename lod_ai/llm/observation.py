"""Render a Liberty or Death game state into compact text for an LLM player."""
from __future__ import annotations

from copy import deepcopy
from typing import Optional

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
    from lod_ai.cards.effects.brilliant_stroke import preparations_total
    # The canonical naval helper may initialize a missing marker dictionary.
    # Rendering an observation must not mutate even a sparse caller's state.
    public_state = {**state, "markers": deepcopy(state.get("markers", {}))}
    lines.append(
        f"French Preparations: player/full CBC={preparations_total(public_state)}, "
        f"Non-player/half CBC={preparations_total(public_state, nonplayer=True)}; "
        "Treaty of Alliance threshold > 15 (2.3.9; 8.1).")
    return "\n".join(lines)


def _pool_summary(state: dict) -> str:
    labels = dict(_PIECE_LABELS)
    labels[C.BLOCKADE] = "Squadron/Blockade"
    labels[C.SQUADRON] = "Squadron"
    lines = []
    for key, name in (("available", "Available"), ("unavailable", "Unavailable"),
                      ("casualties", "Casualties")):
        pool = state.get(key, {})
        tags = [tag for tag, _ in _PIECE_LABELS]
        tags.extend(sorted(set(pool) - set(tags)))
        lines.append(f"{name} pieces: " + ", ".join(
            f"{pool.get(tag, 0)} {labels.get(tag, tag)}" for tag in tags))
    markers = state.get("markers", {})
    lines.append("Markers available: " + ", ".join(
        f"{tag}={markers.get(tag, {}).get('pool', 0)}"
        for tag in (C.PROPAGANDA, C.RAID)))
    blockades = markers.get(C.BLOCKADE, {})
    lines.append(
        f"Squadrons/Blockades: West Indies={blockades.get('pool', 0)}, "
        f"on Cities={len(blockades.get('on_map', ()))}, "
        f"Unavailable={state.get('unavailable', {}).get(C.BLOCKADE, 0)}")
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
        out = ["Victory margins (both conditions > 0 pass a faction's check under 7.2):"]
        for name, (m1, m2) in rows:
            out.append(f"  {name:<9} cond1={m1:+d}  cond2={m2:+d}")
        out.append("French victory also requires Treaty of Alliance to have been played.")
        totals = victory._totals(t)
        out.append("Final Support Phase scores (7.3): " + "  ".join(
            f"{name}={totals[name]:+g}" if totals[name] != float("-inf")
            else f"{name}=ineligible before Treaty of Alliance" for name, _ in rows))
        groups = victory.player_groups(state)
        if len(groups) == 1:
            out.append(
                "One-player rules (8.8): the lone human player never wins a Victory Phase. "
                "Avoid any Non-player victory through the final Winter Quarters. "
                "At final scoring, use the lowest owned faction score minus the highest "
                "Non-player score: lead 1-5 is a stalemate; lead 6+ is player victory; "
                "a tied/lower player score loses.")
            if state.get("solo_difficulty", False):
                out.append(
                    "Greater challenge enabled: from the second Winter Quarters, "
                    "any owned faction score below a Non-player score also loses "
                    "during the Victory Phase (8.8).")
        elif any(len(group) > 1 for group in groups):
            out.append(
                "Combined player: both owned factions must pass their checks for a "
                "Victory Phase win (7.2); final scoring uses their lower score (7.3).")
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


def _space_line(state: dict, sid: str, sp: dict) -> str:
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
    sup = state.get("support", {}).get(sid, 0)
    sup_txt = _SUPPORT_NAMES.get(sup, str(sup))
    bits = ", ".join(pieces) if pieces else "-"
    if leaders:
        bits += f"  | Leaders: {', '.join(leaders)}"
    from lod_ai.map.adjacency import population
    marker_counts = []
    for tag in (C.PROPAGANDA, C.RAID, C.BLOCKADE):
        on_map = markers.get(tag, {}).get("on_map", {})
        count = on_map.get(sid, 0) if isinstance(on_map, dict) else int(sid in on_map)
        marker_counts.append(f"{tag}={count}")
    bits += f"  | Population={population(sid)}; " + "; ".join(marker_counts)
    # Two explicit separator spaces also cover a value filling its entire
    # column (notably Passive Opposition and Connecticut_Rhode_Island).
    return f"  {sid:<22}  {sup_txt:<18}  {_control_of(state, sid):<17}  {bits}"


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
    lines.append(_pool_summary(state))
    lines.append(_victory_summary(state))
    lines.append("-" * 70)
    lines.append("BOARD (all spaces, including empty spaces):")
    lines.append(f"  {'Space':<22} {'Support/Opp':<18} {'Control':<17} Pieces")
    for sid in sorted(state.get("spaces", {})):
        lines.append(_space_line(state, sid, state["spaces"][sid]))
    if faction:
        lines.append("-" * 70)
        lines.append(f"YOU ARE PLAYING: {faction}")
        goal = _FACTION_GOALS.get(faction)
        if goal:
            lines.append(f"Your victory objective: {goal}")
    lines.append("=" * 70)
    return "\n".join(lines)
