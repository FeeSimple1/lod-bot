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

# ---------------------------------------------------------------------------
#  Helper constants
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
CITIES = [n for n, d in _MAP_DATA.items() if d.get("type") == "City"]


class PatriotBot(BaseBot):
    """Full non‑player Patriot AI."""
    faction = "PATRIOTS"             # canonical faction key

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    def _event_directive(self, card_id: int) -> str:
        """
        Patriots use the existing Brown‑Bess instruction table keyed as 'PATRIOTS'.
        Keeping the table as‑is while this bot uses the canonical 'PATRIOTS' key.
        """
        return EI.PATRIOTS.get(card_id, "normal")

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
            # If Rabble‑Rousing impossible → Rally
            return self._execute_rally(state)
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
        refresh_control(state)
        for sid, sp in state["spaces"].items():
            if self._battle_strength(sp) > self._british_strength(sp):
                return True
        return False

    def _execute_battle(self, state: Dict) -> bool:
        """Select targets per P4 bullets and resolve Battle."""
        refresh_control(state)
        targets = []
        for sid, sp in state["spaces"].items():
            if self._battle_strength(sp) > self._british_strength(sp):
                has_wash = sp.get("leader") == "LEADER_WASHINGTON"
                pop = sp.get("population", 0)
                villages = sp.get(C.VILLAGE, 0)
                targets.append((-has_wash, -pop, -villages, random.random(), sid))
        if not targets:
            return False
        targets.sort()
        chosen = [sid for *_, sid in targets]
        battle.execute(state, self.faction, {}, chosen)
        return True

    def _battle_strength(self, sp: Dict) -> int:
        rebels = (
            sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
            sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        )
        # include French if present
        return rebels

    def _british_strength(self, sp: Dict) -> int:
        royal = (
            sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) +
            sp.get(C.WARPARTY_A, 0)  # active Indians only per rule
        )
        return royal

    # ---------- March (P5) --------------------------------------------
    def _execute_march(self, state: Dict) -> bool:
        refresh_control(state)
        # Origins with largest rebel groups
        origins = sorted(
            (self._rebel_group_size(sp), sid)
            for sid, sp in state["spaces"].items()
            if self._rebel_group_size(sp) >= 3
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
                limited=True,
            )
            used += 1
        return used > 0

    def _rebel_group_size(self, sp: Dict) -> int:
        return (
            sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
            sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        )

    def _march_destination(self, state: Dict, origin: str) -> str | None:
        """Pick destination per bullet list (Villages > Cities > other)."""
        best = None
        best_key = (-1, -1, -1)
        for token in _MAP_DATA[origin]["adj"]:
            for dst in token.split("|"):
                dsp = state["spaces"][dst]
                if dsp.get("control") == "REBELLION":
                    continue
                # lose no Rebel Control in origin/destination test left to command layer
                has_village = dsp.get(C.VILLAGE, 0)
                is_city = dst in CITIES
                pop = dsp.get("population", 0)
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
        forts_to_build = set(fort_targets[:2])

        # Militia placement – favour Forts lacking other Patriot pieces
        militia_spaces = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.FORT_PAT, 0) and self._rebel_group_size(sp) == sp.get(C.MILITIA_U, 0):
                militia_spaces.append(sid)
        if not militia_spaces:
            # else try to flip control elsewhere
            for sid, sp in state["spaces"].items():
                if sp.get("control") != "REBELLION":
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
        if state["resources"][self.faction] == 0:
            return False  # rule: Persuasion instead
        for sid, sp in state["spaces"].items():
            if sp.get(C.MILITIA_U, 0) and (
                sp.get(C.VILLAGE, 0) or
                sp.get(C.WARPARTY_A, 0) or
                sp.get(C.REGULAR_BRI, 0) or
                sp.get(C.TORY, 0)
            ):
                try:
                    partisans.execute(state, self.faction, {}, sid, option=1)
                    return True
                except Exception:
                    continue
        return False

    def _try_skirmish(self, state: Dict) -> bool:
        if state["resources"][self.faction] == 0:
            return False
        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_PAT, 0) and (
                sp.get(C.FORT_BRI, 0) or sp.get(C.REGULAR_BRI, 0) or sp.get(C.TORY, 0)
            ):
                try:
                    skirmish.execute(state, self.faction, {}, sid, option=1)
                    return True
                except Exception:
                    continue
        return False

    def _try_persuasion(self, state: Dict) -> bool:
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if sp.get("control") == "REBELLION" and sp.get(C.MILITIA_U, 0)
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
        text = card.get("unshaded_event", "")
        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # • Support > Opposition & event shifts Support/Opposition
        if sup > opp and any(k in text for k in ("Support", "Opposition")):
            return True
        # • Places Militia underground, Fort, or removes Village
        if any(k in text for k in ("Militia", "Fort", "Village")):
            return True
        # • Adds ≥3 Patriot Resources
        if "Resources" in text:
            return True
        # • Ineffective die‑roll bullet handled by BaseBot after effectiveness test
        return False
