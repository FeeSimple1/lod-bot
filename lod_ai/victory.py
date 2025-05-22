"""
Victory evaluation  (Rules 7.1 & 7.2)

Assumed state keys
------------------
state["support"]            : int   # 0-30   (spaces at Active/Passive Support)
state["opposition"]         : int   # 0-30   (spaces at Active/Passive Opposition)
state["cbc"]                : int   # Cumulative British Casualties
state["crc"]                : int   # Cumulative Rebellion Casualties
state["forts"]["Patriot"]   : int   # Patriot Forts on map
state["villages"]           : int   # Indian Villages on map
state["treaty_of_alliance"] : bool  # Treaty of Alliance Event resolved?

If your project uses different keys, adjust the look-ups below.
"""

from lod_ai.rules_consts import FORT_PAT, VILLAGE

# --------------------------------------------------------------------------- #
#  Board summarizer – converts the live map into the tallies used below       #
# --------------------------------------------------------------------------- #
def _summarize_board(state) -> dict:
    """
    Derive total Support, Opposition, forts, Villages, and casualty counts
    from the current game state.  Returns a dict with the keys that the
    margin helpers expect.
    """
    support_total     = 0
    opposition_total  = 0
    patriot_forts     = 0
    villages          = 0

    for sid, sp in state["spaces"].items():
        lvl = state["support"].get(sid, 0)
        if lvl > 0:
            support_total += lvl
        elif lvl < 0:
            opposition_total += abs(lvl)

        patriot_forts += sp.get(FORT_PAT, 0)
        villages      += sp.get(VILLAGE, 0)

    # Casualties boxes—assumes these counters exist in state
    cbc = state.get("cbc", 0)   # cumulative British casualties
    crc = state.get("crc", 0)   # cumulative Rebellion casualties

    return {
        "support":   support_total,
        "opposition": opposition_total,
        "cbc":       cbc,
        "crc":       crc,
        "forts":     {"Patriot": patriot_forts},
        "villages":  villages,
        "treaty_of_alliance": state.get("treaty_of_alliance", False),
    }

from lod_ai.util.history import push_history

# --------------------------------------------------------------------------- #
# Helper functions                                                            #
# --------------------------------------------------------------------------- #
def _british_margin(t):
    sup_minus_opp = t["support"] - t["opposition"]
    crc_vs_cbc    = t["crc"] - t["cbc"]
    return sup_minus_opp - 10, crc_vs_cbc


def _patriot_margin(st) -> tuple[int, int]:
    cond1 = st["opposition"] - st["support"] - 10
    cond2 = (st["forts"]["Patriot"] + 3) - st["villages"]
    return cond1, cond2


def _french_margin(st) -> tuple[int, int]:
    cond1 = st["opposition"] - st["support"] - 10
    cond2 = st["cbc"] - st["crc"]
    return cond1, cond2


def _indian_margin(st) -> tuple[int, int]:
    cond1 = st["support"] - st["opposition"] - 10
    cond2 = (st["villages"] - 3) - st["forts"]["Patriot"]
    return cond1, cond2

# --------------------------------------------------------------------------- #
# 7.3  Final-Round Scoring                                                    #
# --------------------------------------------------------------------------- #
def final_scoring(state) -> None:
    """
    Apply Rule 7.3 when the final Winter-Quarters Support Phase ends.
    Adds the two victory-condition margins for each faction and logs
    the totals.  Declares the winner (or tie order) per Rule 7.1.
    """
    t = _summarize_board(state)

    totals = {
        "British":  sum(_british_margin(t)),
        "Patriots": sum(_patriot_margin(t)),
        "French":   sum(_french_margin(t)),
        "Indians":  sum(_indian_margin(t)),
    }

    # Treaty requirement: French score only if ToA played
    if not t["treaty_of_alliance"]:
        totals["French"] = float("-inf")

    # Rank: higher total wins; ties resolved BRI > PAT > FRE > IND
    order = ["Patriots", "British", "French", "Indians"]
    winner = max(order, key=lambda f: totals[f])

    log = "Final Scoring – " + "  ".join(f"{f}:{totals[f]}" for f in order)
    push_history(state, log)
    push_history(state, f"Winner: {winner} (Rule 7.3)")

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def check(state) -> bool:
    """
    Return True if *any* faction meets both of its victory conditions
    at the Winter-Quarters Victory-Check Phase (Rule 6.1 & 7.2).
    Logs margins for debugging.

    Final-round Support-Phase scoring (Rule 7.3) will be added later.
    """
    tallies = _summarize_board(state)
    brit1, brit2 = _british_margin(tallies)
    pat1, pat2   = _patriot_margin(tallies)
    fre1, fre2   = _french_margin(tallies)
    ind1, ind2   = _indian_margin(tallies)

    log = (
        f"Victory Check  –  "
        f"BRI({brit1},{brit2})  PAT({pat1},{pat2})  "
        f"FRE({fre1},{fre2})  IND({ind1},{ind2})"
    )
    push_history(state, log)

    british_win = (brit1 > 0 and brit2 > 0)
    patriot_win = (pat1 > 0 and pat2 > 0)
    french_win  = (
        tallies["treaty_of_alliance"]
        and fre1 > 0 and fre2 > 0
    )
    indian_win  = (ind1 > 0 and ind2 > 0)

    return british_win or patriot_win or french_win or indian_win