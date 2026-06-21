"""Regression tests for the headless human-mode QA harness and the
pause-point meta-command fix it surfaced."""

import builtins
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai import cli_display
from lod_ai import cli_utils
from lod_ai.cli_utils import set_game_state, set_undo_checkpoint, UndoException
from lod_ai.tools import human_qa


def _feed(inputs):
    it = iter(inputs)
    return lambda *a, **k: next(it)


def test_pause_for_player_honors_meta_commands(tmp_path, monkeypatch):
    """status/save are handled at a pause; a bare Enter returns ''."""
    st = build_state("1775", seed=1)
    eng = Engine(initial_state=st, use_cli=True)
    eng.set_human_factions({"PATRIOTS"})
    set_game_state(eng.state, engine=eng)
    monkeypatch.chdir(tmp_path)  # save writes under ./saves
    # 'save' is handled (loops), then '' returns.
    monkeypatch.setattr(builtins, "input", _feed(["save", ""]))
    out = cli_display.pause_for_player()
    assert out == ""
    assert os.path.isdir("saves") and os.listdir("saves"), "save should write a file"


def test_pause_for_player_undo_raises(monkeypatch):
    """'undo' typed at a pause raises UndoException, like at any prompt."""
    st = build_state("1775", seed=1)
    eng = Engine(initial_state=st, use_cli=True)
    eng.set_human_factions({"PATRIOTS"})
    set_game_state(eng.state, engine=eng)
    set_undo_checkpoint({"spaces": {}})  # any non-None checkpoint
    monkeypatch.setattr(builtins, "input", _feed(["undo"]))
    with pytest.raises(UndoException):
        cli_display.pause_for_player()


def test_pause_for_player_passes_through_non_meta(monkeypatch):
    st = build_state("1775", seed=1)
    eng = Engine(initial_state=st, use_cli=True)
    set_game_state(eng.state, engine=eng)
    monkeypatch.setattr(builtins, "input", _feed(["7"]))
    assert cli_display.pause_for_player() == "7"


def test_harness_run_one_clean_and_exercises_wq_undo(tmp_path):
    r = human_qa.run_one("1775", 1, ("PATRIOTS",), dump_dir=str(tmp_path))
    assert r["wq_undo_fired"] >= 1, "WQ-undo path should be exercised"
    assert r["meta_fired"] >= 1
    # No crash dumps written on a clean game.
    assert not list(tmp_path.glob("*.json"))


def test_harness_save_load_resume(tmp_path):
    assert human_qa.run_resume("1778", 2, ("FRENCH", "PATRIOTS"),
                               dump_dir=str(tmp_path)) is True


def test_harness_multi_human_clean(tmp_path):
    r = human_qa.run_one("1776", 1, ("PATRIOTS", "BRITISH", "INDIANS"),
                         dump_dir=str(tmp_path))
    assert r["prompts"] > 0
    assert not list(tmp_path.glob("*.json"))
