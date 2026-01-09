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
import random, json

from lod_ai.bots.base_bot import BaseBot
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
WEST_INDIES = "West_Indies"
_VALID_PROVINCES: List[str] = ["Quebec", "New_York", "New_Hampshire", "Massachusetts"]


# ---------------------------------------------------------------------------
#  Helper to run Préparer la Guerre (both before and after Treaty)
# ---------------------------------------------------------------------------
def _preparer_la_guerre(state: Dict, post_treaty: bool) -> bool:
    """
    Execute the Préparer la Guerre special activity.

    Logic (flow‑chart F8 & F15):
        • Move 1 Blockade from Unavailable → West Indies.
        • If none, up to 3 French Regulars Unavailable → Available.
        • Post Treaty extra: if nothing moved and Resources==0 → +2 Resources.
    Return True if *anything* was done.
    """
    moved = False
    unavail = state.setdefault("unavailable", {})
    avail_pool = state.setdefault("available", {})
    if unavailable_blockades(state) > 0:
        moved = move_blockades_to_west_indies(state, 1)
        if moved == 0:
            return False
        push_history(state, "Préparer la Guerre: Blockade to West Indies")
        moved = True
    elif unavail.get(C.REGULAR_FRE, 0) > 0:
        avail = min(3, unavail[C.REGULAR_FRE])
        unavail[C.REGULAR_FRE] -= avail
        avail_pool[C.REGULAR_FRE] = avail_pool.get(C.REGULAR_FRE, 0) + avail
        push_history(state, f"Préparer la Guerre: {avail} Regulars to Available")
        moved = True

    if post_treaty and not moved and state["resources"]["FRENCH"] == 0:
        state["resources"]["FRENCH"] += 2
        push_history(state, "Préparer la Guerre: +2 Resources (post‑Treaty bonus)")
        moved = True

    return moved


