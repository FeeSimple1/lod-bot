# lod_ai/bots/french.py
"""
Non‑player French bot – *full* flow‑chart implementation (§8.6).

Flow covered (nodes F1‑F17):

  • Before Treaty of Alliance ........ F5 Agent Mobilisation / F6 Hortalez
  • Préparer la Guerre SA ............ F8 (pre‑Treaty) / F15 (post‑Treaty)
  • After Treaty  .................... Muster → Skirmish → Préparer la Guerre
                                        or Battle / March alternatives
  • Loop logic  ...................... F12 Skirmish → F15 Préparer → F17 Naval → F12

Reference: “french bot flowchart and reference.txt”
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import json

from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai import rules_consts as C
from lod_ai.commands import (
    french_agent_mobilization as fam,
    hortelez,
    muster,
    march,
    battle,
)
from lod_ai.special_activities import skirmish, naval_pressure
# Some installs already expose a helper – fall back to a local stub if absent
try:
    from lod_ai.special_activities import preparer_la_guerre as plg
except ImportError:  # pragma: no cover
    plg = None

from lod_ai.util.history import push_history
from lod_ai.board.control import refresh_control
from lod_ai.util.naval import move_blockades_to_west_indies, unavailable_blockades

# ---------------------------------------------------------------------------
#  Static data
# ---------------------------------------------------------------------------
_MAP_DATA = json.load(
    open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json")
)
WEST_INDIES = C.WEST_INDIES_ID
_VALID_PROVINCES: List[str] = ["Quebec_City", "New_York", "New_Hampshire", "Massachusetts"]


# ---------------------------------------------------------------------------
#  Helper to run Préparer la Guerre (both before and after Treaty)
# ---------------------------------------------------------------------------
def _preparer_la_guerre(state: Dict, post_treaty: bool) -> bool:
    """
    Execute the Préparer la Guerre special activity.

    Logic (flow‑chart F8 & F15):
        • Pre-Treaty (F8): Move 1 Blockade → WI, or up to 3 Regulars Unavailable → Available.
        • Post-Treaty (F15): Only if 1D6 <= Unavailable French Regulars + Blockades.
          Move 1 Blockade → WI, or up to 3 Regulars Unavailable → Available.
          If nothing moved and Resources==0 → +2 Resources.
    Return True if *anything* was done.
    """
    moved = False
    unavail = state.setdefault("unavailable", {})
    avail_pool = state.setdefault("available", {})

    # F15 post-Treaty D6 gate
    if post_treaty:
        unavail_regs = unavail.get(C.REGULAR_FRE, 0)
        unavail_blk = unavailable_blockades(state)
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Preparer D6", roll))
        if roll > (unavail_regs + unavail_blk):
            # D6 exceeded threshold — nothing happens
            if state["resources"][C.FRENCH] == 0:
                state["resources"][C.FRENCH] += 2
                push_history(state, "Préparer la Guerre: +2 Resources (post‑Treaty bonus)")
                return True
            return False

    if unavailable_blockades(state) > 0:
        count = move_blockades_to_west_indies(state, 1)
        if count > 0:
            push_history(state, "Préparer la Guerre: Blockade to West Indies")
            moved = True
    # If no Blockade moved, try up to 3 Regulars from Unavailable to Available
    if not moved and unavail.get(C.REGULAR_FRE, 0) > 0:
        avail = min(3, unavail[C.REGULAR_FRE])
        unavail[C.REGULAR_FRE] -= avail
        avail_pool[C.REGULAR_FRE] = avail_pool.get(C.REGULAR_FRE, 0) + avail
        push_history(state, f"Préparer la Guerre: {avail} Regulars to Available")
        moved = True

    if post_treaty and not moved and state["resources"][C.FRENCH] == 0:
        state["resources"][C.FRENCH] += 2
        push_history(state, "Préparer la Guerre: +2 Resources (post‑Treaty bonus)")
        moved = True

    return moved


class FrenchBot(BaseBot):
    faction = C.FRENCH

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    # ===================================================================
    #  BRILLIANT STROKE LimCom  (§8.3.7)
    # ===================================================================
    def get_bs_limited_command(self, state: Dict) -> str | None:
        """Walk French flowchart for the first valid Limited Command
        that can involve the French Leader in the Leader's current space.

        BS requires ToA played, so only post-Treaty branch applies.
        Flowchart order: F3 → F9 (Muster) → F13 (Battle) → F14 (March).
        Returns a command name or None.
        """
        leader_space = self._find_bs_leader_space(state)
        if not leader_space:
            return None

        # F3: Resources > 0?
        if state.get("resources", {}).get(C.FRENCH, 0) <= 0:
            return None

        sp = state["spaces"].get(leader_space, {})
        refresh_control(state)

        # F9/F10: Muster — Available French Regulars > 0?
        # Muster can target the leader's space.
        if state["available"].get(C.REGULAR_FRE, 0) > 0:
            return "muster"

        # F13: Battle — Rebel cubes + Leader exceed British pieces
        # in the leader's space?
        from lod_ai.leaders import leader_location
        rebel_leaders = ["LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN"]
        leader_bonus = 0
        for ldr in rebel_leaders:
            if leader_location(state, ldr) == leader_space:
                leader_bonus += 1
        rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
        rebel = rebel_cubes + leader_bonus
        british = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                   + sp.get(C.FORT_BRI, 0))
        if rebel > 0 and british > 0 and rebel > british:
            return "battle"

        # F14: March — French Regulars in leader's space can march
        if sp.get(C.REGULAR_FRE, 0) > 0:
            return "march"

        return None

    # ===================================================================
    #  FLOW‑CHART DRIVER
    # ===================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        # F3: French Resources > 0?
        if state.get("resources", {}).get(C.FRENCH, 0) <= 0:
            push_history(state, "FRENCH PASS (no Resources)")
            return

        treaty = state.get("toa_played", False)

        # -------- PRE-TREATY BRANCH (F5-F8) ----------------------------------
        if not treaty:
            if self._before_treaty(state):
                return
            push_history(state, "FRENCH PASS")
            return

        # -------- POST-TREATY BRANCH (F9-F17) --------------------------------
        if self._after_treaty(state):
            return
        push_history(state, "FRENCH PASS")

    # -------------------------------------------------------------------
    #  PRE‑TREATY implementation (F5 → F8)
    # -------------------------------------------------------------------
    def _before_treaty(self, state: Dict) -> bool:
        # F5: Patriot Resources < 1D3 ?
        need_hortalez = (
            state["resources"][C.PATRIOTS]
            < state["rng"].randint(1, 3)
        )

        # F7: Agent Mobilisation max 1
        if not need_hortalez and self._can_agent_mobilization(state):
            if self._agent_mobilization(state):
                _preparer_la_guerre(state, post_treaty=False)  # F8
                return True

        # F6: Roderigue Hortalez et Cie
        if self._can_hortelez(state):
            self._hortelez(state, before_treaty=True)
            _preparer_la_guerre(state, post_treaty=False)  # F8
            return True

        return False

    # -------------------------------------------------------------------
    #  POST‑TREATY implementation
    # -------------------------------------------------------------------
    def _after_treaty(self, state: Dict) -> bool:
        # ---------- F9 decision 1D6 < Available Regulars? -----------------
        avail_regs = state["available"].get(C.REGULAR_FRE, 0)
        if state["rng"].randint(1, 6) < avail_regs:
            if self._muster_chain(state):  # F10 + F12 loop or F11 fallback
                return True
        # ---------- Otherwise F13 decision (Battle vs March) --------------
        if self._battle_chain(state):      # F16 else F14 + F12 loop
            return True
        # ---------- Last chance: March chain may flow back in -------------
        return False

    # ========== EXECUTION CHAINS ========================================
    #  (wrap Command + SA loops exactly as chart dictates)
    # -------------------------------------------------------------------
    def _muster_chain(self, state: Dict) -> bool:
        if self._can_muster(state) and self._muster(state):  # F10
            self._skirmish_loop(state)                      # F12 etc.
            return True
        # F11 fallback: Roderigue Hortalez
        if self._can_hortelez(state):
            self._hortelez(state, before_treaty=False)
            self._skirmish_loop(state)
            return True
        return False

    def _skirmish_loop(self, state: Dict) -> None:
        """
        Implements the F12 → F15 → F17 loop until an SA succeeds or the
        entire chain fails to do anything.
        """
        if self._try_skirmish(state):      # F12
            return
        if _preparer_la_guerre(state, post_treaty=True):  # F15
            return
        self._try_naval_pressure(state)    # F17 (may fall back to Skirmish)

    def _battle_chain(self, state: Dict) -> bool:
        # F13: Rebel cubes + Leader exceed British?
        if self._can_battle(state) and self._battle(state):  # F16
            return True
        # F13 No (or F16 none) → F14 March
        if self._can_march(state) and self._march(state):    # F14
            self._skirmish_loop(state)                       # F12 loop
            return True
        # F14 "If none" → F10 (Muster)
        return self._muster_chain(state)

    # ===================================================================
    #  SPECIAL‑ACTIVITY HELPERS
    # ===================================================================
    def _try_skirmish(self, state: Dict) -> bool:
        """
        F12 rules:
          – Space with French & British not selected for Battle or Muster
          – West Indies first
          – Remove first a British Fort, then most British cubes
        """
        affected = state.get("_turn_affected_spaces", set())

        def _has_british(sp: Dict) -> bool:
            return (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                    + sp.get(C.FORT_BRI, 0)) > 0

        def _skirmish_option(sp: Dict) -> int:
            """option=3 if enemy Fort present and no enemy cubes; else option=2 (remove 2 cubes)."""
            enemy_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if enemy_cubes == 0 and sp.get(C.FORT_BRI, 0) > 0:
                return 3
            if enemy_cubes >= 2:
                return 2
            if enemy_cubes >= 1:
                return 1
            return 1  # fallback

        def _try_space(sid: str) -> bool:
            if sid in affected:
                return False
            sp = state["spaces"].get(sid)
            if not sp or not sp.get(C.REGULAR_FRE, 0) or not _has_british(sp):
                return False
            opt = _skirmish_option(sp)
            try:
                skirmish.execute(state, C.FRENCH, {}, sid, option=opt)
                return True
            except Exception:
                return False

        # 1) West Indies first
        if _try_space(WEST_INDIES):
            return True

        # 2) Any other shared space — prefer most British cubes
        candidates = []
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES or sid in affected:
                continue
            if sp.get(C.REGULAR_FRE, 0) and _has_british(sp):
                brit_cubes = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                candidates.append((-brit_cubes, sid))
        candidates.sort()
        for _, sid in candidates:
            if _try_space(sid):
                return True
        return False

    def _try_naval_pressure(self, state: Dict) -> bool:
        """
        F17: Add 1 Blockade, first in a City selected for Battle, then at most Support.
        If none, Skirmish (F12). If Skirmish also fails, Préparer (F15).
        """
        # Determine city_choice: first a city selected for Battle, then most Support
        affected = state.get("_turn_affected_spaces", set())
        bloc = state.get("markers", {}).get(C.BLOCKADE, {})
        pool = bloc.get("pool", 0)
        if pool > 0 and state.get("toa_played"):
            # Find best city: battle space first, then most Support
            best_city = None
            best_score = (-1, -1)
            for sid in state.get("spaces", {}):
                if _MAP_DATA.get(sid, {}).get("type") != "City":
                    continue
                in_battle = 1 if sid in affected else 0
                sup = state.get("support", {}).get(sid, 0)
                score = (in_battle, sup)
                if score > best_score:
                    best_score = score
                    best_city = sid
            if best_city:
                try:
                    naval_pressure.execute(state, C.FRENCH, {}, city_choice=best_city)
                    return True
                except Exception:
                    pass

        # F17 failed → fallback to F12 (Skirmish)
        if self._try_skirmish(state):
            return True
        # F12 also failed → fallback to F15 (Préparer la Guerre)
        return _preparer_la_guerre(state, post_treaty=True)

    # ===================================================================
    #  COMMAND IMPLEMENTATIONS
    # ===================================================================
    # ----- Agent Mobilisation (F7) ------------------------------
    def _agent_mobilization(self, state: Dict) -> bool:
        """F7: Place 2 Militia, or—if not possible—1 Continental.
        In Quebec City, New York, New Hampshire, or Massachusetts;
        first to add most Rebel Control, then where most Patriot units.
        """
        best, best_score = None, -1
        ctrl = state.get("control", {})
        for prov in _VALID_PROVINCES:
            sp = state["spaces"].get(prov)
            if not sp:
                continue
            # first to add most Rebel Control, then most Patriot units
            rc_shift = 1 if ctrl.get(prov) != "REBELLION" else 0
            patriots = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) + sp.get(C.REGULAR_PAT, 0)
            score = rc_shift * 10 + patriots
            if score > best_score:
                best, best_score = prov, score
        if not best:
            return False
        # Try 2 Militia first; if Militia not available, place 1 Continental
        avail_militia = state.get("available", {}).get(C.MILITIA_U, 0)
        place_continental = avail_militia < 2
        fam.execute(state, C.FRENCH, {}, best, place_continental=place_continental)
        return True

    def _can_agent_mobilization(self, state: Dict) -> bool:
        if state.get("toa_played"):
            return False
        return any(
            state["spaces"].get(p) and self._support_level(state, p) != C.ACTIVE_SUPPORT
            for p in _VALID_PROVINCES
        )

    # ----- Hortalez (F6 / F11) ---------------------------------
    def _hortelez(self, state: Dict, *, before_treaty: bool) -> None:
        roll = state["rng"].randint(1, 3)
        state.setdefault("rng_log", []).append(("Hortalez 1D3", roll))
        pay = min(state["resources"][C.FRENCH], roll)
        hortelez.execute(state, C.FRENCH, {}, pay=pay)
        phase = "pre‑Treaty" if before_treaty else "post‑Treaty"
        push_history(state, f"Roderigue Hortalez et Cie ({phase}): Pay {pay}")

    def _can_hortelez(self, state: Dict) -> bool:
        return state["resources"][C.FRENCH] > 0

    # ----- Muster (F10) ----------------------------------------
    def _muster(self, state: Dict) -> bool:
        """F10: Muster (Max 1) in 1 space with Rebel Control or the West Indies.

        Per flowchart:
        - If fewer than 4 French Regulars Available AND WI is not Rebel Controlled,
          Muster in West Indies.
        - Otherwise, Muster first in a Colony or City with Continentals, then random.
        """
        west_indies = state["spaces"].get(WEST_INDIES)
        avail_regs = state["available"].get(C.REGULAR_FRE, 0)
        ctrl = state.get("control", {})
        west_rebel = ctrl.get(WEST_INDIES) == "REBELLION"

        if avail_regs < 4 and not west_rebel:
            targets = [WEST_INDIES] if west_indies else []
        else:
            # Muster first in a Colony or City with Continentals and Rebel Control
            targets = [
                sid for sid, sp in state["spaces"].items()
                if (sp.get(C.REGULAR_PAT, 0) > 0
                    and ctrl.get(sid) == "REBELLION"
                    and _MAP_DATA.get(sid, {}).get("type") in ("Colony", "City"))
            ]
            if not targets:
                # Fallback: any space with Rebel Control
                targets = [
                    sid for sid in state["spaces"]
                    if ctrl.get(sid) == "REBELLION"
                ]

        if not targets:
            return False
        target = state["rng"].choice(targets)
        state.setdefault("_turn_affected_spaces", set()).add(target)
        muster.execute(state, C.FRENCH, {}, [target])
        return True

    # ----- March (F14) -----------------------------------------
    def _march(self, state: Dict) -> bool:
        """F14: March with French Regulars + Continentals to add Rebel Control,
        first in Cities, within that first where most British.
        """
        refresh_control(state)
        ctrl = state.get("control", {})
        candidates: List[Tuple[tuple, str, str]] = []
        for src, sp in state["spaces"].items():
            if sp.get(C.REGULAR_FRE, 0) == 0:
                continue
            for adj in _MAP_DATA.get(src, {}).get("adj", []):
                for dst in adj.split("|"):
                    if dst not in state.get("spaces", {}):
                        continue
                    if ctrl.get(dst) == "REBELLION":
                        continue
                    dsp = state["spaces"][dst]
                    is_city = 1 if _MAP_DATA.get(dst, {}).get("type") == "City" else 0
                    british = dsp.get(C.REGULAR_BRI, 0) + dsp.get(C.TORY, 0)
                    candidates.append(((is_city, british, state["rng"].random()), src, dst))
        if not candidates:
            return False
        _, src, dst = max(candidates)
        march.execute(state, C.FRENCH, {}, [src], [dst], bring_escorts=False, limited=False)
        return True

    # ----- Battle (F16) ----------------------------------------
    def _battle(self, state: Dict) -> bool:
        """F16: Select spaces where Rebel Force > Royalist Force, highest Pop.
        SA entry at F17 (Naval Pressure), not F12.
        """
        from lod_ai.leaders import leader_location
        refresh_control(state)
        targets = []

        # Determine Rebel leader locations for force-level bonus
        rebel_leaders = ["LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN"]
        leader_locs: Dict[str, int] = {}
        for ldr in rebel_leaders:
            loc = leader_location(state, ldr)
            if loc:
                leader_locs[loc] = leader_locs.get(loc, 0) + 1

        for sid, sp in state["spaces"].items():
            # Rebel force: cubes + Active Militia (Underground don't count)
            rebel_cubes = sp.get(C.REGULAR_FRE, 0) + sp.get(C.REGULAR_PAT, 0)
            active_militia = sp.get(C.MILITIA_A, 0)
            rebel_force = rebel_cubes + active_militia + leader_locs.get(sid, 0)

            # Royalist force: British cubes + Forts + Active WP
            british_pieces = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                              + sp.get(C.FORT_BRI, 0))
            crown_force = british_pieces + sp.get(C.WARPARTY_A, 0)

            if rebel_force > crown_force and british_pieces > 0:
                pop = _MAP_DATA.get(sid, {}).get("population", 0)
                targets.append((pop, sid))
        if not targets:
            return False
        targets.sort(reverse=True)
        # Track affected spaces so Skirmish can exclude them
        state.setdefault("_turn_affected_spaces", set()).update(
            sid for _, sid in targets
        )
        # F16: "First execute a Special Activity." SA entry at F17 (Naval Pressure)
        self._try_naval_pressure(state)
        battle.execute(state, C.FRENCH, {}, [sid for _, sid in targets])
        return True

    # ===================================================================
    #  FLOW‑CHART PRE‑CONDITION TESTS
    # ===================================================================
    def _can_muster(self, state: Dict) -> bool:
        return state["available"].get(C.REGULAR_FRE, 0) > 0

    def _can_battle(self, state: Dict) -> bool:
        """F13: Rebel cubes + Leader exceed British pieces in space with both?
        Rebel cubes = Continentals + French Regulars.
        British pieces = Regulars + Tories + Forts (British faction only, not Indians).
        Leader = any Rebel leader present (+1 each).
        """
        from lod_ai.leaders import leader_location
        rebel_leaders = ["LEADER_WASHINGTON", "LEADER_ROCHAMBEAU", "LEADER_LAUZUN"]
        leader_locs: Dict[str, int] = {}
        for ldr in rebel_leaders:
            loc = leader_location(state, ldr)
            if loc:
                leader_locs[loc] = leader_locs.get(loc, 0) + 1

        for sid, sp in state["spaces"].items():
            rebel_cubes = sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
            leader_bonus = leader_locs.get(sid, 0)
            rebel = rebel_cubes + leader_bonus
            british = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                       + sp.get(C.FORT_BRI, 0))
            if rebel > 0 and british > 0 and rebel > british:
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.REGULAR_FRE, 0) for sp in state["spaces"].values())

    # ===================================================================
    #  FRENCH EVENT INSTRUCTION CONDITIONALS
    # ===================================================================
    def _force_condition_met(self, directive: str, state: Dict, card: Dict) -> bool:
        """Evaluate force_if_X directives from the French instruction sheet.

        Each card instruction specifies a condition; if not met, the bot
        skips the event and proceeds to Command & SA instead.
        """
        if directive == "force_if_52":
            # Card 52: "Remove no French Regulars. If the Battle Command
            # instruction would select no Battle space, Command & SA instead."
            # Check: are there any spaces where French could battle British?
            for sid, sp in state["spaces"].items():
                has_french = sp.get(C.REGULAR_FRE, 0) > 0
                has_british = (sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
                               + sp.get(C.FORT_BRI, 0)) > 0
                if has_french and has_british:
                    # Set flag so card handler knows not to remove French Regulars
                    state["card52_no_remove_french"] = True
                    return True
            return False

        if directive == "force_if_62":
            # Card 62: "Place Militia only. If not possible, Command & SA."
            # Shaded places 3 Militia in Northwest or 3 French Regs in Quebec.
            # Bot instruction: only place Militia. Check if Militia available.
            avail_militia = state.get("available", {}).get(C.MILITIA_U, 0)
            if avail_militia > 0:
                state["card62_shaded_choice"] = "MILITIA_NORTHWEST"
                return True
            return False

        if directive == "force_if_70":
            # Card 70: "Remove British Regulars from spaces with Rebels.
            # If none, Command & SA."
            for sid, sp in state["spaces"].items():
                brit_regs = sp.get(C.REGULAR_BRI, 0)
                rebels = (sp.get(C.REGULAR_PAT, 0) + sp.get(C.REGULAR_FRE, 0)
                          + sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0))
                if brit_regs > 0 and rebels > 0:
                    return True
            return False

        if directive in ("force_if_73", "force_if_95"):
            # Card 73/95: "If no British Fort is removed, Command & SA."
            # Check: is there a British Fort on the map that could be removed?
            for sid, sp in state["spaces"].items():
                if sp.get(C.FORT_BRI, 0) > 0:
                    return True
            return False

        if directive == "force_if_83":
            # Card 83: "Select Quebec City. If playing the Event does not
            # gain Rebellion there, Command & SA."
            ctrl = state.get("control", {})
            if ctrl.get("Quebec_City") == "REBELLION":
                return False  # already Rebellion, no gain possible
            # Would placing up to 3 coalition pieces swing control?
            # The shaded event places up to 3 pieces (French + Patriot).
            # If Quebec City is not already Rebellion, the event might gain it.
            state["card83_target"] = "Quebec_City"
            return True

        return True  # default: play the event

    # ===================================================================
    #  EVENT‑VS‑COMMAND BULLETS  (F2)
    # ===================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """F2: Check shaded Event conditions for French bot via CARD_EFFECTS."""
        effects = CARD_EFFECTS.get(card.get("id"))
        if effects is None:
            return False  # unknown card → fall through to Command
        eff = effects["shaded"]

        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # 1. Support > Opposition and Event shifts in Rebel favor
        if sup > opp and eff["shifts_support_rebel"]:
            return True
        # 2. Places French pieces from Unavailable
        if eff["places_french_from_unavailable"]:
            return True
        # 3. Places French pieces on map
        if eff["places_french_on_map"]:
            return True
        # 4. Inflicts British casualties
        if eff["inflicts_british_casualties"]:
            return True
        # 5. Adds French Resources
        if eff["adds_french_resources"]:
            return True
        # 6. (After ToA only) Event is effective, D6 >= 5
        if state.get("toa_played") and eff["is_effective"]:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("Event D6", roll))
            if roll >= 5:
                return True
        return False
