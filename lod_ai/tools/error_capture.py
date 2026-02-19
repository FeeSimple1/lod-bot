#!/usr/bin/env python3
"""
Capture detailed bot_error and illegal_action data from 60 zero-player games.

Writes raw data to bot_error_log_round4.json with full tracebacks and
illegal action details.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path

_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai import rules_consts as C

SCENARIOS = ["1775", "1776", "1778"]
SEEDS_PER_SCENARIO = 20
CARD_SAFETY_LIMIT = 200
FACTIONS = [C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH]
OUTPUT_PATH = Path(__file__).resolve().parent / "bot_error_log_round4.json"


def run_one_game(scenario: str, seed: int) -> dict:
    """Run a single zero-player game, returning error/illegal data."""
    game_info = {
        "scenario": scenario,
        "seed": seed,
        "bot_errors": [],
        "illegal_actions": [],
        "cards_played": 0,
        "end_reason": None,
        "crash": None,
        "turn_counts": {f: 0 for f in FACTIONS},
        "success_counts": {f: 0 for f in FACTIONS},
        "pass_counts": {f: 0 for f in FACTIONS},
        "pass_reasons": {f: Counter() for f in FACTIONS},
    }

    try:
        state = build_state(scenario, seed=seed)
        engine = Engine(initial_state=state, use_cli=False)
        engine.set_human_factions([])

        cards_played = 0
        while cards_played < CARD_SAFETY_LIMIT:
            card = engine.draw_card()
            if card is None:
                game_info["end_reason"] = "DECK_EXHAUSTED"
                break

            # Clear per-card logs
            engine.state.pop("_bot_error_log", None)
            engine.state.pop("_illegal_action_log", None)

            engine.play_card(card, human_decider=None)
            cards_played += 1

            # Harvest bot errors
            for err in engine.state.get("_bot_error_log", []):
                err["scenario"] = scenario
                err["seed"] = seed
                err["card_played_number"] = cards_played
                game_info["bot_errors"].append(err)

            # Harvest illegal actions
            for ill in engine.state.get("_illegal_action_log", []):
                ill["scenario"] = scenario
                ill["seed"] = seed
                ill["card_played_number"] = cards_played
                game_info["illegal_actions"].append(ill)

            # Track per-card turn log
            for entry in engine.state.get("_card_turn_log", []):
                faction = entry.get("faction")
                if faction not in FACTIONS:
                    continue
                game_info["turn_counts"][faction] += 1
                action = entry.get("action")
                if action == "pass":
                    game_info["pass_counts"][faction] += 1
                    reason = entry.get("pass_reason", "other")
                    game_info["pass_reasons"][faction][reason] += 1
                else:
                    game_info["success_counts"][faction] += 1

            # Check for game over
            history = engine.state.get("history", [])
            game_over = False
            for entry in reversed(history[-40:]):
                msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
                if "Winner:" in msg or "Victory achieved" in msg:
                    game_over = True
                    break
            if game_over:
                game_info["end_reason"] = "WINNER"
                break
        else:
            game_info["end_reason"] = "TIMEOUT"

        game_info["cards_played"] = cards_played

    except EOFError:
        game_info["end_reason"] = "INTERACTIVE_PROMPT"
        game_info["crash"] = "Engine tried to read interactive input"
    except Exception as exc:
        game_info["end_reason"] = "CRASH"
        game_info["crash"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"

    # Convert Counters to dicts for JSON
    game_info["pass_reasons"] = {
        f: dict(c) for f, c in game_info["pass_reasons"].items()
    }
    return game_info


def main() -> None:
    print(f"Running error capture: {len(SCENARIOS)} scenarios x {SEEDS_PER_SCENARIO} seeds = "
          f"{len(SCENARIOS) * SEEDS_PER_SCENARIO} games")

    all_games = []
    total_bot_errors = 0
    total_illegal = 0

    for scenario in SCENARIOS:
        for seed in range(1, SEEDS_PER_SCENARIO + 1):
            tag = f"[{scenario} seed={seed:>2}]"
            sys.stdout.write(f"  {tag} ... ")
            sys.stdout.flush()

            result = run_one_game(scenario, seed)
            all_games.append(result)

            n_err = len(result["bot_errors"])
            n_ill = len(result["illegal_actions"])
            total_bot_errors += n_err
            total_illegal += n_ill

            status = result["end_reason"] or "?"
            extra = f" err={n_err} ill={n_ill}"
            if result["crash"]:
                extra += f" CRASH"
            print(f"{status} ({result['cards_played']} cards){extra}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  TOTALS: {total_bot_errors} bot_errors, {total_illegal} illegal_actions")
    print(f"{'=' * 60}")

    # Per-faction summary
    faction_errors = Counter()
    faction_illegal = Counter()
    faction_turns = Counter()
    faction_success = Counter()

    for g in all_games:
        for err in g["bot_errors"]:
            faction_errors[err.get("faction", "?")] += 1
        for ill in g["illegal_actions"]:
            faction_illegal[ill.get("faction", "?")] += 1
        for f in FACTIONS:
            faction_turns[f] += g["turn_counts"][f]
            faction_success[f] += g["success_counts"][f]

    print(f"\n  {'Faction':<12} {'Turns':>6} {'Success':>8} {'Errors':>7} {'Illegal':>8}")
    print(f"  {'-' * 43}")
    for f in FACTIONS:
        print(f"  {f:<12} {faction_turns[f]:>6} {faction_success[f]:>8} "
              f"{faction_errors[f]:>7} {faction_illegal[f]:>8}")

    # Error type summary
    error_types = Counter()
    for g in all_games:
        for err in g["bot_errors"]:
            # Use first line of exception message as key
            msg = err.get("exception_message", "unknown")
            key = msg.split("\n")[0][:100]
            error_types[key] += 1

    print(f"\n  Top bot_error types:")
    for msg, count in error_types.most_common(20):
        print(f"    [{count:>4}] {msg}")

    # Illegal action summary
    illegal_types = Counter()
    for g in all_games:
        for ill in g["illegal_actions"]:
            reason = ill.get("illegal_reason", "unknown")
            cmd = ill.get("attempted_command", "?")
            fac = ill.get("faction", "?")
            key = f"{fac}/{cmd}/{reason}"
            illegal_types[key] += 1

    print(f"\n  Top illegal_action types:")
    for key, count in illegal_types.most_common(30):
        print(f"    [{count:>4}] {key}")

    # Write raw data
    OUTPUT_PATH.write_text(json.dumps(all_games, indent=2, default=str), encoding="utf-8")
    print(f"\nRaw data written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
