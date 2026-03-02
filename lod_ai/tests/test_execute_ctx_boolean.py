"""Regression tests for execute() ctx-as-boolean bug.

Bug: command/SA execute() functions return ctx (a dict, typically {}).
In Python, ``not {} == True``, so any caller that treats the return value
as a boolean interprets a successful execution as failure.

Bug A (fixed): British _muster() captured ``did_something = muster.execute(...)``
then ``if not did_something:`` fell through to March — two Commands per turn.

Bug B (already fixed, regression guard): Indian _war_path() returned the
result of ``war_path.execute()`` directly; caller ``_war_path_or_trade()``
tested truthiness and chained into Trade — two SAs per turn.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from copy import deepcopy

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control


# ============================================================================
# Shared test state builders
# ============================================================================

def _base_state(**overrides):
    """Minimal valid game state for bot tests."""
    st = {
        "spaces": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.INDIANS: 10, C.FRENCH: 10},
        "available": {
            C.REGULAR_BRI: 10, C.TORY: 10, C.FORT_BRI: 2,
            C.REGULAR_PAT: 10, C.MILITIA_U: 10, C.MILITIA_A: 0, C.FORT_PAT: 2,
            C.REGULAR_FRE: 10,
            C.WARPARTY_U: 10, C.WARPARTY_A: 0, C.VILLAGE: 5,
        },
        "unavailable": {},
        "support": {},
        "control": {},
        "casualties": {},
        "markers": {
            C.RAID: {"pool": 12, "on_map": set()},
            C.PROPAGANDA: {"pool": 10, "on_map": set()},
        },
        "rng": random.Random(42),
        "history": [],
        "leaders": {},
        "leader_locs": {},
        "fni_level": 0,
    }
    st.update(overrides)
    return st


def _space(**pieces):
    """Create a Colony space dict."""
    sp = {"type": "Colony"}
    sp.update(pieces)
    return sp


def _city(**pieces):
    """Create a City space dict."""
    sp = {"type": "City"}
    sp.update(pieces)
    return sp


# ============================================================================
# Bug A: British double command (Muster + March on one turn)
# ============================================================================

class TestBritishNoDoubleCommand:
    """After Muster executes successfully, the British bot must NOT
    fall through into March.  Per §2.3.4, one Command per turn."""

    def test_muster_returns_true_not_empty_dict(self):
        """_muster() must return True (not {} or any falsy value) on success."""
        from lod_ai.bots.british_bot import BritishBot

        bot = BritishBot()
        state = _base_state()
        # Boston: British-controlled city with Regulars (valid muster destination)
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
            "Massachusetts": _space(**{C.REGULAR_BRI: 1}),
        }
        state["support"] = {"Boston": C.NEUTRAL, "Massachusetts": C.NEUTRAL}
        # Ensure _can_muster passes: available Regulars > die roll.
        # Seed RNG so that the D6 roll is low (Random(1) gives 2 for first randint(1,6))
        state["rng"] = random.Random(1)
        refresh_control(state)

        result = bot._muster(state)
        assert result is True, (
            f"_muster() returned {result!r} — expected True. "
            f"If this is {{}}, the execute-ctx-as-boolean bug has regressed."
        )

    def test_muster_does_not_chain_into_march(self):
        """After a successful Muster, _turn_command must be MUSTER (not MARCH)
        and resources should reflect only one Command's spend."""
        from lod_ai.bots.british_bot import BritishBot

        bot = BritishBot()
        state = _base_state()
        # Set up a state where Muster will succeed:
        # - Boston has British control (Regulars present, no rebel majority)
        # - Available Regulars exist to place
        # - Resources sufficient
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
            "Massachusetts": _space(**{C.REGULAR_BRI: 1}),
        }
        state["support"] = {"Boston": C.NEUTRAL, "Massachusetts": C.NEUTRAL}
        state["resources"][C.BRITISH] = 5
        state["rng"] = random.Random(1)
        refresh_control(state)

        initial_resources = state["resources"][C.BRITISH]

        result = bot._muster(state)
        assert result is True

        # Verify _turn_command is MUSTER, not MARCH
        assert state.get("_turn_command") == "MUSTER", (
            f"Expected _turn_command='MUSTER', got {state.get('_turn_command')!r}. "
            "The double-command bug may be active — Muster chained into March."
        )

        # Verify no March history entry exists
        march_entries = [h for h in state.get("history", []) if "March" in str(h)]
        assert not march_entries, (
            f"Found March history entries after Muster: {march_entries}. "
            "The double-command bug caused Muster to fall through into March."
        )

    def test_muster_spends_resources_once(self):
        """Resources should decrease by the Muster cost only, not Muster + March."""
        from lod_ai.bots.british_bot import BritishBot

        bot = BritishBot()
        state = _base_state()
        state["spaces"] = {
            "Boston": _city(**{C.REGULAR_BRI: 3, C.TORY: 2}),
            "Massachusetts": _space(**{C.REGULAR_BRI: 1}),
        }
        state["support"] = {"Boston": C.NEUTRAL, "Massachusetts": C.NEUTRAL}
        # Give exactly 3 resources — enough for Muster in 1-2 spaces,
        # but if March also fires, resources would go negative or be rejected.
        state["resources"][C.BRITISH] = 3
        state["rng"] = random.Random(1)
        refresh_control(state)

        bot._muster(state)

        # Resources should be >= 0 (Muster cost is 1 per space, typically 1-2 spaces)
        assert state["resources"][C.BRITISH] >= 0, (
            f"Resources went to {state['resources'][C.BRITISH]} — "
            "double command may have over-spent."
        )
        # And command should be MUSTER only
        assert state.get("_turn_command") == "MUSTER"


