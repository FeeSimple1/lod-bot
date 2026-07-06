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


class _ScriptedRng:
    """random.Random wrapper: pops scripted randint(1,6) results first
    (the Playbook's narrated dice), then falls through to the seeded
    stream for everything else."""

    def __init__(self, base, script):
        self._base = base
        self._script = list(script)

    def randint(self, a, b):
        if (a, b) == (1, 6) and self._script:
            return self._script.pop(0)
        return self._base.randint(a, b)

    def __deepcopy__(self, memo):
        # The engine simulates each bot turn on a deepcopy of the state
        # (engine._simulate_action) and commits the sandbox wholesale —
        # the wrapper must survive the copy WITH its remaining script.
        import copy as _c
        return _ScriptedRng(_c.deepcopy(self._base, memo),
                            list(self._script))

    def __getattr__(self, name):
        # Never forward dunders: deepcopy/pickle would otherwise hijack
        # the base Random's __getstate__/__setstate__ and produce a
        # hollow wrapper whose attribute lookups recurse forever.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._base, name)


import pytest


def test_playbook_example_5_indian_scout_war_path():
    """Playbook Example 5 (p.26): 1776 Medium Scenario + one extra War
    Party in each Indian Reserve (3 left Available) + 2 Indian
    Resources.  Card #73, Indians 1st Eligible.  Dice: I3=4 (no Raid),
    Gather=5 (skip), Brant-follow=2 (follows).

    Golden: Scout from New York into Massachusetts (Patriot-Fort
    priority) with 1 WP + 2 Regulars + 1 Tory; the move Activates the
    WP and the MA Militia; Brant follows; the Scout's Skirmish (option
    2) removes the Continental (to Casualties), the Militia (to
    Available) and one British Regular (CBC 1->2, CRC 3->4); War Path
    then fires in QUEBEC (Village space), Activating one WP and
    removing the Patriot Militia there.  Indians end at 1 Resource,
    British at 4.
    """
    state = build_state("1776", seed=1)
    for r in ("Quebec", "Northwest", "Southwest", "Florida"):
        state["spaces"][r][C.WARPARTY_U] = state["spaces"][r].get(C.WARPARTY_U, 0) + 1
    state["available"][C.WARPARTY_U] -= 4
    assert state["available"][C.WARPARTY_U] == 3, "Playbook: three WP left Available"
    state["resources"][C.INDIANS] = state["resources"].get(C.INDIANS, 0) + 2
    # Preconditions per the printed setup that the example relies on
    assert state["resources"][C.INDIANS] == 2
    assert state["resources"][C.BRITISH] == 5
    assert state.get("cbc") == 1 and state.get("crc") == 3
    ny = state["spaces"]["New_York"]
    assert ny.get(C.REGULAR_BRI) == 3 and ny.get(C.TORY) == 3 and ny.get(C.WARPARTY_U) == 2

    state["rng"] = _ScriptedRng(state["rng"], [4, 5, 2])
    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([])
    # Isolate the Indian action (the example narrates only their turn)
    eng.state["ineligible_next"] = {C.BRITISH, C.PATRIOTS, C.FRENCH}
    eng.play_card(_card(73), human_decider=None)

    st = eng.state
    ma = st["spaces"]["Massachusetts"]
    ny = st["spaces"]["New_York"]
    qc = st["spaces"]["Quebec"]
    from lod_ai.leaders import leader_location

    # D1 — Scout group composition (1 WP + 2R + 1T into MA)
    assert ma.get(C.WARPARTY_A, 0) >= 1, "the scouting War Party arrives Active in MA"
    assert ny.get(C.WARPARTY_U, 0) + ny.get(C.WARPARTY_A, 0) == 1, "one WP stays in NY"
    assert ma.get(C.REGULAR_BRI, 0) == 1, "2 Regulars arrived, 1 died in the Skirmish"
    assert ma.get(C.TORY, 0) == 1, "one Tory scouts along (§8.1.2 alternation)"
    assert ny.get(C.REGULAR_BRI, 0) == 1 and ny.get(C.TORY, 0) == 2

    # Skirmish outcome (matched already pre-fix)
    assert ma.get(C.REGULAR_PAT, 0) == 0 and ma.get(C.MILITIA_A, 0) == 0
    assert ma.get(C.FORT_PAT, 0) == 1, "the Fort survives, unprotected"
    assert st.get("cbc") == 2 and st.get("crc") == 4

    # D2 — Brant follows the scouts on the 1-3 die (rolled 2)
    assert leader_location(st, "LEADER_BRANT") == "Massachusetts"

    # D3 — War Path in Quebec (Village tiebreak), removing the Militia
    assert qc.get(C.MILITIA_U, 0) + qc.get(C.MILITIA_A, 0) == 0, (
        "War Path removes the Quebec Patriot Militia (Village-space "
        "tiebreak; Militia before Continentals per §8.1.2)"
    )
    assert st["resources"][C.INDIANS] == 1 and st["resources"][C.BRITISH] == 4
