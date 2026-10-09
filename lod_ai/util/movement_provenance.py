"""Track move-once eligibility when an intervening SA flips or removes units.

Counters of one type and posture are interchangeable. Keep every feasible
assignment of previously moved counters, then narrow those assignments when
the player moves a later group. This allows all legal choices without letting
activation erase the fact that a unit has already moved.
"""
from __future__ import annotations


class MovementProvenance:
    def __init__(self, underground: str, active: str):
        self.underground = underground
        self.active = active
        self.moved: dict[str, set[tuple[int, int]]] = {}

    def _possibilities(self, sid: str) -> set[tuple[int, int]]:
        return self.moved.get(sid, {(0, 0)})

    def snapshot(self, state: dict) -> dict[str, tuple[int, int]]:
        return {
            sid: (sp.get(self.underground, 0), sp.get(self.active, 0))
            for sid, sp in state["spaces"].items()
        }

    def reconcile_special(self, before: dict, state: dict) -> None:
        """Apply own-faction SA activation/removal to all possible identities.

        Persuasion/Trade activate; Partisans/War Path activate and may
        sacrifice one of those newly activated units; Plunder removes.
        These are the own-unit changes available during Rally/Gather.
        """
        after = self.snapshot(state)
        for sid, (old_u, old_a) in before.items():
            new_u, new_a = after[sid]
            if (old_u, old_a) == (new_u, new_a):
                continue
            possible = set()
            if new_u <= old_u and new_a >= old_a:
                activated = old_u - new_u
                sacrificed = activated - (new_a - old_a)
                if not 0 <= sacrificed <= activated:
                    raise ValueError("Unexpected unit placement during Special Activity.")
                for moved_u, moved_a in self._possibilities(sid):
                    # Which of the activated units had already moved?
                    for flipped_moved in range(
                            max(0, activated - (old_u - moved_u)),
                            min(activated, moved_u) + 1):
                        # Any sacrifice is one of the newly activated
                        # units (§4.3.2/§4.4.2), not an old Active unit.
                        for removed_moved in range(
                                max(0, sacrificed - (activated - flipped_moved)),
                                min(sacrificed, flipped_moved) + 1):
                            possible.add((moved_u - flipped_moved,
                                          moved_a + flipped_moved - removed_moved))
            elif new_u <= old_u and new_a <= old_a:
                removed_u, removed_a = old_u - new_u, old_a - new_a
                for moved_u, moved_a in self._possibilities(sid):
                    for gone_u in range(max(0, removed_u - (old_u - moved_u)),
                                        min(removed_u, moved_u) + 1):
                        for gone_a in range(max(0, removed_a - (old_a - moved_a)),
                                            min(removed_a, moved_a) + 1):
                            possible.add((moved_u - gone_u, moved_a - gone_a))
            else:
                raise ValueError("Unexpected unit movement during Special Activity.")
            if not possible:
                raise ValueError("Special Activity has no legal unit assignment.")
            self.moved[sid] = possible

    def movable(self, state: dict, sid: str) -> int:
        sp = state["spaces"][sid]
        total = sp.get(self.underground, 0) + sp.get(self.active, 0)
        return max(total - u - a for u, a in self._possibilities(sid))

    def take(self, state: dict, sid: str, count: int, *,
             active_first: bool = False) -> tuple[int, int]:
        """Choose unmoved units in the requested posture order."""
        sp = state["spaces"][sid]
        underground = sp.get(self.underground, 0)
        active = sp.get(self.active, 0)
        choices: dict[tuple[int, int], set[tuple[int, int]]] = {}
        for moved_u, moved_a in self._possibilities(sid):
            if active_first:
                take_a = min(count, active - moved_a)
                take_u = count - take_a
            else:
                take_u = min(count, underground - moved_u)
                take_a = count - take_u
            if (0 <= take_u <= underground - moved_u
                    and 0 <= take_a <= active - moved_a):
                choices.setdefault((take_u, take_a), set()).add((moved_u, moved_a))
        if not choices:
            raise ValueError(f"{sid}: not enough unmoved units.")
        take_u, take_a = max(choices, key=lambda take: take[1] if active_first else take[0])
        self.moved[sid] = choices[(take_u, take_a)]
        return take_u, take_a

    def arrive_and_hide(self, sid: str, count: int) -> None:
        """Arrivals have moved; all units in the destination become Underground."""
        self.moved[sid] = {(u + a + count, 0)
                           for u, a in self._possibilities(sid)}

    def take_exact(self, state: dict, sid: str, underground: int, active: int) -> None:
        """Narrow identities to a legal explicitly chosen March group."""
        sp = state["spaces"][sid]
        possible = {(u, a) for u, a in self._possibilities(sid)
                    if sp.get(self.underground, 0) - u >= underground
                    and sp.get(self.active, 0) - a >= active}
        if not possible:
            raise ValueError(f"{sid}: not enough unmoved units of the selected facing.")
        self.moved[sid] = possible

    def arrive(self, sid: str, underground: int, active: int) -> None:
        self.moved[sid] = {(u + underground, a + active)
                           for u, a in self._possibilities(sid)}

    def activate_moved(self, sid: str, count: int) -> None:
        """Mandatory March activation affects the moving group itself."""
        possible = {(u - count, a + count) for u, a in self._possibilities(sid)
                    if u >= count}
        if not possible:
            raise ValueError("Cannot activate more moved Underground units than arrived.")
        self.moved[sid] = possible
