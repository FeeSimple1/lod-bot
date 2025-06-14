# lod_ai/bots/british_bot.py
from typing import Dict, List
from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.commands import garrison, muster, march, battle
from lod_ai.special_activities import naval_pressure, skirmish, common_cause
from lod_ai.map import adjacency
from lod_ai.util.history import push_history
import json
from pathlib import Path

_MAP_DATA = json.load(open(Path(__file__).resolve().parents[1] / "map" / "data" / "map.json"))
CITIES = [name for name, info in _MAP_DATA.items() if info.get("type") == "City"]

class BritishBot(BaseBot):
    faction = "BRITISH"

    # ---------------------------------------------------------
    # 2. Command / SA flow-chart
    # ---------------------------------------------------------
    def _follow_flowchart(self, state: Dict) -> None:
        # A. GARRISON
        if self._can_garrison(state):
            if self._garrison(state):
                return

        # B. MUSTER
        if self._can_muster(state):
            if self._muster(state):
                return

        # C. BATTLE
        if self._can_battle(state):
            if self._battle(state):
                return

        # D. MARCH
        if self._can_march(state):
            if self._march(state):
                return

        # E. PASS
        push_history(state, "BRITISH PASS")

    # ---------------------------------------------------------
    # ---- Helper: attempt Naval Pressure then Skirmish -------
    # ---------------------------------------------------------
    def _naval_or_skirmish(self, state: Dict) -> None:
        """Execute Naval Pressure if allowed else attempt a Skirmish."""
        try:
            naval_pressure.execute(state, "BRITISH", {})
            return
        except Exception:
            pass

        for sid, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) == 0:
                continue
            reb = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
                + sp.get(C.MILITIA_U, 0)
            )
            if reb:
                try:
                    skirmish.execute(state, "BRITISH", {}, sid, option=1)
                    return
                except Exception:
                    continue


    # ---------------------------------------------------------
    # ---- Command executors  (stubs – fill bullets later) ----
    # ---------------------------------------------------------
    def _garrison(self, state: Dict) -> bool:
        """Execute Garrison per 8.4.1 (simplified)."""
        self._naval_or_skirmish(state)
        refresh_control(state)

        # pick target City needing British Control
        target = None
        most_rebels = -1
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            if sp.get("Patriot_Fort", 0):
                continue
            if sp.get("control") != "BRITISH":
                rebels = (
                    sp.get(C.REGULAR_PAT, 0)
                    + sp.get(C.REGULAR_FRE, 0)
                    + sp.get(C.MILITIA_A, 0)
                    + sp.get(C.MILITIA_U, 0)
                )
                if rebels > most_rebels:
                    most_rebels = rebels
                    target = name
        if not target and state["spaces"].get("New_York_City"):
            if state["spaces"]["New_York_City"].get("control") != "BRITISH":
                target = "New_York_City"
        if not target:
            return False

        origins = []
        for sid, sp in state["spaces"].items():
            if sid == target:
                continue
            if sp.get("control") == "BRITISH" and sp.get(C.REGULAR_BRI, 0) > 1:
                origins.append(sid)
        if not origins:
            # If nothing moves, Muster instead
            return self._muster(state)

        move_map = {orig: {target: 1} for orig in origins[:2]}

        # displacement target if rebels present
        displace_city = None
        displace_target = None
        sp_t = state["spaces"].get(target, {})
        if (
            sp_t.get(C.REGULAR_PAT, 0)
            + sp_t.get(C.REGULAR_FRE, 0)
            + sp_t.get(C.MILITIA_A, 0)
            + sp_t.get(C.MILITIA_U, 0)
        ):
            adj = set()
            for token in _MAP_DATA[target]["adj"]:
                adj.update(token.split("|"))
            if adj:
                displace_city = target
                displace_target = sorted(adj)[0]

        garrison.execute(
            state,
            "BRITISH",
            {},
            move_map,
            displace_city=displace_city,
            displace_target=displace_target,
        )
        return True

    def _muster(self, state: Dict) -> bool:
        """Simplified Muster following 8.4.2."""
        spaces = list(state["spaces"].keys())
        if not spaces:
            return False
        target = spaces[0]
        selected = [target]

        build_fort = False
        reward_levels = 0
        sp = state["spaces"][target]
        if sp.get("support", 0) <= C.PASSIVE_OPPOSITION:
            reward_levels = 1
        elif sp.get(C.FORT_BRI, 0) == 0 and sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0) >= 5:
            build_fort = True

        muster.execute(
            state,
            "BRITISH",
            {},
            selected,
            regular_plan={"space": target, "n": 1},
            tory_plan={target: 1},
            build_fort=build_fort,
            reward_levels=reward_levels,
        )

        self._naval_or_skirmish(state)
        return True

    def _march(self, state: Dict) -> bool:
        """Simplified March per 8.4.3."""
        for src, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) <= 1:
                continue
            adj = set()
            for token in _MAP_DATA[src]["adj"]:
                adj.update(token.split("|"))
            for dst in sorted(adj):
                if dst == src:
                    continue
                march.execute(
                    state,
                    "BRITISH",
                    {},
                    [src],
                    [dst],
                    bring_escorts=False,
                    limited=True,
                )
                self._naval_or_skirmish(state)
                return True
        return False

    def _battle(self, state: Dict) -> bool:
        """Simplified Battle following 8.4.4."""
        refresh_control(state)
        targets: List[str] = []
        for name, sp in state["spaces"].items():
            rebels = (
                sp.get(C.REGULAR_PAT, 0)
                + sp.get(C.REGULAR_FRE, 0)
                + sp.get(C.MILITIA_A, 0)
            )
            roy = sp.get(C.REGULAR_BRI, 0)
            if rebels >= 2 and roy > rebels:
                targets.append(name)

        if not targets:
            return False

        battle.execute(state, "BRITISH", {}, targets)
        self._naval_or_skirmish(state)
        return True

    # ---------------------------------------------------------
    # ---- Flow-chart pre-condition tests ---------------------
    # ---------------------------------------------------------
    # each _can_* mirrors the italic opening sentence of §8.4.x

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Apply the Event-or-Command bullets from Rule 8.4."""
        return self._brit_event_conditions(state, card)

    def _brit_event_conditions(self, state: Dict, card: Dict) -> bool:
        text = card.get("unshaded_event", "")

        sup = sum(max(0, lvl) for lvl in state.get("support", {}).values())
        opp = sum(max(0, -lvl) for lvl in state.get("support", {}).values())

        if opp > sup and any(w in text for w in ["Support", "Opposition", "Blockade"]):
            push_history(state, "BRITISH plays Event for support shift")
            return True

        if "Unavailable" in text or "out of play" in text:
            push_history(state, "BRITISH plays Event from Unavailable")
            return True

        if "Tory" in text:
            for sid, sp in state["spaces"].items():
                if sp.get("support", 0) == C.ACTIVE_OPPOSITION and sp.get(C.TORY, 0) == 0:
                    push_history(state, "BRITISH plays Event for Tory placement")
                    return True

        if "Fort" in text:
            for sid, sp in state["spaces"].items():
                if sp.get("type") == "Colony" and sp.get(C.FORT_BRI, 0) == 0:
                    push_history(state, "BRITISH plays Event for Fort placement")
                    return True

        if "Regular" in text:
            for sid, sp in state["spaces"].items():
                if sp.get("type") in ("City", "Colony"):
                    push_history(state, "BRITISH plays Event for Regular placement")
                    return True

        if "remove" in text or "casualty" in text.lower() or "Battle" in text or "Skirmish" in text:
            if any(k in text for k in ["Patriot", "Militia", "Continental"]):
                push_history(state, "BRITISH plays Event for casualties")
                return True

        brit_cities = sum(
            1
            for c in CITIES
            if state["spaces"].get(c, {}).get("control") == "BRITISH"
        )
        if brit_cities >= 5:
            roll = state["rng"].randint(1, 6)
            state.setdefault("rng_log", []).append(("D6", roll))
            if roll >= 5:
                push_history(state, "BRITISH plays Event by die roll")
                return True

        return False

    def _can_garrison(self, state: Dict) -> bool:
        refresh_control(state)
        regs = sum(sp.get(C.REGULAR_BRI, 0) for sp in state["spaces"].values())
        if regs < 10:
            return False
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            if sp.get("control") == "REBELLION" and sp.get("Patriot_Fort", 0) == 0:
                return True
        return False

    def _can_muster(self, state: Dict) -> bool:
        avail = state.get("available", {}).get(C.REGULAR_BRI, 0)
        import random
        return avail > random.randint(1, 6)

    def _can_battle(self, state: Dict) -> bool:
        refresh_control(state)
        for sp in state["spaces"].values():
            rebels = sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0)
            if rebels >= 2 and sp.get(C.REGULAR_BRI, 0) > rebels:
                return True
        return False

    def _can_march(self, state: Dict) -> bool:
        # Assume March is always possible if any British Regulars exist
        return any(sp.get(C.REGULAR_BRI, 0) for sp in state["spaces"].values())
