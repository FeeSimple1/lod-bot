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
    baseline: Dict[str, Any] | None = None,
) -> None:
    """Run every per-card invariant in order."""
    check_state_valid(
        state, scenario=scenario, seed=seed, card_number=card_number,
        human_factions=human_factions, setup_method=setup_method, dump_dir=dump_dir,
    )
    check_rules_properties(
        state, scenario=scenario, seed=seed, card_number=card_number,
        human_factions=human_factions, setup_method=setup_method, dump_dir=dump_dir,
        baseline=baseline,
    )
    check_save_load_roundtrip(
        state, scenario=scenario, seed=seed, card_number=card_number,
        human_factions=human_factions, setup_method=setup_method, dump_dir=dump_dir,
    )


# ---------------------------------------------------------------------------
# Rules-derived properties (ROADMAP Piece 4, Session 67)
# ---------------------------------------------------------------------------
# These encode *rules*, not implementation:
#   - Piece conservation per component family (§1.2): map + Available +
#     Unavailable + Casualties + Out-of-play is constant.  Session 66 (C8)
#     verified all three scenarios sum EXACTLY to the boxed maxima at setup;
#     this keeps it true after every card.
#   - Marker conservation (Propaganda/Raid/Blockade) against a per-game
#     baseline captured at setup (the Session 56/61 Blockade-destruction
#     class of bug).
#   - Reserves and the West Indies are always Neutral (§1.6.2).
#   - Resources within [0, 50] (§1.7).
#   - 0 <= FNI <= 3 (§1.9; the fni_ceiling relation is enforced by
#     util.naval.adjust_fni's clamp and allows a legal overhang when the
#     ceiling drops below an already-set level, so it is not asserted here).
#   - Control map equals recomputation from piece counts (§1.7 control is
#     derived state; catches stale-control drift after any mutation).
#   - §8.3.3 post-hoc: no bot-CHOSEN Event (flowchart Event-or-Command
#     path) nets a Support-minus-Opposition shift favoring the enemy side.
#     base_bot records d_before/d_after at the choice site.

from lod_ai import rules_consts as C
from lod_ai.map import adjacency as _adj
from lod_ai.board import control as _control_mod

_FAMILY_TAGS = {
    "British_Regular":     ((C.REGULAR_BRI, C.BRIT_UNAVAIL), C.MAX_REGULAR_BRI),
    "British_Tory":        ((C.TORY, C.TORY_UNAVAIL),        C.MAX_TORY),
    "French_Regular":      ((C.REGULAR_FRE, C.FRENCH_UNAVAIL), C.MAX_REGULAR_FRE),
    "Patriot_Continental": ((C.REGULAR_PAT,),                C.MAX_REGULAR_PAT),
    "Patriot_Militia":     ((C.MILITIA_A, C.MILITIA_U),      C.MAX_MILITIA),
    "Indian_War_Party":    ((C.WARPARTY_A, C.WARPARTY_U),    C.MAX_WAR_PARTY),
    "Village":             ((C.VILLAGE,),                    C.MAX_VILLAGE),
    "British_Fort":        ((C.FORT_BRI,),                   C.MAX_FORT_BRI),
    "Patriot_Fort":        ((C.FORT_PAT,),                   C.MAX_FORT_PAT),
}
_TAG_TO_FAMILY = {t: fam for fam, (tags, _mx) in _FAMILY_TAGS.items() for t in tags}
_POOL_KEYS = ("available", "unavailable", "casualties", "out_of_play")


def piece_census(state: Dict[str, Any]) -> Dict[str, int]:
    """Sum every piece family across the map and all holding boxes."""
    counts = {fam: 0 for fam in _FAMILY_TAGS}
    for sp in (state.get("spaces") or {}).values():
        if not isinstance(sp, dict):
            continue
        for tag, qty in sp.items():
            fam = _TAG_TO_FAMILY.get(tag)
            if fam and isinstance(qty, int) and qty > 0:
                counts[fam] += qty
    for pool_key in _POOL_KEYS:
        for tag, qty in (state.get(pool_key) or {}).items():
            fam = _TAG_TO_FAMILY.get(tag)
            if fam and isinstance(qty, int) and qty > 0:
                counts[fam] += qty
    return counts


def marker_census(state: Dict[str, Any]) -> Dict[str, int]:
    """Total physical markers per tag: pool + on-map (+ Unavailable for
    Blockade/Squadron counters, §4.5)."""
    out = {}
    markers = state.get("markers") or {}
    unavail = state.get("unavailable") or {}
    for tag in (C.PROPAGANDA, C.RAID, C.BLOCKADE):
        entry = markers.get(tag) or {}
        om = entry.get("on_map") or ()
        # Q23: Propaganda/Raid stack — on_map is {sid: count}.
        on_map_total = (sum(int(v) for v in om.values())
                        if isinstance(om, dict) else len(om))
        total = int(entry.get("pool", 0) or 0) + on_map_total
        if tag == C.BLOCKADE:
            total += int(unavail.get(C.BLOCKADE, 0) or 0)
        out[tag] = total
    return out


def capture_baseline(state: Dict[str, Any]) -> Dict[str, Any]:
    """Capture per-game conserved totals at setup.  Marker totals are
    scenario-dependent; piece families are anchored to MAX_* directly."""
    return {"markers": marker_census(state)}


