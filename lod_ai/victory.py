"""Victory checks and final scoring under §§7.1–7.3 and solitaire §8.8."""

from lod_ai.rules_consts import BRITISH, PATRIOTS, FRENCH, INDIANS, FORT_PAT, VILLAGE
from lod_ai.map.adjacency import population as _map_population
from lod_ai.rules_consts import BLOCKADE

# --------------------------------------------------------------------------- #
#  Board summarizer – converts the live map into the tallies used below       #
# --------------------------------------------------------------------------- #
def _summarize_board(state) -> dict:
    """
    Derive total Support, Opposition, forts, Villages, and casualty counts
    from the current game state.  Returns a dict with the keys that the
    margin helpers expect.

    Per Rules §1.6.2-1.6.3:
      Total Support    = sum(level × population) for spaces at Support
      Total Opposition = sum(|level| × population) for spaces at Opposition
    """
    support_total     = 0
    opposition_total  = 0
    patriot_forts     = 0
    villages          = 0

    for sid, sp in state["spaces"].items():
        lvl = state.get("support", {}).get(sid, 0)
        # §1.9: a Blockaded City's population counts 0 for Support
        # (Session 46, C1).
        pop = _map_population(sid)
        if lvl > 0:
            blockaded = state.get("markers", {}).get(BLOCKADE, {}).get("on_map", ())
            support_total += lvl * (0 if sid in blockaded else pop)
        elif lvl < 0:
            opposition_total += abs(lvl) * pop

        patriot_forts += sp.get(FORT_PAT, 0)
        villages      += sp.get(VILLAGE, 0)

    # Casualties boxes—assumes these counters exist in state
    cbc = state.get("cbc", 0)   # cumulative British casualties
    crc = state.get("crc", 0)   # cumulative Rebellion casualties

    toa = state.get("toa_played", state.get("treaty_of_alliance", False))
    return {
        "support":   support_total,
        "opposition": opposition_total,
        "cbc":       cbc,
        "crc":       crc,
        "forts":     {PATRIOTS: patriot_forts},
        "villages":  villages,
        "treaty_of_alliance": bool(toa),
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
    cond2 = (st["forts"][PATRIOTS] + 3) - st["villages"]
    return cond1, cond2


def _french_margin(st) -> tuple[int, int]:
    cond1 = st["opposition"] - st["support"] - 10
    cond2 = st["cbc"] - st["crc"]
    return cond1, cond2


def _indian_margin(st) -> tuple[int, int]:
    cond1 = st["support"] - st["opposition"] - 10
    cond2 = (st["villages"] - 3) - st["forts"][PATRIOTS]
    return cond1, cond2

_ORDER = (PATRIOTS, BRITISH, FRENCH, INDIANS)
_SOLO_NP_ORDER = (FRENCH, INDIANS, PATRIOTS, BRITISH)


def player_groups(state) -> list[tuple[str, ...]]:
    """Read explicit ownership; never infer a shared player from two factions.

    Older saves selected one faction per player. A single human faction is
    unambiguously a solitaire game; multiple human factions remain separate
    unless the user has supplied an ownership map.
    """
    humans = set(state.get("human_factions") or ())
    groups = state.get("player_factions")
    if groups is None:
        return [(f,) for f in _ORDER if f in humans]
    normalized = [tuple(group) for group in groups if group]
    owned = [f for group in normalized for f in group]
    if len(owned) != len(set(owned)) or set(owned) != humans:
        raise ValueError("player_factions must assign every human faction exactly once")
    for group in normalized:
        if len(group) > 1 and set(group) not in ({BRITISH, INDIANS}, {PATRIOTS, FRENCH}):
            raise ValueError("A player may control one faction or both allied factions")
    return normalized


def _totals(tallies) -> dict:
    # §7.3 prints raw sums without the -10 victory-check threshold.
    scores = {
        BRITISH: sum(_british_margin(tallies)) + 10,
        PATRIOTS: sum(_patriot_margin(tallies)) + 10,
        FRENCH: sum(_french_margin(tallies)) + 10,
        INDIANS: sum(_indian_margin(tallies)) + 10,
    }
    if not tallies["treaty_of_alliance"]:
        scores[FRENCH] = float("-inf")
    return scores


def _solo_np_winner(totals, humans):
    bots = [f for f in _SOLO_NP_ORDER if f not in humans]
    return max(bots, key=lambda f: (totals[f], -_SOLO_NP_ORDER.index(f)))


def final_scoring(state) -> None:
    """Resolve final Support Phase scoring, including combined and solo play."""
    totals = _totals(_summarize_board(state))
    humans = set(state.get("human_factions") or ())
    groups = player_groups(state)
    push_history(state, "Final Scoring – " + "  ".join(f"{f}:{totals[f]}" for f in _ORDER))
    placement = sorted(_ORDER, key=lambda f: (totals[f], f not in humans,
                                              -_ORDER.index(f)), reverse=True)
    push_history(state, "Placements (7.1): " + " > ".join(placement))

    result: dict = {"type": "final_scoring", "margins": totals, "outcome": "victory"}
    if len(groups) == 1:
        group = groups[0]
        opponent = _solo_np_winner(totals, humans)
        margin = min(totals[f] for f in group)
        gap = margin - totals[opponent]
        result.update(gap=gap, human_won=gap >= 6)
        # §8.8 requires the highest margin; the printed stalemate band is
        # 1–5. A tied/lower player margin loses (Non-player wins ties).
        if gap <= 0:
            winner = opponent
        elif gap <= 5:
            result.update(winner=None, outcome="stalemate")
            state["victory_result"] = result
            push_history(state, f"Stalemate: player margin lead {gap} (Rule 7.3; 8.8)")
            return
        else:
            winner = " + ".join(group)
        push_history(state, f"One-player margin lead: {gap} (8.8)")
    else:
        # §7.3: a player controlling a side scores its LOWER margin.
        competitors = [(f,) for f in _ORDER if f not in humans] + groups
        def rank(group):
            return (min(totals[f] for f in group),
                    all(f not in humans for f in group),
                    -min(_ORDER.index(f) for f in group))
        winner = " + ".join(max(competitors, key=rank))
    result["winner"] = winner
    state["victory_result"] = result
    push_history(state, f"Winner: {winner} (Rule 7.3{' / 8.8' if len(groups) == 1 else ''})")


def check(state) -> bool:
    """Resolve a Winter Quarters Victory Check, returning whether play ends."""
    tallies = _summarize_board(state)
    margins = {BRITISH: _british_margin(tallies),
               PATRIOTS: _patriot_margin(tallies),
               FRENCH: _french_margin(tallies),
               INDIANS: _indian_margin(tallies)}
    push_history(state, "Victory Check  –  " + "  ".join(
        f"{label}({margins[f][0]},{margins[f][1]})"
        for label, f in (("BRI", BRITISH), ("PAT", PATRIOTS),
                         ("FRE", FRENCH), ("IND", INDIANS))))
    passed = {f for f, (first, second) in margins.items() if first > 0 and second > 0
              and (f != FRENCH or tallies["treaty_of_alliance"])}
    humans = set(state.get("human_factions") or ())
    groups = player_groups(state)
    totals = _totals(tallies)
    bot_passes = passed - humans
    solo = len(groups) == 1
    difficulty_loss = (solo and state.get("solo_difficulty", False)
                       and state.get("winter_quarters_count", 0) >= 2
                       and min(totals[f] for f in groups[0]) <
                           max(totals[f] for f in _ORDER if f not in humans))
    if solo:
        if not bot_passes and not difficulty_loss:
            return False  # §8.8: the lone player never wins a Victory Phase.
        winner = _solo_np_winner(totals, humans)
    elif bot_passes:
        winner = min(bot_passes, key=_ORDER.index)
    else:
        # §7.2 Combined Victory requires BOTH factions' conditions.
        winning_groups = [group for group in groups if set(group) <= passed]
        if not winning_groups:
            return False
        group = min(winning_groups, key=lambda g: min(_ORDER.index(f) for f in g))
        winner = " + ".join(group)
    state["victory_result"] = {"type": "victory_check", "outcome": "victory",
                               "winner": winner, "margins": totals,
                               "human_won": not (bot_passes or difficulty_loss)}
    if bot_passes:
        passer = min(bot_passes, key=_ORDER.index)
        push_history(state, f"Victory Check passed by {passer} (7.2)")
    elif difficulty_loss:
        push_history(state, "One-player difficulty: Non-player margin exceeds player margin (8.8)")
    else:
        push_history(state, f"Victory Check passed by {winner} (7.2)")
    if humans and (bot_passes or difficulty_loss):
        push_history(state, "Non-player victory — all players lose equally (7.1)")
    push_history(state, f"Winner: {winner} (Rule {'8.8' if solo else '7.2'})")
    return True