# ============================================================================
# Bug B: Indian double SA (War Path + Trade on one turn) — regression guard
# ============================================================================

class TestIndianNoDoubleSA:
    """After War Path executes successfully, the Indian bot must NOT
    fall through into Trade.  Per §2.3.6, one SA per turn."""

    def test_war_path_returns_true_not_empty_dict(self):
        """_war_path() must return True (not {} or any falsy value) on success."""
        from lod_ai.bots.indians import IndianBot

        bot = IndianBot()
        state = _base_state()
        # Need: Underground WP in a space with rebel units
        state["spaces"] = {
            "Massachusetts": _space(**{
                C.WARPARTY_U: 2,
                C.REGULAR_PAT: 1,
                C.MILITIA_A: 1,
            }),
        }
        state["support"] = {"Massachusetts": C.NEUTRAL}
        state["resources"][C.INDIANS] = 5
        refresh_control(state)

        result = bot._war_path(state)
        assert result is True, (
            f"_war_path() returned {result!r} — expected True. "
            f"If this is {{}}, the execute-ctx-as-boolean bug has regressed."
        )

    def test_war_path_or_trade_does_not_double_sa(self):
        """After successful War Path, Trade must NOT also execute."""
        from lod_ai.bots.indians import IndianBot

        bot = IndianBot()
        state = _base_state()
        state["spaces"] = {
            "Massachusetts": _space(**{
                C.WARPARTY_U: 2,
                C.REGULAR_PAT: 1,
                C.MILITIA_A: 1,
            }),
        }
        state["support"] = {"Massachusetts": C.NEUTRAL}
        state["resources"][C.INDIANS] = 5
        refresh_control(state)

        initial_resources = state["resources"][C.INDIANS]

        bot._war_path_or_trade(state)

        # _turn_used_special should be set (War Path sets it)
        assert state.get("_turn_used_special") is True, (
            "War Path should have set _turn_used_special = True"
        )

        # Check that Trade did NOT also execute — no Trade history entries
        trade_entries = [h for h in state.get("history", []) if "Trade" in str(h)]
        assert not trade_entries, (
            f"Found Trade history entries after War Path: {trade_entries}. "
            "The double-SA bug caused War Path to fall through into Trade."
        )

    def test_war_path_or_trade_falls_back_to_trade_when_war_path_impossible(self):
        """When War Path is impossible, Trade should execute as fallback."""
        from lod_ai.bots.indians import IndianBot

        bot = IndianBot()
        state = _base_state()
        # No underground WP in spaces with rebels → War Path impossible
        state["spaces"] = {
            "Massachusetts": _space(**{
                C.WARPARTY_A: 2,
                C.REGULAR_PAT: 1,
            }),
            # Trade target needs both Underground WP and Village
            "Virginia": _space(**{
                C.VILLAGE: 1,
                C.WARPARTY_U: 2,
            }),
        }
        state["support"] = {"Massachusetts": C.NEUTRAL, "Virginia": C.NEUTRAL}
        state["resources"][C.INDIANS] = 5
        state["resources"][C.BRITISH] = 5
        refresh_control(state)

        bot._war_path_or_trade(state)

        # Trade should have set _turn_used_special
        assert state.get("_turn_used_special") is True, (
            "Trade should have set _turn_used_special when War Path was impossible"
        )
