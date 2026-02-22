import json
import random
import re
from lod_ai.state import setup_state, map_loader
from lod_ai import rules_consts as C


def _id_from_val(val):
    m = re.match(r"(?:Card_)?(\d{1,3})$", str(val))
    return int(m.group(1)) if m else None


def test_build_state_standard_deck(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
    }
    path = tmp_path / "scen.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)

    state = setup_state.build_state(path.name, seed=1, setup_method="standard")

    assert state["deck"]  # non-empty
    assert state["setup_method"] == "standard"


def test_build_state_period_deck(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
    }
    path = tmp_path / "scen_hist.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)

    state = setup_state.build_state(path.name, seed=1, setup_method="period")

    assert state["deck"]  # non-empty
    assert state["setup_method"] == "period"


def test_load_map_default_path():
    mp = map_loader.load_map()
    assert isinstance(mp, dict)
    assert "Boston" in mp
    assert len(mp) >= 22


def test_deck_lengths_standard():
    long_state = setup_state.build_state("1775", seed=2, setup_method="standard")
    medium_state = setup_state.build_state("1776", seed=3, setup_method="standard")
    short_state = setup_state.build_state("1778", seed=4, setup_method="standard")

    assert len(long_state["deck"]) == 66
    assert len(medium_state["deck"]) == 44
    assert len(short_state["deck"]) == 33


def test_deck_lengths_period():
    long_state = setup_state.build_state("1775", seed=5, setup_method="period")
    medium_state = setup_state.build_state("1776", seed=6, setup_method="period")
    short_state = setup_state.build_state("1778", seed=7, setup_method="period")

    assert len(long_state["deck"]) == 66
    assert len(medium_state["deck"]) == 44
    assert len(short_state["deck"]) == 33


def test_unavailable_format_a_keys(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
        "unavailable": {
            "British_Regular_Unavailable": 2,
            "French_Regular_Unavailable": 1,
            "British_Tory_Unavailable": 3,
        },
    }
    path = tmp_path / "scen_a.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)

    state = setup_state.build_state(path.name, seed=1, setup_method="standard")

    assert state["available"][C.REGULAR_BRI] == C.MAX_REGULAR_BRI - 2
    assert state["unavailable"][C.REGULAR_BRI] == 2
    assert state["available"][C.REGULAR_FRE] == C.MAX_REGULAR_FRE - 1
    assert state["unavailable"][C.REGULAR_FRE] == 1
    assert state["available"][C.TORY] == C.MAX_TORY - 3
    assert state["unavailable"][C.TORY] == 3


def test_unavailable_format_b_keys(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
        "unavailable": {
            C.REGULAR_BRI: 1,
            C.REGULAR_FRE: 2,
        },
    }
    path = tmp_path / "scen_b.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)

    state = setup_state.build_state(path.name, seed=1, setup_method="standard")

    assert state["available"][C.REGULAR_BRI] == C.MAX_REGULAR_BRI - 1
    assert state["unavailable"][C.REGULAR_BRI] == 1
    assert state["available"][C.REGULAR_FRE] == C.MAX_REGULAR_FRE - 2
    assert state["unavailable"][C.REGULAR_FRE] == 2


def test_wq_insertion_bottom_4():
    """Winter Quarters card must be shuffled into bottom 4 event cards only (rulebook setup)."""
    from lod_ai.state.setup_state import _insert_wq

    # Create a 10-card pile with identifiable cards
    pile = [{"id": i, "title": f"Event {i}"} for i in range(10)]
    wq = {"id": 99, "title": "Winter Quarters", "winter_quarters": True}

    # Run 1000 times and track where WQ lands
    positions = []
    for seed in range(1000):
        rng = random.Random(seed)
        result = _insert_wq(list(pile), wq, rng)
        pos = next(i for i, c in enumerate(result) if c["id"] == 99)
        positions.append(pos)

    # Pile is 11 cards (10 events + 1 WQ). WQ should only appear in
    # positions 6-10 (the last 5 cards = bottom 4 events + WQ shuffled).
    # It should NEVER appear in positions 0-5.
    assert min(positions) >= 6, f"WQ appeared at position {min(positions)}, earliest allowed is 6"
    assert max(positions) <= 10
