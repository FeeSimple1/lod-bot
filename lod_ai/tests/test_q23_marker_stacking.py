"""Q23 (Eric's ruling, July 10 2026): Propaganda/Raid markers STACK.

on_map is a {space_id: count} dict for these tags; the global pool of 12
is the only cap.  Pinned here: stacking placement paths (Raid command
re-raid, cards' qty=2 placements), §6.4.1/6.4.2 PER-MARKER removal
pricing (each stacked marker costs 1 Resource before any shift), the
Muster Reward-Loyalty cost, WQ reset returning full stacks, and
save/load round-tripping counts.  Blockades keep the Q21 set model.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.board.pieces import place_marker, remove_piece, marker_count
from lod_ai.tools import invariants as I


def _census_ok(st):
    cen = I.marker_census(st)
    assert cen[C.PROPAGANDA] == C.MAX_PROPAGANDA
    assert cen[C.RAID] == C.MAX_RAID


def test_raid_command_stacks_on_reraid():
    """§3.4.4 + Q23: re-Raiding a marked Province adds another marker."""
    from lod_ai.commands import raid as raid_cmd
    st = build_state("1775", seed=2)
    prov = "North_Carolina"
    st["spaces"][prov][C.WARPARTY_U] = 2
    st["support"][prov] = -1          # Raid requires Opposition (§3.4.4)
    st["resources"][C.INDIANS] = 3    # Raid cost
    st["markers"][C.RAID]["on_map"][prov] = 1
    st["markers"][C.RAID]["pool"] -= 1
    pool0 = st["markers"][C.RAID]["pool"]
    raid_cmd.execute(st, C.INDIANS, {}, [prov])
    assert st["markers"][C.RAID]["on_map"][prov] == 2
    assert st["markers"][C.RAID]["pool"] == pool0 - 1
    _census_ok(st)


def test_remove_piece_takes_stacked_markers_one_per_call():
    st = build_state("1776", seed=3)
    place_marker(st, C.RAID, "Virginia", 3)
    assert marker_count(st, C.RAID, "Virginia") == 3
    assert remove_piece(st, C.RAID, "Virginia", 1, to="available") == 1
    assert marker_count(st, C.RAID, "Virginia") == 2
    assert remove_piece(st, C.RAID, "Virginia", 5, to="available") == 2
    assert marker_count(st, C.RAID, "Virginia") == 0
    assert "Virginia" not in st["markers"][C.RAID]["on_map"]
    _census_ok(st)


def _rl_state():
    """A 1776 state where Virginia qualifies for Reward Loyalty."""
    st = build_state("1776", seed=4)
    sid = "Virginia"
    sp = st["spaces"][sid]
    sp[C.REGULAR_BRI] = sp.get(C.REGULAR_BRI, 0) + 3
    sp[C.TORY] = sp.get(C.TORY, 0) + 2
    for tag in (C.REGULAR_PAT, C.REGULAR_FRE, C.MILITIA_A, C.MILITIA_U,
                C.FORT_PAT):
        sp.pop(tag, None)
    st["support"][sid] = 0
    # Make every OTHER shiftable space Active Support so Virginia is the
    # only Reward-Loyalty candidate (the RL order prefers fewest-marker
    # spaces, which would otherwise drain the purse first).
    from lod_ai.map import adjacency as _madj
    for other in st["spaces"]:
        if other != sid and _madj.space_type(other) not in ("Reserve", "Special"):
            st["support"][other] = 2
    from lod_ai.board.control import refresh_control
    refresh_control(st)
    assert st["control"][sid] == C.BRITISH
    return st, sid


def test_wq_reward_loyalty_pays_per_stacked_marker():
    """§6.4.1 + Q23: '.every one Resource spent removes ONE Raid or
    Propaganda marker — once no Raid or Propaganda is in a space —
    shifts it.'  Two stacked Raid + one Propaganda cost 3 before the
    first shift."""
    from lod_ai.util.year_end import _support_phase
    st, sid = _rl_state()
    place_marker(st, C.RAID, sid, 2)
    place_marker(st, C.PROPAGANDA, sid, 1)
    # Purse: exactly markers (3) + one shift (1).  Zero out other
    # factions so only the British act.
    st["resources"] = {C.BRITISH: 4, C.PATRIOTS: 0, C.FRENCH: 0,
                       C.INDIANS: 0}
    _support_phase(st)
    assert marker_count(st, C.RAID, sid) == 0
    assert marker_count(st, C.PROPAGANDA, sid) == 0
    assert st["support"][sid] == 1, "3 paid for markers leaves 1 shift"
    assert st["resources"][C.BRITISH] == 0
    _census_ok(st)


def test_wq_reward_loyalty_skips_space_it_cannot_clear_and_shift():
    """§8.4.5: 'Do not Reward Loyalty in a space if only Raid and/or
    Propaganda markers would be removed' — with 3 stacked markers and a
    purse of 3, the space is skipped entirely."""
    from lod_ai.util.year_end import _support_phase
    st, sid = _rl_state()
    place_marker(st, C.RAID, sid, 2)
    place_marker(st, C.PROPAGANDA, sid, 1)
    st["resources"] = {C.BRITISH: 3, C.PATRIOTS: 0, C.FRENCH: 0,
                       C.INDIANS: 0}
    _support_phase(st)
    assert marker_count(st, C.RAID, sid) == 2, "space must be skipped"
    assert st["support"][sid] == 0
    assert st["resources"][C.BRITISH] == 3
    _census_ok(st)


def test_muster_reward_loyalty_costs_every_stacked_marker():
    from lod_ai.commands.muster import _reward_loyalty
    st, sid = _rl_state()
    place_marker(st, C.PROPAGANDA, sid, 2)
    st["resources"][C.BRITISH] = 10
    _reward_loyalty(st, st["spaces"][sid], sid, 1)
    assert marker_count(st, C.PROPAGANDA, sid) == 0
    # cost = 2 markers + 1 shift
    assert st["resources"][C.BRITISH] == 7
    assert st["support"][sid] == 1
    _census_ok(st)


def test_wq_reset_returns_full_stacks_to_pool():
    from lod_ai.util.year_end import _reset_phase
    st = build_state("1775", seed=5)
    place_marker(st, C.RAID, "Georgia", 3)
    place_marker(st, C.PROPAGANDA, "Virginia", 2)
    _reset_phase(st)
    assert st["markers"][C.RAID]["on_map"] == {}
    assert st["markers"][C.PROPAGANDA]["on_map"] == {}
    assert st["markers"][C.RAID]["pool"] == C.MAX_RAID
    assert st["markers"][C.PROPAGANDA]["pool"] == C.MAX_PROPAGANDA


def test_save_load_round_trips_counts():
    from lod_ai.save_game import save_game, load_game
    st = build_state("1778", seed=6)
    place_marker(st, C.PROPAGANDA, "Virginia", 2)
    place_marker(st, C.RAID, "Georgia", 3)
    path = save_game(st, {"BRITISH"}, filename="q23_roundtrip_test")
    loaded, _hf = load_game(path)
    assert loaded["markers"][C.PROPAGANDA]["on_map"]["Virginia"] == 2
    assert loaded["markers"][C.RAID]["on_map"]["Georgia"] == 3
    _census_ok(loaded)


def test_normalize_preserves_counts_and_coerces_legacy_sets():
    from lod_ai.util.normalize_state import normalize_state
    st = build_state("1775", seed=7)
    st["markers"][C.PROPAGANDA]["on_map"] = {"Virginia": 2}
    st["markers"][C.PROPAGANDA]["pool"] = C.MAX_PROPAGANDA - 2
    st["markers"][C.RAID] = {"pool": C.MAX_RAID - 1,
                             "on_map": {"Georgia"}}   # legacy set form
    normalize_state(st)
    assert st["markers"][C.PROPAGANDA]["on_map"] == {"Virginia": 2}
    assert st["markers"][C.RAID]["on_map"] == {"Georgia": 1}
    assert isinstance(st["markers"][C.BLOCKADE]["on_map"], set)
