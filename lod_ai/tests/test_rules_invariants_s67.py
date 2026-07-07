"""Session 67 — ROADMAP Piece 4: rules-derived property invariants and the
bugs they exposed (piece/marker conservation, Always-Neutral spaces, WQ
control refresh, Available-pool variant handling)."""
import pytest

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.tools import invariants as I


def _violations(st, baseline=None):
    return I._rules_property_violations(st, baseline)


# ---------------------------------------------------------------------------
# The invariants themselves
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scen", ["1775", "1776", "1778"])
def test_setup_state_satisfies_all_properties(scen):
    st = build_state(scen, seed=1)
    assert _violations(st, I.capture_baseline(st)) == []


def test_census_detects_piece_loss():
    st = build_state("1776", seed=1)
    st["available"][C.MILITIA_U] -= 1  # simulate a destroyed Militia
    assert any("Patriot_Militia" in v for v in _violations(st, None))


def test_marker_conservation_detects_destruction():
    st = build_state("1776", seed=1)
    base = I.capture_baseline(st)
    st["markers"][C.PROPAGANDA]["pool"] -= 1  # debit without placement
    assert any("Propaganda" in v for v in _violations(st, base))


def test_reserve_support_is_flagged():
    st = build_state("1776", seed=1)
    st.setdefault("support", {})["Northwest"] = -1
    assert any("S1.6.2" in v for v in _violations(st, None))


def test_resource_bounds_flagged():
    st = build_state("1776", seed=1)
    st["resources"][C.BRITISH] = C.MAX_RESOURCES + 1
    assert any("S1.7" in v for v in _violations(st, None))


def test_fni_bounds_flagged():
    st = build_state("1776", seed=1)
    st["fni_level"] = C.MAX_FNI + 1
    assert any("S1.9" in v for v in _violations(st, None))


def test_stale_control_flagged():
    st = build_state("1776", seed=1)
    from lod_ai.board.control import refresh_control
    refresh_control(st)
    sid = next(iter(st["spaces"]))
    st["control"][sid] = "REBELLION" if st["control"][sid] != "REBELLION" else C.BRITISH
    assert any("control staleness" in v for v in _violations(st, None))


def test_event_audit_net_shift_flagged_and_cleared():
    st = build_state("1776", seed=1)
    from lod_ai.board.control import refresh_control
    refresh_control(st)
    # Royalist bot choosing an event that moved Support-Opposition toward
    # the Rebellion violates S8.3.3.
    st["event_choice_audit"] = [
        {"faction": C.BRITISH, "card": 42, "d_before": 3, "d_after": 1}]
    assert any("S8.3.3" in v for v in _violations(st, None))
    # A favorable shift passes, and the checked entry is drained.
    st["event_choice_audit"] = [
        {"faction": C.BRITISH, "card": 42, "d_before": 3, "d_after": 5}]
    assert _violations(st, None) == []
    assert st["event_choice_audit"] == []


def test_check_rules_properties_raises_and_dumps(tmp_path):
    st = build_state("1776", seed=1)
    st.setdefault("support", {})["Northwest"] = -1
    with pytest.raises(I.InvariantError):
        I.check_rules_properties(
            st, scenario="1776", seed=1, card_number=1,
            dump_dir=str(tmp_path))
    assert list(tmp_path.glob("invariant_rules_*.json"))


# ---------------------------------------------------------------------------
# Fixes the invariants forced
# ---------------------------------------------------------------------------

def test_place_marker_conserves_on_remark():
    from lod_ai.board.pieces import place_marker
    st = build_state("1776", seed=1)
    pool0 = st["markers"][C.PROPAGANDA]["pool"]
    assert place_marker(st, C.PROPAGANDA, "Boston", 1) == 1
    # qty>1 and re-placement never destroy markers (one per space)
    assert place_marker(st, C.PROPAGANDA, "Boston", 2) == 0
    assert st["markers"][C.PROPAGANDA]["pool"] == pool0 - 1
    assert I.marker_census(st)[C.PROPAGANDA] == C.MAX_PROPAGANDA


def test_rabble_rousing_rejects_reserves():
    from lod_ai.commands import rabble_rousing
    st = build_state("1775", seed=1)
    st["spaces"]["Northwest"][C.MILITIA_U] = 1
    st["resources"][C.PATRIOTS] = 5
    with pytest.raises(ValueError, match="S3.3.4"):
        rabble_rousing.execute(st, C.PATRIOTS, {}, ["Northwest"])


