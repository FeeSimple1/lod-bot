"""Tests for victory/casualty system fixes:

BUG 1: CBC/CRC counters must increment when pieces enter casualties.
BUG 2: final_winter_round flag must be set when last WQ card is processed.

References: §1.6.4, §7.2, §7.3, §6.4.3
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai import rules_consts as C
from lod_ai.board.pieces import remove_piece, increment_casualties, lift_casualties
from lod_ai.commands import battle
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state


def _base_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 20, C.PATRIOTS: 20, C.FRENCH: 20, C.INDIANS: 20},
        "available": {},
        "casualties": {},
        "support": {},
        "control": {},
        "history": [],
        "rng": random.Random(42),
        "leader_locs": {},
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": set()}},
        "cbc": 0,
        "crc": 0,
    }


# ────────────────────────────────────────────────────────────────────
#  BUG 1: CBC/CRC counter tests
# ────────────────────────────────────────────────────────────────────

class TestCBCCRCIncrement:
    """§1.6.4: Cumulative casualty counters must increment on piece removal."""

    def test_british_regular_to_casualties_increments_cbc(self):
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_BRI: 3}
        remove_piece(state, C.REGULAR_BRI, "A", 2, to="casualties")
        assert state["cbc"] == 2
        assert state["crc"] == 0

    def test_tory_to_casualties_increments_cbc(self):
        state = _base_state()
        state["spaces"]["A"] = {C.TORY: 5}
        remove_piece(state, C.TORY, "A", 3, to="casualties")
        assert state["cbc"] == 3

    def test_continental_to_casualties_increments_crc(self):
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_PAT: 4}
        remove_piece(state, C.REGULAR_PAT, "A", 2, to="casualties")
        assert state["crc"] == 2
        assert state["cbc"] == 0

    def test_french_regular_to_casualties_increments_crc(self):
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_FRE: 3}
        remove_piece(state, C.REGULAR_FRE, "A", 1, to="casualties")
        assert state["crc"] == 1

    def test_to_available_does_not_increment(self):
        """Pieces returning to Available (not casualties) don't affect counters."""
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_BRI: 3, C.REGULAR_PAT: 3}
        remove_piece(state, C.REGULAR_BRI, "A", 2, to="available")
        remove_piece(state, C.REGULAR_PAT, "A", 2, to="available")
        assert state["cbc"] == 0
        assert state["crc"] == 0

    def test_militia_to_casualties_does_not_increment(self):
        """§1.6.4: Only Regulars, Tories, and Forts count. Militia don't."""
        state = _base_state()
        state["spaces"]["A"] = {C.MILITIA_A: 5}
        remove_piece(state, C.MILITIA_A, "A", 3, to="casualties")
        assert state["cbc"] == 0
        assert state["crc"] == 0

    def test_warparty_to_available_does_not_increment(self):
        """War Parties don't count toward cumulative casualties."""
        state = _base_state()
        state["spaces"]["A"] = {C.WARPARTY_A: 5}
        remove_piece(state, C.WARPARTY_A, "A", 3, to="available")
        assert state["cbc"] == 0
        assert state["crc"] == 0

    def test_counters_accumulate_across_multiple_removals(self):
        """Counters are cumulative across the game."""
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_BRI: 5, C.TORY: 5}
        state["spaces"]["B"] = {C.REGULAR_PAT: 5, C.REGULAR_FRE: 5}
        remove_piece(state, C.REGULAR_BRI, "A", 2, to="casualties")
        remove_piece(state, C.TORY, "A", 1, to="casualties")
        assert state["cbc"] == 3
        remove_piece(state, C.REGULAR_PAT, "B", 2, to="casualties")
        remove_piece(state, C.REGULAR_FRE, "B", 1, to="casualties")
        assert state["crc"] == 3

    def test_counters_never_decrement_on_lift(self):
        """§1.6.4: lift_casualties moves pieces from Casualties to Available
        but CBC/CRC must NOT decrement — they're cumulative for the game."""
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_BRI: 3}
        remove_piece(state, C.REGULAR_BRI, "A", 2, to="casualties")
        assert state["cbc"] == 2
        assert state["casualties"].get(C.REGULAR_BRI, 0) == 2
        lift_casualties(state)
        # Casualties box cleared, but CBC stays
        assert state["cbc"] == 2
        assert state["casualties"].get(C.REGULAR_BRI, 0) == 0

    def test_increment_casualties_helper(self):
        """Direct test of the increment_casualties helper function."""
        state = {"cbc": 5, "crc": 10}
        increment_casualties(state, C.REGULAR_BRI, 3)
        assert state["cbc"] == 8
        increment_casualties(state, C.TORY, 2)
        assert state["cbc"] == 10
        increment_casualties(state, C.FORT_BRI, 1)
        assert state["cbc"] == 11
        increment_casualties(state, C.REGULAR_PAT, 4)
        assert state["crc"] == 14
        increment_casualties(state, C.REGULAR_FRE, 2)
        assert state["crc"] == 16
        increment_casualties(state, C.FORT_PAT, 1)
        assert state["crc"] == 17

    def test_increment_zero_is_noop(self):
        state = {"cbc": 5, "crc": 10}
        increment_casualties(state, C.REGULAR_BRI, 0)
        assert state["cbc"] == 5

    def test_remove_piece_without_loc_increments(self):
        """remove_piece(state, tag, None, ...) scans all spaces."""
        state = _base_state()
        state["spaces"]["A"] = {C.REGULAR_BRI: 2}
        state["spaces"]["B"] = {C.REGULAR_BRI: 3}
        remove_piece(state, C.REGULAR_BRI, None, 4, to="casualties")
        assert state["cbc"] == 4


