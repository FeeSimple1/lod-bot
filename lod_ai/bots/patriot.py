# lod_ai/bots/patriot.py
"""
Full-flow implementation of the Non-Player **Patriot** bot (§8.7).

Flow-chart nodes covered (P1 -> P13):

  - Event-vs-Command handled by BaseBot._choose_event_vs_flowchart().
  - P3  Resources test
  - P6  Battle-vs-other decision
  - P4  Battle    -> P8 loop  (Win-the-Day: free Rally + Blockade move)
  - P5  March     -> P8 loop  (full 2-phase with control constraints)
  - P7  Rally     -> P8 loop  (all 6 bullets)
  - P11 Rabble-Rousing fallback -> P8 loop
  - P8  Partisans -> Skirmish -> Persuasion chain
  - P13 Persuasion (resource injection) terminal

OPS Summary: Supply, Redeploy, Desertion, BS trigger, Leader Movement.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import json
from pathlib import Path

from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots import event_instructions as EI
from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai import rules_consts as C
from lod_ai.commands import rally, march, battle, rabble_rousing
from lod_ai.special_activities import partisans, skirmish, persuasion
from lod_ai.board.control import refresh_control
from lod_ai.util.history import push_history
from lod_ai.leaders import leader_location
from lod_ai.map import adjacency as map_adj

# ---------------------------------------------------------------------------
#  Helper constants
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
CITIES = [n for n, d in _MAP_DATA.items() if d.get("type") == "City"]

# Rebel piece tags for control simulation
_REBEL_TAGS = (C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT)
_ROYALIST_TAGS = (C.REGULAR_BRI, C.TORY, C.WARPARTY_A, C.WARPARTY_U, C.FORT_BRI, C.VILLAGE)


class PatriotBot(BaseBot):
    """Full non-player Patriot AI."""
    faction = C.PATRIOTS             # canonical faction key

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    def _event_directive(self, card_id: int) -> str:
        return EI.PATRIOTS.get(card_id, "normal")

    # ===================================================================
    #  CONTROL SIMULATION HELPERS
    # ===================================================================
    @staticmethod
    def _rebel_pieces_in(sp: Dict) -> int:
        """Count all Rebellion pieces (cubes + bases) in a space dict."""
        return sum(sp.get(t, 0) for t in _REBEL_TAGS)

    @staticmethod
    def _royalist_pieces_in(sp: Dict) -> int:
        """Count all Royalist pieces (cubes + bases) in a space dict."""
        return sum(sp.get(t, 0) for t in _ROYALIST_TAGS)

    def _would_lose_rebel_control(self, state: Dict, sid: str,
                                   to_remove: Dict[str, int]) -> bool:
        """Return True if removing *to_remove* pieces from *sid*
        would cause Rebellion to lose control."""
        ctrl = state.get("control", {}).get(sid)
        if ctrl != "REBELLION":
            return False  # nothing to lose
        sp = state["spaces"][sid]
        rebels_after = 0
        royalist = 0
        for tag in _REBEL_TAGS:
            rebels_after += max(0, sp.get(tag, 0) - to_remove.get(tag, 0))
        for tag in _ROYALIST_TAGS:
            royalist += sp.get(tag, 0)
        return rebels_after <= royalist

    def _would_gain_rebel_control(self, state: Dict, sid: str,
                                   to_add: int = 0) -> bool:
        """Return True if adding *to_add* Rebel pieces to *sid*
        would gain Rebellion control (assuming currently not REBELLION)."""
        ctrl = state.get("control", {}).get(sid)
        if ctrl == "REBELLION":
            return False  # already controlled
        sp = state["spaces"][sid]
        rebels = self._rebel_pieces_in(sp) + to_add
        royalist = self._royalist_pieces_in(sp)
        return rebels > royalist

    # ===================================================================
    #  MOVABLE PIECES HELPER (for March leave-behind rules)
    # ===================================================================
    def _movable_from(self, state: Dict, sid: str) -> Dict[str, int]:
        """Compute movable Patriot pieces from *sid* respecting P5 constraints:
        - Leave 1 Active Patriot unit with each Patriot Fort
        - Leave 1 Patriot unit (Underground preferred) where no Active Opposition
        - Lose no Rebel Control
        Returns dict of {tag: max_movable_count}.
        """
        sp = state["spaces"][sid]
        avail = {
            C.REGULAR_PAT: sp.get(C.REGULAR_PAT, 0),
            C.MILITIA_A: sp.get(C.MILITIA_A, 0),
            C.MILITIA_U: sp.get(C.MILITIA_U, 0),
            C.REGULAR_FRE: sp.get(C.REGULAR_FRE, 0),
        }
        total_movable = sum(avail.values())
        if total_movable == 0:
            return {}

        retain = 0

        # Rule: Leave 1 Active Patriot unit with each Patriot Fort
        if sp.get(C.FORT_PAT, 0) > 0:
            retain = max(retain, 1)

        # Rule: Leave 1 Patriot unit where no Active Opposition
        support = self._support_level(state, sid)
        if support > C.ACTIVE_OPPOSITION:
            retain = max(retain, 1)

        # Rule: Lose no Rebel Control
        ctrl = state.get("control", {}).get(sid)
        if ctrl == "REBELLION":
            royalist = self._royalist_pieces_in(sp)
            # Need rebels_after > royalist
            # rebels_after = total_rebel - moved
            # So moved < total_rebel - royalist
            total_rebel = self._rebel_pieces_in(sp)
            # Cannot remove Fort, so movable rebels only = cubes
            movable_rebel = total_movable
            max_can_move = total_rebel - royalist - 1  # must keep strict majority
            if max_can_move < 0:
                max_can_move = 0
            retain = max(retain, total_movable - max_can_move)

        if retain >= total_movable:
            return {}

        can_move = total_movable - retain

        # Build result: prefer moving Active Militia first (keep Underground for leave-behind)
        result = {}
        remaining = can_move
        # Move Continentals first, then Active Militia, then French Regulars
        # Keep Underground Militia for last (preferred to leave behind)
        for tag in [C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE, C.MILITIA_U]:
            take = min(remaining, avail.get(tag, 0))
            if take > 0:
                result[tag] = take
                remaining -= take
            if remaining <= 0:
                break

        return result

    # ===================================================================
    #  BRILLIANT STROKE LimCom  (§8.3.7)
    # ===================================================================
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk Patriot flowchart for the first valid Limited Command
        that can involve Washington in his current space."""
        leader_space = self._find_bs_leader_space(state)
        if not leader_space:
            return None

        if state.get("resources", {}).get(C.PATRIOTS, 0) <= 0:
            return None

        sp = state["spaces"].get(leader_space, {})
        refresh_control(state)

        rebel = self._rebel_cube_count(state, leader_space)
        royal = self._active_royal_count(sp)
        if rebel > 0 and royal > 0 and rebel > royal:
            return "battle"

        avail_forts = state["available"].get(C.FORT_PAT, 0)
        rebel_group = self._rebel_group_size(sp)
        if avail_forts and rebel_group >= 4 and sp.get(C.FORT_PAT, 0) == 0:
            return "rally"
        avail_militia = state["available"].get(C.MILITIA_U, 0)
        if avail_militia > 0 or rebel_group >= 4:
            return "rally"

        support = self._support_level(state, leader_space)
        if support > C.ACTIVE_OPPOSITION:
            return "rabble_rousing"

        if rebel_group >= 1:
            return "march"

        return None

    # ===================================================================
    #  FLOW-CHART DRIVER
    # ===================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # Node P3
        if state["resources"][self.faction] == 0:
            push_history(state, "PATRIOTS PASS (no Resources)")
            return

        # Node P6
        if self._battle_possible(state):
            if self._battle_chain(state):
                return
        else:
            if self._rally_preferred(state):
                if self._rally_chain(state):
                    return
            elif self._rabble_possible(state):
                if self._rabble_chain(state):
                    return
            if self._march_chain(state):
                return

        push_history(state, "PATRIOTS PASS")

    # ===================================================================
    #  EXECUTION CHAINS (with recursion guard for Rally/Rabble loop)
    # ===================================================================
    def _battle_chain(self, state: Dict) -> bool:
        if not self._execute_battle(state):
            return self._rally_chain(state)
        self._partisans_loop(state)
        return True

    def _march_chain(self, state: Dict) -> bool:
        if not self._execute_march(state):
            return self._rally_chain(state)
        self._partisans_loop(state)
        return True

    def _rally_chain(self, state: Dict, *, _from_rabble: bool = False) -> bool:
        used_persuasion = False
        if not self._execute_rally(state):
            if _from_rabble:
                return False  # prevent infinite Rally<->Rabble loop
            return self._rabble_chain(state, _from_rally=True)
        if state["resources"][self.faction] == 0:
            used_persuasion = self._try_persuasion(state)
        if not used_persuasion:
            self._partisans_loop(state)
        return True

    def _rabble_chain(self, state: Dict, *, _from_rally: bool = False) -> bool:
        used_persuasion = False
        if not self._execute_rabble(state):
            if _from_rally:
                return False  # prevent infinite Rabble<->Rally loop
            return self._rally_chain(state, _from_rabble=True)
        if state["resources"][self.faction] == 0:
            used_persuasion = self._try_persuasion(state)
        if not used_persuasion:
            self._partisans_loop(state)
        return True

    # -------------- Partisans -> Skirmish -> Persuasion ---------------
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
        """P4: Select all spaces where Rebel Force Level exceeds Royalist FL.
        §8.5.1: Include French only if French Resources > 0.
        If resources too low for all, prioritize: Washington, highest Pop,
        most Villages, random.
        Win-the-Day: free Rally (P7 priorities) + French Blockade move.
        """
        refresh_control(state)
        french_res = state["resources"].get(C.FRENCH, 0)
        targets = []
        for sid, sp in state["spaces"].items():
            pat_cubes = sp.get(C.REGULAR_PAT, 0)
            # §8.5.1: include French only if French Resources > 0
            if french_res > 0:
                fre_cubes = min(sp.get(C.REGULAR_FRE, 0), pat_cubes)
            else:
                fre_cubes = 0
            active_mil = sp.get(C.MILITIA_A, 0)
            rebel_force = pat_cubes + fre_cubes + (active_mil // 2)

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

        # §8.5.1: If Patriot Resources too low for all spaces, trim list
        pat_res = state["resources"].get(self.faction, 0)
        if pat_res < len(chosen):
            chosen = chosen[:max(pat_res, 1)]

        # Win-the-Day: select free Rally space and Blockade destination
        win_rally_space = self._best_rally_space(state)
        win_rally_kwargs = {}
        if win_rally_space:
            # Build minimal Rally kwargs for the free Rally
            sp_r = state["spaces"].get(win_rally_space, {})
            if (sp_r.get(C.FORT_PAT, 0) == 0
                    and self._rebel_group_size(sp_r) >= 4
                    and state["available"].get(C.FORT_PAT, 0) > 0):
                win_rally_kwargs["build_fort"] = {win_rally_space}

        win_blockade_dest = self._best_blockade_city(state)

        battle.execute(
            state, self.faction, {}, chosen,
            win_rally_space=win_rally_space,
            win_rally_kwargs=win_rally_kwargs if win_rally_space else None,
            win_blockade_dest=win_blockade_dest,
        )
        return True

    def _best_rally_space(self, state: Dict) -> str | None:
        """Select Rally space per P7 priorities for Win-the-Day free Rally.
        Priority: Fort placement first (Cities, highest Pop), then Militia
        placement (change Control, no Active Opposition, Cities, highest Pop).
        """
        refresh_control(state)
        ctrl = state.get("control", {})

        # Priority 1: Space where Fort can be built
        avail_forts = state["available"].get(C.FORT_PAT, 0)
        if avail_forts > 0:
            candidates = []
            for sid, sp in state["spaces"].items():
                if sp.get(C.FORT_PAT, 0) > 0:
                    continue
                bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0)
                if bases >= 2:
                    continue
                if self._rebel_group_size(sp) >= 4:
                    is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    candidates.append((-is_city, -pop, sid))
            if candidates:
                candidates.sort()
                return candidates[0][2]

        # Priority 2: Space to change Control or no Active Opposition
        candidates = []
        for sid, sp in state["spaces"].items():
            support = self._support_level(state, sid)
            changes_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            no_active_opp = 1 if support > C.ACTIVE_OPPOSITION else 0
            is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            candidates.append((-changes_ctrl, -no_active_opp, -is_city, -pop, sid))
        if candidates:
            candidates.sort()
            return candidates[0][4]
        return None

    def _best_blockade_city(self, state: Dict) -> str | None:
        """Select City with most Support for French Blockade move (P4)."""
        best = None
        best_support = -999
        for sid in CITIES:
            sup = self._support_level(state, sid)
            if sup > best_support:
                best_support = sup
                best = sid
        return best

    def _rebel_cube_count(self, state: Dict, sid: str) -> int:
        """P6: 'Rebel cubes + Leaders' = Continentals + French Regulars
        + all Rebellion leaders present (§8.5.1 says 'Leaders' plural)."""
        sp = state["spaces"].get(sid, {})
        cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        for ldr in ("LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN"):
            if leader_location(state, ldr) == sid:
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
        """P5 March: Full implementation.
        - Lose no Rebel Control
        - Leave 1 Active Patriot unit with each Patriot Fort
        - Leave 1 Patriot unit (Underground Militia preferred) where no Active Opposition
        - Phase 1: moving largest groups first, add Rebel Control to 2 spaces,
          first where Villages then Cities then elsewhere, within that highest Pop.
          Include most French Regulars possible.
        - Phase 2: get 1 Militia (Underground preferred) into each space with none,
          first to change most Control then random.
        """
        refresh_control(state)
        ctrl = state.get("control", {})

        # ---------- Phase 1: Add Rebel Control to up to 2 spaces ----------
        # Find potential destinations (not already Rebellion-controlled)
        phase1_dests = []
        for sid in state["spaces"]:
            if ctrl.get(sid) == "REBELLION":
                continue
            sp = state["spaces"][sid]
            has_village = sp.get(C.VILLAGE, 0)
            is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            # Check if gaining control is plausible (need to exceed royalist)
            phase1_dests.append((-has_village, -is_city, -pop, sid))
        phase1_dests.sort()

        # Build move plans for Phase 1
        move_plans: List[Dict] = []
        used_destinations: Set[str] = set()
        moved_from: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for _, _, _, dst in phase1_dests:
            if len(used_destinations) >= 2:
                break
            dst_sp = state["spaces"][dst]
            royalist_at_dst = self._royalist_pieces_in(dst_sp)
            rebels_at_dst = self._rebel_pieces_in(dst_sp)
            need = royalist_at_dst - rebels_at_dst + 1  # pieces needed to gain control
            if need <= 0:
                continue  # would already gain control, shouldn't happen

            # Find adjacent sources with movable pieces, largest groups first
            adj_set = map_adj.adjacent_spaces(dst)
            sources = []
            for src in adj_set:
                if src not in state["spaces"]:
                    continue
                src_sp = state["spaces"][src]
                grp_size = self._rebel_group_size(src_sp)
                if grp_size > 0:
                    sources.append((-grp_size, src))
            sources.sort()

            pieces_gathered = 0
            dst_plan_pieces: Dict[str, int] = {}
            plan_sources: List[Tuple[str, Dict[str, int]]] = []

            for _, src in sources:
                if pieces_gathered >= need:
                    break
                # Compute what can move from this source
                remaining_sp = dict(state["spaces"][src])
                # Account for pieces already committed from this source
                for tag, cnt in moved_from[src].items():
                    remaining_sp[tag] = remaining_sp.get(tag, 0) - cnt

                movable = self._movable_from_simulated(state, src, remaining_sp)
                if not movable:
                    continue

                # Take as much as needed
                src_pieces: Dict[str, int] = {}
                taken = 0
                # Include French Regulars as escorts (1-for-1 with Continentals)
                pat_cubes = min(movable.get(C.REGULAR_PAT, 0), need - pieces_gathered)
                if pat_cubes > 0:
                    src_pieces[C.REGULAR_PAT] = pat_cubes
                    taken += pat_cubes
                    # Escort French Regulars
                    fre = min(movable.get(C.REGULAR_FRE, 0), pat_cubes, need - pieces_gathered - taken)
                    if fre > 0:
                        src_pieces[C.REGULAR_FRE] = fre
                        taken += fre

                for tag in [C.MILITIA_A, C.MILITIA_U]:
                    still_need = need - pieces_gathered - taken
                    if still_need <= 0:
                        break
                    take = min(movable.get(tag, 0), still_need)
                    if take > 0:
                        src_pieces[tag] = take
                        taken += take

                if taken > 0:
                    plan_sources.append((src, src_pieces))
                    pieces_gathered += taken
                    for tag, cnt in src_pieces.items():
                        moved_from[src][tag] += cnt

            # Verify we can actually gain control
            if pieces_gathered >= need:
                for src, pieces in plan_sources:
                    move_plans.append({"src": src, "dst": dst, "pieces": pieces})
                used_destinations.add(dst)

        # ---------- Phase 2: Get 1 Militia into spaces with none ----------
        # Find spaces with no Patriot units
        phase2_targets = []
        for sid, sp in state["spaces"].items():
            if sid in used_destinations:
                continue
            pat_units = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                         + sp.get(C.REGULAR_PAT, 0))
            if pat_units > 0:
                continue
            # Priority: first to change most Control, then random
            changes_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            phase2_targets.append((-changes_ctrl, state["rng"].random(), sid))
        phase2_targets.sort()

        for _, _, dst in phase2_targets:
            adj_set = map_adj.adjacent_spaces(dst)
            found = False
            for src in sorted(adj_set):
                if src not in state["spaces"]:
                    continue
                remaining_sp = dict(state["spaces"][src])
                for tag, cnt in moved_from[src].items():
                    remaining_sp[tag] = remaining_sp.get(tag, 0) - cnt
                movable = self._movable_from_simulated(state, src, remaining_sp)
                # Prefer Underground Militia
                if movable.get(C.MILITIA_U, 0) > 0:
                    move_plans.append({"src": src, "dst": dst,
                                       "pieces": {C.MILITIA_U: 1}})
                    moved_from[src][C.MILITIA_U] += 1
                    found = True
                    break
                elif movable.get(C.MILITIA_A, 0) > 0:
                    move_plans.append({"src": src, "dst": dst,
                                       "pieces": {C.MILITIA_A: 1}})
                    moved_from[src][C.MILITIA_A] += 1
                    found = True
                    break
                elif movable.get(C.REGULAR_PAT, 0) > 0:
                    move_plans.append({"src": src, "dst": dst,
                                       "pieces": {C.REGULAR_PAT: 1}})
                    moved_from[src][C.REGULAR_PAT] += 1
                    found = True
                    break

        if not move_plans:
            return False

        # Collect all unique destinations
        all_dests = list(dict.fromkeys(p["dst"] for p in move_plans))
        all_srcs = list(dict.fromkeys(p["src"] for p in move_plans))

        try:
            march.execute(
                state, self.faction, {},
                all_srcs, all_dests,
                bring_escorts=True,
                limited=False,
                move_plan=move_plans,
            )
            return True
        except (ValueError, KeyError):
            return False

    def _movable_from_simulated(self, state: Dict, sid: str,
                                 simulated_sp: Dict) -> Dict[str, int]:
        """Like _movable_from but uses a simulated space dict instead of live state."""
        sp = simulated_sp
        avail = {
            C.REGULAR_PAT: max(0, sp.get(C.REGULAR_PAT, 0)),
            C.MILITIA_A: max(0, sp.get(C.MILITIA_A, 0)),
            C.MILITIA_U: max(0, sp.get(C.MILITIA_U, 0)),
            C.REGULAR_FRE: max(0, sp.get(C.REGULAR_FRE, 0)),
        }
        total_movable = sum(avail.values())
        if total_movable == 0:
            return {}

        retain = 0

        if sp.get(C.FORT_PAT, 0) and sp.get(C.FORT_PAT, 0) > 0:
            retain = max(retain, 1)

        support = self._support_level(state, sid)
        if support > C.ACTIVE_OPPOSITION:
            retain = max(retain, 1)

        # Control constraint
        ctrl = state.get("control", {}).get(sid)
        if ctrl == "REBELLION":
            rebels_total = sum(max(0, sp.get(t, 0)) for t in _REBEL_TAGS)
            royalist = sum(max(0, sp.get(t, 0)) for t in _ROYALIST_TAGS)
            max_can_move = rebels_total - royalist - 1
            if max_can_move < 0:
                max_can_move = 0
            retain = max(retain, total_movable - max_can_move)

        if retain >= total_movable:
            return {}

        can_move = total_movable - retain
        result = {}
        remaining = can_move
        for tag in [C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE, C.MILITIA_U]:
            take = min(remaining, avail.get(tag, 0))
            if take > 0:
                result[tag] = take
                remaining -= take
            if remaining <= 0:
                break
        return result

    def _rebel_group_size(self, sp: Dict) -> int:
        return (
            sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
            sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        )

    # ---------- Rally (P7) --------------------------------------------
    def _execute_rally(self, state: Dict) -> bool:
        """P7 Rally: Full 6-bullet implementation.
        1. Place Fort in each space with 4+ Patriot units and room
           (Cities first, highest Pop).
        2. Place Militia at Patriot Forts with no other Rebellion pieces.
        3. If Continentals Available, place at Fort with most Militia.
        4. At Fort with most Militia of those already selected, replace all
           Militia except 1 Underground with Continentals.
        5. If Patriot Fort Available, place Militia in space with no Fort
           and most Patriot units.
        6. Place Militia (first to change Control, then where no Active
           Opposition; within each Cities first, highest Pop).
        7. At 1 Fort, move adjacent Active Militia without losing Rebel
           Control, flip all Militia at Fort Underground.
        Returns False if nothing can be done.
        """
        refresh_control(state)
        ctrl = state.get("control", {})
        spaces_used: List[str] = []  # Track Rally spaces (Max 4)
        build_fort_set: Set[str] = set()
        promote_space: str | None = None
        promote_n: int | None = None
        move_plan_list: List[Tuple[str, str, int]] = []

        avail_forts = state["available"].get(C.FORT_PAT, 0)
        avail_militia = state["available"].get(C.MILITIA_U, 0)
        avail_cont = state["available"].get(C.REGULAR_PAT, 0)

        # --- Bullet 1: Fort placement ---
        if avail_forts > 0:
            fort_candidates = []
            for sid, sp in state["spaces"].items():
                if sp.get(C.FORT_PAT, 0) > 0:
                    continue
                bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0)
                if bases >= 2:
                    continue
                if self._rebel_group_size(sp) >= 4:
                    is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    fort_candidates.append((-is_city, -pop, sid))
            fort_candidates.sort()
            for _, _, sid in fort_candidates:
                if len(spaces_used) >= 4 or avail_forts <= 0:
                    break
                build_fort_set.add(sid)
                spaces_used.append(sid)
                avail_forts -= 1

        # --- Bullet 2: Militia at lonely Fort spaces ---
        for sid, sp in state["spaces"].items():
            if len(spaces_used) >= 4:
                break
            if sp.get(C.FORT_PAT, 0) == 0:
                continue
            # "no other Rebellion pieces" = only the Fort itself
            other = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
                     sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0))
            if other == 0 and sid not in spaces_used:
                spaces_used.append(sid)

        # --- Bullet 3: Continental placement at Fort with most Militia ---
        # §8.5.2: "then if any Continentals are Available at the Fort with
        # the largest number of Militia already."
        # This adds a new Rally space (the Fort with most Militia globally).
        if avail_cont > 0 and len(spaces_used) < 4:
            best_cont_fort = None
            best_cont_mil = -1
            for sid, sp in state["spaces"].items():
                if sid in spaces_used:
                    continue  # already selected
                if sp.get(C.FORT_PAT, 0) == 0 and sid not in build_fort_set:
                    continue
                mil = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                if mil > best_cont_mil:
                    best_cont_mil = mil
                    best_cont_fort = sid
            if best_cont_fort and best_cont_mil > 0:
                spaces_used.append(best_cont_fort)

        # --- Bullet 4: Continental replacement ---
        # §8.5.2: "In the Patriot Fort space with most Militia OF THOSE
        # ALREADY SELECTED FOR RALLY, replace all Militia except 1
        # Underground with Continentals."
        if avail_cont > 0:
            best_fort = None
            best_mil = -1
            for sid in spaces_used:
                sp = state["spaces"].get(sid, {})
                if sp.get(C.FORT_PAT, 0) == 0 and sid not in build_fort_set:
                    continue
                mil = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                if mil > best_mil:
                    best_mil = mil
                    best_fort = sid
            if best_fort and best_mil > 0:
                promote_space = best_fort
                promote_n = max(0, best_mil - 1)
                if promote_n == 0:
                    promote_space = None
                    promote_n = None

        # --- Bullet 5: Militia at non-Fort space with most Patriot units ---
        # Reference: "If Patriot Fort Available" — check post-Bullet-1 count
        if avail_forts > 0:
            no_fort_spaces = []
            for sid, sp in state["spaces"].items():
                if sp.get(C.FORT_PAT, 0) > 0 or sid in build_fort_set:
                    continue
                pat_units = self._rebel_group_size(sp)
                no_fort_spaces.append((-pat_units, sid))
            no_fort_spaces.sort()
            for _, sid in no_fort_spaces:
                if len(spaces_used) >= 4:
                    break
                if sid not in spaces_used:
                    spaces_used.append(sid)
                    break

        # --- Bullet 6: Militia to change Control or no Active Opposition ---
        remaining_slots = 4 - len(spaces_used)
        if remaining_slots > 0:
            militia_targets = []
            for sid, sp in state["spaces"].items():
                if sid in spaces_used:
                    continue
                changes_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
                no_active_opp = 1 if self._support_level(state, sid) > C.ACTIVE_OPPOSITION else 0
                is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                militia_targets.append((-changes_ctrl, -no_active_opp, -is_city, -pop, sid))
            militia_targets.sort()
            for _, _, _, _, sid in militia_targets:
                if len(spaces_used) >= 4:
                    break
                spaces_used.append(sid)

        # --- Bullet 7: Move adjacent Militia to 1 Fort, flip Underground ---
        # §8.5.2: "in one Fort space NOT already selected above"
        fort_spaces_for_gather = [
            sid for sid, sp in state["spaces"].items()
            if sid not in spaces_used
            and (sp.get(C.FORT_PAT, 0) > 0 or sid in build_fort_set)
            and len(spaces_used) < 4  # must have room for one more space
        ]
        if fort_spaces_for_gather:
            # Pick the Fort that can gather the most adjacent Active Militia
            best_gather_fort = None
            best_gather_count = 0
            best_gather_moves: List[Tuple[str, str, int]] = []

            for fort_sid in fort_spaces_for_gather:
                adj_set = map_adj.adjacent_spaces(fort_sid)
                gather_moves = []
                gather_total = 0
                for adj_sid in adj_set:
                    if adj_sid not in state["spaces"]:
                        continue
                    adj_sp = state["spaces"][adj_sid]
                    active_mil = adj_sp.get(C.MILITIA_A, 0)
                    if active_mil == 0:
                        continue
                    # Check if removing Active Militia would lose Rebel Control
                    can_take = active_mil
                    for n in range(active_mil, 0, -1):
                        if not self._would_lose_rebel_control(
                                state, adj_sid, {C.MILITIA_A: n}):
                            can_take = n
                            break
                    else:
                        can_take = 0
                    if can_take > 0:
                        gather_moves.append((adj_sid, fort_sid, can_take))
                        gather_total += can_take

                if gather_total > best_gather_count:
                    best_gather_count = gather_total
                    best_gather_fort = fort_sid
                    best_gather_moves = gather_moves

            if best_gather_moves:
                move_plan_list = best_gather_moves
                # Ensure the Fort is in spaces_used
                if best_gather_fort and best_gather_fort not in spaces_used:
                    if len(spaces_used) < 4:
                        spaces_used.append(best_gather_fort)

        if not spaces_used:
            return False

        # Check we have resources to pay
        if state["resources"][self.faction] < len(spaces_used):
            # Reduce spaces to what we can afford
            spaces_used = spaces_used[:state["resources"][self.faction]]
            if not spaces_used:
                return False
            # Remove Fort targets not in spaces_used
            build_fort_set &= set(spaces_used)
            if promote_space and promote_space not in spaces_used:
                promote_space = None
                promote_n = None
            move_plan_list = [(s, d, n) for s, d, n in move_plan_list
                              if d in spaces_used]

        try:
            rally.execute(
                state, self.faction, {},
                spaces_used,
                build_fort=build_fort_set,
                promote_space=promote_space,
                promote_n=promote_n,
                move_plan=move_plan_list,
            )
            # Check for mid-Rally Persuasion interrupt
            if state["resources"][self.faction] == 0:
                self._try_persuasion(state)
            return True
        except (ValueError, KeyError):
            return False

    # ---------- Rabble-Rousing (P11) ----------------------------------
    @staticmethod
    def _rabble_eligible(state: Dict, sid: str, sp: Dict) -> bool:
        """Check §3.3.4 eligibility: (Rebellion Control AND Patriot pieces) OR
        Underground Militia.  Also must not be at Active Opposition."""
        from lod_ai.rules_consts import ACTIVE_OPPOSITION
        if state.get("support", {}).get(sid, 0) <= ACTIVE_OPPOSITION:
            return False
        rebellion_ctrl = state.get("control", {}).get(sid) == "REBELLION"
        has_pat = any(sp.get(t, 0) > 0 for t in
                      (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT))
        has_underground = sp.get(C.MILITIA_U, 0) > 0
        return (rebellion_ctrl and has_pat) or has_underground

    def _execute_rabble(self, state: Dict) -> bool:
        """P11: Rabble-Rousing. Shift spaces toward Active Opposition.
        First in Active Support, within that highest Pop.
        No artificial cap (reference doesn't state a max).
        Persuasion interrupt when resources reach 0.
        Only eligible spaces per §3.3.4: (Rebellion Control + Patriot pieces)
        or Underground Militia.
        """
        refresh_control(state)
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if self._rabble_eligible(state, sid, sp)
        ]
        if not spaces:
            return False
        spaces.sort(key=lambda n: (
            -self._support_level(state, n),
            -_MAP_DATA[n].get("population", 0),
        ))
        # No artificial cap - use all eligible spaces (limited by resources)
        max_spaces = state["resources"][self.faction]
        selected = spaces[:max_spaces] if max_spaces > 0 else []
        if not selected:
            return False
        rabble_rousing.execute(state, self.faction, {}, selected)
        # Persuasion interrupt when resources reach 0
        if state["resources"][self.faction] == 0:
            self._try_persuasion(state)
        return True

    # ===================================================================
    #  SPECIAL-ACTIVITY HELPERS
    # ===================================================================
    def _try_partisans(self, state: Dict) -> bool:
        """P8: Partisans (Max 1)."""
        if state["resources"][self.faction] == 0:
            return False
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
            adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
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
            enemy_cubes = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                           + sp.get(C.WARPARTY_A, 0))
            own_militia = sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
            # §8.1 "maximum extent": option 2 nets +1 removal over option 1
            # (sacrifice 1 own piece → remove 2 enemy) when 2+ enemy cubes
            if has_village and enemy_cubes == 0 and not wp:
                opt = 3
            elif enemy_cubes >= 2 and own_militia >= 1:
                opt = 2
            else:
                opt = 1
            try:
                partisans.execute(state, self.faction, {}, sid, option=opt)
                return True
            except Exception:
                continue
        return False

    def _try_skirmish(self, state: Dict) -> bool:
        """P12: Skirmish (Max 1)."""
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
            own_regs = sp.get(C.REGULAR_PAT, 0)
            # §8.1 "maximum extent": option 2 nets +1 removal over option 1
            # (sacrifice 1 own piece → remove 2 enemy) when 2+ enemy cubes
            if has_fort and not enemy_cubes:
                opt = 3
            elif enemy_cubes >= 2 and own_regs >= 1:
                opt = 2
            else:
                opt = 1
            try:
                skirmish.execute(state, self.faction, {}, sid, option=opt)
                return True
            except Exception:
                continue
        return False

    def _try_persuasion(self, state: Dict) -> bool:
        refresh_control(state)
        ctrl = state.get("control", {})
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if ctrl.get(sid) == "REBELLION" and sp.get(C.MILITIA_U, 0)
            and _MAP_DATA.get(sid, {}).get("type") in ("Colony", "City")
        ]
        if not spaces:
            return False
        spaces.sort(key=lambda n: (
            -state["spaces"][n].get(C.FORT_PAT, 0),
            -_MAP_DATA.get(n, {}).get("population", 0),
        ))
        try:
            persuasion.execute(state, self.faction, {}, spaces=spaces[:3])
            return True
        except (ValueError, KeyError):
            return False

    # ===================================================================
    #  DECISION-HELPER FUNCTIONS
    # ===================================================================
    def _rally_preferred(self, state: Dict) -> bool:
        """P9: Rally if would place Fort OR 1D6 > Underground Militia."""
        avail_forts = state["available"].get(C.FORT_PAT, 0)
        if avail_forts and any(
            self._rebel_group_size(sp) >= 4 and sp.get(C.FORT_PAT, 0) == 0
            for sp in state["spaces"].values()
        ):
            return True
        hidden = sum(sp.get(C.MILITIA_U, 0) for sp in state["spaces"].values())
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Rally-test 1D6", roll))
        return roll > hidden

    def _rabble_possible(self, state: Dict) -> bool:
        """P10: 'Rabble-Rousing can shift 1+ spaces toward Active Opposition?'
        Must also check §3.3.4 eligibility for each space."""
        refresh_control(state)
        return any(
            self._rabble_eligible(state, sid, sp)
            for sid, sp in state["spaces"].items()
        )

    # ===================================================================
    #  CARD 51 CONDITIONAL + EVENT INSTRUCTION OVERRIDE
    # ===================================================================
    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives from the Patriot instruction sheet."""
        if directive == "force_if_52":
            # Card 52: "Remove no French Regulars; select space per Battle
            # instructions, else ignore."
            # Check: any space where both French and British pieces exist
            # that would satisfy Battle selection?
            refresh_control(state)
            for sid, sp in state["spaces"].items():
                french = sp.get(C.REGULAR_FRE, 0)
                brit = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                        + sp.get(C.WARPARTY_A, 0))
                if french > 0 and brit > 0:
                    return True
            return False
        if directive == "force_if_51":
            # Card 51: "March to set up Battle per the Battle instructions.
            # If not possible, choose Command & Special Activity instead."
            # Check: can any March destination lead to a valid Battle space?
            refresh_control(state)
            for sid, sp in state["spaces"].items():
                pat_cubes = sp.get(C.REGULAR_PAT, 0)
                fre_cubes = min(sp.get(C.REGULAR_FRE, 0), pat_cubes)
                active_mil = sp.get(C.MILITIA_A, 0)
                rebel_force = pat_cubes + fre_cubes + (active_mil // 2)
                regs = sp.get(C.REGULAR_BRI, 0)
                tories = sp.get(C.TORY, 0)
                active_wp = sp.get(C.WARPARTY_A, 0)
                brit_force = regs + tories + (active_wp // 2) + sp.get(C.FORT_BRI, 0)
                if (regs + tories + active_wp) > 0:
                    # Could marching units here tip the balance?
                    adj_set = map_adj.adjacent_spaces(sid)
                    extra = 0
                    for adj_sid in adj_set:
                        adj_sp = state["spaces"].get(adj_sid, {})
                        extra += self._rebel_group_size(adj_sp)
                    if rebel_force + extra > brit_force:
                        return True
            return False
        return True  # default: play the event

    # ===================================================================
    #  EVENT-VS-COMMAND BULLETS  (P2)
    # ===================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """P2: Check shaded Event conditions for Patriot bot via CARD_EFFECTS."""
        effects = CARD_EFFECTS.get(card.get("id"))
        if effects is None:
            return False
        eff = effects["shaded"]

        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        if sup > opp and eff["shifts_support_rebel"]:
            return True
        if eff["places_patriot_militia_u"]:
            # P2 bullet 2 (§8.5): "places Underground Militia in at least one
            # Active Support or Village space that has none already"
            for sid, sp in state["spaces"].items():
                has_militia = (sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)) > 0
                if has_militia:
                    continue
                sup = support_map.get(sid, 0)
                if sup == C.ACTIVE_SUPPORT or sp.get(C.VILLAGE, 0) > 0:
                    return True
        if eff["places_patriot_fort"] or eff["removes_village"]:
            return True
        if eff["adds_patriot_resources_3plus"]:
            return True
        if eff["is_effective"]:
            pieces_on_map = sum(
                sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0) + sp.get(C.FORT_PAT, 0)
                for sp in state["spaces"].values()
            )
            if pieces_on_map >= 25:
                roll = state["rng"].randint(1, 6)
                state.setdefault("rng_log", []).append(("Event D6", roll))
                if roll >= 5:
                    return True
        return False

    # ===================================================================
    #  OPS SUMMARY (year-end / operational mechanics)
    # ===================================================================
    def ops_supply_priority(self, state: Dict) -> List[str]:
        """Patriot Supply: Pay only if removing pieces would change Control,
        within that first where British could Reward Loyalty, then where most
        Indian Villages, then highest Pop."""
        refresh_control(state)
        ctrl = state.get("control", {})
        spaces = []
        for sid, sp in state["spaces"].items():
            # Check if removing Patriot pieces would change control
            pat_count = self._rebel_pieces_in(sp)
            if pat_count == 0:
                continue
            royal = self._royalist_pieces_in(sp)
            # If rebels barely exceed royalist, removing 1 could change control
            margin = pat_count - royal
            if margin <= 1:
                changes_ctrl = 1
            else:
                changes_ctrl = 0
            # British could Reward Loyalty (has British pieces + not Active Support)
            has_british = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) > 0
            support = self._support_level(state, sid)
            could_rl = 1 if has_british and support < C.ACTIVE_SUPPORT else 0
            villages = sp.get(C.VILLAGE, 0)
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            spaces.append((-changes_ctrl, -could_rl, -villages, -pop, sid))
        spaces.sort()
        return [sid for *_, sid in spaces]

    def ops_redeploy_washington(self, state: Dict) -> str | None:
        """Redeploy Washington to space with most Continentals."""
        best = None
        best_cont = -1
        for sid, sp in state["spaces"].items():
            cont = sp.get(C.REGULAR_PAT, 0)
            if cont > best_cont:
                best_cont = cont
                best = sid
        return best

    def ops_patriot_desertion_priority(self, state: Dict) -> List[Tuple[str, str]]:
        """Patriot Desertion: Remove so as to change least Control,
        within that without removing last Patriot unit from any space.
        Returns list of (space_id, piece_tag) to remove in order."""
        refresh_control(state)
        ctrl = state.get("control", {})
        candidates = []
        for sid, sp in state["spaces"].items():
            for tag in [C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT]:
                if sp.get(tag, 0) == 0:
                    continue
                # Would removing change control?
                changes = 1 if self._would_lose_rebel_control(
                    state, sid, {tag: 1}) else 0
                # Is this the last Patriot unit?
                total_pat = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                             + sp.get(C.REGULAR_PAT, 0))
                is_last = 1 if total_pat <= 1 else 0
                candidates.append((changes, is_last, sid, tag))
        candidates.sort()
        return [(sid, tag) for _, _, sid, tag in candidates]

    def ops_bs_trigger(self, state: Dict) -> bool:
        """Brilliant Stroke: Use after Treaty of Alliance when Washington is
        in a space with 4+ Continentals, and a player Faction is 1st Eligible."""
        if not state.get("toa_played"):
            return False
        wash_loc = leader_location(state, "LEADER_WASHINGTON")
        if not wash_loc:
            return False
        sp = state["spaces"].get(wash_loc, {})
        return sp.get(C.REGULAR_PAT, 0) >= 4
