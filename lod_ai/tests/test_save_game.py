"""Tests for save/load game functionality."""
from __future__ import annotations

import json
import os
import random
import shutil
import tempfile
from copy import deepcopy

import pytest

from lod_ai.save_game import (
    SAVE_DIR,
    _convert_sets,
    _deserialize_state,
    _serialize_state,
    list_saves,
    load_game,
    save_game,
)
from lod_ai.state.setup_state import build_state


@pytest.fixture
def tmp_save_dir(monkeypatch, tmp_path):
    """Redirect SAVE_DIR to a temp directory for isolated tests."""
    d = str(tmp_path / "saves")
    monkeypatch.setattr("lod_ai.save_game.SAVE_DIR", d)
    return d


class TestConvertSets:
    def test_set_to_sorted_list(self):
        assert _convert_sets({"a", "c", "b"}) == ["a", "b", "c"]

    def test_nested_sets(self):
        data = {"markers": {"on_map": {"X", "Y"}}, "items": [{"s": {3, 1, 2}}]}
        result = _convert_sets(data)
        assert result["markers"]["on_map"] == ["X", "Y"]
        assert result["items"][0]["s"] == [1, 2, 3]

    def test_no_sets_unchanged(self):
        data = {"a": 1, "b": [2, 3], "c": "hello"}
        assert _convert_sets(data) == data


class TestSerializeDeserialize:
    def test_round_trip_preserves_rng(self):
        state = {"rng": random.Random(42), "foo": "bar"}
        serialized = _serialize_state(state, set())
        restored, hf = _deserialize_state(serialized)
        # RNG should produce the same sequence
        orig_rng = random.Random(42)
        assert restored["rng"].random() == orig_rng.random()
        assert restored["foo"] == "bar"

    def test_round_trip_preserves_sets(self):
        state = {
            "rng": random.Random(1),
            "markers": {
                "Propaganda": {"pool": 3, "on_map": {"Boston", "Quebec"}},
            },
            "eligible_next": {"BRITISH", "FRENCH"},
            "ineligible_next": {"PATRIOTS"},
        }
        serialized = _serialize_state(state, {"BRITISH"})
        restored, hf = _deserialize_state(serialized)
        assert isinstance(restored["markers"]["Propaganda"]["on_map"], set)
        assert restored["markers"]["Propaganda"]["on_map"] == {"Boston", "Quebec"}
        assert isinstance(restored["eligible_next"], set)
        assert restored["eligible_next"] == {"BRITISH", "FRENCH"}
        assert isinstance(restored["ineligible_next"], set)
        assert hf == {"BRITISH"}

    def test_human_factions_stored(self):
        state = {"rng": random.Random(1)}
        serialized = _serialize_state(state, {"PATRIOTS", "INDIANS"})
        assert serialized["_save_meta"]["human_factions"] == ["INDIANS", "PATRIOTS"]

    def test_metadata_version(self):
        state = {"rng": random.Random(1)}
        serialized = _serialize_state(state, set())
        assert serialized["_save_meta"]["version"] == 1
        assert "save_time" in serialized["_save_meta"]


class TestSaveLoad:
    def test_save_creates_file(self, tmp_save_dir):
        state = build_state("1775", seed=99)
        state["_seed"] = 99
        state["_scenario"] = "1775"
        filepath = save_game(state, set())
        assert os.path.exists(filepath)
        assert filepath.startswith(tmp_save_dir)

    def test_save_load_round_trip(self, tmp_save_dir):
        state = build_state("1775", seed=42)
        state["_seed"] = 42
        state["_scenario"] = "1775"
        state["_setup_method"] = "standard"
        human = {"BRITISH"}

        filepath = save_game(state, human)
        loaded_state, loaded_human = load_game(filepath)

        assert loaded_human == human
        assert loaded_state.get("_seed") == 42 or loaded_state.get("seed") == 42
        assert loaded_state.get("_scenario") == "1775" or loaded_state.get("scenario") == "1775"
        # RNG should be a Random instance
        assert isinstance(loaded_state["rng"], random.Random)
        # Marker on_map should be sets
        for tag, entry in loaded_state.get("markers", {}).items():
            if "on_map" in entry:
                assert isinstance(entry["on_map"], set), f"markers[{tag}].on_map should be set"

    def test_save_with_custom_filename(self, tmp_save_dir):
        state = {"rng": random.Random(1), "seed": 1}
        filepath = save_game(state, set(), filename="mysave")
        assert filepath.endswith("mysave.json")
        assert os.path.exists(filepath)

    def test_save_with_json_extension(self, tmp_save_dir):
        state = {"rng": random.Random(1), "seed": 1}
        filepath = save_game(state, set(), filename="test.json")
        assert filepath.endswith("test.json")
        assert not filepath.endswith(".json.json")

    def test_autosave_overwrites(self, tmp_save_dir):
        state = {"rng": random.Random(1), "seed": 1}
        fp1 = save_game(state, set(), filename="autosave")
        state["seed"] = 2
        fp2 = save_game(state, set(), filename="autosave")
        assert fp1 == fp2
        with open(fp2) as f:
            data = json.load(f)
        assert data.get("seed") == 2


class TestListSaves:
    def test_list_empty(self, tmp_save_dir):
        saves = list_saves()
        assert saves == []

    def test_list_returns_saves(self, tmp_save_dir):
        state = {"rng": random.Random(1), "seed": 42, "scenario": "1775"}
        save_game(state, {"BRITISH"}, filename="save1")
        save_game(state, set(), filename="save2")

        saves = list_saves()
        assert len(saves) == 2
        filenames = {s["filename"] for s in saves}
        assert "save1.json" in filenames
        assert "save2.json" in filenames

    def test_list_ignores_non_json(self, tmp_save_dir):
        os.makedirs(tmp_save_dir, exist_ok=True)
        with open(os.path.join(tmp_save_dir, "notes.txt"), "w") as f:
            f.write("not a save file")
        saves = list_saves()
        assert len(saves) == 0