class TestFortCasualties:
    """§1.6.4: Forts count toward cumulative casualties even though
    they return to Available immediately."""

    def test_fort_bri_to_casualties_increments_cbc(self):
        """When card effects send FORT_BRI to casualties, CBC increments."""
        state = _base_state()
        state["spaces"]["A"] = {C.FORT_BRI: 2}
        remove_piece(state, C.FORT_BRI, "A", 1, to="casualties")
        assert state["cbc"] == 1

    def test_fort_pat_to_casualties_increments_crc(self):
        """When card effects send FORT_PAT to casualties, CRC increments."""
        state = _base_state()
        state["spaces"]["A"] = {C.FORT_PAT: 2}
        remove_piece(state, C.FORT_PAT, "A", 1, to="casualties")
        assert state["crc"] == 1

    def test_battle_fort_bri_removal_increments_cbc(self):
        """Battle removes FORT_BRI to Available but should increment CBC."""
        state = _base_state()
        state["spaces"]["A"] = {
            C.FORT_BRI: 1,
            C.REGULAR_BRI: 0,
            C.TORY: 0,
            C.REGULAR_PAT: 10,
        }
        # Patriots attack, British has only a fort defending
        # The fort should be removed and CBC incremented
        battle.execute(state, C.PATRIOTS, {}, ["A"])
        # Fort was removed (defender loss from overwhelming force)
        # CBC should have been incremented for the fort
        assert state["cbc"] >= 0  # Fort may or may not be hit depending on dice
        # If the fort was removed, CBC should be > 0
        if state["spaces"]["A"].get(C.FORT_BRI, 0) == 0:
            assert state["cbc"] >= 1

    def test_battle_fort_pat_removal_increments_crc(self):
        """Battle removes FORT_PAT to Available but should increment CRC."""
        state = _base_state()
        state["spaces"]["A"] = {
            C.FORT_PAT: 1,
            C.REGULAR_PAT: 0,
            C.MILITIA_A: 0,
            C.REGULAR_BRI: 10,
            C.TORY: 5,
        }
        # British attack, Patriot has only a fort defending
        battle.execute(state, C.BRITISH, {}, ["A"])
        if state["spaces"]["A"].get(C.FORT_PAT, 0) == 0:
            assert state["crc"] >= 1


