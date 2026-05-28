"""Regression test: Manual §4.1 — one Special Activity per Command turn.

The Patriot bot calls Persuasion from multiple flowchart nodes (P7 Rally,
P8 Partisans, P11 Rabble-Rousing, P12 Skirmish), and within
_execute_rabble / _execute_rally it tries Persuasion as a mid-command
resource refill whenever Patriot Resources hit 0.  Before the fix
nothing prevented Persuasion from firing more than once per turn:
instrumenting a 50-game 1776 batch showed 30% of Persuasion-using turns
(52/172) involved >1 Persuasion call, with one turn firing it 4 times.

Persuasion grants +1 Resource per space (§4.3.1), so multi-fire turns
let Patriots refill resources beyond what one SA would allow,
extending Rabble-Rousing past the legal envelope.

Fix: gate _try_persuasion with a turn-scoped flag
state['_turn_persuasion_used'], cleared at the start of every turn via
a PatriotBot.take_turn override.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from unittest.mock import patch

from lod_ai.bots.patriot import PatriotBot
from lod_ai import rules_consts as C
from lod_ai.special_activities import persuasion as persuasion_mod


def _state_with_4_persuasion_targets():
    """State with 4 Rebellion-controlled Colonies/Cities each with
    Underground Militia — Persuasion-eligible per §4.3.1."""
    sids = ("Massachusetts", "Philadelphia", "North_Carolina", "Georgia")
    return {
        "spaces": {
            sid: {
                C.REGULAR_BRI: 0, C.TORY: 0, C.MILITIA_A: 0,
                C.MILITIA_U: 1, C.REGULAR_PAT: 0, C.REGULAR_FRE: 0,
                C.FORT_BRI: 0, C.FORT_PAT: 0, C.VILLAGE: 0,
                "adj": [],
            }
            for sid in sids
        },
        "resources": {C.PATRIOTS: 0, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {C.FORT_PAT: 0},
        "rng": random.Random(0),
        "history": [],
        "support": {sid: C.NEUTRAL for sid in sids},
        "control": {sid: "REBELLION" for sid in sids},
        "markers": {C.PROPAGANDA: {"pool": 12, "on_map": set()},
                    C.RAID: {"pool": 0, "on_map": set()}},
        "casualties": {},
    }


def test_persuasion_can_only_fire_once_per_turn():
    """Two consecutive _try_persuasion calls in the same turn: the
    second must return False without invoking persuasion.execute."""
    bot = PatriotBot()
    state = _state_with_4_persuasion_targets()

    call_count = {"n": 0}
    real_execute = persuasion_mod.execute

    def counting_execute(*a, **kw):
        call_count["n"] += 1
        return real_execute(*a, **kw)

    with patch.object(persuasion_mod, "execute", side_effect=counting_execute):
        first = bot._try_persuasion(state)
        # Patriot bot also imports persuasion at module level; patch the
        # bot's reference too, since _try_persuasion uses the bound name.
        import lod_ai.bots.patriot as patbot
        with patch.object(patbot, "persuasion", persuasion_mod):
            second = bot._try_persuasion(state)

    assert first is True, "first Persuasion call should succeed"
    assert second is False, (
        "second Persuasion call must return False (§4.1 one SA per turn)"
    )
    assert call_count["n"] == 1, (
        f"persuasion.execute should be called at most once per turn; "
        f"got {call_count['n']} calls"
    )
    assert state.get("_turn_persuasion_used") is True, (
        "_turn_persuasion_used flag should be set after first Persuasion"
    )


def test_take_turn_clears_persuasion_flag():
    """After take_turn() the per-turn flag must be reset so subsequent
    turns are not blocked from using Persuasion."""
    bot = PatriotBot()
    state = _state_with_4_persuasion_targets()

    # Simulate that the previous turn used Persuasion
    state["_turn_persuasion_used"] = True

    # take_turn should clear the flag.  Use a tiny stub card and skip
    # the full flowchart by mocking _follow_flowchart.
    card = {"id": 1, "type": "EVENT", "order": [C.PATRIOTS], "order_icons": "P",
            "title": "stub", "faction_icons": {}, "winter_quarters": False,
            "unshaded_event": "", "shaded_event": "", "musket": False, "sword": False}

    with patch.object(PatriotBot, "_follow_flowchart", lambda self, st: None):
        bot.take_turn(state, card)

    assert "_turn_persuasion_used" not in state, (
        "take_turn() must clear _turn_persuasion_used at turn start"
    )
