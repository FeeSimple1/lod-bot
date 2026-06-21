"""Regression tests for the runtime invariant gate (lod_ai.tools.invariants)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai.tools import invariants
from lod_ai.tools.batch_smoke import _parse_repro, run_one_game


def _play(scenario, seed, cards):
    st = build_state(scenario, seed=seed)
    eng = Engine(initial_state=st, use_cli=False)
    eng.set_human_factions(set())
    for _ in range(cards):
        c = eng.draw_card()
        if c is None:
            break
        eng.play_card(c)
    return eng


def test_check_all_passes_on_real_games(tmp_path):
    """Invariants hold after every card across scenarios/seeds."""
    for scen in ("1775", "1776", "1778"):
        for seed in (1, 2):
            st = build_state(scen, seed=seed)
            eng = Engine(initial_state=st, use_cli=False)
            eng.set_human_factions(set())
            for n in range(1, 16):
                c = eng.draw_card()
                if c is None:
                    break
                eng.play_card(c)
                invariants.check_all(
                    eng.state, scenario=scen, seed=seed, card_number=n,
                    human_factions=set(), dump_dir=str(tmp_path),
                )


def test_save_load_roundtrip_preserves_rng(tmp_path):
    eng = _play("1778", 7, 6)
    # Should not raise.
    invariants.check_save_load_roundtrip(
        eng.state, scenario="1778", seed=7, card_number=6,
        human_factions=set(), dump_dir=str(tmp_path),
    )


def test_validate_failure_raises_and_dumps(tmp_path):
    """A corrupted state raises InvariantError and writes a repro dump."""
    eng = _play("1775", 1, 4)
    sid = next(iter(eng.state["spaces"]))
    eng.state["spaces"][sid]["CONTINENTAL"] = -5  # illegal negative count

    with pytest.raises(invariants.InvariantError):
        invariants.check_state_valid(
            eng.state, scenario="1775", seed=1, card_number=4,
            human_factions=set(), dump_dir=str(tmp_path),
        )
    dumps = list(tmp_path.glob("invariant_validate_*.json"))
    assert dumps, "expected a crash-repro dump to be written"
    text = dumps[0].read_text()
    assert "--repro 1775:1" in text


def test_roundtrip_failure_raises_and_dumps(tmp_path):
    """A field that cannot survive persistence is caught and dumped."""
    eng = _play("1775", 2, 4)
    # Inject a non-JSON-round-trippable object under a persisted key: a dict
    # keyed by a tuple becomes a string key on reload, so before != after.
    eng.state["control"][("X", "Y")] = "BRITISH"

    with pytest.raises(invariants.InvariantError):
        invariants.check_save_load_roundtrip(
            eng.state, scenario="1775", seed=2, card_number=4,
            human_factions=set(), dump_dir=str(tmp_path),
        )
    dumps = list(tmp_path.glob("invariant_roundtrip_*.json"))
    assert dumps, "expected a roundtrip dump to be written"


def test_dump_repro_embeds_one_command(tmp_path):
    eng = _play("1776", 3, 3)
    path, repro = invariants.dump_repro(
        eng.state, scenario="1776", seed=3, card_number=3,
        kind="crash", detail="boom", dump_dir=str(tmp_path),
    )
    assert os.path.exists(path)
    assert repro == "python -m lod_ai.tools.batch_smoke --repro 1776:3"


def test_parse_repro():
    assert _parse_repro(["--repro", "1778:7"]) == ("1778", 7)
    assert _parse_repro(["--repro=1775:12"]) == ("1775", 12)
    assert _parse_repro(["--repro", "1776"]) == ("1776", 1)
    assert _parse_repro(["--large"]) is None


def test_run_one_game_with_invariants_clean(tmp_path):
    """A full bot game with invariants on completes without INVARIANT/CRASH."""
    result = run_one_game("1775", 1, check_invariants=True, dump_dir=str(tmp_path))
    assert result["end_reason"] not in ("INVARIANT", "CRASH"), result.get("error")
    assert result["error"] is None
