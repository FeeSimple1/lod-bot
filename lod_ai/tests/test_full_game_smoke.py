"""
Automated smoke test: run a full 4-bot game to completion.

Uses the 1775 scenario with all four factions as bots.  Draws cards, runs
all bot decisions, resolves events/commands/special activities/Winter Quarters/
victory checks — the full sequence of play.

Validates after every card:
  - No unhandled exceptions
  - State passes validate_state()
  - No negative resources
  - No pieces exceeding caps

Runs 10 times with different random seeds to catch edge cases.
"""

from __future__ import annotations

import logging
import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.util.normalize_state import normalize_state
from lod_ai.util.validate import validate_state
from lod_ai.util.caps import enforce_global_caps, CAP_TABLE
from lod_ai.economy.resources import MAX_RESOURCES, MIN_RESOURCES
from lod_ai.victory import check as victory_check

logger = logging.getLogger(__name__)

# Maximum cards before we declare a runaway game (safety valve).
# 1775 long game has ~66 cards.  200 is generous enough for any scenario.
MAX_CARDS = 200

# All faction piece tags that can appear in spaces.
_ALL_PIECE_TAGS = (
    C.REGULAR_BRI, C.TORY, C.FORT_BRI,
    C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT,
    C.REGULAR_FRE,
    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE,
)


# ------------------------------------------------------------------ #
#  Crash context: captures exactly what was happening when things break
# ------------------------------------------------------------------ #
@dataclass
class CrashContext:
    seed: int
    card_number: int
    card_id: Optional[int] = None
    card_title: Optional[str] = None
    acting_faction: Optional[str] = None
    phase: str = "unknown"
    error: str = ""
    traceback: str = ""


@dataclass
class GameResult:
    seed: int
    cards_played: int = 0
    victory: bool = False
    final_scoring: bool = False
    winner: Optional[str] = None
    crash: Optional[CrashContext] = None
    validation_errors: List[str] = field(default_factory=list)


# ------------------------------------------------------------------ #
#  State validation (beyond validate_state)
# ------------------------------------------------------------------ #
def _check_resources(state: dict) -> List[str]:
    """Return a list of resource violations."""
    errors = []
    for faction, amount in state.get("resources", {}).items():
        if not isinstance(amount, (int, float)):
            errors.append(f"{faction} resources is not a number: {amount!r}")
            continue
        if amount < MIN_RESOURCES:
            errors.append(f"{faction} resources negative: {amount}")
        if amount > MAX_RESOURCES:
            errors.append(f"{faction} resources exceeds cap: {amount}")
    return errors


def _check_piece_caps(state: dict) -> List[str]:
    """Return a list of piece-cap violations (global caps only)."""
    errors = []
    from collections import defaultdict

    live = defaultdict(int)
    for sp in state.get("spaces", {}).values():
        for tag, qty in sp.items():
            if not isinstance(qty, int):
                continue
            for key in CAP_TABLE:
                if tag == key:
                    live[key] += qty

    for key, limit in CAP_TABLE.items():
        if live[key] > limit:
            errors.append(f"Global cap exceeded: {key} has {live[key]} on map (max {limit})")
    return errors


def _check_negative_pieces(state: dict) -> List[str]:
    """Return a list of spaces with negative piece counts."""
    errors = []
    for sid, sp in state.get("spaces", {}).items():
        for tag, qty in sp.items():
            if isinstance(qty, int) and qty < 0:
                errors.append(f"Negative pieces: {tag} in {sid} = {qty}")
    for pool_name in ("available", "unavailable", "casualties"):
        pool = state.get(pool_name, {})
        for tag, qty in pool.items():
            if isinstance(qty, int) and qty < 0:
                errors.append(f"Negative count in {pool_name}: {tag} = {qty}")
    return errors


def _validate_full(state: dict) -> List[str]:
    """Run all validations; return list of error strings (empty = ok)."""
    errors = []

    # Core schema validation
    try:
        validate_state(state)
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"validate_state: {exc}")

    errors.extend(_check_resources(state))
    errors.extend(_check_piece_caps(state))
    errors.extend(_check_negative_pieces(state))
    return errors


