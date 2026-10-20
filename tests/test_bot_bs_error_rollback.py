"""Fault injection: a failed bot Brilliant Stroke cannot leak partial changes.

These tests exercise controlled exceptions, not a claim that a particular
ordinary no-plan Brilliant Stroke observed in a game was an engine failure.
"""

from copy import deepcopy

import pytest

import lod_ai.engine as engine_module
from lod_ai import rules_consts as C
from lod_ai.cli_utils import UndoException
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.tools.run_diagnostics import collect_runtime_diagnostics


def _engine():
    engine = Engine(initial_state=build_state("1778", seed=21))
    engine.state["resources"][C.BRITISH] = 5
    engine.state["current_card"] = {"id": 1, "title": "Waxhaws Massacre"}
    engine.ctx["preserved"] = {"spaces": ["Boston"]}
    return engine


@pytest.mark.parametrize("failure_at", ["planner", "normalize"])
def test_bot_bs_exception_restores_state_context_and_rng_and_reports_error(monkeypatch, failure_at):
    engine = _engine()
    state_ref, ctx_ref = engine.state, engine.ctx
    before = deepcopy(engine.state)
    before_ctx = deepcopy(engine.ctx)
    rng_before = engine.state["rng"].getstate()

    class _FaultingBot:
        def _march(self, state, *, tried_muster):
            assert tried_muster is True
            assert state["_limited"] and state["bs_free"]
            assert state["_bs_leader_origin"] == "Boston"
            state["resources"][C.BRITISH] -= 1
            state["spaces"]["Boston"][C.REGULAR_BRI] = 99
            state["rng"].random()
            state["partly_applied"] = True
            engine.ctx["preserved"]["spaces"].append("Norfolk")
            engine.ctx["partial_plan"] = True
            if failure_at == "planner":
                raise RuntimeError("injected Brilliant Stroke failure")
            return True

    if failure_at == "normalize":
        def bad_normalize(state):
            raise RuntimeError("injected Brilliant Stroke failure")
        monkeypatch.setattr(engine_module, "normalize_state", bad_normalize)

    assert engine._run_bot_limcom(
        _FaultingBot(), C.BRITISH, "march", leader_origin="Boston") is False

    assert engine.state is state_ref
    assert engine.ctx is ctx_ref
    assert engine.ctx == before_ctx
    assert engine.state["rng"].getstate() == rng_before
    expected_state = {key: value for key, value in before.items()
                      if key not in ("rng", "history")}
    actual_state = {key: value for key, value in engine.state.items()
                    if key not in ("rng", "history", "_bot_error_log")}
    assert actual_state == expected_state
    assert engine.state["history"][:-1] == before["history"]
    assert "Command rolled back" in engine.state["history"][-1]["msg"]

    diagnostics = collect_runtime_diagnostics(engine.state)
    assert diagnostics["bot_error_count"] == 1
    error = diagnostics["bot_errors"][0]
    assert error["faction"] == C.BRITISH
    assert error["card_number"] == 1
    assert error["operation"] == "march"
    assert error["phase"] == "brilliant_stroke"
    assert error["leader_origin"] == "Boston"
    assert error["exception_type"] == "RuntimeError"
    assert error["exception_message"] == "injected Brilliant Stroke failure"
    assert "RuntimeError" in error["traceback_str"]


@pytest.mark.parametrize("result", [False, None, True])
def test_ordinary_planner_results_keep_existing_nonexception_behavior(result):
    engine = _engine()

    class _Bot:
        def _battle(self, state):
            state["resources"][C.BRITISH] -= 1
            return result

    assert engine._run_bot_limcom(_Bot(), C.BRITISH, "battle") is bool(result)
    assert engine.state["resources"][C.BRITISH] == 4
    assert collect_runtime_diagnostics(engine.state)["bot_error_count"] == 0
    assert not any(key in engine.state for key in
                   ("_limited", "bs_free", "_bs_leader_origin"))


def test_undo_is_propagated_without_becoming_bot_failure():
    engine = _engine()
    undo = UndoException()

    class _Bot:
        def _battle(self, state):
            raise undo

    with pytest.raises(UndoException) as caught:
        engine._run_bot_limcom(_Bot(), C.BRITISH, "battle")
    assert caught.value is undo
    assert collect_runtime_diagnostics(engine.state)["bot_error_count"] == 0


def test_missing_planner_is_a_normal_false_result():
    engine = _engine()
    assert engine._run_bot_limcom(object(), C.BRITISH, "march") is False
    assert engine.state["resources"][C.BRITISH] == 5
    assert collect_runtime_diagnostics(engine.state)["bot_error_count"] == 0
