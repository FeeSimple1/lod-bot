# lod_ai/util/normalize.py
from __future__ import annotations
from typing import Any, Dict
from lod_ai import rules_consts as C

def normalize_state(state: Dict[str, Any]) -> None:
    """
    Idempotent cleanup so the rest of the engine sees a consistent state.
    Safe to call after *any* mutation.
    """

    # --- 1) Per-space Support → state["support"][space] (−2..+2) ----------
    support = state.setdefault("support", {})
    for sid, sp in state.get("spaces", {}).items():
        if sid not in support:
            sup = sp.pop("Support", None)
            opp = sp.pop("Opposition", None)
            if sup is None and opp is None:
                support[sid] = support.get(sid, 0)
            else:
                sup = int(sup or 0)
                opp = int(opp or 0)
                lvl = max(-2, min(2, sup - opp))
                support[sid] = lvl

    # --- 2) Treaty flag expected by victory module -------------------------
    # victory.check() looks for "treaty_of_alliance", not "toa_played".
    state.setdefault("toa_played", bool(state.get("treaty_of_alliance", False)))
    state.setdefault("treaty_of_alliance", bool(state.get("toa_played", False)))

    # --- 3) Casualty tallies expected by victory module --------------------
    # victory.check() uses "cbc" and "crc".  Map from existing fields if needed.
    if "cbc" not in state or "crc" not in state:
        cas = state.get("casualties", {})
        cbc = cas.get("BRITISH", state.get("british_casualties", 0))
        # "Rebellion" casualties ≈ Patriots (+ French if tracked)
        crc = cas.get("PATRIOTS", state.get("patriot_casualties", 0)) + cas.get("FRENCH", 0)
        state.setdefault("cbc", int(cbc))
        state.setdefault("crc", int(crc))
    state.setdefault("cbc", 0)
    state.setdefault("crc", 0)

    # --- 4) Marker pools for Propaganda/Raid used by card effects ----------
    def _ensure_pool(tag: str, cap: int) -> None:
        placed = sum(sp.get(tag, 0) for sp in state.get("spaces", {}).values())
        pool_default = max(0, cap - placed)
        state.setdefault("markers", {}).setdefault(tag, {}).setdefault("pool", pool_default)

    _ensure_pool(C.PROPAGANDA, C.MAX_PROPAGANDA)
    _ensure_pool(C.RAID,        C.MAX_RAID)

    # --- 5) FNI and eligibility defaults -----------------------------------
    state.setdefault("fni_level", 0)
    if not state.get("toa_played"):
        state["fni_level"] = 0
    state["ineligible_next"] = set(state.get("ineligible_next", set()))
    state["eligible_next"] = set(state.get("eligible_next", set()))

    # --- 6) Leader counters (convert simple 'leaders' mapping into pieces) --
    leaders = state.get("leaders")
    if isinstance(leaders, dict):
        for short, loc in leaders.items():
            if not loc:
                continue
            tag = f"LEADER_{short.upper()}"
            if loc in state.get("spaces", {}) and state["spaces"][loc].get(tag, 0) == 0:
                state["spaces"][loc][tag] = 1