#!/usr/bin/env python3
"""
Single-game diagnostic runner that captures full bot exception details.

Runs a 1775 scenario game (seed=1) with all factions as bots,
then dumps the _bot_error_log to JSON for analysis.

Usage:
    python -m lod_ai.tools.error_diagnostic_runner
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Redirect stdin to /dev/null so any accidental interactive prompt
# raises EOFError instead of blocking.
_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai import rules_consts as C

CARD_SAFETY_LIMIT = 200
OUTPUT_PATH = Path(__file__).resolve().parent / "bot_error_log.json"
FACTIONS = [C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH]


def run() -> None:
    print("Running 1775 scenario, seed=1, all bots ...")
    state = build_state("1775", seed=1)
    engine = Engine(initial_state=state, use_cli=False)
    engine.set_human_factions([])  # all bots

    cards_played = 0
    winner = None

    while cards_played < CARD_SAFETY_LIMIT:
        card = engine.draw_card()
        if card is None:
            print(f"Deck exhausted after {cards_played} cards.")
            break

        engine.play_card(card, human_decider=None)
        cards_played += 1

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

    print(f"Game finished: {cards_played} cards played, winner={winner or 'none'}")

    # Extract error log
    error_log = engine.state.get("_bot_error_log", [])
    print(f"Total bot errors captured: {len(error_log)}")

    # Count by faction
    from collections import Counter
    by_faction = Counter(e["faction"] for e in error_log)
    for fac in FACTIONS:
        print(f"  {fac}: {by_faction.get(fac, 0)} errors")

    # Write the full error log
    OUTPUT_PATH.write_text(json.dumps(error_log, indent=2), encoding="utf-8")
    print(f"\nFull error log written to {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
