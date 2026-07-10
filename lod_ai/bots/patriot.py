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
from lod_ai.bots.random_spaces import (pick_by_priority, choose_random_space,
                                       pick_random_spaces)
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

    def _control_after_add(self, state: Dict, sid: str,
                           to_add: int = 1) -> str | None:
        """Control value (§1.7 semantics as in board.control) after
        adding *to_add* Rebellion pieces to *sid*."""
        sp = state["spaces"][sid]
        rebels = self._rebel_pieces_in(sp) + to_add
        royalist = self._royalist_pieces_in(sp)
        bri = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
               + sp.get(C.FORT_BRI, 0))
        if rebels > royalist:
            return "REBELLION"
        if royalist > rebels and bri > 0:
            return "BRITISH"
        return None

    def _control_after_remove(self, state: Dict, sid: str,
                              to_remove: Dict[str, int]) -> str | None:
        """Control value (§1.7) after removing *to_remove* Rebellion
        pieces from *sid*."""
        sp = state["spaces"][sid]
        rebels = sum(max(0, sp.get(t, 0) - to_remove.get(t, 0))
                     for t in _REBEL_TAGS)
        royalist = self._royalist_pieces_in(sp)
        bri = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
               + sp.get(C.FORT_BRI, 0))
        if rebels > royalist:
            return "REBELLION"
        if royalist > rebels and bri > 0:
            return "BRITISH"
        return None

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

        # §8.5.4: Leave Active Patriot unit at Fort; leave Underground
        # preferred where no Active Opposition.
        has_fort = sp.get(C.FORT_PAT, 0) > 0
        if has_fort:
            # Fort present: move Underground first so Active pieces stay
            move_order = [C.MILITIA_U, C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE]
        else:
            # No Fort: move Active first, keep Underground for leave-behind
            move_order = [C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE, C.MILITIA_U]

        result = {}
        remaining = can_move
        for tag in move_order:
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
        if (avail_forts and rebel_group >= 4 and sp.get(C.FORT_PAT, 0) == 0
                and self._fort_room(sp)):
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
    #  TURN RESET HOOKS
    # ===================================================================
    def take_turn(self, state, card, allowed=None):
        # Clear per-turn flags so single-fire SA gates reset at every turn.
        # Manual §4.1: a Faction may execute *one* Special Activity per
        # Command turn.  Persuasion in particular is callable from many
        # nodes (P7, P8, P11, P12) so we need a turn-scoped guard.
        state.pop("_turn_persuasion_used", None)
        return super().take_turn(state, card, allowed=allowed)

    # ===================================================================
    #  FLOW-CHART DRIVER
    # ===================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # Node P3
        if state["resources"][self.faction] == 0:
            state['_pass_reason'] = 'resource_gate'
            push_history(state, "PATRIOTS PASS (no Resources)")
            return

        # Node P6
        if self._battle_possible(state):
            if self._battle_chain(state):
                return
        else:
            if self._rally_preferred(state):          # P9
                if self._rally_chain(state):
                    return
                # P9 was Yes but Rally+Rabble both failed → PASS
            elif self._rabble_possible(state):        # P10=Yes
                if self._rabble_chain(state):
                    return
                # P10 was Yes but Rabble+Rally both failed → PASS
            else:                                     # P10=No → P5 March
                if self._march_chain(state):
                    return

        state['_pass_reason'] = 'no_valid_command'
        push_history(state, "PATRIOTS PASS")

    # ===================================================================
    #  EXECUTION CHAINS (with recursion guard for Rally/Rabble loop)
    # ===================================================================
    def _battle_chain(self, state: Dict) -> bool:
        if not self._execute_battle(state):
            self._reset_command_trace(state)
            return self._rally_chain(state)
        if not (state.get("_limited") or state.get("_no_special")):
            self._partisans_loop(state)
        return True

    def _march_chain(self, state: Dict) -> bool:
        if not self._execute_march(state):
            self._reset_command_trace(state)
            return self._rally_chain(state)
        if not (state.get("_limited") or state.get("_no_special")):
            self._partisans_loop(state)
        return True

    def _rally_chain(self, state: Dict, *, _from_rabble: bool = False) -> bool:
        if not self._execute_rally(state):
            if _from_rabble:
                return False  # prevent infinite Rally<->Rabble loop
            self._reset_command_trace(state)
            return self._rabble_chain(state, _from_rally=True)
        no_sa = state.get("_limited") or state.get("_no_special")
        # §8.5.2: "if no Persuasion was used during the Rally"
        # _execute_rally returns (True, persuasion_used) — check mid-Rally usage
        persuasion_during = state.pop("_rally_persuasion_used", False)
        if not no_sa:
            if not persuasion_during and state["resources"][self.faction] == 0:
                persuasion_during = self._try_persuasion(state)
            if not persuasion_during:
                self._partisans_loop(state)
        return True

    def _rabble_chain(self, state: Dict, *, _from_rally: bool = False) -> bool:
        if not self._execute_rabble(state):
            if _from_rally:
                return False  # prevent infinite Rabble<->Rally loop
            self._reset_command_trace(state)
            return self._rally_chain(state, _from_rabble=True)
        no_sa = state.get("_limited") or state.get("_no_special")
        # §8.5.3: "if no Persuasion was used during Rabble-Rousing"
        persuasion_during = state.pop("_rabble_persuasion_used", False)
        if not no_sa:
            if not persuasion_during and state["resources"][self.faction] == 0:
                persuasion_during = self._try_persuasion(state)
            if not persuasion_during:
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
        """P4: Select all spaces where Rebel Force Level + modifiers exceeds
        Royalist FL + modifiers (§3.6.5-6).
        §8.5.1: Include French only if French Resources > 0.
        If resources too low for all, prioritize: Washington, highest Pop,
        most Villages, random.
        Win-the-Day: free Rally (P7 priorities) + French Blockade move.
        """
        refresh_control(state)
        french_res = state["resources"].get(C.FRENCH, 0)
        targets = []
        # §8.3.7 (S64): first-BS-LimCom leader tie — only Washington's
        # space may be selected when flagged (British pattern, S61).
        _bs_o = state.get("_bs_leader_origin")
        for sid, sp in state["spaces"].items():
            if _bs_o and sid != _bs_o:
                continue
            # P4: "Rebel Force Level (if possible including French) +
            # modifiers exceeds the British Force Level + modifiers." Use the
            # resolver's exact Force Level / Loss-Level modifier maths
            # (§3.6.2-3.6.6) via the shared helper -- same code the Battle
            # actually resolves with -- instead of a hand-rolled approximation.
            # §8.5.1: include the French ally only if French Resources > 0.
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0)
            active_wp = sp.get(C.WARPARTY_A, 0)
            ally = french_res > 0
            att_score, def_score = battle.bot_battle_scores(
                state, sid, "REBELLION",
                attacker_faction=C.PATRIOTS, ally_involved=ally)
            if att_score > def_score and (regs + tories + active_wp) > 0:
                has_wash = 1 if leader_location(state, "LEADER_WASHINGTON") == sid else 0
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                villages = sp.get(C.VILLAGE, 0)
                targets.append(((-has_wash, -pop, -villages), sid))
        if not targets:
            return False
        # Q22: table-resolved ties
        targets = [(None, s) for s in pick_by_priority(state, targets)]
        chosen = [sid for *_, sid in targets]

        # Limited Command: cap to 1 space
        if state.get("_limited"):
            chosen = chosen[:1]

        # §8.5.1: If Patriot Resources too low for all spaces, trim list
        pat_res = state["resources"].get(self.faction, 0)
        if pat_res < len(chosen):
            chosen = chosen[:max(pat_res, 1)]

        # Win-the-Day: per-space callback for free Rally + Blockade move
        def _win_callback(st, battle_sid):
            """Per-space Win-the-Day callback per §3.6.8.

            Returns (rally_space, rally_kwargs, blockade_dest) for this
            battle space.  Rally uses P7 priorities; Blockade moves to
            the City with most Support (excluding the battle city itself).
            """
            # §8.5.1: "the Patriots execute a free Rally Command (8.5.2)
            # in one space" — the space is selected by the 8.5.2/P7
            # priorities, NOT hardwired to the battle space (Session 31;
            # the correct selector existed as dead code).
            rally_space = self._best_rally_space(st)
            rally_kwargs = {}
            if rally_space:
                sp_r = st["spaces"].get(rally_space, {})
                removable = (sp_r.get(C.MILITIA_U, 0)
                             + sp_r.get(C.MILITIA_A, 0)
                             + sp_r.get(C.REGULAR_PAT, 0))
                if (sp_r.get(C.FORT_PAT, 0) == 0
                        and self._rebel_group_size(sp_r) >= 4
                        and removable >= 2
                        and st["available"].get(C.FORT_PAT, 0) > 0
                        and self._fort_room(sp_r)):   # §1.4.2 stacking
                    rally_kwargs["build_fort"] = {rally_space}
            # Blockade: "to another City with MORE Support" than the
            # battle City (§8.5.1) — strictly greater, else no move.
            blockade_dest = self._best_blockade_city(
                st, exclude=battle_sid,
                min_support=self._support_level(st, battle_sid))
            return rally_space, rally_kwargs, blockade_dest

        battle.execute(
            state, self.faction, {}, chosen,
            win_callback=_win_callback,
        )
        return True

    # ------------------------------------------------------------------
    #  Rally / placement legality filter
    # ------------------------------------------------------------------
    @staticmethod
    def _is_illegal_rally_space(sid: str) -> bool:
        """Return True if *sid* cannot receive Patriot Rally placement.

        West Indies (§1.4.2): only British/French Regulars, British Forts,
        French Squadrons may occupy.
        Indian Reserve Provinces: Militia cannot exist there.
        """
        return sid == C.WEST_INDIES_ID or map_adj.space_type(sid) == "Reserve"

    def _can_rally_in(self, state: Dict, sid: str) -> bool:
        """Return False if *sid* is illegal for Rally.

        Combines the West Indies / Indian Reserve check with the §3.3.1
        Active Support prohibition.
        """
        if self._support_level(state, sid) == C.ACTIVE_SUPPORT:
            return False
        if self._is_illegal_rally_space(sid):
            return False
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
                if not self._can_rally_in(state, sid):
                    continue
                if sp.get(C.FORT_PAT, 0) > 0:
                    continue
                bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0)
                if bases >= 2:
                    continue
                if (sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
                        + sp.get(C.REGULAR_PAT, 0)) >= 4:  # §8.5.2 Patriot units
                    is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    candidates.append((-is_city, -pop, sid))
            if candidates:
                candidates.sort()
                return candidates[0][2]

        # Priority 2: Space to change Control or no Active Opposition
        candidates = []
        for sid, sp in state["spaces"].items():
            if not self._can_rally_in(state, sid):
                continue
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

    def _best_blockade_city(self, state: Dict,
                            exclude: str | None = None,
                            min_support: int | None = None) -> str | None:
        """Select City with most Support for French Blockade move (P4).

        Parameters
        ----------
        exclude : str | None
            A city to exclude (the battle city the blockade moves FROM).
        min_support : int | None
            §8.5.1/§8.6.6: the destination must have strictly MORE
            Support than the origin City; pass the origin's level.
        """
        best = None
        best_support = min_support if min_support is not None else -999
        for sid in CITIES:
            if sid == exclude:
                continue
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
        _bs_o = state.get("_bs_leader_origin")  # §8.3.7 BS LimCom1 leader tie (S64)
        refresh_control(state)
        ctrl = state.get("control", {})

        # ---------- Phase 1: Add Rebel Control to up to 2 spaces ----------
        # Find potential destinations (not already Rebellion-controlled)
        phase1_dests = []
        for sid in state["spaces"]:
            if _bs_o and sid != _bs_o:
                continue  # leader tie (origins)
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
        # §3.3.2: 1 Patriot Resource per destination; §2.3.5: a Limited
        # Command has a single destination.  §8.5.4 itself sets no
        # destination cap (Session 45: an artificial 4-destination cap
        # also throttled Phase 2).
        if state.get("bs_free"):
            march_max = 999
            fre_res = 999
        else:
            march_max = state["resources"].get(self.faction, 0)
            fre_res = state["resources"].get(C.FRENCH, 0)
        if state.get("_limited"):
            march_max = 1
        roch_loc = leader_location(state, "LEADER_ROCHAMBEAU")
        fre_dests: Set[str] = set()
        move_plans: List[Dict] = []
        used_destinations: Set[str] = set()
        moved_from: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for _, _, _, dst in phase1_dests:
            if len(used_destinations) >= min(2, march_max):
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

            # §8.5.4: "If French Resources exceed 0, include as many
            # French Regulars as possible in the moves."  §3.3.2 charges
            # the French 1 Resource per destination they enter (waived
            # where Rochambeau is — leader_capabilities), so French join
            # only into destinations their purse can pay (Session 45:
            # French Regulars were planned at 0 French Resources and the
            # escort-fee validation in march.execute aborted the whole
            # March).
            _chargeable = len([d for d in fre_dests if d != roch_loc])
            fre_ok = fre_res > 0 and (
                dst == roch_loc or _chargeable + 1 <= fre_res)

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
                    # Escort French Regulars 1-for-1 with Continentals
                    # (§3.3.2), only while the French purse allows.
                    # §8.5.4 (S56): "If French Resources exceed 0, include
                    # as many French Regulars as possible in the moves" —
                    # the sentence follows the stop-at-Control clause, so
                    # escorts are NOT capped at the remaining Control need
                    # (they count toward Control anyway; overshoot is the
                    # rule).  Legal max stays 1-for-1 with the moving
                    # Continentals (§3.3.2).
                    if fre_ok:
                        fre = min(movable.get(C.REGULAR_FRE, 0), pat_cubes)
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

            # Verify we can actually gain control
            if pieces_gathered >= need:
                # Session 45 latent fix: reserve source pieces only when
                # the destination actually commits — a failed gather used
                # to leave its takes in moved_from and starve later
                # destinations of movable pieces.
                for src, pieces in plan_sources:
                    move_plans.append({"src": src, "dst": dst, "pieces": pieces})
                    for tag, cnt in pieces.items():
                        moved_from[src][tag] += cnt
                used_destinations.add(dst)
                if any(p.get(C.REGULAR_FRE, 0) for _, p in plan_sources):
                    fre_dests.add(dst)

        # ---------- Phase 2: Get 1 Militia into spaces with none ----------
        # §8.5.4: "Then March to get one Militia (Underground if possible)
        # into each space with none, first to change Control of the most
        # Population, then elsewhere."  Only Militia move here (Session
        # 45: a Continental fallback and an artificial destination cap
        # were removed); destinations are limited by the Patriot purse
        # (1 Resource each, §3.3.2) via march_max.
        phase2_targets = []
        for sid, sp in state["spaces"].items():
            if _bs_o and sid != _bs_o:
                continue  # leader tie (origins)
            if sid in used_destinations:
                continue
            pat_units = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                         + sp.get(C.REGULAR_PAT, 0))
            if pat_units > 0:
                continue
            changes_ctrl = 1 if (self._control_after_add(state, sid, 1)
                                 != ctrl.get(sid)) else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            phase2_targets.append(((-changes_ctrl, -(pop * changes_ctrl)),
                                   sid))
        # Q22: table-resolved ties
        for dst in pick_by_priority(state, phase2_targets):
            if len(used_destinations) >= march_max:
                break
            adj_set = map_adj.adjacent_spaces(dst)
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
                    used_destinations.add(dst)
                    break
                elif movable.get(C.MILITIA_A, 0) > 0:
                    move_plans.append({"src": src, "dst": dst,
                                       "pieces": {C.MILITIA_A: 1}})
                    moved_from[src][C.MILITIA_A] += 1
                    used_destinations.add(dst)
                    break

        if not move_plans:
            return False

        # --- Post-planning verification: Lose no Rebel Control ---
        # Aggregate total removals per source across all moves, then verify
        # that no Rebellion-controlled origin would flip to Crown control.
        agg_removals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for plan in move_plans:
            for tag, cnt in plan["pieces"].items():
                agg_removals[plan["src"]][tag] += cnt

        verified_plans = []
        for plan in move_plans:
            src = plan["src"]
            if src in agg_removals and self._would_lose_rebel_control(
                    state, src, dict(agg_removals[src])):
                # Skip this plan — would lose Rebel Control at origin
                # Also reduce aggregated removals for this source
                for tag, cnt in plan["pieces"].items():
                    agg_removals[src][tag] -= cnt
                continue
            verified_plans.append(plan)

        if not verified_plans:
            return False

        move_plans = verified_plans

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

        # §8.5.4: Leave Active Patriot unit at Fort; leave Underground
        # preferred where no Active Opposition.
        has_fort = sp.get(C.FORT_PAT, 0) and sp.get(C.FORT_PAT, 0) > 0
        if has_fort:
            move_order = [C.MILITIA_U, C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE]
        else:
            move_order = [C.REGULAR_PAT, C.MILITIA_A, C.REGULAR_FRE, C.MILITIA_U]

        result = {}
        remaining = can_move
        for tag in move_order:
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
        _bs_o = state.get("_bs_leader_origin")  # §8.3.7 BS LimCom1 leader tie (S64)
        refresh_control(state)
        ctrl = state.get("control", {})
        max_rally = 1 if state.get("_limited") else 4
        spaces_used: List[str] = []  # Track Rally spaces (Max max_rally)
        build_fort_set: Set[str] = set()
        place_one_set: Set[str] = set()   # Spaces that need explicit Militia placement
        bulk_place_map: Dict[str, int] = {}  # Fort spaces: §3.3.1 bulk Militia placement
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
                if _bs_o and sid != _bs_o:
                    continue  # leader tie
                if not self._can_rally_in(state, sid):
                    continue
                if sp.get(C.FORT_PAT, 0) > 0:
                    continue
                bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0)
                if bases >= 2:
                    continue
                # §8.5.2: "4+ Patriot units" — units are the Patriots' own
                # Militia and Continentals (Glossary §1.4: not Forts or
                # Villages; French Regulars are French pieces).  Session
                # 45: was _rebel_group_size, which counted French
                # Regulars.  4+ Patriot units implies the 2 removable
                # units §3.3.1 needs for the Fort.
                pat_units = (sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
                             + sp.get(C.REGULAR_PAT, 0))
                if pat_units >= 4:
                    is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    fort_candidates.append(((-is_city, -pop), sid))
            # Q22: table-resolved ties
            for sid in pick_by_priority(state, fort_candidates):
                if len(spaces_used) >= max_rally or avail_forts <= 0:
                    break
                build_fort_set.add(sid)
                spaces_used.append(sid)
                avail_forts -= 1

        # --- Bullet 2: Militia at lonely Fort spaces ---
        # §8.5.2: "place Militia, first at each Patriot Fort with no other
        # Rebellion pieces"
        # Only add if Militia are actually Available to place.
        if avail_militia > 0:
            lonely_forts = []
            for sid, sp in state["spaces"].items():
                if _bs_o and sid != _bs_o:
                    continue  # leader tie
                if not self._can_rally_in(state, sid):
                    continue
                # §8.5.2: "first at each Patriot Fort with no other
                # Rebellion pieces" — requires an existing Patriot Fort
                # (Session 45: the old filter also admitted fortless
                # spaces at the 2-base stacking cap).
                if sp.get(C.FORT_PAT, 0) == 0:
                    continue
                # "no other Rebellion pieces" = only the Fort itself
                other = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) +
                         sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0))
                if other == 0 and sid not in spaces_used:
                    lonely_forts.append(sid)
            # Q22: equal-priority spaces ordered by the Random Spaces table
            for sid in pick_by_priority(state, [((0,), s) for s in lonely_forts]):
                if len(spaces_used) >= max_rally or avail_militia <= 0:
                    break
                sp = state["spaces"][sid]
                # §3.3.1 Fort-space Rally places up to (#Patriot Forts +
                # Population) Militia; §8.1.1 executes to the maximum
                # extent possible (Session 45: was a single Militia).
                extent = min(sp.get(C.FORT_PAT, 0)
                             + _MAP_DATA.get(sid, {}).get("population", 0),
                             avail_militia)
                if extent <= 0:
                    continue
                spaces_used.append(sid)
                bulk_place_map[sid] = extent
                avail_militia -= extent

        # --- Bullet 3: Continental placement at Fort with most Militia ---
        # §8.5.2: "then if any Continentals are Available at the Fort with
        # the largest number of Militia already."
        # This adds a new Rally space (the Fort with most Militia globally).
        # Unlike Bullet 4, this may select a Fort not yet in spaces_used.
        if avail_cont > 0 and len(spaces_used) < max_rally:
            best_cont_fort = None
            best_cont_mil = -1
            best_cont_key = None
            for sid, sp in state["spaces"].items():
                if _bs_o and sid != _bs_o:
                    continue  # leader tie
                if not self._can_rally_in(state, sid):
                    continue
                if sid in spaces_used:
                    continue  # already selected — checked separately in Bullet 4
                # "at the Fort with the largest number of Militia
                # already" — needs an existing Patriot Fort (Session 45:
                # the old filter also admitted fortless 2-base spaces).
                if sp.get(C.FORT_PAT, 0) == 0:
                    continue
                mil = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                key = (-mil,)   # Q22: ties table-resolved below
                if best_cont_key is None or key < best_cont_key:
                    best_cont_key = key
                    best_cont_mil = mil
                    best_cont_fort = sid
                    _cont_tied = [sid]
                elif key == best_cont_key:
                    _cont_tied.append(sid)
            if best_cont_fort and len(_cont_tied) > 1:
                # Q22: table-resolved tie among equal keys
                best_cont_fort = (choose_random_space(_cont_tied, state["rng"])
                                  or best_cont_fort)
            if best_cont_fort and best_cont_mil > 0:
                spaces_used.append(best_cont_fort)
                # §3.3.1/§8.1.1: place Militia there to the maximum
                # extent (Session 45: was a single default Militia).
                extent = min(state["spaces"][best_cont_fort].get(C.FORT_PAT, 0)
                             + _MAP_DATA.get(best_cont_fort, {}).get("population", 0),
                             avail_militia)
                if extent > 0:
                    bulk_place_map[best_cont_fort] = extent
                    avail_militia -= extent

        # --- Bullet 4: Continental replacement ---
        # §8.5.2: "In the Patriot Fort space with most Militia OF THOSE
        # ALREADY SELECTED FOR RALLY, replace all Militia except 1
        # Underground with Continentals."
        if avail_cont > 0:
            best_fort = None
            best_mil = -1
            for sid in spaces_used:
                sp = state["spaces"].get(sid, {})
                # Needs a Patriot Fort now or one built this Rally
                # (Session 45: the old filter also admitted fortless
                # 2-base spaces).
                if sp.get(C.FORT_PAT, 0) == 0 and sid not in build_fort_set:
                    continue
                # "most Militia" counts this Rally's planned placements
                mil = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                       + bulk_place_map.get(sid, 0)
                       + (1 if sid in place_one_set else 0))
                if mil > best_mil:
                    best_mil = mil
                    best_fort = sid
            if best_fort and best_mil > 0:
                promote_space = best_fort
                # Replace all except 1 Underground, capped by available Continentals
                promote_n = min(max(0, best_mil - 1), avail_cont)
                if promote_n == 0:
                    promote_space = None
                    promote_n = None

        # --- Bullet 5: Militia at non-Fort space with most Patriot units ---
        # Reference: "If Patriot Fort Available" — check post-Bullet-1 count
        if avail_forts > 0:
            no_fort_spaces = []
            for sid, sp in state["spaces"].items():
                if _bs_o and sid != _bs_o:
                    continue  # leader tie
                if not self._can_rally_in(state, sid):
                    continue
                if sp.get(C.FORT_PAT, 0) > 0 or sid in build_fort_set:
                    continue
                pat_units = self._rebel_group_size(sp)
                no_fort_spaces.append((-pat_units, sid))
            no_fort_spaces.sort()
            for _, sid in no_fort_spaces:
                if len(spaces_used) >= max_rally:
                    break
                if sid not in spaces_used:
                    spaces_used.append(sid)
                    break

        # --- Bullet 6: Militia to change Control or no Active Opposition ---
        remaining_slots = max_rally - len(spaces_used)
        if remaining_slots > 0:
            militia_targets = []
            for sid, sp in state["spaces"].items():
                if _bs_o and sid != _bs_o:
                    continue  # leader tie
                if not self._can_rally_in(state, sid):
                    continue
                if sid in spaces_used:
                    continue
                # §8.5.2 bullet 6: "first to change Control, then in
                # spaces not at Active Opposition" — a space that does
                # neither is not selected (Session 45: no-benefit spaces
                # previously padded the four slots; Control change is now
                # simulated for the 1 placed Militia per §1.7).
                changes_ctrl = 1 if (self._control_after_add(state, sid, 1)
                                     != ctrl.get(sid)) else 0
                no_active_opp = 1 if self._support_level(state, sid) > C.ACTIVE_OPPOSITION else 0
                if not changes_ctrl and not no_active_opp:
                    continue
                is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                militia_targets.append(
                    ((-changes_ctrl, -no_active_opp, -is_city, -pop), sid))
            # Q22: table-resolved ties
            for sid in pick_by_priority(state, militia_targets):
                if len(spaces_used) >= max_rally:
                    break
                spaces_used.append(sid)

        # --- Bullet 7: Move adjacent Militia to 1 Fort, flip Underground ---
        # §8.5.2: "in one Fort space NOT already selected above"
        fort_spaces_for_gather = [
            sid for sid, sp in state["spaces"].items()
            if self._can_rally_in(state, sid)
            and sid not in spaces_used
            and (sp.get(C.FORT_PAT, 0) > 0 or sid in build_fort_set)
            and len(spaces_used) < max_rally  # must have room for one more space
        ]
        if fort_spaces_for_gather:
            # Pick the Fort that can gather the most adjacent Active Militia
            best_gather_fort = None
            best_gather_count = 0
            best_gather_key = None
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
                    # §8.5.2: "that can be moved without changing Control
                    # of their origin spaces" — any change counts,
                    # including Uncontrolled → BRITISH (Session 45: only
                    # Rebellion-control loss was checked).
                    can_take = 0
                    for n in range(active_mil, 0, -1):
                        if (self._control_after_remove(
                                state, adj_sid, {C.MILITIA_A: n})
                                == ctrl.get(adj_sid)):
                            can_take = n
                            break
                    if can_take > 0:
                        gather_moves.append((adj_sid, fort_sid, can_take))
                        gather_total += can_take

                gkey = (-gather_total,)  # Q22: first-found wins equal keys
                if gather_total > 0 and (best_gather_key is None
                                         or gkey < best_gather_key):
                    best_gather_key = gkey
                    best_gather_count = gather_total
                    best_gather_fort = fort_sid
                    best_gather_moves = gather_moves

            if best_gather_moves:
                move_plan_list = best_gather_moves
                # Ensure the Fort is in spaces_used
                if best_gather_fort and best_gather_fort not in spaces_used:
                    if len(spaces_used) < max_rally:
                        spaces_used.append(best_gather_fort)

        if not spaces_used:
            return False

        # Check we have resources to pay
        if state["resources"][self.faction] < 1:
            return False

        # §8.5.2/P7+P13: Execute space-by-space, checking after each space
        # whether resources hit 0 and triggering Persuasion mid-command.
        # Track whether Persuasion was used during Rally for SA chain gate.
        executed_any = False
        persuasion_used = False
        no_sa = state.get("_limited") or state.get("_no_special")
        for sid in spaces_used:
            if state["resources"][self.faction] < 1:
                # Try mid-command Persuasion to restore resources (skip if limited)
                if not no_sa and self._try_persuasion(state):
                    persuasion_used = True
                if state["resources"][self.faction] < 1:
                    break  # still no resources — stop

            kw = {}
            if sid in build_fort_set:
                # Guard: verify the space still has >= 2 removable Patriot
                # units before requesting a fort build.  State may have
                # changed from earlier operations in this turn.
                sp_check = state["spaces"].get(sid, {})
                removable = (sp_check.get(C.MILITIA_U, 0)
                             + sp_check.get(C.MILITIA_A, 0)
                             + sp_check.get(C.REGULAR_PAT, 0))
                if removable >= 2:
                    kw["build_fort"] = {sid}
                else:
                    # Can't build fort — fall back to place_one
                    kw["place_one"] = {sid}
            if sid in place_one_set:
                kw["place_one"] = {sid}
            if sid in bulk_place_map:
                sp_check = state["spaces"].get(sid, {})
                n = min(bulk_place_map[sid],
                        sp_check.get(C.FORT_PAT, 0)
                        + _MAP_DATA.get(sid, {}).get("population", 0))
                if n > 0 and sp_check.get(C.FORT_PAT, 0) > 0:
                    kw["bulk_place"] = {sid: n}
                else:
                    kw["place_one"] = {sid}
            if promote_space == sid:
                kw["promote_space"] = promote_space
                kw["promote_n"] = promote_n
            move_for_space = [(s, d, n) for s, d, n in move_plan_list
                              if d == sid]
            if move_for_space:
                kw["move_plan"] = move_for_space
            try:
                rally.execute(
                    state, self.faction, {},
                    [sid],
                    **kw,
                )
                executed_any = True
                # Check for mid-Rally Persuasion interrupt (skip if limited)
                if not no_sa and state["resources"][self.faction] == 0:
                    if self._try_persuasion(state):
                        persuasion_used = True
            except (ValueError, KeyError):
                continue
        if persuasion_used:
            state["_rally_persuasion_used"] = True
        return executed_any

    # ---------- Rabble-Rousing (P11) ----------------------------------
    @staticmethod
    def _rabble_eligible(state: Dict, sid: str, sp: Dict) -> bool:
        """Check §3.3.4 eligibility: (Rebellion Control AND Patriot pieces) OR
        Underground Militia.  Also must not be at Active Opposition."""
        from lod_ai.rules_consts import ACTIVE_OPPOSITION
        from lod_ai.map.adjacency import space_type
        # S3.3.4: only Provinces or Cities may be Rabble-Roused (Reserves
        # and the West Indies are Always Neutral, S1.6.2) — Session 67.
        if space_type(sid) not in ("City", "Colony"):
            return False
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
        _bs_o = state.get("_bs_leader_origin")  # §8.3.7 BS LimCom1 leader tie (S64)
        refresh_control(state)
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if self._rabble_eligible(state, sid, sp)
            and (not _bs_o or sid == _bs_o)
        ]
        if not spaces:
            return False
        # §8.5.3: "first in spaces with Active Support, within that
        # first in the space with highest Population" — a BINARY
        # Active-Support tier, then Population, then seeded ties (§8.2).
        # (Session 44: was a raw support-level cascade, which wrongly
        # ranked Passive Support above Neutral etc.)
        # Q22: table-resolved ties behind the substantive priorities
        spaces = pick_by_priority(state, [
            ((0 if self._support_level(state, n) == C.ACTIVE_SUPPORT else 1,
              -_MAP_DATA[n].get("population", 0)), n)
            for n in spaces])
        # Limited Command: 1 space only
        if state.get("_limited"):
            spaces = spaces[:1]
        if state["resources"][self.faction] < 1:
            return False

        # §8.5.3/P11+P13: Execute space-by-space, checking after each space
        # whether resources hit 0 and triggering Persuasion mid-command.
        # Track whether Persuasion was used for SA chain gate.
        no_sa = state.get("_limited") or state.get("_no_special")
        executed_any = False
        persuasion_used = False
        for sid in spaces:
            if state["resources"][self.faction] < 1:
                # Try mid-command Persuasion to restore resources (skip if limited)
                if not no_sa and self._try_persuasion(state):
                    persuasion_used = True
                if state["resources"][self.faction] < 1:
                    break  # still no resources — stop
            try:
                rabble_rousing.execute(state, self.faction, {}, [sid])
                executed_any = True
                # Check for mid-Rabble Persuasion interrupt (skip if limited)
                if not no_sa and state["resources"][self.faction] == 0:
                    if self._try_persuasion(state):
                        persuasion_used = True
            except (ValueError, KeyError):
                continue
        if persuasion_used:
            state["_rabble_persuasion_used"] = True
        return executed_any

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
        battle_spaces = state.get("_turn_battle_spaces", set())
        for sid, sp in state["spaces"].items():
            if sid in battle_spaces:
                continue  # §4.3.2: Partisans may not be in a Battle space
            if not sp.get(C.MILITIA_U, 0):
                continue
            has_village = sp.get(C.VILLAGE, 0)
            wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            british = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            # §4.3.2 option 3 is the only Partisans way to remove a
            # Village: no War Parties there and two Underground Militia.
            village_removable = 1 if (has_village and wp == 0
                                      and sp.get(C.MILITIA_U, 0) >= 2) else 0
            # Options 1/2 remove Royalist UNITS (Glossary §1.4 — Forts
            # and Villages are not units).
            enemy_units = wp + british
            if not village_removable and enemy_units == 0:
                continue  # nothing Partisans could remove here
            adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
            key = (-village_removable, -wp, -british, -adds_rebel_ctrl,
                   -removes_brit_ctrl)
            candidates.append((key, sid))
        if not candidates:
            return False
        # Q22: table-resolved ties
        for sid in pick_by_priority(state, candidates):
            sp = state["spaces"][sid]
            has_village = sp.get(C.VILLAGE, 0)
            wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            enemy_units = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                           + sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0))
            ug_militia = sp.get(C.MILITIA_U, 0)
            # §4.3.2 option 3 requires only "If no War Parties there"
            # (plus 2 Underground Militia and a Village) — enemy cubes
            # MAY be present (Session 45, Eric's queue: the old gate
            # wrongly required no enemy cubes).  §8.5.1 removes a
            # Village first.
            if has_village and wp == 0 and ug_militia >= 2:
                opt = 3
            # §8.1 "maximum extent": option 2 nets +1 removal over
            # option 1 when 2+ Royalist units and 2 Underground Militia
            # (§4.3.2 requires two to Activate).
            elif enemy_units >= 2 and ug_militia >= 2:
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
        battle_spaces = state.get("_turn_battle_spaces", set())
        candidates = []
        for sid, sp in state["spaces"].items():
            if sid in battle_spaces:
                continue  # §4.3.3: no Skirmish in a Battle space
            if not sp.get(C.REGULAR_PAT, 0):
                continue
            has_fort = sp.get(C.FORT_BRI, 0)
            enemy_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            has_enemy = has_fort or enemy_cubes
            if not has_enemy:
                continue
            adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
            removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
            key = (-has_fort, -adds_rebel_ctrl, -removes_brit_ctrl)
            candidates.append((key, sid))
        if not candidates:
            return False
        # Q22: table-resolved ties
        for sid in pick_by_priority(state, candidates):
            sp = state["spaces"][sid]
            has_fort = sp.get(C.FORT_BRI, 0)
            enemy_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            own_regs = sp.get(C.REGULAR_PAT, 0)
            # §8.5.1: "first to remove a British Fort" — space selection
            # prefers Fort spaces.  Option 3 (Fort removal) is only valid
            # when no enemy cubes remain in the space (skirmish.execute rule).
            if has_fort and not enemy_cubes:
                opt = 3
            elif enemy_cubes >= 2 and own_regs >= 1:
                opt = 2  # §8.1 "maximum extent": sacrifice 1, remove 2
            else:
                opt = 1
            try:
                skirmish.execute(state, self.faction, {}, sid, option=opt)
                return True
            except Exception:
                continue
        return False

    def _try_persuasion(self, state: Dict) -> bool:
        # Manual §4.1: a Faction may execute one Special Activity per
        # Command turn.  Persuasion fires from several Patriot flowchart
        # nodes (P7 Rally, P8 Partisans, P11 Rabble-Rousing, P12 Skirmish);
        # only the first call per turn is legal.  Gate with a turn-scoped
        # flag (cleared in take_turn).
        if state.get("_turn_persuasion_used"):
            return False
        refresh_control(state)
        ctrl = state.get("control", {})
        spaces = [
            sid for sid, sp in state["spaces"].items()
            if ctrl.get(sid) == "REBELLION" and sp.get(C.MILITIA_U, 0)
            and _MAP_DATA.get(sid, {}).get("type") in ("Colony", "City")
        ]
        if not spaces:
            return False
        # §8.5.1 PERSUASION: "first spaces with Patriot Forts" — a binary
        # presence tier; remaining ties are seeded random per §8.2 (S56:
        # the old sort invented a Population tiebreak).
        # Q22: table-resolved ties behind the Fort-presence tier
        spaces = pick_by_priority(state, [
            ((0 if state["spaces"][n].get(C.FORT_PAT, 0) else 1,), n)
            for n in spaces])
        try:
            persuasion.execute(state, self.faction, {}, spaces=spaces[:3])
            state["_turn_persuasion_used"] = True
            return True
        except (ValueError, KeyError):
            return False

    # ===================================================================
    #  DECISION-HELPER FUNCTIONS
    # ===================================================================
    @staticmethod
    def _fort_room(sp: Dict) -> bool:
        """§1.4.2 stacking: max two base pieces per space. rally.execute's
        _replace_with_fort raises past this; the planner must agree
        (Session 30 — gate 1778:12 crash once turn flags unfroze)."""
        return (sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0)
                + sp.get(C.VILLAGE, 0)) < 2

    def _rally_preferred(self, state: Dict) -> bool:
        """P9: Rally if would place Fort OR 1D6 > Underground Militia."""
        avail_forts = state["available"].get(C.FORT_PAT, 0)
        if avail_forts and any(
            (sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
             + sp.get(C.REGULAR_PAT, 0)) >= 4   # §8.5.2 "4+ Patriot units"
            and sp.get(C.FORT_PAT, 0) == 0
            and (sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0)
                 + sp.get(C.VILLAGE, 0)) < 2       # room (max 2 bases)
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
            # Card 51 (shaded): "Patriots free March to then free Battle in
            # one space."  Patriot bot instruction: "March to set up Battle
            # per the Battle instructions.  If not possible, choose Command
            # & Special Activity instead."
            # T13: evaluated with battle.bot_battle_scores — the exact
            # Force-Level + Loss-modifier maths the resolver uses — over a
            # simulated March from all adjacent origins (the old check
            # hand-rolled halved-Militia approximations and ignored the
            # Loss-Level modifiers entirely).
            refresh_control(state)
            from lod_ai.commands import battle as _battle
            return _battle.bot_march_sets_up_battle(state, C.PATRIOTS)
        if directive == "force_if_80":
            # Card 80 ERRATA: "Choose Indians and select spaces where an
            # Indian Village would be removed. If none, choose Command &
            # SA instead."  T15: the handler removes 2 Indian pieces per
            # selected space in War-Party-first order — a Village is
            # actually removed only where the Indians have >= 2 pieces and
            # at most ONE non-Village piece (so the second removal reaches
            # the Village).  The old check accepted any Village anywhere.
            qualifying = []
            for sid, sp in state["spaces"].items():
                village = sp.get(C.VILLAGE, 0)
                if village == 0:
                    continue
                wps = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
                if wps + village >= 2 and wps <= 1:
                    qualifying.append(sid)
            if qualifying:
                state["card80_faction"] = C.INDIANS
                # Equal-priority spaces -> §8.2 table (Q22; was dict
                # order).
                state["card80_spaces"] = pick_random_spaces(
                    state, qualifying, 2)
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
        # Non-dual cards carry their single printed text under "unshaded"
        # (S8.3.4 shaded-side selection applies to DUAL cards only), so
        # evaluate that column for them — reading the empty "shaded" dict
        # made all six single-sided benefit cards (52/68/72/73/92/95)
        # invisible to this bullet list (Piece 5 coverage, Session 67).
        eff = effects["shaded"] if card.get("dual") else effects["unshaded"]

        sup, opp = self._support_opposition_totals(state)

        if sup > opp:
            if eff["shifts_support_rebel"]:
                return True
            # §8.5 bullet 1 "(including by increasing FNI...)" —
            # dynamic §1.9 check (Session 49).
            if eff.get("raises_fni"):
                from lod_ai.util.naval import fni_raise_could_reduce_support
                if fni_raise_could_reduce_support(state):
                    return True
        if eff["places_patriot_militia_u"] and state.get("available", {}).get(C.MILITIA_U, 0) > 0:
            # P2 bullet 2 (§8.5): "places Underground Militia in at least one
            # Active Support or Village space that has none already"
            for sid, sp in state["spaces"].items():
                has_militia = (sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)) > 0
                if has_militia:
                    continue
                sup = state.get("support", {}).get(sid, 0)
                if sup == C.ACTIVE_SUPPORT or sp.get(C.VILLAGE, 0) > 0:
                    return True
        if eff["places_patriot_fort"]:
            if state.get("available", {}).get(C.FORT_PAT, 0) > 0:
                return True
        if eff["removes_village"]:
            if any(sp.get(C.VILLAGE, 0) > 0
                   for sp in state.get("spaces", {}).values()):
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
        """§8.5.6: Redeploy Washington to the space with most
        Continentals.  §6.5.2 scopes legal targets to spaces with the
        Faction's own pieces — at 0 Continentals the pick falls back to
        any Patriot-piece space, and with no Patriot pieces anywhere
        Washington goes to Available (None).  §8.2 table ties (Q22).
        (Session 43: the old scan could return a Patriot-less
        dict-order space at 0 Continentals.)"""
        scored = []
        for sid, sp in state["spaces"].items():
            pat_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0)
                          + sp.get(C.MILITIA_U, 0) + sp.get(C.FORT_PAT, 0))
            if pat_pieces == 0:
                continue  # §6.5.2: not a legal redeploy space
            scored.append(((-sp.get(C.REGULAR_PAT, 0),), sid))
        picked = pick_by_priority(state, scored, count=1)  # Q22
        return picked[0] if picked else None

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
                # §8.2 seeded-random tie-break (Session 45: was
                # alphabetical space order).
                candidates.append(((changes, is_last), (sid, tag)))
        # Q22: table-resolved ties within equal priority tuples;
        # sids resolved per group, tags re-attached.
        by_key = {}
        for key, pair in candidates:
            by_key.setdefault(key, []).append(pair)
        out = []
        for key in sorted(by_key):
            group = by_key[key]
            sids = [s for s, _t in group]
            ordered = pick_by_priority(state, [((0,), s) for s in sids])
            tag_by_sid = {}
            for s, t in group:
                tag_by_sid.setdefault(s, []).append(t)
            for s in ordered:
                for t in tag_by_sid.get(s, []):
                    out.append((s, t))
        return out

    def ops_bs_trigger(self, state: Dict) -> bool:
        """Brilliant Stroke: Use after Treaty of Alliance when Washington is
        in a space with 4+ Continentals, and a player Faction is 1st Eligible."""
        if not state.get("toa_played"):
            return False
        # §8.5.8: "a player Faction is 1st Eligible"
        human_factions = state.get("human_factions", set())
        eligible = state.get("eligible", {})
        first_eligible = state.get("first_eligible")
        if first_eligible and first_eligible not in human_factions:
            return False  # 1st Eligible is not a player Faction
        wash_loc = leader_location(state, "LEADER_WASHINGTON")
        if not wash_loc:
            return False
        sp = state["spaces"].get(wash_loc, {})
        return sp.get(C.REGULAR_PAT, 0) >= 4
