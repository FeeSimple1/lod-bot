"""Piece 9 lint: gameplay code must draw randomness only from the seeded
``state["rng"]`` (Q22 / determinism), never the process-global ``random``
module.  A non-seeded draw makes an outcome irreproducible and breaks the
Random Spaces tie procedure.

Sanctioned and NOT flagged:
  • ``random.Random(seed)`` — constructing the seeded rng itself
    (setup_state, save_game).  Only random-DRAW methods are banned.
  • ``lod_ai/bots/random_spaces.py`` — the seeded Random-Spaces wrapper,
    which keeps a global fallback for bare unit-test states.
The CLI seed generator (``interactive_cli``) intentionally draws a fresh
OS seed when the user picks "Random"; it is outside the gameplay tree
scanned here.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]

# Core gameplay trees + single-file modules where determinism must hold.
_DIRS = ["lod_ai/bots", "lod_ai/cards", "lod_ai/commands",
         "lod_ai/special_activities", "lod_ai/state", "lod_ai/util",
         "lod_ai/board", "lod_ai/economy", "lod_ai/map"]
_FILES = ["lod_ai/engine.py"]

# Global-random draw methods (NOT random.Random, which seeds the rng).
_DRAW = ("random", "choice", "choices", "randint", "randrange", "shuffle",
         "sample", "uniform", "gauss", "getrandbits", "betavariate",
         "triangular", "normalvariate", "randbytes", "randbits")
_PAT = re.compile(r"\brandom\.(" + "|".join(_DRAW) + r")\s*\(")

# Files permitted to touch the global module (seeded wrapper / fallback).
_ALLOW = {"lod_ai/bots/random_spaces.py"}


def _gameplay_files():
    seen = []
    for d in _DIRS:
        seen += sorted((REPO / d).rglob("*.py"))
    seen += [REPO / f for f in _FILES]
    for path in seen:
        rel = path.relative_to(REPO).as_posix()
        if rel in _ALLOW or "__pycache__" in rel:
            continue
        yield rel, path


def test_no_global_random_draw_in_gameplay():
    offenders = []
    for rel, path in _gameplay_files():
        for i, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]           # ignore comments
            if _PAT.search(code):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, (
        "Gameplay code must use state['rng'], not the global random "
        "module:\n" + "\n".join(offenders))


def test_lint_pattern_actually_matches():
    # Guard against a broken regex silently passing everything.
    assert _PAT.search("x = random.choice(cands)")
    assert _PAT.search("random.shuffle(order)")
    assert not _PAT.search("rng = random.Random(seed)")   # seeding is fine
    assert not _PAT.search("state['rng'].random()")       # seeded rng is fine
