# lod_ai/bots/random_spaces.py
"""
Random Spaces table (Rule 8.2).

RANDOM_SPACES[row][col]  where
    row = 0-5   → result of 1D6 − 1
    col = 0-2   → result of 1D3 − 1
Each cell is a list; try the names in order, then follow arrows
(continue downward in the same column, wrap to next column, and
finally from Massachusetts to Quebec City).
"""

RANDOM_SPACES = [
    # 1D3 = 1           2                       3
    [["Quebec_City"],   ["Northwest", "Maryland-Delaware"], ["North_Carolina"]],
    [["Quebec", "New_York"], ["Philadelphia"],            ["Savannah"]],
    [["New_Hampshire"], ["Pennsylvania"],                   ["Florida", "South_Carolina"]],
    [["Connecticut", "Rhode_Island"], ["Norfolk"],          ["Georgia"]],
    [["New_York_City"], ["Southwest", "Virginia"],          ["Boston"]],
    [["New_Jersey"],    ["Charles_Town"],                   ["Massachusetts"]],
]

import random


def _roll(rng, sides: int) -> int:
    return rng.randint(1, sides)


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
    col = _roll(rng, 3)  # 1-3
    row = _roll(rng, 6)  # 1-6
    start = (row, col)
    visited = 0
    while visited < 18:  # 3 columns × 6 rows
        entry = RANDOM_SPACES[row - 1][col - 1]
        for name in entry:
            if name in candidates:
                return name
        if row < 6:
            row += 1
        else:
            row = 1
            col = 1 if col == 3 else col + 1
        visited += 1
    return None


def iter_random_spaces():
    """Yield an infinite stream of spaces following the 8.2 arrow rules."""
    rng = random
    col = _roll(rng, 3)  # 1-3
    row = _roll(rng, 6)  # 1-6
    while True:
        for space in RANDOM_SPACES[row - 1][col - 1]:
            yield space
        if row < 6:
            row += 1
        else:
            row = 1
            col = 1 if col == 3 else col + 1
