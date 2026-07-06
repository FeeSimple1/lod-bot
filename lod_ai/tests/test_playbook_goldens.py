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

    def __init__(self, base, script, script_d3=None):
        self._base = base
        self._script = list(script)
        self._script_d3 = list(script_d3 or [])

    def randint(self, a, b):
        if (a, b) == (1, 6) and self._script:
            return self._script.pop(0)
        if (a, b) == (1, 3) and self._script_d3:
            return self._script_d3.pop(0)
        return self._base.randint(a, b)

    def __deepcopy__(self, memo):
        # The engine simulates each bot turn on a deepcopy of the state
        # (engine._simulate_action) and commits the sandbox wholesale —
        # the wrapper must survive the copy WITH its remaining script.
        import copy as _c
        return _ScriptedRng(_c.deepcopy(self._base, memo),
                            list(self._script), list(self._script_d3))

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


def test_playbook_example_3_british_muster_skirmish():
    """Playbook Example 3 (p.22-24): 1776 Medium Scenario with the
    Militia and Rebellion Control removed from Philadelphia.  Card #29
    (Edward Bancroft, British Spy), British 1st Eligible, musket icon.

    Golden (structural asserts only where the walk-through resolves
    ties via the printed Random Spaces table — our §8.2 seeded ties are
    mechanically different, so exact tie-picks like "Connecticut" are
    not asserted):
    - Event IGNORED (instruction: fewer than 4 Militia would Activate).
    - No Garrison (only Rebellion-controlled City has a Patriot Fort).
    - B6 needs NO die (7 Available Regulars) — S59 parity fix.
    - Muster in 4 spaces: 6 Regulars into one Neutral/Passive
      control-adding City/Colony; Tories placed; D3=3 so Support+3
      beats Opposition 5 -> NO Reward Loyalty; a Fort replaces cubes in
      a 5+-cube Colony among the selected spaces, removing 2 Regulars
      + 1 Tory (§8.1.2: alternate starting with the MOST — 6R/2T).
    - Resources 5 -> 1 (4 Muster spaces).
    - Skirmish (SA) in New York (not a Muster space): option 2 removes
      2 Continentals + 1 British Regular.  CBC 1->2, CRC 3->5.
    """
    state = build_state("1776", seed=3)
    # Alteration noted in the example
    phl = state["spaces"]["Philadelphia"]
    phl[C.MILITIA_U] = 0
    phl[C.MILITIA_A] = 0
    from lod_ai.board.control import refresh_control
    refresh_control(state)
    assert state["control"].get("Philadelphia") != "REBELLION"
    # Printed-setup preconditions the walk-through relies on
    assert state["resources"][C.BRITISH] == 5
    assert state["available"][C.REGULAR_BRI] == 7
    assert state.get("cbc") == 1 and state.get("crc") == 3
    assert state["spaces"]["New_York"].get(C.REGULAR_PAT) == 3

    # Book dice under Q22 table parity (S62): reg-destination walk
    # D3=3/D6=4 -> Connecticut; Tory-P2 walk D3=3/D6=5 -> Boston; the
    # RL/fort D3=3 (Support 3+3 beats Opposition 5 -> Fort).  Padding
    # values cover the remaining table consumers.
    state["rng"] = _ScriptedRng(state["rng"], [4, 5, 5, 5],
                                script_d3=[3, 3, 3, 3])
    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([])
    eng.state["ineligible_next"] = {C.INDIANS, C.PATRIOTS, C.FRENCH}
    eng.play_card(_card(29), human_decider=None)

    st = eng.state
    hist = [h["msg"] if isinstance(h, dict) else str(h)
            for h in st.get("history", [])]
    joined = " | ".join(hist)

    # Event ignored -> Muster command executed
    assert "BRITISH MUSTER" in joined
    # B6 must not have consumed a die (7 Available -> no roll)
    assert not any(lbl == "B6 1D6" for lbl, *_ in st.get("rng_log", [])), (
        "Playbook: 'no need to roll the die' with 7 Available Regulars"
    )
    # EXACT PICKS under Q22 table parity (S62): the book's table rolls
    # reproduce the printed Muster precisely.
    ct = st["spaces"]["Connecticut_Rhode_Island"]
    assert ct.get(C.REGULAR_BRI, 0) == 4 and ct.get(C.TORY, 0) == 1, (
        "Connecticut: 6 Regulars + 2 Tories placed, then the Fort "
        "replaces 2 Regulars + 1 Tory (§8.1.2 R,T,R from 6R/2T)"
    )
    assert ct.get(C.FORT_BRI, 0) == 1
    assert st["spaces"]["New_York_City"].get(C.TORY, 0) == 2
    assert st["spaces"]["Pennsylvania"].get(C.TORY, 0) == 2
    assert st["spaces"]["Boston"].get(C.TORY, 0) == 1, (
        "Boston is at Passive Opposition — a single Tory (§8.4.2)"
    )
    # No Reward Loyalty (D3=3: Support 3+3 beats Opposition 5)
    assert "Reward Loyalty" not in joined and "reward" not in joined.lower()
    # Resources: 5 - 4 Muster spaces = 1
    assert st["resources"][C.BRITISH] == 1, (
        f"expected 1 Resource after a 4-space Muster, got {st['resources'][C.BRITISH]}"
    )
    # Skirmish in New York Colony: 2 Continentals + 1 Regular to Casualties
    assert st["spaces"]["New_York"].get(C.REGULAR_PAT, 0) == 1
    assert st.get("cbc") == 2 and st.get("crc") == 5


