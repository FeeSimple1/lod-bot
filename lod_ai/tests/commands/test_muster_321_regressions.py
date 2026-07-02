"""§3.2.1 Muster regressions surfaced by the §8.1 T1 fix (TRACEABILITY.md).

1. Tories may be placed only in Cities or Colonies — a plan naming a
   Reserve is skipped by the executor.
2. A Tory-only Muster passes ``regular_plan=None`` (the executor's
   documented contract); the fabricated zero-count Regular plan the
   British bot used to send pointed the §3.2.1 Regular-destination check
   at arbitrary spaces (e.g. a Blockaded City) and raised.
3. Step 3 (Fort / Reward Loyalty) has no implicit target without a
   Regular destination — previously an UnboundLocalError; and the RL
   space passes through ``fort_space`` so RL lands where the flowchart
   chose it, not at the Regular destination.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lod_ai.commands import muster
from lod_ai import rules_consts as C


def _state():
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 2, C.TORY: 1, "support": C.NEUTRAL},
            "Massachusetts": {"support": C.NEUTRAL},
            "Northwest": {C.REGULAR_BRI: 1, "support": C.NEUTRAL},
        },
        "support": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_BRI: 4, C.TORY: 4},
        "control": {"Boston": C.BRITISH},
        "markers": {},
        "rng": random.Random(3),
    }


def test_tory_plan_in_reserve_is_skipped():
    state = _state()
    muster.execute(
        state, C.BRITISH, {}, ["Boston", "Northwest"],
        regular_plan={"space": "Boston", "n": 1},
        tory_plan={"Northwest": 2},
    )
    assert state["spaces"]["Northwest"].get(C.TORY, 0) == 0


def test_tory_only_muster_regular_plan_none():
    state = _state()
    muster.execute(
        state, C.BRITISH, {}, ["Massachusetts"],
        regular_plan=None,
        tory_plan={"Massachusetts": 2},
    )
    assert state["spaces"]["Massachusetts"].get(C.TORY, 0) == 2


def test_step3_without_regular_destination_no_crash_and_rl_at_chosen_space():
    state = _state()
    # RL space passed through fort_space; no Regular plan at all.
    muster.execute(
        state, C.BRITISH, {}, ["Boston"],
        regular_plan=None,
        reward_levels=1,
        fort_space="Boston",
    )
    assert state.get("support", {}).get("Boston", 0) == 1  # shifted toward Support


def test_step3_skipped_when_no_target_at_all():
    state = _state()
    # reward_levels set but neither fort_space nor Regular destination:
    # previously UnboundLocalError, now a clean skip.
    muster.execute(
        state, C.BRITISH, {}, ["Massachusetts"],
        regular_plan=None,
        reward_levels=1,
        tory_plan={"Massachusetts": 1},
    )
    assert state["spaces"]["Massachusetts"].get(C.TORY, 0) == 1