def test_rabble_rousing_conserves_propaganda_on_marked_space():
    from lod_ai.commands import rabble_rousing
    st = build_state("1775", seed=1)
    sid = "Massachusetts"
    st["spaces"][sid][C.MILITIA_U] = 2
    st["resources"][C.PATRIOTS] = 5
    st["markers"][C.PROPAGANDA]["on_map"].add(sid)
    st["markers"][C.PROPAGANDA]["pool"] -= 1
    pool0 = st["markers"][C.PROPAGANDA]["pool"]
    sup0 = st.get("support", {}).get(sid, 0)
    rabble_rousing.execute(st, C.PATRIOTS, {}, [sid])
    assert st["markers"][C.PROPAGANDA]["pool"] == pool0  # marker conserved
    assert st["support"][sid] == max(-2, sup0 - 1)       # shift still happens
    assert I.marker_census(st)[C.PROPAGANDA] == C.MAX_PROPAGANDA


def test_garrison_displacement_is_a_move_preserving_facing():
    from lod_ai.commands.garrison import _displace_rebellion
    st = build_state("1776", seed=1)
    org, tgt = "Boston", "Massachusetts"
    for t in (C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_U, C.MILITIA_A):
        st["spaces"][org][t] = 0
        st["spaces"][tgt][t] = 0
    st["spaces"][org][C.MILITIA_A] = 2
    st["spaces"][org][C.MILITIA_U] = 1
    avail0 = dict(st["available"])
    census0 = I.piece_census(st)["Patriot_Militia"]
    _displace_rebellion(org, tgt, st)
    # S3.2.2: a displacement is a map-to-map move — facing preserved,
    # Available untouched, census constant.
    assert st["spaces"][tgt][C.MILITIA_A] == 2
    assert st["spaces"][tgt][C.MILITIA_U] == 1
    assert st["spaces"][org].get(C.MILITIA_A, 0) == 0
    assert st["available"] == avail0
    assert I.piece_census(st)["Patriot_Militia"] == census0


def test_add_piece_active_variant_single_debit():
    from lod_ai.board.pieces import add_piece
    st = build_state("1776", seed=1)
    pool_u = st["available"][C.MILITIA_U]
    placed = add_piece(st, C.MILITIA_A, "Massachusetts", 1)
    assert placed == 1
    assert st["spaces"]["Massachusetts"].get(C.MILITIA_A, 0) >= 1
    assert st["available"].get(C.MILITIA_U, 0) == pool_u - 1  # exactly one
    assert I.piece_census(st)["Patriot_Militia"] == C.MAX_MILITIA


def test_battle_win_the_day_never_shifts_always_neutral():
    from lod_ai.commands.battle import _apply_shifts_to
    st = build_state("1775", seed=1)
    remaining = _apply_shifts_to(st, "Northwest", "ROYALIST", 3)
    assert remaining == 3  # overflow to adjacents per S3.6.8
    assert st.get("support", {}).get("Northwest", 0) == 0


def test_wq_reward_loyalty_skips_reserves():
    from lod_ai.util.year_end import _support_phase
    from lod_ai.board.control import refresh_control
    st = build_state("1778", seed=1)
    # Make Quebec (a Reserve) maximally attractive for RL
    st["spaces"]["Quebec"][C.REGULAR_BRI] = 3
    st["spaces"]["Quebec"][C.TORY] = 3
    st["resources"][C.BRITISH] = 10
    refresh_control(st)
    _support_phase(st)
    assert st.get("support", {}).get("Quebec", 0) == 0


def test_ineffective_event_uses_effective_population():
    """S8.3.3 x S1.9: a Support drop confined to a Blockaded City does not
    move the (effective) Support-Opposition difference, so the Event is
    not Ineffective by the net-shift clause for the British."""
    from lod_ai.bots.british_bot import BritishBot
    from lod_ai.cards import CARD_HANDLERS
    from lod_ai.board.control import refresh_control

    def _handler(state, shaded=False):
        state["support"]["Boston"] = state["support"].get("Boston", 0) - 1

    CARD_HANDLERS[9999] = _handler
    try:
        bot = BritishBot()
        card = {"id": 9999, "dual": False}

        st = build_state("1776", seed=1)
        st["support"]["Boston"] = 2
        refresh_control(st)
        st["markers"][C.BLOCKADE]["on_map"].add("Boston")   # pop counts 0
        assert bot._is_ineffective_event(card, st) is False

        st2 = build_state("1776", seed=1)
        st2["support"]["Boston"] = 2
        refresh_control(st2)                                # not blockaded
        assert bot._is_ineffective_event(card, st2) is True
    finally:
        del CARD_HANDLERS[9999]
