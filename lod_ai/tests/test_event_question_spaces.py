"""§8.3.5 flowchart-question-spaces-first (Piece 3 residual, Session 73).

Manual §8.3.5: "If a Non-player Faction executes an Event due to one of
the 'Event or Command?' questions on the flowchart, select as many
spaces as possible that match that question before selecting other
spaces (if any)."

Mechanism under test: a space-conditioned B2/P2 bullet records its FULL
matching set in state["_event_q_spaces"]; the §8.2 pickers
(pick_by_priority / pick_random_spaces) rank/exhaust those spaces
first; base_bot._execute_event clears the key right after the handler
so free-op planning and later turns never see it.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random

import lod_ai.rules_consts as C
from lod_ai.bots.random_spaces import pick_by_priority, pick_random_spaces
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot


def _state(**over):
    st = {
        "spaces": {}, "support": {}, "control": {},
        "available": {C.TORY: 10, C.MILITIA_U: 10, C.FORT_BRI: 3,
                      C.REGULAR_BRI: 10},
        "unavailable": {}, "casualties": {}, "markers": {}, "leaders": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.FRENCH: 10,
                      C.INDIANS: 10},
        "rng": random.Random(7), "history": [], "fni_level": 0,
    }
    st.update(over)
    return st


def test_pick_by_priority_prefers_question_spaces():
    st = _state()
    st["_event_q_spaces"] = {"Georgia"}
    # Boston has the strictly better substantive key; Georgia matches
    # the flowchart question and must still win (§8.3.5 bullet order).
    scored = [((0,), "Boston"), ((5,), "Georgia")]
    assert pick_by_priority(st, scored, count=1) == ["Georgia"]
    # Without the key, the substantive key decides.
    st.pop("_event_q_spaces")
    assert pick_by_priority(st, scored, count=1) == ["Boston"]


def test_pick_random_spaces_exhausts_question_spaces_first():
    st = _state()
    st["_event_q_spaces"] = {"Georgia", "Savannah"}
    picked = pick_random_spaces(
        st, ["Boston", "Georgia", "Savannah", "Norfolk"], count=3)
    assert set(picked[:2]) == {"Georgia", "Savannah"}, (
        "question spaces must be exhausted before any other candidate")


def _card16():
    return {"id": 16, "title": "Mercy Warren", "dual": True,
            "unshaded_event": "Place two Tories anywhere.",
            "shaded_event": "Shift one City to Passive Opposition."}


def test_british_bullet3_places_tories_in_question_space():
    """B2 bullet 3 fires on 'Tories into Active Opposition with none' —
    the handler must then place there, even though its own §8.3.8
    default prefers a Control-gain space elsewhere."""
    bot = BritishBot()
    st = _state(
        spaces={
            # Massachusetts: Active Opposition, no Tories (the question
            # match) — but rebels dominate, so no Control gain here.
            "Massachusetts": {C.MILITIA_U: 4},
            # Georgia: the handler's default pick (2 Tories would gain
            # British Control), NOT a question match (no Opposition).
            "Georgia": {C.MILITIA_U: 1},
        },
        support={"Massachusetts": C.ACTIVE_OPPOSITION, "Georgia": 0},
    )
    fired = bot._faction_event_conditions(st, _card16())
    assert fired, "bullet 3a must fire on the Massachusetts match"
    assert st.get("_event_q_spaces") == {"Massachusetts"}

    bot._execute_event(_card16(), st, force_unshaded=True)
    assert st["spaces"]["Massachusetts"].get(C.TORY, 0) == 2, (
        "§8.3.5: the question space gets the placement, not the "
        "handler's Control-gain default")
    assert "_event_q_spaces" not in st, (
        "the question set must be cleared right after the handler")


def _card19():
    return {"id": 19, "title": "Nathan Hale", "dual": True,
            "unshaded_event": "Patriot Resources -4.",
            "shaded_event": "Place three Patriot Militia anywhere."}


def test_patriot_bullet2_places_militia_in_question_spaces():
    """P2 bullet 2: 'Underground Militia into an Active Support or
    Village space with none' — card 19's three Militia must go to the
    matching spaces first."""
    bot = PatriotBot()
    st = _state(
        spaces={
            # The question matches: Active Support, no Militia.
            "Boston": {},
            # Village space with no Militia: also a match.
            "Northwest": {C.VILLAGE: 1},
            # The handler's own §8.5.2 default would love a
            # Control-flip space like this one, but it has Militia
            # already (not a match).
            "Georgia": {C.MILITIA_U: 1, C.TORY: 1},
            "Virginia": {C.TORY: 2},
        },
        support={"Boston": C.ACTIVE_SUPPORT, "Georgia": 0, "Virginia": 0,
                 "Northwest": 0},
    )
    fired = bot._faction_event_conditions(st, _card19())
    assert fired, "P2 bullet 2 must fire"
    assert st.get("_event_q_spaces") == {"Boston", "Northwest"}

    bot._execute_event(_card19(), st)   # PATRIOTS -> shaded side
    assert st["spaces"]["Boston"].get(C.MILITIA_U, 0) >= 1
    assert st["spaces"]["Northwest"].get(C.MILITIA_U, 0) >= 1, (
        "both question spaces must be served before any other space")
    assert "_event_q_spaces" not in st


def test_stale_question_set_cleared_before_bullet_list():
    """A leftover set from a previous decision must not leak into the
    next event evaluation: _choose_event_vs_flowchart clears the key
    before running the bullet list."""
    bot = BritishBot()
    st = _state(
        spaces={"Georgia": {C.MILITIA_U: 1}},
        support={"Georgia": 0},
    )
    st["_event_q_spaces"] = {"Georgia"}   # stale garbage
    # Card 16 unshaded on this board fires NO space-conditioned bullet
    # (no Active-Opposition-no-Tory space, <5 controlled Cities), so
    # after the decision the key must simply be gone.
    bot._choose_event_vs_flowchart(st, _card16())
    assert "_event_q_spaces" not in st, (
        "stale set must be cleared before the bullet list runs")
