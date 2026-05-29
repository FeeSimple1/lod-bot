"""
lod_ai.leaders
==============
Lookup helper for the location of each leader piece on the board.

Background
----------
This module used to register `pre_*` hooks for each of the 9 leader
capabilities on Reference Card #110 (Washington, Rochambeau, Lauzun,
Gage, Howe, Clinton, Brant, Cornplanter, Dragging Canoe) and exposed
`apply_leader_modifiers(state, faction, hook, ctx)` that command and
SA files were supposed to call before each rule application.

The hook system was dead code in real games:
  * `apply_leader_modifiers` iterated `state["leaders"].get(faction, [])`
    which returned [] because real game state stores leaders as
    `{leader_id: space_id}` (the scenario-JSON convention), not
    `{faction: [leader_id, ...]}` as the hooks expected.
  * Most capabilities were redundantly implemented via direct
    `leader_location()` checks in their command/SA files, which DO
    work against the real state shape.
  * Four capabilities (Clinton, Cornplanter, Gage, Rochambeau) had
    only the dead-hook path and were silently broken; Session 18
    surfaced and fixed them with direct `leader_location()` checks.

This module was therefore simplified: only the working primitive,
`leader_location()`, remains.  All command/SA leader-capability
rules now live next to the rule they affect, checked per-space via
`leader_location()`.

State shape (canonical)
-----------------------
`state["leaders"]` is a mapping from leader identifier to current
space ID, with None meaning the leader is off the map::

    {
        "LEADER_GAGE":           None,
        "LEADER_HOWE":           "New_York_City",
        "LEADER_CLINTON":        None,
        "LEADER_WASHINGTON":     "New_York",
        "LEADER_ROCHAMBEAU":     None,
        "LEADER_LAUZUN":         None,
        "LEADER_BRANT":          "New_York",
        "LEADER_CORNPLANTER":    None,
        "LEADER_DRAGGING_CANOE": None,
    }

`leader_location()` also tolerates two legacy shapes for
backwards-compatibility with older tests:

  * `state["leader_locs"][leader_id] == space_id`
  * `state["leaders"][space_id] == leader_id` (reverse mapping)
"""

from typing import Dict, Any

from lod_ai.map import adjacency as map_adj

State = Dict[str, Any]


def _leader_keys(leader_id: str) -> set[str]:
    return {leader_id}


def leader_location(state: State, leader_id: str) -> str | None:
    """Return the current space ID of *leader_id*, or None if off-map.

    Tolerates three state shapes for the leaders data, in this order
    of preference:

      1. ``state["leader_locs"][leader_id] == space_id``
      2. ``state["leaders"][leader_id] == space_id``
      3. ``state["leaders"][space_id] == leader_id`` (reverse map)

    Falls back to scanning ``state["spaces"]`` for a leader token if
    none of the above match.
    """
    valid_spaces = set(map_adj.all_space_ids())
    for key in _leader_keys(leader_id):
        loc = state.get("leader_locs", {}).get(key)
        if isinstance(loc, str) and loc in valid_spaces:
            return loc
        loc = state.get("leaders", {}).get(key)
        if isinstance(loc, str) and loc in valid_spaces:
            return loc
    leaders_dict = state.get("leaders", {})
    for key in _leader_keys(leader_id):
        for space_key, val in leaders_dict.items():
            if val == key and space_key in valid_spaces:
                return space_key
    for key in _leader_keys(leader_id):
        for sid, sp in state.get("spaces", {}).items():
            if sp.get(key, 0):
                return sid
            if sp.get("leader") == key:
                return sid
    return None
