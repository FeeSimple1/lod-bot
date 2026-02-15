# lod_ai/bots/patriot.py
"""
Full‑flow implementation of the Non‑Player **Patriot** bot (§8.7).

Flow‑chart nodes covered (P1 → P13):

  • Event‑vs‑Command handled by BaseBot._choose_event_vs_flowchart().
  • P3  Resources test
  • P6  Battle‑vs‑other decision
  • P4  Battle    → P8 loop
  • P5  March     → P8 loop
  • P7  Rally     → P8 loop
  • P11 Rabble‑Rousing fallback → P8 loop
  • P8  Partisans → Skirmish → Persuasion chain
  • P13 Persuasion (resource injection) terminal

The implementation relies on existing command / SA modules and concentrates on
correct *selection* of spaces rather than re‑implementing combat resolution.
"""

from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict
import random, json
from pathlib import Path

from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots import event_instructions as EI
from lod_ai import rules_consts as C
from lod_ai.commands import rally, march, battle, rabble_rousing
from lod_ai.special_activities import partisans, skirmish, persuasion
from lod_ai.board.control import refresh_control
from lod_ai.util.history import push_history
from lod_ai.leaders import leader_location

# ---------------------------------------------------------------------------
#  Helper constants
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
CITIES = [n for n, d in _MAP_DATA.items() if d.get("type") == "City"]


