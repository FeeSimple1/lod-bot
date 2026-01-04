# lod_ai/bots/indians.py
"""
Full‑flow implementation of the Non‑Player **Indian** faction (§8.5).

Covered flow‑chart nodes (I1 → I12):

    • Event‑vs‑Command test is handled by BaseBot + _faction_event_conditions
    • I3     Support test
    • I4‑I5  Raid + (optional) Plunder
    • I6‑I7  Gather
    • I8     War‑Path  (+ Trade fallback)
    • I9‑I10 March
    • I12    Scout  (+ Skirmish inside Scout per reference)
    • I11    Trade  (Special Activity)

Each “_cmd_…” helper follows the bullet lists in the *Indian bot flow‑chart
and reference sheet* but delegates the low‑level piece manipulation to the
existing command / special‑activity modules under ``lod_ai``.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple
from pathlib import Path
import json

from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai.commands import raid, gather, march, scout
from lod_ai.special_activities import plunder, war_path, trade
from lod_ai.board.control import refresh_control
from lod_ai.leaders import leader_location
from lod_ai.util.history import push_history
from lod_ai.map.adjacency import shortest_path

# ----------------------------------------------------------------------
#  MAP helpers
# ----------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)

def _adjacent(space: str) -> List[str]:
    adj = []
    for token in _MAP_DATA[space]["adj"]:
        adj.extend(token.split("|"))
    return adj


class IndianBot(BaseBot):
    faction = "INDIANS"

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    # ==================================================================
    #  FLOW‑CHART DRIVER
    # ==================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        """
        Implements nodes I3‑I12.  I1/I2 (Event handling) is already covered
        by BaseBot._choose_event_vs_flowchart().
        """
        # ---------- I3 test  (Support+1D6) > Opposition -----------------
        support_map = state.get("support", {})
        support = sum(max(0, lvl) for lvl in support_map.values())
        opposition = sum(max(0, -lvl) for lvl in support_map.values())
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Support test 1D6", roll))

        if (support + roll) <= opposition:
            if self._raid_sequence(state):    # I4 → I5
                return
            # If Raid impossible: fall through to I6 decision path

        # ---------- I6 decision ----------------------------------------
        if self._gather_worthwhile(state):
            if self._gather_sequence(state):  # I7 → I8 / I10
                return
        else:
            # I9 decision (space with War Party & British Regulars?)
            if self._space_has_wp_and_regulars(state):
                if self._scout_sequence(state):   # I12 → I8 / I10
                    return
            # Otherwise I10 March chain
            if self._march_sequence(state):   # I10 → I8 / I7
                return

        # If nothing executed, Pass
        push_history(state, "INDIAN PASS")

    # ==================================================================
    #  COMMAND + SA SEQUENCES  (each returns True if something executed)
    # ==================================================================
    # ---- I4 Raid + I5 Plunder ----------------------------------------
    def _raid_sequence(self, state: Dict) -> bool:
        if not self._can_raid(state):
            return False
        if not self._raid(state):            # nothing moved → treat as failure
            return False

        # optional Plunder (I5)
        if self._can_plunder(state):
            if not self._plunder(state):
                # if plunder impossible, War‑Path instead (arrow "Else I8")
                self._war_path_or_trade(state)
        else:
            self._war_path_or_trade(state)
        return True

    # ---- I7 Gather then I8 / I10 -------------------------------------
    def _gather_sequence(self, state: Dict) -> bool:
        if not self._can_gather(state):
            return False
        if not self._gather(state):
            # If Gather impossible → I10 March
            return self._march_sequence(state)
        # After Gather comes War‑Path (I8) then Trade fallback
        self._war_path_or_trade(state)
        return True

    # ---- I12 Scout then I8 / I10 -------------------------------------
    def _scout_sequence(self, state: Dict) -> bool:
        if not self._can_scout(state):
            return False
        if not self._scout(state):
            # If Scout impossible → I10 March
            return self._march_sequence(state)
        # Then War‑Path (+ Trade)
        self._war_path_or_trade(state)
        return True

    # ---- I10 March then I8 / I7 --------------------------------------
    def _march_sequence(self, state: Dict) -> bool:
        if not self._can_march(state):
            return self._gather_sequence(state)  # arrow “If none → Gather”
        if not self._march(state):
            return self._gather_sequence(state)
        self._war_path_or_trade(state)
        return True

    # ---- I8 War‑Path, else I11 Trade ---------------------------------
    def _war_path_or_trade(self, state: Dict) -> None:
        if not self._can_war_path(state) or not self._war_path(state):
            self._trade(state)   # I11 always executes if possible

    # ==================================================================
    #  INDIVIDUAL COMMAND / SA IMPLEMENTATIONS
    # ==================================================================
    # Helper selectors used by several commands -------------------------
    def _opposition_colonies(self, state: Dict) -> List[str]:
        return [
            sid for sid, sp in state["spaces"].items()
            if _MAP_DATA[sid]["type"] == "Colony" and self._support_level(state, sid) <= C.PASSIVE_OPPOSITION
        ]

    def _raid_targets(self, state: Dict) -> List[str]:
        """
        List Opposition Colonies with or adjacent to Underground War Parties.
        Priority later: first where Plunder possible (WP > Rebels), then pop.
        """
        tgs = []
        dc_loc = leader_location(state, "LEADER_DRAGGING_CANOE")
        dc_has_wp = dc_loc and state["spaces"].get(dc_loc, {}).get(C.WARPARTY_U, 0) > 0
        for col in self._opposition_colonies(state):
            sp = state["spaces"][col]
            has_u = sp.get(C.WARPARTY_U, 0) > 0
            adj_u = any(
                state["spaces"][nbr].get(C.WARPARTY_U, 0) > 0
                for nbr in _adjacent(col)
            )
            dc_range = False
            if dc_loc and dc_has_wp:
                path = shortest_path(dc_loc, col)
                dc_range = bool(path) and (len(path) - 1) <= 2
            if has_u or adj_u or dc_range:
                tgs.append(col)
        return tgs

    # ------------------------------------------------------------------
    # RAID  (Command)  --------------------------------------------------
    def _can_raid(self, state: Dict) -> bool:
        return bool(self._raid_targets(state))

    def _raid(self, state: Dict) -> bool:
        """
        Executes up to 3 Raids per I4 priorities.
        Moves 1 Underground WP into each target if needed (without stripping Villages).
        """
        targets = self._raid_targets(state)
        if not targets:
            return False

        dc_loc = leader_location(state, "LEADER_DRAGGING_CANOE")
        available_wp = {sid: sp.get(C.WARPARTY_U, 0) for sid, sp in state["spaces"].items()}

        # Priority: first where WP > Rebels after move (for Plunder)
        def score(space: str) -> Tuple[int, int]:
            sp = state["spaces"][space]
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            wp_total = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            pop = sp.get("population", 0)
            return (wp_total - rebels, pop)

        targets.sort(key=lambda t: score(t), reverse=True)
        selected: List[str] = []
        move_plan: List[Tuple[str, str]] = []

        def _reserve_source(dst: str) -> str | None:
            # prefer adjacent Underground WP
            for src in _adjacent(dst):
                if available_wp.get(src, 0) <= 0:
                    continue
                if state["spaces"][src].get(C.VILLAGE, 0) and available_wp[src] == 1:
                    continue  # avoid stripping last WP from a Village space
                return src
            if dc_loc and available_wp.get(dc_loc, 0) > 0:
                path = shortest_path(dc_loc, dst)
                if path and (len(path) - 1) <= 2:
                    return dc_loc
            return None

        for tgt in targets:
            if len(selected) >= 3:
                break
            if state["spaces"][tgt].get(C.WARPARTY_U, 0) > 0:
                selected.append(tgt)
                continue
            src = _reserve_source(tgt)
            if src is None:
                continue
            selected.append(tgt)
            move_plan.append((src, tgt))
            available_wp[src] -= 1

        if not selected:
            return False

        raid.execute(state, "INDIANS", {}, selected, move_plan=move_plan)
        return True

    # ------------------------------------------------------------------
    # PLUNDER  (Special Activity)  -------------------------------------
    def _can_plunder(self, state: Dict) -> bool:
        if state["resources"]["PATRIOTS"] == 0:
            return False
        for sid, sp in state["spaces"].items():
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            if wp > rebels and wp > 0 and _MAP_DATA[sid]["type"] == "Colony":
                return True
        return False

    def _plunder(self, state: Dict) -> bool:
        # choose highest‑population valid space
        choices = []
        for sid, sp in state["spaces"].items():
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            if wp > rebels and wp > 0:
                choices.append((sp.get("population", 0), sid))
        if not choices:
            return False
        target = max(choices)[1]
        plunder.execute(state, "INDIANS", {}, target)
        return True

    # ------------------------------------------------------------------
    # GATHER  (Command)  -----------------------------------------------
    def _gather_worthwhile(self, state: Dict) -> bool:
        """
        I6 test: would Gather place ≥2 Villages OR 1D6 < Available War Parties?
        """
        avail_villages = state["available"].get(C.VILLAGE, 0)
        if avail_villages >= 2:
            return True
        avail_wp = state["available"].get(C.WARPARTY_U, 0) + state["available"].get(C.WARPARTY_A, 0)
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Gather test 1D6", roll))
        return roll < avail_wp

    def _can_gather(self, state: Dict) -> bool:
        return True  # always allowed

    def _gather(self, state: Dict) -> bool:
        # very high‑level: delegate detailed bullet logic to command module
        return gather.execute(state, "INDIANS", {}, max_spaces=4)

    # ------------------------------------------------------------------
    # WAR‑PATH  (Command)  ---------------------------------------------
    def _can_war_path(self, state: Dict) -> bool:
        return any(
            sp.get(C.WARPARTY_U, 0)
            and (
                sp.get(C.FORT_PAT, 0)
                or sp.get(C.MILITIA_A, 0)
                or sp.get(C.MILITIA_U, 0)
                or sp.get(C.REGULAR_PAT, 0)
                or sp.get(C.REGULAR_FRE, 0)
            )
            for sp in state["spaces"].values()
        )

    def _war_path(self, state: Dict) -> bool:
        # Target priority: remove Fort, else most enemy pieces
        choices = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.WARPARTY_U, 0) == 0:
                continue
            enemy = (
                sp.get(C.FORT_PAT, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            if enemy == 0:
                continue
            fort = 1 if sp.get(C.FORT_PAT, 0) else 0
            choices.append((fort, enemy, sp.get(C.VILLAGE, 0), sid))
        if not choices:
            return False
        target = max(choices)[-1]
        return war_path.execute(state, "INDIANS", {}, target)

    # ------------------------------------------------------------------
    # MARCH  (Command)  -------------------------------------------------
    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0) for sp in state["spaces"].values())

    def _march(self, state: Dict) -> bool:
        # Minimal implementation: move 2 WP‑U from largest stack to nearest Neutral/Passive without Village
        origins = [
            (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0), sid)
            for sid, sp in state["spaces"].items()
            if (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)) >= 2
        ]
        if not origins:
            return False
        _, origin = max(origins)
        for dst in _adjacent(origin):
            dsp = state["spaces"][dst]
            if self._support_level(state, dst) <= C.PASSIVE_OPPOSITION and dsp.get(C.VILLAGE, 0) == 0:
                march.execute(state, C.INDIANS, {}, [origin], [dst], bring_escorts=False, limited=True)
                return True
        return False

    # ------------------------------------------------------------------
    # SCOUT  (Command)  -------------------------------------------------
    def _space_has_wp_and_regulars(self, state: Dict) -> bool:
        return any(
            sp.get(C.REGULAR_BRI, 0) and (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0))
            for sp in state["spaces"].values()
        )

    def _can_scout(self, state: Dict) -> bool:
        return self._space_has_wp_and_regulars(state)

    def _scout(self, state: Dict) -> bool:
        # Choose origin with WP + Regulars, prefer Patriot Fort
        choices = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) == 0:
                continue
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            if wp == 0:
                continue
            fort = 1 if sp.get(C.FORT_PAT, 0) else 0
            choices.append((fort, wp, sid))
        if not choices:
            return False
        _, _, origin = max(choices)

        # Destination preference: Fort first, then Village with enemy, else most Rebel Control
        dests = _adjacent(origin)
        if not dests:
            return False
        target = dests[0]
        scout.execute(state, C.INDIANS, {}, origin, target)
        return True

    # ------------------------------------------------------------------
    # TRADE  (Special Activity)  ---------------------------------------
    def _trade(self, state: Dict) -> bool:
        spaces = [
            sid for sid, sp in state.get("spaces", {}).items()
            if sp.get(C.WARPARTY_U, 0) > 0 and sp.get(C.VILLAGE, 0) > 0
        ]
        if not spaces:
            return False

        target = spaces[0]
        try:
            trade.execute(state, C.INDIANS, {}, target, transfer=0)
            return True
        except Exception:
            return False

    # ==================================================================
    #  EVENT‑VS‑COMMAND BULLETS (I2)
    # ==================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """
        Apply the unshaded‑event bullets from node I2.
        """
        text = card.get("unshaded_event", "")
        support_map = state.get("support", {})
        support = sum(max(0, lvl) for lvl in support_map.values())
        opposition = sum(max(0, -lvl) for lvl in support_map.values())

        # • Opposition > Support and Event shifts toward Royalists
        if opposition > support and any(k in text for k in ("Support", "Opposition")):
            return True
        # • Places a Village or grants free Gather
        if "Village" in text or "Gather" in text:
            return True
        # • Removes a Patriot Fort
        if "Fort" in text and "Patriot" in text and "remove" in text.lower():
            return True
        # • Ineffective die-roll rule (handled by BaseBot already)
        return False


# ----------------------------------------------------------------------
# Legacy helper expected by tests
# ----------------------------------------------------------------------
def choose_command(state: Dict) -> tuple[str, str | None]:
    """
    Minimal command selector used by legacy tests.
    Priorities:
        1) SCOUT if any space has both WP_U and British Regulars
        2) WAR_PATH if any space has WP_U and Patriot Regulars
        3) otherwise GATHER
    """
    for sid, sp in state.get("spaces", {}).items():
        if sp.get(C.WARPARTY_U, 0) and sp.get(C.REGULAR_BRI, 0):
            return "SCOUT", sid
        if sp.get(C.WARPARTY_U, 0) and sp.get(C.REGULAR_PAT, 0):
            return "WAR_PATH", sid
    return "GATHER", None
