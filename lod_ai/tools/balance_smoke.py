"""Balance-drift guardrail: bot-only games on fixed seeds vs a stored baseline.

The engine is deterministic for a given (scenario, seed), so every change in a
game's winner is real code drift, not sampling noise.  This tool replays a fixed
matrix of bot-only games, diffs the winners against ``balance_baseline.json``,
and fails when any faction's win rate moves more than ``--band`` within a
scenario.  After an *intended* rules change, refresh with ``--update``.

    python -m lod_ai.tools.balance_smoke                  # check (exit 1 on drift)
    python -m lod_ai.tools.balance_smoke --update         # rebaseline
    python -m lod_ai.tools.balance_smoke --seeds 1-5      # quicker spot check

Background: the Q13 supply bug (see QUESTIONS.md) shifted bot-only 1775 from
Patriots 16/20 to Indians 9/20 without failing any of the 1,189 unit tests.
Win-rate tables are the instrument that caught it; this tool automates them.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Game outcomes depend on set/dict iteration order in places, which Python's
# per-process hash randomization perturbs (e.g. 1778 seed 4 flips winner
# between hash seeds).  Pin the hash seed so this guardrail is reproducible;
# the underlying iteration-order sensitivity is worth fixing separately.
_HASHSEED = "0"
if os.environ.get("PYTHONHASHSEED") != _HASHSEED and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = _HASHSEED
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.balance_smoke"] + sys.argv[1:])

BASELINE_PATH = Path(__file__).resolve().parent / "balance_baseline.json"
SCENARIOS = ("1775", "1776", "1778")
FACTIONS = ("PATRIOTS", "BRITISH", "FRENCH", "INDIANS")
MAX_CARDS = 200


def play_bot_game(scenario: str, seed: int) -> dict:
    """Play one bot-only game; return {'winner': ..., 'cards': ...}."""
    from lod_ai.state.setup_state import build_state
    from lod_ai.engine import Engine
    from lod_ai.tools.batch_smoke import _check_game_over

    state = build_state(scenario, seed=seed)
    engine = Engine(initial_state=state)
    engine.set_human_factions(set())
    winner, cards = None, 0
    with contextlib.redirect_stdout(io.StringIO()):
        while cards < MAX_CARDS:
            card = engine.draw_card()
            if card is None:
                break
            engine.play_card(card)
            cards += 1
            winner = _check_game_over(engine.state)
            if winner:
                break
    return {"winner": winner or "none", "cards": cards}


def _seed_range(spec: str) -> range:
    lo, _, hi = spec.partition("-")
    return range(int(lo), int(hi or lo) + 1)


def _rates(games: dict, scenario: str) -> dict:
    wins = Counter(v["winner"] for k, v in games.items()
                   if k.startswith(scenario + ":"))
    n = sum(wins.values())
    return {f: wins.get(f, 0) / n for f in FACTIONS} if n else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--band", type=float, default=0.15,
                    help="Max allowed win-rate move per faction (default 0.15)")
    ap.add_argument("--update", action="store_true",
                    help="Merge current results into the baseline instead of checking")
    ap.add_argument("--baseline", default=str(BASELINE_PATH))
    args = ap.parse_args(argv)

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    seeds = _seed_range(args.seeds)
    bpath = Path(args.baseline)
    baseline = json.loads(bpath.read_text()) if bpath.exists() else {"games": {}}

    current: dict = {}
    for scen in scenarios:
        for seed in seeds:
            key = f"{scen}:{seed}"
            r = play_bot_game(scen, seed)
            current[key] = r
            print(f"[{scen} seed={seed:2d}] winner={r['winner']} ({r['cards']} cards)")

    if args.update:
        baseline["games"].update(current)
        bpath.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n")
        print(f"\nBaseline updated: {bpath} ({len(baseline['games'])} games)")
        return 0

    base_games = {k: v for k, v in baseline["games"].items() if k in current}
    if not base_games:
        print("\nNo overlapping baseline games found. Run with --update first.")
        return 2

    changed = [k for k in base_games
               if base_games[k]["winner"] != current[k]["winner"]]
    drift_fail = False
    print("\n=== Win rates: baseline -> current (overlapping games) ===")
    for scen in scenarios:
        base_r, cur_r = _rates(base_games, scen), _rates(current, scen)
        if not base_r:
            continue
        for f in FACTIONS:
            delta = cur_r[f] - base_r[f]
            flag = ""
            if abs(delta) > args.band:
                flag = f"  <-- DRIFT beyond ±{args.band:.0%}"
                drift_fail = True
            if base_r[f] or cur_r[f]:
                print(f"  {scen} {f:<9} {base_r[f]:>5.0%} -> {cur_r[f]:>5.0%}"
                      f"  ({delta:+.0%}){flag}")
    if changed:
        print(f"\n{len(changed)} game(s) changed winner: {', '.join(sorted(changed))}")
        print("(Deterministic engine: every change is caused by a code change.)")
    if drift_fail:
        print("\nFAIL: faction win rate moved beyond the allowed band.")
        print("If the change is intended, refresh with: "
              "python -m lod_ai.tools.balance_smoke --update")
        return 1
    print("\nOK: balance within band"
          + (f" ({len(changed)} winner changes, see above)" if changed else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
