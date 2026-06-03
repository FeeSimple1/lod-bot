"""Headless game runner that seats an LLM (via a Policy) in a human chair while
the rule-based bots play the other factions.

The harness reuses the interactive CLI's own ``_human_decider`` and command
wizards verbatim -- it only swaps the *input source*, so the LLM navigates the
exact same legality-checked decision tree a human would.
"""
from __future__ import annotations

import contextlib
import io
from typing import Iterable, Optional

from .observation import serialize_state


def _detect_winner(state: dict) -> Optional[str]:
    """Scan recent history for a victory/end-of-game declaration."""
    history = state.get("history", [])
    for entry in reversed(history[-40:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Winner:" in msg:
            # e.g. "Winner: PATRIOTS (Rule 7.3)"
            after = msg.split("Winner:", 1)[1].strip()
            return after.split()[0] if after else "unknown"
        if "Victory achieved" in msg:
            return msg
    return None


@contextlib.contextmanager
def _maybe_quiet(quiet: bool):
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    else:
        yield


def run_game(
    scenario: str = "1775",
    *,
    seed: int = 1,
    deck_method: str = "standard",
    llm_factions: Iterable[str] = ("PATRIOTS",),
    policy=None,
    max_cards: Optional[int] = None,
    verbose: bool = False,
    quiet: bool = True,
) -> dict:
    """Play a game with ``llm_factions`` driven by ``policy`` and the rest by bots.

    Returns a summary dict: ``winner``, ``cards_played``, ``decisions`` (number
    of LLM choices made), ``human_factions``, and the final ``state``.
    """
    from lod_ai.state.setup_state import build_state
    from lod_ai.engine import Engine
    from lod_ai.cli_utils import set_input_provider, set_game_state
    from lod_ai.commands import battle as battle_cmd
    from lod_ai import interactive_cli as cli
    from .provider import LLMInputProvider
    from .policy import RandomPolicy

    policy = policy or RandomPolicy()
    llm_factions = set(f.upper() for f in llm_factions)

    state = build_state(scenario, seed=seed, setup_method=deck_method)
    state["_seed"] = seed
    state["_scenario"] = scenario
    state["_setup_method"] = deck_method
    state["_deck_display_mode"] = "exact"

    engine = Engine(initial_state=state)
    engine.set_human_factions(llm_factions)
    set_game_state(engine.state, engine=engine)

    provider = LLMInputProvider(policy, engine, llm_factions, verbose=verbose)
    set_input_provider(provider)

    # Let the LLM also choose §3.6.3 Underground activation when DEFENDING during
    # a bot's Battle (this fires outside the LLM's own turn, via a separate hook).
    def _defender_hook(st, sid, def_side, owner, n_ug, ug_tag):
        if owner not in llm_factions:
            return 0
        menu = {
            "kind": "count",
            "prompt": (f"Defending in {sid}: activate how many of your "
                       f"Underground units? (adds half to your Force Level)"),
            "min": 0, "max": n_ug, "default": 0,
        }
        try:
            obs = serialize_state(st, owner)
            return int(policy.choose(obs, "Activate count:", menu, owner) or 0)
        except Exception:
            return 0

    battle_cmd.set_defender_activation_hook(_defender_hook)

    def decider(faction, card, allowed, eng):
        provider.begin_turn(faction, card, allowed)
        return cli._human_decider(faction, card, allowed, eng)

    cards_played = 0
    winner = None
    try:
        with _maybe_quiet(quiet and not verbose):
            while True:
                card = engine.draw_card()
                if card is None:
                    winner = _detect_winner(engine.state) or "deck_exhausted"
                    break
                engine.play_card(card, human_decider=decider)
                cards_played += 1
                w = _detect_winner(engine.state)
                if w is not None:
                    winner = w
                    break
                if max_cards is not None and cards_played >= max_cards:
                    winner = "card_limit_reached"
                    break
    finally:
        set_input_provider(None)
        battle_cmd.set_defender_activation_hook(None)

    return {
        "winner": winner,
        "cards_played": cards_played,
        "decisions": provider.decisions,
        "human_factions": sorted(llm_factions),
        "state": engine.state,
    }
