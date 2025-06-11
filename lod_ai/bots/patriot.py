"""Simplified Patriot bot following the BaseBot framework."""
from __future__ import annotations

from typing import Dict, List
import random

from lod_ai.bots.base_bot import BaseBot
from lod_ai.board.control import refresh_control
from lod_ai.commands import rally, march, battle
from lod_ai.util.history import push_history


class PatriotBot(BaseBot):
    """Very lightweight Patriot AI used for unit tests."""

    faction = "PATRIOTS"

    # ---------------------------------------------------------
    # 2. Command / SA flow-chart
    # ---------------------------------------------------------
    def _follow_flowchart(self, state: Dict) -> None:
        # 1) Broke? Rally to flip one Opposition space
        if state["resources"][self.faction] <= 2:
            if self._rally_flip(state):
                return

        # 2) 40 % chance to Battle if worthwhile target
        if self._can_battle(state) and random.random() < 0.40:
            if self._battle(state):
                return

        # 3) Otherwise Rally for Continentals or March
        if random.random() < 0.50:
            if self._rally_continentals(state):
                return
        if self._march(state):
            return

        push_history(state, "PATRIOTS PASS")

    # ---------------------------------------------------------
    # ---- Command executors  (minimal stubs) -----------------
    # ---------------------------------------------------------
    def _rally_flip(self, state: Dict) -> bool:
        for name, sp in state["spaces"].items():
            if sp.get("Opposition", 0) > 0:
                rally.execute(state, self.faction, {}, [name])
                return True
        return False

    def _rally_continentals(self, state: Dict) -> bool:
        for name, sp in state["spaces"].items():
            if sp.get(C.REGULAR_PAT, 0) < 4:
                rally.execute(state, self.faction, {}, [name])
                return True
        return False

    def _march(self, state: Dict) -> bool:
        for src, sp in state["spaces"].items():
            if sp.get("Patriot_Militia_A", 0) > 0 or sp.get("Patriot_Militia_U", 0) > 0:
                dests = sp.get("adj", [])
                if dests:
                    dst = dests[0]
                    march.execute(state, self.faction, {}, [src], [dst], limited=True)
                    return True
        return False

    def _battle(self, state: Dict) -> bool:
        refresh_control(state)
        for name, sp in state["spaces"].items():
            patriots = (
                sp.get("Patriot_Militia_A", 0)
                + sp.get("Patriot_Militia_U", 0)
                + sp.get(C.REGULAR_PAT, 0)
            )
            crown = sp.get(C.REGULAR_BRI, 0) + sp.get("British_Tory", 0)
            if patriots >= 1 and patriots > crown:
                battle.execute(state, self.faction, {}, [name])
                return True
        return False

    # ---------------------------------------------------------
    # ---- Flow-chart pre-condition tests ---------------------
    # ---------------------------------------------------------
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Very rough implementation of the Event-or-Command bullets."""
        text = card.get("unshaded_event") or ""
        support = sum(sp.get("Support", 0) for sp in state["spaces"].values())
        opposition = sum(sp.get("Opposition", 0) for sp in state["spaces"].values())

        if support < opposition and "Opposition" in text:
            push_history(state, "PATRIOTS play Event for shift")
            return True

        keywords = ["Militia", "Fort", "Continental"]
        if any(k in text for k in keywords):
            push_history(state, "PATRIOTS play Event for placement")
            return True

        if "remove" in text and any(k in text for k in ["British", "Regular", "Tory"]):
            push_history(state, "PATRIOTS play Event for casualties")
            return True

        return False

