"""
lod_ai.util.history
===================

Lightweight, in-state history stack.

• Every mutation helper should call `push_history(state, msg)`.
• Each entry now stores:
      {"seq": 1, "msg": "Patriots Resources +3", "stamp": "2025-05-10 21:04"}
  (stamp is ISO datetime; feel free to ignore it in tests).

Undo/redo is still a stub—only the log itself is maintained.
"""

from datetime import datetime
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
# Core helpers
# --------------------------------------------------------------------------- #

def _ensure_stack(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "history" not in state:
        state["history"] = []
    return state["history"]


def push_history(state: Dict[str, Any], message: str | None = None) -> None:
    """
    Append *message* to the history list with an auto-incremented sequence
    number and a timestamp (string).  Existing code that only looks at
    ["msg"] remains unaffected.
    """
    stack = _ensure_stack(state)
    seq = stack[-1]["seq"] + 1 if stack else 1
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if message is None:                # allow call sites that pass no msg
        message = "—"
    stack.append(
        {"seq": seq, "msg": message, "stamp": stamp}
    )

def last_entry(state: Dict[str, Any]) -> str | None:
    """
    Return the most recent history **msg** (not the whole dict) or None.
    Useful in quick assertions.
    """
    stack = state.get("history", [])
    return stack[-1]["msg"] if stack else None


# --------------------------------------------------------------------------- #
# Optional convenience helpers
# --------------------------------------------------------------------------- #

def reset_history(state: Dict[str, Any]) -> None:
    """Erase the history stack (handy in test fixtures)."""
    state["history"] = []


def undo(state: Dict[str, Any]) -> None:
    """
    Remove the last history entry.
    NOTE: This still does *not* roll back game state—only the log entry.
    """
    stack = _ensure_stack(state)
    if stack:
        stack.pop()
