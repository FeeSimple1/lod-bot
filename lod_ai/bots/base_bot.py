# lod_ai/bots/base_bot.py
import random
from typing import Dict, List, Tuple, Optional
from lod_ai import rules_consts as C
from lod_ai.util import free_ops
from lod_ai.board import pieces
from lod_ai.bots.random_spaces import iter_random_spaces
from lod_ai.bots import event_instructions as EI
from lod_ai import dispatcher
from lod_ai.cards import CARD_HANDLERS

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

    def _execute_event(self, card: Dict, state: Dict) -> None:
        """Dispatch the effect function for *card* using proper shading."""
        handler = CARD_HANDLERS.get(card["id"])
        if not handler:
            return
        shaded = card.get("dual") and self.faction in {"PATRIOTS", "FRENCH"}
        handler(state, shaded=shaded)

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
                self._execute_event(card, state)
                return True
            if directive.startswith("ignore_if_"):
                # example for card 29:  'ignore_if_4_militia'
                if self._condition_satisfied(directive, state, card):
                    return False
                # otherwise fall through to normal test

        # 3. Ineffective-event test (Rule 8.3.3)
        if self._is_ineffective_event(card, state):
            return False

        # 4. Flow-chart bullet list (British example in british_bot)
        if self._faction_event_conditions(state, card):
            self._execute_event(card, state)
            return True
        return False

    # --- stubs for subclass override ---
    def _follow_flowchart(self, state: Dict) -> None:
        raise NotImplementedError

    def _condition_satisfied(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate conditional directives from the instruction sheet."""
        if directive.startswith("ignore_if_") and "militia" in directive:
            try:
                threshold = int(directive.split("_")[2])
            except (IndexError, ValueError):
                return False
            hidden = sum(sp.get("Patriot_Militia_U", 0) for sp in state["spaces"].values())
            to_flip = hidden // 2
            return to_flip < threshold
        return False

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        return False          # subclass will override

    # optional
    def _is_ineffective_event(self, card: Dict, state: Dict) -> bool:
        """Return True if executing *card* would change nothing."""
        handler = CARD_HANDLERS.get(card["id"])
        if not handler:
            return True
        from copy import deepcopy
        before = deepcopy(state)
        after = deepcopy(state)
        shaded = card.get("dual") and self.faction in {"PATRIOTS", "FRENCH"}
        handler(after, shaded=shaded)
        before.pop("history", None)
        after.pop("history", None)
        return before == after