class FrenchBot(BaseBot):
    faction = "FRENCH"

    def _support_level(self, state: Dict, sid: str) -> int:
        return state.get("support", {}).get(sid, 0)

    # ===================================================================
    #  FLOW‑CHART DRIVER
    # ===================================================================
    def _follow_flowchart(self, state: Dict) -> None:
        treaty = state.get("toa_played", False)

        # -------- PRE‑TREATY BRANCH (F5‑F8) ----------------------------------
        if not treaty:
            if self._before_treaty(state):
                return
            push_history(state, "FRENCH PASS")
            return

        # -------- POST‑TREATY BRANCH (F9‑F17) ------------------------------
        if self._after_treaty(state):
            return
        push_history(state, "FRENCH PASS")

    # -------------------------------------------------------------------
    #  PRE‑TREATY implementation (F5 → F8)
    # -------------------------------------------------------------------
    def _before_treaty(self, state: Dict) -> bool:
        # F5: Patriot Resources < 1D3 ?
        need_hortalez = (
            state["resources"]["PATRIOTS"]
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
        # F13 check already passed; decide Battle vs March
        if self._can_battle(state) and self._battle(state):  # F16
            return True
        if self._can_march(state) and self._march(state):    # F14
            self._skirmish_loop(state)                       # F12 loop
            return True
        return False

    # ===================================================================
    #  SPECIAL‑ACTIVITY HELPERS
    # ===================================================================
    def _try_skirmish(self, state: Dict) -> bool:
        """
        F12 rules:
          – Space with French & British not selected for Command
          – West Indies first
          – Remove Fort first, else most British cubes
        """
        # 1) West Indies
        sp = state["spaces"].get(WEST_INDIES)
        if sp and sp.get(C.REGULAR_FRE, 0) and sp.get(C.REGULAR_BRI, 0):
            try:
                skirmish.execute(state, "FRENCH", {}, WEST_INDIES, option=2)
                return True
            except Exception:
                pass

        # 2) Any other shared space
        for sid, sp in state["spaces"].items():
            if sid == WEST_INDIES:
                continue
            if sp.get(C.REGULAR_FRE, 0) and sp.get(C.REGULAR_BRI, 0):
                try:
                    skirmish.execute(state, "FRENCH", {}, sid, option=2)
                    return True
                except Exception:
                    continue
        return False

    def _try_naval_pressure(self, state: Dict) -> bool:
        """
        F17: Add 1 Blockade (Battle space first, else most Support).
        If none, fallback to Skirmish.
        """
        try:
            naval_pressure.execute(state, "FRENCH", {})
            return True
        except Exception:
            # last resort Skirmish
            return self._try_skirmish(state)

    # ===================================================================
    #  COMMAND IMPLEMENTATIONS
    # ===================================================================
    # ----- Agent Mobilisation (F7) ------------------------------
    def _agent_mobilization(self, state: Dict) -> bool:
        """Place 2 Militia or 1 Continental per F7 priorities."""
        best, best_score = None, -1
        for prov in _VALID_PROVINCES:
            sp = state["spaces"].get(prov)
            if not sp:
                continue
            # first to add most Rebel Control, then most Patriot units
            rc_shift = 1 if sp.get("control") != "REBELLION" else 0
            patriots = sp.get(C.MILITIA_A, 0) + sp.get(C.MILITIA_U, 0) + sp.get(C.REGULAR_PAT, 0)
            score = rc_shift * 10 + patriots
            if score > best_score:
                best, best_score = prov, score
        if not best:
            return False
        fam.execute(state, "FRENCH", {}, best, place_continental=False)
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
        pay = min(state["resources"]["FRENCH"], random.randint(1, 3))
        hortelez.execute(state, "FRENCH", {}, pay=pay)
        phase = "pre‑Treaty" if before_treaty else "post‑Treaty"
        push_history(state, f"Roderigue Hortalez et Cie ({phase}): Pay {pay}")

    def _can_hortelez(self, state: Dict) -> bool:
        return state["resources"]["FRENCH"] > 0

    # ----- Muster (F10) ----------------------------------------
    def _muster(self, state: Dict) -> bool:
        # Destination selection per bullet list
        west_indies = state["spaces"].get(WEST_INDIES)
        west_rebel = bool(west_indies and west_indies.get("control") == "REBELLION")
        if west_rebel or state["available"].get(C.REGULAR_FRE, 0) >= 4:
            # With Rebel Control somewhere – look for Colony/City with Continentals
            targets = [
                sid for sid, sp in state["spaces"].items()
                if (sp.get(C.REGULAR_PAT, 0) > 0) and sp.get("control") == "REBELLION"
            ]
        else:
            targets = [WEST_INDIES] if west_indies else []

        if not targets:
            return False
        target = random.choice(targets)
        muster.execute(state, "FRENCH", {}, [target])
        return True

    # ----- March (F14) -----------------------------------------
    def _march(self, state: Dict) -> bool:
        refresh_control(state)
        # Primary: add Rebel Control in Cities first
        candidates: List[Tuple[int, str, str]] = []
        for src, sp in state["spaces"].items():
            if sp.get(C.REGULAR_FRE, 0) == 0:
                continue
            for adj in _MAP_DATA[src]["adj"]:
                for dst in adj.split("|"):
                    dsp = state["spaces"][dst]
                    if dsp.get("control") == "REBELLION":
                        continue
                    dest_score = (dst in _VALID_PROVINCES) * 2 + dsp.get("population", 0)
                    candidates.append((dest_score, src, dst))
        if not candidates:
            return False
        _, src, dst = max(candidates)
        march.execute(state, "FRENCH", {}, [src], [dst], bring_escorts=False, limited=True)
        return True

    # ----- Battle (F16) ----------------------------------------
    def _battle(self, state: Dict) -> bool:
        refresh_control(state)
        targets = []
        for sid, sp in state["spaces"].items():
            rebel_force = (
                sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            crown_force = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
            if rebel_force > crown_force and crown_force > 0:
                targets.append((sp.get("population", 0), sid))
        if not targets:
            return False
        targets.sort(reverse=True)
        # Pre‑Battle SA: Skirmish loop (chart arrow “First execute a SA”)
        self._skirmish_loop(state)
        battle.execute(state, "FRENCH", {}, [sid for _, sid in targets])
        return True

    # ===================================================================
    #  FLOW‑CHART PRE‑CONDITION TESTS
    # ===================================================================
    def _can_muster(self, state: Dict) -> bool:
        return state["available"].get(C.REGULAR_FRE, 0) > 0

    def _can_battle(self, state: Dict) -> bool:
        for sp in state["spaces"].values():
            if sp.get(C.REGULAR_FRE, 0) and sp.get(C.REGULAR_BRI, 0):
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        return any(sp.get(C.REGULAR_FRE, 0) for sp in state["spaces"].values())

    # ===================================================================
    #  EVENT‑VS‑COMMAND BULLETS  (F2)
    # ===================================================================
    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        text = card.get("unshaded_event", "")
        support_map = state.get("support", {})
        sup = sum(max(0, lvl) for lvl in support_map.values())
        opp = sum(max(0, -lvl) for lvl in support_map.values())

        # • Support > Opposition and Event shifts toward Rebels
        if sup > opp and any(k in text for k in ("Support", "Opposition")):
            return True
        # • Moves Regulars/Squadrons from Unavailable OR places French pieces
        if any(k in text for k in ("Squadron", "Regular", "French Leader")):
            return True
        # • Inflicts British casualties
        if "British" in text and "casualt" in text.lower():
            return True
        # • Adds French Resources
        if "Resources" in text:
            return True
        # • Treaty played & Die roll
        if state.get("toa_played") and self._event_die_roll(state):
            return True
        return False

    def _event_die_roll(self, state: Dict) -> bool:
        roll = state["rng"].randint(1, 6)
        state.setdefault("rng_log", []).append(("Event D6", roll))
        return roll >= 5
