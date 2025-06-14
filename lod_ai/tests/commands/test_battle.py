import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import battle
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 1, C.REGULAR_PAT: 1},
        },
        "resources": {C.BRITISH: 3, C.PATRIOTS: 3, C.FRENCH: 0, C.INDIANS: 0},
        "available": {},
        "casualties": {},
        "rng": __import__('random').Random(1),
    }


def test_battle_cost_and_caps(monkeypatch):
    calls = []
    monkeypatch.setattr(battle, "refresh_control", lambda s: calls.append("refresh"))
    monkeypatch.setattr(battle, "enforce_global_caps", lambda s: calls.append("caps"))
    state = simple_state()
    battle.execute(state, C.BRITISH, {}, ["Boston"])
    assert state["resources"][C.BRITISH] == 2
    assert "refresh" in calls and "caps" in calls
