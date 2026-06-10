"""Batch self-play: heuristic strategy profiles vs the rule-based bots.

Runs each profile (and random/first baselines) across seeds and scenarios,
appending one JSON line per game so interrupted batches can resume.

    python -m lod_ai.tools.heuristic_selfplay --scenario 1778 --seeds 1-20 \
        --out results.jsonl                  # all profiles + baselines
    python -m lod_ai.tools.heuristic_selfplay --profiles P-AGIT,B-CITY ...
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lod_ai.llm import run_game
from lod_ai.llm.policy import RandomPolicy, FirstChoicePolicy
from lod_ai.llm.heuristic import HeuristicPolicy, PROFILES

FACTIONS = ("PATRIOTS", "BRITISH", "FRENCH", "INDIANS")


def _make(label: str, seed: int):
    if label.startswith("RANDOM:"):
        return label.split(":")[1], RandomPolicy(seed=seed)
    if label.startswith("FIRST:"):
        return label.split(":")[1], FirstChoicePolicy()
    prof = PROFILES[label]
    return prof["faction"], HeuristicPolicy(prof, seed=seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="1778")
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--profiles", default=None,
                    help="Comma list of profile names and/or RANDOM:FACTION / "
                         "FIRST:FACTION baselines. Default: all profiles + "
                         "RANDOM baselines for each faction.")
    ap.add_argument("--max-cards", type=int, default=200)
    ap.add_argument("--out", default="selfplay_results.jsonl")
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)

    if args.profiles:
        labels = [s.strip() for s in args.profiles.split(",") if s.strip()]
    else:
        labels = list(PROFILES) + [f"RANDOM:{f}" for f in FACTIONS]

    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                rec = json.loads(line)
                done.add((rec["label"], rec["scenario"], rec["seed"]))
            except Exception:
                pass

    with out.open("a") as fh:
        for label in labels:
            for seed in seeds:
                key = (label, args.scenario, seed)
                if key in done:
                    continue
                faction, policy = _make(label, seed)
                t0 = time.time()
                try:
                    r = run_game(args.scenario, seed=seed,
                                 llm_factions=[faction], policy=policy,
                                 max_cards=args.max_cards)
                    rec = {"label": label, "faction": faction,
                           "scenario": args.scenario, "seed": seed,
                           "winner": r["winner"], "cards": r["cards_played"],
                           "decisions": r["decisions"],
                           "secs": round(time.time() - t0, 2)}
                except Exception as exc:
                    rec = {"label": label, "faction": faction,
                           "scenario": args.scenario, "seed": seed,
                           "winner": None, "error": f"{type(exc).__name__}: {exc}",
                           "secs": round(time.time() - t0, 2)}
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                won = rec.get("winner") == faction
                print(f"[{label:>16s} {args.scenario} seed={seed:2d}] "
                      f"winner={rec.get('winner')} "
                      f"{'WIN' if won else ''} {rec.get('error','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
