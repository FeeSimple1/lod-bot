# lod_ai/bots/base_bot.py
import random
from typing import Dict, List, Tuple, Optional
from lod_ai import rules_consts as C
from lod_ai.util import free_ops
from lod_ai.board import pieces
from lod_ai.bots.random_spaces import iter_random_spaces
from lod_ai.bots import event_instructions as EI
from lod_ai import dispatcher

class BaseBot:
    faction: str            # e.g. "BRITISH"

    # ------------ public entry ------------
    def take_turn(self, state: Dict, card: Dict) -> None:
        """Main driver called by engine.play_turn()."""
        if self._choose_event_vs_flowchart(state, card):
            return                      # Event executed

        if state["resources"][self.faction] <= 0:
            free_ops.push_history(state, f"{self.faction} PASS (no Resources)")
            return

        self._follow_flowchart(state)   # implemented by subclass
    # ------------ helpers ---------------

    #  NEW: look-up table for musket-underline directives
    def _event_directive(self, card_id: int) -> str:
        tables = {
            "BRITISH": EI.BRITISH,
            "PATRIOT": EI.PATRIOT,
            "INDIAN":  EI.INDIAN,
            "FRENCH":  EI.FRENCH,
        }
        return tables[self.faction].get(card_id, "normal")

    #  REPLACE the placeholder method with this full version
    def _choose_event_vs_flowchart(self, state: Dict, card: Dict) -> bool:
        """Return True if the bot executes the Event, else False."""
        # 1. Sword icon → auto-ignore
        if card.get("sword"):
            return False

        # 2. Musket icon → consult special instruction sheet
        if card.get("musket"):
            directive = self._event_directive(card["id"])
            if directive == "ignore":
                return False
            if directive == "force":
                dispatcher.execute("EVENT", self.faction, None, state)
                return True
            if directive.startswith("ignore_if_"):
                # example for card 29:  'ignore_if_4_militia'
                if self._condition_satisfied(directive, state, card):
                    return False
                # otherwise fall through to normal test

        # 3. Ineffective-event test (Rule 8.3.3) – still TODO
        #    if self._is_ineffective_event(card, state):
        #        return False

        # 4. Flow-chart bullet list (British example in british_bot)
        return self._faction_event_conditions(state, card)

    # --- stubs for subclass override ---
    def _follow_flowchart(self, state: Dict) -> None:
        raise NotImplementedError

    def _condition_satisfied(self, directive: str, state: Dict, card: Dict) -> bool:
        return False          # TODO: implement special cases (e.g., card 29)

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        return False          # subclass will override

    # optional
    def _is_ineffective_event(self, card: Dict, state: Dict) -> bool:
        return False          # full Rule 8.3.3 logic later
