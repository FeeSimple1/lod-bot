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
    [["Quebec City"],   ["Northwest", "Maryland-Delaware"], ["North Carolina"]],
    [["Quebec", "New York 2"], ["Philadelphia"],            ["Savannah"]],
    [["New Hampshire"], ["Pennsylvania"],                   ["Florida", "South Carolina"]],
    [["Connecticut", "Rhode Island"], ["Norfolk"],          ["Georgia"]],
    [["New York City"], ["Southwest", "Virginia"],          ["Boston"]],
    [["New Jersey"],    ["Charles Town"],                   ["Massachusetts"]],
]

import random, itertools

def iter_random_spaces():
    """Yield an infinite stream of spaces following the 8.2 arrow rules."""
    col = random.randint(0, 2)          # 1D3
    row = random.randint(0, 5)          # 1D6
    order_rows = list(range(row, 6)) + list(range(0, row))
    order_cols = [col, (col + 1) % 3, (col + 2) % 3]
    for r, c in itertools.product(order_rows, order_cols):
        for space in RANDOM_SPACES[r][c]:
            yield space
