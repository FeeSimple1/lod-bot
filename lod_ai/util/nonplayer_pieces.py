"""§8.1.2 Non-player piece placement / removal / movement orders.

"Unless the instruction or Event text being executed specify which pieces
to place, remove or move, once spaces involved are selected, Non-player
Factions: …" — the six bullets of §8.1.2, as shared helpers so card
handlers and bots stop hand-rolling (and mis-rolling) them.

Sides (Glossary "Enemy" mirror, §1.5.2; §8.3.5 treats ally pieces as
friendly): Royalist = British + Indians, Rebellion = Patriots + French.

The "alternating Regulars and Continentals/Tories" cube pair is
side-level: Royalist cubes are (British Regulars, Tories); Rebellion
cubes are (French Regulars, Continentals).

NOTE which bullet applies: FRIENDLY removal alternates from the MOST
numerous cube (Regulars if even) and spares the last Tory/Continental in
the space if possible; ENEMY removal targets Forts/Villages first, then
Militia/War Parties (Underground before Active), then cubes alternating
from the FEWEST (Regulars if even) with no last-cube protection.
"""
from typing import Dict, Tuple

from lod_ai.board.pieces import move_piece, remove_piece
from lod_ai.rules_consts import (
    BLOCKADE, BRITISH, FORT_BRI, FORT_PAT, FRENCH, INDIANS, MILITIA_A,
    MILITIA_U, PATRIOTS, REGULAR_BRI, REGULAR_FRE, REGULAR_PAT, TORY,
    VILLAGE, WARPARTY_A, WARPARTY_U,
)

ROYALIST = "ROYALIST"
REBELLION = "REBELLION"

#                 Forts/Villages          Militia/WP                cubes (Regulars, Continentals/Tories)
_SIDE = {
    ROYALIST:  ((FORT_BRI, VILLAGE), (WARPARTY_U, WARPARTY_A), (REGULAR_BRI, TORY)),
    REBELLION: ((FORT_PAT,),         (MILITIA_U, MILITIA_A),   (REGULAR_FRE, REGULAR_PAT)),
}


def side_of(faction: str) -> str:
    return ROYALIST if faction.upper() in (BRITISH, INDIANS) else REBELLION


def enemy_side_of(faction: str) -> str:
    return REBELLION if side_of(faction) == ROYALIST else ROYALIST


def cubes_of(side: str) -> Tuple[str, str]:
    """(Regulars, Continentals/Tories) pair for *side*."""
    return _SIDE[side][2]


def militia_wp_enemy_order(side: str) -> Tuple[str, str]:
    """§8.1.2 enemy bullet: target Underground before Active."""
    u, a = _SIDE[side][1]
    return (u, a)


def militia_wp_friendly_order(side: str) -> Tuple[str, str]:
    """§8.1.2 friendly-removal bullet: Active before Underground."""
    u, a = _SIDE[side][1]
    return (a, u)


def _alternate_cubes(state: Dict, sid: str, n: int, side: str, *,
                     start_with_most: bool, spare_last_other: bool,
                     to: str) -> int:
    reg, other = cubes_of(side)
    sp = state["spaces"].get(sid, {})
    r0, o0 = sp.get(reg, 0), sp.get(other, 0)
    if start_with_most:
        take_reg = r0 >= o0          # most; Regulars if even
    else:
        take_reg = r0 <= o0          # fewest; Regulars if even
    removed = 0
    while removed < n:
        r, o = sp.get(reg, 0), sp.get(other, 0)
        if r == 0 and o == 0:
            break
        want = reg if take_reg else other
        if spare_last_other and want == other and o == 1 and r > 0:
            want = reg               # "without removing the last Tory/Continental"
        if want == reg and r == 0:
            want = other
        elif want == other and o == 0:
            want = reg
        remove_piece(state, want, sid, 1, to=to)
        removed += 1
        take_reg = want != reg       # alternate
    return removed


def remove_enemy_cubes(state: Dict, sid: str, n: int, target_side: str,
                       *, to: str = "casualties") -> int:
    """§8.1.2 enemy bullet, cube step: alternate Regulars and
    Continentals/Tories beginning with whichever is FEWEST in the space
    (Regulars if even). No last-cube protection."""
    return _alternate_cubes(state, sid, n, target_side,
                            start_with_most=False, spare_last_other=False,
                            to=to)


def remove_friendly_cubes(state: Dict, sid: str, n: int, side: str,
                          *, to: str = "available") -> int:
    """§8.1.2 friendly-removal bullet, cube step: alternate beginning with
    whichever is MOST (Regulars if even), but if possible without removing
    the last Tory/Continental in the space."""
    return _alternate_cubes(state, sid, n, side,
                            start_with_most=True, spare_last_other=True,
                            to=to)


def remove_enemy_pieces(state: Dict, sid: str, n: int, target_side: str,
                        *, to: str = "casualties") -> int:
    """§8.1.2 enemy bullet in full: Forts and Villages, then Militia or
    War Parties (Underground before Active), then cubes (fewest-first
    alternation). Use ONLY when the card text does not name piece types."""
    removed = 0
    for tag in _SIDE[target_side][0]:
        if removed >= n:
            return removed
        removed += remove_piece(state, tag, sid, n - removed, to=to)
    for tag in militia_wp_enemy_order(target_side):
        if removed >= n:
            return removed
        removed += remove_piece(state, tag, sid, n - removed, to=to)
    if removed < n:
        removed += remove_enemy_cubes(state, sid, n - removed, target_side,
                                      to=to)
    return removed


def remove_friendly_pieces(state: Dict, sid: str, n: int, side: str,
                           *, to: str = "available") -> int:
    """§8.1.2 friendly-removal bullet in full: cubes first (most-first
    alternation, sparing the last Tory/Continental), then Active before
    Underground Militia/War Parties, and finally Forts and Villages."""
    removed = remove_friendly_cubes(state, sid, n, side, to=to)
    for tag in militia_wp_friendly_order(side):
        if removed >= n:
            return removed
        removed += remove_piece(state, tag, sid, n - removed, to=to)
    for tag in _SIDE[side][0]:
        if removed >= n:
            return removed
        removed += remove_piece(state, tag, sid, n - removed, to=to)
    return removed


def pull_to_map(state: Dict, tag: str, sid: str, n: int) -> int:
    """§8.1.2 move bullet / §8.3.4: place or move friendly pieces from out
    of Unavailable first, then from Available."""
    moved = move_piece(state, tag, "unavailable", sid, n)
    if moved < n:
        moved += move_piece(state, tag, "available", sid, n - moved)
    return moved


# §8.1.2 move bullet, return order: "Move Unavailable or Casualty pieces
# and markers to Available or the map in this order: Blockades, Forts,
# Continentals/Tories, then Regulars."
_RETURN_RANK = {BLOCKADE: 0, FORT_BRI: 1, FORT_PAT: 1,
                REGULAR_PAT: 2, TORY: 2,
                REGULAR_BRI: 3, REGULAR_FRE: 3}


def return_order(tags) -> list:
    """Sort piece tags into the §8.1.2 Unavailable/Casualties→Available
    return order."""
    return sorted(tags, key=lambda t: _RETURN_RANK.get(t, 99))
