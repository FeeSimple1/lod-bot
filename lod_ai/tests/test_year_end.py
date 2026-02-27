import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Tests for util.year_end phases
import pytest

from lod_ai.util import year_end
from lod_ai import rules_consts as C


# --------------------
# Fixtures
# --------------------

def basic_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "support": {},
        "control": {},
        "available": {},
        "markers": {
            C.RAID: {"pool": 0, "on_map": set()},
            C.PROPAGANDA: {"pool": 0, "on_map": set()},
            C.BLOCKADE: {"pool": 0, "on_map": set()},
        },
        "history": [],
        "leaders": {},
        "deck": [],
    }

def test_supply_pays_when_affordable(monkeypatch):
    state = basic_state()
    state["resources"][C.BRITISH] = 2
    state["spaces"] = {"A": {C.REGULAR_BRI: 1}}
    state["spaces"][C.WEST_INDIES_ID] = {}

    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)
    year_end._supply_phase(state)

    assert state["resources"][C.BRITISH] == 1
    assert state["spaces"]["A"][C.REGULAR_BRI] == 1

def test_supply_removes_if_cannot_pay(monkeypatch):
    state = basic_state()
    state["spaces"] = {"A": {C.REGULAR_BRI: 1}}
    # no resources, so can't pay; support already at Active Opposition so can't shift
    state["support"]["A"] = C.ACTIVE_OPPOSITION
    state["spaces"][C.WEST_INDIES_ID] = {}
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)

    year_end._supply_phase(state)

    assert C.REGULAR_BRI not in state["spaces"]["A"]

def test_resource_income_simple():
    state = basic_state()
    state["spaces"] = {
        "A": {"type": "City", "pop": 3, C.FORT_BRI: 1},
        "B": {"type": "Colony", C.FORT_PAT: 1},
        "C": {C.VILLAGE: 3},
        C.WEST_INDIES_ID: {},
    }
    state["control"] = {"A": "BRITISH", "B": "REBELLION", "C": None, C.WEST_INDIES_ID: None}
    state["markers"][C.BLOCKADE]["pool"] = 1
    year_end._resource_income(state)

    assert state["resources"][C.BRITISH] == 4
    assert state["resources"][C.PATRIOTS] == 1
    assert state["resources"][C.INDIANS] == 1
    assert state["resources"][C.FRENCH] == 2

def test_support_phase_shifts_levels():
    state = basic_state()
    state["resources"][C.BRITISH] = 1
    state["resources"][C.PATRIOTS] = 1
    state["spaces"] = {
        "CityA": {
            C.REGULAR_BRI: 1,
            C.TORY: 1,
        },
        "ColB": {
            C.MILITIA_A: 1,
        },
    }
    state["support"] = {"CityA": 0, "ColB": 0}
    state["control"] = {"CityA": "BRITISH", "ColB": "REBELLION"}

    year_end._support_phase(state)

    assert state["resources"][C.BRITISH] == 0
    assert state["resources"][C.PATRIOTS] == 0
    assert state["support"]["CityA"] == 1
    assert state["support"]["ColB"] == -1

def test_leader_redeploy_assigns_destinations():
    state = basic_state()
    state["leaders"] = {
        C.BRITISH: "LEADER_HOWE",
        C.PATRIOTS: "LEADER_WASHINGTON",
    }
    state["spaces"] = {
        "X": {C.REGULAR_BRI: 2},
        "Y": {C.MILITIA_A: 1},
    }

    year_end._leader_redeploy(state)

    assert state["leader_locs"]["LEADER_HOWE"] == "X"
    assert state["leader_locs"]["LEADER_WASHINGTON"] == "Y"

