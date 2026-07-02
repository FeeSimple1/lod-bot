"""§8.1 "Commands Not Limited" (TRACEABILITY.md T1).

"Whenever a Non-player Faction by the Sequence of Play (2.3.4) is to
execute a Limited Command (2.3.5), it instead executes a full Command and
Special Activity." Human seats keep the SoP limitation; event-granted
free LimComs stay limited via the free-op path (max one space).
"""
import random

from lod_ai import rules_consts as C
from lod_ai.engine import Engine


def _engine(humans=()):
    eng = Engine(initial_state={
        "spaces": {},
        "resources": {C.BRITISH: 20, C.PATRIOTS: 20,
                      C.FRENCH: 20, C.INDIANS: 20},
        "available": {}, "unavailable": {}, "markers": {}, "support": {},
        "rng": random.Random(1),
    })
    if humans:
        eng.set_human_factions(humans)
    return eng


FIRST_CMD_WITH_SA = {"action": "command", "used_special": True}
FIRST_CMD_NO_SA = {"action": "command", "used_special": False}


def test_bot_second_eligible_after_command_gets_full_command_and_sa():
    eng = _engine()
    for first in (FIRST_CMD_WITH_SA, FIRST_CMD_NO_SA):
        allowed = eng._allowed_for_faction(C.PATRIOTS, first)
        assert allowed["limited_only"] is False
        assert allowed["special_allowed"] is True


def test_bot_slot_keeps_sop_event_and_action_availability():
    """§8.1 upgrades only the Command scope — Event availability still
    follows the Sequence of Play."""
    eng = _engine()
    after_sa = eng._allowed_for_faction(C.PATRIOTS, FIRST_CMD_WITH_SA)
    assert after_sa["event_allowed"] is True          # Event or LimCom slot
    after_plain = eng._allowed_for_faction(C.PATRIOTS, FIRST_CMD_NO_SA)
    assert after_plain["event_allowed"] is False      # LimCom-only slot
    assert after_plain["actions"] == {"pass", "command"}


def test_human_second_eligible_keeps_limited_command():
    eng = _engine(humans={C.PATRIOTS})
    allowed = eng._allowed_for_faction(C.PATRIOTS, FIRST_CMD_NO_SA)
    assert allowed["limited_only"] is True
    assert allowed["special_allowed"] is False
    # and a bot seat in the same game is still upgraded
    bot_allowed = eng._allowed_for_faction(C.BRITISH, FIRST_CMD_NO_SA)
    assert bot_allowed["limited_only"] is False
    assert bot_allowed["special_allowed"] is True


def test_first_eligible_unchanged():
    eng = _engine()
    allowed = eng._allowed_for_faction(C.BRITISH, None)
    assert allowed["limited_only"] is False
    assert allowed["special_allowed"] is True
    assert allowed["event_allowed"] is True


def test_second_after_event_unchanged():
    """After a 1st-eligible Event the SoP grants a full Command anyway —
    no §8.1 adjustment should alter that slot."""
    eng = _engine()
    allowed = eng._allowed_for_faction(C.BRITISH, {"action": "event"})
    assert allowed["limited_only"] is False
    assert allowed["special_allowed"] is True
    assert allowed["event_allowed"] is False
