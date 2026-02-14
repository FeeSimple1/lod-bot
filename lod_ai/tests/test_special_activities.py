"""
Tests for Special Activity compliance against Manual Ch 4.txt.
Each test references the specific section and rule it validates.
"""
import sys
from pathlib import Path
import random
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai import rules_consts as C
from lod_ai.special_activities import (
    preparer,
    trade,
    plunder,
    common_cause,
    war_path,
    partisans,
    naval_pressure,
    skirmish,
    persuasion,
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    """Return a minimal valid state dict, with overrides."""
    st = {
        "spaces": {},
        "available": {},
        "casualties": {},
        "unavailable": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.INDIANS: 10, C.FRENCH: 10},
        "history": [],
        "log": [],
        "rng": random.Random(42),
        "toa_played": False,
        "fni_level": 0,
        "markers": {
            C.BLOCKADE: {"pool": 0, "on_map": set()},
            C.PROPAGANDA: {"pool": 12, "on_map": set()},
        },
        "control": {},
        "_turn_used_special": False,
        "leaders": {},
    }
    st.update(overrides)
    return st


def _space(state, sid, **pieces):
    """Add a space with the given piece counts to state."""
    state["spaces"].setdefault(sid, {}).update(pieces)
    return state


# ===========================================================================
# §4.5.1 — Préparer la Guerre
# ===========================================================================

class TestPreparer:
    """§4.5.1: Préparer la Guerre available before AND after TOA."""

    def test_preparer_before_toa_allowed(self):
        """§4.5: French may choose only Préparer la Guerre before TOA — so it
        must be callable pre-TOA."""
        state = _base_state(toa_played=False)
        state["unavailable"][C.BLOCKADE] = 3
        ctx = preparer.execute(state, C.FRENCH, {}, choice="BLOCKADE")
        # Should succeed — no ValueError
        assert state["_turn_used_special"] is True

    def test_preparer_after_toa_allowed(self):
        state = _base_state(toa_played=True)
        state["unavailable"][C.BLOCKADE] = 3
        ctx = preparer.execute(state, C.FRENCH, {}, choice="BLOCKADE")
        assert state["_turn_used_special"] is True

    def test_preparer_resources_choice(self):
        state = _base_state(toa_played=False)
        preparer.execute(state, C.FRENCH, {}, choice="RESOURCES")
        assert state["resources"][C.FRENCH] == 12  # 10 + 2

    def test_preparer_regulars_choice(self):
        state = _base_state(toa_played=False)
        state["unavailable"][C.REGULAR_FRE] = 5
        preparer.execute(state, C.FRENCH, {}, choice="REGULARS")
        # 3 moved from unavailable to available
        assert state["unavailable"].get(C.REGULAR_FRE, 0) == 2
        assert state["available"].get(C.REGULAR_FRE, 0) == 3

    def test_preparer_non_french_rejected(self):
        state = _base_state()
        with pytest.raises(ValueError, match="French-only"):
            preparer.execute(state, C.BRITISH, {}, choice="RESOURCES")


# ===========================================================================
# §4.4.1 — Trade
# ===========================================================================

