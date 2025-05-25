# lod_ai/bots/british_bot.py
from typing import Dict, List
from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai import dispatcher
from lod_ai.board.control import refresh_control
import json
from pathlib import Path

_MAP_DATA = json.load(open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json"))
CITIES = [name for name, info in _MAP_DATA.items() if info.get("type") == "City"]

class BritishBot(BaseBot):
    faction = "BRITISH"

    # ---------------------------------------------------------
    # 2. Command / SA flow-chart
    # ---------------------------------------------------------
    def _follow_flowchart(self, state: Dict) -> None:
        # A. GARRISON
        if self._can_garrison(state):
            if self._garrison(state):
                return

        # B. MUSTER
        if self._can_muster(state):
            if self._muster(state):
                return

        # C. BATTLE
        if self._can_battle(state):
            if self._battle(state):
                return

        # D. MARCH
        if self._can_march(state):
            if self._march(state):
                return

        # E. PASS
        dispatcher.execute("PASS", self.faction, None, state)

    # ---------------------------------------------------------
    # ---- Command executors  (stubs – fill bullets later) ----
    # ---------------------------------------------------------
    def _garrison(self, state: Dict) -> bool:
        # call dispatcher.execute("GARRISON", ...)
        # run Naval Pressure / Skirmish choice
        return True        # return False if aborted

    def _muster(self, state: Dict) -> bool:
        # follow eight-step bullets incl. Reward Loyalty & SA
        return True

    def _march(self, state: Dict) -> bool:
        # bullets incl. Common Cause logic & SA fallback
        return True

    def _battle(self, state: Dict) -> bool:
        # select all battle spaces, resolve, SA fallback if needed
        return True

    # ---------------------------------------------------------
    # ---- Flow-chart pre-condition tests ---------------------
    # ---------------------------------------------------------
    # each _can_* mirrors the italic opening sentence of §8.4.x

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Placeholder for the 'Event or Command?' bullets (Rule 8.4)."""
        return self._brit_event_conditions(state, card)

    def _brit_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Simplified check of B2 bullets. Currently always False."""
        return False

    def _can_garrison(self, state: Dict) -> bool:
        refresh_control(state)
        regs = sum(sp.get("British_Regulars", 0) for sp in state["spaces"].values())
        if regs < 10:
            return False
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            if sp.get("control") == "REBELLION" and sp.get("Patriot_Fort", 0) == 0:
                return True
        return False

    def _can_muster(self, state: Dict) -> bool:
        avail = state.get("available", {}).get("British_Regulars", 0)
        import random
        return avail > random.randint(1, 6)

    def _can_battle(self, state: Dict) -> bool:
        refresh_control(state)
        for sp in state["spaces"].values():
            rebels = sp.get("Patriot_Continentals", 0) + sp.get("Patriot_Militia", 0)
            if rebels >= 2 and sp.get("British_Regulars", 0) > rebels:
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        # Assume March is always possible if any British Regulars exist
        return any(sp.get("British_Regulars", 0) for sp in state["spaces"].values())
