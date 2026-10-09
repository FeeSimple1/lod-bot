"""Bot decisions and the displayed victory totals share §1.9 scoring."""

import random

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.bots.british_bot import BritishBot
from lod_ai.victory import _summarize_board


def test_bot_tally_matches_victory_with_blockaded_support_and_opposition():
    state = {
        "spaces": {sid: {} for sid in ("Boston", "New_York_City", "Virginia")},
        "support": {"Boston": C.ACTIVE_SUPPORT,
                    "New_York_City": C.ACTIVE_OPPOSITION,
                    "Virginia": C.PASSIVE_SUPPORT},
        "markers": {C.BLOCKADE: {"pool": 0,
                                 "on_map": {"Boston", "New_York_City"}}},
    }

    totals = _summarize_board(state)

    assert BaseBot._support_opposition_totals(state) == (2, 4)
    assert BaseBot._support_opposition_totals(state) == (
        totals["support"], totals["opposition"])


def test_blockaded_opposition_still_triggers_british_support_event():
    """B2's Opposition > Support gate must count a Blockaded Opposition City."""
    state = {
        "spaces": {"Boston": {}, "Georgia": {}},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "Georgia": C.PASSIVE_SUPPORT},
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": {"Boston"}}},
        "resources": {f: 5 for f in (C.BRITISH, C.FRENCH, C.PATRIOTS, C.INDIANS)},
        "available": {},
        "control": {},
        "casualties": {},
        "rng": random.Random(42),
        "history": [],
    }

    # Card 10 unshaded shifts Cities toward Active Support. British have
    # no Cities under Control, so B2's five-Cities alternative cannot apply.
    assert BritishBot()._faction_event_conditions(state, {"id": 10})