class TestTrade:
    """§4.4.1: Trade adds flat +1 when British transfer is 0."""

    def test_trade_zero_transfer_adds_one_flat(self):
        """§4.4.1: 'if 0, then Activate one Underground War Party in the
        selected Province and add one Resource.' — flat +1, not 1D3."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.VILLAGE: 1})
        state["available"][C.WARPARTY_A] = 5
        before = state["resources"][C.INDIANS]
        trade.execute(state, C.INDIANS, {}, "Ohio", transfer=0)
        assert state["resources"][C.INDIANS] == before + 1

    def test_trade_positive_transfer(self):
        """§4.4.1: British → Indian transfer when > 0."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.VILLAGE: 1})
        state["available"][C.WARPARTY_A] = 5
        trade.execute(state, C.INDIANS, {}, "Ohio", transfer=3)
        assert state["resources"][C.BRITISH] == 7   # 10 - 3
        assert state["resources"][C.INDIANS] == 13  # 10 + 3

    def test_trade_activates_one_wp(self):
        """§4.4.1: Activate one Underground War Party."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.VILLAGE: 1})
        state["available"][C.WARPARTY_A] = 5
        trade.execute(state, C.INDIANS, {}, "Ohio", transfer=0)
        assert state["spaces"]["Ohio"][C.WARPARTY_U] == 1
        assert state["spaces"]["Ohio"].get(C.WARPARTY_A, 0) == 1

    def test_trade_requires_village(self):
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2})
        with pytest.raises(ValueError, match="Village"):
            trade.execute(state, C.INDIANS, {}, "Ohio", transfer=0)


# ===========================================================================
# §4.4.3 — Plunder
# ===========================================================================

class TestPlunder:
    """§4.4.3: Plunder counts ALL Rebellion pieces, including Underground Militia."""

    def test_plunder_counts_underground_militia(self):
        """Underground Militia are Rebellion pieces for the WP > Rebellion check."""
        state = _base_state()
        # 3 WP vs 2 Rebellion (1 Continental + 1 Underground Militia)
        _space(state, "Virginia", **{
            C.WARPARTY_U: 1, C.WARPARTY_A: 2,
            C.REGULAR_PAT: 1, C.MILITIA_U: 1,
            "population": 2,
        })
        state["available"][C.WARPARTY_U] = 5
        ctx = {"raid_active": True}
        # WP=3, Rebellion=2 (Continental+Underground Militia) → 3 > 2, so valid
        plunder.execute(state, C.INDIANS, ctx, "Virginia")
        assert state["resources"][C.INDIANS] == 12  # 10 + 2 (population)

    def test_plunder_blocked_by_underground_militia(self):
        """If Underground Militia tips Rebellion >= War Parties, Plunder is invalid."""
        state = _base_state()
        # 2 WP vs 2 Rebellion (1 Continental + 1 Underground Militia)
        _space(state, "Virginia", **{
            C.WARPARTY_A: 2,
            C.REGULAR_PAT: 1, C.MILITIA_U: 1,
            "population": 2,
        })
        ctx = {"raid_active": True}
        with pytest.raises(ValueError, match="do not exceed"):
            plunder.execute(state, C.INDIANS, ctx, "Virginia")


# ===========================================================================
# §4.2.1 — Common Cause
# ===========================================================================

class TestCommonCause:
    """§4.2.1: 'spaces with British pieces and War Parties' — any British piece."""

    def test_common_cause_with_tory_only(self):
        """A Tory alone qualifies as a British piece."""
        state = _base_state()
        _space(state, "Georgia", **{C.TORY: 1, C.WARPARTY_U: 2})
        ctx = common_cause.execute(state, C.BRITISH, {}, ["Georgia"])
        assert "Georgia" in ctx.get("common_cause", {})

    def test_common_cause_with_fort_only(self):
        """A British Fort alone qualifies as a British piece."""
        state = _base_state()
        _space(state, "Georgia", **{C.FORT_BRI: 1, C.WARPARTY_U: 2})
        ctx = common_cause.execute(state, C.BRITISH, {}, ["Georgia"])
        assert "Georgia" in ctx.get("common_cause", {})

    def test_common_cause_no_british_piece_rejected(self):
        """No British pieces at all should fail."""
        state = _base_state()
        _space(state, "Georgia", **{C.WARPARTY_U: 2})
        with pytest.raises(ValueError, match="needs British piece"):
            common_cause.execute(state, C.BRITISH, {}, ["Georgia"])

    def test_common_cause_activates_war_parties(self):
        """§4.2.1: Activate War Parties utilized."""
        state = _base_state()
        _space(state, "Georgia", **{C.REGULAR_BRI: 1, C.WARPARTY_U: 3})
        state["available"][C.WARPARTY_A] = 5
        common_cause.execute(state, C.BRITISH, {}, ["Georgia"], wp_counts={"Georgia": 2})
        # 2 WP-U flipped to WP-A
        assert state["spaces"]["Georgia"][C.WARPARTY_U] == 1
        assert state["spaces"]["Georgia"][C.WARPARTY_A] == 2


# ===========================================================================
# §4.4.2 — War Path
# ===========================================================================

class TestWarPath:
    """§4.4.2: cubes and Forts → Casualties; Militia → Available; Brant +1."""

    def test_option1_militia_to_available(self):
        """Militia are not cubes: removed Militia go to Available."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.MILITIA_A: 1})
        state["available"][C.WARPARTY_A] = 5
        war_path.execute(state, C.INDIANS, {}, "Ohio", option=1)
        # Militia should go to available, not casualties
        assert state["available"].get(C.MILITIA_A, 0) + state["available"].get(C.MILITIA_U, 0) >= 1
        assert state["casualties"].get(C.MILITIA_A, 0) == 0

    def test_option1_cube_to_casualties(self):
        """Cubes go to Casualties per the parenthetical."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.REGULAR_PAT: 1})
        state["available"][C.WARPARTY_A] = 5
        war_path.execute(state, C.INDIANS, {}, "Ohio", option=1)
        assert state["casualties"].get(C.REGULAR_PAT, 0) == 1

    def test_option3_fort_to_casualties(self):
        """Forts go to Casualties per §4.4.2 parenthetical."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 3, C.FORT_PAT: 1})
        state["available"][C.WARPARTY_A] = 5
        war_path.execute(state, C.INDIANS, {}, "Ohio", option=3)
        assert state["casualties"].get(C.FORT_PAT, 0) == 1

    def test_no_base_extra_militia_removal(self):
        """Without Brant, War Path does NOT remove extra Militia beyond the option."""
        state = _base_state()
        _space(state, "Ohio", **{
            C.WARPARTY_U: 2,
            C.REGULAR_PAT: 1,
            C.MILITIA_A: 3,
        })
        state["available"][C.WARPARTY_A] = 5
        war_path.execute(state, C.INDIANS, {}, "Ohio", option=1)
        # Option 1 removes 1 piece: the Continental (first cube in priority).
        # No extra Militia should be removed since Brant is not present.
        assert state["spaces"]["Ohio"].get(C.MILITIA_A, 0) == 3

    def test_brant_removes_extra_militia(self):
        """With Brant present, War Path removes 1 additional Militia."""
        state = _base_state()
        _space(state, "Ohio", **{
            C.WARPARTY_U: 2,
            C.REGULAR_PAT: 1,
            C.MILITIA_A: 3,
            "LEADER_BRANT": 1,
        })
        state["available"][C.WARPARTY_A] = 5
        war_path.execute(state, C.INDIANS, {}, "Ohio", option=1)
        # Option 1 removes 1 Continental. Brant removes 1 extra Militia.
        assert state["spaces"]["Ohio"].get(C.MILITIA_A, 0) == 2

    def test_option1_rejects_fort_only(self):
        """Option 1 requires Rebellion units (cubes/Militia), not just a Fort."""
        state = _base_state()
        _space(state, "Ohio", **{C.WARPARTY_U: 2, C.FORT_PAT: 1})
        state["available"][C.WARPARTY_A] = 5
        with pytest.raises(ValueError, match="Options 1/2 require"):
            war_path.execute(state, C.INDIANS, {}, "Ohio", option=1)


