"""
Helpers for categorising pieces by rule definitions.

Cube definition: Regulars, Continentals, and Tories (Manual Glossary).
Loss values (Manual 3.6.7): Regulars/Continentals/Forts count as two
losses; everything else counts as one.
"""

from lod_ai import rules_consts as C


_CUBE_TAGS = {
    C.REGULAR_BRI,
    C.REGULAR_FRE,
    C.REGULAR_PAT,
    C.TORY,
}

_TWO_LOSS_TAGS = {
    C.REGULAR_BRI,
    C.REGULAR_FRE,
    C.REGULAR_PAT,
    C.FORT_BRI,
    C.FORT_PAT,
}


def is_cube(tag: str) -> bool:
    """Return True if *tag* is a cube (Regular, Continental, or Tory)."""

    return tag in _CUBE_TAGS


def loss_value(tag: str) -> int:
    """Return the loss value for *tag* per Manual 3.6.7."""

    return 2 if tag in _TWO_LOSS_TAGS else 1