def test_playbook_example_2_british_garrison_naval_pressure():
    """Playbook Example 2 (p.20-22): 1776 Medium Scenario, card #42
    (British Attack Danbury), British 1st Eligible.

    Forced core asserted (destination/tie picks that the book resolves
    via the Random Spaces table or ad-hoc D6s are structural only):
    - Event IGNORED (no B2 bullet fires) -> Garrison selected (12
      Regulars on map; Philadelphia is Rebellion-controlled, no Fort).
    - SA FIRST: Naval Pressure at FNI 0 -> +1D3 (scripted 1) BEFORE the
      Command; Garrison then costs 2 -> Resources 5+1-2 = 4.
    - Retention: Quebec City's lone Regular never moves (leaving 1
      Royalist vs 0 Rebellion breaks the "2 more" rule and the City is
      neither Pop 0 nor Active Support); New York City keeps >= 2
      Regulars; New York Colony keeps >= 1 Regular.
    - Phase 2a: Philadelphia (most Rebellion pieces without a Patriot
      Fort) receives exactly 2 Regulars ("just enough") and flips to
      BRITISH Control.
    - Displacement: exactly one displaceable Rebellion piece (the
      Philadelphia Militia or the NYC Continental — the book's D6 picks
      Philadelphia) is expelled to an adjacent Province; if it is the
      Philadelphia Militia, it lands in New Jersey (lowest-Pop Neutral
      adjacent) which flips to REBELLION Control.
    """
    state = build_state("1776", seed=5)
    assert state["resources"][C.BRITISH] == 5
    ny_city = state["spaces"]["New_York_City"]
    assert ny_city.get(C.REGULAR_BRI) == 6 and ny_city.get(C.FORT_BRI) == 1
    assert state["spaces"]["Philadelphia"].get(C.MILITIA_U) == 1
    assert state["spaces"]["Quebec_City"].get(C.REGULAR_BRI) == 1
    assert state.get("fni_level", 0) == 0

    state["rng"] = _ScriptedRng(state["rng"], [], script_d3=[1])
    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([])
    eng.state["ineligible_next"] = {C.INDIANS, C.PATRIOTS, C.FRENCH}
    eng.play_card(_card(42), human_decider=None)

    st = eng.state
    hist = [h["msg"] if isinstance(h, dict) else str(h)
            for h in st.get("history", [])]
    joined = " | ".join(hist)

    assert "BRITISH GARRISON" in joined, "Garrison must be selected"
    assert "NAVAL_PRESSURE" in joined, "SA (Naval Pressure) runs first"
    # Naval order: the SA line must precede the Garrison line
    assert joined.index("NAVAL_PRESSURE") < joined.index("BRITISH GARRISON")

    # Resources: 5 + 1 (D3) - 2 (Garrison) = 4
    assert st["resources"][C.BRITISH] == 4, st["resources"][C.BRITISH]

    phl = st["spaces"]["Philadelphia"]
    # Phase 2a needs exactly 2 ("just enough"); the book's random
    # destination draws then spend all movables on new Cities, while a
    # different draw can leave movables for phase 2b to top Philadelphia
    # to three cubes ("at least three British cubes ... beginning with
    # those Cities that have Underground Militia") — both are the
    # letter.  Assert the floor and the flip, not the draw.
    assert phl.get(C.REGULAR_BRI, 0) >= 2
    from lod_ai.board.control import refresh_control
    refresh_control(st)
    assert st["control"].get("Philadelphia") == C.BRITISH

    # Retention
    assert st["spaces"]["Quebec_City"].get(C.REGULAR_BRI, 0) >= 1, (
        "Quebec City's Regular may not LEAVE (the '2 more' rule); "
        "phase 2b may legally add to the city on other draws"
    )
    assert st["spaces"]["New_York_City"].get(C.REGULAR_BRI, 0) >= 2
    assert st["spaces"]["New_York"].get(C.REGULAR_BRI, 0) >= 1

    # Displacement: the Philadelphia Militia is gone from Philadelphia
    # (expelled or, if the tie picked NYC, still Underground there).
    displaced_phl = phl.get(C.MILITIA_U, 0) + phl.get(C.MILITIA_A, 0) == 0
    displaced_nyc = st["spaces"]["New_York_City"].get(C.REGULAR_PAT, 0) == 0
    assert displaced_phl or displaced_nyc, (
        "one displaceable Rebellion piece must be expelled (§8.4.1)"
    )
    if displaced_phl:
        nj = st["spaces"]["New_Jersey"]
        assert nj.get(C.MILITIA_U, 0) + nj.get(C.MILITIA_A, 0) == 1, (
            "the expelled Militia lands in New Jersey (lowest-Pop "
            "Neutral adjacent Province)"
        )