class PatriotBot(BaseBot):
    """Full non‑player Patriot AI."""
    faction = C.PATRIOTS             # canonical faction key

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    def _event_directive(self, card_id: int) -> str:
        """
        Patriots use the existing Brown‑Bess instruction table keyed as 'PATRIOTS'.
        Keeping the table as‑is while this bot uses the canonical 'PATRIOTS' key.
        """
        return EI.PATRIOTS.get(card_id, "normal")

    # ===================================================================
    #  BRILLIANT STROKE LimCom  (§8.3.7)
    # ===================================================================
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk Patriot flowchart for the first valid Limited Command
        that can involve Washington in his current space.

        Flowchart order: P3 → P6 (Battle) → P9 (Rally) → P10 (Rabble-Rousing) → P5 (March).
        Returns a command name or None.
        """
        leader_space = self._find_bs_leader_space(state)
        if not leader_space:
            return None

        # P3: Resources > 0?
        if state.get("resources", {}).get(C.PATRIOTS, 0) <= 0:
            return None

        sp = state["spaces"].get(leader_space, {})
        refresh_control(state)

        # P6: Battle — Rebel cubes + Leader > Active British/Indian pieces
        # in the leader's space (with both sides present)?
        rebel = self._rebel_cube_count(state, leader_space)
        royal = self._active_royal_count(sp)
        if rebel > 0 and royal > 0 and rebel > royal:
            return "battle"

        # P9: Rally — would place Fort OR 1D6 > Underground Militia on map?
        # Check if Rally is valid in the leader's space.
        avail_forts = state["available"].get(C.FORT_PAT, 0)
        rebel_group = self._rebel_group_size(sp)
        if avail_forts and rebel_group >= 4 and sp.get(C.FORT_PAT, 0) == 0:
            return "rally"
        # Also check the 1D6 > Underground Militia condition
        hidden = sum(s.get(C.MILITIA_U, 0) for s in state["spaces"].values())
        # Don't consume a die roll here — just check if Rally is plausible
        # (Militia can be placed in the leader's space)
        avail_militia = state["available"].get(C.MILITIA_U, 0)
        if avail_militia > 0 or rebel_group >= 4:
            return "rally"

        # P10: Rabble-Rousing — can shift leader's space toward Active Opposition?
        support = self._support_level(state, leader_space)
        if support > C.ACTIVE_OPPOSITION:
            return "rabble_rousing"

        # P5: March — can march from leader's space
        if rebel_group >= 1:
            return "march"

        return None

    # ===================================================================
    #  FLOW‑CHART DRIVER
    # ===================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # Node P3 – are we broke?
        if state["resources"][self.faction] == 0:
            push_history(state, "PATRIOTS PASS (no Resources)")
            return

        # Node P6 – can we win a Battle somewhere?
        if self._battle_possible(state):
            if self._battle_chain(state):     # P4 (+ P8 loop)
                return
        else:
            # P9 decision chain → Rally / Rabble‑Rousing / March
            if self._rally_preferred(state):
                if self._rally_chain(state):  # P7 (+ P8 loop)
                    return
            elif self._rabble_possible(state):
                if self._rabble_chain(state): # P11 (+ P8 loop)
                    return
            if self._march_chain(state):      # P5 (+ P8 loop)
                return

        push_history(state, "PATRIOTS PASS")

    # ===================================================================
    #  EXECUTION CHAINS
    # ===================================================================
    def _battle_chain(self, state: Dict) -> bool:
        if not self._execute_battle(state):
            # If no legal Battle, drop to Rally branch (P4 “If none, Rally”)
            return self._rally_chain(state)
        self._partisans_loop(state)           # P8/12/13
        return True

    def _march_chain(self, state: Dict) -> bool:
        if not self._execute_march(state):
            # If March impossible → Rally (P5 “If none, Rally”)
            return self._rally_chain(state)
        self._partisans_loop(state)
        return True

    def _rally_chain(self, state: Dict) -> bool:
        used_persuasion = False
        if not self._execute_rally(state):
            # If Rally impossible → Rabble‑Rousing (P7 “If none”)
            return self._rabble_chain(state)
        # P7: resources might have hit 0 during Rally
        if state["resources"][self.faction] == 0:
            used_persuasion = self._try_persuasion(state)
        if not used_persuasion:
            self._partisans_loop(state)
        return True

    def _rabble_chain(self, state: Dict) -> bool:
        used_persuasion = False
        if not self._execute_rabble(state):
            # P11 "If none" → P7 (Rally with its own fallback chain)
            return self._rally_chain(state)
        # P11: resources may reach 0
        if state["resources"][self.faction] == 0:
            used_persuasion = self._try_persuasion(state)
        if not used_persuasion:
            self._partisans_loop(state)
        return True

    # -------------- Partisans → Skirmish → Persuasion ---------------
    def _partisans_loop(self, state: Dict) -> None:
        if state["resources"][self.faction] == 0:
            if self._try_persuasion(state):
                return
        if self._try_partisans(state):
            return
        if self._try_skirmish(state):
            return
        self._try_persuasion(state)

    # ===================================================================
    #  INDIVIDUAL COMMAND IMPLEMENTATIONS
    # ===================================================================
    # ---------- Battle (P4) -------------------------------------------
    def _battle_possible(self, state: Dict) -> bool:
        """P6: 'Rebel cubes + Leader > Active British and/or Indian pieces
        in space with both?'"""
        refresh_control(state)
        for sid, sp in state["spaces"].items():
            rebel = self._rebel_cube_count(state, sid)
            royal = self._active_royal_count(sp)
            if rebel > 0 and royal > 0 and rebel > royal:
                return True
        return False

    def _execute_battle(self, state: Dict) -> bool:
        """P4: Select all spaces where Rebel Force Level (if possible
        including French) + modifiers exceeds British Force Level + modifiers.

        Priority: first with Washington, then in highest Pop, then where
        most Villages, then random.

        Force Level per §3.6.2-3.6.3:
          Rebellion ATTACKING: cubes + min(French, Patriot cubes) + half Active Militia
            (no forts for attacker)
          Royalist DEFENDING: Regulars + Tories (uncapped when defending)
            + half Active WP + Forts
        """
        refresh_control(state)
        targets = []
        for sid, sp in state["spaces"].items():
            # Rebel Force Level (attacking): cubes + half Active Militia only
            pat_cubes = sp.get(C.REGULAR_PAT, 0)
            fre_cubes = min(sp.get(C.REGULAR_FRE, 0), pat_cubes)
            active_mil = sp.get(C.MILITIA_A, 0)
            rebel_force = pat_cubes + fre_cubes + (active_mil // 2)

            # British Force Level (defending): Regs + Tories (uncapped) +
            # half Active WP + Forts
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0)
            active_wp = sp.get(C.WARPARTY_A, 0)
            brit_force = regs + tories + (active_wp // 2) + sp.get(C.FORT_BRI, 0)

            if rebel_force > brit_force and (regs + tories + active_wp) > 0:
                has_wash = 1 if leader_location(state, "LEADER_WASHINGTON") == sid else 0
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                villages = sp.get(C.VILLAGE, 0)
                targets.append((-has_wash, -pop, -villages, state["rng"].random(), sid))
        if not targets:
            return False
        targets.sort()
        chosen = [sid for *_, sid in targets]
        battle.execute(state, self.faction, {}, chosen)
        return True

    def _rebel_cube_count(self, state: Dict, sid: str) -> int:
        """P6: 'Rebel cubes + Leader' = Continentals + French Regulars + leader."""
        sp = state["spaces"].get(sid, {})
        cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        if leader_location(state, "LEADER_WASHINGTON") == sid:
            cubes += 1
        return cubes

    def _active_royal_count(self, sp: Dict) -> int:
        """P6: 'Active British and/or Indian pieces'."""
        return (
            sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) +
            sp.get(C.WARPARTY_A, 0)
        )

    # ---------- March (P5) --------------------------------------------
    def _execute_march(self, state: Dict) -> bool:
        refresh_control(state)
        # Origins with largest rebel groups (moving largest groups first per P5)
        origins = sorted(
            (self._rebel_group_size(sp), sid)
            for sid, sp in state["spaces"].items()
            if self._rebel_group_size(sp) >= 1
        )
        if not origins:
            return False
        origins.sort(reverse=True)
        used = 0
        for size, sid in origins:
            if used >= 2:
                break
            dst = self._march_destination(state, sid)
            if not dst:
                continue
            march.execute(
                state,
                self.faction,
                {},
                [sid],
                [dst],
                bring_escorts=True,
                limited=False,
            )
            used += 1
        return used > 0

    def _rebel_group_size(self, sp: Dict) -> int:
        return (
            sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
            sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        )

    def _march_destination(self, state: Dict, origin: str) -> str | None:
        """Pick destination per P5 bullets (Villages > Cities > other, highest Pop)."""
        best = None
        best_key = (-1, -1, -1)
        ctrl = state.get("control", {})
        for token in _MAP_DATA[origin]["adj"]:
            for dst in token.split("|"):
                if dst not in state.get("spaces", {}):
                    continue
                if ctrl.get(dst) == "REBELLION":
                    continue
                has_village = state["spaces"][dst].get(C.VILLAGE, 0)
                is_city = 1 if dst in CITIES else 0
                pop = _MAP_DATA.get(dst, {}).get("population", 0)
                key = (has_village, is_city, pop)
                if key > best_key:
                    best_key = key
                    best = dst
        return best

    # ---------- Rally (P7) --------------------------------------------
    def _execute_rally(self, state: Dict) -> bool:
        """
        Implement a condensed version of the big bullet list:
          – build Forts first,
          – then place Militia or Continentals,
          – promote Militia,
          – etc.
        For brevity we delegate all heavy lifting to rally.execute while
        supplying high‑priority spaces selected here.
        """
        # Potential Fort builds
        fort_targets = [
            sid for sid, sp in state["spaces"].items()
            if sp.get(C.FORT_PAT, 0) == 0 and
               self._rebel_group_size(sp) >= 4
        ]
        fort_targets.sort(key=lambda n: (-(_MAP_DATA[n]["type"] == "City"), -_MAP_DATA[n]["population"]))
        # Rally is Max 4 total spaces; build forts in all qualifying spaces up to that limit
        forts_to_build = set(fort_targets[:4])

        # Militia placement – favour Forts lacking other Patriot pieces
        militia_spaces = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.FORT_PAT, 0) and self._rebel_group_size(sp) == sp.get(C.MILITIA_U, 0):
                militia_spaces.append(sid)
        if not militia_spaces:
            # else try to flip control elsewhere
            ctrl = state.get("control", {})
            for sid, sp in state["spaces"].items():
                if ctrl.get(sid) != "REBELLION":
                    militia_spaces.append(sid)
        militia_spaces = militia_spaces[:4]

        rally.execute(
            state,
            self.faction,
            {},
            list(set(list(forts_to_build) + militia_spaces)),
            build_fort=forts_to_build,
            promote_space=None,   # promotion handled by rally rules
        )
        return True

    # ---------- Rabble‑Rousing (P11) ----------------------------------
    def _execute_rabble(self, state: Dict) -> bool:
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if self._support_level(state, sid) > C.ACTIVE_OPPOSITION
        ]
        if not spaces:
            return False
        # active‑support first, higher pop
        spaces.sort(key=lambda n: (-self._support_level(state, n), -_MAP_DATA[n].get("population", 0)))
        rabble_rousing.execute(state, self.faction, {}, spaces[:4])
        return True

    # ===================================================================
    #  SPECIAL‑ACTIVITY HELPERS
    # ===================================================================
    def _try_partisans(self, state: Dict) -> bool:
        """P8: Partisans (Max 1).
        Priority: first to remove a Village, then to remove most War Parties
        then British; within each first to add most Rebel Control then to
        remove most British Control, then random.
        """
        if state["resources"][self.faction] == 0:
            return False  # rule: Persuasion instead
        refresh_control(state)
        candidates = []
        ctrl = state.get("control", {})
        for sid, sp in state["spaces"].items():
            if not sp.get(C.MILITIA_U, 0):
                continue
            has_village = sp.get(C.VILLAGE, 0)
            wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            british = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            enemy = has_village + wp + british
            if enemy == 0:
                continue
            # Would add Rebel Control? (not already REBELLION)
            adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            # Would remove British Control?
            removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
            # Sort key per reference: village first, then most WP, then
            # most British; within each: add Rebel Control, then remove
            # British Control, then random
            key = (-has_village, -wp, -british, -adds_rebel_ctrl,
                   -removes_brit_ctrl, state["rng"].random())
            candidates.append((key, sid))
        if not candidates:
            return False
        candidates.sort()
        for _, sid in candidates:
            sp = state["spaces"][sid]
            has_village = sp.get(C.VILLAGE, 0)
            wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            # Option 3: remove a Village (requires no WP in space)
            if has_village and not wp:
                opt = 3
            else:
                # Option 1: activate 1 Underground Militia, remove 1 enemy
                opt = 1
            try:
                partisans.execute(state, self.faction, {}, sid, option=opt)
                return True
            except Exception:
                continue
        return False

    def _try_skirmish(self, state: Dict) -> bool:
        """P12: Skirmish (Max 1).
        Priority: first to remove a British Fort; within that first to add
        most Rebel Control then to remove most British Control, then random.
        """
        if state["resources"][self.faction] == 0:
            return False
        refresh_control(state)
        ctrl = state.get("control", {})
        candidates = []
        for sid, sp in state["spaces"].items():
            if not sp.get(C.REGULAR_PAT, 0):
                continue
            has_fort = sp.get(C.FORT_BRI, 0)
            enemy_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            has_enemy = has_fort or enemy_cubes
            if not has_enemy:
                continue
            adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
            key = (-has_fort, -adds_rebel_ctrl, -removes_brit_ctrl, state["rng"].random())
            candidates.append((key, sid))
        if not candidates:
            return False
        candidates.sort()
        for _, sid in candidates:
            sp = state["spaces"][sid]
            has_fort = sp.get(C.FORT_BRI, 0)
            enemy_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            # Option 3: remove a British Fort (requires no enemy cubes,
            # costs 1 own Continental)
            if has_fort and not enemy_cubes:
                opt = 3
            else:
                # Option 1: remove 1 enemy cube (no self-cost)
                opt = 1
            try:
                skirmish.execute(state, self.faction, {}, sid, option=opt)
                return True
            except Exception:
                continue
        return False

    def _try_persuasion(self, state: Dict) -> bool:
        ctrl = state.get("control", {})
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if ctrl.get(sid) == "REBELLION" and sp.get(C.MILITIA_U, 0)
        ]
        if not spaces:
            return False
        spaces.sort(key=lambda n: (-state["spaces"][n].get(C.FORT_PAT, 0), -_MAP_DATA[n]["population"]))
        persuasion.execute(state, self.faction, {}, spaces=spaces[:3])
        return True

    # ===================================================================
    #  DECISION‑HELPER FUNCTIONS
    # ===================================================================
    def _rally_preferred(self, state: Dict) -> bool:
        """P9 decision: Rally if would place Fort OR 1D6 > Underground Militia."""
        avail_forts = state["available"].get(C.FORT_PAT, 0)
        if avail_forts and any(
            self._rebel_group_size(sp) >= 4 and sp.get(C.FORT_PAT, 0) == 0
            for sp in state["spaces"].values()
        ):
            return True
        hidden = sum(sp.get(C.MILITIA_U, 0) for sp in state["spaces"].values())
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Rally‑test 1D6", roll))
        return roll > hidden

    def _rabble_possible(self, state: Dict) -> bool:
        return any(
            self._support_level(state, sid) > C.ACTIVE_OPPOSITION
            for sid in state["spaces"]
        )

    # ===================================================================
    #  EVENT‑VS‑COMMAND BULLETS  (P2)
    # ===================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        # Patriots play SHADED events per flowchart P2
        text = card.get("shaded_event", "") or ""
        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # • Support > Opposition & event shifts Support/Opposition in Rebel favor
        if sup > opp and any(k in text for k in ("Support", "Opposition")):
            return True
        # • Places Underground Militia in Active Opposition or Village space with none
        if "Militia" in text:
            return True
        # • Places a Patriot Fort or removes an Indian Village
        if "Fort" in text or "Village" in text:
            return True
        # • Adds 3+ Patriot Resources
        if "Resources" in text and "Patriot" in text:
            return True
        # • Event is effective, Patriots have 25+ pieces on the map, and D6 rolls 5+
        pieces_on_map = sum(
            sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            + sp.get(C.FORT_PAT, 0)
            for sp in state["spaces"].values()
        )
        if pieces_on_map >= 25:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Event D6", roll))
            if roll >= 5:
                return True
        return False
