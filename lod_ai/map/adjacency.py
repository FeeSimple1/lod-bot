"""
lod_ai.map.adjacency
====================
Load immutable geography from JSON and answer adjacency queries.

JSON file path (relative to this module):
    lod_ai/map/data/map.json
"""

import json
from pathlib import Path
from typing import Dict, Set


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


def space_type(space_id: str) -> str | None:
    """Return 'City', 'Colony', or 'Reserve' for the given space."""
    return _TYPE.get(space_id)


def is_city(space_id: str) -> bool:
    """True if *space_id* is a City space."""
    return _TYPE.get(space_id) == "City"
