"""
Full-game smoke tests: run complete 4-bot games to completion.

Runs 10 seeds × 3 scenarios (1775, 1776, 1778) = 30 games.
After every card, validates state integrity:
  - Resources in [0, 50] for each faction
  - FNI in [0, 3]
  - No negative piece counts in spaces, available, unavailable, casualties
  - Total of each piece type across map + pools does not exceed caps
  - British Forts on map <= 6, Patriot Forts on map <= 6, Villages on map <= 12
  - Support/opposition in [-2, 2] for every space
  - state["control"] has an entry for every space in state["spaces"]

Every crash is a real bug — exceptions propagate with full context.
"""

from __future__ import annotations

import traceback
from collections import defaultdict

import pytest

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.util.normalize_state import normalize_state
from lod_ai.victory import check as victory_check

# Safety limit: no game should exceed this many cards.
MAX_CARDS = 200

# Piece caps: total across map + available + unavailable + casualties
_PIECE_CAPS = {
    C.REGULAR_BRI: C.MAX_REGULAR_BRI,
    C.TORY:        C.MAX_TORY,
    C.REGULAR_PAT: C.MAX_REGULAR_PAT,
    C.REGULAR_FRE: C.MAX_REGULAR_FRE,
    C.FORT_BRI:    C.MAX_FORT_BRI,
    C.FORT_PAT:    C.MAX_FORT_PAT,
    C.VILLAGE:     C.MAX_VILLAGE,
    # Militia (A + U share a pool of MAX_MILITIA)
    # War Party (A + U share a pool of MAX_WAR_PARTY)
}

# Tags that share a pool: active + underground variants
_SHARED_POOL_TAGS = {
    "militia": (C.MILITIA_A, C.MILITIA_U),
    "warparty": (C.WARPARTY_A, C.WARPARTY_U),
}
_SHARED_POOL_CAPS = {
    "militia": C.MAX_MILITIA,
    "warparty": C.MAX_WAR_PARTY,
}


# ------------------------------------------------------------------
#  State validation
# ------------------------------------------------------------------

def _count_on_map(state: dict, tag: str) -> int:
    """Count total pieces of *tag* across all spaces."""
    return sum(sp.get(tag, 0) for sp in state["spaces"].values())


def _count_in_pools(state: dict, tag: str) -> int:
    """Count pieces of *tag* across available + unavailable + casualties."""
    total = 0
    for pool in ("available", "unavailable", "casualties"):
        total += state.get(pool, {}).get(tag, 0)
    return total


def validate_integrity(state: dict) -> list[str]:
    """Return a list of integrity violations (empty = OK)."""
    errors: list[str] = []

    # 1. Resources in [0, 50]
    for faction in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS):
        res = state.get("resources", {}).get(faction, 0)
        if not isinstance(res, (int, float)):
            errors.append(f"{faction} resources is not a number: {res!r}")
        elif res < 0:
            errors.append(f"{faction} resources negative: {res}")
        elif res > 50:
            errors.append(f"{faction} resources above 50: {res}")

    # 2. FNI in [0, 3]
    fni = state.get("fni_level", 0)
    if isinstance(fni, int) and (fni < 0 or fni > 3):
        errors.append(f"fni_level out of range [0,3]: {fni}")

    # 3. No negative piece counts in spaces
    for sid, sp in state.get("spaces", {}).items():
        for tag, qty in sp.items():
            if isinstance(qty, int) and qty < 0:
                errors.append(f"Negative pieces: {tag} in {sid} = {qty}")

    # 4. No negative counts in pools
    for pool_name in ("available", "unavailable", "casualties"):
        pool = state.get(pool_name, {})
        for tag, qty in pool.items():
            if isinstance(qty, int) and qty < 0:
                errors.append(f"Negative count in {pool_name}: {tag} = {qty}")

    # 5. Per-piece-type total across map + pools does not exceed caps
    for tag, cap in _PIECE_CAPS.items():
        on_map = _count_on_map(state, tag)
        in_pools = _count_in_pools(state, tag)
        total = on_map + in_pools
        if total > cap:
            errors.append(
                f"Piece cap exceeded: {tag} total={total} "
                f"(map={on_map}, pools={in_pools}, cap={cap})"
            )

    # Shared-pool caps (militia, warparty)
    for pool_name, tags in _SHARED_POOL_TAGS.items():
        cap = _SHARED_POOL_CAPS[pool_name]
        on_map = sum(_count_on_map(state, t) for t in tags)
        # The pool key for available/casualties uses the underground variant
        pool_tag = tags[1]  # _U variant
        in_pools = _count_in_pools(state, pool_tag)
        # Also count the _A variant in pools (shouldn't normally be there,
        # but check anyway)
        in_pools += _count_in_pools(state, tags[0])
        total = on_map + in_pools
        if total > cap:
            errors.append(
                f"Shared pool cap exceeded: {pool_name} total={total} "
                f"(map={on_map}, pools={in_pools}, cap={cap})"
            )

    # 6. Forts on map <= 6, Villages on map <= 12
    brit_forts = _count_on_map(state, C.FORT_BRI)
    if brit_forts > 6:
        errors.append(f"British Forts on map: {brit_forts} > 6")
    pat_forts = _count_on_map(state, C.FORT_PAT)
    if pat_forts > 6:
        errors.append(f"Patriot Forts on map: {pat_forts} > 6")
    villages = _count_on_map(state, C.VILLAGE)
    if villages > 12:
        errors.append(f"Villages on map: {villages} > 12")

    # 7. Support/opposition in [-2, 2]
    for sid, lvl in state.get("support", {}).items():
        if isinstance(lvl, int) and (lvl < -2 or lvl > 2):
            errors.append(f"Support out of range for {sid}: {lvl}")

    # 8. state["control"] has entry for every space
    control = state.get("control", {})
    for sid in state.get("spaces", {}):
        if sid not in control:
            errors.append(f"Missing control entry for space: {sid}")

    return errors


