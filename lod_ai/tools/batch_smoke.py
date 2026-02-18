#!/usr/bin/env python3
"""
Batch smoke test: run 20 zero-player games per scenario (60 total).

Usage:
    python -m lod_ai.tools.batch_smoke          # full 60-game batch
    python -m lod_ai.tools.batch_smoke --single  # single game sanity check

Records per-game results and prints an aggregate summary table.
Writes detailed results to lod_ai/tools/batch_results.json.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

# Redirect stdin to /dev/null so any accidental interactive prompt
# raises EOFError instead of blocking.
_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.victory import _summarize_board, _british_margin, _patriot_margin, _french_margin, _indian_margin
from lod_ai import rules_consts as C

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCENARIOS = ["1775", "1776", "1778"]
SEEDS_PER_SCENARIO = 20
CARD_SAFETY_LIMIT = 200
RESULTS_PATH = Path(__file__).resolve().parent / "batch_results.json"

# ---------------------------------------------------------------------------
# Single-game runner
# ---------------------------------------------------------------------------

def _determine_winner_from_margins(state: dict) -> str:
    """Use the victory margin functions to determine which faction won."""
    tallies = _summarize_board(state)
    brit1, brit2 = _british_margin(tallies)
    pat1, pat2 = _patriot_margin(tallies)
    fre1, fre2 = _french_margin(tallies)
    ind1, ind2 = _indian_margin(tallies)

    if brit1 > 0 and brit2 > 0:
        return C.BRITISH
    if pat1 > 0 and pat2 > 0:
        return C.PATRIOTS
    if tallies["treaty_of_alliance"] and fre1 > 0 and fre2 > 0:
        return C.FRENCH
    if ind1 > 0 and ind2 > 0:
        return C.INDIANS
    return "UNKNOWN"


def _check_game_over(state: dict) -> str | None:
    """Scan history for a winner or victory message. Return winner or None."""
    history = state.get("history", [])
    for entry in reversed(history[-40:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Winner:" in msg:
            # Extract faction name after "Winner:"
            parts = msg.split("Winner:")
            if len(parts) >= 2:
                faction = parts[1].strip().split()[0].strip("()")
                return faction
        if "Victory achieved" in msg:
            return _determine_winner_from_margins(state)
    return None


def run_one_game(scenario: str, seed: int) -> Dict[str, Any]:
    """Run a single zero-player game. Returns a result dict."""
    result: Dict[str, Any] = {
        "scenario": scenario,
        "seed": seed,
        "winner": None,
        "end_reason": None,
        "cards_played": 0,
        "error": None,
        "traceback": None,
    }
    try:
        state = build_state(scenario, seed=seed)
        engine = Engine(initial_state=state, use_cli=False)
        engine.set_human_factions([])  # all bots

        cards_played = 0
        while cards_played < CARD_SAFETY_LIMIT:
            card = engine.draw_card()
            if card is None:
                result["end_reason"] = "DECK_EXHAUSTED"
                break

            engine.play_card(card, human_decider=None)
            cards_played += 1

            winner = _check_game_over(engine.state)
            if winner:
                result["winner"] = winner
                result["end_reason"] = "WINNER"
                break
        else:
            result["end_reason"] = "TIMEOUT"

        result["cards_played"] = cards_played

    except EOFError:
        result["end_reason"] = "INTERACTIVE_PROMPT"
        result["error"] = "Engine tried to read interactive input in zero-player mode"
        result["traceback"] = traceback.format_exc()
    except Exception as exc:
        result["end_reason"] = "CRASH"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()

    return result


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]], label: str) -> None:
    """Print a summary table for a list of game results."""
    total = len(results)
    if total == 0:
        return

    wins: Counter[str] = Counter()
    end_reasons: Counter[str] = Counter()
    total_cards = 0

    for r in results:
        end_reasons[r["end_reason"] or "UNKNOWN"] += 1
        if r["winner"] and r["end_reason"] == "WINNER":
            wins[r["winner"]] += 1
        total_cards += r.get("cards_played", 0)

    avg_cards = total_cards / total if total else 0

    print(f"\n{'=' * 60}")
    print(f"  {label}  ({total} games)")
    print(f"{'=' * 60}")
    print(f"  {'Faction':<16} {'Wins':>6}")
    print(f"  {'-' * 24}")
    for faction in ["BRITISH", "PATRIOTS", "INDIANS", "FRENCH", "VICTORY"]:
        if wins[faction]:
            print(f"  {faction:<16} {wins[faction]:>6}")
    draws = end_reasons.get("DRAW", 0)
    if draws:
        print(f"  {'DRAW':<16} {draws:>6}")
    print(f"  {'-' * 24}")
    print(f"  {'Deck exhausted':<16} {end_reasons.get('DECK_EXHAUSTED', 0):>6}")
    print(f"  {'Timeouts':<16} {end_reasons.get('TIMEOUT', 0):>6}")
    print(f"  {'Crashes':<16} {end_reasons.get('CRASH', 0):>6}")
    print(f"  {'Interactive hang':<16} {end_reasons.get('INTERACTIVE_PROMPT', 0):>6}")
    print(f"  {'Avg cards played':<16} {avg_cards:>6.1f}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    single_mode = "--single" in sys.argv

    if single_mode:
        print("Running single sanity-check game: scenario=1775, seed=1 ...")
        result = run_one_game("1775", 1)
        print(f"  end_reason={result['end_reason']}, winner={result['winner']}, "
              f"cards_played={result['cards_played']}")
        if result["error"]:
            print(f"  ERROR: {result['error']}")
            if result["traceback"]:
                print(result["traceback"])
        return

    print(f"Running batch smoke test: {len(SCENARIOS)} scenarios x {SEEDS_PER_SCENARIO} seeds "
          f"= {len(SCENARIOS) * SEEDS_PER_SCENARIO} games")
    print(f"Safety limit: {CARD_SAFETY_LIMIT} cards per game\n")

    all_results: List[Dict[str, Any]] = []
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for scenario in SCENARIOS:
        for seed in range(1, SEEDS_PER_SCENARIO + 1):
            tag = f"[{scenario} seed={seed:>2}]"
            sys.stdout.write(f"  {tag} ... ")
            sys.stdout.flush()

            result = run_one_game(scenario, seed)
            all_results.append(result)
            by_scenario[scenario].append(result)

            status = result["end_reason"] or "?"
            extra = ""
            if result["winner"]:
                extra = f" -> {result['winner']}"
            if result["error"]:
                extra += f"  ERR: {result['error'][:60]}"
            print(f"{status} ({result['cards_played']} cards){extra}")

    # Per-scenario summaries
    for scenario in SCENARIOS:
        _print_summary(by_scenario[scenario], f"Scenario {scenario}")

    # Overall summary
    _print_summary(all_results, "Overall")

    # Write JSON results
    serialisable = []
    for r in all_results:
        entry = dict(r)
        # traceback can be very long; keep it but truncate
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        serialisable.append(entry)

    RESULTS_PATH.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    print(f"Full results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
