"""CI gate: bot-only games must be CLEAN, not merely completed.

Replays bot-only games across scenarios/seeds and fails (exit 1) if any
game traps a bot error or logs an illegal action. Companion to
balance_smoke (which guards WHO wins; this guards HOW the games run).

    python -m lod_ai.tools.clean_sweep_gate --seeds 1-20
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys

# Outcomes are now hash-seed invariant, but pin anyway so CI logs are
# byte-comparable across runs.
if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.clean_sweep_gate"] + sys.argv[1:])

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine

SCENARIOS = ("1775", "1776", "1778")


def play(scenario: str, seed: int):
    st = build_state(scenario, seed=seed)
    eng = Engine(initial_state=st)
    eng.set_human_factions(set())
    with contextlib.redirect_stdout(io.StringIO()):
        n = 0
        while n < 200:
            card = eng.draw_card()
            if card is None:
                break
            eng.play_card(card)
            n += 1
    errs = eng.state.get("_bot_error_log", []) or []
    illegal = [h for h in eng.state.get("history", [])
               if "illegal" in str(h).lower()]
    return errs, illegal, n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    dirty = 0
    for scen in [s for s in args.scenarios.split(",") if s]:
        for seed in range(int(lo), int(hi or lo) + 1):
            errs, illegal, cards = play(scen, seed)
            tag = f"[{scen} seed={seed:2d}] {cards} cards"
            if errs or illegal:
                dirty += 1
                print(f"{tag}  DIRTY: {len(errs)} bot error(s), "
                      f"{len(illegal)} illegal action(s)")
                for e in errs[:3]:
                    print(f"    bot_error: {str(e.get('error'))[:100]}")
                for h in illegal[:3]:
                    print(f"    illegal: {str(h)[:100]}")
            else:
                print(f"{tag}  clean")
    if dirty:
        print(f"\nFAIL: {dirty} game(s) trapped bot errors or illegal actions.")
        return 1
    print("\nOK: every game clean (zero trapped bot errors, zero illegal actions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
