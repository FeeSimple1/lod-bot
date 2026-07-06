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

from typing import Dict, List, Tuple
from pathlib import Path
import json

from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai import rules_consts as C
from lod_ai.commands import raid, gather, march, scout
from lod_ai.special_activities import plunder, war_path, trade
from lod_ai.board.control import refresh_control
from lod_ai.leaders import leader_location
from lod_ai.util.history import push_history
from lod_ai.map import adjacency as map_adj
from lod_ai.map.adjacency import shortest_path
from lod_ai.economy.resources import can_afford

# ----------------------------------------------------------------------
#  MAP helpers
# ----------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)

def _adjacent(space: str) -> List[str]:
    """Return adjacent spaces (bidirectional)."""
    return list(map_adj.adjacent_spaces(space))


def _ops_leader_destination(state: Dict, leader: str) -> str | None:
    """OPS Leader Movement (§8.1): follow the largest group of own units
    that moves from (or stays in) the leader's origin space; equal-size
    groups are selected RANDOMLY (seeded rng).

    Approximation note (TRACEABILITY T5, partial): the executors do not
    record which War Parties moved this command, so "group that moved
    from origin" is approximated by post-move WP counts in the origin and
    its neighbours. Full fidelity needs move recording in the March/
    Scout/Gather/Raid executors."""
    loc = leader_location(state, leader)
    if not loc:
        return None

    def _wp(sid: str) -> int:
        sp = state["spaces"].get(sid, {})
        return sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)

    candidates = [(_wp(loc), loc)] + [(_wp(n), n) for n in _adjacent(loc)]
    best = max(cnt for cnt, _ in candidates)
    if best == 0:
        return None
    ties = [sid for cnt, sid in candidates if cnt == best]
    if ties == [loc]:
        return None                      # origin group is largest → stays
    if len(ties) == 1:
        pick = ties[0]
    else:
        # §8.1: "If two or more such groups are of the same size, select
        # which one the Leader joins randomly."
        rng = state.get("rng")
        pick = (ties[rng.randrange(len(ties))] if rng is not None
                else sorted(ties)[0])
    return None if pick == loc else pick


def follow_indian_leaders_after_move(state: Dict) -> None:
    """OPS: each Indian Leader (Brant / Cornplanter / Dragging Canoe) follows
    the largest group of War Parties that moves from (or stays in) its space.

    Module-level so it can run after ANY command that moves War Parties --
    including a *British* March that used Common Cause, where War Parties move
    as Tory-equivalents out of an Indian Leader's space (the leader must
    still follow per OPS). Operates purely on post-move board state.
    """
    leaders_state = state.get("leaders")
    leader_locs = state.get("leader_locs")
    for leader in ("LEADER_BRANT", "LEADER_CORNPLANTER", "LEADER_DRAGGING_CANOE"):
        current_loc = leader_location(state, leader)
        if not current_loc:
            continue
        new_loc = _ops_leader_destination(state, leader)
        if not new_loc or new_loc == current_loc:
            continue
        updated = False
        if isinstance(leaders_state, dict):
            if leader in leaders_state and isinstance(leaders_state.get(leader), (str, type(None))):
                leaders_state[leader] = new_loc
                updated = True
            else:
                keys_to_remove = [k for k, v in leaders_state.items() if v == leader]
                if keys_to_remove:
                    for k in keys_to_remove:
                        leaders_state.pop(k, None)
                    leaders_state[new_loc] = leader
                    updated = True
        if isinstance(leader_locs, dict) and leader in leader_locs:
            leader_locs[leader] = new_loc
            updated = True
        if updated:
            push_history(
                state,
                f"{leader} follows largest WP group: {current_loc} -> {new_loc}"
            )


