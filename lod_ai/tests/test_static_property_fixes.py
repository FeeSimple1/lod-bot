"""
Tests for static-property query fixes (sp.get("type") / sp.get("indian_reserve") bug class).

Each test validates that runtime code correctly uses the static map helpers
(space_type, is_city from lod_ai.map.adjacency) instead of querying keys
that only exist in the JSON map data, not in runtime space dicts.

Bug 1: Patriot Desertion (year_end.py) — §6.6.1
Bug 2: Gather reserve discount (gather.py) — §3.4.1
Bug 3: March WP activation (march.py) — §3.4.2
Bug 4: Common Cause city restriction (common_cause.py) — §4.2.1
"""
import sys
from pathlib import Path
import random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai import rules_consts as C
from lod_ai.util import year_end
from lod_ai.commands import gather, march
from lod_ai.special_activities import common_cause


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    st = {
        "spaces": {},
        "available": {},
        "casualties": {},
        "unavailable": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.INDIANS: 10, C.FRENCH: 10},
        "support": {},
        "control": {},
        "history": [],
        "log": [],
        "rng": random.Random(42),
        "markers": {
            C.BLOCKADE: {"pool": 0, "on_map": set()},
            C.PROPAGANDA: {"pool": 12, "on_map": set()},
            C.RAID: {"pool": 0, "on_map": set()},
        },
        "_turn_used_special": False,
        "leaders": {},
        "deck": [],
    }
    st.update(overrides)
    return st


# ===========================================================================
# Bug 1 — Patriot Desertion removes pieces from the map (§6.6.1)
# ===========================================================================

class TestPatriotDesertion:
    """§6.6.1: 'Remove 1 in 5 Militia and 1 in 5 Continentals from the map.'
    No Colony restriction — pieces in any space count."""

    def test_militia_desertion_removes_correct_count(self):
        """10 Militia across multiple spaces → remove 2 (10 // 5)."""
        state = _base_state()
        # Use real Colony space IDs but do NOT put "type" in the runtime dict
        state["spaces"] = {
            "Massachusetts": {C.MILITIA_U: 6},
            "Virginia": {C.MILITIA_U: 4},
        }
        state["support"] = {"Massachusetts": 0, "Virginia": 0}

        year_end._patriot_desertion(state)

        total = sum(
            sp.get(C.MILITIA_U, 0) + sp.get(C.MILITIA_A, 0)
            for sp in state["spaces"].values()
        )
        assert total == 8, f"Expected 8 militia remaining (10 - 10//5), got {total}"

    def test_continental_desertion_removes_correct_count(self):
        """15 Continentals → remove 3 (15 // 5)."""
        state = _base_state()
        state["spaces"] = {
            "Massachusetts": {C.REGULAR_PAT: 10},
            "Virginia": {C.REGULAR_PAT: 5},
        }
        state["support"] = {"Massachusetts": 0, "Virginia": 0}

        year_end._patriot_desertion(state)

        total = sum(
            sp.get(C.REGULAR_PAT, 0) for sp in state["spaces"].values()
        )
        assert total == 12, f"Expected 12 Continentals remaining (15 - 15//5), got {total}"

    def test_desertion_works_without_type_key(self):
        """Runtime space dicts don't have 'type' — desertion must still work."""
        state = _base_state()
        # Explicitly no "type" key in runtime dicts
        state["spaces"] = {
            "Massachusetts": {C.MILITIA_U: 5, C.REGULAR_PAT: 5},
        }
        state["support"] = {"Massachusetts": 0}

        year_end._patriot_desertion(state)

        mil = state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0)
        con = state["spaces"]["Massachusetts"].get(C.REGULAR_PAT, 0)
        assert mil == 4, f"Expected 4 militia (5 - 5//5), got {mil}"
        assert con == 4, f"Expected 4 Continentals (5 - 5//5), got {con}"

    def test_desertion_from_reserve_spaces(self):
        """Pieces in Reserve spaces also subject to desertion (rule says 'from the map')."""
        state = _base_state()
        state["spaces"] = {
            "Northwest": {C.MILITIA_U: 5},
            "Massachusetts": {C.MILITIA_U: 5},
        }
        state["support"] = {"Northwest": 0, "Massachusetts": 0}

        year_end._patriot_desertion(state)

        total = sum(
            sp.get(C.MILITIA_U, 0) for sp in state["spaces"].values()
        )
        assert total == 8, f"Expected 8 militia (10 - 10//5), got {total}"

    def test_zero_desertion_when_below_five(self):
        """4 militia → 4 // 5 = 0, no removal."""
        state = _base_state()
        state["spaces"] = {
            "Massachusetts": {C.MILITIA_U: 4},
        }

        year_end._patriot_desertion(state)

        assert state["spaces"]["Massachusetts"].get(C.MILITIA_U, 0) == 4


