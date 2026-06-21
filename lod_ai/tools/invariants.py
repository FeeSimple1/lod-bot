"""
Runtime invariant checks for the smoke / CI harnesses.

These are meant to be asserted *after every card* during a bot-only or
scripted game, turning rare state-corruption bugs (the kind that survive
playtests) into loud, reproducible failures.

Two invariants:

  * ``check_state_valid`` -- the canonical schema holds
    (delegates to :func:`lod_ai.util.validate.validate_state`).

  * ``check_save_load_roundtrip`` -- serializing the live state to the
    on-disk JSON form and loading it back reproduces the same canonical
    state *and* the same RNG internal state.  Catches fields that do not
    survive persistence and silent state drift.

On failure each helper writes a crash-repro dump (scenario + seed + card
number + traceback + full serialized state) next to the other diagnostic
reports and raises :class:`InvariantError`, so the harness fails loudly
and the failure is reproducible in one command:

    python -m lod_ai.tools.batch_smoke --repro <scenario>:<seed>
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from lod_ai.util.validate import validate_state
from lod_ai.save_game import _serialize_state, _deserialize_state
from lod_ai.tools.state_serializer import serialize_state, save_report


DEFAULT_DUMP_DIR = "crash_dumps"


class InvariantError(AssertionError):
    """Raised when a runtime invariant is violated mid-game."""


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------

# Runtime-only / diagnostic keys that are not part of the persisted game
# state and must not participate in the round-trip equality check.
_VOLATILE_KEYS = frozenset({
    "rng",       # random.Random -- its *internal* state is checked separately
    "rng_log",   # diagnostic trace, not persisted
})


def _canonical(state: Dict[str, Any]) -> Dict[str, Any]:
    """A JSON-comparable snapshot of *state* with volatile keys removed."""
    canon = serialize_state(state)
    for key in _VOLATILE_KEYS:
        canon.pop(key, None)
    return canon


def _roundtrip(state: Dict[str, Any], human_factions: set) -> tuple[dict, set]:
    """Serialize to the on-disk form, round-trip through JSON, reload."""
    disk = _serialize_state(state, human_factions)
    disk = json.loads(json.dumps(disk, default=str))  # simulate the file hop
    return _deserialize_state(disk)


# ---------------------------------------------------------------------------
# Crash-repro dumps
# ---------------------------------------------------------------------------

def dump_repro(
    state: Dict[str, Any],
    *,
    scenario: str,
    seed: int,
    card_number: int,
    kind: str,
    detail: str,
    traceback_str: str = "",
    human_factions: set | None = None,
    setup_method: str | None = None,
    dump_dir: str = DEFAULT_DUMP_DIR,
) -> tuple[str, str]:
    """Write a crash-repro dump and return ``(path, repro_command)``.

    The dump embeds scenario + seed + card so the failure is reproducible
    with a single command.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{kind}_{scenario}_seed{seed}_card{card_number}_{ts}.json"
    path = Path(dump_dir) / fname
    repro_cmd = f"python -m lod_ai.tools.batch_smoke --repro {scenario}:{seed}"
    report = {
        "report_type": kind,
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario,
        "seed": seed,
        "card_number": card_number,
        "detail": detail,
        "repro_command": repro_cmd,
        "traceback": traceback_str,
        "setup_method": setup_method or state.get("setup_method", "unknown"),
        "human_factions": sorted(human_factions) if human_factions else [],
        "game_state": serialize_state(state),
    }
    written = save_report(report, path)
    return written, repro_cmd


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

def check_state_valid(
    state: Dict[str, Any],
    *,
    scenario: str,
    seed: int,
    card_number: int,
    human_factions: set | None = None,
    setup_method: str | None = None,
    dump_dir: str = DEFAULT_DUMP_DIR,
) -> None:
    """Assert the canonical schema holds; dump + raise on violation."""
    try:
        validate_state(state)
    except Exception as exc:  # noqa: BLE001 -- re-raised as InvariantError
        import traceback as _tb
        path, repro = dump_repro(
            state, scenario=scenario, seed=seed, card_number=card_number,
            kind="invariant_validate", detail=f"{type(exc).__name__}: {exc}",
            traceback_str=_tb.format_exc(), human_factions=human_factions,
            setup_method=setup_method, dump_dir=dump_dir,
        )
        raise InvariantError(
            f"validate_state failed at {scenario} seed={seed} card={card_number}: "
            f"{type(exc).__name__}: {exc}\n  dump: {path}\n  repro: {repro}"
        ) from exc


def check_save_load_roundtrip(
    state: Dict[str, Any],
    *,
    scenario: str,
    seed: int,
    card_number: int,
    human_factions: set | None = None,
    setup_method: str | None = None,
    dump_dir: str = DEFAULT_DUMP_DIR,
) -> None:
    """Assert save -> load reproduces the same canonical state + RNG.

    Dumps a repro and raises :class:`InvariantError` on any divergence.
    """
    hf = human_factions if human_factions is not None else state.get("human_factions", set())
    before = _canonical(state)
    rng_before = state["rng"].getstate() if "rng" in state else None

    try:
        reloaded, _hf2 = _roundtrip(state, set(hf))
    except Exception as exc:  # noqa: BLE001
        import traceback as _tb
        path, repro = dump_repro(
            state, scenario=scenario, seed=seed, card_number=card_number,
            kind="invariant_roundtrip", detail=f"serialize/deserialize raised: {exc}",
            traceback_str=_tb.format_exc(), human_factions=set(hf),
            setup_method=setup_method, dump_dir=dump_dir,
        )
        raise InvariantError(
            f"save/load raised at {scenario} seed={seed} card={card_number}: "
            f"{type(exc).__name__}: {exc}\n  dump: {path}\n  repro: {repro}"
        ) from exc

    after = _canonical(reloaded)
    rng_after = reloaded["rng"].getstate() if "rng" in reloaded else None

    diffs = []
    if before != after:
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                diffs.append(key)
    rng_ok = (rng_before == rng_after)

    if diffs or not rng_ok:
        detail_parts = []
        if diffs:
            detail_parts.append(f"non-round-tripping keys: {diffs}")
        if not rng_ok:
            detail_parts.append("RNG internal state not preserved")
        detail = "; ".join(detail_parts)
        path, repro = dump_repro(
            state, scenario=scenario, seed=seed, card_number=card_number,
            kind="invariant_roundtrip", detail=detail,
            human_factions=set(hf), setup_method=setup_method, dump_dir=dump_dir,
        )
        raise InvariantError(
            f"save/load round-trip diverged at {scenario} seed={seed} "
            f"card={card_number}: {detail}\n  dump: {path}\n  repro: {repro}"
        )


def check_all(
    state: Dict[str, Any],
    *,
    scenario: str,
    seed: int,
    card_number: int,
    human_factions: set | None = None,
    setup_method: str | None = None,
    dump_dir: str = DEFAULT_DUMP_DIR,
) -> None:
    """Run every per-card invariant in order."""
    check_state_valid(
        state, scenario=scenario, seed=seed, card_number=card_number,
        human_factions=human_factions, setup_method=setup_method, dump_dir=dump_dir,
    )
    check_save_load_roundtrip(
        state, scenario=scenario, seed=seed, card_number=card_number,
        human_factions=human_factions, setup_method=setup_method, dump_dir=dump_dir,
    )
