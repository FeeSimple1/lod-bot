# lod_ai/bots/random_spaces.py
"""
Random Spaces table (Rule 8.2).

The table is indexed as RANDOM_SPACES_TABLE[row][col] where
    row = 0-5   → result of 1D6 − 1
    col = 0-2   → result of 1D3 − 1
Entries containing “A / B” represent two candidate spaces for that cell.
"""

import random

from lod_ai.map import adjacency as map_adj

RANDOM_SPACES_TABLE = [
    # 1D3 = 1                     2                               3
    ["Quebec City",               "Northwest / Maryland-Delaware", "North Carolina"],
    ["Quebec / New York",         "Philadelphia",                  "Savannah"],
    ["New Hampshire",             "Pennsylvania",                  "Florida / South Carolina"],
    ["Connecticut_Rhode_Island",  "Rhode_Island",                  "Norfolk"],
    ["New York City",             "Southwest / Virginia",          "Boston"],
    ["New Jersey",                "Charles Town",                  "Massachusetts"],
]


def _roll_d3(rng) -> int:
    return rng.randint(1, 3)


def _roll_d6(rng) -> int:
    return rng.randint(1, 6)


def _normalize_label(label: str) -> str:
    return label.replace("_", " ").replace("-", " ").replace("/", " ").lower().strip()


_SPACE_LOOKUP = {_normalize_label(sid): sid for sid in map_adj.all_space_ids()}
_SPACE_ALIASES = {
    "connecticut": "Connecticut_Rhode_Island",
    "rhode island": "Connecticut_Rhode_Island",
    "connecticut rhode island": "Connecticut_Rhode_Island",
}


def _label_to_ids(label: str) -> list[str]:
    ids: list[str] = []
    for token in label.split("/"):
        name = token.strip()
        key = _normalize_label(name)
        alias = _SPACE_ALIASES.get(key)
        if alias:
            ids.append(alias)
            continue
        match = _SPACE_LOOKUP.get(key)
        if match:
            ids.append(match)
            continue
        ids.append(name.replace(" ", "_"))
    return ids


def choose_random_space(candidates):
    """
    Select a random space from *candidates* using the Random Spaces table (Rule 8.2).
    Rolls 1D3 for the starting column and 1D6 for the starting row, then follows the
    arrow order (down the column, then wrap to the next column) until a candidate
    space is found. Returns None if no candidate appears in the table.
    """
    if not candidates:
        return None
    rng = random
    remaining = set(candidates)
    start_col = _roll_d3(rng)  # 1-3
    start_row = _roll_d6(rng)  # 1-6
    order_rows = list(range(start_row, 7)) + list(range(1, start_row))
    order_cols = list(range(start_col, 4)) + list(range(1, start_col))
    for c in order_cols:
        for r in order_rows:
            entry = RANDOM_SPACES_TABLE[r - 1][c - 1]
            for space_id in _label_to_ids(entry):
                if space_id in remaining:
                    return space_id
    return None


def iter_random_spaces():
    """Yield an infinite stream of spaces following the 8.2 arrow rules."""
    rng = random
    start_col = _roll_d3(rng)  # 1-3
    start_row = _roll_d6(rng)  # 1-6
    order_rows = list(range(start_row, 7)) + list(range(1, start_row))
    order_cols = list(range(start_col, 4)) + list(range(1, start_col))
    while True:
        for c in order_cols:
            for r in order_rows:
                for space in _label_to_ids(RANDOM_SPACES_TABLE[r - 1][c - 1]):
                    yield space
