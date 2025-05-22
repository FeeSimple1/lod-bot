"""
lod_ai.special_activities.common_cause
======================================
§4.2.1 Common Cause — British may use War Parties as if they were Tories
during the *same* March or Battle.

* Allowed only if:
    – faction == "BRITISH"
    – each listed space contains ≥1 British cube and ≥1 War-Party.
* War Parties chosen become **Active** immediately.
* They may **not** move into or between Cities.
* We record how many WP are “loaned” in ctx["common_cause"] so the
  accompanying Command can treat them as Tories.
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.rules_consts import (
    REGULAR_BRI,
    WARPARTY_U, WARPARTY_A,
)
from lod_ai.util.history import push_history

SA_NAME = "COMMON_CAUSE"      # auto-registered by special_activities/__init__.py


def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    spaces: List[str],
    *,
    wp_counts: Dict[str, int] | None = None,   # omit ⇒ use *all* WP in each space
    mode: str = "MARCH",                       # "MARCH" or "BATTLE"
    destinations: List[str] | None = None,     # required for March validation
) -> Dict:
    if faction != "BRITISH":
        raise ValueError("Only BRITISH may invoke Common Cause.")

    push_history(state, f"BRITISH COMMON_CAUSE in {', '.join(spaces)}")
    wp_counts = wp_counts or {}

    ctx.setdefault("common_cause", {})

    for s in spaces:
        sp = state["spaces"][s]

        if sp.get(REGULAR_BRI, 0) == 0:
            raise ValueError(f"{s}: needs British piece for Common Cause.")
        if (sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0)) == 0:
            raise ValueError(f"{s}: no War Parties present.")

        use = wp_counts.get(s, sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0))
        if use < 1:
            continue

        if use > sp.get(WARPARTY_U, 0) + sp.get(WARPARTY_A, 0):
            raise ValueError(f"{s}: requested {use} WP, only "
                             f"{sp.get(WARPARTY_U,0)+sp.get(WARPARTY_A,0)} present.")

        # Flip Underground first
        take_u = min(use, sp.get(WARPARTY_U, 0))
        sp[WARPARTY_U] -= take_u
        sp[WARPARTY_A] += take_u
        # any remainder already Active

        ctx["common_cause"][s] = use

    # March-specific validation: WP may not enter or move between Cities
    if mode == "MARCH" and destinations:
        for dst in destinations:
            if state["spaces"][dst].get("city", False) or state["spaces"][dst].get("type") == "City":
                raise ValueError("Common-Cause War Parties may not move into Cities.")

    return ctx