"""
lod_ai.save_game
=================
Save and load game state to/from JSON files.
"""

from __future__ import annotations

import json
import os
import random
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict


SAVE_DIR = "saves"


def _ensure_save_dir() -> None:
    os.makedirs(SAVE_DIR, exist_ok=True)


def _convert_sets(obj: Any) -> Any:
    """Recursively convert sets to sorted lists for JSON serialization."""
    if isinstance(obj, set):
        try:
            return sorted(obj)
        except TypeError:
            return list(obj)
    if isinstance(obj, frozenset):
        try:
            return sorted(obj)
        except TypeError:
            return list(obj)
    if isinstance(obj, dict):
        return {k: _convert_sets(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_sets(v) for v in obj]
    return obj


def _serialize_state(state: Dict[str, Any], human_factions: set) -> dict:
    """Convert game state to a JSON-serializable dict."""
    data = deepcopy(state)

    # Winter Quarters handlers schedule a Python callable for Reset.  Store
    # its authoritative card identity, not repr(function), which reloads as
    # an inert string and silently drops the card's effect.
    winter_event = data.pop("winter_card_event", None)
    if winter_event is not None:
        from lod_ai.rules_consts import WINTER_QUARTERS_CARDS
        card_id = (data.get("current_card") or {}).get("id")
        if not callable(winter_event) or card_id not in WINTER_QUARTERS_CARDS:
            raise ValueError("Cannot save an unidentified Winter Quarters effect.")
        data["_winter_card_event_id"] = card_id

    # Handle random.Random -> save its internal state
    rng = data.pop("rng", None)
    if rng and isinstance(rng, random.Random):
        rng_state = rng.getstate()
        # getstate() returns (version, tuple_of_625_ints, gauss_next)
        data["_rng_state"] = (rng_state[0], list(rng_state[1]), rng_state[2])

    # Convert all sets to sorted lists
    data = _convert_sets(data)

    # Save metadata
    data["_save_meta"] = {
        "human_factions": sorted(human_factions),
        "save_time": datetime.now().isoformat(),
        "version": 1,
    }

    return data


def _deserialize_state(data: dict) -> tuple[dict, set]:
    """Convert loaded JSON data back to a live game state.

    Returns (state, human_factions).
    """
    # Extract metadata
    meta = data.pop("_save_meta", {})
    human_factions = set(meta.get("human_factions", []))

    # Restore random.Random
    rng_state_raw = data.pop("_rng_state", None)
    if rng_state_raw:
        rng = random.Random()
        restored = (rng_state_raw[0], tuple(rng_state_raw[1]), rng_state_raw[2])
        rng.setstate(restored)
        data["rng"] = rng
    else:
        data["rng"] = random.Random()

    # Restore marker on_map fields (Q23: Propaganda/Raid are dicts of
    # per-space counts and survive JSON natively; legacy list saves
    # become count-1 dicts.  Blockade stays a set.)
    markers = data.get("markers", {})
    from lod_ai.rules_consts import PROPAGANDA as _PROP, RAID as _RAID
    for tag in markers:
        entry = markers[tag]
        om = entry.get("on_map")
        if tag in (_PROP, _RAID):
            if isinstance(om, list):
                entry["on_map"] = {sid: 1 for sid in om}   # legacy save
            elif isinstance(om, dict):
                entry["on_map"] = {sid: int(cnt) for sid, cnt in om.items()}
        elif isinstance(om, list):
            entry["on_map"] = set(om)

    # Restore sets for eligibility tracking fields
    for key in ("eligible_next", "ineligible_next", "remain_eligible",
                "ineligible_through_next"):
        if key in data and isinstance(data[key], list):
            data[key] = set(data[key])

    winter_card_id = data.pop("_winter_card_event_id", None)
    if winter_card_id is None and isinstance(data.get("winter_card_event"), str):
        # Older saves wrote repr(callback).  Its current-card identity is
        # sufficient to recover the queued effect without trusting repr.
        from lod_ai.rules_consts import WINTER_QUARTERS_CARDS
        current_id = (data.get("current_card") or {}).get("id")
        if current_id in WINTER_QUARTERS_CARDS:
            winter_card_id = current_id
    if winter_card_id is not None:
        from lod_ai.cards import CARD_HANDLERS
        from lod_ai.rules_consts import WINTER_QUARTERS_CARDS
        if winter_card_id not in WINTER_QUARTERS_CARDS:
            raise ValueError("Save contains an unknown Winter Quarters effect.")
        pending: Dict[str, Any] = {}
        CARD_HANDLERS[winter_card_id](pending, False)
        data["winter_card_event"] = pending["winter_card_event"]

    return data, human_factions


def save_game(state: Dict[str, Any], human_factions: set,
              filename: str | None = None) -> str:
    """Save resumable game data to JSON and return the filepath.

    Interactive callers must pass ``engine.state_for_save()`` so a save
    inside a preview or unfinished phase contains its committed boundary,
    rather than a partial operation that needs an unavailable call stack.
    ``_card_progress`` and ``_resume_boundary`` persist with the rest of the
    state; the former retains completed turns and the latter explains any
    unfinished operation that must restart.
    """
    _ensure_save_dir()

    if not filename:
        seed = state.get("seed", state.get("_seed", 0))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lod_save_{seed}_{timestamp}.json"

    if not filename.endswith(".json"):
        filename += ".json"

    filepath = os.path.join(SAVE_DIR, filename)
    data = _serialize_state(state, human_factions)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

    return filepath


def load_game(filepath: str) -> tuple[dict, set]:
    """Load a game from a JSON file.

    Returns (state, human_factions).
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    return _deserialize_state(data)


def list_saves() -> list[dict]:
    """Return a list of available save files with metadata."""
    _ensure_save_dir()
    saves = []
    for fname in sorted(os.listdir(SAVE_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(SAVE_DIR, fname)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            meta = data.get("_save_meta", {})
            saves.append({
                "filename": fname,
                "filepath": filepath,
                "save_time": meta.get("save_time", "?"),
                "human_factions": meta.get("human_factions", []),
                "seed": data.get("seed", data.get("_seed", "?")),
                "scenario": data.get("scenario", data.get("_scenario", "?")),
            })
        except Exception:
            continue
    return saves
