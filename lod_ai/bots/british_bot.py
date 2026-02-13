# lod_ai/bots/british_bot.py
"""
Non‑player British bot – **full implementation**

Implements rules §8.4 and the “British bot flow‑chart & reference”.  The code
sticks to the published priorities but relies on the command / SA modules
(`garrison`, `muster`, `march`, `battle`, `naval_pressure`, `skirmish`,
`common_cause`) to perform the low‑level piece movements exactly as the
rulebook specifies.  Where those helpers need guidance, a detailed plan is
handed to them.

Author: gizmo‑assistant – 2025‑06‑14
"""

from __future__ import annotations
from typing import Dict, List, Tuple
from pathlib import Path
import json
import random

from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.commands import garrison, muster, march, battle
from lod_ai.special_activities import naval_pressure, skirmish, common_cause
from lod_ai.util.history import push_history

# ---------------------------------------------------------------------------
#  Shared geography helpers
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
CITIES: List[str] = [n for n, d in _MAP_DATA.items() if d.get("type") == "City"]
WEST_INDIES = C.WEST_INDIES_ID

def _adjacent(space: str) -> List[str]:
    """Return list of adjacent space IDs (split multi‑edge tokens)."""
    adj = []
    for token in _MAP_DATA[space]["adj"]:
        adj.extend(token.split("|"))
    return adj


