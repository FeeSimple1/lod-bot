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
            tgt_sp = state["spaces"][tgt]
            wp_in_tgt = tgt_sp.get(C.WARPARTY_U, 0) + tgt_sp.get(C.WARPARTY_A, 0)
            rebels_in_tgt = (tgt_sp.get(C.MILITIA_A, 0) + tgt_sp.get(C.MILITIA_U, 0)
                             + tgt_sp.get(C.REGULAR_PAT, 0) + tgt_sp.get(C.REGULAR_FRE, 0))
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
                selected.append(tgt)

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
        I6 test: Gather would place 2+ Villages, OR 1D6 < Available War Parties?
        "Would place" means: 2+ Available Villages AND 2+ eligible spaces.
        """
        avail_villages = state["available"].get(C.VILLAGE, 0)
        if avail_villages >= 2:
            corn_loc = leader_location(state, "LEADER_CORNPLANTER")
            eligible_count = 0
            for sid, sp in state["spaces"].items():
                if not self._village_room(state, sid):
                    continue
                if sp.get(C.VILLAGE, 0) > 0:
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

        selected: List[str] = []
        build_village: set = set()
        bulk_place: Dict[str, int] = {}

        # --- Bullet 1: Place Villages where room and 3+ WP (2+ if Cornplanter) ---
        village_cands = []
        for sid, sp in state["spaces"].items():
            if not self._village_room(state, sid):
                continue
            if sp.get(C.VILLAGE, 0) > 0:
                continue  # already has a Village; build_village replaces 2 WP
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
            if len(selected) >= 4:
                break
            selected.append(sid)
            build_village.add(sid)
            villages_placed += 1

        # --- Bullet 2: Place War Parties at Villages ---
        if avail_wp > 0:
            wp_cands = []
            for sid, sp in state["spaces"].items():
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
                if len(selected) >= 4:
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
            placed_count = 0
            for _, _, sid in room_cands:
                if placed_count >= 2:
                    break
                if len(selected) >= 4:
                    break
                if avail_wp <= 0:
                    break
                if sid not in selected:
                    selected.append(sid)
                bulk_place[sid] = bulk_place.get(sid, 0) + 1
                avail_wp -= 1
                placed_count += 1

        # --- Bullet 4: If no more WP Available, in 1 Village space move in
        #     all adjacent Active WP without adding Rebel Control, flip UG ---
        final_avail_wp = state["available"].get(C.WARPARTY_U, 0) + state["available"].get(C.WARPARTY_A, 0)
        # Subtract what we plan to place
        final_avail_wp -= sum(bulk_place.values())
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
                moves = []
                total = 0
                for nbr in _adjacent(sid):
                    nsp = state["spaces"].get(nbr, {})
                    active_wp = nsp.get(C.WARPARTY_A, 0)
                    if active_wp == 0:
                        continue
                    # "without adding any Rebel Control" — skip if moving
                    # WP out would cause Rebellion to gain control in nbr
                    # (simplified: skip if nbr would lose all Indian pieces)
                    remaining = (nsp.get(C.WARPARTY_U, 0) + active_wp - active_wp
                                 + nsp.get(C.VILLAGE, 0))
                    if remaining == 0 and ctrl.get(nbr) != "REBELLION":
                        # Moving all WP_A out might flip control
                        rebel_pieces = (nsp.get(C.MILITIA_A, 0) + nsp.get(C.MILITIA_U, 0)
                                        + nsp.get(C.REGULAR_PAT, 0) + nsp.get(C.REGULAR_FRE, 0)
                                        + nsp.get(C.FORT_PAT, 0))
                        if rebel_pieces > 0:
                            continue  # would add Rebel Control
                    moves.append((nbr, active_wp))
                    total += active_wp
                if total > best_total:
                    best_total = total
                    best_dst = sid
                    best_moves = moves
            if best_dst and best_moves:
                if best_dst not in selected:
                    if len(selected) < 4:
                        selected.append(best_dst)
                    else:
                        best_dst = None
                if best_dst:
                    for src, n in best_moves:
                        move_plan_list.append((src, best_dst, n))

        if not selected:
            return False

        # Remove spaces from build_village that aren't in selected
        build_village = build_village & set(selected)
        # Remove bulk_place entries for spaces not selected
        bulk_place = {s: n for s, n in bulk_place.items() if s in selected}

        gather.execute(
            state, C.INDIANS, {}, selected,
            build_village=build_village if build_village else None,
            bulk_place=bulk_place if bulk_place else None,
            move_plan=move_plan_list if move_plan_list else None,
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
        else:
            option = 1
        return war_path.execute(state, C.INDIANS, {}, target, option=option)

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
            key = (pop, state["rng"].random())
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
        """I9: A space has War Party and British Regulars?"""
        return any(
            sp.get(C.REGULAR_BRI, 0)
            and (sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0))
            for sp in state["spaces"].values()
        )

    def _can_scout(self, state: Dict) -> bool:
        return self._space_has_wp_and_regulars(state)

    def _scout(self, state: Dict) -> bool:
        """I12: Scout (Max 1).
        Move 1 War Party + most Regulars+Tories possible without changing
        Control in origin space.
        Destination priority: first to a Patriot Fort, then to a Village
        with enemy, then to remove most Rebel Control.
        Skirmish to remove first a Patriot Fort then most enemy pieces.
        """
        refresh_control(state)
        ctrl = state.get("control", {})

        # Origin: space with WP (any type) + British Regulars
        choices = []
        for sid, sp in state["spaces"].items():
            n_regs = sp.get(C.REGULAR_BRI, 0)
            if n_regs == 0:
                continue
            total_wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            if total_wp == 0:
                continue
            # Prefer origin with most Regulars+Tories (to move most pieces)
            n_tories = sp.get(C.TORY, 0)
            choices.append((n_regs + n_tories, total_wp, sid))
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
            rebel_ctrl = 1 if ctrl.get(dst) == "REBELLION" else 0
            key = (has_pat_fort, village_enemy, rebel_ctrl, state["rng"].random())
            dest_scores.append((key, dst))
        if not dest_scores:
            return False
        _, target = max(dest_scores)

        sp = state["spaces"][origin]
        # Reference: "Move 1 War Party" — exactly 1 WP
        n_wp = 1

        # "most Regulars+Tories possible without changing Control in origin"
        n_regs = sp.get(C.REGULAR_BRI, 0)
        n_tories = sp.get(C.TORY, 0)

        # Check control preservation: compute how many pieces we can remove
        # without flipping control.  We need at least 1 Regular for Scout.
        if n_regs == 0:
            return False

        # Simplified control check: count all Royalist pieces in origin.
        # If removing pieces would let Rebellion gain control, reduce count.
        royalist = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                    + sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
                    + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0))
        rebel = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                 + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                 + sp.get(C.FORT_PAT, 0))
        moveable = royalist - rebel - 1  # keep 1 more than rebels
        if moveable < 2:  # need at least 1 WP + 1 Regular
            # Try moving just 1 WP + 1 Regular (minimum)
            n_regs = 1
            n_tories = 0
        else:
            # Cap to what we can move: 1 WP + regs + tories ≤ moveable
            total_desired = n_wp + n_regs + n_tories
            if total_desired > moveable:
                # Reduce tories first, then regulars
                excess = total_desired - moveable
                tory_cut = min(excess, n_tories)
                n_tories -= tory_cut
                excess -= tory_cut
                if excess > 0:
                    n_regs = max(1, n_regs - excess)

        scout.execute(
            state, C.INDIANS, {}, origin, target,
            n_warparties=n_wp, n_regulars=n_regs, n_tories=n_tories,
            skirmish=True,
        )
        return True

    # ------------------------------------------------------------------
    # TRADE  (Special Activity)  ---------------------------------------
    def _trade(self, state: Dict) -> bool:
        """I11: Trade (Max 1).
        First request Resources from British.  If no Resources given,
        Trade in the Village space with most Underground War Parties.
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

        # I11: "first request Resources from the British"
        transfer = 0
        brit_res = state.get("resources", {}).get(C.BRITISH, 0)
        if brit_res > 0:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Indian Trade D6", roll))
            if roll < brit_res:
                transfer = -(-roll // 2)  # ceil(roll / 2)
                push_history(state, f"Indian Trade: British offer {transfer} (rolled {roll})")

        try:
            trade.execute(state, C.INDIANS, {}, target, transfer=transfer)
            return True
        except Exception:
            return False

    # ==================================================================
    #  EVENT‑VS‑COMMAND  (I1 / I2)
    # ==================================================================
    # Cards where the Indian special instruction says
    # "If no Village can be placed, Command & SA instead."
    _VILLAGE_REQUIRED_CARDS = {4, 72, 90}
    # Cards: "Target an Eligible enemy Faction. If none, Command & SA."
    _ELIGIBLE_ENEMY_CARDS = {18, 44}
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

    def _has_eligible_enemy(self, state: Dict) -> bool:
        """Return True if any enemy faction is currently Eligible."""
        elig_map = state.get("eligible", {})
        for fac in (C.PATRIOTS, C.FRENCH):
            if elig_map.get(fac, True):  # default True if not tracked
                return True
        return False

    def _can_place_war_parties(self, state: Dict) -> bool:
        """Return True if War Parties can be placed (any available)."""
        return (state["available"].get(C.WARPARTY_U, 0)
                + state["available"].get(C.WARPARTY_A, 0)) > 0

    def _choose_event_vs_flowchart(self, state: Dict, card: Dict) -> bool:
        """Override base to handle Indian conditional event instructions.
        Cards 4/72/90: play event only if Village can be placed.
        Cards 18/44: play event only if eligible enemy exists.
        Card 38: play event only if War Parties can be placed.
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
        elif cid in self._ELIGIBLE_ENEMY_CARDS:
            if not self._has_eligible_enemy(state):
                return False
        elif cid in self._WP_REQUIRED_CARDS:
            if not self._can_place_war_parties(state):
                return False

        # Delegate to base class for normal processing
        return super()._choose_event_vs_flowchart(state, card)

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