# ===========================================================================
# §4.3.2 — Partisans
# ===========================================================================

class TestPartisans:
    """§4.3.2: 'cubes are removed to Casualties' — only cubes, not Forts."""

    def test_option1_cube_to_casualties(self):
        """Tory (cube) goes to Casualties."""
        state = _base_state()
        _space(state, "SC", **{C.MILITIA_U: 2, C.TORY: 1})
        state["available"][C.MILITIA_A] = 5
        partisans.execute(state, C.PATRIOTS, {}, "SC", option=1)
        assert state["casualties"].get(C.TORY, 0) == 1

    def test_option1_warparty_to_available(self):
        """War Party (not a cube) goes to Available."""
        state = _base_state()
        _space(state, "SC", **{C.MILITIA_U: 2, C.WARPARTY_A: 1})
        state["available"][C.MILITIA_A] = 5
        partisans.execute(state, C.PATRIOTS, {}, "SC", option=1)
        # War Party should go to available, not casualties
        assert state["casualties"].get(C.WARPARTY_A, 0) == 0
        assert state["available"].get(C.WARPARTY_A, 0) + state["available"].get(C.WARPARTY_U, 0) >= 1

    def test_option1_fort_to_available(self):
        """§4.3.2 says 'cubes are removed to Casualties' (no Forts) —
        so a British Fort goes to Available."""
        state = _base_state()
        _space(state, "SC", **{C.MILITIA_U: 2, C.FORT_BRI: 1})
        state["available"][C.MILITIA_A] = 5
        partisans.execute(state, C.PATRIOTS, {}, "SC", option=1)
        assert state["casualties"].get(C.FORT_BRI, 0) == 0
        assert state["available"].get(C.FORT_BRI, 0) == 1

    def test_option2_militia_removed_to_available(self):
        """Removed Militia (not a cube) goes to Available, not Casualties."""
        state = _base_state()
        _space(state, "SC", **{C.MILITIA_U: 3, C.TORY: 2})
        state["available"][C.MILITIA_A] = 5
        partisans.execute(state, C.PATRIOTS, {}, "SC", option=2)
        # 1 Militia removed should go to Available
        assert state["casualties"].get(C.MILITIA_A, 0) == 0

    def test_option3_militia_removed_to_available(self):
        """Option 3: removed Militia goes to Available."""
        state = _base_state()
        _space(state, "SC", **{C.MILITIA_U: 3, C.VILLAGE: 1})
        state["available"][C.MILITIA_A] = 5
        state["available"][C.VILLAGE] = 5
        partisans.execute(state, C.PATRIOTS, {}, "SC", option=3)
        assert state["casualties"].get(C.MILITIA_A, 0) == 0


