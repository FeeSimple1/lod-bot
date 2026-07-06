"""Piece 5 — Playbook goldens (Session 57).

The Playbook's "Non-Player Examples of Play" (Playbook Aug2016.txt
lines ~1014-1470) are worked, designer-authored walk-throughs of the
non-player system: ground truth the engine can be replayed against.
Setup convention (Playbook): "set up the board according to the Medium
Scenario: 1776-1779 ... plus any alterations noted below", one-player
game, player as Patriots+French.

Transcribed so far:
  Example 1 (lines 1029-1071): Non-Player British Event, card #28.
TODO (next session; line ranges in the Playbook):
  Example 2 (1073-1197): British Garrison movements + expulsion.
  Example 3 (1198-1324): British Muster + Skirmish.
  Example 4 (1325-1426): British Brilliant Stroke (the §8.3.7 example).
  Example 5 (1427-1467): Indian Scout + War Path (Scouts bring two
    British Regulars and one Tory).
"""
import json

import lod_ai.rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state


def _card(cid: int) -> dict:
    data = json.load(open("lod_ai/cards/data.json"))
    cards = data if isinstance(data, list) else data.get("cards", data)
    return next(c for c in cards if c.get("id") == cid)


def test_playbook_example_1_british_event_card_28():
    """Playbook Example 1: card #28 (Battle of Moore's Creek Bridge),
    British 1st Eligible in the 1776 Medium Scenario.

    Golden outcome (Playbook p.19-20): the British PLAY the unshaded
    Event — the third "Event or Command?" bullet fires ("Event places
    Tories in an Active Opposition space with none already": only
    Massachusetts qualifies) — and "the player duly replaces the single
    Militia in MA with two Tories, removes the Rebellion Control
    marker".
    """
    state = build_state("1776", seed=1)
    ma = state["spaces"]["Massachusetts"]
    # Preconditions per the printed 1776 setup (the example relies on them)
    assert state["support"].get("Massachusetts") == C.ACTIVE_OPPOSITION
    assert ma.get(C.MILITIA_U, 0) == 1 and ma.get(C.TORY, 0) == 0

    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([])
    # Isolate the British action (the example narrates only their turn;
    # the Patriots' 2nd-eligible response is out of scope).
    eng.state["eligible"] = {C.BRITISH: True, C.PATRIOTS: False,
                             C.FRENCH: False, C.INDIANS: False}
    eng.play_card(_card(28), human_decider=None)

    ma = eng.state["spaces"]["Massachusetts"]
    assert ma.get(C.TORY, 0) == 2, (
        "golden: the single MA Militia is replaced with two Tories"
    )
    assert ma.get(C.MILITIA_U, 0) == 0 and ma.get(C.MILITIA_A, 0) == 0
    from lod_ai.board.control import refresh_control
    refresh_control(eng.state)
    assert eng.state["control"].get("Massachusetts") != "REBELLION", (
        "golden: the Rebellion Control marker is removed"
    )
    hist = " | ".join(h["msg"] if isinstance(h, dict) else str(h)
                      for h in eng.state.get("history", []))
    assert "PASS" not in hist.split("BRITISH")[-1][:40], (
        "the British must act on the Event, not pass"
    )
