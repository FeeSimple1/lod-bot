"""Smoke gate for tools/policy_seat.py (S74).

The policy-seat harness must drive the real interactive loop with its
authored strategy without crashing, answer every prompt (no stdin
reads), and leave the CLI hooks torn down.  A short card-capped game
keeps this CI-cheap; full games are exercised from the command line.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import builtins

import lod_ai.rules_consts as C
from lod_ai.tools.policy_seat import play, Strategist


def test_policy_seat_plays_a_capped_game_cleanly():
    engine, provider, stats, out, err = play("1778", 3, C.FRENCH,
                                             max_cards=8)
    assert err in (None, "card-cap"), f"harness error: {err}"
    assert len(provider.log) > 0, "the seat must have answered prompts"
    assert len(engine.state.get("played_cards", [])) >= 1
    # hooks restored
    assert builtins.input is not provider.prompt
    # the strategist made classified decisions, not fuzz: every logged
    # answer is a menu index / count / meta string
    assert all("->" in line or line.startswith("LOOPBREAK")
               for line in provider.log)


def test_strategist_battle_gate_is_decisive_margin():
    """The policy only volunteers Battle on a decisive resolver margin
    (the S74 lesson: battle is tempo, not points)."""
    from lod_ai.tools.policy_seat import DECISIVE_MARGIN
    assert DECISIVE_MARGIN >= 2

    class _Probe(Strategist):
        def __init__(self):  # no engine needed
            self.faction = C.BRITISH
            self._wb = [(1, "Boston")]
            self._card_attempts = {}

        @property
        def state(self):
            return {"resources": {C.BRITISH: 9}, "played_cards": []}

        def _winnable_battles(self):
            return self._wb

        def _resources(self):
            return 9

    p = _Probe()
    options = ["Muster", "Garrison", "March", "Battle"]
    # margin 1: not decisive -> Muster leads
    assert options[int(p._command_menu(options)) - 1] == "Muster"
    p._card_attempts.clear()
    p._wb = [(DECISIVE_MARGIN, "Boston")]
    assert options[int(p._command_menu(options)) - 1] == "Battle"