def test_reset_phase_cleans_up(monkeypatch):
    state = basic_state()
    state["spaces"] = {
        "S": {
            C.MILITIA_A: 1,
            C.WARPARTY_A: 1,
        }
    }
    state["markers"] = {
        C.RAID: {"pool": 0, "on_map": {"S"}},
        C.PROPAGANDA: {"pool": 0, "on_map": {"S"}},
    }
    state["deck"] = [{"title": "Next"}]
    state["winter_card_event"] = lambda s: s.setdefault("event", True)
    lifted = {}
    def fake_lift(s):
        lifted["done"] = True
    monkeypatch.setattr(year_end, "lift_casualties", fake_lift)

    year_end._reset_phase(state)

    sp = state["spaces"]["S"]
    assert sp.get(C.MILITIA_U) == 1 and sp.get(C.MILITIA_A, 0) == 0
    assert sp.get(C.WARPARTY_U) == 1 and sp.get(C.WARPARTY_A, 0) == 0
    assert not state["markers"][C.RAID]["on_map"]
    assert not state["markers"][C.PROPAGANDA]["on_map"]
    assert state["markers"][C.RAID]["pool"] == 1
    assert state["markers"][C.PROPAGANDA]["pool"] == 1
    assert state["eligible"][C.BRITISH]
    assert state.get("upcoming_card", {}).get("title") == "Next"
    assert state.get("event") is True
    assert lifted.get("done") is True


def test_desertion_runs_unconditionally(monkeypatch):
    """§6.6: Desertion is unconditional — runs every WQ without winter_flag."""
    state = basic_state()
    state["spaces"] = {
        "A": {"type": "Colony", C.MILITIA_U: 10, C.MILITIA_A: 0, C.REGULAR_PAT: 5},
        "B": {"type": "Colony", C.TORY: 10},
        C.WEST_INDIES_ID: {},
    }
    state["control"] = {"A": "REBELLION", "B": "BRITISH", C.WEST_INDIES_ID: None}
    state["eligible"] = {C.BRITISH: True, C.PATRIOTS: True, C.FRENCH: True, C.INDIANS: True}
    # Do NOT set winter_flag — desertion should still run
    monkeypatch.setattr(year_end, "victory_check", lambda s: False)
    monkeypatch.setattr(year_end, "return_leaders", lambda s: None)
    monkeypatch.setattr(year_end, "_supply_phase", lambda s, **kw: None)
    monkeypatch.setattr(year_end, "_resource_income", lambda s: None)
    monkeypatch.setattr(year_end, "_support_phase", lambda s: None)
    monkeypatch.setattr(year_end, "_leader_change", lambda s: None)
    monkeypatch.setattr(year_end, "_leader_redeploy", lambda s, **kw: None)
    monkeypatch.setattr(year_end, "_british_release", lambda s: None)
    monkeypatch.setattr(year_end, "_fni_drift", lambda s, **kw: None)
    monkeypatch.setattr(year_end, "_reset_phase", lambda s: None)

    year_end.resolve(state)

    # Desertion should have reduced pieces even without winter_flag
    total_militia = sum(
        sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
        for sp in state["spaces"].values()
    )
    total_tories = sum(sp.get(C.TORY, 0) for sp in state["spaces"].values())
    # 10 Militia → remove 2 (10//5), so 8 remain
    assert total_militia == 8
    # 10 Tories → remove 2 (10//5), so 8 remain
    assert total_tories == 8


def test_reset_phase_keeps_existing_upcoming(monkeypatch):
    state = basic_state()
    state["spaces"][C.WEST_INDIES_ID] = {}
    state["upcoming_card"] = {"title": "Keep"}
    state["deck"] = [{"title": "Next"}]

    monkeypatch.setattr(year_end, "lift_casualties", lambda s: None)

    year_end._reset_phase(state)

    assert state["upcoming_card"]["title"] == "Keep"
    assert state["deck"] == [{"title": "Next"}]


# ──────────────────────────────────────────────────────────────
#  British Release Date (§6.5.3)
# ──────────────────────────────────────────────────────────────

def test_british_release_moves_regulars_and_tories():
    """§6.5.3: Pop one tranche, move both Regulars and Tories from Unavailable."""
    state = basic_state()
    state["unavailable"] = {C.REGULAR_BRI: 12, C.TORY: 12}
    state["available"] = {}
    state["brit_release_schedule"] = [
        {C.REGULAR_BRI: 6, C.TORY: 6},
        {C.REGULAR_BRI: 6, C.TORY: 6},
    ]

    year_end._british_release(state)

    # First tranche should be consumed
    assert len(state["brit_release_schedule"]) == 1
    assert state["available"].get(C.REGULAR_BRI) == 6
    assert state["available"].get(C.TORY) == 6
    assert state["unavailable"].get(C.REGULAR_BRI) == 6
    assert state["unavailable"].get(C.TORY) == 6


