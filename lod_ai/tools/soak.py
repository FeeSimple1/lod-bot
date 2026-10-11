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
from lod_ai.tools.run_diagnostics import COUNT_KEYS, issue_summary, result_is_clean

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
    ap.add_argument("--coverage", default=None,
                    help="aggregate decision coverage into this json (Piece 5)")
    args = ap.parse_args(argv)

    schedule = list(_plan(args.games, args.seed_base))
    done = _completed(args.out)
    if args.coverage:
        from lod_ai.tools import coverage as _cov
        _coll = _cov.enable()
        import os as _os
        if _os.path.exists(args.coverage):
            _coll.merge(_cov.Collector.load(args.coverage))
            _coll.games = _coll.games  # resumed totals carry forward
    start = time.time()
    ran = 0
    failures = 0

    with open(args.out, "a") as f:
        for idx in range(done, len(schedule)):
            if args.max_seconds and (time.time() - start) >= args.max_seconds:
                break
            scen, seed = schedule[idx]
            result = run_one_game(scen, seed, check_invariants=args.invariants)
            bad = not result_is_clean(result)
            rec = {
                "i": idx, "scenario": scen, "seed": seed,
                "end_reason": result["end_reason"],
                "winner": result["winner"],
                "cards": result["cards_played"],
                "error": result["error"],
                "repro": result.get("repro_command"),
                "clean": not bad,
                "issues": issue_summary(result) if bad else None,
                "event_outcome_observations": result.get("event_outcome_observations", []),
                "event_outcome_observation_count": result.get("event_outcome_observation_count", 0),
                **{key: result.get(key, 0) for key in COUNT_KEYS},
            }
            f.write(json.dumps(rec) + "\n")
            f.flush()
            ran += 1
            if args.coverage:
                _coll.finish_game()
            if bad:
                failures += 1
                print(f"  FAIL [{scen} seed={seed}] {result['end_reason']}: "
                      f"{issue_summary(result)}  repro: {result.get('repro_command')}")

    if args.coverage:
        _coll.save(args.coverage)

    now_done = _completed(args.out)
    elapsed = time.time() - start
    print(f"ran {ran} game(s) this invocation in {elapsed:.1f}s "
          f"({now_done}/{len(schedule)} total); {failures} failure(s) here")
    # Include failures from previous invocations, even when they reached a
    # winner or were stored under a legacy DIRTY/TIMEOUT end reason.
    with open(args.out) as fh:
        all_records = [json.loads(line) for line in fh if line.strip()]
    dirty_total = sum(not result_is_clean(record) for record in all_records)
    if now_done >= len(schedule):
        print(f"DONE: {now_done} games. dirty={dirty_total}")
        return 1 if dirty_total else 0
    print(f"PARTIAL: re-run the same command to continue. dirty_so_far={dirty_total}")
    return 1 if dirty_total else 0



if __name__ == "__main__":
    raise SystemExit(main())