class IndianBot(BaseBot):
    faction = C.INDIANS

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    # ==================================================================
    #  BRILLIANT STROKE LimCom  (§8.3.7)
    # ==================================================================
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk Indian flowchart for the first valid Limited Command
        that can involve the Indian Leader in the Leader's current space.

        Flowchart order: I3 (D6 gate) → I4 (Raid) / I6 (Gather) → I9 (Scout) → I10 (March).
        Returns a command name or None.
        """
        leader_space = self._find_bs_leader_space(state)
        if not leader_space:
            return None

        sp = state["spaces"].get(leader_space, {})
        wp_total = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)

        # I3: (Support + 1D6) > Opposition?
        support, opposition = self._support_opposition_totals(state)
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("I3 BS D6", roll))
        i3_yes = (support + roll) > opposition

        if not i3_yes:
            # --- Raid branch (I3 No → I4) ---
            # I4: Raid — leader's space must be an Opposition Colony with or
            # adjacent to Underground War Parties
            stype = _MAP_DATA.get(leader_space, {}).get("type", "")
            sup_level = self._support_level(state, leader_space)
            if (stype == "Colony"
                    and sup_level <= C.PASSIVE_OPPOSITION
                    and sp.get(C.WARPARTY_U, 0) > 0):
                return "raid"
            # If Raid not possible, fall through to Gather (I6)

        # --- Gather branch (I3 Yes, or Raid not possible) ---
        # I6/I7: Gather — leader's space has room for Village or WP can be
        # placed there
        avail_wp = (state["available"].get(C.WARPARTY_U, 0)
                    + state["available"].get(C.WARPARTY_A, 0))
        avail_villages = state["available"].get(C.VILLAGE, 0)
        if avail_wp > 0 or avail_villages > 0:
            # Gather is viable if we can place WP or Villages at leader's space
            if self._village_room(state, leader_space) or wp_total > 0:
                return "gather"

        # I9: Scout — leader's space has War Party AND British Regulars?
        if wp_total > 0 and sp.get(C.REGULAR_BRI, 0) > 0:
            return "scout"

        # I10: March — War Parties exist in leader's space
        if wp_total > 0:
            return "march"

        return None

    # ==================================================================
    #  FLOW‑CHART DRIVER
    # ==================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        """
        Implements nodes I3‑I12.  I1/I2 (Event handling) is already covered
        by BaseBot._choose_event_vs_flowchart().
        """
        # ---------- I3 test  (Support+1D6) > Opposition -----------------
        support, opposition = self._support_opposition_totals(state)
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Support test 1D6", roll))

        if (support + roll) <= opposition:
            if self._raid_sequence(state):    # I4 → I5
                return
            # Failed Raid → the I6 decision, NOT unconditional Gather.
            # Manual 8.7.2 and the I4 box fine print say "instead Gather";
            # the flowchart edge routes to I6. QUESTIONS.md Q17 ruling
            # (Eric, July 2026): the specific flowchart routing controls
            # over the general manual clause — Gather still takes its
            # 2-Villages-or-die-roll entry test. Same for a failed March.
            self._reset_command_trace(state)

        # ---------- I6 decision ----------------------------------------
        if self._gather_worthwhile(state):
            if self._gather_sequence(state):  # I7 → I8 / I10
                return
        else:
            # I9 decision (space with War Party & British Regulars?)
            if self._space_has_wp_and_regulars(state):
                if self._scout_sequence(state):   # I12 → I8 / I10
                    return
                self._reset_command_trace(state)
            # Otherwise I10 March chain
            if self._march_sequence(state):   # I10 → I8 / I7
                return

        # If nothing executed, Pass
        state['_pass_reason'] = 'no_valid_command'
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

        no_sa = state.get("_limited") or state.get("_no_special")
        if not no_sa and not state.get("_turn_used_special"):
            # ONE Special Activity total (§4.1). 8.7.1: if Resources fell
            # to zero during the Raid, "Plunder (or if that is not
            # possible, Trade)"; otherwise I5: Plunder in a Raid space,
            # else War Path, else Trade. (Previously this block ran
            # Plunder AND Trade unconditionally at 0 Resources and then
            # fell through to the I5 block — up to three SAs per turn.
            # Session 35.)
            if state["resources"].get(C.INDIANS, 0) == 0:
                if not (self._can_plunder(state) and self._plunder(state)):
                    self._trade(state)
            elif not (self._can_plunder(state) and self._plunder(state)):
                self._war_path_or_trade(state)
        return True

    # ---- I7 Gather then I8 / I10 -------------------------------------
    def _gather_sequence(self, state: Dict, _visited: set | None = None) -> bool:
        if _visited is None:
            _visited = set()
        if "gather" in _visited:
            return False
        _visited.add("gather")
        if not self._can_gather(state):
            return False
        if not self._gather(state):
            # If Gather impossible → I10 March
            self._reset_command_trace(state)
            return self._march_sequence(state, _visited)
        # After Gather comes War‑Path (I8) then Trade fallback (skip if limited)
        if not (state.get("_limited") or state.get("_no_special")):
            self._war_path_or_trade(state)
        return True

    # ---- I12 Scout then I8 / I10 -------------------------------------
    def _scout_sequence(self, state: Dict) -> bool:
        if not self._can_scout(state):
            return False
        if not self._scout(state):
            # If Scout impossible → I10 March
            self._reset_command_trace(state)
            return self._march_sequence(state)
        # Then War‑Path (+ Trade) (skip if limited)
        if not (state.get("_limited") or state.get("_no_special")):
            self._war_path_or_trade(state)
        return True

    # ---- I10 March then I8 / I7 --------------------------------------
    def _march_sequence(self, state: Dict, _visited: set | None = None) -> bool:
        if _visited is None:
            _visited = set()
        if "march" in _visited:
            return False
        _visited.add("march")
        if not self._can_march(state):
            self._reset_command_trace(state)
            return self._gather_sequence(state, _visited)  # arrow "If none → Gather"
        if not self._march(state):
            self._reset_command_trace(state)
            return self._gather_sequence(state, _visited)
        # War‑Path (+ Trade) (skip if limited)
        if not (state.get("_limited") or state.get("_no_special")):
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
                state["spaces"].get(nbr, {}).get(C.WARPARTY_U, 0) > 0
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
        # Track DC extended-range budget separately: mirrors raid.py's
        # dc_pool / dc_used validation.  Only non-adjacent moves from DC's
        # location consume extended-range budget.
        dc_initial_pool = available_wp.get(dc_loc, 0) if dc_loc else 0
        dc_extended_used = 0

        # Priority: first where Plunder possible (WP > Rebels), within each highest Pop
        def score(space: str) -> Tuple[int, int]:
            sp = state["spaces"][space]
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            wp_total = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            pop = _MAP_DATA.get(space, {}).get("population", 0)
            return (wp_total - rebels, pop)

        # 8.7.1: "first where Plunder will be possible after the Raid
        # movement, then elsewhere, within each in the spaces with the
        # highest Population" — a two-TIER sort (boolean, then Pop), not
        # a raw WP-minus-Rebels margin; equal candidates break randomly
        # per 8.2 (Session 35).
        def tier_key(space: str) -> Tuple[int, int]:
            sp = state["spaces"][space]
            rebels = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                      + sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                      + sp.get(C.FORT_PAT, 0))
            wp_total = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            wp_after = wp_total + (1 if (wp_total == 0
                                         or wp_total <= rebels) else 0)
            pop = _MAP_DATA.get(space, {}).get("population", 0)
            return (1 if wp_after > rebels else 0, pop)

        from lod_ai.bots.random_spaces import pick_random_spaces
        groups: Dict[Tuple[int, int], List[str]] = {}
        for t in targets:
            groups.setdefault(tier_key(t), []).append(t)
        targets = []
        for key in sorted(groups, reverse=True):
            g = groups[key]
            targets.extend(g if len(g) == 1
                           else pick_random_spaces(state, g, len(g)))
        selected: List[str] = []
        move_plan: List[Tuple[str, str]] = []

        def _is_adjacent(src: str, dst: str) -> bool:
            return dst in _adjacent(src)

        def _reserve_source(dst: str) -> str | None:
            nonlocal dc_extended_used
            # prefer adjacent Underground WP (includes DC loc if adjacent)
            for src in _adjacent(dst):
                if available_wp.get(src, 0) <= 0:
                    continue
                if state["spaces"][src].get(C.VILLAGE, 0) and available_wp[src] == 1:
                    continue  # avoid stripping last WP from a Village space
                return src
            # DC extended-range fallback: only if DC has WP remaining AND
            # we haven't exhausted the DC pool budget AND the destination
            # is within 2 moves of DC (but NOT adjacent, since adjacent
            # was already checked above).
            if (dc_loc
                    and available_wp.get(dc_loc, 0) > 0
                    and dc_initial_pool > dc_extended_used):
                if not _is_adjacent(dc_loc, dst):
                    path = shortest_path(dc_loc, dst)
                    if path and (len(path) - 1) <= 2:
                        dc_extended_used += 1
                        return dc_loc
            return None

        # Q18 ruling (QUESTIONS.md, July 3 2026 — specific over general):
        # §8.7.1 "If Resources fall to zero during the Raid Command,
        # Plunder (or if that is not possible, Trade) before completing
        # the Raid Command" governs over §3.1's affordability clause.
        # With an unspent SA the non-player Indians may SELECT up to
        # three targets regardless of the current purse and refuel
        # mid-Command; without an SA in hand, selection stays capped at
        # affordability (the Playbook's Indian example, where Trade was
        # already spent).
        sa_available = not (state.get("_limited")
                            or state.get("_no_special")
                            or state.get("_turn_used_special"))
        if sa_available:
            max_raid = 3
        else:
            max_raid = min(3, state["resources"].get(C.INDIANS, 0))
        if state.get("_limited"):
            max_raid = min(max_raid, 1)
        for tgt in targets:
            if len(selected) >= max_raid:
                break
            tgt_sp = state["spaces"][tgt]
            wp_in_tgt = tgt_sp.get(C.WARPARTY_U, 0) + tgt_sp.get(C.WARPARTY_A, 0)
            rebels_in_tgt = (tgt_sp.get(C.MILITIA_A, 0) + tgt_sp.get(C.MILITIA_U, 0)
                             + tgt_sp.get(C.REGULAR_PAT, 0) + tgt_sp.get(C.REGULAR_FRE, 0)
                             + tgt_sp.get(C.FORT_PAT, 0))
            # Move a WP into target if: none present OR WP don't exceed Rebels
            needs_move = (wp_in_tgt == 0) or (wp_in_tgt <= rebels_in_tgt)
            if needs_move:
                src = _reserve_source(tgt)
                if src is None and tgt_sp.get(C.WARPARTY_U, 0) == 0:
                    continue  # can't raid without any WP present
                if src is not None:
                    selected.append(tgt)
                    move_plan.append((src, tgt))
                    available_wp[src] -= 1
                elif tgt_sp.get(C.WARPARTY_U, 0) > 0:
                    selected.append(tgt)  # has UG WP, no move needed
            else:
                # WP exceed Rebels, but raid still needs an Underground WP
                if tgt_sp.get(C.WARPARTY_U, 0) > 0:
                    selected.append(tgt)
                else:
                    # All WP are Active — move in an Underground one
                    src = _reserve_source(tgt)
                    if src is not None:
                        selected.append(tgt)
                        move_plan.append((src, tgt))
                        available_wp[src] -= 1

        if not selected:
            return False

        # Final validation: ensure every (src, dst) in move_plan passes
        # the same adjacency / DC-extended-range check that raid.execute()
        # will perform, so we never hand it an invalid plan.
        dc_verify_used = 0
        validated_plan: List[Tuple[str, str]] = []
        validated_selected: List[str] = []
        plan_dsts = {dst for _, dst in move_plan}
        for src, dst in move_plan:
            path = shortest_path(src, dst)
            dist = (len(path) - 1) if path else None
            is_dc_ext = (dc_loc and src == dc_loc
                         and dc_initial_pool > dc_verify_used
                         and dist is not None and dist <= 2)
            if is_dc_ext:
                dc_verify_used += 1
                validated_plan.append((src, dst))
                validated_selected.append(dst)
            elif dist == 1:
                validated_plan.append((src, dst))
                validated_selected.append(dst)
            # else: skip this move — it would fail validation in raid.py

        # Add targets that didn't need a move (already have WP)
        for tgt in selected:
            if tgt not in plan_dsts and tgt not in validated_selected:
                validated_selected.append(tgt)

        if not validated_selected:
            return False

        # Final Underground WP check: after all validated moves, every target
        # must have at least 1 Underground WP.  Moves OUT of a target as a
        # source can leave it without an Underground WP.
        wp_delta: Dict[str, int] = {}
        for src, dst in validated_plan:
            wp_delta[src] = wp_delta.get(src, 0) - 1
            wp_delta[dst] = wp_delta.get(dst, 0) + 1
        final_selected = []
        for tgt in validated_selected:
            base_ug = state["spaces"][tgt].get(C.WARPARTY_U, 0)
            after_ug = base_ug + wp_delta.get(tgt, 0)
            if after_ug >= 1:
                final_selected.append(tgt)
            else:
                # Remove any validated moves targeting this space
                validated_plan = [(s, d) for s, d in validated_plan if d != tgt]
        validated_selected = final_selected

        if not validated_selected:
            return False

        res = state["resources"].get(C.INDIANS, 0)
        if len(validated_selected) <= res:
            raid.execute(state, C.INDIANS, {}, validated_selected,
                         move_plan=validated_plan)
            self._follow_leaders_after_move(state)
            return True

        # Q18 ruling: raid the affordable spaces first, replenish
        # mid-Command (Plunder in a just-raided space, else Trade), then
        # raid the remainder with the new funds.  Unpaid spaces are
        # skipped when the replenish comes up short.  (Over-selection
        # only happens with an unspent SA — see max_raid above.)
        def _batch(spaces_batch):
            plan_batch = [(s, d) for s, d in validated_plan
                          if d in spaces_batch]
            raid.execute(state, C.INDIANS, {}, spaces_batch,
                         move_plan=plan_batch)

        first = validated_selected[:res]
        rest = validated_selected[res:]
        raided_any = False
        if first:
            _batch(first)
            raided_any = True
        # Mid-raid replenish (§8.7.1).  Plunder removes one War Party
        # from its space, so exclude the remaining batch's move SOURCES
        # from the Plunder pick — their War Parties are spoken for.
        rest_sources = {s for s, d in validated_plan if d in rest}
        if not (self._can_plunder(state)
                and self._plunder(state, exclude=rest_sources)):
            self._trade(state)
        res = state["resources"].get(C.INDIANS, 0)
        if rest and res > 0:
            # The first batch's raids Activate Underground War Parties
            # (and the replenish Plunder may remove one), so a remainder
            # space can lose its §3.4.4 Underground-WP access between
            # batches (gate 1776:9, Session 48).  Execute the remainder
            # one space at a time, skipping any space that no longer
            # qualifies (§5.1.3 / the Q18 skip-unpaid pattern).
            for tgt in rest[:res]:
                if state["resources"].get(C.INDIANS, 0) < 1:
                    break
                plan_t = [(s, d) for s, d in validated_plan if d == tgt]
                try:
                    raid.execute(state, C.INDIANS, {}, [tgt],
                                 move_plan=plan_t)
                    raided_any = True
                except (ValueError, KeyError):
                    continue
        if not raided_any:
            return False
        self._follow_leaders_after_move(state)
        return True

    # ------------------------------------------------------------------
    # PLUNDER  (Special Activity)  -------------------------------------
    def _can_plunder(self, state: Dict) -> bool:
        if state["resources"][C.PATRIOTS] == 0:
            return False
        # I5: Plunder candidates restricted to Raid spaces only
        raid_spaces = state.get("_turn_affected_spaces", set())
        for sid in raid_spaces:
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            if pop <= 0:
                continue  # no population to plunder
            sp = state["spaces"].get(sid, {})
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            if wp > rebels and wp > 0:
                return True
        return False

    def _plunder(self, state: Dict, exclude: set | None = None) -> bool:
        """I5: Plunder in a Raid space with more WP than Rebels, highest Pop.

        `exclude` (Q18 mid-raid path): spaces whose War Parties are
        reserved as sources for the rest of the Raid — Plunder removes a
        War Party, so picking one of these could strand a planned move.
        """
        # Filter to spaces affected by the Raid command
        raid_spaces = state.get("_turn_affected_spaces", set())
        exclude = exclude or set()
        choices = []
        for sid in raid_spaces:
            if sid in exclude:
                continue
            sp = state["spaces"].get(sid, {})
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            if pop <= 0:
                continue  # no population to plunder
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            rebels = (
                sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            if wp > rebels and wp > 0:
                choices.append((pop, sid))
        if not choices:
            return False
        target = max(choices)[1]
        plunder.execute(state, C.INDIANS, {"raid_active": True}, target)
        return True

    # ------------------------------------------------------------------
    # GATHER  (Command)  -----------------------------------------------
    def _gather_worthwhile(self, state: Dict) -> bool:
        """
        I6 test: Gather would place 2+ Villages, OR 1D6 < Available War Parties?
        "Would place" means: 2+ Available Villages AND 2+ eligible spaces.
        """
        avail_villages = state["available"].get(C.VILLAGE, 0)
        if avail_villages >= 2:
            corn_loc = leader_location(state, "LEADER_CORNPLANTER")
            eligible_count = 0
            for sid, sp in state["spaces"].items():
                # §3.4.1: Gather selects Provinces at Neutral/Passive only
                # (Session 51: the worthwhile count ignored the support
                # gate) and a 1-Village space WITH room takes a second
                # Village (§1.4.2 — the old check excluded them).
                if not self._gather_support_ok(state, sid):
                    continue
                if not self._village_room(state, sid):
                    continue
                total_wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
                threshold = 2 if sid == corn_loc else 3
                if total_wp >= threshold:
                    eligible_count += 1
                    if eligible_count >= 2:
                        return True
        avail_wp = state["available"].get(C.WARPARTY_U, 0) + state["available"].get(C.WARPARTY_A, 0)
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Gather test 1D6", roll))
        return roll < avail_wp

    def _can_gather(self, state: Dict) -> bool:
        return True  # always allowed

    def _village_room(self, state: Dict, sid: str) -> bool:
        """Return True if *sid* has room for a Village (bases < 2 stacking limit)."""
        sp = state["spaces"][sid]
        bases = sp.get(C.VILLAGE, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.FORT_PAT, 0)
        return bases < 2

    def _gather_support_ok(self, state: Dict, sid: str) -> bool:
        """Return True if *sid* is at an eligible support level for Gather."""
        sup = self._support_level(state, sid)
        return sup in (C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION)

    def _gather(self, state: Dict) -> bool:
        """I7: Gather (Max 4 spaces).

        Reference bullets:
        1. Place Villages where room and 3+ War Parties (2+ if Cornplanter
           in the space), first with Indian Leader.
        2. Then place War Parties at Villages, first where enemies, then
           where no Underground War Parties, then with Indian Leader, then random.
        3. If any Villages Available: Place War Parties in 2 spaces with room
           for a Village, first where exactly 2 WP already, then where exactly
           1 WP, then random.
        4. Then if no more WP Available, in 1 Village space move in all
           adjacent Active War Parties possible without adding any Rebel
           Control, then flip them Underground.
        """
        corn_loc = leader_location(state, "LEADER_CORNPLANTER")
        brant_loc = leader_location(state, "LEADER_BRANT")
        dc_loc = leader_location(state, "LEADER_DRAGGING_CANOE")
        leader_locs = {loc for loc in (corn_loc, brant_loc, dc_loc) if loc}

        avail_villages = state["available"].get(C.VILLAGE, 0)
        avail_wp = state["available"].get(C.WARPARTY_U, 0) + state["available"].get(C.WARPARTY_A, 0)

        gather_max = 1 if state.get("_limited") else 4
        selected: List[str] = []
        build_village: set = set()
        bulk_place: Dict[str, int] = {}

        # --- Bullet 1: Place Villages where room and 3+ WP (2+ if Cornplanter) ---
        village_cands = []
        for sid, sp in state["spaces"].items():
            if not self._gather_support_ok(state, sid):
                continue
            if not self._village_room(state, sid):
                continue
            # §8.7.2 bullet 1: "each space with room for one and at least
            # three War Parties" — a 1-Village space with base room takes
            # a SECOND Village (§1.4.2; gather.execute allows it; Session
            # 51: such spaces were excluded).
            total_wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
            threshold = 2 if sid == corn_loc else 3
            if total_wp < threshold:
                continue
            has_leader = 1 if sid in leader_locs else 0
            village_cands.append((-has_leader, state["rng"].random(), sid))
        village_cands.sort()

        villages_placed = 0
        for _, _, sid in village_cands:
            if villages_placed >= avail_villages:
                break
            if len(selected) >= gather_max:
                break
            selected.append(sid)
            build_village.add(sid)
            villages_placed += 1

        # --- Bullet 2: Place War Parties at Villages ---
        if avail_wp > 0:
            wp_cands = []
            for sid, sp in state["spaces"].items():
                if not self._gather_support_ok(state, sid):
                    continue
                if sp.get(C.VILLAGE, 0) == 0 and sid not in build_village:
                    continue  # needs a Village (or about to get one)
                enemies = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                           + sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0))
                has_ug = 1 if sp.get(C.WARPARTY_U, 0) > 0 else 0
                has_leader = 1 if sid in leader_locs else 0
                # Priority: enemies first, then no UG WP, then leader, then random
                wp_cands.append((-enemies, has_ug, -has_leader, state["rng"].random(), sid))
            wp_cands.sort()
            for _, _, _, _, sid in wp_cands:
                if len(selected) >= gather_max:
                    break
                if avail_wp <= 0:
                    break
                if sid not in selected:
                    selected.append(sid)
                # Determine how many WP to place: villages + 1
                sp = state["spaces"][sid]
                villages_in_space = sp.get(C.VILLAGE, 0) + (1 if sid in build_village else 0)
                n_place = min(avail_wp, villages_in_space + 1)
                if n_place > 0:
                    bulk_place[sid] = bulk_place.get(sid, 0) + n_place
                    avail_wp -= n_place

        # --- Bullet 3: If any Villages Available, place WP in 2 spaces with
        #     room for a Village (exactly 2 WP first, then 1, then random) ---
        remaining_avail_villages = state["available"].get(C.VILLAGE, 0) - villages_placed
        if remaining_avail_villages > 0 and avail_wp > 0:
            room_cands = []
            for sid, sp in state["spaces"].items():
                if not self._gather_support_ok(state, sid):
                    continue
                if not self._village_room(state, sid):
                    continue
                if sp.get(C.VILLAGE, 0) > 0:
                    continue
                if sid in build_village:
                    continue
                total_wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
                # Priority: exactly 2 WP first, then 1 WP, then random
                if total_wp == 2:
                    pri = 0
                elif total_wp == 1:
                    pri = 1
                else:
                    pri = 2
                room_cands.append((pri, state["rng"].random(), sid))
            room_cands.sort()
            self._b3_placed = 0
            placed_count = 0
            for _, _, sid in room_cands:
                if placed_count >= 2:
                    break
                if len(selected) >= gather_max:
                    break
                if avail_wp <= 0:
                    break
                if sid not in selected:
                    selected.append(sid)
                # Bullet 3 places WP in spaces without Village yet, so use
                # place_one (gather.execute default) instead of bulk_place
                # which requires an existing Village.
                avail_wp -= 1
                placed_count += 1
                self._b3_placed = placed_count

        # --- Bullet 4: If no more WP Available, in 1 Village space move in
        #     all adjacent Active WP without adding Rebel Control, flip UG ---
        final_avail_wp = state["available"].get(C.WARPARTY_U, 0) + state["available"].get(C.WARPARTY_A, 0)
        # Subtract what we plan to place — bullet 2's bulk placements AND
        # bullet 3's single placements (Session 51: bullet 3 was not
        # counted, so bullet 4 fired less often than §8.7.2 says).
        final_avail_wp -= sum(bulk_place.values())
        final_avail_wp -= getattr(self, "_b3_placed", 0)
        move_plan_list: List[Tuple[str, str, int]] = []
        if final_avail_wp <= 0:
            refresh_control(state)
            ctrl = state.get("control", {})
            best_dst = None
            best_moves: List[Tuple[str, int]] = []
            best_total = 0
            for sid, sp in state["spaces"].items():
                if sp.get(C.VILLAGE, 0) == 0:
                    continue
                if not self._gather_support_ok(state, sid):
                    continue
                moves = []
                total = 0
                for nbr in _adjacent(sid):
                    nsp = state["spaces"].get(nbr, {})
                    active_wp = nsp.get(C.WARPARTY_A, 0)
                    if active_wp == 0:
                        continue
                    # "without adding any Rebel Control" — simulate the
                    # departure per §1.7 (Session 51: the old shortcut
                    # only caught spaces losing ALL Indian pieces and
                    # missed partial departures that still flipped
                    # Control).
                    if ctrl.get(nbr) != "REBELLION":
                        rebel_pieces = (nsp.get(C.MILITIA_A, 0) + nsp.get(C.MILITIA_U, 0)
                                        + nsp.get(C.REGULAR_PAT, 0) + nsp.get(C.REGULAR_FRE, 0)
                                        + nsp.get(C.FORT_PAT, 0))
                        royal_after = (nsp.get(C.REGULAR_BRI, 0) + nsp.get(C.TORY, 0)
                                       + nsp.get(C.FORT_BRI, 0) + nsp.get(C.VILLAGE, 0)
                                       + nsp.get(C.WARPARTY_U, 0))   # Actives leave
                        if rebel_pieces > royal_after:
                            continue  # would add Rebel Control
                    moves.append((nbr, active_wp))
                    total += active_wp
                if total > best_total:
                    best_total = total
                    best_dst = sid
                    best_moves = moves
            if best_dst and best_moves:
                if best_dst not in selected:
                    if len(selected) < gather_max:
                        selected.append(best_dst)
                    else:
                        best_dst = None
                if best_dst:
                    for src, n in best_moves:
                        move_plan_list.append((src, best_dst, n))

        if not selected:
            return False

        # §3.4.1: 1 Resource per Province, but "Pay 0 for the first
        # Indian Reserve Province" — gather.execute applies the same
        # discount (Session 51: the old conservative check refused a
        # free single-Reserve Gather at 0 Resources).
        def _gather_cost(sel):
            cost = len(sel)
            if any(_MAP_DATA.get(s, {}).get("type") == "Reserve"
                   for s in sel):
                cost -= 1
            return cost

        res_now = state["resources"].get(C.INDIANS, 0)
        while selected and _gather_cost(selected) > res_now:
            selected.pop()          # trim lowest-priority picks first
        if not selected:
            return False

        # Remove spaces from build_village that aren't in selected
        build_village = build_village & set(selected)
        # Remove bulk_place entries for spaces not selected
        bulk_place = {s: n for s, n in bulk_place.items() if s in selected}
        # Remove move_plan entries whose destination was pruned from selected
        selected_set = set(selected)
        move_plan_list = [(s, d, n) for s, d, n in move_plan_list
                          if d in selected_set]

        # Validate move_plan against actual state: gather.execute() processes
        # build_village first (removing 2 WP from the space), so if a source
        # space is also a build_village target, the planned move count may
        # exceed the post-village WP count.
        if move_plan_list:
            _wp_avail: Dict[str, int] = {}
            for src, _, _ in move_plan_list:
                if src not in _wp_avail:
                    sp_s = state["spaces"].get(src, {})
                    total_wp = sp_s.get(C.WARPARTY_U, 0) + sp_s.get(C.WARPARTY_A, 0)
                    # Account for WP removed by build_village
                    if src in build_village:
                        total_wp -= 2
                    _wp_avail[src] = max(0, total_wp)
            capped_moves = []
            for src, dst, n in move_plan_list:
                take = min(n, _wp_avail.get(src, 0))
                if take > 0:
                    capped_moves.append((src, dst, take))
                    _wp_avail[src] -= take
            move_plan_list = capped_moves

        gather.execute(
            state, C.INDIANS, {}, selected,
            build_village=build_village if build_village else None,
            bulk_place=bulk_place if bulk_place else None,
            move_plan=move_plan_list if move_plan_list else None,
        )
        self._follow_leaders_after_move(state)
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
            # ("Province" = Colony or Reserve; map.json has no "Province"
            # type, so the previous == "Province" check never matched)
            is_prov = 1 if _MAP_DATA.get(sid, {}).get("type") in ("Colony", "Reserve") else 0
            has_village = 1 if sp.get(C.VILLAGE, 0) >= 1 else 0
            prov_vill = is_prov * has_village
            choices.append((fort, enemy, prov_vill, state["rng"].random(), sid))
        if not choices:
            return False
        target = max(choices)[-1]
        tsp = state["spaces"][target]
        # Select the correct War Path option per §4.4.2:
        #   option 3 = remove Patriot Fort (requires no Rebel cubes, 2+ WP_U)
        #   option 2 = activate 2 WP, remove 1, remove 2 Rebel units (need 2+ WP_U)
        #   option 1 = activate 1 WP, remove 1 Rebel unit (default)
        rebel_cubes = sum(tsp.get(t, 0) for t in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE))
        if tsp.get(C.FORT_PAT, 0) and rebel_cubes == 0 and tsp.get(C.WARPARTY_U, 0) >= 2:
            option = 3
        elif rebel_cubes >= 2 and tsp.get(C.WARPARTY_U, 0) >= 2:
            option = 2
        elif rebel_cubes >= 1:
            option = 1
        else:
            return False  # no valid option (Fort only but can't use option 3)
        war_path.execute(state, C.INDIANS, {}, target, option=option)
        return True

    # ------------------------------------------------------------------
    # MARCH  (Command)  -------------------------------------------------
    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0) for sp in state["spaces"].values())

    def _march(self, state: Dict) -> bool:
        """I10: March (Max 3).

        Reference bullets:
        * With: Underground then Active WP, without moving last WP from
          any Village or adding any Rebel Control.
        * If 1+ Villages Available, March to get 3+ WP in 1 additional
          Neutral or Passive space with room for a Village.
        * Then to remove most Rebel Control, first where no Active Support.
        If no March possible, Gather.
        """
        refresh_control(state)
        ctrl = state.get("control", {})
        indian_res = state["resources"].get(C.INDIANS, 0)
        # §3.4.2: "Pay 0 for the first destination where all War Parties
        # are originating from Indian Reserve Provinces" — plan one
        # optimistic destination past the purse; the post-plan budget
        # check (all_reserve credit) trims it away if not free (Session
        # 51: 0-Resource all-Reserve Marches were refused up front).
        max_dests = min(3, indian_res + 1)
        if state.get("_limited"):
            max_dests = min(max_dests, 1)
        if max_dests <= 0:
            return False

        # ---- Snapshot of WP counts for planning (decremented as we go) ----
        wp_snap = {}
        for sid, sp in state["spaces"].items():
            wp_snap[sid] = [sp.get(C.WARPARTY_U, 0), sp.get(C.WARPARTY_A, 0)]

        def _total(sid):
            return wp_snap[sid][0] + wp_snap[sid][1]

        def _can_remove(src):
            """Can we take 1 WP from *src* without violating constraints?"""
            u, a = wp_snap[src]
            if u + a == 0:
                return False
            sp = state["spaces"][src]
            # Don't move last WP from Village
            if sp.get(C.VILLAGE, 0) > 0 and (u + a) <= 1:
                return False
            # §8.7.3: Don't move the last 3 WP from a space where Gather
            # could place a Village (Province with room, no Village already)
            src_meta = _MAP_DATA.get(src, {})
            if (src_meta.get("type") != "City"
                    and sp.get(C.VILLAGE, 0) == 0
                    and self._village_room(state, src)
                    and (u + a) <= 3):
                return False
            # Don't add Rebel Control
            if ctrl.get(src) != "REBELLION":
                reb = sum(sp.get(t, 0) for t in (
                    C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT))
                bri = sum(sp.get(t, 0) for t in (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
                royalist_after = bri + (u + a - 1)
                if reb > royalist_after:
                    return False
            return True

        def _take(src):
            """Take 1 WP from *src* (Underground first). Returns tag."""
            if wp_snap[src][0] > 0:
                wp_snap[src][0] -= 1
                return C.WARPARTY_U
            elif wp_snap[src][1] > 0:
                wp_snap[src][1] -= 1
                return C.WARPARTY_A
            return None

        planned = {}   # (src, dst) → {tag: count}
        destinations = []

        def _add(src, dst, tag):
            key = (src, dst)
            if key not in planned:
                planned[key] = {}
            planned[key][tag] = planned[key].get(tag, 0) + 1

        def _adj_supply(dst):
            """Return [(nbr, can_give)] for adjacent sources of *dst*."""
            result = []
            for nbr in _adjacent(dst):
                if nbr not in wp_snap:
                    continue
                nbr_sp = state["spaces"].get(nbr, {})
                nbr_total = _total(nbr)
                min_keep = 1 if nbr_sp.get(C.VILLAGE, 0) > 0 else 0
                # §8.7.3: Keep at least 3 WP in Gather-eligible spaces
                nbr_meta = _MAP_DATA.get(nbr, {})
                if (nbr_meta.get("type") != "City"
                        and nbr_sp.get(C.VILLAGE, 0) == 0
                        and self._village_room(state, nbr)
                        and min_keep < 3):
                    min_keep = 3
                can_give = max(0, nbr_total - min_keep)
                if can_give > 0:
                    result.append((nbr, can_give))
            return result

        # === Phase 1: If 1+ Villages Available, get 3+ WP in 1 additional
        # Neutral/Passive space with room for Village ===
        avail_villages = state["available"].get(C.VILLAGE, 0)
        if avail_villages > 0 and len(destinations) < max_dests:
            candidates = []
            for sid in state["spaces"]:
                mdata = _MAP_DATA.get(sid, {})
                if mdata.get("type") == "City":
                    continue
                sup = self._support_level(state, sid)
                if sup not in (C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION):
                    continue
                if not self._village_room(state, sid):
                    continue
                if state["spaces"][sid].get(C.VILLAGE, 0) > 0:
                    continue
                current = _total(sid)
                if current >= 3:
                    continue
                needed = 3 - current
                adj = _adj_supply(sid)
                total_supply = sum(n for _, n in adj)
                if total_supply >= needed:
                    candidates.append((needed, state["rng"].random(), sid, adj))
            candidates.sort()
            if candidates:
                needed, _, target, adj = candidates[0]
                destinations.append(target)
                for src, max_give in adj:
                    if needed <= 0:
                        break
                    for _ in range(min(needed, max_give)):
                        if not _can_remove(src):
                            break
                        tag = _take(src)
                        if tag:
                            _add(src, target, tag)
                            wp_snap[target][0] += 1
                            needed -= 1

        # === Phase 2: Remove most Rebel Control, first no Active Support ===
        while len(destinations) < max_dests:
            candidates = []
            for sid in state["spaces"]:
                if sid in destinations:
                    continue
                mdata = _MAP_DATA.get(sid, {})
                if mdata.get("type") == "City":
                    continue
                if ctrl.get(sid) != "REBELLION":
                    continue
                sp = state["spaces"][sid]
                reb = sum(sp.get(t, 0) for t in (
                    C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT))
                bri = sum(sp.get(t, 0) for t in (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
                current_royalist = bri + _total(sid)
                if reb <= current_royalist:
                    continue
                # §1.7: Rebellion Control needs rebels to EXCEED — moving
                # in (reb - royalist) War Parties reaches equality and
                # removes it (Session 51: +1 overshoot wasted a WP that
                # could flip another space).
                wp_needed = reb - current_royalist
                adj = _adj_supply(sid)
                total_supply = sum(n for _, n in adj)
                if total_supply < wp_needed:
                    continue
                sup = self._support_level(state, sid)
                no_active = 0 if sup >= C.ACTIVE_SUPPORT else 1
                rebel_excess = reb - current_royalist
                candidates.append((
                    -no_active, -rebel_excess,
                    state["rng"].random(), sid, wp_needed, adj))
            if not candidates:
                break
            candidates.sort()
            _, _, _, target, wp_needed, adj = candidates[0]
            destinations.append(target)
            for src, max_give in adj:
                if wp_needed <= 0:
                    break
                for _ in range(min(wp_needed, max_give)):
                    if not _can_remove(src):
                        break
                    tag = _take(src)
                    if tag:
                        _add(src, target, tag)
                        wp_snap[target][0] += 1
                        wp_needed -= 1

        if not planned:
            return False

        plan = [
            {"src": src, "dst": dst, "pieces": pieces}
            for (src, dst), pieces in planned.items()
        ]

        # Validate plan against actual state: the planning snapshot may
        # over-count WP_U at spaces that received virtual arrivals.
        # Cap each piece tag to what actually exists, tracking cumulative
        # draws from each source across all plan entries.
        _drawn: Dict[str, Dict[str, int]] = {}
        validated_plan = []
        for entry in plan:
            src = entry["src"]
            sp = state["spaces"].get(src, {})
            drawn_here = _drawn.setdefault(src, {})
            capped = {}
            for tag, count in entry["pieces"].items():
                actual = sp.get(tag, 0) - drawn_here.get(tag, 0)
                take = min(count, max(0, actual))
                if take > 0:
                    capped[tag] = take
                    drawn_here[tag] = drawn_here.get(tag, 0) + take
            if capped:
                validated_plan.append({"src": src, "dst": entry["dst"],
                                       "pieces": capped})

        if not validated_plan:
            return False

        # §3.4.2: pay 1 Resource per destination Province; pay 0 for the
        # first destination where all Marching War Parties originate in
        # Indian Reserves. §8.1: trim to what is affordable (execute the
        # instructions the Faction can pay for), else fall through.
        from lod_ai.map.adjacency import space_type as _sptype
        all_reserve = all(_sptype(e["src"]) == "Reserve"
                          for e in validated_plan)
        budget = state["resources"].get(C.INDIANS, 0) + (1 if all_reserve
                                                         else 0)
        dests: list = []
        for entry in validated_plan:
            if entry["dst"] not in dests:
                dests.append(entry["dst"])
        if len(dests) > budget:
            allowed = set(dests[:budget])
            validated_plan = [e for e in validated_plan
                              if e["dst"] in allowed]
            if not validated_plan:
                return False

        march.execute(state, C.INDIANS,
                      {"all_reserve_origin": all_reserve}, [], [],
                      plan=validated_plan)
        self._follow_leaders_after_move(state)
        return True

    # ------------------------------------------------------------------
    # SCOUT  (Command)  -------------------------------------------------
    def _space_has_wp_and_regulars(self, state: Dict) -> bool:
        """I9: A space has War Party and British Regulars?"""
        return any(
            sp.get(C.REGULAR_BRI, 0)
            and (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0))
            for sp in state["spaces"].values()
        )

    def _can_scout(self, state: Dict) -> bool:
        # Scout costs 1 Indian + 1 British Resource (§3.4.3). §8.1: a
        # Command the Faction (or the paying ally) cannot afford is
        # treated as unexecutable — continue down the flowchart. (The
        # Indian check was shielded by the old blanket 0-Resource PASS
        # gate, which the Indian flowchart does not have.)
        if state["resources"].get(C.BRITISH, 0) < 1:
            return False
        if state["resources"].get(C.INDIANS, 0) < 1:
            return False
        return self._space_has_wp_and_regulars(state)

    def _scout_budget(self, state: Dict, origin: str):
        """Max (n_regs, n_tories) movable out of *origin* per §8.7.4:
        "the most Regulars and Tories possible without losing British
        Control or adding Rebellion Control in the origin space", and
        §3.4.3's escort shape (1+ Regular must move; Tories up to the
        number of Regulars).  Returns None when no legal Scout group
        exists from this origin (Session 36 rules preserved)."""
        sp = state["spaces"][origin]
        if sp.get(C.REGULAR_BRI, 0) == 0:
            return None
        if sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0) == 0:
            return None
        royalist = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                    + sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
                    + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0))
        rebel = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                 + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                 + sp.get(C.FORT_PAT, 0))
        if state.get("control", {}).get(origin) == C.BRITISH:
            budget = royalist - rebel - 1        # keep the Royalist majority
            keep_brit = 0 if sp.get(C.FORT_BRI, 0) else 1  # keep a British piece
        else:
            # Not British-controlled: only avoid ADDING Rebellion Control
            budget = royalist - rebel
            keep_brit = 0
        if budget < 2:                            # 1 WP + 1 Regular minimum
            return None
        brit_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
        max_cubes = min(budget - 1, brit_cubes - keep_brit)
        if max_cubes < 1:
            return None
        n_regs = min(sp.get(C.REGULAR_BRI, 0), max_cubes)
        n_tories = min(sp.get(C.TORY, 0), max_cubes - n_regs)
        # §3.4.3: "Tories up to the number of Regulars may" move
        n_tories = min(n_tories, n_regs)
        return (n_regs, n_tories)

    def _scout(self, state: Dict) -> bool:
        """I12: Scout (Max 1) per §8.7.4.

        The DESTINATION priorities govern the whole selection — "first
        to a space with a Patriot Fort, then to a Village space with
        enemy pieces, then to remove the most Rebellion Control
        possible" — and the origin is whichever legal origin serves the
        best destination, moving the most Regulars and Tories possible.
        (The old code picked the biggest origin FIRST and only then
        scored that origin's neighbours — survey Indian #4 remnant.)
        A destination matching none of the three priorities is not a
        Scout target; with no target the flowchart falls to March.
        Tier 3 is a post-move simulation: the move must actually remove
        Rebellion Control (§1.7 tally with the arriving group counted).
        """
        refresh_control(state)
        ctrl = state.get("control", {})

        best = None  # (key, origin, dst, n_regs, n_tories)
        for origin in state["spaces"]:
            mv = self._scout_budget(state, origin)
            if mv is None:
                continue
            n_regs, n_tories = mv
            incoming = 1 + n_regs + n_tories  # WP + cubes, all Royalist
            for dst in _adjacent(origin):
                if dst not in state.get("spaces", {}):
                    continue
                # §3.4.3: destination must be a Province (not City)
                if _MAP_DATA.get(dst, {}).get("type") == "City":
                    continue
                dsp = state["spaces"][dst]
                has_fort = dsp.get(C.FORT_PAT, 0) > 0
                enemy = (dsp.get(C.REGULAR_PAT, 0) + dsp.get(C.REGULAR_FRE, 0)
                         + dsp.get(C.MILITIA_A, 0) + dsp.get(C.MILITIA_U, 0))
                village_enemy = dsp.get(C.VILLAGE, 0) > 0 and enemy > 0
                removes_ctrl = False
                if ctrl.get(dst) == "REBELLION":
                    roy_d = (dsp.get(C.REGULAR_BRI, 0) + dsp.get(C.TORY, 0)
                             + dsp.get(C.WARPARTY_U, 0) + dsp.get(C.WARPARTY_A, 0)
                             + dsp.get(C.FORT_BRI, 0) + dsp.get(C.VILLAGE, 0))
                    reb_d = (enemy + dsp.get(C.FORT_PAT, 0))
                    removes_ctrl = reb_d <= roy_d + incoming
                if not (has_fort or village_enemy or removes_ctrl):
                    continue
                tier = 0 if has_fort else (1 if village_enemy else 2)
                key = (tier, -(n_regs + n_tories), state["rng"].random())
                if best is None or key < best[0]:
                    best = (key, origin, dst, n_regs, n_tories)

        if best is None:
            return False
        _, origin, target, n_regs, n_tories = best
        n_wp = 1  # Reference: "Move one War Party" — exactly 1 WP

        # I12: Skirmish option — "first a Patriot Fort then most enemy pieces"
        # Calculate post-move enemy cubes (Scout flips all Militia Active)
        dsp = state["spaces"][target]
        enemy_after = (dsp.get(C.REGULAR_PAT, 0) + dsp.get(C.REGULAR_FRE, 0)
                       + dsp.get(C.MILITIA_A, 0) + dsp.get(C.MILITIA_U, 0))
        has_pat_fort = dsp.get(C.FORT_PAT, 0) > 0
        do_skirmish = has_pat_fort or enemy_after > 0
        if has_pat_fort and enemy_after == 0:
            skirmish_opt = 3
        elif enemy_after >= 2:
            skirmish_opt = 2
        else:
            skirmish_opt = 1

        scout.execute(
            state, C.INDIANS, {}, origin, target,
            n_warparties=n_wp, n_regulars=n_regs, n_tories=n_tories,
            skirmish=do_skirmish, skirmish_option=skirmish_opt,
        )
        self._follow_leaders_after_move(state)
        return True

    # ------------------------------------------------------------------
    # TRADE  (Special Activity)  ---------------------------------------
    def _trade(self, state: Dict) -> bool:
        """I11: Trade (Max 1).
        First request Resources from British (per OPS reference, the
        British bot decides whether and how much to offer based on its
        own resource state and a 1D6 roll).  Then Trade in the Village
        space with most Underground War Parties.
        """
        spaces = [
            (sp.get(C.WARPARTY_U, 0), sid)
            for sid, sp in state.get("spaces", {}).items()
            if sp.get(C.WARPARTY_U, 0) > 0 and sp.get(C.VILLAGE, 0) > 0
        ]
        if not spaces:
            return False
        # Sort by most Underground WP (descending)
        spaces.sort(reverse=True)
        target = spaces[0][1]

        # I11: "first request Resources from the British".  Per the
        # British bot OPS reference: if Indian Resources >= British
        # Resources, British offers 0.  Otherwise roll 1D6 and offer
        # half (round up) if the roll < British Resources.  This
        # delegation also fixes the previous inline implementation
        # which was missing the Indian < British gate.
        from lod_ai.bots.british_bot import BritishBot
        transfer = BritishBot.bot_indian_trade(state)
        if transfer > 0:
            push_history(
                state,
                f"Indian Trade: British offer {transfer} Resources"
            )

        try:
            trade.execute(state, C.INDIANS, {}, target, transfer=transfer)
            return True
        except Exception:
            return False

    # ==================================================================
    #  IN-TURN LEADER MOVEMENT  (OPS: Leader Movement during Campaigns)
    # ==================================================================
    def _follow_leaders_after_move(self, state: Dict) -> None:
        """Apply OPS leader-movement rule after any Indian move command.

        OPS reference: "Royalist Leaders accompany the largest group of
        units from their Faction that moves from (or stays in) their
        origin spaces."  Indians have three leaders: Brant, Cornplanter,
        Dragging Canoe.

        Uses the existing ops_leader_movement() which inspects post-move
        board state — call this helper AFTER march/scout/gather/raid
        execute so the WP counts at adjacent spaces reflect what just
        happened.
        """
        follow_indian_leaders_after_move(state)

        # ==================================================================
    #  OPS SUMMARY METHODS  (year-end / operational helpers)
    # ==================================================================
    def ops_supply_priority(self, state: Dict, spaces: List[str]) -> List[str]:
        """OPS: Supply payment priority.
        First where necessary to prevent Rebel Control,
        then where Gather could place a Village.
        """
        refresh_control(state)
        prevent_rebel = []
        gather_village = []
        other = []
        for sid in spaces:
            sp = state["spaces"].get(sid, {})
            reb = sum(sp.get(t, 0) for t in (
                C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT))
            bri = sum(sp.get(t, 0) for t in (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
            ind_wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            royalist = bri + ind_wp
            if reb > 0 and royalist > 0 and reb <= royalist:
                prevent_rebel.append(sid)
            elif self._village_room(state, sid) and sp.get(C.VILLAGE, 0) == 0:
                gather_village.append(sid)
            else:
                other.append(sid)
        return prevent_rebel + gather_village + other

    def ops_patriot_desertion_priority(
        self, state: Dict, candidates: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """OPS: Patriot Desertion removal priority.
        First from Village spaces, then to remove most Rebel Control
        (i.e. where removing 1 Patriot piece changes control from
        Rebellion), then last of type in space, then random.
        """
        refresh_control(state)
        ctrl = state.get("control", {})

        def sort_key(item):
            sid, tag = item
            sp = state["spaces"].get(sid, {})
            has_village = 1 if sp.get(C.VILLAGE, 0) > 0 else 0
            # Would removing 1 rebel piece change control from Rebellion?
            reb = sum(sp.get(t, 0) for t in (
                C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT))
            royalist = sum(sp.get(t, 0) for t in (
                C.REGULAR_BRI, C.TORY, C.FORT_BRI,
                C.WARPARTY_U, C.WARPARTY_A, C.VILLAGE))
            changes_ctrl = (ctrl.get(sid) == "REBELLION"
                            and royalist >= (reb - 1))
            is_last = 1 if sp.get(tag, 0) == 1 else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            # Population tiebreaks WITHIN control-change tier only
            ctrl_pop = -pop if changes_ctrl else 0
            return (-has_village, -int(changes_ctrl), ctrl_pop,
                    -is_last, state["rng"].random())

        return sorted(candidates, key=sort_key)

    def ops_redeploy(self, state: Dict) -> Dict[str, str | None]:
        """OPS: Leader redeployment destinations.
        Brant/Dragging Canoe: space with most WP.
        Cornplanter: Neutral/Passive Province with 2+ WP and room for Village;
        if none, space with most WP.
        """
        result: Dict[str, str | None] = {}

        rng = state["rng"]

        def _most_wp_space():
            # §6.5.2: only spaces with INDIAN pieces (War Parties or
            # Villages) are legal redeploy targets; with none anywhere
            # the Leader goes to Available (None).  Ties seeded per
            # §8.2.  (Session 43: the old scan returned a dict-order
            # space with no Indian pieces when no War Parties were on
            # the map, and broke most-WP ties by dict order.)
            best_key, best_sid = None, None
            for sid, sp in state["spaces"].items():
                n = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
                if n + sp.get(C.VILLAGE, 0) == 0:
                    continue
                key = (-n, rng.random())
                if best_key is None or key < best_key:
                    best_key, best_sid = key, sid
            return best_sid

        for leader in ("LEADER_BRANT", "LEADER_DRAGGING_CANOE"):
            result[leader] = _most_wp_space()

        corn_target = None
        corn_key = None
        for sid, sp in state["spaces"].items():
            mdata = _MAP_DATA.get(sid, {})
            if mdata.get("type") == "City":
                continue
            sup = self._support_level(state, sid)
            if sup not in (C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION):
                continue
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            if wp < 2:
                continue
            if not self._village_room(state, sid):
                continue
            # Ties among qualifying Provinces seeded per §8.2 (was
            # first-seen dict order).
            key = rng.random()
            if corn_key is None or key < corn_key:
                corn_key, corn_target = key, sid
        if corn_target is None:
            corn_target = _most_wp_space()
        result["LEADER_CORNPLANTER"] = corn_target

        return result

    def ops_bs_trigger(self, state: Dict) -> bool:
        """OPS: Brilliant Stroke trigger conditions.
        Use after Treaty of Alliance when Indian Leader is in a space
        with 3+ War Parties, and a player is 1st Eligible or a Rebel
        Faction plays a Brilliant Stroke card other than the Treaty of
        Alliance.
        """
        if not state.get("toa_played"):
            return False
        # §8.1: "no Winter Quarters card is showing"
        current_card = state.get("current_card", {}).get("id")
        if current_card in C.WINTER_QUARTERS_CARDS:
            return False
        # Must have a player 1st eligible or a Rebel Faction plays BS
        human = state.get("human_factions", set())
        eligible = state.get("eligible", [])
        first_eligible = eligible[0] if eligible else None
        player_is_first = first_eligible in human
        bs_map = state.get("bs_played", {})
        rebel_bs_played = bs_map.get(C.PATRIOTS, False) or bs_map.get(C.FRENCH, False)
        if not (player_is_first or rebel_bs_played):
            return False
        # Indian Leader with 3+ War Parties
        for leader in ("LEADER_BRANT", "LEADER_CORNPLANTER", "LEADER_DRAGGING_CANOE"):
            loc = leader_location(state, leader)
            if not loc:
                continue
            sp = state["spaces"].get(loc, {})
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            if wp >= 3:
                return True
        return False

    def ops_leader_movement(self, state: Dict, leader: str) -> str | None:
        """OPS: Leader Movement during Campaigns.
        Leaders accompany the largest group of units from their Faction
        that moves from (or stays in) their origin space.
        """
        loc = leader_location(state, leader)
        if not loc:
            return None
        sp = state["spaces"].get(loc, {})
        origin_wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
        best_dst = None
        best_wp = origin_wp
        for nbr in _adjacent(loc):
            nsp = state["spaces"].get(nbr, {})
            nbr_wp = nsp.get(C.WARPARTY_U, 0) + nsp.get(C.WARPARTY_A, 0)
            if nbr_wp > best_wp:
                best_wp = nbr_wp
                best_dst = nbr
        return best_dst

    # ==================================================================
    #  EVENT‑VS‑COMMAND  (I1 / I2)
    # ==================================================================
    # Cards where the Indian special instruction says
    # "If no Village can be placed, Command & SA instead."
    _VILLAGE_REQUIRED_CARDS = {4, 72, 90}
    # Card 38: "Place War Parties; if not possible, Command & SA instead."
    _WP_REQUIRED_CARDS = {38}
    # Card 83: "Use shaded if Village can be placed, otherwise unshaded."
    _CARD_83 = 83

    def _can_place_village(self, state: Dict) -> bool:
        """Return True if at least one Village could be placed on the map."""
        if state["available"].get(C.VILLAGE, 0) == 0:
            return False
        for sid, sp in state["spaces"].items():
            if not self._village_room(state, sid):
                continue
            if sp.get(C.VILLAGE, 0) > 0:
                continue
            # Need WP to build (Gather places where 3+ WP / 2+ if Cornplanter)
            # but for the "can a Village be placed" check, just check stacking
            return True
        return False

    def _can_place_war_parties(self, state: Dict) -> bool:
        """Return True if War Parties can be placed (any available)."""
        return (state["available"].get(C.WARPARTY_U, 0)
                + state["available"].get(C.WARPARTY_A, 0)) > 0

    def _choose_event_vs_flowchart(self, state: Dict, card: Dict) -> bool:
        """Override base to handle Indian conditional event instructions.
        Cards 4/72/90: play event only if Village can be placed.
        Card 38: play event only if War Parties can be placed.
        (Cards 18/44 route through the generic force_if_eligible_enemy
        directive, which also TARGETS the chosen enemy per the sheet and
        §8.3.5 — the old local check verified eligibility but let the
        handler fall back to a default target.)
        Card 83: shaded if Village placeable, else unshaded.
        """
        cid = card.get("id")

        # Card 83 special: always play, but pick the side
        if cid == self._CARD_83:
            if card.get("sword"):
                return False
            from lod_ai.cards import CARD_HANDLERS
            handler = CARD_HANDLERS.get(cid)
            if not handler:
                return False
            shaded = self._can_place_village(state)
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
            return True

        # Cards with "if condition not met, Command & SA instead"
        if cid in self._VILLAGE_REQUIRED_CARDS:
            if not self._can_place_village(state):
                return False  # fall through to flowchart (Command & SA)
        elif cid in self._WP_REQUIRED_CARDS:
            if not self._can_place_war_parties(state):
                return False

        # Delegate to base class for normal processing
        return super()._choose_event_vs_flowchart(state, card)

    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives from the Indian instruction sheet."""
        if directive == "force_if_80":
            # Card 80: "Choose Patriots and select spaces where a Patriot
            # Fort would be removed. If none, choose Command & SA instead."
            # The non-player TARGET removes its own pieces with Forts LAST
            # (§8.1.2), so the Fort actually goes only where at most ONE
            # Patriot unit stands beside it (2 removals reach the Fort).
            # Session 47: the old check accepted any Fort anywhere and
            # never preset the handler keys, so evt_080 defaulted the
            # target to INDIANS and removed the Indians' own pieces.
            rng = state["rng"]
            qualifying = []
            for sid, sp in state["spaces"].items():
                if sp.get(C.FORT_PAT, 0) == 0:
                    continue
                units = (sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                         + sp.get(C.REGULAR_PAT, 0))
                if units <= 1:
                    qualifying.append((rng.random(), sid))
            if qualifying:
                qualifying.sort()
                state["card80_faction"] = C.PATRIOTS
                state["card80_spaces"] = [sid for _r, sid in qualifying[:2]]
                return True
            return False
        return True  # default: play the event

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """I2: Check unshaded Event conditions for Indian bot via CARD_EFFECTS."""
        effects = CARD_EFFECTS.get(card.get("id"))
        if effects is None:
            return False  # unknown card → fall through to Command
        eff = effects["unshaded"]

        support, opposition = self._support_opposition_totals(state)

        # 1. Opposition > Support and Event shifts in Royalist favor
        #    "(including by reducing FNI, but not by free Battles)" —
        #    needs a Blockade on a Support City to un-zero (§1.9;
        #    Session 49, mirroring the B2 fix).
        if opposition > support:
            if eff["shifts_support_royalist"]:
                return True
            if eff.get("removes_blockade"):
                blockaded = (state.get("markers", {})
                             .get(C.BLOCKADE, {}).get("on_map", set()))
                if any(state.get("support", {}).get(sid, 0) > 0
                       for sid in blockaded):
                    return True
        # 2. Event places Village or grants free Gather
        if eff["places_village"]:
            if state.get("available", {}).get(C.VILLAGE, 0) > 0:
                return True
        if eff["grants_free_gather"]:
            return True
        # 3. Event removes a Patriot Fort
        if eff["removes_patriot_fort"]:
            if any(sp.get(C.FORT_PAT, 0) > 0
                   for sp in state.get("spaces", {}).values()):
                return True
        # 4. Event is effective, 4+ Villages on map, D6 >= 5
        if eff["is_effective"]:
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
