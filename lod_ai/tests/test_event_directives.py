import pytest
from lod_ai.bots import event_instructions as EI
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.indians import IndianBot
from lod_ai.bots.french import FrenchBot


def test_instruction_constants_exist():
    assert isinstance(EI.BRITISH, dict)
    assert isinstance(EI.PATRIOTS, dict)
    assert isinstance(EI.INDIANS, dict)
    assert isinstance(EI.FRENCH, dict)


def test_event_directive_lookup():
    brit = BritishBot()
    pat = PatriotBot()
    fre = FrenchBot()
    ind = IndianBot()
    # PatriotBot stores faction name as "PATRIOTS" so adjust for lookup
    pat.faction = "PATRIOTS"

    assert brit._event_directive(18) == EI.BRITISH[18]
    assert pat._event_directive(18) == EI.PATRIOTS[18]
    assert fre._event_directive(52) == EI.FRENCH[52]
    card_id = next(iter(EI.INDIANS))
    assert pat._event_directive(18) == EI.PATRIOTS[18]
    assert ind._event_directive(card_id) == EI.INDIANS[card_id]