def test_british_release_caps_at_unavailable():
    """§6.5.3: Move only those that are in Unavailable."""
    state = basic_state()
    state["unavailable"] = {C.REGULAR_BRI: 3}  # only 3, not 6
    state["available"] = {}
    state["brit_release_schedule"] = [
        {C.REGULAR_BRI: 6, C.TORY: 6},
    ]

    year_end._british_release(state)

    assert state["available"].get(C.REGULAR_BRI) == 3
    assert state["available"].get(C.TORY, 0) == 0  # no Tories in Unavailable
    assert state["brit_release_schedule"] == []


def test_british_release_noop_when_empty_schedule():
    """No schedule → no action, no crash."""
    state = basic_state()
    state["brit_release_schedule"] = []
    state["unavailable"] = {C.REGULAR_BRI: 6}

    year_end._british_release(state)

    # Nothing should have moved
    assert state["unavailable"].get(C.REGULAR_BRI) == 6


def test_british_release_two_rounds():
    """Two consecutive calls consume both tranches in order."""
    state = basic_state()
    state["unavailable"] = {C.REGULAR_BRI: 12, C.TORY: 12}
    state["available"] = {}
    state["brit_release_schedule"] = [
        {C.REGULAR_BRI: 6, C.TORY: 6},
        {C.REGULAR_BRI: 6, C.TORY: 6},
    ]

    year_end._british_release(state)
    year_end._british_release(state)

    assert state["brit_release_schedule"] == []
    assert state["available"].get(C.REGULAR_BRI) == 12
    assert state["available"].get(C.TORY) == 12
    assert state["unavailable"].get(C.REGULAR_BRI, 0) == 0
    assert state["unavailable"].get(C.TORY, 0) == 0


# ──────────────────────────────────────────────────────────────
#  FNI drift with bot Blockade rearrangement (§8.6.9)
# ──────────────────────────────────────────────────────────────

class FakeFrenchBot:
    """Stub French bot for year-end tests."""
    faction = C.FRENCH

    def ops_supply_priority(self, state):
        return []

    def ops_redeploy_leader(self, state):
        return None

    def ops_loyalist_desertion_priority(self, state):
        return []

    def ops_bs_trigger(self, state):
        return state.get("_test_bs_trigger", False)


def test_fni_drift_bot_removes_least_support_blockade(monkeypatch):
    """§8.6.9: Bot French removes Blockade from City with least Support."""
    state = basic_state()
    state["treaty_of_alliance"] = True
    state["fni_level"] = 1
    state["spaces"] = {
        "Boston": {"type": "City"},
        "New_York_City": {"type": "City"},
        "Charleston": {"type": "City"},
    }
    state["support"] = {"Boston": 2, "New_York_City": -1, "Charleston": 0}
    state["markers"][C.BLOCKADE] = {"pool": 0, "on_map": {"Boston", "New_York_City", "Charleston"}}

    monkeypatch.setattr(year_end.map_adj, "space_meta",
                        lambda sid: {"type": "City"}, raising=False)

    bots = {C.FRENCH: FakeFrenchBot()}
    year_end._fni_drift(state, bots=bots, human_factions=set())

    on_map = state["markers"][C.BLOCKADE]["on_map"]
    # Least support is New_York_City (-1) — it should be removed
    assert "New_York_City" not in on_map
    # Remaining 2 blockades rearranged to cities with most support
    # Boston (2) and Charleston (0) — since 2 blockades remain,
    # they go to the top 2 cities by support
    assert "Boston" in on_map


