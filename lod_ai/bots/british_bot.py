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
from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.commands import garrison, muster, march, battle
from lod_ai.special_activities import naval_pressure, skirmish, common_cause
from lod_ai.util.history import push_history
from lod_ai.leaders import leader_location, apply_leader_modifiers

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

    # -------------------------------------------------------------------
    #  Leader helpers
    # -------------------------------------------------------------------
    def _british_leader(self, state: Dict) -> str | None:
        """Return the current British leader ID, or None."""
        # Check explicit british_leader key
        bl = state.get("british_leader")
        if bl and bl.startswith("LEADER_"):
            return bl
        # Check leaders dict (faction -> leader or faction -> [leaders])
        leaders = state.get("leaders", {})
        brit_leaders = leaders.get(C.BRITISH)
        if isinstance(brit_leaders, str) and brit_leaders.startswith("LEADER_"):
            return brit_leaders
        if isinstance(brit_leaders, list):
            for lid in brit_leaders:
                if isinstance(lid, str) and lid.startswith("LEADER_"):
                    return lid
        # Scan leader_locs for any British leader on the map
        for lid in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"):
            if leader_location(state, lid):
                return lid
        return None

    def _is_howe(self, state: Dict) -> bool:
        return self._british_leader(state) == "LEADER_HOWE"

    def _is_gage(self, state: Dict) -> bool:
        return self._british_leader(state) == "LEADER_GAGE"

    def _apply_howe_fni(self, state: Dict) -> None:
        """B38: If Howe is British Leader, lower FNI by 1 before SAs."""
        if self._is_howe(state):
            fni = state.get("fni_level", 0)
            if fni > 0:
                state["fni_level"] = fni - 1
                push_history(state, "Howe capability: FNI lowered by 1 before SA")

    # =======================================================================
    #  BRILLIANT STROKE LimCom  (§8.3.7)
    # =======================================================================
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk British flowchart for the first valid Limited Command
        that can involve the British Leader in the Leader's current space.

        Flowchart order: B3 → B4 (Garrison) → B6 (Muster) → B9 (Battle) → B10 (March).
        Returns a command name or None.
        """
        leader_space = self._find_bs_leader_space(state)
        if not leader_space:
            return None

        # B3: Resources > 0?
        if state.get("resources", {}).get(C.BRITISH, 0) <= 0:
            return None

        sp = state["spaces"].get(leader_space, {})
        refresh_control(state)

        # B4: Garrison — valid if 10+ Regulars on map AND leader is in a
        # Rebellion-controlled City without Rebel Fort (the garrison target).
        if self._can_garrison(state):
            ctrl = state.get("control", {}).get(leader_space)
            if (ctrl == "REBELLION"
                    and sp.get(C.FORT_PAT, 0) == 0
                    and leader_space in CITIES):
                return "garrison"

        # B6: Muster — Available Regulars > 1D6?  (consume a die roll)
        avail_regs = state["available"].get(C.REGULAR_BRI, 0)
        avail_tories = state["available"].get(C.TORY, 0)
        if avail_regs > 0 or avail_tories > 0:
            # Muster can always target the leader's space (City/Colony)
            stype = _MAP_DATA.get(leader_space, {}).get("type", "")
            if stype in ("City", "Colony"):
                return "muster"

        # B9: Battle — 2+ Active Rebels in leader's space outnumbered by
        # British Regulars + Leader?
        active_rebel = (sp.get(C.REGULAR_PAT, 0)
                        + sp.get(C.MILITIA_A, 0)
                        + sp.get(C.REGULAR_FRE, 0))
        regs = sp.get(C.REGULAR_BRI, 0)
        if active_rebel >= 2 and regs > active_rebel:
            return "battle"

        # B10: March — can march from leader's space if pieces exist
        if sp.get(C.REGULAR_BRI, 0) > 0 or sp.get(C.TORY, 0) > 0:
            return "march"

        return None

    # =======================================================================
    #  EVENT‑VS‑COMMAND BULLETS (B2)
    # =======================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """B2: Check unshaded Event conditions for British bot via CARD_EFFECTS."""
        effects = CARD_EFFECTS.get(card.get("id"))
        if effects is None:
            return False  # unknown card → fall through to Command
        eff = effects["unshaded"]

        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # 1. "Opposition > Support, and Event shifts Support/Opposition in
        #     Royalist favor (including by removing a Blockade)?"
        if opp > sup and (eff["shifts_support_royalist"] or eff["removes_blockade"]):
            return True

        # 2. "Event places British pieces from Unavailable?"
        if eff["places_british_from_unavailable"]:
            return True

        # 3. "Event places Tories in Active Opposition with none, a British Fort
        #     in a Colony with none, or British Regulars in a City or Colony?"
        if eff["places_tories"]:
            for sid, sp in state["spaces"].items():
                if (self._support_level(state, sid) == C.ACTIVE_OPPOSITION
                        and sp.get(C.TORY, 0) == 0):
                    return True
        if eff["places_british_fort"]:
            for sid in state["spaces"]:
                if (_MAP_DATA.get(sid, {}).get("type") == "Colony"
                        and state["spaces"][sid].get(C.FORT_BRI, 0) == 0):
                    return True
        if eff["places_british_regulars"]:
            for sid in state["spaces"]:
                if _MAP_DATA.get(sid, {}).get("type") in ("City", "Colony"):
                    return True

        # 4. "Event inflicts Rebel Casualties (including free Skirmish or Battle)?"
        if eff["inflicts_rebel_casualties"]:
            return True

        # 5. "British Control 5+ Cities, the Event is effective, and a D6 rolls 5+?"
        if eff["is_effective"]:
            controlled_cities = sum(
                1 for sid in CITIES
                if self._control(state, sid) == C.BRITISH
            )
            if controlled_cities >= 5:
                roll = state["rng"].randint(1, 6)
                state.setdefault("rng_log", []).append(("Event D6", roll))
                if roll >= 5:
                    return True
        return False

    # =======================================================================
    #  CONDITIONAL FORCE DIRECTIVES (musket instructions)
    # =======================================================================
    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives from the British instruction sheet.

        Each card instruction specifies a condition; if not met, the bot
        skips the event and proceeds to Command & SA instead.
        """
        if directive in ("force_if_51", "force_if_52"):
            # Cards 51/52: "March to set up Battle per the Battle instructions.
            # If not possible, choose Command & Special Activity instead."
            # Check: any space where Royalist FL exceeds Rebel FL and British
            # could march there from adjacent?
            refresh_control(state)
            for sid, sp in state["spaces"].items():
                rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                total_militia = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                rebel_forts = sp.get(C.FORT_PAT, 0)
                if rebel_cubes + total_militia + rebel_forts == 0:
                    continue
                rebel_force = rebel_cubes + (total_militia // 2) + rebel_forts
                regs = sp.get(C.REGULAR_BRI, 0)
                tories = min(sp.get(C.TORY, 0), regs)
                active_wp = sp.get(C.WARPARTY_A, 0)
                royal_force = regs + tories + (active_wp // 2)
                # Check if British already exceed here
                if royal_force > rebel_force:
                    return True
                # Check if marching in from adjacent could tip the balance
                for adj_sid in _adjacent(sid):
                    adj_sp = state["spaces"].get(adj_sid, {})
                    march_regs = adj_sp.get(C.REGULAR_BRI, 0)
                    if march_regs > 0 and (royal_force + march_regs) > rebel_force:
                        return True
            return False

        if directive == "force_if_62":
            # Card 62: "If New York is at Active Opposition and has no Tories
            # already, place Tories there. Otherwise, Command & SA."
            ny = state["spaces"].get("New_York", {})
            if (self._support_level(state, "New_York") == C.ACTIVE_OPPOSITION
                    and ny.get(C.TORY, 0) == 0):
                return True
            return False

        if directive == "force_if_70":
            # Card 70: "Remove French Regulars from West Indies, then from
            # spaces with British pieces. If none, Command & SA."
            # Check: any French Regulars in WI or spaces with British pieces?
            wi = state["spaces"].get(WEST_INDIES, {})
            if wi.get(C.REGULAR_FRE, 0) > 0:
                return True
            for sid, sp in state["spaces"].items():
                if sid == WEST_INDIES:
                    continue
                brit_present = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                                + sp.get(C.FORT_BRI, 0))
                if brit_present > 0 and sp.get(C.REGULAR_FRE, 0) > 0:
                    return True
            return False

        if directive == "force_if_80":
            # Card 80: "Choose a Rebel Faction with pieces in Cities, and select
            # Cities where that Faction has pieces. If none, Command & SA."
            rebel_tags = {
                C.PATRIOTS: [C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT],
                C.FRENCH: [C.REGULAR_FRE],
                C.INDIANS: [C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE],
            }
            for faction, tags in rebel_tags.items():
                for city_sid in CITIES:
                    sp = state["spaces"].get(city_sid, {})
                    if any(sp.get(tag, 0) > 0 for tag in tags):
                        return True
            return False

        return True  # default: play the event

    # =======================================================================
    #  MAIN FLOW‑CHART DRIVER  (§8.4 nodes B4 → B13)
    # =======================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # --- B3  : Resources > 0? -----------------------------------------
        if state.get("resources", {}).get(C.BRITISH, 0) <= 0:
            state['_pass_reason'] = 'resource_gate'
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
        state['_pass_reason'] = 'no_valid_command'
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
            Option 2: remove 2 cubes + sacrifice 1 Regular (if 2+ enemy cubes and 1+ own Regs)
            Option 3: remove 1 Fort + sacrifice 1 Regular (if enemy Fort and no enemy cubes)
            Option 1: remove 1 piece (no sacrifice)
            """
            enemy_cubes = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
            )
            own_regs = sp.get(C.REGULAR_BRI, 0)
            # Option 2: maximize cube removal — sacrifice 1 Regular, so only 1 needed
            if enemy_cubes >= 2 and own_regs >= 1:
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
                # Clinton bonus is handled inside skirmish.execute via the
                # leader modifier system (apply_leader_modifiers → _clinton).
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
        fni = state.get("fni_level", 0)
        # Check Gage/Clinton leader requirement for blockade removal
        brit_leader = self._british_leader(state)
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
    #  NODE B5  :  GARRISON Command  (full multi-phase per flowchart)
    # =======================================================================
    def _garrison(self, state: Dict) -> bool:
        """Full multi-phase Garrison per B5 reference:

        Phase 1: SA first (Skirmish then Naval).
        Phase 2a: From British-controlled origins (retention rules), move
                  just enough Regulars to add British Control to cities.
                  Priority: most Rebels without Patriot Fort, then NYC.
        Phase 2b: Reinforce existing British Control cities:
                  first 1+ Regular if without Active Support,
                  then 3+ British cubes first where Underground Militia.
        Phase 3: If no cubes moved, Muster fallback.
        Phase 4: If cubes moved, Activate Underground Militia and displace
                  Rebels (first most Opposition, then least Support, lowest Pop).
        """
        # Phase 1: SA first
        self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
        self._skirmish_then_naval(state)
        state["_sa_done_this_turn"] = True

        refresh_control(state)

        # Build origin pool: how many Regulars each British-controlled space
        # can contribute, per retention rules.
        origin_avail = self._garrison_origin_pool(state)

        # Phase 2a: Move just enough to add British Control to cities
        # Target: Rebellion-controlled Cities without Patriot Fort
        phase2a_targets = self._garrison_phase2a_targets(state)
        move_map: Dict[str, Dict[str, int]] = {}
        total_moved = 0
        dest_cities: List[str] = []

        for city, needed in phase2a_targets:
            if needed <= 0:
                continue
            still_needed = needed
            # Pick origins sorted by most available first
            for origin in sorted(origin_avail, key=lambda o: -origin_avail.get(o, 0)):
                if still_needed <= 0:
                    break
                avail = origin_avail.get(origin, 0)
                if avail <= 0 or origin == city:
                    continue
                give = min(avail, still_needed)
                move_map.setdefault(origin, {})[city] = \
                    move_map.get(origin, {}).get(city, 0) + give
                origin_avail[origin] -= give
                still_needed -= give
                total_moved += give
            if still_needed < needed:
                dest_cities.append(city)

        # Phase 2b: Reinforce existing British Control cities
        reinforce_targets = self._garrison_phase2b_targets(state)
        for city, need in reinforce_targets:
            if need <= 0:
                continue
            still_need = need
            for origin in sorted(origin_avail, key=lambda o: -origin_avail.get(o, 0)):
                if still_need <= 0:
                    break
                avail = origin_avail.get(origin, 0)
                if avail <= 0 or origin == city:
                    continue
                give = min(avail, still_need)
                move_map.setdefault(origin, {})[city] = \
                    move_map.get(origin, {}).get(city, 0) + give
                origin_avail[origin] -= give
                still_need -= give
                total_moved += give
            if still_need < need:
                dest_cities.append(city)

        # Phase 3: If no cubes moved, Muster fallback
        if total_moved == 0:
            return self._muster(state, tried_march=False)

        # Phase 4: Displacement — pick city with most Rebels as source
        displace_city, displace_target = self._select_displacement(state, dest_cities)

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
    def _garrison_origin_pool(self, state: Dict) -> Dict[str, int]:
        """Compute how many Regulars each British-controlled origin can
        contribute to Garrison, respecting retention rules:
        - Leave 2 more Royalist than Rebel pieces (counting Forts)
        - Remove last Regular only if Pop 0 or Active Support
        """
        pool: Dict[str, int] = {}
        for sid, sp in state["spaces"].items():
            if self._control(state, sid) != C.BRITISH:
                continue
            royalist = (
                sp.get(C.REGULAR_BRI, 0)
                + sp.get(C.TORY, 0)
                + sp.get(C.WARPARTY_A, 0)
                + sp.get(C.WARPARTY_U, 0)
                + sp.get(C.FORT_BRI, 0)
            )
            rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            must_leave = rebel + 2
            spare = max(0, royalist - must_leave)
            regs = sp.get(C.REGULAR_BRI, 0)
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            at_active_support = self._support_level(state, sid) >= C.ACTIVE_SUPPORT
            min_regs = 0 if (pop == 0 or at_active_support) else 1
            movable = min(spare, max(0, regs - min_regs))
            if movable > 0:
                pool[sid] = movable
        return pool

    def _garrison_phase2a_targets(self, state: Dict) -> List[Tuple[str, int]]:
        """Phase 2a: Cities where moving Regulars would add British Control.
        Returns list of (city, regulars_needed), sorted by priority:
        first where most Rebels without Patriot Fort, then NYC.
        """
        targets: List[Tuple[tuple, str, int]] = []
        for city in CITIES:
            sp = state["spaces"].get(city, {})
            if self._control(state, city) != "REBELLION":
                continue
            if sp.get(C.FORT_PAT, 0) > 0:
                continue
            rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
                + sp.get(C.FORT_PAT, 0)
            )
            brit_there = (
                sp.get(C.REGULAR_BRI, 0)
                + sp.get(C.TORY, 0)
                + sp.get(C.FORT_BRI, 0)
            )
            # Need enough to exceed rebel pieces (brit > rebel for control)
            needed = max(0, rebel + 1 - brit_there)
            is_nyc = 1 if city == "New_York_City" else 0
            # Sort: most rebels first, NYC second, random tiebreak
            key = (-rebel, -is_nyc, state["rng"].random())
            targets.append((key, city, needed))
        targets.sort()
        return [(city, needed) for _, city, needed in targets]

    def _garrison_phase2b_targets(self, state: Dict) -> List[Tuple[str, int]]:
        """Phase 2b: Reinforce existing British Control cities.
        - First 1+ Regular if without Active Support
        - Then 3+ British cubes first where Underground Militia
        Returns list of (city, cubes_needed), sorted by priority.
        """
        targets: List[Tuple[tuple, str, int]] = []
        for city in CITIES:
            sp = state["spaces"].get(city, {})
            if self._control(state, city) != C.BRITISH:
                continue
            regs = sp.get(C.REGULAR_BRI, 0)
            at_active_support = self._support_level(state, city) >= C.ACTIVE_SUPPORT
            brit_cubes = regs + sp.get(C.TORY, 0)
            has_underground = sp.get(C.MILITIA_U, 0) > 0

            # First priority: 1+ Regular if without Active Support
            if not at_active_support and regs == 0:
                targets.append(((0, 0, city), city, 1))
            # Second priority: 3+ cubes first where Underground Militia
            if brit_cubes < 3:
                need = 3 - brit_cubes
                underground_prio = 0 if has_underground else 1
                targets.append(((1, underground_prio, city), city, need))

        targets.sort()
        return [(city, need) for _, city, need in targets]

    def _select_displacement(self, state: Dict, dest_cities: List[str]) -> Tuple[str | None, str | None]:
        """Phase 4: Activate Militia then displace most Rebels.
        Pick the destination city with most Rebels as the displacement source.
        Pick Province with most Opposition, then least Support, then lowest Pop.
        """
        if not dest_cities:
            return (None, None)

        # Pick city with most Rebels for displacement
        best_city = None
        most_rebels = -1
        for city in dest_cities:
            sp = state["spaces"].get(city, {})
            rebels = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            if rebels > most_rebels:
                most_rebels = rebels
                best_city = city

        if not best_city or most_rebels == 0:
            return (None, None)

        # Pick Colony/Province target: most Opposition, least Support, lowest Pop
        # (The game's "Province" spaces are "Colony" type in map data)
        best_province = None
        best_key = None
        for sid in state["spaces"]:
            stype = _MAP_DATA.get(sid, {}).get("type", "")
            if stype not in ("Colony", "Province"):
                continue
            support_level = self._support_level(state, sid)
            opp = max(0, -support_level)
            sup = max(0, support_level)
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            key = (-opp, sup, pop)  # minimize: most opp, least support, lowest pop
            if best_key is None or key < best_key:
                best_key = key
                best_province = sid

        return (best_city, best_province) if best_province else (None, None)

    # =======================================================================
    #  NODE B8  :  MUSTER Command
    # =======================================================================
    def _muster(self, state: Dict, *, tried_march: bool = False) -> bool:
        """Full bullet-list implementation for node B8 (Max 4 spaces).

        Reference priorities:
        1. Place Regulars: first in Neutral or Passive, within that first
           to add British Control then where Tories are the only British
           units then random; within each first in highest Pop.
        2. Place up to 2 Tories per space (1 if Passive Opposition):
           - First where Regulars are the only British cubes
             (within that first where Regulars were just placed)
           - Then to change most Control
           - Then in Colonies with < 5 British cubes and no British Fort
           - Skip Active Opposition; require adjacency to British power.
        3. In 1 space, first one already selected above:
           RL if Opposition > Support + 1D3 OR no Forts Available;
           else Fort in Colony with 5+ cubes and no Fort.
           Pass fort_space to muster.execute for correct targeting.
        B39 Gage: Free first Reward Loyalty shift.
        """
        avail_regs = state["available"].get(C.REGULAR_BRI, 0)
        avail_tories = state["available"].get(C.TORY, 0)
        if avail_regs == 0 and avail_tories == 0:
            return False

        refresh_control(state)

        # ----- step 1: choose spaces for Regular placement (sorted) --------
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
            neutral_priority = 0 if is_neutral_or_passive else 1
            adds_control = 0 if self._control(state, sid) != C.BRITISH else 1
            tories_only = 0 if (sp.get(C.TORY, 0) > 0
                                and sp.get(C.REGULAR_BRI, 0) == 0
                                and sp.get(C.FORT_BRI, 0) == 0) else 1
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            key = (neutral_priority, adds_control, tories_only, -pop,
                   state["rng"].random())
            reg_candidates.append((key, sid))

        reg_candidates.sort()
        regular_destinations: List[str] = []
        if avail_regs > 0 and reg_candidates:
            regular_destinations.append(reg_candidates[0][1])

        # ----- step 2: Tory placement priorities ---------------------------
        # Up to 2 Tories per space (1 if Passive Opposition).
        # Skip Active Opposition spaces and spaces not adjacent to British power.
        selected_spaces = set(regular_destinations)
        tory_plan: Dict[str, int] = {}

        def _tory_eligible(sid: str) -> bool:
            """Check if a space is eligible for Tory placement."""
            if sid == WEST_INDIES:
                return False
            sup = self._support_level(state, sid)
            if sup <= C.ACTIVE_OPPOSITION:
                return False  # Skip Active Opposition
            # Adjacency to British power check
            sp = state["spaces"].get(sid, {})
            if sp.get(C.REGULAR_BRI, 0) > 0 or sp.get(C.FORT_BRI, 0) > 0:
                return True
            for nbr in _adjacent(sid):
                nsp = state["spaces"].get(nbr, {})
                if nsp and (nsp.get(C.REGULAR_BRI, 0) > 0 or nsp.get(C.FORT_BRI, 0) > 0):
                    return True
            return False

        def _tory_max(sid: str) -> int:
            """Max Tories placeable in a space (1 if Passive Opposition, else 2)."""
            sup = self._support_level(state, sid)
            return 1 if sup == C.PASSIVE_OPPOSITION else 2

        # Priority 1: where Regulars are the only British cubes
        tory_p1: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if not _tory_eligible(sid):
                continue
            if sp.get(C.REGULAR_BRI, 0) > 0 and sp.get(C.TORY, 0) == 0 and sp.get(C.FORT_BRI, 0) == 0:
                just_placed = 0 if sid in selected_spaces else 1
                tory_p1.append(((just_placed,), sid))
        tory_p1.sort()
        for _, sid in tory_p1:
            if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                break
            n = min(_tory_max(sid), avail_tories)
            tory_plan[sid] = n
            avail_tories -= n

        # Priority 2: change most Control
        if avail_tories > 0:
            tory_p2: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in tory_plan or not _tory_eligible(sid):
                    continue
                brit_pieces = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) + sp.get(C.FORT_BRI, 0)
                rebel_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                                + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                                + sp.get(C.FORT_PAT, 0))
                gap = rebel_pieces - brit_pieces
                tory_p2.append((-gap, sid))
            tory_p2.sort()
            for _, sid in tory_p2:
                if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                    break
                if sid in tory_plan:
                    continue
                n = min(_tory_max(sid), avail_tories)
                tory_plan[sid] = n
                avail_tories -= n

        # Priority 3: Colonies with < 5 British cubes and no British Fort
        if avail_tories > 0:
            tory_p3: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in tory_plan or not _tory_eligible(sid):
                    continue
                if (_MAP_DATA.get(sid, {}).get("type") == "Colony"
                        and sp.get(C.FORT_BRI, 0) == 0
                        and (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)) < 5):
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    tory_p3.append((-pop, sid))
            tory_p3.sort()
            for _, sid in tory_p3:
                if avail_tories <= 0 or len(tory_plan) + len(selected_spaces) >= 4:
                    break
                n = min(_tory_max(sid), avail_tories)
                tory_plan[sid] = n
                avail_tories -= n

        # ----- step 3: Reward Loyalty OR build Fort in one space -----------
        all_selected = list(selected_spaces | set(tory_plan.keys()))
        reward_levels = 0
        fort_space: str | None = None
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
                shift = -sup
                already = 0 if n in all_selected else 1
                return (already, markers, -shift)

            rl_candidates = [
                sid for sid, sp in state["spaces"].items()
                if self._support_level(state, sid) < C.ACTIVE_SUPPORT
                and self._control(state, sid) == C.BRITISH
                and sp.get(C.REGULAR_BRI, 0) >= 1
                and sp.get(C.TORY, 0) >= 1
            ]
            if rl_candidates:
                chosen_rl_space = min(rl_candidates, key=_rl_key)
                reward_levels = 1

        if chosen_rl_space is None and state["available"].get(C.FORT_BRI, 0):
            fort_targets = [
                sid
                for sid, sp in state["spaces"].items()
                if _MAP_DATA.get(sid, {}).get("type") == "Colony"
                and sp.get(C.FORT_BRI, 0) == 0
                and (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)) >= 5
            ]
            fort_targets.sort(key=lambda n: (0 if n in all_selected else 1))
            if fort_targets:
                fort_space = fort_targets[0]

        # ----- EXECUTE MUSTER ---------------------------------------------
        all_muster_spaces = list(set(regular_destinations + list(tory_plan.keys())))
        # Include fort_space in selected if not already there
        if fort_space and fort_space not in all_muster_spaces:
            all_muster_spaces.append(fort_space)
        # Include RL space in selected if not already there
        if chosen_rl_space and chosen_rl_space not in all_muster_spaces:
            all_muster_spaces.append(chosen_rl_space)

        reg_plan = (
            {"space": regular_destinations[0], "n": min(4, state["available"].get(C.REGULAR_BRI, 0))}
            if state["available"].get(C.REGULAR_BRI, 0) > 0 and regular_destinations
            else None
        )

        if not reg_plan and not tory_plan and not reward_levels and not fort_space:
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        if not reg_plan and all_muster_spaces:
            reg_plan = {"space": all_muster_spaces[0], "n": 0}

        if not all_muster_spaces:
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        # B39 Gage: free first Reward Loyalty shift
        rl_free_first = self._is_gage(state) and reward_levels > 0

        did_something = muster.execute(
            state,
            C.BRITISH,
            {},
            all_muster_spaces,
            regular_plan=reg_plan,
            tory_plan=tory_plan,
            reward_levels=reward_levels,
            build_fort=bool(fort_space),
            fort_space=fort_space,
            rl_free_first=rl_free_first,
        )

        if not did_something:
            if not tried_march:
                return self._march(state, tried_muster=True)
            return False

        # Execute SA (skip if already done during Garrison fallback)
        if not state.get("_sa_done_this_turn"):
            self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
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
        cc_spaces: Dict[str, int] = {}  # B13: CC War Parties per space
        spaces_used = 0
        for _, dst, origin in control_targets:
            if dst in seen_dst or spaces_used >= 2:
                continue
            movable = _movable_from(origin)
            total = movable.get(C.REGULAR_BRI, 0) + movable.get(C.TORY, 0)

            # B10+B13: When destination is an adjacent Province, include
            # War Parties via Common Cause to increase group size.
            # CC restriction: War Parties may never move into Cities.
            # "Province" in rules = Colony or Reserve (anything not a City).
            dst_type = _MAP_DATA.get(dst, {}).get("type", "")
            cc_wp_count = 0
            osp = state["spaces"][origin]
            if dst_type not in ("City", "Special"):
                # B13: WP as Tories when Regulars > Tories
                regs_here = osp.get(C.REGULAR_BRI, 0)
                tories_here = osp.get(C.TORY, 0) + movable.get(C.TORY, 0)
                if regs_here > tories_here:
                    wp_a = osp.get(C.WARPARTY_A, 0)
                    wp_u = osp.get(C.WARPARTY_U, 0)
                    # Preserve last WP per B13 March constraint
                    avail_wp = max(0, wp_a + wp_u - 1)
                    cc_wp_count = min(avail_wp, regs_here - tories_here)
                    total += cc_wp_count

            if total <= 0:
                continue
            pieces: Dict[str, int] = {}
            if movable.get(C.REGULAR_BRI, 0) > 0:
                pieces[C.REGULAR_BRI] = movable[C.REGULAR_BRI]
            if movable.get(C.TORY, 0) > 0:
                pieces[C.TORY] = movable[C.TORY]
            if cc_wp_count > 0:
                cc_spaces[origin] = cc_wp_count
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

        # B10+B13: Execute Common Cause BEFORE the March so that WP from CC
        # contribute to group sizes for adjacent Province destinations.
        used_cc = False
        march_ctx = {}
        if cc_spaces:
            try:
                cc_ctx = common_cause.execute(
                    state, C.BRITISH, {}, list(cc_spaces.keys()),
                    mode="MARCH", wp_counts=cc_spaces, preserve_wp=True,
                )
                march_ctx = cc_ctx
                used_cc = True
            except (ValueError, KeyError):
                pass  # CC failed — proceed without it

        # Execute the March (Max 4 spaces) for actual moves
        if move_plan:
            all_srcs = list({p["src"] for p in move_plan})[:4]
            all_dsts = list({p["dst"] for p in move_plan})[:4]
            march.execute(
                state,
                C.BRITISH,
                march_ctx,
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

        # If CC was not used during planning, try it post-March (fallback),
        # otherwise skip to SA chain
        if not used_cc:
            if not self._try_common_cause(state, mode="MARCH"):
                self._apply_howe_fni(state)
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

        Modifiers included per §3.6.5-3.6.6:
          Attacker (Defender Loss): +1 half regs, +1 underground, +1 leader
          Defender (Attacker Loss): +1 half regs, +1 underground, +1 leader, +/- forts, blockade
        """
        refresh_control(state)
        targets: List[Tuple[int, str]] = []

        for sid, sp in state["spaces"].items():
            # B12: "spaces with Rebel Forts and/or Rebel cubes"
            rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            total_militia = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            rebel_forts = sp.get(C.FORT_PAT, 0)
            if rebel_cubes + total_militia + rebel_forts == 0:
                continue

            # Rebel Defense Force Level
            rebel_force = rebel_cubes + (total_militia // 2) + rebel_forts

            # Royalist Attack Force Level
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = min(sp.get(C.TORY, 0), regs)
            active_wp = sp.get(C.WARPARTY_A, 0)
            royal_force = regs + tories + (active_wp // 2)

            # --- Estimate net modifier advantage for the bot ---
            # Attacker (British) modifiers on Defender Loss:
            att_mod = 0
            att_cubes = regs + sp.get(C.TORY, 0)
            if att_cubes > 0 and regs * 2 >= att_cubes:
                att_mod += 1  # half regs
            if sp.get(C.WARPARTY_U, 0) > 0:
                att_mod += 1  # underground piece
            # British leader bonus
            for lid in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"):
                if leader_location(state, lid) == sid:
                    att_mod += 1
                    break
            # -1 per defending Fort
            att_mod -= rebel_forts

            # Defender (Rebel) modifiers on Attacker Loss:
            def_mod = 0
            def_regs = rebel_cubes
            if def_regs > 0 and def_regs * 2 >= rebel_cubes:
                def_mod += 1  # half regs
            if sp.get(C.MILITIA_U, 0) > 0:
                def_mod += 1  # underground
            # Rebel leader bonus
            for lid in ("LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN"):
                if leader_location(state, lid) == sid:
                    def_mod += 1
                    break
            # +1 per defending fort (fort helps defender's attacker-loss roll)
            def_mod += rebel_forts

            # Net advantage: positive means British is stronger
            net_advantage = (royal_force + att_mod) - (rebel_force + def_mod)
            if net_advantage > 0:
                british_count = regs + sp.get(C.TORY, 0)
                targets.append((-british_count, sid))

        if not targets:
            return False

        targets.sort()
        chosen = [sid for _, sid in targets]

        # Common Cause before the battles
        used_cc = self._try_common_cause(state)

        # If no Common Cause, execute Skirmish/Naval loop first
        if not used_cc:
            self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
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
            common_cause.execute(state, C.BRITISH, {}, spaces, mode=mode,
                                 preserve_wp=True)
            return True
        except Exception:
            return False

    # =======================================================================
    #  PRE‑CONDITION CHECKS  (mirrors italics at start of §8.4.x)
    # =======================================================================
    def _can_garrison(self, state: Dict) -> bool:
        # Garrison unavailable at FNI level 3
        if state.get("fni_level", 0) >= 3:
            return False
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
        # B6: Roll once and cache the result for this turn
        if "_muster_die_cached" not in state:
            die = state["rng"].randint(1, 6)
            state["_muster_die_cached"] = die
            state.setdefault("rng_log", []).append(("B6 1D6", die))
        return state["available"].get(C.REGULAR_BRI, 0) > state["_muster_die_cached"]

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
            has_british_leader = any(
                leader_location(state, lid) == sid
                for lid in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON")
            )
            if royal + (1 if has_british_leader else 0) > active_rebel:
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.REGULAR_BRI, 0) > 0 for sp in state["spaces"].values())

    # =======================================================================
    #  OPS Summary methods (year-end and during-turn bot decisions)
    # =======================================================================

    def bot_supply_priority(self, state: Dict) -> List[str]:
        """British Supply: Pay only in spaces where removing British would
        prevent Reward Loyalty or allow Committees of Correspondance,
        first with Resources in highest Pop, then with shifts in highest Pop.

        Returns ordered list of space IDs where British should pay Supply.
        """
        pay_spaces: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid == C.WEST_INDIES_ID:
                continue
            brit_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if brit_cubes == 0:
                continue
            meta = _MAP_DATA.get(sid, {})
            stype = meta.get("type", "")
            if sp.get(C.FORT_BRI, 0) or (stype == "City" and self._control(state, sid) == C.BRITISH):
                continue  # in supply, no payment needed

            # Check: would removing British prevent RL?
            prevents_rl = (
                sp.get(C.REGULAR_BRI, 0) >= 1
                and sp.get(C.TORY, 0) >= 1
                and self._control(state, sid) == C.BRITISH
                and self._support_level(state, sid) < C.ACTIVE_SUPPORT
            )
            # Check: would removing British allow Committees?
            rebel_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                           + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0))
            allows_committees = rebel_pieces > 0  # removing British would let Rebels gain control

            if prevents_rl or allows_committees:
                pop = meta.get("population", 0)
                # First by highest Pop
                pay_spaces.append((-pop, sid))

        pay_spaces.sort()
        return [sid for _, sid in pay_spaces]

    def bot_redeploy_leader(self, state: Dict) -> str | None:
        """Redeploy: British Leader to the space with most British Regulars."""
        best_sid = None
        best_regs = -1
        for sid, sp in state["spaces"].items():
            regs = sp.get(C.REGULAR_BRI, 0)
            if regs > best_regs:
                best_regs = regs
                best_sid = sid
        return best_sid

    def bot_loyalist_desertion(self, state: Dict, count: int) -> List[Tuple[str, int]]:
        """Loyalist Desertion: Remove Tories to change least Control,
        if possible without removing last Tory in any space.

        Returns list of (space_id, n_to_remove) totaling *count*.
        """
        removals: List[Tuple[str, int]] = []
        remaining = count

        # Build list of spaces with Tories, sorted by least Control impact
        candidates: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            tories = sp.get(C.TORY, 0)
            if tories == 0:
                continue
            # Compute how much control would change if we remove 1 Tory
            royalist = (sp.get(C.REGULAR_BRI, 0) + tories
                       + sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
                       + sp.get(C.FORT_BRI, 0))
            rebel = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                    + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                    + sp.get(C.FORT_PAT, 0))
            margin = royalist - rebel
            is_last = 1 if tories == 1 else 0  # avoid last Tory
            # Sort: avoid last first, then least margin change (biggest margin first)
            candidates.append(((is_last, -margin), sid))

        candidates.sort()

        for _, sid in candidates:
            if remaining <= 0:
                break
            sp = state["spaces"][sid]
            tories = sp.get(C.TORY, 0)
            # Avoid removing last Tory if possible (only do it if we must)
            can_take = tories - 1 if tories > 1 else 0
            if can_take <= 0 and remaining > 0:
                # Only take last Tory if we must
                continue
            take = min(can_take, remaining)
            if take > 0:
                removals.append((sid, take))
                remaining -= take

        # If we still need more, reluctantly take last Tories
        if remaining > 0:
            for _, sid in candidates:
                if remaining <= 0:
                    break
                sp = state["spaces"][sid]
                tories = sp.get(C.TORY, 0)
                already = sum(n for s, n in removals if s == sid)
                left = tories - already
                if left > 0:
                    take = min(left, remaining)
                    removals.append((sid, take))
                    remaining -= take

        return removals

    def bot_indian_trade(self, state: Dict) -> int:
        """Indian Trade: If Indian Resources < British Resources, roll 1D6.
        If roll < British Resources, offer half (round up) the number rolled.

        Returns the amount to transfer (0 if trade not possible/favorable).
        """
        indian_res = state.get("resources", {}).get(C.INDIANS, 0)
        british_res = state.get("resources", {}).get(C.BRITISH, 0)
        if indian_res >= british_res:
            return 0
        die = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Indian Trade 1D6", die))
        if die >= british_res:
            return 0
        offer = (die + 1) // 2  # half rounded up
        return offer

    def bot_leader_movement(self, state: Dict, leader: str, spaces_with_moves: Dict[str, int]) -> str | None:
        """Leader Movement: Royalist Leaders follow largest group of own units
        that moves from (or stays in) their spaces.

        *spaces_with_moves* maps space_id -> total British pieces moving from/staying.
        Returns the space ID the leader should be in.
        """
        leader_loc = leader_location(state, leader)
        if not leader_loc:
            return None

        # Find the largest group of British units moving from or staying in the leader's space
        best_dest = leader_loc
        best_count = 0
        sp = state["spaces"].get(leader_loc, {})
        staying = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
        if staying > best_count:
            best_count = staying
            best_dest = leader_loc

        for dest, count in spaces_with_moves.items():
            if count > best_count:
                best_count = count
                best_dest = dest

        return best_dest
