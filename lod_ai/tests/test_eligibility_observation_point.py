"""Timed-eligibility observation-point gates (S76, from the fs-bot
"set-but-never-applied" audit brief).

The fs lesson: assert eligibility AFTER the end-of-card adjustment, not
at the handler's set-site — in both fs failure modes the handler was
correct and the §2.3.9 reset won.  LoD verdicts, Manual in hand:

* "Ineligible through the next card": the Manual's play note (§2.3.9)
  says the marker shows the faction "will be Ineligible FOR THE NEXT
  card" — the current card's acting queue is unaffected by design, and
  the flag must survive the did-not-act reset bullet ("and was not
  rendered Ineligible by an Event").  VERIFIED conforming.
* "remain Eligible": consumed by _mark_executed at the grant card's own
  adjustment.  BUG FOUND & FIXED (S76): a grant to a faction that did
  NOT act that card went stale and wrongly retained the faction after a
  LATER card's Command.  _prepare_card now clears leftovers.
* Collision (both flags): the specific penalty beats the general
  retention — ineligible_through_next is consumed after eligible_next.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state


def _engine():
    eng = Engine(initial_state=build_state("1776", seed=2), use_cli=False)
    eng.set_human_factions([])
    return eng


def _card(n):
    return {"id": 200 + n, "title": f"stub{n}",
            "order": [C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS]}


def test_ineligible_through_next_survives_the_did_not_act_reset():
    """A faction that did NOT act, rendered Ineligible by an Event,
    must NOT be flipped back by the 'did not act -> Eligible' bullet."""
    eng = _engine()
    eng._prepare_card(_card(1))
    # Event on card 1 benches the French; French never act on card 1.
    eng.state.setdefault("ineligible_through_next", set()).add(C.FRENCH)
    queue = eng._prepare_card(_card(2))     # the adjustment + next card
    assert eng.state["eligible"][C.FRENCH] is False
    assert C.FRENCH not in queue
    # ...and the penalty is spent: card 3 restores them.
    queue3 = eng._prepare_card(_card(3))
    assert eng.state["eligible"][C.FRENCH] is True
    assert C.FRENCH in queue3


def test_remain_eligible_consumed_by_the_acting_faction():
    eng = _engine()
    eng._prepare_card(_card(1))
    eng.state.setdefault("remain_eligible", set()).add(C.BRITISH)
    eng._mark_executed(C.BRITISH)           # acted; grant consumes here
    queue = eng._prepare_card(_card(2))
    assert eng.state["eligible"][C.BRITISH] is True
    assert C.BRITISH in queue
    # The retention was one-shot: acting on card 2 benches them for 3.
    eng._mark_executed(C.BRITISH)
    eng._prepare_card(_card(3))
    assert eng.state["eligible"][C.BRITISH] is False


def test_stale_remain_eligible_grant_does_not_fire_on_a_later_card():
    """S76 bug: a remain-Eligible grant to a NON-acting faction (card 67
    can name the non-executing partner) must expire at its card's
    adjustment, not retain the faction after some later Command."""
    eng = _engine()
    eng._prepare_card(_card(1))
    eng.state.setdefault("remain_eligible", set()).add(C.FRENCH)
    # French do NOT act on card 1; adjustment happens.
    eng._prepare_card(_card(2))
    assert C.FRENCH not in (eng.state.get("remain_eligible") or set()), (
        "stale grant must be cleared at the next card's start")
    # French act normally on card 2 -> they must be benched for card 3.
    eng._mark_executed(C.FRENCH)
    eng._prepare_card(_card(3))
    assert eng.state["eligible"][C.FRENCH] is False, (
        "the stale grant must not retain the French after a later card")


def test_collision_penalty_beats_retention():
    """A faction under BOTH 'remain Eligible' (acted, consumed) and
    'Ineligible through next card': the specific penalty wins."""
    eng = _engine()
    eng._prepare_card(_card(1))
    eng.state.setdefault("remain_eligible", set()).add(C.PATRIOTS)
    eng._mark_executed(C.PATRIOTS)          # retention -> eligible_next
    eng.state.setdefault("ineligible_through_next", set()).add(C.PATRIOTS)
    queue = eng._prepare_card(_card(2))
    assert eng.state["eligible"][C.PATRIOTS] is False
    assert C.PATRIOTS not in queue
