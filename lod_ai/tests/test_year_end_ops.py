"""Tests for year_end OPS wiring — verifying that bot priority methods
are used for Supply, Leader Redeploy, and Desertion when bots are provided."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from unittest.mock import MagicMock

from lod_ai.util import year_end
from lod_ai import rules_consts as C


# --------------------
# Fixtures
# --------------------

def basic_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "support": {},
        "control": {},
        "available": {},
        "markers": {
            C.RAID: {"pool": 0, "on_map": set()},
            C.PROPAGANDA: {"pool": 0, "on_map": set()},
            C.BLOCKADE: {"pool": 0, "on_map": set()},
        },
        "history": [],
        "leaders": {},
        "deck": [],
    }


def _noop_refresh(state):
    pass


# ============================================================
#  SUPPLY PRIORITY TESTS
# ============================================================

class TestBritishSupplyPriority:
    """British Supply: bot_supply_priority controls which space gets paid."""

    def test_bot_priority_respected(self, monkeypatch):
        """With 1 Resource, only the first space in bot priority gets paid."""
        monkeypatch.setattr(year_end.board_control, "refresh_control", _noop_refresh, raising=False)
        monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)

        state = basic_state()
        state["resources"][C.BRITISH] = 1
        # Three unsupplied spaces with British cubes
        state["spaces"] = {
            "SpaceA": {C.REGULAR_BRI: 2, C.TORY: 0},
            "SpaceB": {C.REGULAR_BRI: 1, C.TORY: 1},
            "SpaceC": {C.REGULAR_BRI: 3, C.TORY: 0},
            C.WEST_INDIES_ID: {},
        }
        state["support"] = {
            "SpaceA": C.ACTIVE_OPPOSITION,
            "SpaceB": C.ACTIVE_OPPOSITION,
            "SpaceC": C.ACTIVE_OPPOSITION,
        }

        # Bot says: pay SpaceC first, then SpaceA, then SpaceB
        bot = MagicMock()
        bot.bot_supply_priority.return_value = ["SpaceC", "SpaceA", "SpaceB"]
        bots = {C.BRITISH: bot}

        year_end._supply_phase(state, bots=bots, human_factions=set())

        # SpaceC should keep its pieces (paid), SpaceA and SpaceB should lose pieces
        assert state["spaces"]["SpaceC"][C.REGULAR_BRI] == 3  # kept
        assert state["spaces"]["SpaceA"].get(C.REGULAR_BRI, 0) == 0  # removed
        assert state["spaces"]["SpaceB"].get(C.REGULAR_BRI, 0) == 0  # removed


class TestPatriotSupplyPriority:
    """Patriot Supply: ops_supply_priority controls payment order."""

    def test_bot_priority_respected(self, monkeypatch):
        monkeypatch.setattr(year_end.board_control, "refresh_control", _noop_refresh, raising=False)
        monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)

        state = basic_state()
        state["resources"][C.PATRIOTS] = 1
        state["spaces"] = {
            "ColA": {C.MILITIA_U: 4, C.MILITIA_A: 0, C.REGULAR_PAT: 0},
            "ColB": {C.MILITIA_U: 2, C.MILITIA_A: 0, C.REGULAR_PAT: 0},
            C.WEST_INDIES_ID: {},
        }
        state["support"] = {"ColA": C.ACTIVE_OPPOSITION, "ColB": C.ACTIVE_OPPOSITION}

        bot = MagicMock()
        # Bot says pay ColB first (ColB keeps pieces, ColA loses)
        bot.ops_supply_priority.return_value = ["ColB", "ColA"]
        bots = {C.PATRIOTS: bot}

        year_end._supply_phase(state, bots=bots, human_factions=set())

        assert state["spaces"]["ColB"][C.MILITIA_U] == 2  # kept
        # ColA should have lost half its militia (4//2 = 2 removed)
        assert state["spaces"]["ColA"][C.MILITIA_U] == 2


class TestIndianSupplyPriority:
    """Indian Supply: ops_supply_priority(state, spaces) reorders unsupplied."""

    def test_bot_priority_respected(self, monkeypatch):
        monkeypatch.setattr(year_end.board_control, "refresh_control", _noop_refresh, raising=False)
        monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)

        state = basic_state()
        state["resources"][C.INDIANS] = 1
        state["spaces"] = {
            "ProvA": {C.WARPARTY_U: 2, C.WARPARTY_A: 0},
            "ProvB": {C.WARPARTY_U: 1, C.WARPARTY_A: 0, C.VILLAGE: 1},  # Village = in supply
            "ProvC": {C.WARPARTY_U: 3, C.WARPARTY_A: 0},
            C.WEST_INDIES_ID: {},
        }
        state["support"] = {}

        bot = MagicMock()
        # Bot reorders: ProvC first, then ProvA
        bot.ops_supply_priority.return_value = ["ProvC", "ProvA"]
        bots = {C.INDIANS: bot}

        year_end._supply_phase(state, bots=bots, human_factions=set())

        # Bot should have been called with the unsupplied spaces list
        bot.ops_supply_priority.assert_called_once()
        call_args = bot.ops_supply_priority.call_args
        # The second arg should be a list of unsupplied space IDs
        unsupplied_arg = call_args[0][1]
        assert "ProvA" in unsupplied_arg
        assert "ProvC" in unsupplied_arg
        assert "ProvB" not in unsupplied_arg  # ProvB has a Village, so in supply


# ============================================================
#  LEADER REDEPLOY TESTS
# ============================================================

class TestBritishRedeploy:
    """British bot_redeploy_leader picks space with most Regulars."""

    def test_bot_picks_most_regulars_not_most_pieces(self):
        state = basic_state()
        state["spaces"] = {
            "CityA": {C.REGULAR_BRI: 1, C.TORY: 5},  # 6 total but 1 Regular
            "CityB": {C.REGULAR_BRI: 3, C.TORY: 0},   # 3 total but 3 Regulars
        }
        state["leaders"] = {C.BRITISH: "LEADER_HOWE"}
        state["leader_locs"] = {}

        bot = MagicMock()
        bot.bot_redeploy_leader.return_value = "CityB"
        bots = {C.BRITISH: bot}

        year_end._leader_redeploy(state, bots=bots, human_factions=set())

        assert state["leader_locs"]["LEADER_HOWE"] == "CityB"
        assert any("bot" in h.get("msg", "") for h in state["history"])


class TestPatriotRedeploy:
    """Patriot ops_redeploy_washington picks space with most Continentals."""

    def test_bot_picks_most_continentals(self):
        state = basic_state()
        state["spaces"] = {
            "ColA": {C.MILITIA_U: 5, C.REGULAR_PAT: 1},  # most pieces
            "ColB": {C.REGULAR_PAT: 4},                    # most Continentals
        }
        state["leaders"] = {C.PATRIOTS: "LEADER_WASHINGTON"}
        state["leader_locs"] = {}

        bot = MagicMock()
        bot.ops_redeploy_washington.return_value = "ColB"
        bots = {C.PATRIOTS: bot}

        year_end._leader_redeploy(state, bots=bots, human_factions=set())

        assert state["leader_locs"]["LEADER_WASHINGTON"] == "ColB"


class TestFrenchRedeploy:
    """French ops_redeploy_leader prefers co-location with Continentals."""

    def test_bot_picks_colocation(self):
        state = basic_state()
        state["spaces"] = {
            "CityX": {C.REGULAR_FRE: 3, C.REGULAR_PAT: 0},  # French only
            "CityY": {C.REGULAR_FRE: 2, C.REGULAR_PAT: 2},  # co-located
        }
        state["leaders"] = {C.FRENCH: "LEADER_ROCHAMBEAU"}
        state["leader_locs"] = {}

        bot = MagicMock()
        bot.ops_redeploy_leader.return_value = "CityY"
        bots = {C.FRENCH: bot}

        year_end._leader_redeploy(state, bots=bots, human_factions=set())

        assert state["leader_locs"]["LEADER_ROCHAMBEAU"] == "CityY"


class TestIndianRedeploy:
    """Indian ops_redeploy returns dict with all leaders."""

    def test_multi_leader_uses_active_leader(self):
        state = basic_state()
        state["spaces"] = {
            "ProvA": {C.WARPARTY_U: 4, C.WARPARTY_A: 0, C.VILLAGE: 1},
            "ProvB": {C.WARPARTY_U: 2, C.WARPARTY_A: 0},
        }
        state["leaders"] = {C.INDIANS: "LEADER_BRANT"}
        state["leader_locs"] = {}

        bot = MagicMock()
        bot.ops_redeploy.return_value = {
            "LEADER_BRANT": "ProvA",
            "LEADER_CORNPLANTER": "ProvB",
            "LEADER_DRAGGING_CANOE": "ProvA",
        }
        bots = {C.INDIANS: bot}

        year_end._leader_redeploy(state, bots=bots, human_factions=set())

        # Should use the deploy_map entry for the active leader (LEADER_BRANT)
        assert state["leader_locs"]["LEADER_BRANT"] == "ProvA"


# ============================================================
#  DESERTION PRIORITY TESTS
# ============================================================

class TestIndianPatriotDesertionPriority:
    """Indian bot picks Patriot Desertion target via ops_patriot_desertion_priority."""

    def test_bot_picks_differently_than_default(self):
        state = basic_state()
        state["spaces"] = {
            "ColA": {"type": "Colony", C.MILITIA_U: 3, C.MILITIA_A: 0, C.REGULAR_PAT: 3},
            "ColB": {"type": "Colony", C.MILITIA_U: 2, C.MILITIA_A: 0, C.REGULAR_PAT: 2},
            C.WEST_INDIES_ID: {},
        }
        # Default heuristic would pick ColA (highest support)
        state["support"] = {"ColA": C.ACTIVE_SUPPORT, "ColB": C.PASSIVE_OPPOSITION}

        bot = MagicMock()
        # Bot picks ColB instead (e.g., because it has a Village)
        bot.ops_patriot_desertion_priority.return_value = [
            ("ColB", C.MILITIA_U),
            ("ColA", C.MILITIA_U),
        ]
        bots = {C.INDIANS: bot}

        year_end._patriot_desertion(state, bots=bots, human_factions=set())

        # ColB should have lost a Militia (Indian choice)
        assert state["spaces"]["ColB"][C.MILITIA_U] == 1


class TestFrenchToryDesertionPriority:
    """French bot picks Tory Desertion target via ops_loyalist_desertion_priority."""

    def test_bot_picks_differently_than_default(self):
        state = basic_state()
        state["spaces"] = {
            "SpA": {C.TORY: 3},
            "SpB": {C.TORY: 3},
        }
        # Default heuristic picks highest Patriot Support
        state["support"] = {"SpA": C.ACTIVE_SUPPORT, "SpB": C.PASSIVE_OPPOSITION}

        bot = MagicMock()
        # French bot picks SpB first (e.g., would change control)
        bot.ops_loyalist_desertion_priority.return_value = [
            ("SpB", C.TORY),
            ("SpA", C.TORY),
        ]
        bots = {C.FRENCH: bot}

        year_end._tory_desertion(state, bots=bots, human_factions=set())

        # SpB should have lost a Tory (French choice)
        assert state["spaces"]["SpB"][C.TORY] == 2


class TestBritishLoyalistDesertionAvoidLastTory:
    """British bot_loyalist_desertion preserves last Tory when possible."""

    def test_avoids_last_tory(self):
        state = basic_state()
        # 10 Tories total → remove 2 (10//5). French picks 1, British picks 1.
        state["spaces"] = {
            "SpA": {C.TORY: 1},   # last Tory — should be preserved
            "SpB": {C.TORY: 4},   # plenty
            "SpC": {C.TORY: 5},   # plenty
        }
        state["support"] = {"SpA": 0, "SpB": 0, "SpC": 0}

        french_bot = MagicMock()
        french_bot.ops_loyalist_desertion_priority.return_value = [
            ("SpC", C.TORY),
        ]

        british_bot = MagicMock()
        # British bot avoids last Tory in SpA, removes from SpB instead
        british_bot.bot_loyalist_desertion.return_value = [("SpB", 1)]

        bots = {C.FRENCH: french_bot, C.BRITISH: british_bot}

        year_end._tory_desertion(state, bots=bots, human_factions=set())

        assert state["spaces"]["SpA"][C.TORY] == 1  # preserved
        assert state["spaces"]["SpC"][C.TORY] == 4  # French took 1
        assert state["spaces"]["SpB"][C.TORY] == 3  # British took 1


# ============================================================
#  BACKWARD COMPATIBILITY TESTS
# ============================================================

class TestBackwardCompat:
    """Verify resolve(state) with no extra args still works."""

    def test_no_bots_passed(self, monkeypatch):
        """resolve(state) with no bots arg uses old behavior."""
        monkeypatch.setattr(year_end, "victory_check", lambda s: False)
        monkeypatch.setattr(year_end, "return_leaders", lambda s: None)
        monkeypatch.setattr(year_end.board_control, "refresh_control", _noop_refresh, raising=False)
        monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)

        state = basic_state()
        state["spaces"] = {
            "A": {"type": "Colony", C.MILITIA_U: 5, C.TORY: 5},
            C.WEST_INDIES_ID: {},
        }
        state["support"] = {"A": C.ACTIVE_OPPOSITION}
        state["eligible"] = {C.BRITISH: True, C.PATRIOTS: True, C.FRENCH: True, C.INDIANS: True}
        state["deck"] = [{"title": "Next"}]

        # Should not raise — backward compat
        year_end.resolve(state)

    def test_human_faction_skipped(self, monkeypatch):
        """With British as human and others as bot, British uses old logic."""
        monkeypatch.setattr(year_end.board_control, "refresh_control", _noop_refresh, raising=False)
        monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)

        state = basic_state()
        state["resources"][C.BRITISH] = 1
        state["spaces"] = {
            "SpA": {C.REGULAR_BRI: 2},
            "SpB": {C.REGULAR_BRI: 1},
            C.WEST_INDIES_ID: {},
        }
        state["support"] = {"SpA": C.ACTIVE_OPPOSITION, "SpB": C.ACTIVE_OPPOSITION}

        bot = MagicMock()
        bots = {C.BRITISH: bot}

        # British is human — bot_supply_priority should NOT be called
        year_end._supply_phase(state, bots=bots, human_factions={C.BRITISH})

        bot.bot_supply_priority.assert_not_called()