def test_playbook_example_4_british_brilliant_stroke():
    """Playbook Example 4 (p.24-25): British Brilliant Stroke, card #6,
    1776 Medium Scenario + the printed modifications, ToA in effect.

    Forced core asserted (the LimCom2 destination and the RL-vs-Fort
    D3 branch are die-dependent):
    - The British BS fires (ToA + Howe with 4+ Regulars + player 1st
      Eligible) and CANCELS the card (all factions end Eligible).
    - LimCom1 (leader-tied): D6=4 kills the Muster gate (3 Available);
      Battle needs 2+ enemy pieces (NYC has 1) -> March: Howe leads 5
      of 6 Regulars NYC -> New Jersey (Blockade allows adjacent only),
      1 stays (Control + not Active Support), New Jersey flips BRITISH,
      Howe follows.
    - SA: Skirmish first in the West Indies — 2 French + 1 British
      Regular to Casualties (CBC 1->2, CRC 3->5), WI turns BRITISH.
    - Howe's ability: FNI 1->0 AND the New York City Blockade returns
      to the West Indies on its Squadron side (§1.9 — the marker MUST
      move with the level).
    - LimCom2 (flowchart, no leader tie): D6=2 < 3 -> Muster in ONE
      space by the bot's priorities: 3 Regulars + 2 Tories placed, and
      the Muster itself is FREE (§8.3.7) — any Resources spent come
      only from Reward Loyalty (§3.2.1 exception).
    """
    state = build_state("1776", seed=9)
    state["spaces"]["Philadelphia"][C.MILITIA_U] = 0
    state["unavailable"][C.BLOCKADE] = 0
    bloc = state["markers"][C.BLOCKADE]
    bloc["pool"] += 1
    state["available"][C.REGULAR_FRE] -= 6
    state["unavailable"][C.REGULAR_FRE] += 6
    state["toa_played"] = True
    state["treaty_of_alliance"] = True
    state["fni_level"] = 1
    bloc["pool"] -= 1
    bloc["on_map"] = {"New_York_City"}
    ct = state["spaces"]["Charles_Town"]
    ct[C.REGULAR_FRE] = ct.get(C.REGULAR_FRE, 0) + 4
    state["unavailable"][C.REGULAR_FRE] -= 4
    state["leaders"]["LEADER_ROCHAMBEAU"] = "Charles_Town"
    if "leader_locs" in state:
        state["leader_locs"]["LEADER_ROCHAMBEAU"] = "Charles_Town"
    wi = state["spaces"]["West_Indies"]
    wi[C.REGULAR_FRE] = wi.get(C.REGULAR_FRE, 0) + 3
    wi[C.REGULAR_BRI] = wi.get(C.REGULAR_BRI, 0) + 3
    state["unavailable"][C.REGULAR_FRE] -= 3
    state["unavailable"][C.REGULAR_BRI] -= 3
    conn = state["spaces"]["Connecticut_Rhode_Island"]
    conn[C.REGULAR_BRI] = 4
    conn[C.TORY] = 1
    conn[C.FORT_BRI] = 1
    state["available"][C.REGULAR_BRI] -= 4
    state["available"][C.TORY] -= 1
    state["available"][C.FORT_BRI] -= 1
    from lod_ai.board.control import refresh_control
    refresh_control(state)
    # Printed-setup preconditions
    assert state["available"][C.REGULAR_BRI] == 3
    assert state["available"][C.TORY] == 9
    assert state.get("cbc") == 1 and state.get("crc") == 3

    state["rng"] = _ScriptedRng(state["rng"], [4, 2, 3], script_d3=[2, 1])
    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([C.PATRIOTS, C.FRENCH])
    eng.play_card(_card(6), human_decider=None)

    st = eng.state
    from lod_ai.leaders import leader_location
    assert st.get("bs_played", {}).get(C.BRITISH) is True
    assert all(st["eligible"].values()), "BS resolves with all Eligible"
    # LimCom1
    nj = st["spaces"]["New_Jersey"]
    assert nj.get(C.REGULAR_BRI, 0) == 5 and st["control"].get("New_Jersey") == C.BRITISH
    assert st["spaces"]["New_York_City"].get(C.REGULAR_BRI, 0) == 1
    assert leader_location(st, "LEADER_HOWE") == "New_Jersey"
    # SA
    assert st["spaces"]["West_Indies"].get(C.REGULAR_FRE, 0) == 1
    assert st["spaces"]["West_Indies"].get(C.REGULAR_BRI, 0) == 2
    assert st.get("cbc") == 2 and st.get("crc") == 5
    # Howe / §1.9
    assert st.get("fni_level") == 0
    assert "New_York_City" not in st["markers"][C.BLOCKADE]["on_map"]
    # LimCom2: a single-space Muster placed 3 Regulars + 2 Tories
    hist = " | ".join(h["msg"] if isinstance(h, dict) else str(h)
                      for h in st.get("history", []))
    assert "3×British_Regular  available →" in hist
    assert "2×British_Tory  available →" in hist
    # Free Muster: any spend is RL-only (0, 2 or 3 by the D3 branch)
    assert st["resources"][C.BRITISH] >= 2
