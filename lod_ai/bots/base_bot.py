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
            state.pop('_pass_reason', None)
            return {
                "action": "event",
                "used_special": bool(state.get("_turn_used_special")),
                "notes": notes or "",
            }  # Event executed

        if state["resources"][self.faction] <= 0:
            state['_pass_reason'] = 'resource_gate'
            push_history(state, f"{self.faction} PASS (no Resources)")
            return {
                "action": "pass",
                "used_special": bool(state.get("_turn_used_special")),
                "notes": "no resources",
            }

        self._follow_flowchart(state)   # implemented by subclass
        history = state.get("history") or []
        last_entry = history[-1] if history else None
        # History entries are dicts with a "msg" key; handle both formats
        if isinstance(last_entry, dict):
            last_text = (last_entry.get("msg", "") or "").upper()
        elif isinstance(last_entry, str):
            last_text = last_entry.upper()
        else:
            last_text = ""
        action = "pass" if last_text.startswith(f"{self.faction} PASS") else "command"
        if action == "pass" and '_pass_reason' not in state:
            state['_pass_reason'] = 'no_valid_command'
        elif action != "pass":
            state.pop('_pass_reason', None)
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

    def _execute_event(self, card: Dict, state: Dict, *,
                       force_unshaded: bool = False,
                       force_shaded: bool = False) -> None:
        """Dispatch the effect function for *card* using proper shading."""
        handler = CARD_HANDLERS.get(card["id"])
        if not handler:
            return
        if force_shaded:
            shaded = True
        elif force_unshaded:
            shaded = False
        else:
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
            if directive == "force_unshaded":
                self._execute_event(card, state, force_unshaded=True)
                return True
            if directive == "force_shaded":
                self._execute_event(card, state, force_shaded=True)
                return True
            if directive == "force_if_french_not_human":
                if not state.get("human_factions", set()) & {C.FRENCH}:
                    self._execute_event(card, state)
                    return True
                return False  # French is human → Command & SA instead
            if directive == "force_if_eligible_enemy":
                enemies = {C.BRITISH, C.INDIANS, C.FRENCH} - {self.faction}
                eligible = state.get("eligible", {})
                if any(eligible.get(e, False) for e in enemies):
                    self._execute_event(card, state)
                    return True
                return False  # No eligible enemy → Command & SA instead
            if directive.startswith("ignore_if_"):
                # example for card 29:  'ignore_if_4_militia'
                if self._condition_satisfied(directive, state, card):
                    return False
                # otherwise fall through to normal test
            if directive.startswith("force_if_"):
                # Conditional force: play event if condition is satisfied, else
                # fall through to flowchart (Command & SA).
                if self._force_condition_met(directive, state, card):
                    self._execute_event(card, state)
                    return True
                return False  # condition not met → Command & SA

        # 3. Ineffective-event test (Rule 8.3.3)
        if self._is_ineffective_event(card, state):
            return False

        # 4. Flow-chart bullet list (British example in british_bot)
        if self._faction_event_conditions(state, card):
            self._execute_event(card, state)
            return True
        return False

    # --- stubs for subclass override ---
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk this faction's flowchart for the first valid Limited Command
        that can involve the faction's Leader in the Leader's current space.

        Returns a command name string (e.g. "battle", "muster", "march") or
        None if no valid LimCom is found (which aborts the BS).

        Subclasses must override this with faction-specific flowchart logic.
        """
        return None

    def _find_bs_leader_space(self, state: Dict) -> str | None:
        """Return the space ID of this faction's leader that meets the BS
        piece threshold, or None."""
        from lod_ai.cards.effects.brilliant_stroke import _LEADER_PIECE_THRESHOLD
        entry = _LEADER_PIECE_THRESHOLD.get(self.faction)
        if not entry:
            return None
        leaders, piece_tags, threshold = entry
        from lod_ai.leaders import leader_location
        for leader in leaders:
            loc = leader_location(state, leader)
            if not loc:
                continue
            sp = state.get("spaces", {}).get(loc, {})
            total = sum(sp.get(tag, 0) for tag in piece_tags)
            if total >= threshold:
                return loc
        return None

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

    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives. Subclass should override."""
        return True           # default: always force

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
