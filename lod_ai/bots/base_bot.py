# lod_ai/bots/base_bot.py
import random
from typing import Dict, List, Tuple, Optional
from lod_ai import rules_consts as C
from lod_ai.board import pieces
from lod_ai.bots import event_instructions as EI
from lod_ai import dispatcher
from lod_ai.cards import CARD_HANDLERS
from lod_ai.map.adjacency import population as _map_population
from lod_ai.util.history import push_history
from lod_ai.util import eligibility as elig

class BaseBot:
    faction: str            # e.g. "BRITISH"

    # ------------ public entry ------------
    def take_turn(self, state: Dict, card: Dict, *, notes: str | None = None,
                  allowed: Dict | None = None) -> Dict[str, object]:
        """Main driver called by engine.play_turn().

        *allowed* carries slot constraints from the engine:
          - event_allowed (bool): False -> skip event evaluation
          - limited_only (bool): True -> 1 space, no SA
          - special_allowed (bool): False -> skip SA
        """
        # Per-TURN coordination flags. These are set during a turn (e.g.
        # Garrison marks its SA so a same-turn Muster fallback doesn't run
        # a second one; B6 caches its Muster-vs-Battle die) but nothing
        # ever cleared them, freezing them for the rest of the GAME:
        # after the first Garrison SA every later British Muster silently
        # skipped its Skirmish/Naval Pressure, and B6's "a D6 roll" was
        # rolled once per game (Session 30 audit).
        state.pop("_sa_done_this_turn", None)
        state.pop("_muster_die_cached", None)
        # Spaces where a Skirmish was executed this turn (§8.4.1: no
        # Garrison moves into a skirmished City). Set by skirmish.execute.
        state.pop("_turn_skirmished_spaces", None)
        # Spaces where a Battle was fought this turn (§4.2.2/§4.3.2/
        # §4.3.3/§4.5.2: no Skirmish/Partisans in a Battle space).
        # Set by battle.execute.
        state.pop("_turn_battle_spaces", None)

        # Propagate slot constraints into state so command methods can check.
        if allowed:
            if allowed.get("limited_only"):
                state["_limited"] = True
            if not allowed.get("special_allowed", True):
                state["_no_special"] = True

        event_ok = allowed.get("event_allowed", True) if allowed else True
        if event_ok and self._choose_event_vs_flowchart(state, card):
            state.pop('_pass_reason', None)
            return {
                "action": "event",
                "used_special": bool(state.get("_turn_used_special")),
                "notes": notes or "",
            }  # Event executed

        # British B3, Patriot P3 and French F3 are explicit flowchart
        # nodes: "Resources > 0? No → PASS". The INDIAN flowchart has no
        # such node — it handles 0 Resources inline (I8: "If Indian
        # Resources = 0, Trade if possible…"; Raid: "Plunder then Trade
        # before completing"), so Indians must reach their flowchart.
        if (state["resources"][self.faction] <= 0
                and self.faction != C.INDIANS):
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

    @staticmethod
    def _reset_command_trace(state: Dict) -> None:
        """Reset per-command trace between fallback attempts.

        When a bot's flowchart tries command A, which partially modifies
        ``_turn_affected_spaces``, and then falls through to command B,
        the accumulated affected spaces would cause false positives in the
        engine's legality check.  Call this before each fallback attempt.
        """
        state["_turn_used_special"] = False
        state["_turn_affected_spaces"] = set()
        state.pop("_turn_command", None)
        state.pop("_turn_command_meta", None)

    @staticmethod
    def _support_opposition_totals(state: Dict) -> tuple[int, int]:
        """Population-weighted Support and Opposition totals (Rules §1.6.3).

        Total Support    = sum(level × population) for spaces with level > 0
        Total Opposition = sum(|level| × population) for spaces with level < 0
        """
        from lod_ai.util.naval import effective_population
        sup = 0
        opp = 0
        for sid, lvl in state.get("support", {}).items():
            # §1.9: Blockaded-City pop counts 0 for Support (Session 46, C1)
            pop = effective_population(state, sid, _map_population(sid))
            if lvl > 0:
                sup += lvl * pop
            elif lvl < 0:
                opp += (-lvl) * pop
        return sup, opp

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
        # 1. Sword icon → auto-ignore (per-faction, not global)
        faction_icons = card.get("faction_icons", {})
        if faction_icons.get(self.faction) == "SWORD":
            return False

        # 2. Musket icon → consult special instruction sheet (per-faction)
        if faction_icons.get(self.faction) == "MUSKET":
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
                # Sheet (cards 18/44): "Target an Eligible enemy Faction.
                # If none, choose Command & Special Activity instead."
                # Enemy = the other SIDE (Glossary / 1.5.2), so Royalist
                # bots target Rebellion factions and vice versa.
                eligible = state.get("eligible", {})
                elig_enemies = [e for e in self._enemy_factions()
                                if eligible.get(e, False)]
                if elig_enemies:
                    # §8.3.5: harmful choice → random enemy, player first.
                    humans = state.get("human_factions", set()) or set()
                    pool = ([e for e in elig_enemies if e in humans]
                            or elig_enemies)
                    rng = state.get("rng")
                    if rng is not None and len(pool) > 1:
                        target = pool[rng.randrange(len(pool))]
                    else:
                        target = sorted(pool)[0]
                    state[f"card{card['id']}_target_faction"] = target
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
            # §8.3.3 post-hoc audit (ROADMAP Piece 4): record the actual
            # Support−Opposition difference around a bot-CHOSEN event so
            # tools.invariants can assert the net shift never favors the
            # enemy side.  Directive-forced events above are exempt
            # (§8.3.1 instructions override the Ineffective test).
            sup_b, opp_b = self._support_opposition_totals(state)
            self._execute_event(card, state)
            sup_a, opp_a = self._support_opposition_totals(state)
            state.setdefault("event_choice_audit", []).append({
                "faction": self.faction,
                "card": int(card.get("id", 0)),
                "d_before": sup_b - opp_b,
                "d_after": sup_a - opp_a,
            })
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
            # Card 29: "Patriots … must Activate their Militia … until ½ of
            # them are Active, rounding down." Sheet (British): "Target
            # Patriots. If < 4 Militia would Activate, choose Command &
            # Special Activity instead." The number that WOULD Activate is
            # floor(total/2) − already-Active, not half the Underground
            # count (audit Session 28).
            try:
                threshold = int(directive.split("_")[2])
            except (IndexError, ValueError):
                return False
            hidden = sum(sp.get(C.MILITIA_U, 0) for sp in state["spaces"].values())
            active = sum(sp.get(C.MILITIA_A, 0) for sp in state["spaces"].values())
            to_flip = max(0, (hidden + active) // 2 - active)
            return to_flip < threshold
        return False

    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives. Subclass should override."""
        return True           # default: always force

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        return False          # subclass will override

    # optional
    def _enemy_factions(self) -> tuple:
        """Factions of the other Side (Glossary "Enemy"; 1.5.2):
        Royalist = British + Indians, Rebellion = Patriots + French."""
        if self.faction in (C.BRITISH, C.INDIANS):
            return (C.PATRIOTS, C.FRENCH)
        return (C.BRITISH, C.INDIANS)

    # Side piece tags for the §8.3.3 friendly-removal clause. Space-count
    # pieces only: Blockades/Squadrons live in the markers dict, so any
    # change to them fails the reconstruction equality below and correctly
    # blocks an "only friendly removal" verdict.
    _SIDE_PIECES = {
        C.BRITISH:  (C.REGULAR_BRI, C.TORY, C.FORT_BRI,
                     C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE),
        C.INDIANS:  (C.REGULAR_BRI, C.TORY, C.FORT_BRI,
                     C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE),
        C.PATRIOTS: (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U,
                     C.FORT_PAT, C.REGULAR_FRE),
        C.FRENCH:   (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U,
                     C.FORT_PAT, C.REGULAR_FRE),
    }

    def _only_removes_friendly_pieces(self, before: Dict, after: Dict) -> bool:
        """§8.3.3 clause 2: True when the Event's ONLY effect is to remove
        one or more friendly pieces from the map without replacing them
        with other friendly pieces. "Friendly" spans the executing
        faction's Side (Glossary "Enemy" mirror; §1.5.2, §8.3.5 "remove
        the other Faction's pieces" treats the ally's pieces as friendly).

        Method: exact reconstruction. Take *after*, put every removed
        friendly piece back (per space, per tag) and restore the pool
        entries (available/casualties/unavailable/out_of_play) for those
        tags. If the result equals *before*, nothing else happened. Any
        friendly placement anywhere, or any other change (support,
        resources, markers, enemy pieces, eligibility), makes the
        reconstruction differ → not Ineffective by this clause."""
        from copy import deepcopy
        tags = self._SIDE_PIECES[self.faction]
        b_spaces = before.get("spaces", {})
        test = deepcopy(after)
        t_spaces = test.get("spaces", {})
        if set(t_spaces) != set(b_spaces):
            return False
        removed_any = False
        for sid, sp_b in b_spaces.items():
            sp_t = t_spaces[sid]
            for tag in tags:
                b, a = sp_b.get(tag, 0), sp_t.get(tag, 0)
                if a > b:
                    return False        # friendly pieces placed → replaced
                if a < b:
                    removed_any = True
                    sp_t[tag] = b       # put them back
                    if b == 0:
                        sp_t.pop(tag, None)
        if not removed_any:
            return False
        for pool in ("available", "casualties", "unavailable", "out_of_play"):
            pb, pt = before.get(pool), test.get(pool)
            if isinstance(pb, dict) and isinstance(pt, dict):
                for tag in tags:
                    if tag in pb:
                        pt[tag] = pb[tag]
                    else:
                        pt.pop(tag, None)
        b_cmp = deepcopy(before)
        for st_ in (test, b_cmp):
            for k in ("history", "rng", "rng_log"):
                st_.pop(k, None)
        return test == b_cmp

    def _is_ineffective_event(self, card: Dict, state: Dict) -> bool:
        """Return True if executing *card* would be Ineffective per §8.3.3:
        it would have no effect at all, its only effect would be to remove
        friendly pieces without replacing them, or it would shift the
        difference between Support and Opposition in favor of the enemy
        side."""
        handler = CARD_HANDLERS.get(card["id"])
        if not handler:
            return True
        from copy import deepcopy
        before = deepcopy(state)
        after = deepcopy(state)
        # Handlers read state["active"] for §8.3.6 side selection; mirror
        # _execute_event. Set on BOTH copies so the equality test below is
        # unaffected by the key itself.
        before["active"] = self.faction
        after["active"] = self.faction
        shaded = card.get("dual") and self.faction in {C.PATRIOTS, C.FRENCH}
        try:
            handler(after, shaded=shaded)
        except Exception:
            return True  # treat as ineffective if handler crashes
        # §8.3.3 net-shift clause. Total Support − Total Opposition per
        # §1.6.2/§1.6.3 with §1.9 blockade-zeroed population (C1
        # precedent, Session 46; effective-pop here Session 67): a level
        # shift on a Blockaded City moves the tracked difference by 0,
        # and an Event that Blockades/un-Blockades a City moves it even
        # with no level change.
        def _support_diff(st):
            sup, opp = self._support_opposition_totals(st)
            return sup - opp
        d_before, d_after = _support_diff(before), _support_diff(after)
        if self.faction in (C.BRITISH, C.INDIANS) and d_after < d_before:
            return True
        if self.faction in (C.PATRIOTS, C.FRENCH) and d_after > d_before:
            return True
        # §8.3.3: "where the only effect would be to remove one or more
        # friendly pieces without replacing them with other friendly pieces"
        if self._only_removes_friendly_pieces(before, after):
            return True
        # No-effect comparison. Drop non-semantic keys: two deepcopies of a
        # random.Random NEVER compare equal (identity-based __eq__), which
        # silently disabled this clause in any state carrying the seeded
        # rng; rng_log grows on any die roll, and rolling dice is not an
        # effect.
        for st_ in (before, after):
            for k in ("history", "rng", "rng_log"):
                st_.pop(k, None)
        return before == after