def test_fni_drift_no_bot_uses_arbitrary_removal():
    """Without bots, blockade removal is arbitrary (no rearrangement)."""
    state = basic_state()
    state["treaty_of_alliance"] = True
    state["fni_level"] = 1
    state["spaces"] = {
        "Boston": {"type": "City"},
        "Charleston": {"type": "City"},
    }
    state["support"] = {"Boston": 2, "Charleston": -1}
    state["markers"][C.BLOCKADE] = {"pool": 0, "on_map": {"Boston", "Charleston"}}

    year_end._fni_drift(state)

    on_map = state["markers"][C.BLOCKADE]["on_map"]
    pool = state["markers"][C.BLOCKADE]["pool"]
    # One removed, one remains
    assert len(on_map) == 1
    assert pool == 1


def test_check_bs_triggers_calls_bot_method():
    """check_bs_triggers should call ops_bs_trigger on each bot faction."""
    state = basic_state()
    state["_test_bs_trigger"] = True

    bots = {C.FRENCH: FakeFrenchBot()}
    result = year_end.check_bs_triggers(state, bots=bots, human_factions=set())
    assert result.get(C.FRENCH) is True


def test_check_bs_triggers_excludes_humans():
    """Human-controlled factions should not be checked for BS triggers."""
    state = basic_state()
    state["_test_bs_trigger"] = True

    bots = {C.FRENCH: FakeFrenchBot()}
    result = year_end.check_bs_triggers(
        state, bots=bots, human_factions={C.FRENCH}
    )
    assert C.FRENCH not in result


def test_check_bs_triggers_returns_empty_when_no_trigger():
    """If ops_bs_trigger returns False, faction should not appear."""
    state = basic_state()
    state["_test_bs_trigger"] = False

    bots = {C.FRENCH: FakeFrenchBot()}
    result = year_end.check_bs_triggers(state, bots=bots, human_factions=set())
    assert C.FRENCH not in result


# ──────────────────────────────────────────────────────────────
#  Bug 1: Support Phase marker removal must NOT count against
#          the 2-level shift cap (§6.4.1 / §6.4.2)
# ──────────────────────────────────────────────────────────────

def test_reward_loyalty_markers_dont_consume_shift_cap():
    """§6.4.1: Space at Passive Opposition with both Raid and Propaganda markers.
    British should remove both markers (2 Resources) AND shift 2 levels (2 Resources).
    Total cost = 4 Resources. Final support = +1 (Active Support = Passive Opp -> Neutral -> Passive Support).
    Wait, Passive Opposition is -1, so +2 shifts -> +1 (Passive Support)."""
    state = basic_state()
    state["resources"][C.BRITISH] = 10
    state["spaces"] = {
        "CityA": {
            C.REGULAR_BRI: 1,
            C.TORY: 1,
        },
    }
    state["support"] = {"CityA": C.PASSIVE_OPPOSITION}  # -1
    state["control"] = {"CityA": "BRITISH"}
    state["markers"][C.RAID]["on_map"] = {"CityA"}
    state["markers"][C.PROPAGANDA]["on_map"] = {"CityA"}

    year_end._support_phase(state)

    # Both markers should be removed
    assert "CityA" not in state["markers"][C.RAID]["on_map"]
    assert "CityA" not in state["markers"][C.PROPAGANDA]["on_map"]
    # Support should have shifted 2 levels: -1 -> 0 -> +1
    assert state["support"]["CityA"] == C.PASSIVE_SUPPORT  # +1
    # Total Resources spent: 2 (markers) + 2 (shifts) = 4
    assert state["resources"][C.BRITISH] == 6


def test_committees_raid_marker_doesnt_consume_shift_cap():
    """§6.4.2: Space at Passive Support with a Raid marker.
    Patriots should remove the Raid marker (1 Resource) AND shift 2 levels (2 Resources).
    Total cost = 3 Resources. Final support = -1 (Passive Opposition)."""
    state = basic_state()
    state["resources"][C.PATRIOTS] = 10
    state["spaces"] = {
        "ColA": {
            C.MILITIA_A: 1,
        },
    }
    state["support"] = {"ColA": C.PASSIVE_SUPPORT}  # +1
    state["control"] = {"ColA": "REBELLION"}
    state["markers"][C.RAID]["on_map"] = {"ColA"}

    year_end._support_phase(state)

    # Raid marker should be removed
    assert "ColA" not in state["markers"][C.RAID]["on_map"]
    # Support should have shifted 2 levels: +1 -> 0 -> -1
    assert state["support"]["ColA"] == C.PASSIVE_OPPOSITION  # -1
    # Total Resources spent: 1 (marker) + 2 (shifts) = 3
    assert state["resources"][C.PATRIOTS] == 7