class BritishBot(BaseBot):
    faction = C.BRITISH

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    def _control(self, state: Dict, sid: str):
        return state.get("control", {}).get(sid)

    # =======================================================================
    #  MAIN FLOW‑CHART DRIVER  (§8.4 nodes B4 → B13)
    # =======================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # --- B3  : Resources > 0? -----------------------------------------
        if state.get("resources", {}).get(C.BRITISH, 0) <= 0:
            push_history(state, "BRITISH PASS (no Resources)")
            return

        # --- B4  : GARRISON decision --------------------------------------
        if self._can_garrison(state) and self._garrison(state):
            return

        # --- B6–B8 : MUSTER decision --------------------------------------
        if self._can_muster(state) and self._muster(state):
            return

        # --- B9 / B12 : BATTLE decision -----------------------------------
        if self._can_battle(state) and self._battle(state):
            return

        # --- B10 : MARCH decision -----------------------------------------
        if self._can_march(state) and self._march(state):
            return

        # --- Otherwise PASS ------------------------------------------------
        push_history(state, "BRITISH PASS")

    # =======================================================================
    #  SPECIAL‑ACTIVITY HELPER LOOPS  (B11 ⇄ B7)
    # =======================================================================
    def _skirmish_then_naval(self, state: Dict) -> None:
        """SA loop entry when the flow‑chart arrow points to B11 (Skirmish)."""
        if self._try_skirmish(state):
            return
        self._try_naval_pressure(state)

    def _naval_then_skirmish(self, state: Dict) -> None:
        """SA loop entry when the flow‑chart arrow points to B7 (Naval)."""
        if self._try_naval_pressure(state):
            return
        self._try_skirmish(state)

    def _try_skirmish(self, state: Dict) -> bool:
        """
        Execute Skirmish (B11) following the priority list:
            • In 1 space not selected for Battle or Muster, nor as
              Garrison destination (tracked via _turn_affected_spaces).
            • West Indies first
            • spaces with exactly 1 British Regular
            • otherwise as many casualties as possible
        Falls back to Naval Pressure if nothing happens.
        """
        excluded = state.get("_turn_affected_spaces", set())

        # 1) West Indies check
        if WEST_INDIES not in excluded and state["spaces"].get(WEST_INDIES, {}).get(C.REGULAR_BRI, 0):
            try:
                skirmish.execute(state, C.BRITISH, {}, WEST_INDIES, option=1)
                return True
            except Exception:
                pass

        # 2) Exactly‑one‑Regular spaces then others
        targets = []
        for sid, sp in state["spaces"].items():
            if sid in excluded or sid == WEST_INDIES:
                continue
            reg = sp.get(C.REGULAR_BRI, 0)
            enemy = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.WARPARTY_A, 0)
                + sp.get(C.WARPARTY_U, 0)
            )
            if enemy == 0:
                continue
            priority = 0
            if reg == 1:
                priority += 100  # bubble up "exactly one Regular" rule
            priority += enemy
            targets.append((-priority, sid))  # minus = larger first

        targets.sort()
        for _, sid in targets:
            try:
                skirmish.execute(state, C.BRITISH, {}, sid, option=1)
                return True
            except Exception:
                continue

        # 3) If Skirmish impossible, attempt Naval Pressure (loop rule)
        return False  # caller may chain

    def _try_naval_pressure(self, state: Dict) -> bool:
        """
        Execute Naval Pressure (B7).  Priorities:
            • Remove a Blockade if Gage/Clinton & FNI > 0
            • Else add +1D3 Resources if FNI == 0
        Falls back to Skirmish if nothing happens.
        """
        try:
            naval_pressure.execute(state, C.BRITISH, {})
            return True
        except Exception:
            return False  # caller may chain

    # =======================================================================
    #  NODE B5  :  GARRISON Command
    # =======================================================================
    def _garrison(self, state: Dict) -> bool:
        # Flow‑chart: "First execute a Special Activity."
        self._skirmish_then_naval(state)   # B5 edge "With: B11" → Skirmish first

        refresh_control(state)

        # ----- step 1: choose TARGET City needing British Control ----------
        target = self._select_garrison_city(state)
        if not target:
            return False  # nothing to do → flow‑chart directs to MUSTER

        # ----- step 2: build move-map respecting “leave 2 more pieces” -----
        move_map: Dict[str, Dict[str, int]] = {}
        moved_cubes = 0
        for sid, sp in state["spaces"].items():
            if sid == target or self._control(state, sid) != C.BRITISH:
                continue
            brit_units = (
                sp.get(C.REGULAR_BRI, 0)
                + sp.get(C.TORY, 0)
            )
            rebel_units = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            # must leave 2 more Crown than Rebel pieces
            must_leave = max(0, rebel_units) + 2
            movable = max(0, sp.get(C.REGULAR_BRI, 0) - must_leave)
            if movable <= 0:
                continue
            qty = 1 if moved_cubes < 3 else 0  # seldom need more than 3 cubes
            if qty:
                move_map[sid] = {target: qty}
                moved_cubes += qty
            if moved_cubes >= 3:
                break

        if moved_cubes == 0:
            # “If no cubes have moved yet, instead Muster.”
            return self._muster(state)

        # Displacement target (Province with most Opposition then least Support)
        displace_city, displace_target = self._select_displacement(state, target)

        garrison.execute(
            state,
            C.BRITISH,
            {},
            move_map,
            displace_city=displace_city,
            displace_target=displace_target,
        )
        return True

    # -------------------------------------------------------------------
    def _select_garrison_city(self, state: Dict) -> str | None:
        """Apply priority bullets to pick the City to relieve.

        Reference: "first where most Rebels without Patriot Fort, then
        New York City, first where Underground Militia, then random."
        """
        candidates: List[Tuple[tuple, str]] = []
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            if self._control(state, name) == C.BRITISH or sp.get(C.FORT_PAT, 0):
                continue
            rebels = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            has_underground = 1 if sp.get(C.MILITIA_U, 0) > 0 else 0
            is_nyc = 1 if name == "New_York_City" else 0
            # Sort key: most rebels, NYC tiebreak, underground militia tiebreak
            key = (-rebels, -is_nyc, -has_underground)
            candidates.append((key, name))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    def _select_displacement(self, state: Dict, target_city: str) -> Tuple[str | None, str | None]:
        """
        Choose where displaced Rebels will go after Garrison:
        – Province with most Opposition, then least Support, then lowest Pop.
        """
        best = None
        best_key = (-1, 99, 99)  # higher Opposition, lower Support, lower Pop
        for sid, sp in state["spaces"].items():
            if _MAP_DATA[sid]["type"] != "Province":
                continue
            support_level = self._support_level(state, sid)
            opp = max(0, -support_level)
            sup = max(0, support_level)
            pop = _MAP_DATA[sid].get("population", 0)
            key = (opp, -sup, -pop)
            if key > best_key:
                best_key = key
                best = sid
        return (target_city, best) if best else (None, None)

    # =======================================================================
    #  NODE B8  :  MUSTER Command
    # =======================================================================
    def _muster(self, state: Dict) -> bool:
        """Full bullet-list implementation for node B8 (Max 4 spaces).

        Reference priorities:
        1. Place Regulars: first in Neutral or Passive, within that first
           to add British Control then where Tories are the only British
           units then random; within each first in highest Pop.
        2. Place Tories: first where Regulars are the only British cubes
           (within that first where Regulars were just placed), then to
           change most Control, then in Colonies with < 5 British cubes
           and no British Fort.
        3. In 1 space, first one already selected above:
           RL if Opposition > Support + 1D3 OR no Forts Available;
           else Fort in Colony with 5+ cubes and no Fort.
        """
        avail_regs = state["available"].get(C.REGULAR_BRI, 0)
        avail_tories = state["available"].get(C.TORY, 0)
        if avail_regs == 0 and avail_tories == 0:
            return False

        refresh_control(state)

        # ----- step 1: choose space for Regular placement (sorted) ---------
        # Candidates: Neutral or Passive support levels (0, +1, -1)
        reg_candidates: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES:
                continue
            stype = _MAP_DATA.get(sid, {}).get("type", "")
            if stype == "Province":
                continue
            sup = self._support_level(state, sid)
            is_neutral_or_passive = sup in (
                C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION
            )
            if not is_neutral_or_passive:
                continue
            # Priority: add British Control (not already controlled)
            adds_control = 0 if self._control(state, sid) != C.BRITISH else 1
            # Then: Tories are the only British units
            tories_only = 0 if (sp.get(C.TORY, 0) > 0
                                and sp.get(C.REGULAR_BRI, 0) == 0
                                and sp.get(C.FORT_BRI, 0) == 0) else 1
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            # Sort: adds_control ASC (0=yes first), tories_only ASC, -pop, random
            key = (adds_control, tories_only, -pop, random.random())
            reg_candidates.append((key, sid))

        reg_candidates.sort()
        regular_destinations: List[str] = []
        if avail_regs > 0 and reg_candidates:
            regular_destinations.append(reg_candidates[0][1])

        # ----- step 2: Tory placement priorities ---------------------------
        selected_spaces = set(regular_destinations)
        tory_plan: Dict[str, int] = {}

        # Priority 1: where Regulars are the only British cubes
        # (within that, first where Regulars were just placed)
        tory_p1: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES:
                continue
            if sp.get(C.REGULAR_BRI, 0) > 0 and sp.get(C.TORY, 0) == 0 and sp.get(C.FORT_BRI, 0) == 0:
                just_placed = 0 if sid in selected_spaces else 1
                tory_p1.append(((just_placed,), sid))
        tory_p1.sort()
        for _, sid in tory_p1:
            if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                break
            tory_plan[sid] = 1
            avail_tories -= 1

        # Priority 2: change most Control
        if avail_tories > 0:
            tory_p2: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in tory_plan or sid == WEST_INDIES:
                    continue
                # "change most Control" = spaces closest to flipping control
                brit_pieces = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) + sp.get(C.FORT_BRI, 0)
                rebel_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                                + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                                + sp.get(C.FORT_PAT, 0))
                # Adding a Tory helps most where the gap is smallest
                gap = rebel_pieces - brit_pieces
                tory_p2.append((-gap, sid))
            tory_p2.sort()
            for _, sid in tory_p2:
                if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                    break
                if sid in tory_plan:
                    continue
                tory_plan[sid] = 1
                avail_tories -= 1

        # Priority 3: Colonies with < 5 British cubes and no British Fort
        if avail_tories > 0:
            for sid, sp in state["spaces"].items():
                if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                    break
                if sid in tory_plan or sid == WEST_INDIES:
                    continue
                if (_MAP_DATA.get(sid, {}).get("type") == "Colony"
                        and sp.get(C.FORT_BRI, 0) == 0
                        and (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)) < 5):
                    tory_plan[sid] = 1
                    avail_tories -= 1

        # ----- step 3: Reward Loyalty OR build Fort in one space -----------
        # "in 1 space, first one already selected above"
        all_selected = list(selected_spaces | set(tory_plan.keys()))
        reward_levels = 0
        build_fort: set[str] | None = None
        chosen_rl_space = None
        die = state["rng"].randint(1, 3)
        state.setdefault("rng_log", []).append(("1D3", die))

        support_map = state.get("support", {})
        total_support = sum(max(0, lvl) for lvl in support_map.values())
        total_opp = sum(max(0, -lvl) for lvl in support_map.values())
        if total_opp > total_support + die or state["available"].get(C.FORT_BRI, 0) == 0:
            # Reward Loyalty
            raid_on_map = state.get("markers", {}).get(C.RAID, {}).get("on_map", set())
            prop_on_map = state.get("markers", {}).get(C.PROPAGANDA, {}).get("on_map", set())

            def _rl_key(n):
                markers = (1 if n in raid_on_map else 0) + (1 if n in prop_on_map else 0)
                sup = self._support_level(state, n)
                shift = -sup  # more opposition → larger shift toward support
                # Prefer spaces already selected ("first one already selected above")
                already = 0 if n in all_selected else 1
                return (-already, -markers, shift)

            # RL requires British Control + 1+ Regular + 1+ Tory (§3.2.1)
            # and room to shift (not at Active Support)
            rl_candidates = [
                sid for sid, sp in state["spaces"].items()
                if self._support_level(state, sid) < C.ACTIVE_SUPPORT
                and self._control(state, sid) == C.BRITISH
                and sp.get(C.REGULAR_BRI, 0) >= 1
                and sp.get(C.TORY, 0) >= 1
            ]
            # "Do not RL where only Raid/Propaganda markers would be removed"
            rl_candidates = [
                sid for sid in rl_candidates
                if not (self._support_level(state, sid) == C.PASSIVE_SUPPORT
                        and sid not in raid_on_map and sid not in prop_on_map)
            ]
            if rl_candidates:
                chosen_rl_space = max(rl_candidates, key=_rl_key)
                reward_levels = 1

        if chosen_rl_space is None and state["available"].get(C.FORT_BRI, 0):
            # Place Fort in Colony with 5+ British cubes and no British Fort
            fort_targets = [
                sid
                for sid, sp in state["spaces"].items()
                if _MAP_DATA.get(sid, {}).get("type") == "Colony"
                and sp.get(C.FORT_BRI, 0) == 0
                and (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)) >= 5
            ]
            # Prefer already selected spaces
            fort_targets.sort(key=lambda n: (0 if n in all_selected else 1))
            if fort_targets:
                build_fort = {fort_targets[0]}

        # ----- EXECUTE MUSTER ---------------------------------------------
        did_something = muster.execute(
            state,
            C.BRITISH,
            {},
            list(set(regular_destinations + list(tory_plan.keys()))),
            regular_plan={"space": regular_destinations[0], "n": min(4, avail_regs)}
            if avail_regs and regular_destinations
            else None,
            tory_plan=tory_plan,
            reward_levels=reward_levels,
            build_fort=bool(build_fort),
        )

        if not did_something:
            # "If not possible, March unless already tried"
            return self._march(state)

        # Execute Special-Activity: B11 arrow (Skirmish first)
        self._skirmish_then_naval(state)
        return True

    # =======================================================================
    #  NODE B10 :  MARCH Command
    # =======================================================================
    def _march(self, state: Dict) -> bool:
        """Implements all four bullet blocks of node B10."""
        refresh_control(state)

        # Collect origin spaces with spare Regulars
        origins: List[str] = []
        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) > 0:
                origins.append(sid)

        if not origins:
            return False

        # Helper: ensure we lose no British Control in origin
        def can_leave(sid: str) -> bool:
            sp = state["spaces"][sid]
            if self._control(state, sid) != C.BRITISH:
                return False
            cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.WARPARTY_A, 0)
                + sp.get(C.WARPARTY_U, 0)
            )
            return cubes - 1 >= rebel  # leave at least parity

        # Primary goal: add British Control to up to two Cities / Colonies
        target_spaces: List[str] = []
        for sid in origins:
            if len(target_spaces) >= 2:
                break
            for dst in _adjacent(sid):
                if dst not in state.get("spaces", {}) or dst in target_spaces:
                    continue
                if state.get("control", {}).get(dst) == "REBELLION":
                    target_spaces.append(dst)
        # Fallback – Pop 1+ spaces not at Active Support
        if not target_spaces:
            for sid in origins:
                for dst in _adjacent(sid):
                    if dst not in state.get("spaces", {}) or dst in target_spaces:
                        continue
                    if self._support_level(state, dst) != C.ACTIVE_SUPPORT and _MAP_DATA[dst].get("population", 0) >= 1:
                        target_spaces.append(dst)
                        if len(target_spaces) >= 2:
                            break

        if not target_spaces:
            return False  # nothing worth marching

        # Build move plan (largest origin groups first)
        origins.sort(
            key=lambda n: -(state["spaces"][n].get(C.REGULAR_BRI, 0) + state["spaces"][n].get(C.TORY, 0))
        )
        move_plan: List[Dict] = []
        for dst in target_spaces:
            best_origin = next((o for o in origins if dst in _adjacent(o) and can_leave(o)), None)
            if not best_origin:
                continue
            qty = 2 if state["spaces"][best_origin].get(C.REGULAR_BRI, 0) >= 3 else 1
            move_plan.append({"src": best_origin, "dst": dst, "pieces": {C.REGULAR_BRI: qty}})

        if not move_plan:
            return False

        # Execute the March
        march.execute(
            state,
            C.BRITISH,
            {},
            list({p["src"] for p in move_plan}),
            list({p["dst"] for p in move_plan}),
            plan=move_plan,
            bring_escorts=False,
            limited=False,
        )

        # Common Cause check (B13)
        if not self._try_common_cause(state):
            self._skirmish_then_naval(state)
        return True

    # =======================================================================
    #  NODE B12 :  BATTLE Command
    # =======================================================================
    def _battle(self, state: Dict) -> bool:
        """B12: Select spaces where Royalist Force Level + modifiers > Rebel Force Level + modifiers.

        Force Level per §3.6.2-3.6.3:
          British Attack: Regulars + min(Tories, Regulars) + floor(Active_WP/2)
          Rebel Defense: Continentals + French_Regulars + floor(total_Militia/2) + Forts
        Leader modifiers affect dice rolls (§3.6.5), not force level.
        """
        refresh_control(state)
        targets: List[str] = []

        for sid, sp in state["spaces"].items():
            # Rebel Defense Force Level (assume defender activates Underground)
            rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            total_militia = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            rebel_force = rebel_cubes + (total_militia // 2) + sp.get(C.FORT_PAT, 0)

            # Royalist Attack Force Level
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = min(sp.get(C.TORY, 0), regs)  # Tories capped at Regulars
            active_wp = sp.get(C.WARPARTY_A, 0)
            royal_force = regs + tories + (active_wp // 2)

            if royal_force > rebel_force and (rebel_cubes + total_militia) > 0:
                # "first where most British"
                british_count = regs + sp.get(C.TORY, 0)
                targets.append((-british_count, sid))

        if not targets:
            return False

        targets.sort()
        chosen = [sid for _, sid in targets]

        # Common Cause before the battles
        used_cc = self._try_common_cause(state)

        # If no Common Cause, execute Skirmish/Naval loop first (B11/B7)
        if not used_cc:
            self._skirmish_then_naval(state)

        battle.execute(state, C.BRITISH, {}, chosen)
        return True

    # -------------------------------------------------------------------
    def _try_common_cause(self, state: Dict) -> bool:
        """Return True if Common Cause executed successfully."""
        try:
            common_cause.execute(state, C.BRITISH, {})
            return True
        except Exception:
            return False

    # =======================================================================
    #  PRE‑CONDITION CHECKS  (mirrors italics at start of §8.4.x)
    # =======================================================================
    def _can_garrison(self, state: Dict) -> bool:
        refresh_control(state)
        regs_on_map = sum(sp.get(C.REGULAR_BRI, 0) for sp in state["spaces"].values())
        if regs_on_map < 10:
            return False
        for name in CITIES:
            sp = state["spaces"][name]
            if self._control(state, name) == "REBELLION" and sp.get(C.FORT_PAT, 0) == 0:
                return True
        return False

    def _can_muster(self, state: Dict) -> bool:
        die = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("1D6", die))
        return state["available"].get(C.REGULAR_BRI, 0) > die

    def _can_battle(self, state: Dict) -> bool:
        """B9: '2+ Active Rebels in a space outnumbered by British Regulars + Leader'
        Active Rebels = Continentals + Active Militia + French Regulars (no Underground).
        """
        refresh_control(state)
        for sid, sp in state["spaces"].items():
            active_rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.REGULAR_FRE, 0)
            )
            if active_rebel < 2:
                continue
            royal = sp.get(C.REGULAR_BRI, 0)
            leader = state.get("leaders", {}).get(sid, "")
            has_british_leader = leader in {
                "LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"
            }
            if royal + (1 if has_british_leader else 0) > active_rebel:
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.REGULAR_BRI, 0) > 0 for sp in state["spaces"].values())
