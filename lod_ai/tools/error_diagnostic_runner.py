#!/usr/bin/env python3
"""
Full 60-game diagnostic runner that captures bot exception details across
all scenarios and seeds.

Runs 20 games per scenario (1775, 1776, 1778) with seeds 1-20, all factions
as bots. Captures both bot_error (unhandled exceptions) and illegal_action
(command rejected by validation) pass reasons.

Outputs:
  - bot_error_log_full.json: raw error/pass data for all 60 games
  - Console summary for immediate inspection

Usage:
    python -m lod_ai.tools.error_diagnostic_runner
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback as _tb_module
from collections import Counter, defaultdict
from pathlib import Path

# Redirect stdin to /dev/null so any accidental interactive prompt
# raises EOFError instead of blocking.
_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai import rules_consts as C

CARD_SAFETY_LIMIT = 200
OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = OUTPUT_DIR / "bot_error_log_full.json"
FACTIONS = [C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH]
SCENARIOS = ["1775", "1776", "1778"]
SEEDS_PER_SCENARIO = 20


def run_single_game(scenario: str, seed: int) -> dict:
    """Run a single zero-player game and return diagnostics."""
    state = build_state(scenario, seed=seed)
    engine = Engine(initial_state=state, use_cli=False)
    engine.set_human_factions([])  # all bots

    cards_played = 0
    winner = None

    # Collect all _card_turn_log entries across the game
    all_turn_logs: list[dict] = []

    while cards_played < CARD_SAFETY_LIMIT:
        card = engine.draw_card()
        if card is None:
            break

        engine.play_card(card, human_decider=None)
        cards_played += 1

        # Collect turn log entries from this card
        card_turn_log = engine.state.get("_card_turn_log", [])
        for entry in card_turn_log:
            entry["card_number"] = card.get("id")
            entry["scenario"] = scenario
            entry["seed"] = seed
        all_turn_logs.extend(card_turn_log)

        # Check for winner
        history = engine.state.get("history", [])
        for entry in reversed(history[-20:]):
            msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
            if "Winner:" in msg:
                parts = msg.split("Winner:")
                if len(parts) >= 2:
                    winner = parts[1].strip().split()[0].strip("()")
                    break
            if "Victory achieved" in msg:
                winner = "DETERMINED_FROM_MARGINS"
                break
        if winner:
            break

    # Extract bot_error log (unhandled exceptions with tracebacks)
    bot_error_log = engine.state.get("_bot_error_log", [])
    for entry in bot_error_log:
        entry["scenario"] = scenario
        entry["seed"] = seed

    return {
        "scenario": scenario,
        "seed": seed,
        "cards_played": cards_played,
        "winner": winner,
        "bot_errors": bot_error_log,
        "turn_logs": all_turn_logs,
    }


def run() -> None:
    total_games = len(SCENARIOS) * SEEDS_PER_SCENARIO
    print(f"Running {total_games} games ({SEEDS_PER_SCENARIO} per scenario) ...")
    print(f"Scenarios: {', '.join(SCENARIOS)}")
    print()

    all_results: list[dict] = []
    all_bot_errors: list[dict] = []
    all_turn_logs: list[dict] = []

    game_num = 0
    start_time = time.time()

    for scenario in SCENARIOS:
        for seed in range(1, SEEDS_PER_SCENARIO + 1):
            game_num += 1
            label = f"[{game_num}/{total_games}] {scenario}/seed={seed}"
            try:
                result = run_single_game(scenario, seed)
                n_errors = len(result["bot_errors"])
                n_turns = len(result["turn_logs"])
                print(f"  {label}: {result['cards_played']} cards, "
                      f"winner={result['winner'] or 'none'}, "
                      f"bot_errors={n_errors}, turns={n_turns}")
                all_results.append(result)
                all_bot_errors.extend(result["bot_errors"])
                all_turn_logs.extend(result["turn_logs"])
            except Exception as exc:
                print(f"  {label}: GAME CRASHED: {type(exc).__name__}: {exc}")
                all_results.append({
                    "scenario": scenario,
                    "seed": seed,
                    "cards_played": 0,
                    "winner": None,
                    "bot_errors": [],
                    "turn_logs": [],
                    "game_crash": {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "traceback_str": _tb_module.format_exc(),
                    },
                })

    elapsed = time.time() - start_time
    print(f"\nAll {total_games} games completed in {elapsed:.1f}s")

    # ── Aggregate statistics ──────────────────────────────────────────────

    # 1. Pass reason breakdown across ALL turns
    pass_reasons: Counter = Counter()
    pass_by_faction_reason: dict[str, Counter] = defaultdict(Counter)
    total_turns_by_faction: Counter = Counter()
    for entry in all_turn_logs:
        faction = entry.get("faction", "UNKNOWN")
        total_turns_by_faction[faction] += 1
        action = entry.get("action")
        if action == "pass":
            reason = entry.get("pass_reason", "unknown")
            pass_reasons[reason] += 1
            pass_by_faction_reason[faction][reason] += 1

    print("\n=== PASS REASON BREAKDOWN (all 60 games) ===")
    for reason, count in pass_reasons.most_common():
        print(f"  {reason}: {count}")
        for fac in FACTIONS:
            fac_count = pass_by_faction_reason[fac].get(reason, 0)
            if fac_count:
                print(f"    {fac}: {fac_count}")

    # 2. bot_error exception breakdown
    print(f"\n=== BOT ERRORS (unhandled exceptions): {len(all_bot_errors)} total ===")
    error_by_faction: Counter = Counter()
    error_by_msg: Counter = Counter()
    error_by_msg_faction: dict[str, Counter] = defaultdict(Counter)
    error_by_msg_scenario: dict[str, set] = defaultdict(set)
    error_representative_tb: dict[str, str] = {}

    for err in all_bot_errors:
        faction = err.get("faction", "UNKNOWN")
        msg = err.get("exception_message", "unknown")
        exc_type = err.get("exception_type", "Exception")
        key = f"{exc_type}: {msg}"
        error_by_faction[faction] += 1
        error_by_msg[key] += 1
        error_by_msg_faction[key][faction] += 1
        error_by_msg_scenario[key].add(err.get("scenario", "?"))
        if key not in error_representative_tb:
            error_representative_tb[key] = err.get("traceback_str", "")

    print("\nBy faction:")
    for fac in FACTIONS:
        total_turns = total_turns_by_faction.get(fac, 0)
        n_err = error_by_faction.get(fac, 0)
        print(f"  {fac}: {n_err} bot_errors / {total_turns} total turns")

    print("\nTop errors by frequency:")
    for i, (key, count) in enumerate(error_by_msg.most_common(20), 1):
        scenarios = sorted(error_by_msg_scenario[key])
        fac_breakdown = ", ".join(
            f"{f}={c}" for f, c in error_by_msg_faction[key].most_common()
        )
        print(f"  #{i} ({count}x) [{','.join(scenarios)}] [{fac_breakdown}]: {key}")

    # 3. Write full output
    output = {
        "summary": {
            "total_games": total_games,
            "total_bot_errors": len(all_bot_errors),
            "total_turns": len(all_turn_logs),
            "pass_reasons": dict(pass_reasons.most_common()),
            "bot_errors_by_faction": dict(error_by_faction.most_common()),
            "total_turns_by_faction": dict(total_turns_by_faction.most_common()),
        },
        "pass_by_faction_reason": {
            fac: dict(counter.most_common())
            for fac, counter in pass_by_faction_reason.items()
        },
        "distinct_errors": [
            {
                "rank": i,
                "key": key,
                "count": count,
                "faction_breakdown": dict(error_by_msg_faction[key].most_common()),
                "scenarios": sorted(error_by_msg_scenario[key]),
                "representative_traceback": error_representative_tb.get(key, ""),
            }
            for i, (key, count) in enumerate(error_by_msg.most_common(), 1)
        ],
        "game_results": [
            {
                "scenario": r["scenario"],
                "seed": r["seed"],
                "cards_played": r["cards_played"],
                "winner": r["winner"],
                "num_bot_errors": len(r["bot_errors"]),
                "num_turns": len(r["turn_logs"]),
                "game_crash": r.get("game_crash"),
            }
            for r in all_results
        ],
        "all_bot_errors": all_bot_errors,
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\nFull error log written to {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
