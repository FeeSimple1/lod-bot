"""T15 (Session 41): "would-be-removed / would-gain" sheet conditions
tightened by simulation — P80, F73, F95, F83.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.french import FrenchBot
from lod_ai import rules_consts as C


def _state(spaces, available=None):
    return {
        "spaces": spaces,
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": available or {}, "unavailable": {}, "casualties": {},
        "support": {}, "control": {}, "markers": {}, "leaders": {},
        "rng": random.Random(9), "history": [], "fni_level": 0,
    }


class TestP80VillageWouldBeRemoved:
    def test_village_behind_war_parties_does_not_qualify(self):
        """Card 80 removes 2 Indian pieces War-Parties-first: a Village
        behind 3 War Parties survives — condition False (the old check
        accepted any Village)."""
        bot = PatriotBot()
        st = _state({"Northwest": {C.VILLAGE: 1, C.WARPARTY_U: 3}})
        assert bot._force_condition_met("force_if_80", st, {}) is False

    def test_exposed_village_qualifies_and_targets(self):
        """<=1 non-Village piece: the second removal reaches the Village."""
        bot = PatriotBot()
        st = _state({"Northwest": {C.VILLAGE: 1, C.WARPARTY_U: 1},
                     "Southwest": {C.VILLAGE: 1, C.WARPARTY_U: 4}})
        assert bot._force_condition_met("force_if_80", st, {}) is True
        assert st["card80_faction"] == C.INDIANS
        assert st["card80_spaces"] == ["Northwest"]


class TestF73F95FortInRemovableSpace:
    def test_f73_fort_outside_card_spaces_declines(self):
        """Card 73 only removes in New_York / Northwest / Quebec."""
        bot = FrenchBot()
        st = _state({"Georgia": {C.FORT_BRI: 1}, "New_York": {}})
        assert bot._force_condition_met("force_if_73", st, {}) is False

    def test_f73_fort_in_card_space_qualifies_and_pins_target(self):
        bot = FrenchBot()
        st = _state({"New_York": {C.FORT_PAT: 1}, "Quebec": {C.FORT_BRI: 1}})
        assert bot._force_condition_met("force_if_73", st, {}) is True
        assert st["card73_space"] == "Quebec", (
            "the pinned target must hold the BRITISH Fort")

    def test_f95_requires_northwest_fort(self):
        bot = FrenchBot()
        st = _state({"New_York": {C.FORT_BRI: 1}, "Northwest": {}})
        assert bot._force_condition_met("force_if_95", st, {}) is False
        st["spaces"]["Northwest"][C.FORT_BRI] = 1
        assert bot._force_condition_met("force_if_95", st, {}) is True


class TestF83GainSimulation:
    def test_gain_impossible_against_big_garrison(self):
        """5 Royalist pieces in Quebec City: 3 placed pieces cannot gain
        Rebellion Control — condition False (was unconditionally True
        whenever QC wasn't already Rebellion)."""
        bot = FrenchBot()
        st = _state({"Quebec_City": {C.REGULAR_BRI: 5}},
                    available={C.REGULAR_FRE: 5, C.MILITIA_U: 5})
        assert bot._force_condition_met("force_if_83", st, {}) is False

    def test_gain_possible_with_available_pieces(self):
        bot = FrenchBot()
        st = _state({"Quebec_City": {C.REGULAR_BRI: 2}},
                    available={C.REGULAR_FRE: 3, C.FORT_PAT: 1})
        assert bot._force_condition_met("force_if_83", st, {}) is True
        assert st["card83_target"] == "Quebec_City"

    def test_no_available_pieces_declines(self):
        bot = FrenchBot()
        st = _state({"Quebec_City": {C.REGULAR_BRI: 1}}, available={})
        assert bot._force_condition_met("force_if_83", st, {}) is False
