import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import scout
from lod_ai import rules_consts as C


def _state(src_wp_u=2, src_wp_a=1, src_reg=2, src_tory=1, dst_mil_u=2):
    """Build a minimal state for Scout tests."""
    return {
        "spaces": {
            "Province_A": {
                C.WARPARTY_U: src_wp_u, C.WARPARTY_A: src_wp_a,
                C.REGULAR_BRI: src_reg, C.TORY: src_tory,
            },
            "Province_B": {C.MILITIA_U: dst_mil_u},
        },
        "resources": {
            C.BRITISH: 5, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 5,
        },
        "available": {},
        "rng": __import__('random').Random(1),
    }


def test_scout_wp_activation_no_double_count(monkeypatch):
    """§3.4.3: All moving War Parties arrive Active.  Previously the code
    double-counted Active WP, inflating the count."""
    monkeypatch.setattr(scout, "refresh_control", lambda s: None)
    monkeypatch.setattr(scout, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(scout, "is_adjacent", lambda a, b: True)
    monkeypatch.setattr(scout, "_is_city", lambda s: False)
    state = _state(src_wp_u=2, src_wp_a=1, src_reg=2, src_tory=0)
    scout.execute(
        state, C.INDIANS, {}, "Province_A", "Province_B",
        n_warparties=3, n_regulars=2,
    )
    dst = state["spaces"]["Province_B"]
    # All 3 WP should be Active, 0 Underground
    assert dst.get(C.WARPARTY_A, 0) == 3
    assert dst.get(C.WARPARTY_U, 0) == 0
    # Source should have 0 WP
    src = state["spaces"]["Province_A"]
    assert src.get(C.WARPARTY_A, 0) == 0
    assert src.get(C.WARPARTY_U, 0) == 0


def test_scout_militia_activation(monkeypatch):
    """§3.4.3: Activate all Militia in the destination space."""
    monkeypatch.setattr(scout, "refresh_control", lambda s: None)
    monkeypatch.setattr(scout, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(scout, "is_adjacent", lambda a, b: True)
    monkeypatch.setattr(scout, "_is_city", lambda s: False)
    state = _state(src_wp_u=1, src_wp_a=0, src_reg=1, src_tory=0, dst_mil_u=3)
    scout.execute(
        state, C.INDIANS, {}, "Province_A", "Province_B",
        n_warparties=1, n_regulars=1,
    )
    dst = state["spaces"]["Province_B"]
    assert dst.get(C.MILITIA_U, 0) == 0
    assert dst.get(C.MILITIA_A, 0) == 3


def test_scout_resource_cost(monkeypatch):
    """§3.4.3: Indians pay 1, British pay 1."""
    monkeypatch.setattr(scout, "refresh_control", lambda s: None)
    monkeypatch.setattr(scout, "enforce_global_caps", lambda s: None)
    monkeypatch.setattr(scout, "is_adjacent", lambda a, b: True)
    monkeypatch.setattr(scout, "_is_city", lambda s: False)
    state = _state(src_wp_u=1, src_wp_a=0, src_reg=1, src_tory=0)
    scout.execute(
        state, C.INDIANS, {}, "Province_A", "Province_B",
        n_warparties=1, n_regulars=1,
    )
    assert state["resources"][C.INDIANS] == 4
    assert state["resources"][C.BRITISH] == 4
