# lod_ai/bots/french.py
"""Simplified French bot implementation.

This bot mirrors the approach used for the British bot but keeps the logic
lightweight.  It covers only the early branches of the French flow‑chart from
Rulebook Chapter 8.  The Event/Command decision uses the criteria listed in
section 8.6 and the flowchart in the Reference folder.
"""

from __future__ import annotations
from typing import Dict, List

from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai.commands import (
    french_agent_mobilization as fam,
    hortelez,
    muster,
    march,
    battle,
)
from lod_ai.util.history import push_history
from lod_ai.board.control import refresh_control

_VALID_PROVINCES: List[str] = ["Quebec", "New_York", "New_Hampshire", "Massachusetts"]


class FrenchBot(BaseBot):
    faction = "FRENCH"

    # ---------------------------------------------------------
    # 2. Command / SA flow‑chart (greatly simplified)
    # ---------------------------------------------------------
    def _follow_flowchart(self, state: Dict) -> None:
        treaty = state.get("toa_played", False)

        if not treaty:
            # Before Treaty of Alliance
            if self._can_agent_mobilization(state) and self._agent_mobilization(state):
                return
            if self._can_hortelez(state) and self._hortelez(state):
                return
            push_history(state, "FRENCH PASS")
            return

        # After Treaty of Alliance
        if self._can_muster(state) and self._muster(state):
            return
        if self._can_battle(state) and self._battle(state):
            return
        if self._can_march(state) and self._march(state):
            return
        push_history(state, "FRENCH PASS")

    # ---------------------------------------------------------
    # ---- Pre-condition helpers ------------------------------
    # ---------------------------------------------------------
    def _can_agent_mobilization(self, state: Dict) -> bool:
        if state.get("toa_played"):
            return False
        if state["resources"].get("FRENCH", 0) < 1:
            return False
        return any(
            state["spaces"].get(p) and state["spaces"][p].get("support", 0) != C.ACTIVE_SUPPORT
            for p in _VALID_PROVINCES
        )

    def _can_hortelez(self, state: Dict) -> bool:
        return state["resources"].get("FRENCH", 0) > 0 and not state.get("toa_played")

    def _can_muster(self, state: Dict) -> bool:
        if not state.get("toa_played"):
            return False
        return state["available"].get(C.REGULAR_FRE, 0) > 0

    def _can_battle(self, state: Dict) -> bool:
        if not state.get("toa_played"):
            return False
        for sp in state["spaces"].values():
            if sp.get(C.REGULAR_FRE, 0) and sp.get(C.REGULAR_BRI, 0):
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        if not state.get("toa_played"):
            return False
        return any(sp.get(C.REGULAR_FRE, 0) for sp in state["spaces"].values())

    # ---------------------------------------------------------
    # ---- Command executors (minimal implementations) ---------
    # ---------------------------------------------------------
    def _agent_mobilization(self, state: Dict) -> bool:
        for prov in _VALID_PROVINCES:
            sp = state["spaces"].get(prov)
            if sp and sp.get("support", 0) != C.ACTIVE_SUPPORT:
                fam.execute(state, "FRENCH", {}, prov, place_continental=False)
                return True
        return False

    def _hortelez(self, state: Dict) -> bool:
        pay = min(3, state["resources"].get("FRENCH", 0))
        if pay <= 0:
            return False
        hortelez.execute(state, "FRENCH", {}, pay=pay)
        return True

    def _muster(self, state: Dict) -> bool:
        spaces = [n for n in state["spaces"] if state["spaces"][n].get(C.REGULAR_FRE, 0) < 4]
        if not spaces:
            return False
        target = spaces[0]
        muster.execute(state, "FRENCH", {}, [target])
        return True

    def _march(self, state: Dict) -> bool:
        for src, sp in state["spaces"].items():
            if sp.get(C.REGULAR_FRE, 0) > 0 and sp.get("adj"):
                dst = sp["adj"][0]
                march.execute(state, "FRENCH", {}, [src], [dst], bring_escorts=False, limited=True)
                return True
        return False

    def _battle(self, state: Dict) -> bool:
        refresh_control(state)
        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_FRE, 0) and sp.get(C.REGULAR_BRI, 0):
                battle.execute(state, "FRENCH", {}, [sid])
                return True
        return False

    # ---------------------------------------------------------
    # ---- Flow‑chart pre‑condition tests ---------------------
    # ---------------------------------------------------------
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Apply the Event vs Command bullets from Rule 8.6."""
        text = card.get("unshaded_event", "")
        support = sum(sp.get("Support", 0) for sp in state["spaces"].values())
        opposition = sum(sp.get("Opposition", 0) for sp in state["spaces"].values())

        if support > opposition and any(w in text for w in ["Support", "Opposition"]):
            push_history(state, "FRENCH plays Event for support shift")
            return True

        keywords = ["French", "Squadron", "Regular"]
        if any(k in text for k in keywords):
            push_history(state, "FRENCH plays Event for placement")
            return True

        if "British" in text and "casualties" in text.lower():
            push_history(state, "FRENCH plays Event for casualties")
            return True

        if "Resources" in text:
            push_history(state, "FRENCH plays Event for resources")
            return True

        return False