def _expected_control(state: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute control exactly as board.control.refresh_control does,
    without mutating the state."""
    expected: Dict[str, Any] = {}
    for sid, sp in (state.get("spaces") or {}).items():
        if not isinstance(sp, dict):
            continue
        rebels = _control_mod._tally(sp, _control_mod.REB_PREFIXES)
        bri = _control_mod._tally(sp, _control_mod.BRI_PREFIXES)
        ind = _control_mod._tally(sp, _control_mod.IND_PREFIXES) + sp.get(C.VILLAGE, 0)
        royalist = bri + ind
        control = None
        if rebels > royalist:
            control = "REBELLION"
        elif royalist > rebels and bri > 0:
            control = "BRITISH"
        expected[str(sid)] = control
    return expected


_ROYALIST = (C.BRITISH, C.INDIANS)
_REBEL = (C.PATRIOTS, C.FRENCH)


def _rules_property_violations(state: Dict[str, Any],
                               baseline: Dict[str, Any] | None) -> list[str]:
    problems: list[str] = []

    # §1.2 piece conservation
    census = piece_census(state)
    for fam, (_tags, expected) in _FAMILY_TAGS.items():
        if census[fam] != expected:
            problems.append(
                f"piece conservation (S1.2): {fam} census {census[fam]} != {expected}")

    # Marker conservation / bounds
    markers = marker_census(state)
    if markers[C.PROPAGANDA] > C.MAX_PROPAGANDA:
        problems.append(
            f"marker bound (S3.3.4): Propaganda {markers[C.PROPAGANDA]} > {C.MAX_PROPAGANDA}")
    if markers[C.RAID] > C.MAX_RAID:
        problems.append(
            f"marker bound (S3.4.4): Raid {markers[C.RAID]} > {C.MAX_RAID}")
    if baseline is not None:
        for tag, expected in (baseline.get("markers") or {}).items():
            if markers.get(tag) != expected:
                problems.append(
                    f"marker conservation: {tag} census {markers.get(tag)} != setup {expected}")

    # §1.6.2 Reserves / West Indies always Neutral
    for sid, lvl in (state.get("support") or {}).items():
        if lvl == 0:
            continue
        if sid == C.WEST_INDIES_ID or _adj.space_type(sid) == "Reserve":
            problems.append(
                f"support (S1.6.2): {sid} is a Reserve/West Indies but at level {lvl}")

    # §1.7 Resources within [0, 50]
    for faction, val in (state.get("resources") or {}).items():
        if not isinstance(val, int) or val < C.MIN_RESOURCES or val > C.MAX_RESOURCES:
            problems.append(f"resources (S1.7): {faction} at {val!r}, outside [0, 50]")

    # §1.9 FNI track bounds
    fni = state.get("fni_level", 0) or 0
    if not isinstance(fni, int) or fni < 0 or fni > C.MAX_FNI:
        problems.append(f"FNI (S1.9): fni_level {fni!r} outside [0, {C.MAX_FNI}]")

    # Control is derived state (§1.7): stored map == recomputation
    expected_ctrl = _expected_control(state)
    stored_ctrl = state.get("control") or {}
    if stored_ctrl != expected_ctrl:
        stale = sorted(
            sid for sid in set(expected_ctrl) | set(stored_ctrl)
            if stored_ctrl.get(sid) != expected_ctrl.get(sid))
        problems.append(f"control staleness: recomputation differs at {stale}")

    # §8.3.3 post-hoc: bot-chosen Events must not net-shift the
    # Support-Opposition difference in favor of the enemy side.
    audit = state.get("event_choice_audit")
    if audit:
        for entry in audit:
            fac = entry.get("faction")
            d_b, d_a = entry.get("d_before"), entry.get("d_after")
            if fac in _ROYALIST and d_a < d_b:
                problems.append(
                    f"S8.3.3 net shift: {fac} chose event card {entry.get('card')} "
                    f"but Support-Opposition moved {d_b} -> {d_a} (favors Rebellion)")
            elif fac in _REBEL and d_a > d_b:
                problems.append(
                    f"S8.3.3 net shift: {fac} chose event card {entry.get('card')} "
                    f"but Support-Opposition moved {d_b} -> {d_a} (favors Royalists)")
        if not problems:
            audit.clear()  # checked; keep the key bounded

    return problems


def check_rules_properties(
    state: Dict[str, Any],
    *,
    scenario: str,
    seed: int,
    card_number: int,
    human_factions: set | None = None,
    setup_method: str | None = None,
    dump_dir: str = DEFAULT_DUMP_DIR,
    baseline: Dict[str, Any] | None = None,
) -> None:
    """Assert the rules-derived properties; dump + raise on violation."""
    problems = _rules_property_violations(state, baseline)
    if not problems:
        return
    detail = "; ".join(problems)
    path, repro = dump_repro(
        state, scenario=scenario, seed=seed, card_number=card_number,
        kind="invariant_rules", detail=detail,
        human_factions=human_factions, setup_method=setup_method,
        dump_dir=dump_dir,
    )
    raise InvariantError(
        f"rules properties violated at {scenario} seed={seed} card={card_number}: "
        f"{detail}\n  dump: {path}\n  repro: {repro}"
    )
