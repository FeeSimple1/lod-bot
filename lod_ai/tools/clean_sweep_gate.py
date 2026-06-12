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
    hist = [str(h.get("msg", "") if isinstance(h, dict) else h)
            for h in eng.state.get("history", [])]
    illegal = [h for h in hist if "illegal" in h.lower()]
    # Free-op fidelity: a card-granted free op should run, not be silently
    # skipped for lack of a target. A planner that genuinely declines logs
    # "declined (no legal plan)" instead, which is allowed.
    free_skips = [h for h in hist
                  if "FREE " in h and "skipped (no valid target)" in h]
    return errs, illegal, free_skips, n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    dirty = 0
    skip_games = 0
    for scen in [s for s in args.scenarios.split(",") if s]:
        for seed in range(int(lo), int(hi or lo) + 1):
            errs, illegal, free_skips, cards = play(scen, seed)
            tag = f"[{scen} seed={seed:2d}] {cards} cards"
            if errs or illegal:
                dirty += 1
                print(f"{tag}  DIRTY: {len(errs)} bot error(s), "
                      f"{len(illegal)} illegal action(s)")
                for e in errs[:3]:
                    print(f"    bot_error: {str(e.get('error'))[:100]}")
                for h in illegal[:3]:
                    print(f"    illegal: {str(h)[:100]}")
            elif free_skips:
                skip_games += 1
                print(f"{tag}  FREE-OP SKIPS: {len(free_skips)}")
                for h in free_skips[:3]:
                    print(f"    {h[:100]}")
            else:
                print(f"{tag}  clean")
    if dirty:
        print(f"\nFAIL: {dirty} game(s) trapped bot errors or illegal actions.")
        return 1
    if skip_games:
        # HARD gate since the per-faction free-Command and free-SA
        # planners landed: a planner-approved free op must execute.
        # Genuine "no legal target" outcomes log as "declined (no legal
        # plan)" in the planner and are allowed; an execution-time skip
        # means the planner and an executor disagree about legality.
        print(f"\nFAIL: {skip_games} game(s) had free-op execution skips "
              f"(planner/executor divergence).")
        return 1
    print("\nOK: every game clean (zero bot errors, illegal actions, "
          "free-op skips).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
