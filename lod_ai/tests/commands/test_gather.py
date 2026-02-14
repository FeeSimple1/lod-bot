import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import gather
from lod_ai import rules_consts as C


def _base_state():
    return {
        "spaces": {
            "Province_A": {
                C.WARPARTY_U: 3, C.WARPARTY_A: 1, C.VILLAGE: 1,
                "indian_reserve": False,
            },
            "Province_B": {
                C.WARPARTY_U: 2,
                "indian_reserve": False,
            },
        },
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 5},
        "available": {C.WARPARTY_U: 10, C.VILLAGE: 2},
        "support": {"Province_A": C.NEUTRAL, "Province_B": C.NEUTRAL},
        "rng": __import__('random').Random(1),
    }


def test_move_requires_village(monkeypatch):
    """§3.4.1: Move-and-flip action requires at least one Village in the
    destination Province."""
    monkeypatch.setattr(gather, "refresh_control", lambda s: None)
    monkeypatch.setattr(gather, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(gather, "is_adjacent", lambda a, b: True)
    state = _base_state()
    # Province_B has no Village — move should be rejected
    with pytest.raises(ValueError, match="no Village"):
        gather.execute(
            state, C.INDIANS, {},
            ["Province_B"],
            move_plan=[("Province_A", "Province_B", 1)],
        )


def test_move_with_village_succeeds(monkeypatch):
    """Move-and-flip works when destination has a Village."""
    monkeypatch.setattr(gather, "refresh_control", lambda s: None)
    monkeypatch.setattr(gather, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(gather, "is_adjacent", lambda a, b: True)
    state = _base_state()
    # Province_A has a Village — move should succeed
    gather.execute(
        state, C.INDIANS, {},
        ["Province_A"],
        move_plan=[("Province_B", "Province_A", 1)],
    )
    # All WP in Province_A should be Underground after move-and-flip
    sp = state["spaces"]["Province_A"]
    total_wp = sp.get(C.WARPARTY_U, 0) + sp.get(C.WARPARTY_A, 0)
    assert sp.get(C.WARPARTY_A, 0) == 0  # all flipped Underground
    assert sp.get(C.WARPARTY_U, 0) == total_wp