# ------------------------------------------------------------------ #
#  Run a single full game
# ------------------------------------------------------------------ #
def run_full_game(seed: int) -> GameResult:
    """Run a complete 4-bot game with the given seed.  Returns a GameResult."""
    result = GameResult(seed=seed)
    ctx = CrashContext(seed=seed, card_number=0)

    try:
        state = build_state("1775", seed=seed)
        engine = Engine(initial_state=state)
        # All factions are bots (human_factions is empty by default).

        card_count = 0
        game_over = False

        while not game_over and card_count < MAX_CARDS:
            ctx.card_number = card_count + 1
            ctx.phase = "draw_card"
            ctx.acting_faction = None

            card = engine.draw_card()
            if card is None:
                # Deck exhausted — game ends via final scoring.
                # The last WQ should have triggered final_scoring already.
                result.final_scoring = True
                break

            ctx.card_id = card.get("id")
            ctx.card_title = card.get("title") or f"Card {card.get('id')}"

            card_count += 1
            ctx.phase = "play_card"

            # Play the card (handles eligibility, bot turns, WQ, etc.)
            engine.play_card(card)

            # Normalize after play
            ctx.phase = "post_card_normalize"
            normalize_state(engine.state)

            # Full validation after every card
            ctx.phase = "post_card_validate"
            errs = _validate_full(engine.state)
            if errs:
                for e in errs:
                    result.validation_errors.append(
                        f"Card #{card_count} ({ctx.card_title}): {e}"
                    )

            # Check if the game ended (victory was achieved during WQ).
            # Look for victory log entries.
            history = engine.state.get("history", [])
            if any("Victory achieved" in str(h) for h in history):
                result.victory = True
                game_over = True
            if any("Winner:" in str(h) for h in history):
                result.final_scoring = True
                # Extract winner from history
                for h in reversed(history):
                    h_str = str(h)
                    if "Winner:" in h_str:
                        result.winner = h_str
                        break
                game_over = True

        result.cards_played = card_count

    except Exception as exc:
        ctx.error = str(exc)
        ctx.traceback = traceback.format_exc()
        result.crash = ctx

    return result


# ------------------------------------------------------------------ #
#  Pytest parametrized test — 10 seeds
# ------------------------------------------------------------------ #
@pytest.mark.parametrize("seed", range(1, 11))
def test_full_game_smoke(seed: int) -> None:
    """Run a full 4-bot game with the given seed.

    Asserts:
      - No unhandled exceptions (no crash).
      - Game state is valid after every card.
    """
    result = run_full_game(seed)

    # Crash check — produce a detailed failure message.
    if result.crash is not None:
        c = result.crash
        pytest.fail(
            f"CRASH at seed={c.seed}, card #{c.card_number} "
            f"({c.card_title or '?'}, id={c.card_id}), "
            f"phase={c.phase}, faction={c.acting_faction}\n"
            f"Error: {c.error}\n"
            f"Traceback:\n{c.traceback}"
        )

    # Validation errors — report all of them.
    if result.validation_errors:
        msg = f"Seed {seed}: {len(result.validation_errors)} validation error(s):\n"
        # Show first 20 to keep output manageable.
        for err in result.validation_errors[:20]:
            msg += f"  - {err}\n"
        if len(result.validation_errors) > 20:
            msg += f"  ... and {len(result.validation_errors) - 20} more\n"
        pytest.fail(msg)

    # The game should have played at least some cards.
    assert result.cards_played > 0, f"Seed {seed}: no cards were played"


# ------------------------------------------------------------------ #
#  Standalone runner for quick manual testing
# ------------------------------------------------------------------ #
def main() -> None:
    """Run 10 games and print a summary."""
    import sys

    seeds = range(1, 11)
    failures = 0

    for seed in seeds:
        print(f"--- Seed {seed} ---")
        result = run_full_game(seed)

        if result.crash:
            c = result.crash
            print(
                f"  CRASH at card #{c.card_number} "
                f"({c.card_title}, id={c.card_id}), "
                f"phase={c.phase}, faction={c.acting_faction}"
            )
            print(f"  Error: {c.error}")
            print(f"  Traceback:\n{c.traceback}")
            failures += 1
        elif result.validation_errors:
            print(f"  VALIDATION ERRORS ({len(result.validation_errors)}):")
            for err in result.validation_errors[:10]:
                print(f"    - {err}")
            failures += 1
        else:
            status = "victory" if result.victory else "final scoring" if result.final_scoring else "deck exhausted"
            print(f"  OK — {result.cards_played} cards played, ended by {status}")
            if result.winner:
                print(f"  {result.winner}")

    print(f"\n{'='*60}")
    print(f"Results: {len(seeds) - failures}/{len(seeds)} passed, {failures} failed")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
