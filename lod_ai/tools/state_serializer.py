"""
State serializer for crash/bug/autosave reports.

Safely converts game state to JSON-serializable dict, handling:
- sets → sorted lists
- frozensets → sorted lists
- defaultdicts → plain dicts
- Random objects → seed string
- Any other non-serializable types → string repr
"""

from __future__ import annotations

import json
import random
import traceback
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (set, frozenset)):
        return sorted(_make_serializable(item) for item in obj)
    if isinstance(obj, defaultdict):
        return {_make_serializable(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    if isinstance(obj, random.Random):
        return f"<Random seed={getattr(obj, '_seed', 'unknown')}>"
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    # Fallback: string repr
    try:
        return repr(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"


def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert full game state to a JSON-serializable dict."""
    try:
        return _make_serializable(deepcopy(state))
    except Exception:
        # If deepcopy fails, try direct conversion
        return _make_serializable(state)


def build_crash_report(
    state: Dict[str, Any],
    exc: BaseException,
    tb_str: str,
    *,
    human_factions: set | None = None,
    seed: int | None = None,
    scenario: str | None = None,
    setup_method: str | None = None,
) -> Dict[str, Any]:
    """Build a full crash report dict."""
    return {
        "report_type": "crash",
        "timestamp": datetime.now().isoformat(),
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": tb_str,
        "current_card": _make_serializable(state.get("current_card")),
        "upcoming_card": _make_serializable(state.get("upcoming_card")),
        "card_number": len(state.get("played_cards", [])),
        "turn_number": len(state.get("history", [])),
        "eligible": _make_serializable(state.get("eligible", {})),
        "scenario": scenario or state.get("_scenario", "unknown"),
        "seed": seed if seed is not None else state.get("_seed", "unknown"),
        "setup_method": setup_method or state.get("_setup_method", "unknown"),
        "human_factions": sorted(human_factions) if human_factions else [],
        "history": _make_serializable(state.get("history", [])),
        "game_state": serialize_state(state),
    }


def build_bug_report(
    state: Dict[str, Any],
    description: str,
    *,
    human_factions: set | None = None,
    seed: int | None = None,
    scenario: str | None = None,
    setup_method: str | None = None,
    wizard_log: List[Dict] | None = None,
    sa_log: List[Dict] | None = None,
    rejection_log: List[Dict] | None = None,
) -> Dict[str, Any]:
    """Build a bug report dict."""
    history = state.get("history", [])
    recent_history = _make_serializable(history[-20:]) if len(history) > 20 else _make_serializable(history)
    report = {
        "report_type": "bug",
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "current_card": _make_serializable(state.get("current_card")),
        "upcoming_card": _make_serializable(state.get("upcoming_card")),
        "card_number": len(state.get("played_cards", [])),
        "turn_number": len(state.get("history", [])),
        "eligible": _make_serializable(state.get("eligible", {})),
        "scenario": scenario or state.get("_scenario", "unknown"),
        "seed": seed if seed is not None else state.get("_seed", "unknown"),
        "setup_method": setup_method or state.get("_setup_method", "unknown"),
        "human_factions": sorted(human_factions) if human_factions else [],
        "recent_history": recent_history,
        "game_state": serialize_state(state),
    }
    if wizard_log:
        report["wizard_log"] = _make_serializable(wizard_log)
    if sa_log:
        report["sa_log"] = _make_serializable(sa_log)
    if rejection_log:
        report["rejection_log"] = _make_serializable(rejection_log)
    return report


def build_autosave(
    state: Dict[str, Any],
    *,
    seed: int | None = None,
    scenario: str | None = None,
    setup_method: str | None = None,
    human_factions: set | None = None,
) -> Dict[str, Any]:
    """Build an autosave dict."""
    return {
        "report_type": "autosave",
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario or state.get("_scenario", "unknown"),
        "seed": seed if seed is not None else state.get("_seed", "unknown"),
        "setup_method": setup_method or state.get("_setup_method", "unknown"),
        "human_factions": sorted(human_factions) if human_factions else [],
        "card_number": len(state.get("played_cards", [])),
        "game_state": serialize_state(state),
    }


def build_game_report(
    state: Dict[str, Any],
    game_stats: Dict[str, Any],
    *,
    seed: int | None = None,
    scenario: str | None = None,
    setup_method: str | None = None,
    human_factions: set | None = None,
) -> Dict[str, Any]:
    """Build an end-of-game report dict."""
    return {
        "report_type": "game_report",
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario or state.get("_scenario", "unknown"),
        "seed": seed if seed is not None else state.get("_seed", "unknown"),
        "setup_method": setup_method or state.get("_setup_method", "unknown"),
        "human_factions": sorted(human_factions) if human_factions else [],
        "game_stats": _make_serializable(game_stats),
        "final_state": serialize_state(state),
    }


def save_report(report: Dict[str, Any], filepath: str | Path) -> str:
    """Write a report dict to a JSON file. Returns the path string."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    except Exception as exc:
        # Last resort: try writing with all values as strings
        fallback = json.dumps(report, indent=2, default=repr)
        path.write_text(fallback, encoding="utf-8")
    return str(path)
