"""
Audit: are free-Gather declines genuine "no legal target" outcomes?

The free-op planner returns ``None`` for a queued Indian free Gather when
it finds no legal space. The clean-sweep gate treats that as allowed (a
decline, not an execution skip). This tool verifies, the way the War Path
declines were verified, that every such decline is grounded in the actual
space state -- i.e. for each decline we independently reconstruct WHY no
space was legal and assert it is a real rules reason, not a planner miss.

A free Gather space is legal (per the planner's transcription of Gather
legality, Manual 4.4 / 1.4) iff:
  * it is not the West Indies, AND
  * its Support level is Neutral / Passive Support / Passive Opposition
    (SUPPORT_OK), AND
  * the Indians have a War Party / Village in it or in an adjacent space.

A decline is GENUINE when no candidate space satisfies all three. If a
decline ever coincides with a space that DOES satisfy them, that is a
planner bug and this tool flags it (exit 1).

    python -m lod_ai.tools.gather_decline_audit --seeds 1-20
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.gather_decline_audit"] + sys.argv[1:])

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai import rules_consts as C
from lod_ai.commands.gather import SUPPORT_OK
from lod_ai.map import adjacency as map_adj

SCENARIOS = ("1775", "1776", "1778")


def _legal_gather_spaces(eng: Engine, st: dict) -> list[str]:
    """Every space at which a free Indian Gather is legal, right now."""
    out = []
    for sid in st.get("spaces", {}):
        if sid == C.WEST_INDIES_ID:
            continue
        if st.get("support", {}).get(sid, C.NEUTRAL) not in SUPPORT_OK:
            continue
        if eng._own_force_in(st, sid, C.INDIANS) > 0:
            out.append(sid); continue
        if any(eng._own_force_in(st, nbr, C.INDIANS) > 0
               for nbr in map_adj.adjacent_spaces(sid)):
            out.append(sid)
    return out


def _reason(eng: Engine, st: dict, loc: str | None) -> str:
    """Human-readable, state-grounded reason a gather decline is genuine."""
    if loc is not None:
        if loc == C.WEST_INDIES_ID:
            return f"{loc}: West Indies (Gather illegal there)"
        sup = st.get("support", {}).get(loc, C.NEUTRAL)
        if sup not in SUPPORT_OK:
            return f"{loc}: support={sup} not in {sorted(SUPPORT_OK)}"
        own = eng._own_force_in(st, loc, C.INDIANS)
        adj = [n for n in map_adj.adjacent_spaces(loc)
               if eng._own_force_in(st, n, C.INDIANS) > 0]
        return (f"{loc}: own Indian force={own}, adjacent Indian "
                f"spaces={adj} (no War Party/Village in or beside it)")
    return "anywhere: no space at eligible support has an Indian piece in/adjacent"


def run(seeds, scenarios):
    declines = []
    bugs = []
    for scen in scenarios:
        for seed in seeds:
            st = build_state(scen, seed=seed)
            eng = Engine(initial_state=st)
            eng.set_human_factions(set())
            orig = eng._plan_bot_free_op

            def wrapped(target_state, faction, op, loc, card_id=None,
                        _orig=orig, _eng=eng, _scen=scen, _seed=seed):
                res = _orig(target_state, faction, op, loc, card_id)
                if op == "gather" and faction == C.INDIANS and res is None:
                    legal = _legal_gather_spaces(_eng, target_state)
                    card = len(target_state.get("played_cards", []))
                    rec = {"scenario": _scen, "seed": _seed, "card": card,
                           "loc": loc, "reason": _reason(_eng, target_state, loc),
                           "legal_spaces_found": legal}
                    declines.append(rec)
                    # A located decline is a bug only if THAT loc is legal;
                    # an anywhere decline is a bug if ANY space is legal.
                    if loc is not None:
                        if loc in legal:
                            bugs.append(rec)
                    elif legal:
                        bugs.append(rec)
                return res

            eng._plan_bot_free_op = wrapped
            with contextlib.redirect_stdout(io.StringIO()):
                n = 0
                while n < 200:
                    c = eng.draw_card()
                    if c is None:
                        break
                    eng.play_card(c)
                    n += 1
    return declines, bugs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = [s for s in args.scenarios.split(",") if s]

    declines, bugs = run(seeds, scenarios)
    print(f"Free-Gather declines observed: {len(declines)}")
    for d in declines:
        print(f"  [{d['scenario']} seed={d['seed']:2d} card={d['card']:3d}] "
              f"loc={d['loc']}  -> {d['reason']}")
    if bugs:
        print(f"\nFAIL: {len(bugs)} decline(s) had a legal Gather target the "
              f"planner missed:")
        for b in bugs:
            print(f"  {b}")
        return 1
    print("\nOK: every free-Gather decline is grounded in the actual space "
          "state (genuine no-legal-target).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
