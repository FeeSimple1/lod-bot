"""Tests for _ensure_result_dict and human command action legality.

These tests verify the fix for the bug where command execute() functions
return a dict (typically {}) but _ensure_result_dict() only set
action="command" when the result was NOT a dict, causing _is_action_legal()
to reject every human Command action.
"""

import random
from copy import deepcopy

from lod_ai import rules_consts as C
from lod_ai.engine import Engine


def _minimal_state():
    """Return a minimal game state sufficient for engine operations."""
    return {
        "spaces": {
            "Boston": {C.REGULAR_BRI: 3, C.TORY: 2},
            "New_York_City": {C.REGULAR_PAT: 2, C.MILITIA_U: 1},
        },
        "resources": {C.BRITISH: 20, C.PATRIOTS: 20, C.FRENCH: 20, C.INDIANS: 20},
        "available": {
            C.REGULAR_BRI: 10, C.TORY: 10, C.REGULAR_PAT: 10,
            C.MILITIA_U: 10, C.MILITIA_A: 10, C.REGULAR_FRE: 10,
            C.WARPARTY_A: 10, C.WARPARTY_U: 10,
            C.FORT_BRI: 4, C.FORT_PAT: 4, C.VILLAGE: 10,
        },
        "unavailable": {},
        "markers": {},
        "support": {"Boston": 0, "New_York_City": 0},
        "rng": random.Random(42),
    }


class TestEnsureResultDict:
    """Tests that _ensure_result_dict always sets 'action' on dict results."""

    def test_empty_dict_gets_action_command(self):
        engine = Engine(initial_state=_minimal_state())
        result = engine._ensure_result_dict({}, engine.state)
        assert result["action"] == "command"

    def test_dict_with_no_action_gets_default(self):
        engine = Engine(initial_state=_minimal_state())
        result = engine._ensure_result_dict({"notes": "test"}, engine.state)
        assert result["action"] == "command"

    def test_dict_with_existing_action_preserved(self):
        engine = Engine(initial_state=_minimal_state())
        result = engine._ensure_result_dict({"action": "event"}, engine.state)
        assert result["action"] == "event"

    def test_non_dict_becomes_command(self):
        engine = Engine(initial_state=_minimal_state())
        result = engine._ensure_result_dict(None, engine.state)
        assert result["action"] == "command"

    def test_used_special_set_from_state(self):
        engine = Engine(initial_state=_minimal_state())
        engine.state["_turn_used_special"] = True
        result = engine._ensure_result_dict({}, engine.state)
        assert result["used_special"] is True

    def test_used_special_not_overwritten(self):
        engine = Engine(initial_state=_minimal_state())
        engine.state["_turn_used_special"] = True
        result = engine._ensure_result_dict({"used_special": False}, engine.state)
        assert result["used_special"] is False


class TestCommandActionLegality:
    """Tests that command results from execute() are accepted as legal."""

    def test_empty_dict_result_is_legal_with_affected_spaces(self):
        """Simulates what happens when a command execute() returns {}."""
        engine = Engine(initial_state=_minimal_state())
        allowed = {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        def runner(state, ctx):
            # Simulate a command that affects 1 space (like muster/rally/etc.)
            state.setdefault("_turn_affected_spaces", set()).add("Boston")
            state["_turn_command"] = "MUSTER"
            return {}  # This is what execute() returns

        result, legal, sim_state, sim_ctx = engine._simulate_action(
            C.BRITISH, {"id": 1}, allowed, runner
        )
        assert legal, f"Expected legal but got illegal: {sim_state.get('_illegal_reason')}"
        assert result["action"] == "command"

    def test_none_result_is_legal_with_affected_spaces(self):
        """Some commands may return None."""
        engine = Engine(initial_state=_minimal_state())
        allowed = {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        def runner(state, ctx):
            state.setdefault("_turn_affected_spaces", set()).add("Boston")
            state["_turn_command"] = "RALLY"
            return None

        result, legal, sim_state, sim_ctx = engine._simulate_action(
            C.PATRIOTS, {"id": 1}, allowed, runner
        )
        assert legal, f"Expected legal but got illegal: {sim_state.get('_illegal_reason')}"
        assert result["action"] == "command"

    def test_ctx_dict_result_is_legal(self):
        """Commands that return ctx (a dict, typically {}) should be legal."""
        engine = Engine(initial_state=_minimal_state())
        allowed = {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        ctx = {"some_key": "value"}

        def runner(state, _ctx):
            state.setdefault("_turn_affected_spaces", set()).add("New_York_City")
            state["_turn_command"] = "BATTLE"
            return ctx  # returning ctx dict like real execute() functions

        result, legal, sim_state, sim_ctx = engine._simulate_action(
            C.BRITISH, {"id": 1}, allowed, runner
        )
        assert legal, f"Expected legal but got illegal: {sim_state.get('_illegal_reason')}"
        assert result["action"] == "command"

    def test_event_action_preserved(self):
        """Event results should keep action='event'."""
        engine = Engine(initial_state=_minimal_state())
        allowed = {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        def runner(state, ctx):
            return {"action": "event", "used_special": False}

        result, legal, sim_state, sim_ctx = engine._simulate_action(
            C.BRITISH, {"id": 1}, allowed, runner
        )
        assert legal
        assert result["action"] == "event"

    def test_no_affected_spaces_still_illegal(self):
        """A command that affects 0 spaces should still be rejected."""
        engine = Engine(initial_state=_minimal_state())
        allowed = {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        def runner(state, ctx):
            state["_turn_command"] = "MUSTER"
            # No affected spaces added
            return {}

        result, legal, sim_state, sim_ctx = engine._simulate_action(
            C.BRITISH, {"id": 1}, allowed, runner
        )
        assert not legal
        assert sim_state.get("_illegal_reason") == "no_affected_spaces"
