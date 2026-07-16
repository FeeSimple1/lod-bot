"""C6 §1.4.1 voluntary take-own-forces-from-map (Session 76).

Manual §1.4.1: a Faction executing a Command/SA/Event to place its OWN
forces MAY pull them from the map when the type is not Available
(B/F Regulars excepted).  Manual §8 "No voluntary removal": Non-player
Factions NEVER use this option.

Before S76 place_piece auto-reclaimed from the map on EVERY pool-dry
placement — bots included — via _ensure_available.  Now gated: the
force owner must be a human seat AND the active (executing) faction;
bots simply place what the pool holds (§5.1.3 implement-what-can).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.rules_consts as C
from lod_ai.board.pieces import place_piece


def _state(humans=(), active=None):
    st = {
        "spaces": {"Virginia": {C.WARPARTY_U: 3}, "Georgia": {}},
        "available": {C.WARPARTY_U: 0},
        "unavailable": {}, "casualties": {},
        "markers": {}, "support": {}, "control": {},
        "human_factions": set(humans), "history": [],
    }
    if active:
        st["active"] = active
    return st


def test_bots_never_voluntarily_remove():
    """§8: pool empty + pieces on map -> a bot placement places ZERO,
    it does not strip its own map pieces."""
    st = _state(humans=(), active=C.INDIANS)
    placed = place_piece(st, C.WARPARTY_U, "Georgia", 2)
    assert placed == 0
    assert st["spaces"]["Virginia"][C.WARPARTY_U] == 3, (
        "bot placement must NOT reclaim from the map (Manual §8)")


def test_human_owner_may_pull_own_forces():
    """§1.4.1: a human Indian seat executing its own placement pulls
    War Parties from the map when the pool is dry."""
    st = _state(humans=(C.INDIANS,), active=C.INDIANS)
    placed = place_piece(st, C.WARPARTY_U, "Georgia", 2)
    assert placed == 2
    assert st["spaces"]["Virginia"][C.WARPARTY_U] == 1


def test_pull_scoped_to_own_placement():
    """§1.4.1 scope: 'while executing ... to place their own forces' —
    a human BRITISH executor placing Indian pieces does not exercise
    the Indians' option (Indians here are a bot)."""
    st = _state(humans=(C.BRITISH,), active=C.BRITISH)
    placed = place_piece(st, C.WARPARTY_U, "Georgia", 2)
    assert placed == 0
    assert st["spaces"]["Virginia"][C.WARPARTY_U] == 3


def test_regular_exception_untouched():
    """EXCEPTION: British/French Regulars are never map-pulled (they
    are not reclaim-eligible), even for a human seat."""
    st = _state(humans=(C.BRITISH,), active=C.BRITISH)
    st["spaces"]["Virginia"] = {C.REGULAR_BRI: 3}
    st["available"][C.REGULAR_BRI] = 0
    placed = place_piece(st, C.REGULAR_BRI, "Georgia", 2)
    assert placed == 0
    assert st["spaces"]["Virginia"][C.REGULAR_BRI] == 3
