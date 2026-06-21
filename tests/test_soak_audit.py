"""Regression tests for the soak runner and the free-Gather decline audit."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lod_ai.tools import gather_decline_audit as gda
from lod_ai.tools import soak


def test_gather_declines_are_genuine():
    """Every free-Gather decline must be grounded in the space state;
    none may coincide with a legal Gather target the planner missed."""
    declines, bugs = gda.run(range(1, 11), list(gda.SCENARIOS))
    assert not bugs, f"planner missed legal Gather targets: {bugs}"
    # Each decline carries a concrete, state-derived reason string.
    for d in declines:
        assert d["reason"], d


def test_soak_schedule_covers_scenarios_and_seeds():
    plan = list(soak._plan(9, seed_base=100))
    # round-robin scenarios, seed advances every full cycle
    assert plan[0] == ("1775", 100)
    assert plan[1] == ("1776", 100)
    assert plan[2] == ("1778", 100)
    assert plan[3] == ("1775", 101)
    assert len(plan) == 9


def test_soak_runs_and_is_resumable(tmp_path):
    out = tmp_path / "soak.jsonl"
    rc = soak.main(["--games", "6", "--seed-base", "9000",
                    "--out", str(out)])
    assert rc == 0
    lines = [l for l in out.read_text().splitlines() if l.strip()]
    assert len(lines) == 6
    # Re-invoking does not duplicate completed games.
    soak.main(["--games", "6", "--seed-base", "9000", "--out", str(out)])
    lines2 = [l for l in out.read_text().splitlines() if l.strip()]
    assert len(lines2) == 6
