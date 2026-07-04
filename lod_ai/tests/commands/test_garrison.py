"""Garrison Command (§3.2.2) — Blockade exclusions and Skirmish tracking.

Session 38: garrison.py's `_is_blockaded` read a `state["naval"]["blockades"]`
dict that nothing ever populates (the real store is
state["markers"][BLOCKADE]["on_map"], see lod_ai.util.naval), so the §3.2.2
exclusions — "A Blockaded City or units starting there may not be included
in any part of a Garrison Command" — were dead code.  These tests pin the
now-live checks, plus skirmish.execute's recording of its space for the
§8.4.1 Garrison rule ("Do not move Regulars to any City where a Skirmish
has been executed").
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import garrison
from lod_ai.special_activities import skirmish
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 3},
            "New_York_City": {C.REGULAR_BRI: 1},
            "Quebec_City": {C.REGULAR_BRI: 2},
        },
        "resources": {C.BRITISH: 5, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "support": {},
        "control": {},
        "markers": {},
        "rng": __import__("random").Random(1),
        "fni_level": 0,
    }


def _blockade(state, city):
    state.setdefault("markers", {})[C.BLOCKADE] = {"pool": 0, "on_map": {city}}


def test_garrison_rejects_blockaded_source():
    """§3.2.2: units starting in a Blockaded City may not be included."""
    state = simple_state()
    _blockade(state, "Boston")
    with pytest.raises(ValueError, match="Blockaded"):
        garrison.execute(state, C.BRITISH, {}, {"Boston": {"New_York_City": 1}})


def test_garrison_rejects_blockaded_destination():
    """§3.2.2: Regulars may not move to a Blockaded City."""
    state = simple_state()
    _blockade(state, "New_York_City")
    with pytest.raises(ValueError, match="Blockaded"):
        garrison.execute(state, C.BRITISH, {}, {"Boston": {"New_York_City": 1}})


def test_garrison_rejects_blockaded_displacement_city():
    """§3.2.2: displacement City must not be Blockaded."""
    state = simple_state()
    state["spaces"]["Quebec_City"][C.MILITIA_A] = 1
    _blockade(state, "Quebec_City")
    with pytest.raises(ValueError, match="Blockaded"):
        garrison.execute(
            state, C.BRITISH, {}, {"Boston": {"New_York_City": 1}},
            displace_city="Quebec_City", displace_target="Quebec",
        )


def test_garrison_allows_unblockaded_moves():
    """Sanity: the same move succeeds when no Blockade is present."""
    state = simple_state()
    garrison.execute(state, C.BRITISH, {}, {"Boston": {"New_York_City": 1}})
    assert state["spaces"]["New_York_City"][C.REGULAR_BRI] == 2
    assert state["spaces"]["Boston"][C.REGULAR_BRI] == 2
    assert state["resources"][C.BRITISH] == 3  # 2 Resources total


def test_skirmish_records_space_for_garrison_exclusion():
    """§8.4.1: "Do not move Regulars to any City where a Skirmish has
    been executed" — skirmish.execute records its space in
    state["_turn_skirmished_spaces"] (cleared per turn in base_bot)."""
    state = simple_state()
    state["spaces"]["Boston"][C.MILITIA_A] = 1
    skirmish.execute(state, C.BRITISH, {}, "Boston", option=1)
    assert state["_turn_skirmished_spaces"] == {"Boston"}
