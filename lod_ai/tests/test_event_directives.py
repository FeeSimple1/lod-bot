import pytest
from lod_ai.bots import event_instructions as EI
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.french import FrenchBot


def test_instruction_constants_exist():
    assert isinstance(EI.BRITISH, dict)
    assert isinstance(EI.PATRIOT, dict)
    assert isinstance(EI.INDIAN, dict)
    assert isinstance(EI.FRENCH, dict)


def test_event_directive_lookup():
    brit = BritishBot()
    pat = PatriotBot()
    fre = FrenchBot()
    # PatriotBot stores faction name as "PATRIOTS" so adjust for lookup
    pat.faction = "PATRIOT"

    assert brit._event_directive(18) == "ignore"
    assert pat._event_directive(18) == "force"
    assert fre._event_directive(52) == "force"


