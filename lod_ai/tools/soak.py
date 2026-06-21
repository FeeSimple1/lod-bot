"""
Soak test: run a large number of zero-player games across all scenarios
with broad seed coverage, to flush rare-path crashes and (optionally)
per-card state-corruption that the fast 60-game CI gate would not reach.

Each game's outcome is appended as one JSON line to ``--out`` so the run
is RESUMABLE: re-invoking with the same ``--out`` continues from where it
left off (handy under a per-call time budget). Any crash or invariant
violation also writes a full crash-repro dump under ``crash_dumps/`` via
run_one_game, each naming the one command that reproduces it.

    # 1000 games, resumable, ~38s per invocation:
    python -m lod_ai.tools.soak --games 1000 --out soak.jsonl --max-seconds 38
    # repeat the same command until it prints "DONE".

    # full per-card invariants (slower):
    python -m lod_ai.tools.soak --games 200 --out soak_inv.jsonl --invariants
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.soak"] + sys.argv[1:])

from lod_ai.tools.batch_smoke import run_one_game

SCENARIOS = ("1775", "1776", "1778")


def _plan(games: int, seed_base: int):
    """Deterministic (scenario, seed) schedule covering *games* runs."""
    for i in range(games):
        yield SCENARIOS[i % len(SCENARIOS)], seed_base + (i // len(SCENARIOS))


def _completed(out_path: str) -> int:
    if not os.path.exists(out_path):
        return 0
    with open(out_path) as f:
        return sum(1 for line in f if line.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--out", default="soak.jsonl")
    ap.add_argument("--max-seconds", type=float, default=0.0,
                    help="stop after this wall-time (0 = run to completion)")
    ap.add_argument("--invariants", action="store_true",
                    help="assert per-card invariants (save/load + validate)")
    args = ap.parse_args(argv)

    schedule = list(_plan(args.games, args.seed_base))
    done = _completed(args.out)
    start = time.time()
    ran = 0
    failures = 0

    with open(args.out, "a") as f:
        for idx in range(done, len(schedule)):
            if args.max_seconds and (time.time() - start) >= args.max_seconds:
                break
            scen, seed = schedule[idx]
            result = run_one_game(scen, seed, check_invariants=args.invariants)
            bad = result["end_reason"] in ("CRASH", "INVARIANT",
                                           "INTERACTIVE_PROMPT")
            rec = {
                "i": idx, "scenario": scen, "seed": seed,
                "end_reason": result["end_reason"],
                "winner": result["winner"],
                "cards": result["cards_played"],
                "error": result["error"],
                "repro": result.get("repro_command"),
            }
            f.write(json.dumps(rec) + "\n")
            f.flush()
            ran += 1
            if bad:
                failures += 1
                print(f"  FAIL [{scen} seed={seed}] {result['end_reason']}: "
                      f"{result['error']}  repro: {result.get('repro_command')}")

    now_done = _completed(args.out)
    elapsed = time.time() - start
    print(f"ran {ran} game(s) this invocation in {elapsed:.1f}s "
          f"({now_done}/{len(schedule)} total); {failures} failure(s) here")
    if now_done >= len(schedule):
        # Final tally across the whole file.
        crashes = inval = 0
        with open(args.out) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r["end_reason"] == "CRASH":
                    crashes += 1
                elif r["end_reason"] in ("INVARIANT", "INTERACTIVE_PROMPT"):
                    inval += 1
        print(f"DONE: {now_done} games. crashes={crashes}, "
              f"invariant/prompt failures={inval}")
        return 1 if (crashes or inval) else 0
    print("PARTIAL: re-run the same command to continue.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
