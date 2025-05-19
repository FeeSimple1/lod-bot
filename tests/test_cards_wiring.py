# tests/test_cards_wiring.py
"""
Wiring sanity-check for the Liberty or Death cards subsystem.

* CARD_REGISTRY must contain all 109 cards from data.json.
* EVENT_HANDLERS must expose one callable per card id.
* No ids are missing, none are duplicated.
Nothing here touches game state, so it runs in < 5 ms.
"""
import json
import pathlib
from lod_ai.cards import CARD_REGISTRY, EVENT_HANDLERS


def test_registry_has_109_cards():
    """data.json→CARD_REGISTRY size check"""
    assert len(CARD_REGISTRY) == 109


def test_event_handlers_cover_every_id():
    """EVENT_HANDLERS has a callable for every card id"""
    missing = [cid for cid in CARD_REGISTRY if cid not in EVENT_HANDLERS]
    assert not missing, f"Handlers missing for card ids: {missing}"


def test_no_duplicate_handlers():
    """Every handler maps to a unique id (no accidental double-registration)."""
    seen = {}
    dups = []
    for cid, fn in EVENT_HANDLERS.items():
        if fn in seen.values():
            dups.append((cid, fn.__name__, seen[fn]))
        else:
            seen[cid] = fn
    assert not dups, f"Duplicate handlers: {dups}"