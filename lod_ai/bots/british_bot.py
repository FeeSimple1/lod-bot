# lod_ai/bots/british_bot.py
from typing import Dict, List
from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.commands import garrison, muster, march, battle
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
    # ---- Command executors  (stubs – fill bullets later) ----
    # ---------------------------------------------------------
    def _garrison(self, state: Dict) -> bool:
        """Very simple Garrison: move one Regular to a rebel City."""
        refresh_control(state)
        target = None
        for name in CITIES:
            sp = state["spaces"].get(name, {})
            if sp.get("control") == "REBELLION" and sp.get("Patriot_Fort", 0) == 0:
                target = name
                break
        if not target:
            return False

        origins = [n for n, sp in state["spaces"].items()
                   if sp.get(C.REGULAR_BRI, 0) > 0 and n != target]
        if not origins:
            return False

        move_map = {orig: {target: 1} for orig in origins[:2]}
        garrison.execute(state, "BRITISH", {}, move_map)
        return True

    def _muster(self, state: Dict) -> bool:
        """Place a Regular and Tory in the richest available space."""
        spaces = sorted(state["spaces"].items(),
                        key=lambda kv: kv[1].get("population", 0),
                        reverse=True)
        if not spaces:
            return False
        target = spaces[0][0]
        selected = [target]
        muster.execute(
            state,
            "BRITISH",
            {},
            selected,
            regular_plan={"space": target, "n": 1},
            tory_plan={target: 1},
        )
        return True

    def _march(self, state: Dict) -> bool:
        """Move one Regular from a random space to an adjacent one."""
        for src, sp in state["spaces"].items():
            if sp.get(C.REGULAR_BRI, 0) > 0:
                dests = sp.get("adj", [])
                if dests:
                    dst = dests[0]
                    march.execute(
                        state,
                        "BRITISH",
                        {},
                        [src],
                        [dst],
                        bring_escorts=False,
                        limited=True,
                    )
                    return True
        return False

    def _battle(self, state: Dict) -> bool:
        """Battle in the first space where British outnumber rebels."""
        refresh_control(state)
        for name, sp in state["spaces"].items():
            rebels = sp.get(C.REGULAR_PAT, 0) + sp.get(C.MILITIA_A, 0)
            if rebels >= 1 and sp.get(C.REGULAR_BRI, 0) > rebels:
                battle.execute(state, "BRITISH", {}, [name])
                return True
        return False

    # ---------------------------------------------------------
    # ---- Flow-chart pre-condition tests ---------------------
    # ---------------------------------------------------------
    # each _can_* mirrors the italic opening sentence of §8.4.x

    def _faction_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Placeholder for the 'Event or Command?' bullets (Rule 8.4)."""
        return self._brit_event_conditions(state, card)

    def _brit_event_conditions(self, state: Dict, card: Dict) -> bool:
        """Very rough implementation of the Event-or-Command bullets."""
        text = (card.get("unshaded_event") or "")
        support = sum(sp.get("Support", 0) for sp in state["spaces"].values())
        opposition = sum(sp.get("Opposition", 0) for sp in state["spaces"].values())

        if opposition > support and "Support" in text:
            push_history(state, "BRITISH plays Event for support shift")
            return True

        keywords = ["Regular", "Tory", "Fort"]
        if any(k in text for k in keywords):
            push_history(state, "BRITISH plays Event for placement")
            return True

        if "remove" in text and any(k in text for k in ["Patriot", "Militia", "Continental"]):
            push_history(state, "BRITISH plays Event for casualties")
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