# ──────────────────────────────────────────────────────────────
#  Bug 2: Indian Supply — Reserve detection must use space_type()
# ──────────────────────────────────────────────────────────────

def test_indian_war_parties_in_reserve_are_supplied(monkeypatch):
    """§6.2.1: War Parties in an Indian Reserve Province are in supply."""
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)

    state = basic_state()
    # Quebec is a Reserve space per map.json
    state["spaces"] = {
        "Quebec": {C.WARPARTY_A: 2, C.WARPARTY_U: 1},
        C.WEST_INDIES_ID: {},
    }
    state["resources"][C.INDIANS] = 0  # No resources to pay

    year_end._supply_phase(state)

    # War Parties should NOT be removed — Quebec is a Reserve and they are in supply
    assert state["spaces"]["Quebec"].get(C.WARPARTY_A, 0) == 2
    assert state["spaces"]["Quebec"].get(C.WARPARTY_U, 0) == 1


def test_indian_auto_village_places_in_reserve(monkeypatch):
    """§6.2.1: When no Villages on map, auto-place a Village in a Reserve."""
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)

    state = basic_state()
    # No villages anywhere; Quebec is a Reserve per map.json
    state["spaces"] = {
        "Quebec": {C.WARPARTY_U: 1},
        "Boston": {C.REGULAR_BRI: 0},
        C.WEST_INDIES_ID: {},
    }
    # Ensure there is at least 1 Village in available pool
    state["available"] = {C.VILLAGE: 5}

    year_end._supply_phase(state)

    # A Village should have been auto-placed in a Reserve space
    reserve_spaces = ["Quebec", "Northwest", "Southwest", "Florida"]
    village_placed = any(
        state["spaces"].get(s, {}).get(C.VILLAGE, 0) > 0
        for s in reserve_spaces
        if s in state["spaces"]
    )
    assert village_placed, "Auto-Village should be placed in a Reserve space"


# ──────────────────────────────────────────────────────────────
#  Bug 3: French Supply — must require Colony/City for Rebellion
#          control to count as in-supply (§6.2.1)
# ──────────────────────────────────────────────────────────────

def test_french_regulars_in_rebellion_province_are_unsupplied(monkeypatch):
    """§6.2.1: French Regulars in a Rebellion-controlled Province (not Colony/City)
    should be treated as unsupplied."""
    monkeypatch.setattr(year_end.board_control, "refresh_control", lambda s: None, raising=False)
    monkeypatch.setattr(year_end.caps_util, "enforce_global_caps", lambda s: None, raising=False)
    monkeypatch.setattr(year_end, "battle_execute", lambda *a, **k: None, raising=False)

    state = basic_state()
    # Quebec is a Reserve (Province), not a Colony or City
    state["spaces"] = {
        "Quebec": {C.REGULAR_FRE: 2},
        C.WEST_INDIES_ID: {},
    }
    state["control"] = {"Quebec": "REBELLION"}
    state["resources"][C.FRENCH] = 0  # No resources to pay

    year_end._supply_phase(state)

    # French Regulars should be removed (unsupplied, can't pay, no Fort to move to)
    assert state["spaces"]["Quebec"].get(C.REGULAR_FRE, 0) == 0


# ──────────────────────────────────────────────────────────────
#  Bug: Support Phase must sort eligible spaces per §8.4.5/§8.5.9
# ──────────────────────────────────────────────────────────────

