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
    #  EVENT‑VS‑COMMAND BULLETS (B2)
    # =======================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """B2: Check unshaded Event conditions for British bot."""
        text = card.get("unshaded_event", "") or ""
        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # • Opposition > Support, and Event shifts Support/Opposition in
        #   Royalist favor (including by removing a Blockade)?
        if opp > sup and any(k in text for k in ("Support", "Opposition", "Blockade")):
            return True
        # • Event places British pieces from Unavailable?
        if any(k in text for k in ("Unavailable",)):
            if any(k in text for k in ("Regular", "Tory", "British")):
                return True
        # • Event places Tories in Active Opposition with none, a British Fort
        #   in a Colony with none, or British Regulars in a City or Colony?
        if "Tory" in text or "Tories" in text or "Fort" in text or "Regular" in text:
            return True
        # • Event inflicts Rebel Casualties (including free Skirmish or Battle)?
        if any(k in text.lower() for k in ("casualt", "skirmish", "battle")):
            if any(k in text for k in ("Rebel", "Patriot", "French", "Indian", "Militia", "Continental")):
                return True
        # • British Control 5+ Cities, the Event is effective, and a D6 rolls 5+?
        controlled_cities = sum(
            1 for name in CITIES
            if self._control(state, name) == C.BRITISH
        )
        if controlled_cities >= 5:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Event D6", roll))
            if roll >= 5:
                return True
        return False

    # =======================================================================
    #  MAIN FLOW‑CHART DRIVER  (§8.4 nodes B4 → B13)
    # =======================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # --- B3  : Resources > 0? -----------------------------------------
        if state.get("resources", {}).get(C.BRITISH, 0) <= 0:
            push_history(state, "BRITISH PASS (no Resources)")
            return

        # Track which commands have been tried to implement mutual fallbacks
        tried_muster = False
        tried_march = False

        # --- B4  : GARRISON decision --------------------------------------
        if self._can_garrison(state) and self._garrison(state):
            return

        # --- B6–B8 : MUSTER decision --------------------------------------
        if self._can_muster(state):
            tried_muster = True
            if self._muster(state, tried_march=tried_march):
                return
            # B8 "If none" → B10 (March)
            tried_march = True
            if self._march(state, tried_muster=tried_muster):
                return

        # --- B9 / B12 : BATTLE decision -----------------------------------
        if self._can_battle(state):
            if self._battle(state):
                return
            # B12 "If none" → B10 (March)
            if not tried_march:
                tried_march = True
                if self._march(state, tried_muster=tried_muster):
                    return

        # --- B10 : MARCH decision -----------------------------------------
        if not tried_march:
            tried_march = True
            if self._march(state, tried_muster=tried_muster):
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
            • In 1 space NOT selected for Battle or Muster, NOR as
              Garrison destination (tracked via _turn_affected_spaces).
            • First in West Indies, then where exactly 1 British Regular,
              then per below.
            • Remove as many Rebel cubes as possible, first whichever type
              is least in the space, removing 1 British Regular if necessary.
            • Remove 1 Rebel piece, first last Rebel in space, within that
              first in a City.
            • If Clinton in the space: Remove 1 additional Militia if possible.
        Falls back to Naval Pressure if nothing happens.
        """
        excluded = state.get("_turn_affected_spaces", set())

        def _best_skirmish_option(sid, sp):
            """B11: choose option to maximize Rebel casualties.
            Option 2: remove 2 cubes + sacrifice 1 Regular (if 2+ enemy cubes and 2+ own Regs)
            Option 3: remove 1 Fort + sacrifice 1 Regular (if enemy Fort and no enemy cubes)
            Option 1: remove 1 piece (no sacrifice)
            """
            enemy_cubes = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
            )
            own_regs = sp.get(C.REGULAR_BRI, 0)
            # Option 2: maximize cube removal
            if enemy_cubes >= 2 and own_regs >= 2:
                return 2
            # Option 3: remove Fort when no cubes but Fort exists
            enemy_fort = sp.get(C.FORT_PAT, 0)
            if enemy_cubes == 0 and enemy_fort > 0 and own_regs >= 1:
                return 3
            return 1

        def _is_city(sid):
            return _MAP_DATA.get(sid, {}).get("type") == "City"

        # Build prioritized target list
        # Score: WI first (priority 0), then exactly-1-Regular spaces (priority 1), then others (priority 2)
        # Within each tier: first last Rebel in space (fewest total rebels),
        # within that first in a City
        all_targets: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid in excluded:
                continue
            reg = sp.get(C.REGULAR_BRI, 0)
            if reg == 0 and sid != WEST_INDIES:
                continue  # need at least 1 British piece for Skirmish
            enemy = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            if enemy == 0:
                continue
            # Tier
            if sid == WEST_INDIES:
                tier = 0
            elif reg == 1:
                tier = 1
            else:
                tier = 2
            # "first last Rebel in space" = fewest enemy pieces
            # "within that first in a City"
            city_bonus = 0 if _is_city(sid) else 1
            all_targets.append(((tier, enemy, city_bonus), sid))

        all_targets.sort()
        for _, sid in all_targets:
            sp = state["spaces"][sid]
            opt = _best_skirmish_option(sid, sp)
            try:
                skirmish.execute(state, C.BRITISH, {}, sid, option=opt)
                # Clinton bonus: if Clinton is in this space, try to remove
                # 1 additional Militia
                leader = state.get("leaders", {}).get(sid, "")
                if leader == "LEADER_CLINTON":
                    militia_a = sp.get(C.MILITIA_A, 0)
                    if militia_a > 0:
                        from lod_ai.board.pieces import remove_piece
                        try:
                            remove_piece(state, C.MILITIA_A, sid, to="casualties")
                            push_history(state, f"Clinton Skirmish bonus: remove 1 Militia from {sid}")
                        except Exception:
                            pass
                return True
            except Exception:
                continue

        # If Skirmish impossible, attempt Naval Pressure (loop rule)
        return False  # caller may chain

    def _try_naval_pressure(self, state: Dict) -> bool:
        """
        Execute Naval Pressure (B7).  Priorities:
            • If FNI > 0 and Gage or Clinton is British Leader, remove 1 Blockade:
              first from Battle space, then City with most Rebels without Patriot Fort,
              then City with most Support.
            • Otherwise if FNI == 0, add +1D3 Resources.
        Falls back to Skirmish if nothing happens.
        """
        fni = state.get("fni", 0)
        # Check Gage/Clinton leader requirement for blockade removal
        brit_leader = state.get("british_leader") or ""
        # Also check leaders dict for any space
        if not brit_leader:
            for ldr in state.get("leaders", {}).values():
                if ldr in ("LEADER_GAGE", "LEADER_CLINTON"):
                    brit_leader = ldr
                    break
        is_gage_clinton = brit_leader in ("LEADER_GAGE", "LEADER_CLINTON")

        if fni > 0 and is_gage_clinton:
            # Pick blockade removal city per priority:
            # first from Battle space, then City with most Rebels w/o Patriot Fort,
            # then City with most Support
            battle_spaces = state.get("_turn_affected_spaces", set())
            best_city = None
            best_key = None
            for sid in state.get("spaces", {}):
                sp = state["spaces"][sid]
                if sp.get(C.BLOCKADE, 0) <= 0:
                    continue
                in_battle = 0 if sid in battle_spaces else 1
                has_pat_fort = sp.get(C.FORT_PAT, 0) > 0
                rebels = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                          + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0))
                sup = self._support_level(state, sid)
                # Priority: Battle space (0 first), most Rebels w/o Fort, most Support
                key = (in_battle, 1 if has_pat_fort else 0, -rebels, -sup)
                if best_key is None or key < best_key:
                    best_key = key
                    best_city = sid
            if best_city:
                try:
                    naval_pressure.execute(state, C.BRITISH, {}, city_choice=best_city)
                    return True
                except Exception:
                    pass
        elif fni == 0:
            try:
                naval_pressure.execute(state, C.BRITISH, {})
                return True
            except Exception:
                pass
        return False  # caller may chain

    # =======================================================================
    #  NODE B5  :  GARRISON Command
    # =======================================================================
    def _garrison(self, state: Dict) -> bool:
        # Flow‑chart: "First execute a Special Activity."
        self._skirmish_then_naval(state)   # B5 edge "With: B11" → Skirmish first
        state["_sa_done_this_turn"] = True  # prevent double SA if falling to Muster

        refresh_control(state)

        # ----- step 1: choose TARGET City needing British Control ----------
        target = self._select_garrison_city(state)
        if not target:
            return False  # nothing to do → flow‑chart directs to MUSTER

        # ----- step 2: build move-map respecting "leave 2 more pieces" -----
        # Reference: "leave 2 more Royalist than Rebel pieces and remove last
        # Regular only if Pop 0 or Active Support"
        move_map: Dict[str, Dict[str, int]] = {}
        moved_cubes = 0
        for sid, sp in state["spaces"].items():
            if sid == target or self._control(state, sid) != C.BRITISH:
                continue
            royalist_units = (
                sp.get(C.REGULAR_BRI, 0)
                + sp.get(C.TORY, 0)
                + sp.get(C.WARPARTY_A, 0)
                + sp.get(C.WARPARTY_U, 0)
                + sp.get(C.FORT_BRI, 0)
            )
            rebel_units = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            # must leave 2 more Crown than Rebel pieces
            must_leave_royalist = rebel_units + 2
            spare_royalist = max(0, royalist_units - must_leave_royalist)
            # Only move Regulars; can't move last Regular unless Pop 0 or Active Support
            regs = sp.get(C.REGULAR_BRI, 0)
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            at_active_support = self._support_level(state, sid) >= C.ACTIVE_SUPPORT
            min_regs = 0 if (pop == 0 or at_active_support) else 1
            movable = min(spare_royalist, max(0, regs - min_regs))
            if movable <= 0:
                continue
            move_map[sid] = {target: movable}
            moved_cubes += movable

        if moved_cubes == 0:
            # "If no cubes have moved yet, instead Muster."
            # SA was already done above; _muster will skip SA via _sa_done_this_turn
            return self._muster(state, tried_march=False)

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
        """Apply priority bullets to pick the City to garrison.

        Reference B5 move priorities:
        "first just enough to add British Control, first where most Rebels
        without Patriot Fort, then NYC, then random."
        "Then to give each British Control City first 1+ Regular if without
        Active Support, then 3+ British cubes first where Underground Militia."
        """
        candidates: List[Tuple[tuple, str]] = []
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            # B4/B5: target Rebellion-controlled Cities without Rebel Fort
            if self._control(state, name) != "REBELLION":
                continue
            if sp.get(C.FORT_PAT, 0) > 0:
                continue
            rebels = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            has_underground = 1 if sp.get(C.MILITIA_U, 0) > 0 else 0
            is_nyc = 1 if name == "New_York_City" else 0
            # Sort: most rebels first, NYC tiebreak, underground militia tiebreak
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
    def _muster(self, state: Dict, *, tried_march: bool = False) -> bool:
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

        # ----- step 1: choose spaces for Regular placement (sorted) --------
        # Reference: "first in Neutral or Passive, within that first to add
        # British Control then where Tories are the only British units then
        # random; within each first in highest Pop."
        # Neutral/Passive is a priority, not a hard filter — but Regulars
        # can only Muster in Cities or Colonies (§3.2.1), not Provinces.
        reg_candidates: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES:
                continue
            stype = _MAP_DATA.get(sid, {}).get("type", "")
            if stype not in ("City", "Colony"):
                continue
            sup = self._support_level(state, sid)
            is_neutral_or_passive = sup in (
                C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION
            )
            # Priority: Neutral/Passive first (0), then others (1)
            neutral_priority = 0 if is_neutral_or_passive else 1
            # Within that: add British Control (not already controlled)
            adds_control = 0 if self._control(state, sid) != C.BRITISH else 1
            # Then: Tories are the only British units
            tories_only = 0 if (sp.get(C.TORY, 0) > 0
                                and sp.get(C.REGULAR_BRI, 0) == 0
                                and sp.get(C.FORT_BRI, 0) == 0) else 1
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            # Sort: neutral/passive first, adds_control, tories_only, highest pop, random
            key = (neutral_priority, adds_control, tories_only, -pop,
                   state["rng"].random())
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
                # RL info box: "First where fewest Raid + Propaganda markers,
                # within that for largest shift in (Support – Opposition)."
                # Muster: "in 1 space, first one already selected above"
                markers = (1 if n in raid_on_map else 0) + (1 if n in prop_on_map else 0)
                sup = self._support_level(state, n)
                # Largest shift = most negative support level (biggest
                # improvement toward Active Support)
                shift = -sup
                already = 0 if n in all_selected else 1
                # Sort: already selected first (0), fewest markers, largest shift
                return (already, markers, -shift)

            # RL requires British Control + 1+ Regular + 1+ Tory (§3.2.1)
            # and room to shift (not at Active Support)
            rl_candidates = [
                sid for sid, sp in state["spaces"].items()
                if self._support_level(state, sid) < C.ACTIVE_SUPPORT
                and self._control(state, sid) == C.BRITISH
                and sp.get(C.REGULAR_BRI, 0) >= 1
                and sp.get(C.TORY, 0) >= 1
            ]
            # "Do not RL in a space where only Raid/Propaganda markers would be removed"
            # (i.e., already at Active Support with markers — removing markers is the only effect)
            rl_candidates = [
                sid for sid in rl_candidates
                if not (self._support_level(state, sid) == C.ACTIVE_SUPPORT
                        and (sid in raid_on_map or sid in prop_on_map))
            ]
            if rl_candidates:
                chosen_rl_space = min(rl_candidates, key=_rl_key)
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
        all_muster_spaces = list(set(regular_destinations + list(tory_plan.keys())))
        reg_plan = (
            {"space": regular_destinations[0], "n": min(4, avail_regs)}
            if avail_regs and regular_destinations
            else None
        )

        # Guard: muster.execute requires regular_plan for British faction
        if not reg_plan and not tory_plan and not reward_levels and not build_fort:
            # Nothing to muster
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        # If no regular_plan but we have tory_plan, we need at least a dummy
        # regular_plan since muster.execute requires it for British.
        # Use the first tory target space with n=0 as a placeholder.
        if not reg_plan and all_muster_spaces:
            reg_plan = {"space": all_muster_spaces[0], "n": 0}

        if not all_muster_spaces:
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        did_something = muster.execute(
            state,
            C.BRITISH,
            {},
            all_muster_spaces,
            regular_plan=reg_plan,
            tory_plan=tory_plan,
            reward_levels=reward_levels,
            build_fort=bool(build_fort),
        )

        if not did_something:
            # "If not possible, March unless already tried, else Pass."
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        # Execute Special-Activity: B11 arrow (Skirmish first)
        # (skip if SA was already done during Garrison that fell through to Muster)
        if not state.get("_sa_done_this_turn"):
            self._skirmish_then_naval(state)
        return True

    # =======================================================================
    #  NODE B10 :  MARCH Command
    # =======================================================================
    def _march(self, state: Dict, *, tried_muster: bool = False) -> bool:
        """Implements node B10 (Max 4).

        Reference bullets:
        • Lose no British Control. Leave last Tory and War Party in each space,
          and last Regular if British Control but no Active Support.
        • Moving the largest groups first, add British Control to up to 2 Cities
          then Colonies, within each first where Rebel cubes then highest Pop.
          Use Common Cause to increase group size if destination is adjacent Province.
        • Then March to Pop 1+ spaces not at Active Support, first to add Tories
          where Regulars are the only British units, then to add Regulars where
          Tories are the only British units, within each first in the above destinations.
        • Then March in place to Activate Militia, first in Support.
        • If no Common Cause used, execute a Special Activity.
        • If not possible, Muster unless already tried, else Pass.
        """
        refresh_control(state)

        # Collect origin spaces with British pieces
        origins: List[str] = []
        for sid, sp in state["spaces"].items():
            brit = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if brit > 0:
                origins.append(sid)

        if not origins:
            if not tried_muster:
                return self._muster(state, tried_march=True)
            return False

        def _movable_from(sid: str) -> Dict[str, int]:
            """Compute how many pieces of each type can leave *sid*.

            Rules: lose no British Control. Leave last Tory and War Party.
            Leave last Regular if British Control but no Active Support.
            """
            sp = state["spaces"][sid]
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0)
            wp_a = sp.get(C.WARPARTY_A, 0)
            wp_u = sp.get(C.WARPARTY_U, 0)
            royalist = regs + tories + wp_a + wp_u + sp.get(C.FORT_BRI, 0)
            rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            ctrl = self._control(state, sid)
            at_active_support = self._support_level(state, sid) >= C.ACTIVE_SUPPORT

            # Leave last Tory in each space
            min_tories = min(1, tories)
            # Leave last War Party in each space
            min_wp = min(1, wp_a + wp_u)
            # Leave last Regular if British Control but no Active Support
            min_regs = 0
            if ctrl == C.BRITISH and not at_active_support:
                min_regs = min(1, regs)

            # Also must not lose British Control: keep enough royalist to exceed rebel
            keep_royalist = rebel + 1 if ctrl == C.BRITISH else 0
            # Forts stay, so they count toward the kept royalist
            fort_stays = sp.get(C.FORT_BRI, 0)
            wp_stays = min_wp
            # Total that must stay
            must_stay = max(keep_royalist - fort_stays - wp_stays, 0)

            avail_regs = max(0, regs - min_regs)
            avail_tories = max(0, tories - min_tories)
            total_avail = avail_regs + avail_tories

            # If must_stay requires more than minimums
            if (min_regs + min_tories) < must_stay:
                surplus_needed = must_stay - min_regs - min_tories
                # Reduce available by surplus needed
                total_avail = max(0, total_avail - surplus_needed)
                # Prefer keeping Tories (they're cheaper), reduce Regs first
                if avail_regs + avail_tories > total_avail:
                    cut = (avail_regs + avail_tories) - total_avail
                    cut_tories = min(cut, avail_tories)
                    avail_tories -= cut_tories
                    avail_regs -= (cut - cut_tories)

            return {C.REGULAR_BRI: max(0, avail_regs), C.TORY: max(0, avail_tories)}

        # Sort origins by group size descending (largest groups first)
        origins.sort(
            key=lambda n: -(state["spaces"][n].get(C.REGULAR_BRI, 0)
                            + state["spaces"][n].get(C.TORY, 0))
        )

        # === Phase 1: Add British Control to up to 2 Cities then Colonies ===
        control_targets: List[Tuple[tuple, str]] = []
        for sid in origins:
            for dst in _adjacent(sid):
                if dst not in state.get("spaces", {}):
                    continue
                if self._control(state, dst) == C.BRITISH:
                    continue
                dsp = state["spaces"][dst]
                dtype = _MAP_DATA.get(dst, {}).get("type", "")
                if dtype not in ("City", "Colony"):
                    continue
                is_city = 0 if dtype == "City" else 1  # Cities first
                rebel_cubes = (dsp.get(C.REGULAR_PAT, 0) + dsp.get(C.REGULAR_FRE, 0)
                               + dsp.get(C.MILITIA_A, 0) + dsp.get(C.MILITIA_U, 0))
                pop = _MAP_DATA.get(dst, {}).get("population", 0)
                control_targets.append(((is_city, -rebel_cubes, -pop), dst, sid))
        control_targets.sort()
        # Deduplicate destinations, keep first 2
        seen_dst: set = set()
        move_plan: List[Dict] = []
        spaces_used = 0
        for _, dst, origin in control_targets:
            if dst in seen_dst or spaces_used >= 2:
                continue
            movable = _movable_from(origin)
            total = movable.get(C.REGULAR_BRI, 0) + movable.get(C.TORY, 0)
            if total <= 0:
                continue
            pieces: Dict[str, int] = {}
            if movable.get(C.REGULAR_BRI, 0) > 0:
                pieces[C.REGULAR_BRI] = movable[C.REGULAR_BRI]
            if movable.get(C.TORY, 0) > 0:
                pieces[C.TORY] = movable[C.TORY]
            move_plan.append({"src": origin, "dst": dst, "pieces": pieces})
            seen_dst.add(dst)
            spaces_used += 1

        # === Phase 2: Pop 1+ spaces not at Active Support ===
        if spaces_used < 4:
            phase2_targets: List[Tuple[tuple, str, str]] = []
            for sid in origins:
                for dst in _adjacent(sid):
                    if dst not in state.get("spaces", {}) or dst in seen_dst:
                        continue
                    pop = _MAP_DATA.get(dst, {}).get("population", 0)
                    if pop < 1:
                        continue
                    if self._support_level(state, dst) >= C.ACTIVE_SUPPORT:
                        continue
                    dsp = state["spaces"][dst]
                    # Priority: add Tories where Regulars are only British units
                    regs_only = (dsp.get(C.REGULAR_BRI, 0) > 0
                                 and dsp.get(C.TORY, 0) == 0
                                 and dsp.get(C.FORT_BRI, 0) == 0)
                    # Then add Regulars where Tories are only British units
                    tories_only = (dsp.get(C.TORY, 0) > 0
                                   and dsp.get(C.REGULAR_BRI, 0) == 0
                                   and dsp.get(C.FORT_BRI, 0) == 0)
                    tier = 0 if regs_only else (1 if tories_only else 2)
                    phase2_targets.append(((tier, -pop), dst, sid))
            phase2_targets.sort()
            for _, dst, origin in phase2_targets:
                if spaces_used >= 4 or dst in seen_dst:
                    continue
                movable = _movable_from(origin)
                total = movable.get(C.REGULAR_BRI, 0) + movable.get(C.TORY, 0)
                if total <= 0:
                    continue
                pieces = {}
                if movable.get(C.REGULAR_BRI, 0) > 0:
                    pieces[C.REGULAR_BRI] = movable[C.REGULAR_BRI]
                if movable.get(C.TORY, 0) > 0:
                    pieces[C.TORY] = movable[C.TORY]
                move_plan.append({"src": origin, "dst": dst, "pieces": pieces})
                seen_dst.add(dst)
                spaces_used += 1

        # === Phase 3: March in place to Activate Militia, first in Support ===
        # "March in place" activates Underground Militia where British are present.
        # These are handled separately since the march command requires actual moves.
        activate_in_place: List[str] = []
        if spaces_used < 4:
            activate_targets: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in seen_dst:
                    continue
                if sp.get(C.MILITIA_U, 0) > 0 and sp.get(C.REGULAR_BRI, 0) > 0:
                    sup = self._support_level(state, sid)
                    # First in Support (lower sort key = higher priority)
                    activate_targets.append((-sup, sid))
            activate_targets.sort()
            for _, sid in activate_targets:
                if spaces_used >= 4:
                    break
                activate_in_place.append(sid)
                seen_dst.add(sid)
                spaces_used += 1

        if not move_plan and not activate_in_place:
            if not tried_muster:
                return self._muster(state, tried_march=True)
            return False

        # Execute the March (Max 4 spaces) for actual moves
        if move_plan:
            all_srcs = list({p["src"] for p in move_plan})[:4]
            all_dsts = list({p["dst"] for p in move_plan})[:4]
            march.execute(
                state,
                C.BRITISH,
                {},
                all_srcs,
                all_dsts,
                plan=move_plan[:4],
                bring_escorts=False,
                limited=False,
            )

        # Activate Underground Militia in march-in-place spaces
        if activate_in_place:
            from lod_ai.board.pieces import flip_pieces
            for sid in activate_in_place:
                sp = state["spaces"][sid]
                mu = sp.get(C.MILITIA_U, 0)
                if mu > 0:
                    flip_pieces(state, C.MILITIA_U, C.MILITIA_A, sid, mu)
                    push_history(state, f"BRITISH March in place: Activate {mu} Militia in {sid}")

        # Common Cause check (B13) — mode=MARCH for March-specific constraints
        if not self._try_common_cause(state, mode="MARCH"):
            self._skirmish_then_naval(state)
        return True

    # =======================================================================
    #  NODE B12 :  BATTLE Command
    # =======================================================================
    def _battle(self, state: Dict) -> bool:
        """B12: Select all spaces/WI with Rebel Forts and/or Rebel cubes where
        Royalist Force Level + modifiers exceeds Rebel Force Level + modifiers,
        first where most British.

        Force Level per §3.6.2-3.6.3:
          British Attack: Regulars + min(Tories, Regulars) + floor(Active_WP/2)
          Rebel Defense: Continentals + French_Regulars + floor(total_Militia/2) + Forts
        Leader modifiers affect dice rolls (§3.6.5), not force level.
        """
        refresh_control(state)
        targets: List[str] = []

        for sid, sp in state["spaces"].items():
            # B12: "spaces with Rebel Forts and/or Rebel cubes"
            rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            total_militia = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            rebel_forts = sp.get(C.FORT_PAT, 0)
            if rebel_cubes + total_militia + rebel_forts == 0:
                continue

            # Rebel Defense Force Level (assume defender activates Underground)
            rebel_force = rebel_cubes + (total_militia // 2) + rebel_forts

            # Royalist Attack Force Level
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = min(sp.get(C.TORY, 0), regs)  # Tories capped at Regulars
            active_wp = sp.get(C.WARPARTY_A, 0)
            royal_force = regs + tories + (active_wp // 2)

            if royal_force > rebel_force:
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
    def _try_common_cause(self, state: Dict, *, mode: str = "BATTLE") -> bool:
        """B13: Common Cause — use War Parties (Active first) as Tories
        where British Regulars > Tories, up to the number of Regulars.

        Reference constraints:
        - If Marching into adjacent Province, do NOT use last War Party
          (if possible Underground) in origin space.
        - If Battle, do NOT use last Underground War Party.
        - If not possible, Skirmish.

        Return True if Common Cause executed successfully.
        """
        # Find spaces where British Regulars > Tories and War Parties exist
        spaces = []
        for sid, sp in state["spaces"].items():
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0)
            wp_a = sp.get(C.WARPARTY_A, 0)
            wp_u = sp.get(C.WARPARTY_U, 0)
            if regs > tories and (wp_a + wp_u) > 0:
                spaces.append(sid)
        if not spaces:
            return False
        try:
            common_cause.execute(state, C.BRITISH, {}, spaces, mode=mode)
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
            sp = state["spaces"].get(name, {})
            # B4: "Rebels control City w/o Rebel Fort"
            # Must be Rebellion-controlled (not merely uncontrolled)
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