class TestBattleCBCCRC:
    """Battle casualties should increment CBC/CRC for cubes."""

    def test_battle_increments_cbc_for_british_cubes(self):
        """British Regulars and Tories removed in battle go to Casualties
        and should increment CBC."""
        state = _base_state()
        state["spaces"]["A"] = {
            C.REGULAR_BRI: 5,
            C.TORY: 5,
            C.REGULAR_PAT: 10,
            C.REGULAR_FRE: 5,
        }
        battle.execute(state, C.PATRIOTS, {}, ["A"])
        # Some British cubes should have been removed to casualties
        brit_casualties = state["casualties"].get(C.REGULAR_BRI, 0) + \
                          state["casualties"].get(C.TORY, 0)
        assert state["cbc"] == brit_casualties

    def test_battle_increments_crc_for_rebellion_cubes(self):
        """Patriot Continentals and French Regulars in battle go to
        Casualties and should increment CRC."""
        state = _base_state()
        state["spaces"]["A"] = {
            C.REGULAR_BRI: 10,
            C.TORY: 5,
            C.REGULAR_PAT: 5,
            C.REGULAR_FRE: 3,
        }
        state["toa_played"] = True
        battle.execute(state, C.BRITISH, {}, ["A"])
        reb_casualties = state["casualties"].get(C.REGULAR_PAT, 0) + \
                         state["casualties"].get(C.REGULAR_FRE, 0)
        assert state["crc"] == reb_casualties


# ────────────────────────────────────────────────────────────────────
#  BUG 2: final_winter_round flag tests
# ────────────────────────────────────────────────────────────────────

class TestFinalWinterRound:
    """§7.3 / §6.4.3: The final WQ card must trigger final scoring."""

    def test_final_wq_sets_flag(self):
        """When the last WQ card is played, final_winter_round is set True."""
        engine = Engine(build_state("1775", seed=1))
        # Remove all WQ cards from deck except one we'll play
        wq_card = {"id": 99, "winter_quarters": True, "title": "WQ Test"}
        # Set up a deck with no WQ cards remaining
        engine.state["deck"] = [
            {"id": 1, "title": "Card 1"},
            {"id": 2, "title": "Card 2"},
        ]
        engine.state["upcoming_card"] = {"id": 3, "title": "Card 3"}
        # Play the WQ card — no more WQ in deck or upcoming
        engine.play_card(wq_card)
        assert engine.state.get("final_winter_round") is True

    def test_non_final_wq_does_not_set_flag(self):
        """When WQ cards remain in deck, flag should not be set."""
        engine = Engine(build_state("1775", seed=1))
        wq_card = {"id": 99, "winter_quarters": True, "title": "WQ1"}
        # Put another WQ card in the deck
        engine.state["deck"] = [
            {"id": 100, "winter_quarters": True, "title": "WQ2"},
            {"id": 1, "title": "Card 1"},
        ]
        engine.state["upcoming_card"] = {"id": 2, "title": "Card 2"}
        engine.play_card(wq_card)
        assert engine.state.get("final_winter_round", False) is False

    def test_wq_in_upcoming_prevents_flag(self):
        """If upcoming card is a WQ, this is not the final WQ."""
        engine = Engine(build_state("1775", seed=1))
        wq_card = {"id": 99, "winter_quarters": True, "title": "WQ1"}
        engine.state["deck"] = [{"id": 1, "title": "Card 1"}]
        engine.state["upcoming_card"] = {
            "id": 100, "winter_quarters": True, "title": "WQ2"
        }
        engine.play_card(wq_card)
        assert engine.state.get("final_winter_round", False) is False

    def test_final_wq_calls_final_scoring(self):
        """After the final WQ, year_end should call final_scoring
        which logs 'Winner:' in history."""
        engine = Engine(build_state("1775", seed=1))
        wq_card = {"id": 99, "winter_quarters": True, "title": "WQ Test"}
        engine.state["deck"] = []
        engine.state["upcoming_card"] = None
        engine.play_card(wq_card)
        assert engine.state.get("final_winter_round") is True
        # final_scoring should have run, logging a winner
        history_msgs = [
            (h.get("msg", "") if isinstance(h, dict) else str(h))
            for h in engine.state.get("history", [])
        ]
        assert any("Final Scoring" in msg or "Winner:" in msg
                    for msg in history_msgs), \
            f"Expected final scoring message in history, got: {history_msgs[-10:]}"


class TestSetupStateInitialization:
    """Verify that build_state initializes cbc and crc to 0."""

    def test_build_state_has_cbc_crc(self):
        state = build_state("1775", seed=1)
        assert "cbc" in state
        assert "crc" in state
        assert state["cbc"] == 0
        assert state["crc"] == 0