def test_reward_loyalty_sorts_by_fewest_markers_then_population(monkeypatch):
    """§8.4.5: Space B (0 markers, pop 2) should be shifted before Space A
    (2 markers, pop 1), even if A appears first in dict order."""
    # Control population lookups for test spaces
    _pop = {"SpaceA": 1, "SpaceB": 2}
    monkeypatch.setattr(year_end.map_adj, "population",
                        lambda sid: _pop.get(sid, 0))

    state = basic_state()
    state["resources"][C.BRITISH] = 4
    state["spaces"] = {
        "SpaceA": {C.REGULAR_BRI: 1, C.TORY: 1},
        "SpaceB": {C.REGULAR_BRI: 1, C.TORY: 1},
    }
    state["support"] = {"SpaceA": C.NEUTRAL, "SpaceB": C.NEUTRAL}
    state["control"] = {"SpaceA": C.BRITISH, "SpaceB": C.BRITISH}
    # SpaceA has Raid + Propaganda markers; SpaceB has none
    state["markers"][C.RAID]["on_map"] = {"SpaceA"}
    state["markers"][C.PROPAGANDA]["on_map"] = {"SpaceA"}

    year_end._support_phase(state)

    # SpaceB (0 markers, pop 2) should be shifted first: 2 Resources for 2 shifts
    # SpaceA needs 2 markers + 1 shift = 3 minimum, only 2 left → skipped
    assert state["support"]["SpaceB"] == C.ACTIVE_SUPPORT  # shifted 2 levels
    assert state["support"]["SpaceA"] == C.NEUTRAL  # not shifted (insufficient)
    assert state["resources"][C.BRITISH] == 2  # spent 2 on SpaceB shifts


def test_committees_sorts_by_fewest_raid_then_population(monkeypatch):
    """§8.5.9: Space B (0 Raid, pop 2) should be shifted before Space A
    (1 Raid, pop 1)."""
    _pop = {"SpaceA": 1, "SpaceB": 2}
    monkeypatch.setattr(year_end.map_adj, "population",
                        lambda sid: _pop.get(sid, 0))

    state = basic_state()
    state["resources"][C.PATRIOTS] = 4
    state["spaces"] = {
        "SpaceA": {C.MILITIA_A: 1},
        "SpaceB": {C.MILITIA_A: 1},
    }
    state["support"] = {"SpaceA": C.NEUTRAL, "SpaceB": C.NEUTRAL}
    state["control"] = {"SpaceA": "REBELLION", "SpaceB": "REBELLION"}
    # SpaceA has a Raid marker; SpaceB has none
    state["markers"][C.RAID]["on_map"] = {"SpaceA"}

    year_end._support_phase(state)

    # SpaceB (0 markers, pop 2) shifted first: 2 Resources for 2 shifts
    # SpaceA needs 1 marker + 1 shift = 2 minimum, only 2 left → shifts once
    assert state["support"]["SpaceB"] == C.ACTIVE_OPPOSITION  # shifted 2 levels
    assert state["support"]["SpaceA"] <= C.NEUTRAL  # may or may not shift


# ──────────────────────────────────────────────────────────────
#  Bug: Do not spend on a space if only markers would be removed
# ──────────────────────────────────────────────────────────────

def test_reward_loyalty_skips_space_if_only_markers_removed(monkeypatch):
    """§8.4.5: British have 2 Resources, space has 2 markers at Neutral.
    Minimum cost = 2 (markers) + 1 (shift) = 3.  Can't afford → skip."""
    _pop = {"SpaceA": 1}
    monkeypatch.setattr(year_end.map_adj, "population",
                        lambda sid: _pop.get(sid, 0))

    state = basic_state()
    state["resources"][C.BRITISH] = 2
    state["spaces"] = {
        "SpaceA": {C.REGULAR_BRI: 1, C.TORY: 1},
    }
    state["support"] = {"SpaceA": C.NEUTRAL}
    state["control"] = {"SpaceA": C.BRITISH}
    state["markers"][C.RAID]["on_map"] = {"SpaceA"}
    state["markers"][C.PROPAGANDA]["on_map"] = {"SpaceA"}

    year_end._support_phase(state)

    # No resources should be spent — can't afford markers + shift
    assert state["resources"][C.BRITISH] == 2
    assert state["support"]["SpaceA"] == C.NEUTRAL
    # Markers should still be present
    assert "SpaceA" in state["markers"][C.RAID]["on_map"]
    assert "SpaceA" in state["markers"][C.PROPAGANDA]["on_map"]
