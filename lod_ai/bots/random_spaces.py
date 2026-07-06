# lod_ai/bots/random_spaces.py
"""
Random Spaces table (Rule 8.2).

The table is indexed as RANDOM_SPACES_TABLE[row][col] where
    row = 0-5   → result of 1D6 − 1
    col = 0-2   → result of 1D3 − 1
Entries containing “A / B” represent two candidate spaces for that cell
(choose the top / higher-Population space first per §8.2).

§8.2 is a TIE-BREAKER only: it applies when several candidate spaces have
EQUAL priority for a Non-player Command, Special Activity, or Event (§8.1,
§8.2). Substantive priorities — e.g. §8.3.6 for Support/Opposition shifts,
§8.3.5 piece-maximisation — must be applied by the caller first.

All selection here uses the seeded ``state["rng"]`` so games are
reproducible from the scenario seed and survive the save/load RNG
round-trip enforced by the invariant gate.
"""

import random as _global_random

from lod_ai.map import adjacency as map_adj

RANDOM_SPACES_TABLE = [
    # 1D3 = 1                     2                                3
    ["Quebec City",               "Northwest / Maryland-Delaware", "North Carolina"],
    ["Quebec / New York",         "Philadelphia",                  "Savannah"],
    ["New Hampshire",             "Pennsylvania",                  "Florida / South Carolina"],
    ["Connecticut_Rhode_Island",  "Norfolk",                       "Georgia"],
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


def _walk_from(start_row: int, start_col: int):
    """Yield table entries following the §8.2 arrows: down the starting
    column from the rolled box, from the bottom of one column to the TOP of
    the next, and from Massachusetts (row 6, col 3) back to Quebec City
    (row 1, col 1) — i.e. one column-major cycle over all 18 boxes."""
    start = (start_col - 1) * 6 + (start_row - 1)
    for i in range(18):
        idx = (start + i) % 18
        col, row = divmod(idx, 6)
        yield RANDOM_SPACES_TABLE[row][col]


_TABLE_INDEX: dict = {}
for _c in range(3):
    for _r in range(6):
        for _sid in _label_to_ids(RANDOM_SPACES_TABLE[_r][_c]):
            _TABLE_INDEX.setdefault(_sid, _c * 6 + _r)


def table_position(space_id: str):
    """Column-major table position of *space_id* (None if off-table)."""
    return _TABLE_INDEX.get(space_id)


def choose_random_space(candidates, rng=None):
    """
    Select a random space from *candidates* using the Random Spaces table
    (Rule 8.2). Rolls 1D3 for the starting column and 1D6 for the starting
    row, then follows the arrows until a candidate space is found (two-space
    boxes resolve top space first). Returns None if no candidate appears in
    the table.

    Q22 (Eric's ruling, July 2026 — Playbook Examples 2/3 convention):
    with EXACTLY two candidates, "the player rolls a D6 instead of using
    the Random Spaces table" — 1-3 selects the candidate that appears
    EARLIER in the table (column-major), 4-6 the later one.

    Pass the seeded ``state["rng"]`` as *rng*; the module-level fallback
    exists only for ad-hoc interactive use and is NOT reproducible.
    """
    if not candidates:
        return None
    if rng is None:
        rng = _global_random
    remaining = set(candidates)
    if len(remaining) == 1:
        return next(iter(remaining))
    if len(remaining) == 2:
        a, b = sorted(remaining,
                      key=lambda s: (_TABLE_INDEX.get(s, 99), s))
        roll = _roll_d6(rng)
        return a if roll <= 3 else b
    start_col = _roll_d3(rng)  # 1-3
    start_row = _roll_d6(rng)  # 1-6
    for entry in _walk_from(start_row, start_col):
        for space_id in _label_to_ids(entry):
            if space_id in remaining:
                return space_id
    return None


def pick_by_priority(state, scored, count=None):
    """Q22 engine-wide tie resolution (Eric's ruling, July 2026).

    *scored* is an iterable of (key, space_id) where *key* contains the
    instruction's substantive priorities ONLY (no random component).
    Returns up to *count* space_ids (all, if None): keys ascending;
    EQUAL-key groups are resolved by the Random Spaces procedure,
    re-rolling for each additional pick within a group.
    """
    rng = state.get("rng") if isinstance(state, dict) else None
    groups: dict = {}
    order: list = []
    for key, sid in scored:
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(sid)
    order.sort()
    picked: list = []
    for key in order:
        group = list(dict.fromkeys(groups[key]))
        while group and (count is None or len(picked) < count):
            if len(group) == 1 or rng is None:
                choice = sorted(group)[0] if rng is None else group[0]
            else:
                choice = choose_random_space(group, rng)
                if choice is None:
                    choice = group[rng.randrange(len(group))]
            picked.append(choice)
            group.remove(choice)
        if count is not None and len(picked) >= count:
            break
    return picked


def pick_random_spaces(state, candidates, count=1):
    """
    Pick up to *count* distinct spaces from *candidates* per §8.2, re-rolling
    for each additional space (§8.2: "roll again to select another space only
    if needed"). Uses the seeded ``state["rng"]``.

    Fallbacks: without an rng (bare unit-test states) selection is sorted
    order — the same deterministic stand-in the audited free-op planners use
    (`free_op_planner._rand_choice`). Candidates that do not appear on the
    table (synthetic test spaces) are selected by seeded equal-chance roll,
    which §8.2's Play Note sanctions.
    """
    remaining = sorted(set(candidates))
    picked: list[str] = []
    rng = state.get("rng") if isinstance(state, dict) else None
    while remaining and len(picked) < count:
        if rng is None:
            choice = remaining[0]
        else:
            choice = choose_random_space(remaining, rng)
            if choice is None:
                choice = remaining[rng.randrange(len(remaining))]
        picked.append(choice)
        remaining.remove(choice)
    return picked


def iter_random_spaces(rng=None):
    """Yield an infinite stream of spaces following the 8.2 arrow rules."""
    if rng is None:
        rng = _global_random
    start_col = _roll_d3(rng)  # 1-3
    start_row = _roll_d6(rng)  # 1-6
    while True:
        for entry in _walk_from(start_row, start_col):
            for space in _label_to_ids(entry):
                yield space
