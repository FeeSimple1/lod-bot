# lod_ai/bots/british_bot.py
from typing import Dict, List
from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai import dispatcher

class BritishBot(BaseBot):
    faction = "BRITISH"

    # ---------------------------------------------------------
    # 1. Event or Command?  (8.4 header)
    # ---------------------------------------------------------
    def _choose_event_vs_flowchart(self, state: Dict, card: Dict) -> bool:
        if card["sword"]:
            return False                # auto-skip

        if self._brit_event_conditions(state, card):
            dispatcher.execute("EVENT", self.faction, None, state)
            return True
        return False

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

        # C. MARCH
        if self._can_march(state):
            if self._march(state):
                return

        # D. BATTLE
        if self._can_battle(state):
            if self._battle(state):
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
