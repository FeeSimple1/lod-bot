"""Shared smoke-test diagnostics; a completed game may still be dirty."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from lod_ai import rules_consts as C

FACTIONS = {C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS}
ERROR_END_REASONS = {"CRASH", "INVARIANT", "INTERACTIVE_PROMPT", "TIMEOUT", "DIRTY"}
COUNT_KEYS = ("bot_error_count", "illegal_action_count", "free_op_error_count",
              "free_op_skip_count", "event_preview_error_count")


def collect_runtime_diagnostics(state: dict) -> dict[str, Any]:
    """Read authoritative error logs and legacy free-operation skip entries."""
    history = [str(entry.get("msg", "") if isinstance(entry, dict) else entry)
               for entry in state.get("history", [])]
    diagnostics = {
        "bot_errors": deepcopy(state.get("_bot_error_log") or []),
        "illegal_actions": deepcopy(state.get("_illegal_action_log") or []),
        "free_op_errors": deepcopy(state.get("_free_op_error_log") or []),
        "event_preview_errors": deepcopy(state.get("_event_preview_error_log") or []),
        # Battle-dependent adverse outcomes under Q24 are observations, not a
        # proven illegal decision. Preserve them without making them errors.
        "event_outcome_observations": deepcopy(state.get("event_outcome_observations") or []),
        "free_op_skips": [message for message in history
                          if "FREE " in message and "skipped (no valid target)" in message],
    }
    for singular, plural in (("bot_error", "bot_errors"), ("illegal_action", "illegal_actions"),
                             ("free_op_error", "free_op_errors"), ("free_op_skip", "free_op_skips"),
                             ("event_preview_error", "event_preview_errors")):
        diagnostics[f"{singular}_count"] = len(diagnostics[plural])
    diagnostics["event_outcome_observation_count"] = len(diagnostics["event_outcome_observations"])
    return diagnostics


def result_is_clean(result: dict) -> bool:
    """A zero-player smoke test passes only with a canonical, error-free win.

    Accept older saved results without a ``clean`` field, but never disregard
    an explicit dirty status or any recorded operation error.
    """
    return (result.get("end_reason") == "WINNER"
            and result.get("winner") in FACTIONS
            and not result.get("error")
            and result.get("clean") is not False
            and not any(result.get(key, 0) for key in COUNT_KEYS)
            and not any(result.get(key) for key in
                        ("bot_errors", "illegal_actions", "free_op_errors", "free_op_skips",
                         "event_preview_errors")))


def issue_summary(result: dict) -> str:
    parts = [f"{key.removesuffix('_count').replace('_', ' ')}s={result.get(key, 0)}"
             for key in COUNT_KEYS if result.get(key, 0)]
    if result.get("error"):
        parts.append(str(result["error"]).splitlines()[0])
    if result.get("end_reason") != "WINNER":
        parts.insert(0, f"end_reason={result.get('end_reason')}")
    return "; ".join(parts) or "run marked dirty"