# ------------------------------------------------------------------
#  Game runner
# ------------------------------------------------------------------

def run_full_game(scenario: str, seed: int) -> None:
    """Run a complete 4-bot game. Raises on any crash or validation failure."""
    state = build_state(scenario, seed=seed)
    engine = Engine(initial_state=state)
    # All factions are bots by default (human_factions is empty).

    card_count = 0
    current_card_info = "none"

    while card_count < MAX_CARDS:
        # Draw
        try:
            card = engine.draw_card()
        except Exception:
            raise AssertionError(
                f"CRASH during draw_card | scenario={scenario}, seed={seed}, "
                f"card_count={card_count}, last_card={current_card_info}\n"
                f"{traceback.format_exc()}"
            )

        if card is None:
            # Deck exhausted — game ends.
            break

        card_id = card.get("id", "?")
        card_title = card.get("title", f"Card {card_id}")
        current_card_info = f"#{card_id} '{card_title}'"
        card_count += 1

        # Play
        try:
            engine.play_card(card)
        except Exception:
            raise AssertionError(
                f"CRASH during play_card | scenario={scenario}, seed={seed}, "
                f"card #{card_count} ({current_card_info}), "
                f"active_faction={engine.state.get('active', '?')}\n"
                f"{traceback.format_exc()}"
            ) from None

        # Normalize after play
        try:
            normalize_state(engine.state)
        except Exception:
            raise AssertionError(
                f"CRASH during normalize_state | scenario={scenario}, seed={seed}, "
                f"card #{card_count} ({current_card_info})\n"
                f"{traceback.format_exc()}"
            ) from None

        # Validate state integrity
        errors = validate_integrity(engine.state)
        if errors:
            msg = (
                f"Validation failures after card #{card_count} "
                f"({current_card_info}) | scenario={scenario}, seed={seed}:\n"
            )
            for err in errors:
                msg += f"  - {err}\n"
            raise AssertionError(msg)

        # Check victory
        if victory_check(engine.state):
            break

    else:
        # Loop completed without break — safety limit hit
        pytest.fail(
            f"Game did not terminate within {MAX_CARDS} cards | "
            f"scenario={scenario}, seed={seed}"
        )

    assert card_count > 0, f"No cards played | scenario={scenario}, seed={seed}"


# ------------------------------------------------------------------
#  Parametrized tests — 10 seeds × 3 scenarios
# ------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(10))
def test_full_game_1775(seed: int) -> None:
    """Run a full 4-bot game with the 1775 (long) scenario."""
    run_full_game("1775", seed)


@pytest.mark.parametrize("seed", range(10))
def test_full_game_1776(seed: int) -> None:
    """Run a full 4-bot game with the 1776 (medium) scenario."""
    run_full_game("1776", seed)


@pytest.mark.parametrize("seed", range(10))
def test_full_game_1778(seed: int) -> None:
    """Run a full 4-bot game with the 1778 (short) scenario."""
    run_full_game("1778", seed)