class TestToryDesertion:
    """§6.6.2: 'Remove 1 in 5 Tories from the map (rounding down).'"""

    def test_tory_desertion_removes_correct_count(self):
        """10 Tories → remove 2."""
        state = _base_state()
        state["spaces"] = {
            "Massachusetts": {C.TORY: 6},
            "Virginia": {C.TORY: 4},
        }
        state["support"] = {"Massachusetts": 0, "Virginia": 0}

        year_end._tory_desertion(state)

        total = sum(sp.get(C.TORY, 0) for sp in state["spaces"].values())
        assert total == 8, f"Expected 8 Tories (10 - 10//5), got {total}"

    def test_tory_desertion_no_crash_without_support_key(self):
        """_tory_desertion must not crash if state['support'] is missing."""
        state = _base_state()
        state["spaces"] = {
            "Massachusetts": {C.TORY: 5},
        }
        # Remove support key entirely to test edge case
        del state["support"]

        year_end._tory_desertion(state)

        assert state["spaces"]["Massachusetts"].get(C.TORY, 0) == 4


# ===========================================================================
# Bug 2 — Gather reserve discount (§3.4.1)
# ===========================================================================

class TestGatherReserveDiscount:
    """§3.4.1: First Indian Reserve Province selected for Gather is free."""

    def test_is_indian_reserve_returns_true_for_reserve(self):
        """_is_indian_reserve must return True for a known Reserve space."""
        assert gather._is_indian_reserve("Quebec") is True
        assert gather._is_indian_reserve("Northwest") is True
        assert gather._is_indian_reserve("Southwest") is True
        assert gather._is_indian_reserve("Florida") is True

    def test_is_indian_reserve_returns_false_for_colony(self):
        assert gather._is_indian_reserve("Massachusetts") is False

    def test_is_indian_reserve_returns_false_for_city(self):
        assert gather._is_indian_reserve("Boston") is False

    def test_reserve_discount_applied(self, monkeypatch):
        """Gathering in a Reserve space should cost 0 resources (first Reserve free)."""
        monkeypatch.setattr(gather, "refresh_control", lambda s: None)
        monkeypatch.setattr(gather, "enforce_global_caps", lambda s: None)
        state = _base_state()
        state["spaces"]["Quebec"] = {C.WARPARTY_U: 2, C.VILLAGE: 1}
        state["support"]["Quebec"] = C.NEUTRAL
        state["available"] = {C.WARPARTY_U: 10}

        initial_res = state["resources"][C.INDIANS]
        gather.execute(state, C.INDIANS, {}, ["Quebec"], place_one={"Quebec"})

        # One Reserve selected → free → cost 0
        assert state["resources"][C.INDIANS] == initial_res

    def test_non_reserve_costs_resource(self, monkeypatch):
        """Gathering in a Colony space should cost 1 resource."""
        monkeypatch.setattr(gather, "refresh_control", lambda s: None)
        monkeypatch.setattr(gather, "enforce_global_caps", lambda s: None)
        state = _base_state()
        state["spaces"]["New_York"] = {C.WARPARTY_U: 2, C.VILLAGE: 1}
        state["support"]["New_York"] = C.NEUTRAL
        state["available"] = {C.WARPARTY_U: 10}

        initial_res = state["resources"][C.INDIANS]
        gather.execute(state, C.INDIANS, {}, ["New_York"], place_one={"New_York"})

        assert state["resources"][C.INDIANS] == initial_res - 1


# ===========================================================================
# Bug 3 — March WP activation in Rebellion-controlled Colony (§3.4.2)
# ===========================================================================

