# lod_ai/bots/base_bot.py
import random
from typing import Dict, List, Tuple, Optional
from lod_ai import rules_consts as C
from lod_ai.board import pieces
from lod_ai.bots.random_spaces import iter_random_spaces
from lod_ai.bots import event_instructions as EI
from lod_ai import dispatcher
from lod_ai.cards import CARD_HANDLERS
from lod_ai.util.history import push_history
from lod_ai.util import eligibility as elig

class BaseBot:
    faction: str            # e.g. "BRITISH"

    # ------------ public entry ------------
    def take_turn(self, state: Dict, card: Dict, *, notes: str | None = None) -> Dict[str, object]:
        """Main driver called by engine.play_turn()."""
        if self._choose_event_vs_flowchart(state, card):
            return {
                "action": "event",
                "used_special": bool(state.get("_turn_used_special")),
                "notes": notes or "",
            }  # Event executed

        if state["resources"][self.faction] <= 0:
            push_history(state, f"{self.faction} PASS (no Resources)")
            return {
                "action": "pass",
                "used_special": bool(state.get("_turn_used_special")),
                "notes": "no resources",
            }

        self._follow_flowchart(state)   # implemented by subclass
        history = state.get("history") or []
        last_entry = history[-1] if history else ""
        last_text = last_entry.upper() if isinstance(last_entry, str) else ""
        action = "pass" if last_text.startswith(f"{self.faction} PASS") else "command"
        return {
            "action": action,
            "used_special": bool(state.get("_turn_used_special")),
            "notes": notes or "",
        }
    # ------------ helpers ---------------

    #  NEW: look-up table for musket-underline directives
    def _event_directive(self, card_id: int) -> str:
        tables = {
            C.BRITISH: EI.BRITISH,
            C.PATRIOTS: EI.PATRIOTS,
            C.INDIANS: EI.INDIANS,
            C.FRENCH: EI.FRENCH,
        }
        return tables[self.faction].get(card_id, "normal")

    def _execute_event(self, card: Dict, state: Dict) -> None:
        """Dispatch the effect function for *card* using proper shading."""
        handler = CARD_HANDLERS.get(card["id"])
        if not handler:
            return
        shaded = card.get("dual") and self.faction in {C.PATRIOTS, C.FRENCH}
        previous_active = state.get("active")
        state["active"] = self.faction
        try:
            handler(state, shaded=shaded)
        finally:
            if previous_active is None:
                state.pop("active", None)
            else:
                state["active"] = previous_active
        self._apply_eligibility_effects(state, card, shaded)

    def _apply_eligibility_effects(self, state: Dict, card: Dict, shaded: bool) -> None:
        """
        Parse simple eligibility phrases from card text and mark flags on state.
        This covers “Remain Eligible” and “Ineligible through next card”.
        """
        text_key = "shaded_event" if shaded else "unshaded_event"
        text = (card.get(text_key) or "").lower()
        targets = self._extract_factions_from_text(text) or [self.faction]
        if "remain eligible" in text:
            for fac in targets:
                elig.mark_remain_eligible(state, fac)
        if "ineligible through next card" in text:
            for fac in targets:
                elig.mark_ineligible_through_next(state, fac)

    def _extract_factions_from_text(self, text: str) -> List[str]:
        """Return any faction names mentioned in *text*."""
        names = {
            "british": C.BRITISH,
            "patriot": C.PATRIOTS,
            "patriots": C.PATRIOTS,
            "french": C.FRENCH,
            "indian": C.INDIANS,
            "indians": C.INDIANS,
        }
        found = []
        for key, fac in names.items():
            if key in text:
                found.append(fac)
        return found

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
            hidden = sum(sp.get(C.MILITIA_U, 0) for sp in state["spaces"].values())
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
        shaded = card.get("dual") and self.faction in {C.PATRIOTS, C.FRENCH}
        handler(after, shaded=shaded)
        before.pop("history", None)
        after.pop("history", None)
        return before == after
