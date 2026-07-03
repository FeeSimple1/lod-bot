"""§8.4.11/§8.6.11/§8.7.8 reaction triggers ("…or the X play their
Brilliant Stroke") — Session 34. The engine now re-polls bots after each
declaration; previously other_bs_faction was always None and no bot
could ever respond to another's BS."""
import random
from unittest.mock import patch

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.cards.effects import brilliant_stroke as bs


def _engine():
    eng = Engine(initial_state={
        "spaces": {}, "resources": {C.BRITISH: 9, C.PATRIOTS: 9,
                                    C.FRENCH: 9, C.INDIANS: 9},
        "available": {}, "unavailable": {}, "markers": {}, "support": {},
        "rng": random.Random(1),
    })
    eng.set_human_factions(set())
    return eng


def test_british_bot_responds_to_patriot_bs_and_trumps():
    eng = _engine()
    infos = {
        C.PATRIOTS: {"faction": C.PATRIOTS, "key": "PAT_BS", "toa": False},
        C.BRITISH: {"faction": C.BRITISH, "key": "BRI_BS", "toa": False},
    }
    marks = []

    def fake_wants(state, fac, first_eligible=None, human_factions=None,
                   other_bs_faction=None):
        # British reaction trigger only (8.4.11): Patriots play their BS.
        return fac == C.BRITISH and other_bs_faction == C.PATRIOTS

    with patch.object(eng, "_bs_decl_info", side_effect=lambda d: infos[d]), \
         patch.object(eng, "_bs_is_legal", return_value=True), \
         patch.object(eng, "_bs_can_trump",
                      side_effect=lambda i, cur: i["faction"] == C.BRITISH
                      and cur["faction"] == C.PATRIOTS), \
         patch.object(bs, "bot_wants_bs", side_effect=fake_wants), \
         patch.object(bs, "mark_bs_played",
                      side_effect=lambda st, key, played: marks.append((key, played))):
        current = eng._bs_trump_chain([C.PATRIOTS], first_eligible=None)

    assert current["faction"] == C.BRITISH        # reaction fired + trumped
    assert ("PAT_BS", True) in marks              # Patriots declared…
    assert ("PAT_BS", False) in marks             # …then returned (trumped)
    assert ("BRI_BS", True) in marks              # British card committed


def test_no_reaction_without_trigger():
    eng = _engine()
    info = {"faction": C.PATRIOTS, "key": "PAT_BS", "toa": False}
    with patch.object(eng, "_bs_decl_info", return_value=info), \
         patch.object(eng, "_bs_is_legal", return_value=True), \
         patch.object(bs, "bot_wants_bs", return_value=False), \
         patch.object(bs, "mark_bs_played"):
        current = eng._bs_trump_chain([C.PATRIOTS], first_eligible=None)
    assert current["faction"] == C.PATRIOTS
