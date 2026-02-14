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
    faction = C.INDIANS

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
        push_history(state, "INDIANS PASS")

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
        # I8: "If Indian Resources = 0, Trade if possible."
        if state.get("resources", {}).get(C.INDIANS, 0) == 0:
            self._trade(state)
            return
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

        # Priority: first where Plunder possible (WP > Rebels), within each highest Pop
        def score(space: str) -> Tuple[int, int]:
            sp = state["spaces"][space]
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            wp_total = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            pop = _MAP_DATA.get(space, {}).get("population", 0)
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

        raid.execute(state, C.INDIANS, {}, selected, move_plan=move_plan)
        return True

    # ------------------------------------------------------------------
    # PLUNDER  (Special Activity)  -------------------------------------
    def _can_plunder(self, state: Dict) -> bool:
        if state["resources"][C.PATRIOTS] == 0:
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
        """I5: Plunder in a Raid space with more WP than Rebels, highest Pop."""
        # Filter to spaces affected by the Raid command
        raid_spaces = state.get("_turn_affected_spaces", set())
        choices = []
        for sid in raid_spaces:
            sp = state["spaces"].get(sid, {})
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            if wp > rebels and wp > 0:
                choices.append((_MAP_DATA.get(sid, {}).get("population", 0), sid))
        if not choices:
            return False
        target = max(choices)[1]
        plunder.execute(state, C.INDIANS, {"raid_active": True}, target)
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
        """I7: Gather (Max 4 spaces).

        Priority bullets:
        1. Cornplanter active → spaces with 2+ WP; else 3+ WP
        2. First in a Province with 1+ Villages, then highest Pop
        3. Place Villages, then place War Parties
        4. Build a Village in each space with 3+ WP and no Village
        """
        # Determine WP threshold based on Cornplanter
        corn_loc = leader_location(state, "LEADER_CORNPLANTER")
        wp_threshold = 2 if corn_loc else 3

        # Select spaces with enough WP, prioritising Village provinces then Pop
        candidates = []
        for sid, sp in state["spaces"].items():
            total_wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            if total_wp < wp_threshold:
                continue
            is_prov = 1 if _MAP_DATA.get(sid, {}).get("type") == "Province" else 0
            has_village = 1 if sp.get(C.VILLAGE, 0) >= 1 else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            candidates.append((-is_prov * has_village, -pop, state["rng"].random(), sid))
        candidates.sort()

        selected = [sid for _, _, _, sid in candidates[:4]]
        if not selected:
            return False

        # Determine which spaces should get a Village
        build_village = set()
        for sid in selected:
            sp = state["spaces"][sid]
            total_wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            if total_wp >= 3 and sp.get(C.VILLAGE, 0) == 0:
                build_village.add(sid)

        gather.execute(
            state, C.INDIANS, {}, selected,
            build_village=build_village if build_village else None,
        )
        return True

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
        """I8: War Path, first to remove a Patriot Fort, then most Rebel pieces,
        within that first in a Province with 1+ Villages, then random.
        """
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
            # "within that first in a Province with 1+ Villages"
            is_prov = 1 if _MAP_DATA.get(sid, {}).get("type") == "Province" else 0
            has_village = 1 if sp.get(C.VILLAGE, 0) >= 1 else 0
            prov_vill = is_prov * has_village
            choices.append((fort, enemy, prov_vill, random.random(), sid))
        if not choices:
            return False
        target = max(choices)[-1]
        return war_path.execute(state, C.INDIANS, {}, target)

    # ------------------------------------------------------------------
    # MARCH  (Command)  -------------------------------------------------
    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0) for sp in state["spaces"].values())

    def _march(self, state: Dict) -> bool:
        """I10: March to get 3+ WP in Neutral/Passive space with room for Village,
        then remove most Rebel Control where no Active Support.
        """
        # Move Underground then Active WP from largest stack
        origins = [
            (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0), sid)
            for sid, sp in state["spaces"].items()
            if (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)) >= 2
        ]
        if not origins:
            return False
        _, origin = max(origins)
        # Destination: Neutral or Passive (0, +1, -1) with room for Village
        best_dst = None
        best_key = (-1, -1)
        for dst in _adjacent(origin):
            if dst not in state.get("spaces", {}):
                continue
            dsp = state["spaces"][dst]
            sup = self._support_level(state, dst)
            is_neutral_or_passive = sup in (C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION)
            if not is_neutral_or_passive:
                continue
            if dsp.get(C.VILLAGE, 0) > 0:
                continue  # already has Village, no "room"
            pop = _MAP_DATA.get(dst, {}).get("population", 0)
            key = (pop, random.random())
            if key > best_key:
                best_key = key
                best_dst = dst
        if not best_dst:
            return False
        march.execute(state, C.INDIANS, {}, [origin], [best_dst], bring_escorts=False, limited=False)
        return True

    # ------------------------------------------------------------------
    # SCOUT  (Command)  -------------------------------------------------
    def _space_has_wp_and_regulars(self, state: Dict) -> bool:
        """I9: Space with Underground War Party and British Regulars?"""
        return any(
            sp.get(C.REGULAR_BRI, 0) and sp.get(C.WARPARTY_U, 0)
            for sp in state["spaces"].values()
        )

    def _can_scout(self, state: Dict) -> bool:
        return self._space_has_wp_and_regulars(state)

    def _scout(self, state: Dict) -> bool:
        """I12: Scout (Max 3 WP moved).
        Origin: space with Underground WP + British Regulars.
        Destination priority: first to space with Patriot Fort, then
        Villages with enemy, then most Rebel Control, then random.
        """
        refresh_control(state)
        ctrl = state.get("control", {})
        choices = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) == 0:
                continue
            wp_u = sp.get(C.WARPARTY_U, 0)
            if wp_u == 0:
                continue
            fort = 1 if sp.get(C.FORT_PAT, 0) else 0
            choices.append((fort, wp_u, sid))
        if not choices:
            return False
        _, _, origin = max(choices)

        # Destination priority per reference
        dests = _adjacent(origin)
        if not dests:
            return False
        dest_scores = []
        for dst in dests:
            if dst not in state.get("spaces", {}):
                continue
            dsp = state["spaces"][dst]
            has_pat_fort = 1 if dsp.get(C.FORT_PAT, 0) else 0
            has_village = dsp.get(C.VILLAGE, 0)
            has_enemy = (dsp.get(C.REGULAR_PAT, 0) + dsp.get(C.REGULAR_FRE, 0)
                         + dsp.get(C.MILITIA_A, 0) + dsp.get(C.MILITIA_U, 0))
            village_enemy = 1 if (has_village and has_enemy > 0) else 0
            # "most Rebel Control" → rebellion-controlled spaces first
            rebel_ctrl = 1 if ctrl.get(dst) == "REBELLION" else 0
            key = (has_pat_fort, village_enemy, rebel_ctrl, random.random())
            dest_scores.append((key, dst))
        if not dest_scores:
            return False
        _, target = max(dest_scores)
        sp = state["spaces"][origin]
        # Calculate how many WP to move (Max 3 per Scout)
        wp_u = sp.get(C.WARPARTY_U, 0)
        n_wp = min(wp_u, 3)
        if n_wp == 0:
            return False
        # Scout requires at least 1 British Regular (§3.2.4)
        n_regs = min(sp.get(C.REGULAR_BRI, 0), n_wp)
        if n_regs == 0:
            return False
        scout.execute(
            state, C.INDIANS, {}, origin, target,
            n_warparties=n_wp, n_regulars=n_regs, skirmish=True,
        )
        return True

    # ------------------------------------------------------------------
    # TRADE  (Special Activity)  ---------------------------------------
    def _trade(self, state: Dict) -> bool:
        """I11: Trade in up to 3 spaces with Underground WP and a Village."""
        spaces = [
            sid for sid, sp in state.get("spaces", {}).items()
            if sp.get(C.WARPARTY_U, 0) > 0 and sp.get(C.VILLAGE, 0) > 0
        ]
        if not spaces:
            return False

        # British bot OPS: "roll 1D6; if result < Brit Resources, offer to
        # transfer half (round up) rolled Resources to Indians."
        transfer = 0
        brit_res = state.get("resources", {}).get(C.BRITISH, 0)
        if state.get("resources", {}).get(C.INDIANS, 0) < brit_res:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Indian Trade D6", roll))
            if roll < brit_res:
                transfer = -(-roll // 2)  # ceil(roll / 2)
                push_history(state, f"Indian Trade: British offer {transfer} (rolled {roll})")

        traded = False
        for target in spaces[:3]:
            try:
                trade.execute(state, C.INDIANS, {}, target, transfer=transfer)
                traded = True
                transfer = 0  # Only first trade gets British offer
            except Exception:
                continue
        return traded

    # ==================================================================
    #  EVENT‑VS‑COMMAND BULLETS (I2)
    # ==================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Apply the unshaded‑event bullets from node I2."""
        text = card.get("unshaded_event", "")
        support_map = state.get("support", {})
        support = sum(max(0, lvl) for lvl in support_map.values())
        opposition = sum(max(0, -lvl) for lvl in support_map.values())

        # I2 bullets (from indian bot flowchart and reference.txt):
        # • Opposition > Support and Event shifts Support/Opposition in Royalist favor
        if opposition > support and any(k in text for k in ("Support", "Opposition")):
            return True
        # • Event places at least one Indian Village or grants free Gather
        if "Village" in text or "Gather" in text:
            return True
        # • Event removes a Patriot Fort
        if "Fort" in text and "Patriot" in text and "remove" in text.lower():
            return True
        # • Event is effective, 4+ Villages on the map, and a D6 rolls 5+
        villages_on_map = sum(
            sp.get(C.VILLAGE, 0) for sp in state["spaces"].values()
        )
        if villages_on_map >= 4:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Event D6", roll))
            if roll >= 5:
                return True
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
