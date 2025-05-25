# bots/indians.py
"""
Solo‑bot helper for the Indians faction.
Implements the top three branches of the non‑player flow‑chart (LoD 8.7):

  • If broke  ..................................  TRADE
  • Else if meaningful Raid possible ...........  RAID
  • Else .......................................  GATHER

Keeps things lightweight—no War‑Path/Scout yet, but those can bolt on later.
"""

import random


def choose_command(state):
    res = state["resources"]["INDIANS"]

    # ---------- helper lambdas ----------------------------------------
    spaces = state["spaces"]

    def provinces_with(tag):
        return [n for n, s in spaces.items() if s.get(tag, 0) > 0 and "City" not in n]

    def can_trade():
        for n, s in spaces.items():
            if s.get("Indian_Village") and s.get("Indian_WP_U", 0) > 0:
                return n
        return None

    def raid_targets():
        # Provinces at Opposition *and* with / adjacent to Underground WP
        tgs = []
        for n, s in spaces.items():
            if s.get("Opposition", 0) == 0 or "City" in n:
                continue
            if s.get("Indian_WP_U", 0):
                tgs.append(n)
                continue
            # check adjacency
            for m, t in spaces.items():
                if m == n or "City" in m:
                    continue
                if t.get("Indian_WP_U", 0) and n in t.get("adj", []):
                    tgs.append(n)
                    break
        return tgs

    # ---------- branch 1 – broke  ------------------------------------
    if res <= 1:
        trg = can_trade()
        return ("TRADE", trg) if trg else ("GATHER", None)

    # ---------- branch 2 – RAID if it helps the crown -----------------
    raid = raid_targets()
    if raid:
        return ("RAID", random.choice(raid))

    # ---------- branch 3 – otherwise Gather for bodies ---------------
    return ("GATHER", None)