# ===========================================================================
# §4.5.3 — French Naval Pressure
# ===========================================================================

class TestFrenchNavalPressure:
    """§4.5.3: FNI cap uses pool+on_map, not pool-only."""

    def test_french_np_option_b_rearrange(self):
        """Option B (no markers in WI, rearrange existing) must be reachable."""
        state = _base_state(toa_played=True, fni_level=1)
        state["markers"][C.BLOCKADE] = {"pool": 0, "on_map": {"Boston", "Charleston"}}
        # FNI going from 1 → 2.  Total markers = 0 + 2 = 2.  2 ≤ 2, OK.
        naval_pressure.execute(
            state, C.FRENCH, {},
            rearrange_map={"Boston": 1, "New_York": 1},
        )
        assert state["fni_level"] == 2

    def test_french_np_option_a_place(self):
        """Option A: move Squadron from WI to a city."""
        state = _base_state(toa_played=True, fni_level=0)
        state["markers"][C.BLOCKADE] = {"pool": 2, "on_map": set()}
        naval_pressure.execute(state, C.FRENCH, {}, city_choice="Boston")
        assert state["fni_level"] == 1
        assert "Boston" in state["markers"][C.BLOCKADE]["on_map"]
        assert state["markers"][C.BLOCKADE]["pool"] == 1

    def test_french_np_fni_cap_exceeded(self):
        """Cannot raise FNI beyond total in-play markers."""
        state = _base_state(toa_played=True, fni_level=2)
        state["markers"][C.BLOCKADE] = {"pool": 0, "on_map": {"Boston", "Charleston"}}
        # Total = 2, FNI going to 3 > 2, should fail
        with pytest.raises(ValueError, match="Cannot raise FNI"):
            naval_pressure.execute(
                state, C.FRENCH, {},
                rearrange_map={"Boston": 1, "Charleston": 1},
            )

    def test_french_np_requires_toa(self):
        state = _base_state(toa_played=False)
        with pytest.raises(ValueError, match="Treaty of Alliance"):
            naval_pressure.execute(state, C.FRENCH, {})


# ===========================================================================
# §4.2.3 — British Naval Pressure
# ===========================================================================

class TestBritishNavalPressure:
    """§4.2.3: British Naval Pressure produces Resources or lowers FNI."""

    def test_british_np_pre_toa_adds_resources(self):
        """Before TOA, add 1D3 to British Resources."""
        state = _base_state(toa_played=False)
        before = state["resources"][C.BRITISH]
        naval_pressure.execute(state, C.BRITISH, {})
        gained = state["resources"][C.BRITISH] - before
        assert 1 <= gained <= 3

    def test_british_np_post_toa_fni_zero(self):
        """After TOA, FNI=0 → add 1D3 to British Resources."""
        state = _base_state(toa_played=True, fni_level=0)
        before = state["resources"][C.BRITISH]
        naval_pressure.execute(state, C.BRITISH, {})
        gained = state["resources"][C.BRITISH] - before
        assert 1 <= gained <= 3

    def test_british_np_post_toa_fni_positive(self):
        """After TOA, FNI>0 → lower FNI, remove Blockade to WI."""
        state = _base_state(toa_played=True, fni_level=2)
        state["markers"][C.BLOCKADE] = {"pool": 0, "on_map": {"Boston"}}
        naval_pressure.execute(state, C.BRITISH, {}, city_choice="Boston")
        assert state["fni_level"] == 1
        assert "Boston" not in state["markers"][C.BLOCKADE]["on_map"]
        assert state["markers"][C.BLOCKADE]["pool"] == 1


