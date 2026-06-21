"""
Sandboxed Battle benchmark for the British B12 selection.

B12 selects a space iff "Royalist Force Level + modifiers exceeds Rebel
Force Level + modifiers" -- a deterministic comparison, NOT a dice
simulation (simulating would deviate from the reference). This tool does
not change that; it *measures* the quality of the selection by, for every
space the British bot actually chooses to Battle, simulating the real
Battle resolution K times on a snapshot and recording how often the
Rebellion wins (a "losing attack" that can award Win-the-Day Opposition
against the British).

Run it before and after a change to the selection to see the effect:

    python -m lod_ai.tools.battle_benchmark --seeds 1-10 --trials 200
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import random
import sys
from copy import deepcopy

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.battle_benchmark"] + sys.argv[1:])

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai.commands import battle as battle_cmd

SCENARIOS = ("1775", "1776", "1778")


def _simulate_space(state, ctx, sid, trials):
    """Resolve the Battle in *sid* *trials* times on snapshots; return the
    fraction the Rebellion wins (British losing attack)."""
    reb_wins = 0
    for t in range(trials):
        snap = deepcopy(state)
        snap["rng"] = random.Random((hash(sid) & 0xFFFF) ^ (t * 2654435761) & 0xFFFFFFFF)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                winner = battle_cmd._resolve_space(
                    snap, ctx, "BRITISH", sid, 0,
                    ally_involved=True, attacker_activate=0,
                )
            except Exception:
                winner = None
        if winner == "REBELLION":
            reb_wins += 1
    return reb_wins / trials if trials else 0.0


def run(seeds, scenarios, trials):
    stats = {"spaces": 0, "p_sum": 0.0, "coinflip_or_worse": 0,
             "likely_loss": 0, "games": 0}
    orig_execute = battle_cmd.execute

    def wrapped(state, faction, ctx, spaces, **kw):
        if faction.upper() == "BRITISH" and not kw.get("free"):
            for sid in spaces:
                if sid not in state.get("spaces", {}):
                    continue
                p = _simulate_space(state, ctx, sid, trials)
                stats["spaces"] += 1
                stats["p_sum"] += p
                if p >= 0.5:
                    stats["coinflip_or_worse"] += 1
                if p >= 0.67:
                    stats["likely_loss"] += 1
        return orig_execute(state, faction, ctx, spaces, **kw)

    battle_cmd.execute = wrapped
    try:
        for scen in scenarios:
            for seed in seeds:
                stats["games"] += 1
                st = build_state(scen, seed=seed)
                eng = Engine(initial_state=st)
                eng.set_human_factions(set())
                with contextlib.redirect_stdout(io.StringIO()):
                    n = 0
                    while n < 200:
                        c = eng.draw_card()
                        if c is None:
                            break
                        eng.play_card(c)
                        n += 1
    finally:
        battle_cmd.execute = orig_execute
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--trials", type=int, default=200)
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = [s for s in args.scenarios.split(",") if s]

    st = run(seeds, scenarios, args.trials)
    n = st["spaces"]
    mean_p = (st["p_sum"] / n) if n else 0.0
    print(f"British battle-spaces selected: {n} (across {st['games']} games, "
          f"{args.trials} trials each)")
    print(f"Mean P(Rebellion wins the selected battle): {mean_p:.3f}")
    print(f"Spaces with P(loss) >= 0.50 (coin-flip or worse): "
          f"{st['coinflip_or_worse']} ({100*st['coinflip_or_worse']/n:.1f}%)"
          if n else "  (no battles)")
    print(f"Spaces with P(loss) >= 0.67 (likely loss):        "
          f"{st['likely_loss']} ({100*st['likely_loss']/n:.1f}%)"
          if n else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
