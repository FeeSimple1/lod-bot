"""Command-line entry point for the LLM harness.

Examples
--------
Offline smoke test (random legal moves, no API key needed):

    python -m lod_ai.llm --scenario 1778 --factions PATRIOTS --policy random

Watch an LLM play (needs ANTHROPIC_API_KEY):

    python -m lod_ai.llm --scenario 1775 --factions PATRIOTS \
        --policy anthropic --model claude-sonnet-4-5 --verbose
"""
from __future__ import annotations

import argparse
import sys

from .harness import run_game
from .policy import make_policy


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m lod_ai.llm",
        description="Let an LLM play Liberty or Death against the bots.",
    )
    p.add_argument("--scenario", default="1775", choices=["1775", "1776", "1778"])
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--deck-method", default="standard",
                   choices=["standard", "period"])
    p.add_argument("--factions", default="PATRIOTS",
                   help="Comma-separated factions the LLM controls "
                        "(BRITISH,PATRIOTS,FRENCH,INDIANS).")
    p.add_argument("--policy", default="random",
                   choices=["random", "first", "anthropic"])
    p.add_argument("--model", default="claude-sonnet-4-5")
    p.add_argument("--max-cards", type=int, default=None)
    p.add_argument("--verbose", action="store_true",
                   help="Stream each decision (and don't suppress board output).")
    args = p.parse_args(argv)

    factions = [f.strip().upper() for f in args.factions.split(",") if f.strip()]
    policy = make_policy(args.policy, model=args.model, verbose=args.verbose,
                         seed=args.seed)

    print(f"Liberty or Death -- LLM harness")
    print(f"  scenario={args.scenario} seed={args.seed} deck={args.deck_method}")
    print(f"  LLM plays: {', '.join(factions)}   policy={args.policy}")
    print("  (other factions played by the rule-based bots)\n")

    result = run_game(
        args.scenario, seed=args.seed, deck_method=args.deck_method,
        llm_factions=factions, policy=policy, max_cards=args.max_cards,
        verbose=args.verbose, quiet=not args.verbose,
    )

    print("\n=== RESULT ===")
    print(f"  Winner:        {result['winner']}")
    print(f"  Cards played:  {result['cards_played']}")
    print(f"  LLM decisions: {result['decisions']}")
    print(f"  LLM factions:  {', '.join(result['human_factions'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
