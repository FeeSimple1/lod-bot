"""Session 67 — ROADMAP Piece 5 (decision coverage): the collector, and
targeted tests for every never-fired branch the 300-game matrix exposed
(dead state-space "type" filters in early_war, card 68's missing
places_patriot_fort flag, French Preparer invisible to the engine's
S2.3.4/S2.3.5 slot matrix, and handler proofs for the precondition-rare
sides 17u/36s)."""
import copy
import io
import contextlib

import pytest

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.cards import CARD_HANDLERS


def _run(cid, state, shaded, fac):
    state["active"] = fac
    with contextlib.redirect_stdout(io.StringIO()):
        CARD_HANDLERS[cid](state, shaded=shaded)


# ---------------------------------------------------------------------------
# The dead "type"-filter class (cards 2/6/10/32/41/46/84)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cid,shaded,fac", [
    (2, True, C.PATRIOTS),    # shift 2 Cities toward Opposition + Propaganda
    (10, False, C.BRITISH),   # shift 2 Cities toward Support
    (32, False, C.BRITISH),   # place pieces in a Colony
    (41, False, C.BRITISH),   # shift 2 Colonies toward Support
    (46, True, C.PATRIOTS),   # shift 2 Cities toward Passive Opposition
])
def test_type_filter_cards_have_effect_on_real_states(cid, shaded, fac):
    """Real states never carry a per-space "type" key, so these handlers
    filtered every candidate out and the cards never executed (Piece 5
    coverage matrix; same class as the S48 pick_cities collateral)."""
    st = build_state("1775", seed=3)
    before = copy.deepcopy(st)
    _run(cid, st, shaded, fac)
    for k in ("history", "rng", "rng_log"):
        st.pop(k, None), before.pop(k, None)
    assert st != before, f"card {cid} no-oped on a real state"


def test_card2_shaded_shifts_real_cities():
    st = build_state("1775", seed=3)
    _run(2, st, True, C.PATRIOTS)
    from lod_ai.map.adjacency import space_type
    shifted = [sid for sid, lvl in st["support"].items()
               if lvl < build_state("1775", seed=3)["support"].get(sid, 0)]
    assert shifted, "no city shifted toward Opposition"
    assert all(space_type(s) == "City" for s in shifted)


# ---------------------------------------------------------------------------
# Card 68 — only PATRIOTS can choose it (B/F/I Sword); friendly Fort flag
# ---------------------------------------------------------------------------

def test_card68_patriots_invade_quebec():
    st = build_state("1775", seed=3)
    st["spaces"]["Massachusetts"][C.REGULAR_PAT] = 4
    st["available"][C.FORT_PAT] = st["available"].get(C.FORT_PAT, 0) or 1
    _run(68, st, False, C.PATRIOTS)
    q = st["spaces"]["Quebec"]
    assert q.get(C.REGULAR_PAT, 0) >= 1, "no Continentals relocated to Quebec"
    assert q.get(C.FORT_PAT, 0) == 1, "friendly (Patriot) Fort not placed"


def test_card68_flag_exposes_benefit_to_patriot_bullets():
    from lod_ai.bots.event_eval import CARD_EFFECTS
    assert CARD_EFFECTS[68]["unshaded"]["places_patriot_fort"] is True


def test_card17_unshaded_removes_fort_from_reserve():
    """Precondition-rare side (fort-in-Reserve arrives via card 68/72):
    prove the handler does the printed thing when it holds."""
    st = build_state("1775", seed=3)
    st["spaces"]["Quebec"][C.FORT_PAT] = 1
    _run(17, st, False, C.INDIANS)
    assert st["spaces"]["Quebec"].get(C.FORT_PAT, 0) == 0


def test_card36_shaded_removes_british_regulars_from_west_indies():
    st = build_state("1778", seed=1)
    st["spaces"][C.WEST_INDIES_ID][C.REGULAR_BRI] = 5
    avail0 = st["available"].get(C.REGULAR_BRI, 0)
    _run(36, st, True, C.FRENCH)
    assert st["spaces"][C.WEST_INDIES_ID].get(C.REGULAR_BRI, 0) == 1
    assert st["available"].get(C.REGULAR_BRI, 0) == avail0 + 4


# ---------------------------------------------------------------------------
# French Preparer la Guerre — engine-visible SA usage (S2.3.4/S2.3.5)
# ---------------------------------------------------------------------------

def test_preparer_sets_used_special():
    from lod_ai.bots.french import _preparer_la_guerre
    st = build_state("1775", seed=3)
    st["unavailable"][C.REGULAR_FRE] = 3
    st["_turn_used_special"] = False
    assert _preparer_la_guerre(st, post_treaty=False) is True
    assert st["_turn_used_special"] is True
    assert st.get("_turn_special_type") == "PREPARER"


def test_preparer_noop_does_not_set_used_special():
    from lod_ai.bots.french import _preparer_la_guerre
    st = build_state("1775", seed=3)
    st["unavailable"] = {}
    st["resources"][C.FRENCH] = 5   # blocks the +2 fallback
    st["_turn_used_special"] = False
    assert _preparer_la_guerre(st, post_treaty=False) is False
    assert st["_turn_used_special"] is False


# ---------------------------------------------------------------------------
# The collector itself
# ---------------------------------------------------------------------------

def test_collector_counts_turn_log(tmp_path):
    from lod_ai.tools.coverage import Collector
    c = Collector()
    state = {"_card_turn_log": [
        {"faction": "BRITISH", "action": "event",
         "event_card_id": 7, "event_side": "unshaded"},
        {"faction": "FRENCH", "action": "command", "command_type": "MUSTER",
         "used_special": True, "special_type": "PREPARER"},
        {"faction": "PATRIOTS", "action": "pass", "pass_reason": "resource_gate"},
    ]}
    c.consume_turn_log(state)
    c.finish_game()
    assert c.events[(7, "unshaded", "BRITISH")] == 1
    assert c.commands[("FRENCH", "MUSTER")] == 1
    assert c.sas[("FRENCH", "PREPARER")] == 1
    assert c.passes[("PATRIOTS", "resource_gate")] == 1
    # round-trips through json
    p = tmp_path / "cov.json"
    c.save(p)
    c2 = Collector.load(p)
    assert c2.events == c.events and c2.games == 1