class TestMarchWPActivation:
    """§3.4.2: Underground War Parties flip Active when marching into a
    Rebellion-controlled Colony where group + militia > 3."""

    def test_wp_activate_in_rebellion_colony(self, monkeypatch):
        """WP moving into Rebellion-controlled Colony with group + militia > 3
        should flip to Active."""
        monkeypatch.setattr(march, "refresh_control", lambda s: None)
        monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
        monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
        # Use real space IDs: Massachusetts is a Colony
        state = {
            "spaces": {
                "Connecticut_Rhode_Island": {C.WARPARTY_U: 3},
                "Massachusetts": {C.MILITIA_U: 2},
            },
            "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 5},
            "available": {},
            "control": {"Massachusetts": "REBELLION"},
            "rng": random.Random(42),
        }
        plan = [{"src": "Connecticut_Rhode_Island", "dst": "Massachusetts",
                 "pieces": {C.WARPARTY_U: 3}}]
        march.execute(state, C.INDIANS, {}, [], ["Massachusetts"], plan=plan)

        # 3 WP moving + 2 militia in dst = 5 > 3 → WP should activate
        sp = state["spaces"]["Massachusetts"]
        assert sp.get(C.WARPARTY_A, 0) > 0, \
            "War Parties should have been flipped Active in Rebellion Colony"

    def test_wp_stay_underground_when_not_rebellion_colony(self, monkeypatch):
        """WP should NOT activate in a non-Rebellion space."""
        monkeypatch.setattr(march, "refresh_control", lambda s: None)
        monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
        monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
        state = {
            "spaces": {
                "Connecticut_Rhode_Island": {C.WARPARTY_U: 3},
                "Massachusetts": {C.MILITIA_U: 2},
            },
            "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 5},
            "available": {},
            "control": {"Massachusetts": "BRITISH"},
            "rng": random.Random(42),
        }
        plan = [{"src": "Connecticut_Rhode_Island", "dst": "Massachusetts",
                 "pieces": {C.WARPARTY_U: 3}}]
        march.execute(state, C.INDIANS, {}, [], ["Massachusetts"], plan=plan)

        sp = state["spaces"]["Massachusetts"]
        assert sp.get(C.WARPARTY_A, 0) == 0, \
            "War Parties should stay Underground in British-controlled space"
        assert sp.get(C.WARPARTY_U, 0) == 3

    def test_wp_stay_underground_in_city(self, monkeypatch):
        """WP cannot enter Cities (§3.4.2), but if somehow in a City-like
        scenario, should not activate since it's not a Colony."""
        monkeypatch.setattr(march, "refresh_control", lambda s: None)
        monkeypatch.setattr(march, "enforce_global_caps", lambda s: None)
        monkeypatch.setattr(march, "is_adjacent", lambda a, b: True)
        state = {
            "spaces": {
                "Connecticut_Rhode_Island": {C.WARPARTY_U: 3},
                # Use a Colony, not a City — WP activation only triggers for Colonies
                "New_Hampshire": {C.MILITIA_U: 2},
            },
            "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 5},
            "available": {},
            "control": {"New_Hampshire": None},
            "rng": random.Random(42),
        }
        plan = [{"src": "Connecticut_Rhode_Island", "dst": "New_Hampshire",
                 "pieces": {C.WARPARTY_U: 3}}]
        march.execute(state, C.INDIANS, {}, [], ["New_Hampshire"], plan=plan)

        sp = state["spaces"]["New_Hampshire"]
        # Not Rebellion controlled → no activation
        assert sp.get(C.WARPARTY_A, 0) == 0


# ===========================================================================
# Bug 4 — Common Cause City restriction (§4.2.1)
# ===========================================================================

class TestCommonCauseCityRestriction:
    """§4.2.1: War Parties used via Common Cause may not move into Cities."""

    def test_city_destination_raises(self):
        """Common Cause March into a City should raise ValueError."""
        state = _base_state()
        # Boston is a real City space in the map
        state["spaces"]["Massachusetts"] = {
            C.REGULAR_BRI: 2, C.WARPARTY_U: 2,
        }
        state["spaces"]["Boston"] = {}

        with pytest.raises(ValueError, match="Cities"):
            common_cause.execute(
                state, C.BRITISH, {},
                ["Massachusetts"],
                mode="MARCH",
                destinations=["Boston"],
            )

    def test_colony_destination_allowed(self):
        """Common Cause March into a Colony should NOT raise."""
        state = _base_state()
        state["spaces"]["Massachusetts"] = {
            C.REGULAR_BRI: 2, C.WARPARTY_U: 2,
        }
        state["spaces"]["Virginia"] = {}

        # Virginia is a Colony — should succeed
        ctx = common_cause.execute(
            state, C.BRITISH, {},
            ["Massachusetts"],
            mode="MARCH",
            destinations=["Virginia"],
        )
        assert "common_cause" in ctx
        assert "Massachusetts" in ctx["common_cause"]

    def test_city_check_uses_map_data_not_runtime_dict(self):
        """Even without 'city' or 'type' keys in runtime dict, City detection works."""
        state = _base_state()
        # New_York_City is a City in the static map, no "type"/"city" in runtime dict
        state["spaces"]["Massachusetts"] = {
            C.REGULAR_BRI: 1, C.WARPARTY_U: 1,
        }
        state["spaces"]["New_York_City"] = {}

        with pytest.raises(ValueError, match="Cities"):
            common_cause.execute(
                state, C.BRITISH, {},
                ["Massachusetts"],
                mode="MARCH",
                destinations=["New_York_City"],
            )
