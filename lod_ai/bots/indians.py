# bots/indians.py
"""
Solo‑bot helper for the Indians faction.
Originally this module only covered the very top of the flow‑chart from the
reference (“Indian bot flowchart and reference.txt”).  It now includes the next
couple of decisions so that the bot may also select **War‑Path** and **Scout**
when the conditions arise.

Simplified flow implemented here:

  • If broke  ..................................  TRADE
  • Else if meaningful Raid possible ...........  RAID
  • Else if a Province has War Party & Regulars   SCOUT
  • Else if War‑Path target exists .............  WAR_PATH
  • Else .......................................  GATHER
"""

import random
from lod_ai import rules_consts as C


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

    def scout_options():
        """Return list of (src, dst) province pairs for possible Scout."""
        opts = []
        for src, sp in spaces.items():
            if "City" in src:
                continue
            wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
            if wp == 0 or sp.get(C.REGULAR_BRI, 0) == 0:
                continue
            for dst in sp.get("adj", []):
                if "City" in dst:
                    continue
                opts.append((src, dst))
        return opts

    def war_path_targets():
        """Return Provinces containing WP-U with enemy pieces."""
        targets = []
        enemy_tags = [C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE, C.FORT_PAT]
        for n, s in spaces.items():
            if s.get(C.WARPARTY_U, 0) == 0:
                continue
            if any(s.get(tag, 0) > 0 for tag in enemy_tags):
                targets.append(n)
        return targets

    # ---------- branch 1 – broke  ------------------------------------
    if res <= 1:
        trg = can_trade()
        return ("TRADE", trg) if trg else ("GATHER", None)

    # ---------- branch 2 – RAID if it helps the crown -----------------
    raid = raid_targets()
    if raid:
        return ("RAID", random.choice(raid))

    # ---------- branch 3 – Scout if Regulars present -----------------
    scouts = scout_options()
    if scouts:
        src, dst = random.choice(scouts)
        return ("SCOUT", f"{src}>{dst}")

    # ---------- branch 4 – War Path if enemy adjacent ----------------
    wp = war_path_targets()
    if wp:
        return ("WAR_PATH", random.choice(wp))

    # ---------- branch 5 – otherwise Gather for bodies ---------------
    return ("GATHER", None)
