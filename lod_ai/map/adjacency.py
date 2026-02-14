"""
lod_ai.map.adjacency
====================
Load immutable geography from JSON and answer adjacency queries.

JSON file path (relative to this module):
    lod_ai/map/data/map.json
"""

import json
from collections import deque
from pathlib import Path
from typing import Dict, Iterable, List, Set


# ----------------------------------------------------------------------
# 1. Load the JSON exactly once
# ----------------------------------------------------------------------
_MAP_FILE = Path(__file__).parent / "data" / "map.json"
with _MAP_FILE.open("r", encoding="utf-8") as fh:
    _RAW_MAP: Dict = json.load(fh)                                  

# Build helpers
_ADJ: Dict[str, Set[str]] = {}
_TYPE: Dict[str, str] = {}

for space_id, info in _RAW_MAP.items():
    _TYPE[space_id] = info["type"]
    # split "A|B|C" strings into a set for quick lookup
    _ADJ[space_id] = set()
    for token in info["adj"]:
        _ADJ[space_id].update(token.split("|"))


# ----------------------------------------------------------------------
# 2. Public helpers
# ----------------------------------------------------------------------
def is_adjacent(a: str, b: str) -> bool:
    """Return True if spaces *a* and *b* share an adjacency edge."""
    return b in _ADJ.get(a, set())


def adjacent_spaces(space_id: str) -> Set[str]:
    """Return the set of spaces adjacent to *space_id*."""
    return set(_ADJ.get(space_id, set()))


def space_type(space_id: str) -> str | None:
    """Return 'City', 'Colony', or 'Reserve' for the given space."""
    return _TYPE.get(space_id)


def is_city(space_id: str) -> bool:
    """True if *space_id* is a City space."""
    return _TYPE.get(space_id) == "City"


def space_meta(space_id: str) -> Dict | None:
    """Return the raw map metadata for *space_id* or ``None`` if unknown."""
    return _RAW_MAP.get(space_id)


def all_space_ids() -> Iterable[str]:
    """Return an iterable of all valid space identifiers."""
    return _RAW_MAP.keys()


def shortest_path(start: str, goal: str) -> List[str]:
    """
    Return the shortest path (as a list of space ids) between *start* and *goal*.
    Returns an empty list if no path exists or either space is unknown.
    """
    if start == goal:
        return [start]
    if start not in _ADJ or goal not in _ADJ:
        return []

    visited = {start}
    queue: deque[tuple[str, List[str]]] = deque([(start, [start])])

    while queue:
        node, path = queue.popleft()
        for nbr in _ADJ.get(node, set()):
            if nbr in visited:
                continue
            next_path = path + [nbr]
            if nbr == goal:
                return next_path
            visited.add(nbr)
            queue.append((nbr, next_path))
    return []