# ===========================================================================
# §4.2.2, §4.3.3, §4.5.2 — Skirmish
# ===========================================================================

class TestSkirmish:
    """Skirmish variant tests."""

    def test_patriot_skirmish_rejects_west_indies(self):
        """§4.3.3 says 'any one space' (no West Indies), unlike §4.2.2/§4.5.2."""
        state = _base_state()
        _space(state, C.WEST_INDIES_ID, **{C.REGULAR_PAT: 1, C.REGULAR_BRI: 1})
        with pytest.raises(ValueError, match="West Indies"):
            skirmish.execute(state, C.PATRIOTS, {}, C.WEST_INDIES_ID, option=1)

    def test_british_skirmish_west_indies_allowed(self):
        """§4.2.2 says 'one space or West Indies'."""
        state = _base_state()
        _space(state, C.WEST_INDIES_ID, **{C.REGULAR_BRI: 1, C.REGULAR_PAT: 1})
        skirmish.execute(state, C.BRITISH, {}, C.WEST_INDIES_ID, option=1)
        assert state["_turn_used_special"] is True

    def test_french_skirmish_requires_toa(self):
        state = _base_state(toa_played=False)
        _space(state, "Boston", **{C.REGULAR_FRE: 1, C.REGULAR_BRI: 1})
        with pytest.raises(ValueError, match="Treaty of Alliance"):
            skirmish.execute(state, C.FRENCH, {}, "Boston", option=1)

    def test_british_skirmish_option1_removes_one_rebel(self):
        """§4.2.2 option 1: Remove one Rebellion cube/Active Militia."""
        state = _base_state()
        _space(state, "Boston", **{C.REGULAR_BRI: 2, C.REGULAR_PAT: 1})
        skirmish.execute(state, C.BRITISH, {}, "Boston", option=1)
        assert state["casualties"].get(C.REGULAR_PAT, 0) == 1

    def test_patriot_skirmish_option2(self):
        """§4.3.3 option 2: Remove 2 British cubes and 1 Continental."""
        state = _base_state()
        _space(state, "Boston", **{C.REGULAR_PAT: 2, C.REGULAR_BRI: 3})
        skirmish.execute(state, C.PATRIOTS, {}, "Boston", option=2)
        assert state["casualties"].get(C.REGULAR_BRI, 0) == 2
        assert state["casualties"].get(C.REGULAR_PAT, 0) == 1


# ===========================================================================
# §4.3.1 — Persuasion
# ===========================================================================

class TestPersuasion:
    """§4.3.1: Persuasion — 1-3 Colonies/Cities, Rebellion Control, UG Militia."""

    def test_persuasion_basic(self, monkeypatch):
        """Activate 1 Underground Militia, +1 Resource, +1 Propaganda per space."""
        monkeypatch.setattr(persuasion, "refresh_control", lambda s: None)
        monkeypatch.setattr(persuasion, "enforce_global_caps", lambda s: None)
        # Mock space_type to return "Colony"
        from lod_ai.map import adjacency
        monkeypatch.setattr(adjacency, "space_type", lambda sid: "Colony")

        state = _base_state()
        state["control"]["Virginia"] = "REBELLION"
        _space(state, "Virginia", **{C.MILITIA_U: 2})
        state["available"][C.MILITIA_A] = 5

        persuasion.execute(state, C.PATRIOTS, {}, spaces=["Virginia"])
        assert state["resources"][C.PATRIOTS] == 11
        assert state["spaces"]["Virginia"].get(C.MILITIA_U, 0) == 1
        assert state["spaces"]["Virginia"].get(C.MILITIA_A, 0) == 1

    def test_persuasion_max_3_spaces(self, monkeypatch):
        """Cannot target more than 3 spaces."""
        monkeypatch.setattr(persuasion, "refresh_control", lambda s: None)
        monkeypatch.setattr(persuasion, "enforce_global_caps", lambda s: None)
        state = _base_state()
        with pytest.raises(ValueError, match="1-3"):
            persuasion.execute(state, C.PATRIOTS, {}, spaces=["A", "B", "C", "D"])
