"""§8.3.3 clause 2 (TRACEABILITY.md T3): an Event is Ineffective for a
Non-player when its ONLY effect would be to remove one or more friendly
pieces without replacing them with other friendly pieces. "Friendly"
spans the Side (Glossary; §1.5.2)."""
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot
from lod_ai.cards import CARD_HANDLERS
from lod_ai.board.pieces import remove_piece, place_piece

TEST_CARD_ID = 9901


def _bot(faction):
    b = BaseBot()
    b.faction = faction
    return b


def _state():
    return {
        "spaces": {
            "Massachusetts": {C.MILITIA_A: 2, C.MILITIA_U: 1, C.TORY: 1},
            "Georgia": {C.REGULAR_BRI: 2},
        },
        "available": {}, "casualties": {}, "unavailable": {},
        "support": {"Massachusetts": -1},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "rng": random.Random(11),
    }


@pytest.fixture
def fake_card(monkeypatch):
    """Install a handler for TEST_CARD_ID; each test sets .effect."""
    holder = {}
    def handler(state, shaded=False):
        holder["effect"](state)
    monkeypatch.setitem(CARD_HANDLERS, TEST_CARD_ID, handler)
    return holder


CARD = {"id": TEST_CARD_ID, "dual": False}


def test_pure_friendly_removal_is_ineffective(fake_card):
    fake_card["effect"] = lambda st: remove_piece(
        st, C.MILITIA_A, "Massachusetts", 2, to="available")
    assert _bot(C.PATRIOTS)._is_ineffective_event(CARD, _state()) is True


def test_ally_piece_removal_counts_as_friendly(fake_card):
    """French bot: Patriot Militia are friendly (same Side)."""
    fake_card["effect"] = lambda st: remove_piece(
        st, C.MILITIA_A, "Massachusetts", 1, to="casualties")
    assert _bot(C.FRENCH)._is_ineffective_event(CARD, _state()) is True


def test_enemy_removal_is_not_caught(fake_card):
    """British bot removing Patriot pieces: harmful to the enemy, plays."""
    fake_card["effect"] = lambda st: remove_piece(
        st, C.MILITIA_A, "Massachusetts", 2, to="available")
    assert _bot(C.BRITISH)._is_ineffective_event(CARD, _state()) is False


def test_removal_with_replacement_plays(fake_card):
    def eff(st):
        remove_piece(st, C.MILITIA_A, "Massachusetts", 2, to="available")
        place_piece(st, C.FORT_PAT, "Massachusetts", 1)
    fake_card["effect"] = eff
    st = _state()
    st["available"][C.FORT_PAT] = 1
    assert _bot(C.PATRIOTS)._is_ineffective_event(CARD, st) is False


def test_removal_plus_other_effect_is_not_only_removal(fake_card):
    """Strict transcription: removal + a Resource change is not 'only'
    a removal, so this clause does not fire."""
    def eff(st):
        remove_piece(st, C.MILITIA_A, "Massachusetts", 2, to="available")
        st["resources"][C.PATRIOTS] += 3
    fake_card["effect"] = eff
    assert _bot(C.PATRIOTS)._is_ineffective_event(CARD, _state()) is False


def test_no_effect_at_all_still_ineffective(fake_card):
    fake_card["effect"] = lambda st: None
    assert _bot(C.PATRIOTS)._is_ineffective_event(CARD, _state()) is True
