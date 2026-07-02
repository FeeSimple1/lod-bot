"""Unit tests for the §8.1.2 order helpers (`lod_ai/util/nonplayer_pieces`).

Each test cites the bullet it transcribes; see the module docstring for
the friendly-vs-enemy distinction that earlier sessions misapplied.
"""
from lod_ai import rules_consts as C
from lod_ai.util import nonplayer_pieces as NP


def _st(sp):
    return {"spaces": {"X": dict(sp)}, "available": {}, "casualties": {},
            "unavailable": {}}


# --- enemy cubes: alternate from FEWEST (Regulars if even), no sparing ---

def test_enemy_cubes_start_with_fewest():
    st = _st({C.REGULAR_BRI: 1, C.TORY: 3})
    NP.remove_enemy_cubes(st, "X", 2, NP.ROYALIST)
    # fewest = Regulars → Regular, then alternate → Tory
    assert st["casualties"] == {C.REGULAR_BRI: 1, C.TORY: 1}


def test_enemy_cubes_regulars_first_on_even():
    st = _st({C.REGULAR_BRI: 2, C.TORY: 2})
    NP.remove_enemy_cubes(st, "X", 2, NP.ROYALIST)
    assert st["casualties"] == {C.REGULAR_BRI: 1, C.TORY: 1}
    assert st["spaces"]["X"][C.REGULAR_BRI] == 1  # Regular taken first


def test_enemy_cubes_take_the_last_tory():
    """No last-cube protection on ENEMY removal."""
    st = _st({C.REGULAR_BRI: 3, C.TORY: 1})
    NP.remove_enemy_cubes(st, "X", 2, NP.ROYALIST)
    assert st["casualties"] == {C.TORY: 1, C.REGULAR_BRI: 1}
    assert C.TORY not in st["spaces"]["X"]


# --- friendly cubes: alternate from MOST, spare the last other-cube ---

def test_friendly_cubes_start_with_most_and_spare_last_continental():
    st = _st({C.REGULAR_FRE: 3, C.REGULAR_PAT: 1})
    NP.remove_friendly_cubes(st, "X", 2, NP.REBELLION, to="available")
    # most = French Regulars → Regular; alternate wants Continental but it
    # is the last one and Regulars remain → spare it, take Regular again.
    assert st["available"] == {C.REGULAR_FRE: 2}
    assert st["spaces"]["X"][C.REGULAR_PAT] == 1


def test_friendly_cubes_regulars_first_on_even():
    st = _st({C.REGULAR_BRI: 2, C.TORY: 2})
    NP.remove_friendly_cubes(st, "X", 2, NP.ROYALIST, to="available")
    assert st["available"] == {C.REGULAR_BRI: 1, C.TORY: 1}


# --- full-order removals -------------------------------------------------

def test_remove_enemy_pieces_full_order():
    """Forts/Villages → Underground before Active Militia/WP → cubes."""
    st = _st({C.FORT_PAT: 1, C.MILITIA_A: 1, C.MILITIA_U: 1,
              C.REGULAR_PAT: 1})
    NP.remove_enemy_pieces(st, "X", 3, NP.REBELLION)
    assert st["casualties"] == {C.FORT_PAT: 1, C.MILITIA_U: 1,
                                C.MILITIA_A: 1}
    assert st["spaces"]["X"][C.REGULAR_PAT] == 1


def test_remove_friendly_pieces_full_order():
    """Cubes first, then Active before Underground, Forts/Villages last."""
    st = _st({C.FORT_BRI: 1, C.WARPARTY_A: 1, C.WARPARTY_U: 1,
              C.TORY: 1, C.REGULAR_BRI: 1})
    NP.remove_friendly_pieces(st, "X", 3, NP.ROYALIST, to="available")
    # cubes: even (1-1) → Regular, then Tory is last-other but no Regulars
    # remain → Tory; then Active WP.
    assert st["available"] == {C.REGULAR_BRI: 1, C.TORY: 1, C.WARPARTY_A: 1}
    assert st["spaces"]["X"].get(C.FORT_BRI) == 1
    assert st["spaces"]["X"].get(C.WARPARTY_U) == 1


# --- pools & return order -------------------------------------------------

def test_pull_to_map_unavailable_first():
    st = _st({})
    st["unavailable"] = {C.TORY: 1}
    st["available"] = {C.TORY: 5}
    NP.pull_to_map(st, C.TORY, "X", 2)
    assert st["unavailable"].get(C.TORY, 0) == 0
    assert st["available"][C.TORY] == 4
    assert st["spaces"]["X"][C.TORY] == 2


def test_return_order_blockades_forts_cubes_regulars():
    tags = [C.REGULAR_BRI, C.TORY, C.FORT_BRI, C.BLOCKADE, C.REGULAR_FRE,
            C.REGULAR_PAT, C.FORT_PAT]
    ordered = NP.return_order(tags)
    ranks = [ordered.index(C.BLOCKADE),
             max(ordered.index(C.FORT_BRI), ordered.index(C.FORT_PAT)),
             max(ordered.index(C.TORY), ordered.index(C.REGULAR_PAT)),
             min(ordered.index(C.REGULAR_BRI), ordered.index(C.REGULAR_FRE))]
    assert ranks == sorted(ranks)
