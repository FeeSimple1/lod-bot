"""Simplified Patriot bot following the BaseBot framework."""
from __future__ import annotations

from typing import Dict, List
import random

from lod_ai import rules_consts as C
from lod_ai.commands import (
    rally,
    march,
    battle,
    rabble_rousing,
)
from lod_ai.special_activities import partisans, skirmish, persuasion

from lod_ai.bots.base_bot import BaseBot
from lod_ai.board.control import refresh_control
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
        """Rally in the first Opposition space to flip it toward Neutral."""
        for name, sp in state["spaces"].items():
            if sp.get("Opposition", 0) > 0:
                rally.execute(state, self.faction, {}, [name])
                return True
        return False

    def _rally_continentals(self, state: Dict) -> bool:
        """Rally to bring Continentals onto the map or build Forts."""
        avail = state.get("available", {}).get(C.REGULAR_PAT, 0)
        target = None
        for name, sp in state["spaces"].items():
            if sp.get(C.FORT_PAT, 0) and (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)) > 1:
                target = name
                break
        if not target:
            for name, sp in state["spaces"].items():
                total = sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                if total >= 4 and sp.get(C.FORT_PAT, 0) == 0:
                    rally.execute(state, self.faction, {}, [name], build_fort={name})
                    return True
        if target and avail:
            rally.execute(state, self.faction, {}, [target], promote_space=target)
            return True
        return False

    def _march(self, state: Dict) -> bool:
        """Simple March: move all Patriot pieces from first origin to best adjacent."""
        for src, sp in state["spaces"].items():
            pieces = sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            if pieces > 0:
                dests = sp.get("adj", [])
                if dests:
                    dst = max(dests, key=lambda d: state["spaces"][d].get("population", 0))
                    march.execute(state, self.faction, {}, [src], [dst], bring_escorts=True, limited=True)
                    return True
        return False

    def _battle(self, state: Dict) -> bool:
        """Battle where Patriot force exceeds Crown."""
        refresh_control(state)
        candidates = []
        for name, sp in state["spaces"].items():
            patriots = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
            )
            crown = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if patriots > crown and patriots > 0:
                pop = sp.get("population", 0)
                candidates.append((pop, name))
        if not candidates:
            return False
        _, target = max(candidates)
        battle.execute(state, self.faction, {}, [target])
        return True

    def _can_battle(self, state: Dict) -> bool:
        refresh_control(state)
        for sp in state["spaces"].values():
            patriots = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
            )
            crown = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if patriots > crown and patriots > 0:
                return True
        return False

    def _rabble_rousing(self, state: Dict) -> bool:
        """Execute Rabble-Rousing in all spaces that can shift opposition."""
        targets = []
        for name, sp in state["spaces"].items():
            if sp.get("support", 0) > C.ACTIVE_OPPOSITION:
                targets.append((sp.get("support", 0), name))
        if not targets:
            return False
        # sort: Active Support first then highest population
        targets.sort(key=lambda t: (t[0], state["spaces"][t[1]].get("population", 0)), reverse=True)
        spaces = [n for _, n in targets]
        rabble_rousing.execute(state, self.faction, {}, spaces[:4])
        return True

    def _partisans(self, state: Dict) -> bool:
        """Partisans in a single eligible space."""
        for name, sp in state["spaces"].items():
            if sp.get(C.MILITIA_U, 0) > 0 and (
                sp.get(C.REGULAR_BRI, 0)
                or sp.get(C.TORY, 0)
                or sp.get(C.WARPARTY_A, 0)
                or sp.get(C.WARPARTY_U, 0)
                or sp.get(C.VILLAGE, 0)
            ):
                partisans.execute(state, self.faction, {}, name, option=1)
                return True
        return False

    def _skirmish(self, state: Dict) -> bool:
        """Skirmish in first space with Continentals and enemy."""
        for name, sp in state["spaces"].items():
            if sp.get(C.REGULAR_PAT, 0) > 0 and (
                sp.get(C.REGULAR_BRI, 0)
                or sp.get(C.TORY, 0)
                or sp.get(C.FORT_BRI, 0)
            ):
                skirmish.execute(state, self.faction, {}, name, option=1)
                return True
        return False

    def _persuasion(self, state: Dict) -> bool:
        """Persuasion in up to three Rebel controlled spaces."""
        spaces = []
        for name, sp in state["spaces"].items():
            if sp.get("control") == "REBELLION" and sp.get(C.MILITIA_U, 0) > 0:
                spaces.append((sp.get(C.FORT_PAT, 0), name))
        if not spaces:
            return False
        spaces.sort(key=lambda t: (t[0], state["spaces"][t[1]].get("population", 0)), reverse=True)
        persuasion.execute(state, self.faction, {}, spaces=[n for _, n in spaces[:3]])
        return True

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

