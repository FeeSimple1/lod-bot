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
from lod_ai.leaders import leader_location
from lod_ai.economy.resources import can_afford, spend
from lod_ai.map import adjacency as map_adj
from lod_ai.util.naval import has_blockade

# ---------------------------------------------------------------------------
#  Shared geography helpers
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
CITIES: List[str] = [n for n, d in _MAP_DATA.items() if d.get("type") == "City"]
WEST_INDIES = C.WEST_INDIES_ID

def _adjacent(space: str) -> List[str]:
    """Return list of adjacent space IDs (bidirectional)."""
    return list(map_adj.adjacent_spaces(space))


class BritishBot(BaseBot):
    faction = C.BRITISH

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    def _control(self, state: Dict, sid: str):
        return state.get("control", {}).get(sid)

    # -------------------------------------------------------------------
    #  Leader helpers
    # -------------------------------------------------------------------
    def _is_howe(self, state: Dict) -> bool:
        """Howe capability (leader_capabilities.txt):
        "Before executing a British Special Activity, first lower FNI
        by 1 level."  This is a global effect (no "in the space"
        qualifier), so the predicate is simply "is Howe on the map?".

        Previously delegated to _british_leader which returned the
        *first* British leader on the map; when both Gage and Howe were
        present, Gage was found first and Howe's FNI bonus was
        missed."""
        return leader_location(state, "LEADER_HOWE") is not None

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

        sup, opp = self._support_opposition_totals(state)

        # 1. "Opposition > Support, and Event shifts Support/Opposition in
        #     Royalist favor (including by removing a Blockade from a
        #     Support City by reducing FNI, but not by free Battles)?"
        #     The Blockade half needs an actual Blockade on a City at
        #     Support to un-zero (§1.9 pop-0; Session 49 — the static
        #     flag alone fired pre-ToA with no Blockade anywhere).
        if opp > sup:
            if eff["shifts_support_royalist"]:
                return True
            if eff["removes_blockade"]:
                blockaded = (state.get("markers", {})
                             .get(C.BLOCKADE, {}).get("on_map", set()))
                if any(self._support_level(state, sid) > 0
                       for sid in blockaded):
                    return True

        # 2. "Event places British pieces from Unavailable?"
        if eff["places_british_from_unavailable"]:
            # Session 49: the box is keyed by the on-map tags
            # (REGULAR_BRI / TORY) — C.BRIT_UNAVAIL never exists in real
            # states, so this bullet was dead (same class as the French
            # F2 key bug fixed in Session 30).
            unavail = state.get("unavailable", {})
            if (unavail.get(C.REGULAR_BRI, 0) > 0
                    or unavail.get(C.TORY, 0) > 0):
                return True

        # 3. "Event places Tories in Active Opposition with none, a British Fort
        #     in a Colony with none, or British Regulars in a City or Colony?"
        if eff["places_tories"] and state.get("available", {}).get(C.TORY, 0) > 0:
            # S60 (Playbook Example 2): when the card names its placement
            # space(s), bullet 3 tests THOSE spaces — a map-wide scan let
            # card 42 fire off Massachusetts while its Tory could only
            # ever land in (non-Active-Opposition) Connecticut.
            _t_spaces = eff.get("tories_in") or state["spaces"].keys()
            for sid in _t_spaces:
                sp = state["spaces"].get(sid, {})
                if (self._support_level(state, sid) == C.ACTIVE_OPPOSITION
                        and sp.get(C.TORY, 0) == 0):
                    return True
        if eff["places_british_fort"] and state.get("available", {}).get(C.FORT_BRI, 0) > 0:
            for sid in state["spaces"]:
                if (_MAP_DATA.get(sid, {}).get("type") == "Colony"
                        and state["spaces"][sid].get(C.FORT_BRI, 0) == 0):
                    return True
        if eff["places_british_regulars"] and state.get("available", {}).get(C.REGULAR_BRI, 0) > 0:
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
        if directive == "force_if_51":
            # Card 51: "March to set up Battle per the Battle instructions.
            # If not possible, choose Command & Special Activity instead."
            # T13: evaluated with battle.bot_battle_scores — the exact
            # Force-Level + Loss-modifier maths the resolver uses — over a
            # simulated March from all adjacent origins (the old check
            # hand-rolled halved-Militia/halved-WP approximations).
            refresh_control(state)
            return battle.bot_march_sets_up_battle(state, C.BRITISH)

        if directive == "force_if_52":
            # Card 52 ERRATA: "If possible remove French Regulars from spaces
            # where Rebels outnumber present British."
            # Condition: any French Regulars in a space where Rebel pieces
            # outnumber British pieces?
            for sid, sp in state["spaces"].items():
                fre_regs = sp.get(C.REGULAR_FRE, 0)
                if fre_regs == 0:
                    continue
                rebel = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                         + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                         + sp.get(C.FORT_PAT, 0))
                british = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                           + sp.get(C.FORT_BRI, 0))
                if rebel > british:
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
            # Sheet: "Choose a REBEL Faction with pieces in Cities" —
            # Rebellion = Patriots + French (1.5.2). Indians are Royalist
            # and were wrongly listed here (audit Session 28).
            # Session 47: also PRESET the handler keys — without them
            # evt_080 used to default the target to the EXECUTOR and the
            # British removed their own pieces.
            rng = state["rng"]
            rebel_tags = {
                C.PATRIOTS: [C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT],
                C.FRENCH: [C.REGULAR_FRE],
            }
            best_fac, best_key, best_cities = None, None, []
            for faction, tags in rebel_tags.items():
                cities = []
                for city_sid in CITIES:
                    sp = state["spaces"].get(city_sid, {})
                    have = sum(sp.get(tag, 0) for tag in tags)
                    if have > 0:
                        cities.append((-min(have, 2), rng.random(), city_sid))
                if not cities:
                    continue
                key = (-len(cities), rng.random())
                if best_key is None or key < best_key:
                    cities.sort()
                    best_fac, best_key = faction, key
                    best_cities = [sid for *_x, sid in cities]
            if best_fac is None:
                return False
            state["card80_faction"] = best_fac
            state["card80_spaces"] = best_cities[:2]
            return True

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
        self._reset_command_trace(state)
        if self._can_muster(state):
            tried_muster = True
            if self._muster(state, tried_march=tried_march):
                return
            # B8 "If none" → B10 (March)
            self._reset_command_trace(state)
            tried_march = True
            if self._march(state, tried_muster=tried_muster):
                return

        # --- B9 / B12 : BATTLE decision -----------------------------------
        self._reset_command_trace(state)
        if self._can_battle(state):
            if self._battle(state):
                return
            # B12 "If none" → B10 (March)
            self._reset_command_trace(state)
            if not tried_march:
                tried_march = True
                if self._march(state, tried_muster=tried_muster):
                    return

        # --- B10 : MARCH decision -----------------------------------------
        self._reset_command_trace(state)
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
            """§8.4.1 bullet order with the Glossary-strict reading of
            "cubes" (Cube: Regular, Continental or Tory — Militia are NOT
            cubes; only cubes and Forts reach the Casualties boxes,
            §1.4.1):

            bullet 1 "Remove as many Rebellion cubes as possible ...
            removing one British Regular if necessary": 2+ cubes -> option
            2 (the sacrifice IS necessary for the 2nd cube); exactly 1
            cube -> option 1 (option 2 nets no extra CUBE, so the
            sacrifice is unnecessary).
            bullet 2 (no cubes removable): "remove one Rebellion piece" —
            option 1 on an Active Militia, or option 3 (Fort + Regular)
            when no cubes/Active Militia remain (§4.2.2).
            """
            cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            am = sp.get(C.MILITIA_A, 0)
            own_regs = sp.get(C.REGULAR_BRI, 0)
            if cubes >= 2 and own_regs >= 1:
                return 2
            if cubes == 1:
                return 1
            if am >= 1:
                return 1
            if sp.get(C.FORT_PAT, 0) > 0 and own_regs >= 1:
                return 3
            return 1

        def _is_city(sid):
            return _MAP_DATA.get(sid, {}).get("type") == "City"

        # Build prioritized target list per §8.4.1 SKIRMISH:
        #   location tiers: WI first, then exactly-1-Regular spaces, then
        #   the rest ("Skirmish first in the West Indies, then where there
        #   is exactly one British Regular, then per the highest priority
        #   possible in the bullets below");
        #   bullet 1: "Remove as many Rebellion cubes as possible" — rank
        #   by removable cubes DESC (the old sort took fewest-total-rebels
        #   first, bullet 2\'s tiebreak, and so removed 1 piece where 2
        #   cubes were removable elsewhere — Session 55);
        #   bullet 2 (only when no cubes removable anywhere in the tier):
        #   "remove one Rebellion piece, first where there is only one
        #   Rebellion piece in a space, within that first in a City";
        #   remaining ties seeded random (§8.2).
        # §4.2.2: needs "both British Regulars and Rebellion pieces" —
        # incl. in the West Indies (the old code let WI through with 0
        # Regulars).
        all_targets: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid in excluded:
                continue
            reg = sp.get(C.REGULAR_BRI, 0)
            if reg == 0:
                continue  # §4.2.2: British Regulars required (WI too)
            cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            am = sp.get(C.MILITIA_A, 0)
            fort = sp.get(C.FORT_PAT, 0)
            cubes_gettable = 2 if cubes >= 2 else cubes
            enemy = cubes + am + sp.get(C.MILITIA_U, 0) + fort
            if enemy == 0:
                continue
            # A space where nothing can be removed is not a Skirmish
            # target: §4.2.2 options need cubes/Active Militia, or a
            # Patriot Fort with no cubes/Active Militia remaining.
            if cubes_gettable == 0 and am == 0 and not (
                    cubes + am == 0 and fort > 0):
                continue
            # Tier
            if sid == WEST_INDIES:
                tier = 0
            elif reg == 1:
                tier = 1
            else:
                tier = 2
            if cubes_gettable > 0:
                # bullet 1: maximize cubes removed; ties seeded random
                key = (tier, 0, -cubes_gettable, 0, 0,
                       state["rng"].random())
            else:
                # bullet 2: Fort removal — only-one-piece first, then City
                one_piece = 0 if enemy == 1 else 1
                city_bonus = 0 if _is_city(sid) else 1
                key = (tier, 1, 0, one_piece, city_bonus,
                       state["rng"].random())
            all_targets.append((key, sid))

        all_targets.sort()
        for _, sid in all_targets:
            sp = state["spaces"][sid]
            opt = _best_skirmish_option(sid, sp)
            try:
                skirmish.execute(state, C.BRITISH, {}, sid, option=opt)
                # Clinton bonus is handled inside skirmish.execute via the
                # leader_location() check in skirmish.execute().
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
        # Check Gage/Clinton leader requirement for blockade removal.
        # Per B7 reference: "If FNI > 0 and Gage or Clinton is British
        # Leader, remove 1 Blockade..." — we read this as "is on the
        # map as a British leader" since LoD allows multiple British
        # leaders simultaneously.  Previously used _british_leader
        # which returned the *first* leader, missing Clinton when Gage
        # or Howe was also on the map (and vice versa).
        is_gage_clinton = (
            leader_location(state, "LEADER_GAGE") is not None
            or leader_location(state, "LEADER_CLINTON") is not None
        )

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
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                # Priority: Battle space (0 first), most Rebels w/o Fort,
                # most Support — §8.1.1: "most Support" is the value the
                # space contributes to Total Support, i.e. level x Pop
                # (Session 44: was the raw level).
                key = (in_battle, 1 if has_pat_fort else 0, -rebels,
                       -(sup * pop))
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
        """Full multi-phase Garrison per §8.4.1 / B5 reference:

        Phase 1: SA first (Naval Pressure, else Skirmish).
        Phase 2a: From any non-Blockaded origins (§3.2.2; retention rules
                  per §8.4.1), move just enough Regulars to add British
                  Control to Cities.  Priority: most Rebels without
                  Patriot Fort, then NYC, then random.  No moves into
                  skirmished Cities.
        Phase 2b: Reinforce British Control cities (incl. those flipped
                  in 2a): first 1+ Regular if without Active Support,
                  then 3+ British cubes first where Underground Militia.
        Phase 3: If no cubes moved, Muster fallback.
        Phase 4: If cubes moved, Activate Underground Militia and displace
                  Rebels from any qualifying City (dest-only if Limited):
                  most Rebels first; target Province with most Opposition,
                  then least Support, lowest Pop.
        """
        # Phase 1: SA first (skip if limited/no-SA slot)
        limited = state.get("_limited")
        no_sa = state.get("_no_special") or limited
        if not no_sa:
            self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
            # §8.4.1: "First execute Naval Pressure, or if that is not
            # possible, Skirmish." (Was inverted — Session 31.)
            self._naval_then_skirmish(state)
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

        # A planned target City must not simultaneously act as an origin:
        # sending Regulars OUT of a City being flipped double-books its
        # pieces (each target's "needed" is computed on the pre-move
        # tally) and can leave it short of Control after the moves.
        for _city, _n in phase2a_targets:
            origin_avail.pop(_city, None)

        max_dest = 1 if limited else None  # Limited Command: 1 city only
        for city, needed in phase2a_targets:
            if max_dest is not None and len(dest_cities) >= max_dest:
                break
            if needed <= 0:
                continue
            # §8.4.1 "Move just enough Regulars to ADD British Control":
            # a partial move that cannot reach the Control threshold adds
            # nothing — skip the City rather than strand Regulars there.
            avail_total = sum(
                v for o, v in origin_avail.items() if o != city and v > 0)
            if avail_total < needed:
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

        # Phase 2b: Reinforce British Control cities (incl. those being
        # flipped in Phase 2a — pass planned arrivals so control and the
        # 1-Regular/3-cube thresholds reflect the post-move board).
        # (skip if limited — already filled 1 dest from phase 2a)
        if not (max_dest is not None and len(dest_cities) >= max_dest):
            planned_in: Dict[str, int] = {}
            planned_out: Dict[str, int] = {}
            for origin, inner in move_map.items():
                for dst, n in inner.items():
                    planned_in[dst] = planned_in.get(dst, 0) + n
                    planned_out[origin] = planned_out.get(origin, 0) + n
            reinforce_targets = self._garrison_phase2b_targets(
                state, planned_in, planned_out)
            for city, need in reinforce_targets:
                if max_dest is not None and len(dest_cities) >= max_dest:
                    break
                if need <= 0:
                    continue
                # §8.4.1 "to give each ... at least one Regular / at least
                # three British cubes": skip if the threshold can't be met.
                avail_total = sum(
                    v for o, v in origin_avail.items() if o != city and v > 0)
                if avail_total < need:
                    continue
                # Once targeted, this City must not act as an origin.
                origin_avail.pop(city, None)
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

        # Phase 4: Displacement — any qualifying City (§3.2.2), most
        # Rebels first (§8.4.1); Limited Command restricts to the dest.
        displace_city, displace_target = self._select_displacement(
            state, dest_cities, move_map, limited=bool(limited))

        # Affordability check: Garrison costs 2 Resources (§3.2.2);
        # free Commands exempt (bs_free).
        if not can_afford(state, C.BRITISH, 2):
            return self._muster(state, tried_march=False)

        garrison.execute(
            state,
            C.BRITISH,
            {},
            move_map,
            displace_city=displace_city,
            displace_target=displace_target,
        )

        # OPS reference: "Royalist Leaders follow largest group of own
        # units that moves from (or stays in) their spaces."  Same rule
        # as after a March — apply it for Garrison too.
        self._follow_leaders_after_garrison(state, move_map)
        return True

    # -------------------------------------------------------------------
    @staticmethod
    def _rebellion_pieces(sp: Dict) -> int:
        """Rebellion pieces per the §1.7 Control tally (Patriot_ + French_
        tags) — mirrors board.control.refresh_control."""
        return sum(
            q for t, q in sp.items()
            if isinstance(t, str) and isinstance(q, int) and q > 0
            and t.startswith(("Patriot_", "French_"))
        )

    @staticmethod
    def _royalist_pieces(sp: Dict) -> int:
        """Royalist pieces per the §1.7 Control tally (British_ + Indian_
        tags + Villages) — mirrors board.control.refresh_control."""
        total = sum(
            q for t, q in sp.items()
            if isinstance(t, str) and isinstance(q, int) and q > 0
            and t.startswith(("British_", "Indian_"))
        )
        return total + max(0, sp.get(C.VILLAGE, 0))

    def _garrison_origin_pool(self, state: Dict) -> Dict[str, int]:
        """Compute how many Regulars each origin space can contribute to
        Garrison.

        §3.2.2 PROCEDURE: "Move any number of British Regulars from any
        spaces (not Blockaded Cities)" — the origin pool is NOT limited
        to British-Controlled spaces.  §8.4.1 scopes the two retention
        rules differently:
        - "leave two more Royalist than Rebellion pieces in each origin
          space *with British Control*" — controlled origins only;
        - "remove the last Regular only from spaces with Population 0
          or Active Support" — every origin.
        (Previously only British-Controlled origins contributed at all —
        survey British #3 remnant.)
        """
        pool: Dict[str, int] = {}
        for sid, sp in state["spaces"].items():
            regs = sp.get(C.REGULAR_BRI, 0)
            if regs <= 0:
                continue
            if sid == WEST_INDIES:
                continue  # WI is a holding box, not a map space (§1.3)
            if has_blockade(state, sid):
                continue  # §3.2.2: units starting in a Blockaded City excluded
            if self._control(state, sid) == C.BRITISH:
                must_leave = self._rebellion_pieces(sp) + 2
                spare = max(0, self._royalist_pieces(sp) - must_leave)
            else:
                spare = regs
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            at_active_support = self._support_level(state, sid) >= C.ACTIVE_SUPPORT
            min_regs = 0 if (pop == 0 or at_active_support) else 1
            movable = min(spare, max(0, regs - min_regs))
            if movable > 0:
                pool[sid] = movable
        return pool

    def _garrison_phase2a_targets(self, state: Dict) -> List[Tuple[str, int]]:
        """Phase 2a (§8.4.1): "Move just enough Regulars to add British
        Control of Cities, first where there are the most Rebellion
        pieces without a Patriot Fort, then to New York City, then
        random."

        Candidates are all Cities NOT currently under British Control —
        Rebellion-Controlled or Uncontrolled both "add" British Control
        when flipped (previously only Rebellion-Controlled Cities were
        considered — survey British #3 remnant).  Excluded: Blockaded
        Cities (§3.2.2) and Cities where a Skirmish was executed this
        turn (§8.4.1 "Do not move Regulars to any City where a Skirmish
        has been executed").

        Priorities are successive filters per the bot convention:
        Cities without a Patriot Fort ranked by most Rebellion pieces,
        then New York City, then seeded random (§8.2).  A City WITH a
        Patriot Fort can still gain British Control (§3.2.2 places no
        Fort restriction on movement), so forted Cities stay eligible
        in the trailing tiers.

        Returns list of (city, regulars_needed) in priority order.
        `regulars_needed` uses the §1.7 Control tally (Royalist =
        British + Indian pieces + Villages) and requires at least one
        British piece for British Control.
        """
        skirmished = state.get("_turn_skirmished_spaces", set())
        targets: List[Tuple[tuple, str, int]] = []
        for city in CITIES:
            if city not in state["spaces"]:
                continue
            sp = state["spaces"][city]
            if self._control(state, city) == C.BRITISH:
                continue  # nothing to add
            if city in skirmished:
                continue  # §8.4.1 skirmished-City exclusion
            if has_blockade(state, city):
                continue  # §3.2.2
            rebel = self._rebellion_pieces(sp)
            royalist = self._royalist_pieces(sp)
            brit = (
                sp.get(C.REGULAR_BRI, 0)
                + sp.get(C.TORY, 0)
                + sp.get(C.FORT_BRI, 0)
            )
            needed = rebel - royalist + 1
            if brit == 0:
                needed = max(needed, 1)  # §1.7: need a British piece present
            if needed <= 0:
                continue
            has_fort = sp.get(C.FORT_PAT, 0) > 0
            is_nyc = city == "New_York_City"
            # Successive filters: fortless-most-rebels → NYC → random (§8.2)
            key = (
                1 if has_fort else 0,
                -rebel if not has_fort else 0,
                0 if is_nyc else 1,
                state["rng"].random(),
            )
            targets.append((key, city, needed))
        targets.sort()
        return [(city, needed) for _, city, needed in targets]

    def _garrison_phase2b_targets(
        self, state: Dict, incoming: Dict[str, int] | None = None,
        outgoing: Dict[str, int] | None = None,
    ) -> List[Tuple[str, int]]:
        """Phase 2b (§8.4.1): "Then move additional Regulars, first to
        give each British Controlled City without Active Support at
        least one Regular, then to give each British Controlled City at
        least three British cubes of any types beginning with those
        Cities that have Underground Militia."

        `incoming`/`outgoing` carry Regulars already planned in Phase 2a
        so the checks reflect the post-move board: Cities being flipped
        in Phase 2a count as British Controlled here, planned arrivals
        count toward the 1-Regular / 3-cube thresholds, and planned
        departures (a City can be an origin in the same Command) count
        against them.  Excluded:
        Blockaded Cities (§3.2.2) and skirmished Cities (§8.4.1).
        Ties within each priority are seeded random (§8.2; formerly
        alphabetical).

        Returns list of (city, regulars_needed), sorted by priority.
        """
        incoming = incoming or {}
        outgoing = outgoing or {}
        skirmished = state.get("_turn_skirmished_spaces", set())
        rng = state["rng"]
        targets: List[Tuple[tuple, str, int]] = []
        for city in CITIES:
            sp = state["spaces"].get(city, {})
            net = incoming.get(city, 0) - outgoing.get(city, 0)
            # Post-move British Control per the §1.7 tally
            royalist = self._royalist_pieces(sp) + net
            rebel = self._rebellion_pieces(sp)
            brit_present = (
                sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                + sp.get(C.FORT_BRI, 0) + net
            ) > 0
            if not (royalist > rebel and brit_present):
                continue
            if city in skirmished:
                continue  # §8.4.1: no Regulars into a skirmished City
            if has_blockade(state, city):
                continue  # §3.2.2
            regs = sp.get(C.REGULAR_BRI, 0) + net
            at_active_support = self._support_level(state, city) >= C.ACTIVE_SUPPORT
            brit_cubes = regs + sp.get(C.TORY, 0)
            has_underground = sp.get(C.MILITIA_U, 0) > 0

            # First priority: 1+ Regular if without Active Support
            if not at_active_support and regs == 0:
                targets.append(((0, 0, rng.random()), city, 1))
            # Second priority: 3+ cubes first where Underground Militia
            if brit_cubes < 3:
                need = 3 - brit_cubes
                underground_prio = 0 if has_underground else 1
                targets.append(((1, underground_prio, rng.random()), city, need))

        targets.sort()
        return [(city, need) for _, city, need in targets]

    def _select_displacement(
        self, state: Dict, dest_cities: List[str],
        move_map: dict | None = None,
        *, limited: bool = False,
    ) -> Tuple[str | None, str | None]:
        """Phase 4 (§8.4.1): "displace the largest possible number of
        Rebellion pieces, first to a Province with the most Opposition
        then with least Support, within that to the lowest Population
        possible."

        §3.2.2 scopes the candidate Cities: "in one City (under British
        Control, no Patriot Fort and not Blockaded) displace all
        Rebellion units to an adjacent space" — ANY qualifying City,
        whether or not Regulars just moved there (previously only the
        moved-into Cities were considered — survey British #3 remnant).
        Only under a Limited Command must the displacement originate in
        the destination City (§3.2.2/§2.3.5).  Control is evaluated on
        the post-move board (planned arrivals in move_map count).
        Ties are seeded random (§8.2).
        """
        candidates = dest_cities if limited else list(CITIES)
        if not candidates:
            return (None, None)

        net_by_city: Dict[str, int] = {}
        if move_map:
            for origin, inner in move_map.items():
                for dst, n in inner.items():
                    net_by_city[dst] = net_by_city.get(dst, 0) + n
                    net_by_city[origin] = net_by_city.get(origin, 0) - n

        rng = state["rng"]
        best_city = None
        best_city_key = None
        for city in candidates:
            sp = state["spaces"].get(city, {})
            # garrison.execute rejects Patriot-Fort / Blockaded / non-
            # British-Controlled displacement Cities (§3.2.2).
            if sp.get(C.FORT_PAT, 0) > 0:
                continue
            if has_blockade(state, city):
                continue
            rebels = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            if rebels == 0:
                continue
            inc = net_by_city.get(city, 0)
            royalist = self._royalist_pieces(sp) + inc
            rebel_total = self._rebellion_pieces(sp)
            brit_present = (
                sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                + sp.get(C.FORT_BRI, 0) + inc
            ) > 0
            if not (royalist > rebel_total and brit_present):
                continue  # won't be British-Controlled after moves
            key = (-rebels, rng.random())
            if best_city_key is None or key < best_city_key:
                best_city_key = key
                best_city = city

        if not best_city:
            return (None, None)

        # Pick Colony/Province target: must be ADJACENT to the city.
        # Priority: most Opposition, least Support, lowest Pop (§8.4.1);
        # remaining ties seeded random (§8.2).
        adj_spaces = _adjacent(best_city)
        best_province = None
        best_key = None
        for sid in adj_spaces:
            if sid not in state["spaces"]:
                continue
            stype = _MAP_DATA.get(sid, {}).get("type", "")
            if stype not in ("Colony", "Province"):
                continue
            support_level = self._support_level(state, sid)
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            # §8.1.1: "most Opposition"/"least Support" are contribution
            # values (level x Population); "lowest Population" then
            # separates the remaining ties (Session 44: were raw levels).
            opp = max(0, -support_level) * pop
            sup = max(0, support_level) * pop
            # minimize: most opp, least support, lowest pop, seeded tie-break
            key = (-opp, sup, pop, rng.random())
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
        max_spaces = 1 if state.get("_limited") else 4
        # §8.1 "Paying Resource Costs": pay-as-you-select — a Non-player
        # with enough Resources for at least SOME instructions executes
        # them, paying per selected space.  Cap the plan at the purse
        # instead of building a 4-space plan and aborting it wholesale
        # (that abort made the British PASS ~7 turns/game — Session 55).
        # Free Commands (bs_free) are exempt (§5.1.1; Session 51).
        if not state.get("bs_free"):
            max_spaces = min(max_spaces,
                             max(0, state["resources"].get(C.BRITISH, 0)))
        if max_spaces <= 0:
            if not tried_march:
                self._reset_command_trace(state)
                return self._march(state, tried_muster=True)
            return False

        # ----- step 1: choose spaces for Regular placement (sorted) --------
        from lod_ai.commands.muster import _is_legal_regular_dest
        reg_candidates: List[Tuple[tuple, str]] = []
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES:
                continue
            stype = _MAP_DATA.get(sid, {}).get("type", "")
            if stype not in ("City", "Colony"):
                continue
            # Planner must agree with the executor: Regulars may only be
            # placed in a non-Blockaded City, an adjacent Colony, or the
            # West Indies (3.2.1). Divergence here turned into bot_error
            # passes (external audit, defect 2).
            if not _is_legal_regular_dest(state, sid):
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
        # S59 (Playbook Example 3): later Muster steps must see the
        # Regulars this same Command is about to place — the walk-through
        # puts the FIRST Tory pair "where Regulars were just placed" and
        # builds the Fort in that 5+-cube Colony, all within one Muster.
        # (The old planner read only the pre-execution board, so a
        # previously-empty Regulars destination was invisible to the
        # Tory/Fort/RL steps.)
        _planned_regs: Dict[str, int] = {}
        if regular_destinations:
            _planned_regs[regular_destinations[0]] = min(
                6, state["available"].get(C.REGULAR_BRI, 0))

        def _regs_incl_planned(sid: str) -> int:
            return (state["spaces"].get(sid, {}).get(C.REGULAR_BRI, 0)
                    + _planned_regs.get(sid, 0))

        # ----- step 2: Tory placement priorities ---------------------------
        # Up to 2 Tories per space (1 if Passive Opposition).
        # Skip Active Opposition spaces and spaces not adjacent to British power.
        selected_spaces = set(regular_destinations)
        tory_plan: Dict[str, int] = {}

        def _tory_eligible(sid: str) -> bool:
            """Check if a space is eligible for Tory placement."""
            if sid == WEST_INDIES:
                return False
            # §3.2.1: Tories may be placed only in Cities or Colonies.
            if _MAP_DATA.get(sid, {}).get("type") not in ("City", "Colony"):
                return False
            sup = self._support_level(state, sid)
            if sup <= C.ACTIVE_OPPOSITION:
                return False  # Skip Active Opposition
            # Adjacency to British power check
            sp = state["spaces"].get(sid, {})
            if _regs_incl_planned(sid) > 0 or sp.get(C.FORT_BRI, 0) > 0:
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
            # §8.4.2: "first where Regulars are the only British CUBES"
            # — a British Fort is not a cube (Glossary) and does NOT
            # disqualify; Playbook Example 3 places the second pair in
            # New York City (6 Regulars + a Fort, no Tories) (S59).
            if _regs_incl_planned(sid) > 0 and sp.get(C.TORY, 0) == 0:
                just_placed = 0 if sid in selected_spaces else 1
                tory_p1.append(((just_placed,), sid))
        tory_p1.sort()
        for _, sid in tory_p1:
            if avail_tories <= 0 or len(set(tory_plan) | selected_spaces) >= max_spaces:  # S59: union — the Regular space may also hold a Tory pair (Playbook Ex3: 4 distinct spaces)
                break
            n = min(_tory_max(sid), avail_tories)
            tory_plan[sid] = n
            avail_tories -= n

        # Priority 2 (8.4.2): "then to change Control of the most
        # Population" — only spaces where the placed Tories actually
        # change Control (1.7 simulation), ranked by Population, seeded-
        # random ties (8.2). The old sort took the LARGEST rebel-minus-
        # British deficit — the spaces least likely to flip — and ignored
        # Population entirely (Session 37).
        if avail_tories > 0:
            refresh_control(state)
            tory_p2: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in tory_plan or not _tory_eligible(sid):
                    continue
                n = min(_tory_max(sid), avail_tories)
                if n <= 0:
                    continue
                royalist = (_regs_incl_planned(sid) + sp.get(C.TORY, 0)
                            + sp.get(C.FORT_BRI, 0) + sp.get(C.WARPARTY_A, 0)
                            + sp.get(C.WARPARTY_U, 0) + sp.get(C.VILLAGE, 0))
                rebel_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                                + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                                + sp.get(C.FORT_PAT, 0))
                before = state.get("control", {}).get(sid)
                # After adding n Tories (British pieces, so presence holds):
                if royalist + n > rebel_pieces:
                    after = C.BRITISH
                elif rebel_pieces > royalist + n:
                    after = "REBELLION"
                else:
                    after = None
                if after == before:
                    continue        # placement would not change Control
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                tory_p2.append(((-pop, state["rng"].random()), sid))
            tory_p2.sort()
            for _, sid in tory_p2:
                if avail_tories <= 0 or len(set(tory_plan) | selected_spaces) >= max_spaces:  # S59: union — the Regular space may also hold a Tory pair (Playbook Ex3: 4 distinct spaces)
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
                        and (_regs_incl_planned(sid) + sp.get(C.TORY, 0)) < 5):
                    pop = _MAP_DATA.get(sid, {}).get("population", 0)
                    tory_p3.append((-pop, sid))
            tory_p3.sort()
            for _, sid in tory_p3:
                if avail_tories <= 0 or len(set(tory_plan) | selected_spaces) >= max_spaces:  # S59: union — the Regular space may also hold a Tory pair (Playbook Ex3: 4 distinct spaces)
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

        total_support, total_opp = self._support_opposition_totals(state)
        if total_opp > total_support + die or state["available"].get(C.FORT_BRI, 0) == 0:
            # Reward Loyalty
            raid_on_map = state.get("markers", {}).get(C.RAID, {}).get("on_map", set())
            prop_on_map = state.get("markers", {}).get(C.PROPAGANDA, {}).get("on_map", set())

            def _rl_key(n):
                # §8.4.5: "first select the space or spaces with the
                # lowest total of Raid and Propaganda markers, within
                # that where the largest change in (Support - Opposition)
                # is possible."  The change in the TOTAL score is shift
                # levels x Population (§8.1.1), and "possible" caps the
                # levels at what the purse can pay after the markers
                # (Session 44: was raw levels, uncapped, no §8.2 tie).
                markers = ((1 if n in raid_on_map else 0)
                           + (1 if n in prop_on_map else 0))
                already = 0 if n in all_selected else 1
                max_shift = C.ACTIVE_SUPPORT - self._support_level(state, n)
                muster_count = len(all_selected) + already
                budget = (state["resources"].get(C.BRITISH, 0)
                          - muster_count - markers)
                if leader_location(state, "LEADER_GAGE") == n:
                    budget += 1  # Gage discount (leader_capabilities)
                affordable = min(max_shift, max(0, budget))
                pop = _MAP_DATA.get(n, {}).get("population", 0)
                return (already, markers, -(affordable * pop),
                        state["rng"].random())

            rl_candidates = [
                sid for sid, sp in state["spaces"].items()
                if self._support_level(state, sid) < C.ACTIVE_SUPPORT
                and self._control(state, sid) == C.BRITISH
                and _regs_incl_planned(sid) >= 1
                and (sp.get(C.TORY, 0) + tory_plan.get(sid, 0)) >= 1
            ]
            # §8.4.5: "Do not Reward Loyalty in a space if only Raid
            # and/or Propaganda markers would be removed" — a candidate
            # whose affordable shift is zero levels is not eligible.
            rl_candidates = [
                s for s in rl_candidates if _rl_key(s)[2] < 0
            ]
            # §3.2 / §3.2.1: Muster (Limited Command) affects only 1 space.
            # When we've already filled the per-Muster space cap, the
            # Reward-Loyalty step must reuse an already-selected space per
            # the B8 flowchart ("in 1 space, first one already selected
            # above").  Filter out any RL candidate that would push us
            # over max_spaces.
            if len(all_selected) >= max_spaces:
                rl_candidates = [s for s in rl_candidates if s in all_selected]
            if rl_candidates:
                best_rl = min(rl_candidates, key=_rl_key)
                # §3.2.1: "There is no limit to the number of levels shifted
                # when Rewarding Loyalty during Muster."
                # Calculate maximum affordable shift levels for the best space.
                _sp_rl = state["spaces"].get(best_rl, {})
                _rl_markers = sum(
                    1 for m in (raid_on_map, prop_on_map) if best_rl in m
                )
                _current_sup = self._support_level(state, best_rl)
                _max_shift = C.ACTIVE_SUPPORT - _current_sup  # levels to reach Active Support
                _rl_gage = 1 if leader_location(state, "LEADER_GAGE") == best_rl else 0
                # Muster cost: 1 per selected space (RL space may add 1 more)
                _muster_count = len(all_selected) + (0 if best_rl in all_selected else 1)
                # RL cost = markers + shift_levels - gage_discount
                # Available for RL = total resources - muster space cost
                _avail_for_rl = state["resources"].get(C.BRITISH, 0) - _muster_count
                # Affordable shifts: avail_for_rl >= markers + shifts - gage
                # => shifts <= avail_for_rl - markers + gage
                _affordable_shifts = max(0, _avail_for_rl - _rl_markers + _rl_gage)
                _rl_shift = min(_max_shift, _affordable_shifts)
                if _rl_shift > 0:
                    _rl_cost = _rl_markers + _rl_shift - _rl_gage
                    _total_cost = _muster_count + max(0, _rl_cost)
                    if state["resources"].get(C.BRITISH, 0) >= _total_cost:
                        chosen_rl_space = best_rl
                        reward_levels = _rl_shift

        if chosen_rl_space is None and state["available"].get(C.FORT_BRI, 0):
            fort_targets = [
                sid
                for sid, sp in state["spaces"].items()
                if _MAP_DATA.get(sid, {}).get("type") == "Colony"
                and sp.get(C.FORT_BRI, 0) == 0
                and (sp.get(C.FORT_PAT, 0) + sp.get(C.VILLAGE, 0) + sp.get(C.FORT_BRI, 0)) < 2
                and (_regs_incl_planned(sid) + sp.get(C.TORY, 0)
                     + tory_plan.get(sid, 0)) >= 5
            ]
            # See note above on B8 "first one already selected above".  When
            # at the per-Muster space cap, restrict to already-selected
            # spaces so we don't violate the Limited Command 1-space rule.
            if len(all_selected) >= max_spaces:
                fort_targets = [s for s in fort_targets if s in all_selected]
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
            # 3.2.1 "place up to six Regulars"; 8.4.2 "as many as possible"
            # (was capped at 4 — Session 37).
            {"space": regular_destinations[0], "n": min(6, state["available"].get(C.REGULAR_BRI, 0))}
            if state["available"].get(C.REGULAR_BRI, 0) > 0 and regular_destinations
            else None
        )

        if not reg_plan and not tory_plan and not reward_levels and not fort_space:
            if not tried_march:
                self._reset_command_trace(state)
                return self._march(state, tried_muster=True)
            return False

        # A Tory-only / RL-only / Fort-only Muster passes regular_plan=None
        # (muster.execute's documented contract). Fabricating a zero-count
        # plan pointed the executor's §3.2.1 Regular-destination check at an
        # arbitrary selected space (e.g. a Tory space) and raised.

        if not all_muster_spaces:
            if not tried_march:
                self._reset_command_trace(state)
                return self._march(state, tried_muster=True)
            return False

        # Affordability check: Muster costs 1 per selected space
        muster_cost = len(all_muster_spaces)
        if state["resources"].get(C.BRITISH, 0) < muster_cost:
            if not tried_march:
                self._reset_command_trace(state)
                return self._march(state, tried_muster=True)
            return False

        # B39 Gage capability (leader_capabilities.txt):
        # "First Loyalty shift: Reward Loyalty is free in the space."
        # Gage must be IN the chosen RL space for the discount to apply
        # (was previously a global "is Gage the British leader?" check
        # which gave a discount even when Gage was elsewhere on the map).
        rl_free_first = (
            chosen_rl_space is not None
            and leader_location(state, "LEADER_GAGE") == chosen_rl_space
            and reward_levels > 0
        )

        muster.execute(
            state,
            C.BRITISH,
            {},
            all_muster_spaces,
            regular_plan=reg_plan,
            tory_plan=tory_plan,
            reward_levels=reward_levels,
            build_fort=bool(fort_space),
            # Step-3 target: the Fort space, or the B8-chosen Reward-Loyalty
            # space. (Previously chosen_rl_space was never passed, so the
            # executor silently applied/skipped RL at the Regular
            # destination instead of the space the flowchart selected.)
            fort_space=fort_space or chosen_rl_space,
            rl_free_first=rl_free_first,
        )

        # Execute SA (skip if already done during Garrison fallback, or limited/no-SA slot)
        if (not state.get("_sa_done_this_turn")
                and not state.get("_limited")
                and not state.get("_no_special")):
            self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
            # §8.4.2: "also Skirmish (8.4.1) or, if that is not possible,
            # Naval Pressure (8.4.1)" — the (8.4.1) cites the SA
            # DESCRIPTIONS, not Garrison's NP-first order; the flowchart
            # B8 edge points to B11/Skirmish.  Session 31 had applied
            # Garrison's order here (Session 54).
            self._skirmish_then_naval(state)
        return True

    # =======================================================================
    #  NODE B10 :  MARCH Command
    # =======================================================================
    def _march(self, state: Dict, *, tried_muster: bool = False) -> bool:
        """Implements node B10 (Max 4).

        §8.4.3 bullets (Manual wording governs; flowchart B10 agrees —
        its "Pop 1+" equals the Manual's "Population one or two" on this
        map, where no space exceeds Population 2):
        • Lose no British Control. Leave last Tory and War Party in each
          space, and last Regular if British Control but no Active Support.
        • Moving the largest groups first, add British Control to Cities,
          then Colonies (not Indian Reserves), up to 2 spaces total;
          within each first where there ARE Rebellion cubes, then highest
          Population. Stop moving groups into a destination once British
          Control is established. Use Common Cause to include War Parties
          (Active first) when the destination is an adjacent Province.
        • Then March to Population 1-2 spaces not at Active Support,
          first to add Tories where Regulars are the only British units,
          then to add Regulars where Tories are the only British units;
          within each, move first to March destinations already selected.
        • Then March in place to Activate Underground Militia, first in
          spaces with Support (§3.2.3: one Militia per three British cubes).
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

        # Track committed pieces per origin across all moves in this plan
        _committed: Dict[str, Dict[str, int]] = {}

        def _movable_from(sid: str) -> Dict[str, int]:
            """Compute how many pieces of each type can leave *sid*.

            Rules: lose no British Control. Leave last Tory and War Party.
            Leave last Regular if British Control but no Active Support.
            Accounts for pieces already committed to earlier moves.
            """
            sp = state["spaces"][sid]
            already = _committed.get(sid, {})
            regs = sp.get(C.REGULAR_BRI, 0) - already.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0) - already.get(C.TORY, 0)
            wp_a = sp.get(C.WARPARTY_A, 0)
            wp_u = sp.get(C.WARPARTY_U, 0)
            # §1.7 Control tally (Villages count as Royalist), minus ALL
            # pieces already committed out of this space in this plan
            # (incl. Common-Cause War Parties).
            royalist = self._royalist_pieces(sp) - sum(already.values())
            rebel = self._rebellion_pieces(sp)
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
        # §8.4.3: "Moving the largest groups first, add British Control to
        # Cities, then Colonies (but not Indian Reserve Provinces), for a
        # total of up to two spaces; within each first where there are
        # Rebellion cubes, then with the highest Population. Stop moving
        # groups into each destination space once British Control is
        # established. Use Common Cause to include War Parties (Active
        # first) if this would increase the size of a Marching group
        # moving into an adjacent Province."
        #
        # Multiple groups may feed one destination until Control is
        # established; a destination that cannot reach British Control
        # with the groups available is skipped (a partial move adds
        # nothing).  Rebellion-cube priority is PRESENCE (binary per the
        # rule text) then highest Population then seeded random (§8.2);
        # the old sort used most-cubes, a different cascade.
        march_max = 1 if state.get("_limited") else 4
        no_sa_plan = state.get("_limited") or state.get("_no_special")
        move_plan: List[Dict] = []
        cc_spaces: Dict[str, int] = {}  # B13: CC War Parties used per origin
        seen_dst: set = set()
        spaces_used = 0

        cand_best: Dict[str, tuple] = {}
        for sid in origins:
            for dst in _adjacent(sid):
                if dst in cand_best or dst not in state.get("spaces", {}):
                    continue
                if self._control(state, dst) == C.BRITISH:
                    continue
                dtype = _MAP_DATA.get(dst, {}).get("type", "")
                if dtype not in ("City", "Colony"):
                    continue  # "(but not Indian Reserve Provinces)"
                dsp = state["spaces"][dst]
                rebel_cubes = (dsp.get(C.REGULAR_PAT, 0)
                               + dsp.get(C.REGULAR_FRE, 0)
                               + dsp.get(C.MILITIA_A, 0)
                               + dsp.get(C.MILITIA_U, 0))
                pop = _MAP_DATA.get(dst, {}).get("population", 0)
                cand_best[dst] = (
                    0 if dtype == "City" else 1,
                    0 if rebel_cubes > 0 else 1,
                    -pop,
                    state["rng"].random(),
                )
        control_targets = sorted(cand_best, key=cand_best.get)

        for dst in control_targets:
            if spaces_used >= min(2, march_max):
                break
            dsp = state["spaces"][dst]
            out_committed = sum(_committed.get(dst, {}).values())
            needed = (self._rebellion_pieces(dsp)
                      - (self._royalist_pieces(dsp) - out_committed) + 1)
            brit_dst = (dsp.get(C.REGULAR_BRI, 0) + dsp.get(C.TORY, 0)
                        + dsp.get(C.FORT_BRI, 0))
            if brit_dst == 0:
                needed = max(needed, 1)  # §1.7: Control needs a British piece
            dst_is_colony = _MAP_DATA.get(dst, {}).get("type") == "Colony"
            got = 0
            tentative: List[Dict] = []
            tentative_cc: Dict[str, int] = {}
            # "Moving the largest groups first"
            adj_origins = [o for o in origins
                           if o != dst and o not in seen_dst
                           and dst in _adjacent(o)]
            adj_origins.sort(key=lambda o: -sum(_movable_from(o).values()))
            for origin in adj_origins:
                if got >= needed:
                    break
                movable = _movable_from(origin)
                reg_count = movable.get(C.REGULAR_BRI, 0)
                # §3.2.3: Tories accompany Regulars 1 for 1; the executor
                # caps Tories + CC War Parties together at the Regular count.
                tory_count = min(movable.get(C.TORY, 0), reg_count)
                cc_wp = 0
                if dst_is_colony and not no_sa_plan:
                    # §8.4.3 COMMON CAUSE: "make up the difference between
                    # the number of Regulars and Tories in the group" —
                    # GROUP counts, not space totals.  (The old code added
                    # the space's Tories on top of the group's movable
                    # Tories, understating the difference so CC War
                    # Parties almost never joined a March.)
                    osp = state["spaces"][origin]
                    avail_wp = max(0, osp.get(C.WARPARTY_A, 0)
                                   + osp.get(C.WARPARTY_U, 0) - 1)
                    avail_wp = max(0, avail_wp
                                   - tentative_cc.get(origin, 0)
                                   - cc_spaces.get(origin, 0))
                    cc_wp = min(avail_wp, max(0, reg_count - tory_count))
                if reg_count + tory_count + cc_wp <= 0:
                    continue
                pieces: Dict[str, int] = {}
                if reg_count:
                    pieces[C.REGULAR_BRI] = reg_count
                if tory_count:
                    pieces[C.TORY] = tory_count
                if cc_wp:
                    # CC War Parties MARCH with the group and arrive
                    # Active (§4.2.1).  common_cause.execute only readies
                    # them in the origin (Active first); march.execute
                    # moves them when they are in the plan's pieces — the
                    # old plan left them out, so the "group size" they
                    # added was phantom and the destination never
                    # received them.
                    pieces[C.WARPARTY_A] = cc_wp
                    tentative_cc[origin] = tentative_cc.get(origin, 0) + cc_wp
                tentative.append({"src": origin, "dst": dst, "pieces": pieces})
                oc = _committed.setdefault(origin, {})
                for tag, cnt in pieces.items():
                    oc[tag] = oc.get(tag, 0) + cnt
                got += reg_count + tory_count + cc_wp
            if tentative and got >= needed:
                move_plan.extend(tentative)
                for o, n in tentative_cc.items():
                    cc_spaces[o] = cc_spaces.get(o, 0) + n
                seen_dst.add(dst)
                spaces_used += 1
            else:
                # Control unreachable — roll the tentative commitments back.
                for mv in tentative:
                    oc = _committed.get(mv["src"], {})
                    for tag, cnt in mv["pieces"].items():
                        oc[tag] = oc.get(tag, 0) - cnt

        # === Phase 2: Population 1-2 spaces not at Active Support ===
        # §8.4.3: "Then March to spaces with Population one or two that
        # are not at Active Support, first to add Tories where Regulars
        # are the only British units, then to add Regulars where Tories
        # are the only British units; within each, move first to March
        # destinations already selected above."
        #
        # ONLY those two destination profiles qualify — the old tier-2
        # was a catch-all admitting every Pop 1+ space.  Already-selected
        # destinations are PREFERRED within each tier (the old code
        # excluded them outright), and re-using one consumes no new
        # destination slot (§3.2.3 pays per destination space selected).
        if spaces_used < march_max or seen_dst:
            planned_in: Dict[str, Dict[str, int]] = {}
            for mv in move_plan:
                d = planned_in.setdefault(mv["dst"], {})
                for tag, cnt in mv["pieces"].items():
                    d[tag] = d.get(tag, 0) + cnt

            phase2_targets: List[Tuple[tuple, str]] = []
            p2_seen: set = set()
            for sid in origins:
                if sid in seen_dst:
                    continue  # planned destinations do not act as origins
                for dst in _adjacent(sid):
                    if dst in p2_seen or dst not in state.get("spaces", {}):
                        continue
                    pop = _MAP_DATA.get(dst, {}).get("population", 0)
                    if not (1 <= pop <= 2):
                        continue  # "Population one or two"
                    if self._support_level(state, dst) >= C.ACTIVE_SUPPORT:
                        continue
                    dsp = state["spaces"][dst]
                    inc = planned_in.get(dst, {})
                    regs_d = dsp.get(C.REGULAR_BRI, 0) + inc.get(C.REGULAR_BRI, 0)
                    tories_d = dsp.get(C.TORY, 0) + inc.get(C.TORY, 0)
                    forts_d = dsp.get(C.FORT_BRI, 0)
                    regs_only = regs_d > 0 and tories_d == 0 and forts_d == 0
                    tories_only = tories_d > 0 and regs_d == 0 and forts_d == 0
                    if not (regs_only or tories_only):
                        continue
                    tier = 0 if regs_only else 1
                    already = 0 if dst in seen_dst else 1
                    phase2_targets.append(
                        ((tier, already, state["rng"].random()), dst))
                    p2_seen.add(dst)
            phase2_targets.sort()
            for key, dst in phase2_targets:
                if dst not in seen_dst and spaces_used >= march_max:
                    continue  # a re-used destination needs no new slot
                tier = key[0]
                adj_origins = [o for o in origins
                               if o != dst and o not in seen_dst
                               and dst in _adjacent(o)]
                adj_origins.sort(key=lambda o: -sum(_movable_from(o).values()))
                for origin in adj_origins:
                    movable = _movable_from(origin)
                    reg_count = movable.get(C.REGULAR_BRI, 0)
                    if reg_count <= 0:
                        continue  # §3.2.3: Tories cannot march unescorted
                    tory_count = min(movable.get(C.TORY, 0), reg_count)
                    if tier == 0 and tory_count <= 0:
                        continue  # must actually ADD Tories
                    pieces = {C.REGULAR_BRI: reg_count}
                    if tory_count:
                        pieces[C.TORY] = tory_count
                    move_plan.append({"src": origin, "dst": dst,
                                      "pieces": pieces})
                    oc = _committed.setdefault(origin, {})
                    for tag, cnt in pieces.items():
                        oc[tag] = oc.get(tag, 0) + cnt
                    if dst not in seen_dst:
                        seen_dst.add(dst)
                        spaces_used += 1
                    break

        # === Phase 3: March in place to Activate Militia, first in Support ===
        # "March in place" activates Underground Militia where British are present.
        # These are handled separately since the march command requires actual moves.
        activate_in_place: List[str] = []
        if spaces_used < march_max:
            activate_targets: List[Tuple[tuple, str]] = []
            for sid, sp in state["spaces"].items():
                if sid in seen_dst:
                    continue
                # §3.2.3 PROCEDURE: destinations "Activate one Militia for
                # every three British cubes there" — an in-place space with
                # fewer than 3 British cubes activates nothing, so paying a
                # Resource to select it would be a dead move.
                brit_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                # §3.2.3: "Activate one Militia for every three British
                # cubes there" — cubes, not Regulars specifically; a
                # Tory-only stack of 3+ activates too (S55, B-node
                # inventory).
                if sp.get(C.MILITIA_U, 0) > 0 and brit_cubes >= 3:
                    sup = self._support_level(state, sid)
                    # "first in spaces with Support" (binary presence),
                    # remaining ties seeded random (§8.2)
                    activate_targets.append(
                        ((0 if sup > 0 else 1, state["rng"].random()), sid))
            activate_targets.sort()
            for _, sid in activate_targets:
                if spaces_used >= march_max:
                    break
                activate_in_place.append(sid)
                seen_dst.add(sid)
                spaces_used += 1

        if not move_plan and not activate_in_place:
            if not tried_muster:
                self._reset_command_trace(state)
                return self._muster(state, tried_march=True)
            return False

        # §8.1 "Paying Resource Costs": pay-as-you-select — trim the plan
        # to the purse, keeping the highest-priority destinations (plan
        # append order == §8.4.3 priority order), instead of aborting the
        # whole March when 4 destinations exceed the purse (Session 55).
        # Free Commands (bs_free) are exempt.  In-place activations are
        # budgeted individually after execution (existing can_afford loop).
        if not state.get("bs_free"):
            budget = max(0, state["resources"].get(C.BRITISH, 0))
            dst_order: List[str] = []
            for mv in move_plan:
                if mv["dst"] not in dst_order:
                    dst_order.append(mv["dst"])
            if len(dst_order) > budget:
                keep = set(dst_order[:budget])
                dropped = [mv for mv in move_plan if mv["dst"] not in keep]
                move_plan = [mv for mv in move_plan if mv["dst"] in keep]
                # Un-plan CC War Parties whose groups no longer March so
                # common_cause doesn't Activate them for nothing (§4.2.1).
                for mv in dropped:
                    n = mv["pieces"].get(C.WARPARTY_A, 0)
                    if n and mv["src"] in cc_spaces:
                        cc_spaces[mv["src"]] -= n
                        if cc_spaces[mv["src"]] <= 0:
                            del cc_spaces[mv["src"]]
                if not move_plan and not activate_in_place:
                    if not tried_muster:
                        self._reset_command_trace(state)
                        return self._muster(state, tried_march=True)
                    return False

        # B10+B13: Execute Common Cause BEFORE the March so that WP from CC
        # contribute to group sizes for adjacent Province destinations.
        # (Skip CC and all SAs if in a limited/no-SA slot.)
        no_sa = state.get("_limited") or state.get("_no_special")
        used_cc = False
        march_ctx = {}
        if cc_spaces and not no_sa:
            try:
                cc_ctx = common_cause.execute(
                    state, C.BRITISH, {}, list(cc_spaces.keys()),
                    mode="MARCH", wp_counts=cc_spaces, preserve_wp=True,
                )
                march_ctx = cc_ctx
                used_cc = True
            except (ValueError, KeyError):
                # CC failed — the planned CC War Parties cannot march.
                # Strip them from the plan (and drop entries left empty)
                # so march.execute doesn't try to move unreadied pieces.
                for mv in move_plan:
                    mv["pieces"].pop(C.WARPARTY_A, None)
                move_plan = [mv for mv in move_plan
                             if sum(mv["pieces"].values()) > 0]

        # Execute the March (Max 4 spaces) for actual moves
        if move_plan:
            all_srcs = list({p["src"] for p in move_plan})
            all_dsts = list({p["dst"] for p in move_plan})
            # Resource affordability: march costs 1 per destination.
            # Destination COUNT is capped (≤4) during planning; the plan
            # may hold more than 4 entries when several groups feed one
            # destination, so never slice the entry list.
            march_cost = len(set(p["dst"] for p in move_plan))
            if not can_afford(state, C.BRITISH, march_cost):
                if not tried_muster:
                    self._reset_command_trace(state)
                    return self._muster(state, tried_march=True)
                return False
            # Set bring_escorts=True when any move includes Tories or
            # Common-Cause War Parties, which require Regular escorts.
            needs_escorts = any(
                p["pieces"].get(C.TORY, 0) > 0
                or p["pieces"].get(C.WARPARTY_U, 0) > 0
                or p["pieces"].get(C.WARPARTY_A, 0) > 0
                for p in move_plan
            )
            march.execute(
                state,
                C.BRITISH,
                march_ctx,
                all_srcs,
                all_dsts,
                plan=move_plan,
                bring_escorts=needs_escorts,
                limited=False,
            )

            # OPS reference: "Royalist Leaders follow largest group of
            # own units that moves from (or stays in) their spaces."
            # For each British leader on the map, build the per-leader
            # spaces_with_moves dict (destinations reached from that
            # leader's space + counts of British units that moved
            # there) and let bot_leader_movement decide where they
            # belong post-march.  Skip if no plan or no British leaders.
            self._follow_leaders_after_march(state, move_plan)

            # OPS: a Common-Cause March moves War Parties (as Tory-equivalents)
            # out of their spaces, so any Indian Leader there must follow the
            # largest group too -- not just the British leaders. Mirrors the
            # Indian bot's own post-move leader-follow.
            if used_cc:
                from lod_ai.bots.indians import follow_indian_leaders_after_move
                follow_indian_leaders_after_move(state)

        # Activate Underground Militia in march-in-place spaces.
        # §3.2.3: "Pay one Resource per destination space selected" —
        # march-in-place destinations are selected destinations and
        # cost 1 Resource each.  The march.execute() call above only
        # paid for spaces in move_plan, so charge the in-place spaces
        # here.  Also mark them as a MARCH command so the engine's
        # _is_action_legal() check sees the turn produced effects;
        # otherwise a turn that does only march-in-place + SA fails
        # with illegal_reason='no_affected_spaces'.
        if activate_in_place:
            from lod_ai.board.pieces import flip_pieces
            affordable_in_place: List[str] = []
            for sid in activate_in_place:
                if can_afford(state, C.BRITISH, 1):
                    spend(state, C.BRITISH, 1)
                    affordable_in_place.append(sid)
                else:
                    break
            if affordable_in_place:
                state["_turn_command"] = "MARCH"
                state.setdefault("_turn_affected_spaces", set()).update(
                    affordable_in_place
                )
                for sid in affordable_in_place:
                    sp = state["spaces"][sid]
                    brit_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                    # §3.2.3: Activate ONE Militia per THREE British cubes
                    # (the old code flipped every Underground Militia).
                    mu = min(sp.get(C.MILITIA_U, 0), brit_cubes // 3)
                    if mu > 0:
                        flip_pieces(state, C.MILITIA_U, C.MILITIA_A, sid, mu)
                        push_history(
                            state,
                            f"BRITISH March in place: Activate {mu} "
                            f"Militia in {sid}"
                        )

        # B10 reference: "If no Common Cause used, execute a Special
        # Activity."  Per the flowchart there is no second post-March
        # Common-Cause attempt — if CC wasn't used during planning,
        # the bot proceeds directly to Skirmish/Naval Pressure.
        # Skip all SAs in limited/no-SA slot.
        if not used_cc and not no_sa:
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
        # B12: "Use Common Cause to increase British Force Level." Common
        # Cause is a Special Activity, so it is only available outside a
        # Limited / no-SA slot; otherwise the selection sees no CC boost.
        sel_cc_available = not (state.get("_limited") or state.get("_no_special"))

        for sid, sp in state["spaces"].items():
            # B12: "spaces with Rebel Forts and/or Rebel cubes"
            rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            total_militia = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
            rebel_forts = sp.get(C.FORT_PAT, 0)
            if rebel_cubes + total_militia + rebel_forts == 0:
                continue

            # B12 "Royalist Force Level + modifiers exceeds Rebel Force
            # Level + modifiers": use the resolver's exact Force Level
            # (§3.6.2-3.6.3) and Loss-Level modifiers (§3.6.5-3.6.6) via the
            # shared helper, so the bot's prediction matches what the Battle
            # actually resolves (no more hand-rolled approximation that could
            # over- or under-count modifiers and trigger losing attacks).
            cc_wp = self._cc_battle_wp(sp) if sel_cc_available else 0
            att_score, def_score = battle.bot_battle_scores(
                state, sid, "ROYALIST", cc_wp=cc_wp)
            if att_score > def_score:
                british_count = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                targets.append((-british_count, sid))

        if not targets:
            return False

        targets.sort()
        chosen = [sid for _, sid in targets]

        # Limited Command: cap to 1 space
        if state.get("_limited"):
            chosen = chosen[:1]

        # Affordability check: Battle costs 1 per space
        brit_res = state["resources"].get(C.BRITISH, 0)
        if brit_res < len(chosen):
            chosen = chosen[:max(brit_res, 0)]
        if not chosen:
            return False

        # SA chain (skip in limited/no-SA slot)
        no_sa = state.get("_limited") or state.get("_no_special")
        # §4.2.2 / §8.4.4: Skirmish may not take place "in a Battle ...
        # space" / must be "in a space not selected for Battle".  The SA
        # chain runs BEFORE battle.execute registers the chosen spaces in
        # _turn_affected_spaces, so register them here first (Session 55).
        state.setdefault("_turn_affected_spaces", set()).update(chosen)
        cc_ctx = {}
        if not no_sa:
            # Common Cause before the battles -- only in the spaces actually
            # being battled (§4.2.1 "during the same ... Battle").
            used_cc = self._try_common_cause(state, spaces=chosen)
            if used_cc:
                cc_ctx = used_cc  # ctx with {"common_cause": {sid: n}}

            # If no Common Cause, execute Skirmish/Naval loop first
            if not used_cc:
                self._apply_howe_fni(state)  # B38 Howe lowers FNI before SA
                self._skirmish_then_naval(state)

        # S55: hand the CC ctx to the resolver so the utilized War
        # Parties count "as if they were Tories" (§4.2.1) in the actual
        # Force Level, not just in the B12 selection score.
        battle.execute(state, C.BRITISH, cc_ctx, chosen)
        return True

    # -------------------------------------------------------------------
    @staticmethod
    def _cc_battle_wp(sp: Dict) -> int:
        """B13 (§4.2.1): War Parties this space commits as Tory-equivalents in
        a Battle. "If British Regulars > Tories, use War Parties (Active first)
        as Tories up to the number of Regulars ... do NOT use the last
        Underground War Party." So the count is capped at Regulars - Tories
        (extra Tory-equivalents are wasted, §3.6.3 caps Tories at Regulars)
        and by the usable pool (all Active plus all but one Underground)."""
        regs = sp.get(C.REGULAR_BRI, 0)
        tories = sp.get(C.TORY, 0)
        if regs <= tories:
            return 0
        active = sp.get(C.WARPARTY_A, 0)
        ug = sp.get(C.WARPARTY_U, 0)
        usable = active + max(0, ug - 1)   # keep the last Underground WP
        return max(0, min(regs - tories, usable))

    # -------------------------------------------------------------------
    def _try_common_cause(self, state: Dict, *, mode: str = "BATTLE",
                          spaces: List[str] | None = None) -> bool:
        """B13: Common Cause — use War Parties (Active first) as Tories
        where British Regulars > Tories, up to the number of Regulars.

        Reference constraints:
        - §4.2.1: Common Cause applies "during the same March or Battle," so
          when *spaces* is given (the spaces actually being battled) it is
          restricted to those, rather than loaning War Parties in unrelated
          spaces where it would only expose them for no benefit.
        - If Marching into adjacent Province, do NOT use last War Party
          (if possible Underground) in origin space.
        - If Battle, do NOT use last Underground War Party.
        - If not possible, Skirmish.

        Return True if Common Cause executed successfully.
        """
        # Find spaces where British Regulars > Tories and War Parties exist.
        restrict = set(spaces) if spaces is not None else None
        spaces = []
        wp_counts: Dict[str, int] = {}
        for sid, sp in state["spaces"].items():
            if restrict is not None and sid not in restrict:
                continue
            regs = sp.get(C.REGULAR_BRI, 0)
            tories = sp.get(C.TORY, 0)
            wp_a = sp.get(C.WARPARTY_A, 0)
            wp_u = sp.get(C.WARPARTY_U, 0)
            if regs > tories and (wp_a + wp_u) > 0:
                if mode == "BATTLE":
                    # B13: loan only "up to the number of Regulars" -- the same
                    # amount the B12 selection scored with, so prediction and
                    # resolution agree (don't over-commit/expose War Parties).
                    n = self._cc_battle_wp(sp)
                    if n <= 0:
                        continue
                    wp_counts[sid] = n
                spaces.append(sid)
        if not spaces:
            return False
        try:
            cc_ctx = common_cause.execute(
                state, C.BRITISH, {}, spaces, mode=mode,
                wp_counts=wp_counts or None, preserve_wp=True)
            # S55: return the ctx (ctx["common_cause"] = {sid: n}) so the
            # caller can hand it to battle.execute — the resolver reads
            # cc_wp per space from it (battle.py line ~616).  Discarding
            # it resolved every CC Battle with cc_wp=0: the bot SELECTED
            # spaces with the CC-boosted Force Level, then FOUGHT without
            # it (selection/resolution mismatch, the T13 class).
            if cc_ctx.get("common_cause"):
                return cc_ctx
            return False
        except Exception:
            return False

    # =======================================================================
    #  PRE‑CONDITION CHECKS  (mirrors italics at start of §8.4.x)
    # =======================================================================
    def _can_garrison(self, state: Dict) -> bool:
        # Garrison unavailable at FNI level 3
        if state.get("fni_level", 0) >= 3:
            return False
        # §8.1 "Paying Resource Costs" + §3.2.2 (two Resources total): a
        # Non-player that cannot pay even the minimum for the Command
        # follows the flowchart as if unable to execute it — without
        # burning the Naval-Pressure/Skirmish SA first (Session 55).
        if not can_afford(state, C.BRITISH, 2):
            return False
        refresh_control(state)
        # §8.4.1: "10 or more Regulars in all Cities and Provinces on the
        # map combined" — the West Indies box is neither (Session 55).
        regs_on_map = sum(sp.get(C.REGULAR_BRI, 0)
                          for sid, sp in state["spaces"].items()
                          if sid != WEST_INDIES)
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
        # B6: "Available British Regulars > 1D6?"  Playbook Example 3:
        # with 7+ Available "there is no need to roll the die — a D6
        # can't roll seven or higher" — skip the roll entirely so the
        # rng stream matches the physical procedure (S59).
        avail = state["available"].get(C.REGULAR_BRI, 0)
        if avail >= 7:
            return True
        # Roll once and cache the result for this turn
        if "_muster_die_cached" not in state:
            die = state["rng"].randint(1, 6)
            state["_muster_die_cached"] = die
            state.setdefault("rng_log", []).append(("B6 1D6", die))
        return avail > state["_muster_die_cached"]

    def _can_battle(self, state: Dict) -> bool:
        """B9 trigger, reconciled across the three references (S55):

        §8.4.4: "at least one space (including WI) with at least two
        Rebellion pieces that are outnumbered by British Regulars+Leader";
        §8.4.3 (the exact complement, most detailed): "no space (nor WI)
        with both British and at least 2 Active Rebellion pieces where
        British Regulars plus Leader outnumber all Rebellion pieces plus
        Leaders"; flowchart B9 abbreviates the same.

        So: >= 2 ACTIVE Rebellion pieces (cubes and Forts are always
        Active, Glossary/§1.4.3; Underground Militia excluded from the
        count), and British Regulars + Leader > ALL Rebellion pieces
        (incl. Underground Militia and Forts) plus Rebellion Leaders.
        """
        refresh_control(state)
        for sid, sp in state["spaces"].items():
            active_rebel = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.FORT_PAT, 0)   # Forts are always Active (§1.4.3)
            )
            if active_rebel < 2:
                continue
            all_rebel_pieces = active_rebel + sp.get(C.MILITIA_U, 0)
            rebel_leaders = sum(
                1 for lid in ("LEADER_WASHINGTON", "LEADER_ROCHAMBEAU",
                              "LEADER_LAUZUN")
                if leader_location(state, lid) == sid
            )
            royal = sp.get(C.REGULAR_BRI, 0)
            has_british_leader = any(
                leader_location(state, lid) == sid
                for lid in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON")
            )
            if royal + (1 if has_british_leader else 0) > (
                    all_rebel_pieces + rebel_leaders):
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.REGULAR_BRI, 0) > 0 for sp in state["spaces"].values())

    # =======================================================================
    #  OPS Summary methods (year-end and during-turn bot decisions)
    # =======================================================================

    def _follow_leaders_after_garrison(self, state: Dict, move_map: Dict[str, Dict[str, int]]) -> None:
        """Apply OPS leader-movement rule after a British Garrison.

        Garrison's move_map is structured {origin: {dest_city: count}}.
        For each British leader, the per-leader spaces_with_moves dict
        is simply move_map.get(leader_loc, {}) — destinations the
        leader's space sent Regulars to, with counts.  Then delegate
        to bot_leader_movement and update state["leaders"] if the
        leader should follow.
        """
        leaders_state = state.get("leaders")
        if not isinstance(leaders_state, dict):
            return
        for leader in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"):
            leader_loc = leader_location(state, leader)
            if not leader_loc:
                continue
            spaces_with_moves = dict(move_map.get(leader_loc, {}))
            if not spaces_with_moves:
                continue
            new_loc = BritishBot.bot_leader_movement(state, leader, spaces_with_moves)
            if new_loc and new_loc != leader_loc:
                if leader in leaders_state and isinstance(leaders_state.get(leader), (str, type(None))):
                    leaders_state[leader] = new_loc
                else:
                    keys_to_remove = [k for k, v in leaders_state.items() if v == leader]
                    for k in keys_to_remove:
                        leaders_state.pop(k, None)
                    leaders_state[new_loc] = leader
                push_history(
                    state,
                    f"{leader} follows largest Garrison group: {leader_loc} -> {new_loc}"
                )

    def _follow_leaders_after_march(self, state: Dict, plan: list) -> None:
        """Apply OPS leader-movement rule after a British March.

        For each British leader currently on the map, compute the
        per-leader spaces_with_moves dict from *plan* (filtered to
        moves originating in the leader's current space) and update
        state["leaders"][leader] if bot_leader_movement chooses a
        new location.
        """
        leaders_state = state.get("leaders")
        if not isinstance(leaders_state, dict):
            return
        for leader in ("LEADER_GAGE", "LEADER_HOWE", "LEADER_CLINTON"):
            leader_loc = leader_location(state, leader)
            if not leader_loc:
                continue
            spaces_with_moves: Dict[str, int] = {}
            for mv in plan:
                if mv.get("src") != leader_loc:
                    continue
                pieces = mv.get("pieces", {})
                count = int(pieces.get(C.REGULAR_BRI, 0)) + int(pieces.get(C.TORY, 0))
                if count <= 0:
                    continue
                dst = mv.get("dst")
                if dst:
                    spaces_with_moves[dst] = spaces_with_moves.get(dst, 0) + count
            if not spaces_with_moves:
                continue  # nothing left leader_loc → leader stays
            new_loc = BritishBot.bot_leader_movement(state, leader, spaces_with_moves)
            if new_loc and new_loc != leader_loc:
                # Mutate the leaders map in-place — leader_location()
                # supports both `state['leaders']` and reverse-mapping.
                # Find the existing key (could be leader-name or space-name).
                if leader in leaders_state and isinstance(leaders_state.get(leader), (str, type(None))):
                    leaders_state[leader] = new_loc
                else:
                    # reverse mapping: state['leaders'][space] = leader
                    # Find and remove old, add new
                    keys_to_remove = [k for k, v in leaders_state.items() if v == leader]
                    for k in keys_to_remove:
                        leaders_state.pop(k, None)
                    leaders_state[new_loc] = leader
                push_history(
                    state,
                    f"{leader} follows largest group: {leader_loc} -> {new_loc}"
                )

    def bot_supply_priority(self, state: Dict) -> List[str]:
        """British Supply: Pay only in spaces where removing British would
        prevent Reward Loyalty or allow Committees of Correspondance,
        first with Resources in highest Pop, then with shifts in highest Pop.

        Returns ordered list of space IDs where British should pay Supply.
        """
        # §8.4.7: RL enablement matters only if the British can actually
        # spend during the Support Phase "given expected British earnings
        # from Forts and Cities (but not the West Indies) (6.3)".
        from lod_ai.util.naval import effective_population
        expected = 0
        for sid, sp in state["spaces"].items():
            if sp.get(C.FORT_BRI, 0):
                expected += 1
            if (_MAP_DATA.get(sid, {}).get("type") == "City"
                    and self._control(state, sid) == C.BRITISH):
                expected += effective_population(
                    state, sid, _MAP_DATA.get(sid, {}).get("population", 0))

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

            # Would keeping the cubes allow Reward Loyalty (6.4.1) —
            # and will there be anything to spend on it?
            prevents_rl = (
                sp.get(C.REGULAR_BRI, 0) >= 1
                and sp.get(C.TORY, 0) >= 1
                and self._control(state, sid) == C.BRITISH
                and self._support_level(state, sid) < C.ACTIVE_SUPPORT
                and (state["resources"].get(C.BRITISH, 0) + expected) >= 1
            )
            # Would removing the cubes allow Committees of Correspondence?
            # §6.4.2 needs REBELLION CONTROL + Patriot pieces — simulate
            # the cubes' departure (Session 50: the old proxy fired on
            # any rebel piece anywhere the British stood, over-paying).
            rebels = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                      + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                      + sp.get(C.FORT_PAT, 0))
            pat_pieces = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0)
                          + sp.get(C.MILITIA_U, 0) + sp.get(C.FORT_PAT, 0))
            royal_after = (sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
                           + sp.get(C.VILLAGE, 0) + sp.get(C.FORT_BRI, 0))
            allows_committees = (pat_pieces > 0 and rebels > royal_after)

            if prevents_rl or allows_committees:
                pop = meta.get("population", 0)
                # First by highest Pop
                pay_spaces.append((-pop, sid))

        pay_spaces.sort()
        return [sid for _, sid in pay_spaces]

    def bot_redeploy_leader(self, state: Dict) -> str | None:
        """Redeploy: British Leader to the space with most British
        Regulars.  §6.5.2 scopes legal targets to spaces with the
        Faction's own pieces (Regulars, Tories or a Fort); with none
        anywhere the Leader goes to Available (None).  Ties seeded per
        §8.2.  (Session 43: the old scan could return a British-less
        dict-order space when no Regulars were on the map.)"""
        rng = state["rng"]
        best_key, best_sid = None, None
        for sid, sp in state["spaces"].items():
            brit = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                    + sp.get(C.FORT_BRI, 0))
            if brit == 0:
                continue  # §6.5.2: not a legal redeploy space
            key = (-sp.get(C.REGULAR_BRI, 0), rng.random())
            if best_key is None or key < best_key:
                best_key, best_sid = key, sid
        return best_sid

    def bot_loyalist_desertion(self, state: Dict, count: int) -> List[Tuple[str, int]]:
        """§8.4.10: "Remove Tories so as to change the least Control
        possible, if possible without removing the last Tory from any
        space."  Each removal is scored on a live snapshot and the
        priorities re-computed after every single Tory — the old static
        margin sort bulk-removed from one space and could flip Control
        mid-batch (Session 54, the §8.5.7 fix pattern from Session 45).
        Control changes are §1.7 simulations; §8.2 seeded ties.

        Returns a list of (space_id, 1) removals totaling ≤ *count*.
        """
        rng = state["rng"]
        snap = {sid: dict(sp) for sid, sp in state["spaces"].items()}

        def _ctl(sp):
            reb = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                   + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0)
                   + sp.get(C.FORT_PAT, 0))
            roy = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                   + sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
                   + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0))
            bri = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                   + sp.get(C.FORT_BRI, 0))
            if reb > roy:
                return "REBELLION"
            if roy > reb and bri > 0:
                return C.BRITISH
            return None

        removals: List[Tuple[str, int]] = []
        for _ in range(count):
            best_key, best_sid = None, None
            for sid, sp in snap.items():
                if sp.get(C.TORY, 0) == 0:
                    continue
                after = dict(sp)
                after[C.TORY] -= 1
                changes = 1 if _ctl(after) != _ctl(sp) else 0
                is_last = 1 if sp.get(C.TORY, 0) == 1 else 0
                key = (changes, is_last, rng.random())
                if best_key is None or key < best_key:
                    best_key, best_sid = key, sid
            if best_sid is None:
                break
            snap[best_sid][C.TORY] -= 1
            removals.append((best_sid, 1))
        return removals

    @staticmethod
    def bot_indian_trade(state: Dict) -> int:
        """Compute the British offer for an Indian Trade request per the
        OPS reference: "If Indians request Trade and Indian Resources <
        British Resources, roll 1D6: if the roll < British Resources,
        offer to transfer Resources equal to half (round up) the number
        rolled to Indian Resources."

        Wired into IndianBot._trade so the Indian bot can ask British
        for an offer instead of computing it inline (and missing the
        Indian < British gate).

        Returns the amount to transfer (0 if no offer).
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

    @staticmethod
    def bot_leader_movement(state: Dict, leader: str, spaces_with_moves: Dict[str, int]) -> str | None:
        """OPS reference: "Royalist Leaders follow largest group of own
        units that moves from (or stays in) their spaces."

        Wired into BritishBot._march so each British leader follows the
        largest group originating in (or remaining at) their current
        space after a March.

        Parameters
        ----------
        leader : str
            British leader identifier (LEADER_GAGE / LEADER_HOWE /
            LEADER_CLINTON).
        spaces_with_moves : Dict[str, int]
            Destinations the leader's space sent units to, mapped to the
            count of British units (Regulars + Tories) that moved there.

        Returns the space ID the leader should now occupy.  Returns
        None if the leader is not currently on the map.
        """
        leader_loc = leader_location(state, leader)
        if not leader_loc:
            return None

        # Largest group: the group that stayed at leader_loc, or the
        # group that moved to each destination in spaces_with_moves.
        # If staying tie-breaks against any moving group, the leader
        # stays put (best_dest defaults to leader_loc, only changes if
        # a destination strictly exceeds the staying count).
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
