"""CI gate: bot-only games must be CLEAN, not merely completed.

Replays bot-only games across scenarios/seeds and fails (exit 1) if any
game traps a bot error or logs an illegal action, or violates a per-card invariant (canonical-schema
validation + save/load round-trip). Companion to balance_smoke (which
guards WHO wins; this guards HOW the games run).

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

from lod_ai.tools.batch_smoke import run_one_game
from lod_ai.tools.run_diagnostics import result_is_clean

SCENARIOS = ("1775", "1776", "1778")


def play(scenario: str, seed: int, *, check_invariants: bool = True):
    with contextlib.redirect_stdout(io.StringIO()):
        result = run_one_game(scenario, seed, check_invariants=check_invariants)
    errs = result.get("bot_errors", [])
    illegal = result.get("illegal_actions", [])
    free_issues = list(result.get("free_op_skips", []))
    free_issues.extend(str(issue) for issue in result.get("free_op_errors", []))
    failures = []
    for error in result.get("event_preview_errors", []):
        failures.append(f"Event preview failed: {error}")
    if result.get("error") or result.get("end_reason") != "WINNER":
        failures.append(result.get("error") or f"Unfinished run: {result.get('end_reason')}")
    elif not result_is_clean(result) and not (errs or illegal or free_issues or failures):
        failures.append("Completed run marked dirty or has no canonical winner")
    return errs, illegal, free_issues, failures, result["cards_played"]


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
            errs, illegal, free_skips, inv_fail, cards = play(scen, seed)
            tag = f"[{scen} seed={seed:2d}] {cards} cards"
            if inv_fail:
                dirty += 1
                print(f"{tag}  DIRTY: {len(inv_fail)} execution/invariant failure(s)")
                for m in inv_fail[:2]:
                    print(f"    failure: {m.splitlines()[0][:140]}")
            elif errs or illegal:
                dirty += 1
                print(f"{tag}  DIRTY: {len(errs)} bot error(s), "
                      f"{len(illegal)} illegal action(s)")
                for e in errs[:3]:
                    print(f"    bot_error: {str(e.get('exception_message', e.get('error')))[:100]}")
                for h in illegal[:3]:
                    print(f"    illegal: {str(h)[:100]}")
            elif free_skips:
                skip_games += 1
                print(f"{tag}  FREE-OP ERRORS/SKIPS: {len(free_skips)}")
                for h in free_skips[:3]:
                    print(f"    {h[:100]}")
            else:
                print(f"{tag}  clean")
    if dirty:
        print(f"\nFAIL: {dirty} game(s) failed completion, execution, or invariants.")
        return 1
    if skip_games:
        # HARD gate since the per-faction free-Command and free-SA
        # planners landed: a planner-approved free op must execute.
        # Genuine "no legal target" outcomes log as "declined (no legal
        # plan)" in the planner and are allowed; an execution-time skip
        # means the planner and an executor disagree about legality.
        print(f"\nFAIL: {skip_games} game(s) had free-op execution errors/skips "
              f"(planner/executor divergence).")
        return 1
    print("\nOK: every game clean (zero bot errors, illegal actions, "
          "free-op errors/skips, event-preview errors, invariant violations).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
