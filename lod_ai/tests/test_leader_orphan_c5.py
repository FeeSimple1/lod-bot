"""C5 (§1.10): Leader orphan rule — a Leader in a space with no pieces
of its Faction relocates to the friendliest space, else Available."""
import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.util.normalize_state import normalize_state
from lod_ai.leaders import leader_location


def _clear(st, tags):
    for sp in st["spaces"].values():
        for t in tags:
            sp[t] = 0


def test_orphaned_leader_moves_to_most_pieces():
    st = build_state("1776", seed=1)
    _clear(st, (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
    st["spaces"]["Georgia"][C.REGULAR_BRI] = 4
    st["spaces"]["New_York_City"][C.REGULAR_BRI] = 2
    st.setdefault("leader_locs", {})["LEADER_HOWE"] = "Boston"  # empty of British
    normalize_state(st)
    assert leader_location(st, "LEADER_HOWE") == "Georgia"


def test_orphaned_leader_no_pieces_goes_available():
    st = build_state("1776", seed=1)
    _clear(st, (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
    st.setdefault("leader_locs", {})["LEADER_HOWE"] = "Boston"
    normalize_state(st)
    assert leader_location(st, "LEADER_HOWE") is None


def test_non_orphaned_leader_stays():
    st = build_state("1776", seed=1)
    _clear(st, (C.REGULAR_BRI, C.TORY, C.FORT_BRI))
    st["spaces"]["New_York_City"][C.REGULAR_BRI] = 3
    st["spaces"]["Georgia"][C.REGULAR_BRI] = 9
    st.setdefault("leader_locs", {})["LEADER_HOWE"] = "New_York_City"
    normalize_state(st)
    # Fewer pieces here than Georgia, but the leader is NOT orphaned, so
    # the §1.10 rule does not move him.
    assert leader_location(st, "LEADER_HOWE") == "New_York_City"


def test_orphan_rule_respects_faction():
    """A Patriot orphan follows Patriot pieces, not British ones."""
    st = build_state("1776", seed=1)
    _clear(st, (C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT,
                C.REGULAR_BRI, C.TORY, C.FORT_BRI))
    st["spaces"]["Virginia"][C.REGULAR_PAT] = 3
    st["spaces"]["Boston"][C.REGULAR_BRI] = 9   # British, irrelevant
    st.setdefault("leader_locs", {})["LEADER_WASHINGTON"] = "Boston"
    normalize_state(st)
    assert leader_location(st, "LEADER_WASHINGTON") == "Virginia"
