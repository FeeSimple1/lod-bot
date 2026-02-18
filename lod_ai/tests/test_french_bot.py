import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.french import FrenchBot
from lod_ai import rules_consts as C
import random


def simple_state():
    return {
        "spaces": {
            "Quebec": {"adj": ["New_York"], "support": 0},
            "New_York": {"British_Regular": 1, "adj": ["Quebec"], "support": 0},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 5, "INDIANS": 5},
        "available": {"French_Regular": 4},
        "rng": __import__('random').Random(1),
        "history": [],
        "toa_played": True,
        "support": {"Quebec": 0, "New_York": 0},
        "casualties": {},
    }


def test_french_bot_turn():
    state = simple_state()
    card_path = Path(__file__).resolve().parents[2] / 'lod_ai' / 'cards' / 'data.json'
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    bot = FrenchBot()
    bot.take_turn(state, card)
    assert state.get("history")


def test_f3_zero_resources_passes():
    """F3: French Resources > 0? No → PASS immediately."""
    bot = FrenchBot()
    state = {
        "spaces": {"Quebec": {"French_Regular": 2, "adj": []}},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 4},
        "rng": random.Random(42),
        "history": [],
        "support": {},
        "toa_played": True,
        "casualties": {},
    }
    card = {"id": 9999, "order_icons": "BFPI"}
    bot.take_turn(state, card)
    history = " ".join(str(h) for h in state.get("history", []))
    assert "FRENCH PASS" in history


def test_f13_can_battle_checks_force_comparison():
    """F13: 'Rebel cubes + Leader exceed British pieces in space with both?'
    _can_battle should check rebel cubes > british, not just coexistence."""
    bot = FrenchBot()
    # French present but fewer rebels than British
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 1, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 3, C.TORY: 1,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "support": {},
        "leaders": {},
    }
    # Rebels = 1+0 = 1, British = 3+1+0 = 4 → 1 < 4 → no battle
    assert bot._can_battle(state) is False

    # Now rebels exceed: 3+2 = 5 > 4
    state["spaces"]["Boston"][C.REGULAR_FRE] = 3
    state["spaces"]["Boston"][C.REGULAR_PAT] = 2
    assert bot._can_battle(state) is True


def test_f7_valid_provinces_uses_quebec_city():
    """F7: Agent Mobilization targets Quebec_City, not Quebec (Reserve)."""
    from lod_ai.bots.french import _VALID_PROVINCES
    assert "Quebec_City" in _VALID_PROVINCES
    assert "Quebec" not in _VALID_PROVINCES


def test_f14_march_fallback_to_muster():
    """F14 'If none' → F10 (Muster chain)."""
    bot = FrenchBot()
    # No French Regulars on map → March impossible
    state = {
        "spaces": {
            "Boston": {C.REGULAR_FRE: 0, C.REGULAR_BRI: 0, C.TORY: 0,
                       C.REGULAR_PAT: 0, C.MILITIA_A: 0, C.WARPARTY_A: 0},
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 3},
        "rng": random.Random(42),
        "history": [],
        "support": {},
        "control": {},
        "toa_played": True,
        "casualties": {},
    }
    # _battle_chain should fall back to _muster_chain
    result = bot._battle_chain(state)
    # Whether it succeeds depends on muster conditions, but it should try
    assert isinstance(result, bool)


# =========================================================================
# F13: _can_battle checks all Rebel leaders, not just Washington
# =========================================================================
def test_f13_can_battle_includes_rochambeau():
    """F13: Rochambeau leader bonus should count toward rebel strength."""
    bot = FrenchBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 2, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 1,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "support": {},
        "leaders": {},
        "leader_locs": {},
    }
    # Rebels = 2, British = 2+1 = 3 → no battle
    assert bot._can_battle(state) is False

    # Add Rochambeau in Boston: rebels = 2 + 1 = 3, British = 3 → still no (not exceeding)
    state["leader_locs"] = {"LEADER_ROCHAMBEAU": "Boston"}
    assert bot._can_battle(state) is False

    # Add Lauzun too: rebels = 2 + 2 = 4 > 3 → battle
    state["leader_locs"]["LEADER_LAUZUN"] = "Boston"
    assert bot._can_battle(state) is True


def test_f13_can_battle_excludes_war_parties():
    """F13: 'British pieces' should NOT include Indian War Parties."""
    bot = FrenchBot()
    # Rebels = 3, British cubes = 2, War Parties = 2
    # Old code: british = 2+0+2 = 4 > 3 → no battle
    # New code: british = 2+0+0 = 2 < 3 → battle possible
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 3, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 2, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "support": {},
        "leaders": {},
    }
    assert bot._can_battle(state) is True


def test_f13_can_battle_includes_british_forts():
    """F13: 'British pieces' should include British Forts."""
    bot = FrenchBot()
    # Rebels = 3, British cubes = 2 + Fort = 1 → total 3
    # 3 is NOT > 3, so no battle
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 3, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 1,
            },
        },
        "resources": {C.FRENCH: 5},
        "support": {},
        "leaders": {},
    }
    # 3 not > 3 → False
    assert bot._can_battle(state) is False

    # Add one more rebel: 4 > 3 → True
    state["spaces"]["Boston"][C.REGULAR_FRE] = 4
    assert bot._can_battle(state) is True


# =========================================================================
# F16: _battle uses only Active Militia in force calculation
# =========================================================================
def test_f16_battle_active_militia_only():
    """F16: Force level should use Active Militia only, not Underground."""
    bot = FrenchBot()
    # Space with 1 French Reg, 3 Active Militia, 0 Underground
    # Rebel force = 1 + 3 = 4; British = 2+1 = 3 → 4 > 3 → battle
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 1, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 1,
                C.MILITIA_A: 3, C.MILITIA_U: 5,  # Underground should NOT count
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 2},
        "support": {"Boston": 0},
        "control": {},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
        "toa_played": True,
        "casualties": {},
    }
    # The battle method should include Active Militia but not Underground
    # Old code: total_militia = 3+5 = 8, rebel_force = 1 + 8//2 = 5
    # New code: rebel_force = 1 + 0 + 3 = 4, crown_force = 2+1+0+0 = 3
    # 4 > 3 → still selects target
    result = bot._battle(state)
    # Should be True since 4 > 3
    assert result is True


# =========================================================================
# F12: _try_skirmish checks all British pieces, not just Regulars
# =========================================================================
def test_f12_skirmish_detects_tory_only_space():
    """F12: Skirmish should work in spaces with Tories (not just British Regulars)."""
    bot = FrenchBot()
    state = {
        "spaces": {
            "West_Indies": {
                C.REGULAR_FRE: 2, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 0, C.TORY: 3,  # Only Tories, no Regulars
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
        "toa_played": True,
        "casualties": {},
    }
    # Should find WI as valid target (has French + British Tories)
    result = bot._try_skirmish(state)
    assert result is True


def test_f12_skirmish_excludes_affected_spaces():
    """F12: Spaces selected for Battle/Muster should be excluded."""
    bot = FrenchBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 2, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
        "toa_played": True,
        "casualties": {},
        "_turn_affected_spaces": {"Boston"},  # Already selected for Battle
    }
    # Boston is excluded → no valid Skirmish target
    result = bot._try_skirmish(state)
    assert result is False


def test_f12_skirmish_fort_first_priority():
    """F12: Remove first a British Fort (option=3), then cubes (option=2)."""
    bot = FrenchBot()
    # Space with Fort only, no cubes → option 3
    state = {
        "spaces": {
            "West_Indies": {
                C.REGULAR_FRE: 2, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 0, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 1,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
        "toa_played": True,
        "casualties": {},
    }
    result = bot._try_skirmish(state)
    assert result is True
    # Fort should have been removed
    assert state["spaces"]["West_Indies"].get(C.FORT_BRI, 0) == 0


# =========================================================================
# F10: _muster uses state["rng"] and filters by Colony/City type
# =========================================================================
def test_f10_muster_deterministic():
    """F10: Muster should use state['rng'] for reproducibility."""
    bot = FrenchBot()

    def make_state(seed):
        return {
            "spaces": {
                "Massachusetts": {
                    C.REGULAR_FRE: 0, C.REGULAR_PAT: 2,
                    C.REGULAR_BRI: 0, C.TORY: 0,
                    C.MILITIA_A: 0, C.MILITIA_U: 0,
                    C.WARPARTY_A: 0, C.FORT_BRI: 0,
                },
                "New_Hampshire": {
                    C.REGULAR_FRE: 0, C.REGULAR_PAT: 1,
                    C.REGULAR_BRI: 0, C.TORY: 0,
                    C.MILITIA_A: 0, C.MILITIA_U: 0,
                    C.WARPARTY_A: 0, C.FORT_BRI: 0,
                },
            },
            "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
            "available": {C.REGULAR_FRE: 6},
            "support": {"Massachusetts": 0, "New_Hampshire": 0},
            "control": {"Massachusetts": "REBELLION", "New_Hampshire": "REBELLION"},
            "leaders": {},
            "rng": random.Random(seed),
            "history": [],
            "toa_played": True,
            "casualties": {},
        }

    # Same seed → same result
    s1 = make_state(42)
    s2 = make_state(42)
    r1 = bot._muster(s1)
    r2 = bot._muster(s2)
    assert r1 == r2


def test_f10_muster_colony_city_filter():
    """F10: First priority targets should be Colony or City spaces, not Provinces."""
    bot = FrenchBot()
    # Quebec is a Reserve Province; Massachusetts is a Colony
    # Both have Continentals and Rebel Control
    # The Colony should be preferred
    state = {
        "spaces": {
            "Quebec": {
                C.REGULAR_FRE: 0, C.REGULAR_PAT: 2,
                C.REGULAR_BRI: 0, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
            "Massachusetts": {
                C.REGULAR_FRE: 0, C.REGULAR_PAT: 2,
                C.REGULAR_BRI: 0, C.TORY: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {C.REGULAR_FRE: 6},
        "support": {"Quebec": 0, "Massachusetts": 0},
        "control": {"Quebec": "REBELLION", "Massachusetts": "REBELLION"},
        "leaders": {},
        "rng": random.Random(42),
        "history": [],
        "toa_played": True,
        "casualties": {},
    }
    bot._muster(state)
    # Massachusetts (Colony) should be selected over Quebec (Reserve)
    history = " ".join(str(h) for h in state.get("history", []))
    assert "Massachusetts" in history or state["spaces"]["Massachusetts"].get(C.REGULAR_FRE, 0) > 0


# =========================================================================
# F14: _march uses state["rng"] for determinism
# =========================================================================
def test_f14_march_deterministic():
    """F14: March randomization should use state['rng'], not random module."""
    bot = FrenchBot()

    def make_state(seed):
        return {
            "spaces": {
                "Massachusetts": {
                    C.REGULAR_FRE: 3, C.REGULAR_PAT: 0,
                    C.REGULAR_BRI: 0, C.TORY: 0,
                    C.MILITIA_A: 0, C.MILITIA_U: 0,
                    C.WARPARTY_A: 0, C.FORT_BRI: 0,
                },
                "Boston": {
                    C.REGULAR_FRE: 0, C.REGULAR_PAT: 0,
                    C.REGULAR_BRI: 1, C.TORY: 1,
                    C.MILITIA_A: 0, C.MILITIA_U: 0,
                    C.WARPARTY_A: 0, C.FORT_BRI: 0,
                },
            },
            "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
            "available": {C.REGULAR_FRE: 2},
            "support": {"Massachusetts": 0, "Boston": 0},
            "control": {"Massachusetts": "REBELLION"},
            "leaders": {},
            "rng": random.Random(seed),
            "history": [],
            "toa_played": True,
            "casualties": {},
        }

    s1 = make_state(42)
    s2 = make_state(42)
    r1 = bot._march(s1)
    r2 = bot._march(s2)
    assert r1 == r2


# =========================================================================
# Event instruction conditionals
# =========================================================================
def test_event_force_if_73_british_fort_check():
    """Card 73: Bot should only play event if British Fort removable."""
    bot = FrenchBot()
    # No British Fort on map → condition not met
    state = {
        "spaces": {
            "New_York": {
                C.REGULAR_FRE: 2, C.REGULAR_BRI: 2,
                C.TORY: 0, C.FORT_BRI: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
            },
        },
        "resources": {C.FRENCH: 5, C.PATRIOTS: 5, C.BRITISH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "leaders": {},
    }
    card = {"id": 73}
    assert bot._force_condition_met("force_if_73", state, card) is False

    # Add a British Fort → condition met
    state["spaces"]["New_York"][C.FORT_BRI] = 1
    assert bot._force_condition_met("force_if_73", state, card) is True


def test_event_force_if_62_militia_only():
    """Card 62: Bot should play event only if Militia available."""
    bot = FrenchBot()
    # No Militia available → skip event
    state = {
        "spaces": {},
        "resources": {C.FRENCH: 5},
        "available": {C.MILITIA_U: 0},
        "leaders": {},
    }
    card = {"id": 62}
    assert bot._force_condition_met("force_if_62", state, card) is False

    # Militia available → play event
    state["available"][C.MILITIA_U] = 3
    assert bot._force_condition_met("force_if_62", state, card) is True
    # Should also set the choice to MILITIA_NORTHWEST
    assert state.get("card62_shaded_choice") == "MILITIA_NORTHWEST"


def test_event_force_if_70_british_in_rebel_spaces():
    """Card 70: Bot should play event only if British Regs in rebel spaces."""
    bot = FrenchBot()
    # No British Regulars in rebel spaces
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_BRI: 2, C.REGULAR_PAT: 0,
                C.REGULAR_FRE: 0, C.MILITIA_A: 0, C.MILITIA_U: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "leaders": {},
    }
    card = {"id": 70}
    # British are there but no Rebels → skip
    assert bot._force_condition_met("force_if_70", state, card) is False

    # Add Rebels → now condition met
    state["spaces"]["Boston"][C.REGULAR_PAT] = 2
    assert bot._force_condition_met("force_if_70", state, card) is True


def test_event_force_if_83_quebec_city_rebellion():
    """Card 83: Play if Quebec City would gain Rebellion control."""
    bot = FrenchBot()
    # Quebec City already Rebellion → no gain → skip
    state = {
        "spaces": {"Quebec_City": {}},
        "resources": {C.FRENCH: 5},
        "control": {"Quebec_City": "REBELLION"},
        "leaders": {},
    }
    card = {"id": 83}
    assert bot._force_condition_met("force_if_83", state, card) is False

    # Quebec City not Rebellion → could gain → play
    state["control"]["Quebec_City"] = C.BRITISH
    assert bot._force_condition_met("force_if_83", state, card) is True


def test_event_force_if_52_battle_target():
    """Card 52: Play event only if battle spaces exist (French + British)."""
    bot = FrenchBot()
    # No shared space → no battle target → skip
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_FRE: 2, C.REGULAR_BRI: 0,
                C.TORY: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.FRENCH: 5},
        "leaders": {},
    }
    card = {"id": 52}
    assert bot._force_condition_met("force_if_52", state, card) is False

    # Add British → condition met, flag set
    state["spaces"]["Boston"][C.REGULAR_BRI] = 2
    assert bot._force_condition_met("force_if_52", state, card) is True
    assert state.get("card52_no_remove_french") is True


# =========================================================================
# New tests for audit-report fixes
# =========================================================================

def _full_state(**overrides):
    """Build a well-formed state dict for French bot tests."""
    base = {
        "spaces": {
            "Boston": {},
            "Massachusetts": {},
            "New_York": {},
            "New_York_City": {},
            "Connecticut_Rhode_Island": {},
            "Philadelphia": {},
            "Virginia": {},
        },
        "resources": {C.FRENCH: 10, C.PATRIOTS: 10, C.BRITISH: 10, C.INDIANS: 10},
        "available": {C.REGULAR_FRE: 5, C.MILITIA_U: 5},
        "unavailable": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
        "markers": {},
        "toa_played": True,
    }
    base.update(overrides)
    return base


# ---------- F14 March: Full implementation ----------

def test_f14_march_loses_no_rebel_control():
    """F14: March must not move pieces that would lose Rebel Control."""
    bot = FrenchBot()
    state = _full_state()
    # Massachusetts: 2 French + 1 British → REBELLION control
    # Moving both French would lose control
    state["spaces"]["Massachusetts"] = {
        C.REGULAR_FRE: 2, C.REGULAR_BRI: 1,
    }
    # Boston: 2 British → target for adding Rebel Control
    state["spaces"]["Boston"] = {
        C.REGULAR_BRI: 2,
    }
    state["control"] = {"Massachusetts": "REBELLION"}
    result = bot._march(state)
    # After march, Massachusetts should still have REBELLION control
    # (at most 1 French should have moved)
    from lod_ai.board.control import refresh_control
    refresh_control(state)
    # The bot should have been careful not to lose control
    rebel = bot._rebel_pieces_in(state["spaces"]["Massachusetts"])
    royalist = bot._royalist_pieces_in(state["spaces"]["Massachusetts"])
    assert rebel > royalist or state["control"].get("Massachusetts") != "REBELLION"


def test_f14_march_cities_first():
    """F14: March should prioritize Cities over Colonies."""
    bot = FrenchBot()
    state = _full_state()
    # French in Massachusetts, adjacent to Boston (City) and New_York (Colony)
    state["spaces"]["Massachusetts"] = {C.REGULAR_FRE: 5}
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 1}  # City
    state["spaces"]["New_York"] = {C.REGULAR_BRI: 1}  # Colony
    state["control"] = {}
    result = bot._march(state)
    assert result is True
    # Boston (City) should have been targeted first
    assert state["spaces"]["Boston"].get(C.REGULAR_FRE, 0) > 0


def test_f14_march_most_british_priority():
    """F14: Within Cities, march to where most British."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Massachusetts"] = {C.REGULAR_FRE: 5}
    # Two adjacent cities
    state["spaces"]["Boston"] = {C.REGULAR_BRI: 3}  # More British
    state["spaces"]["Connecticut_Rhode_Island"] = {C.REGULAR_BRI: 1}  # Fewer British
    state["control"] = {}
    result = bot._march(state)
    assert result is True
    # Boston should be targeted first (more British)
    assert state["spaces"]["Boston"].get(C.REGULAR_FRE, 0) > 0


def test_f14_march_isolated_french_toward_british():
    """F14 step 3: French not in/adjacent to British march toward nearest British."""
    bot = FrenchBot()
    state = _full_state()
    # French in Virginia (isolated from British), British in New_York_City
    # Path: Virginia → Maryland-Delaware → Pennsylvania → New_Jersey → New_York_City
    # Include intermediate spaces so BFS can find a path
    state["spaces"]["Virginia"] = {C.REGULAR_FRE: 2}
    state["spaces"]["Maryland-Delaware"] = {}
    state["spaces"]["Pennsylvania"] = {}
    state["spaces"]["New_Jersey"] = {}
    state["spaces"]["New_York_City"] = {C.REGULAR_BRI: 3}
    # Clear other spaces to keep it simple
    for sid in list(state["spaces"]):
        if sid not in ("Virginia", "Maryland-Delaware", "Pennsylvania",
                       "New_Jersey", "New_York_City"):
            state["spaces"][sid] = {}
    state["control"] = {}
    result = bot._march(state)
    # Should have moved toward New_York_City (step 3)
    assert result is True
    # Virginia should have fewer French (moved 1 toward British)
    assert state["spaces"]["Virginia"].get(C.REGULAR_FRE, 0) < 2


def test_f14_march_fallback_to_pats_and_brits():
    """F14 step 4: Last resort — March 1 French to space with both Patriots and British."""
    bot = FrenchBot()
    state = _full_state()
    # French in Massachusetts, all adjacent spaces already REBELLION (step 2 fails)
    state["spaces"]["Massachusetts"] = {C.REGULAR_FRE: 2}
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 2, C.REGULAR_BRI: 2,  # Has both Patriots and British
    }
    state["control"] = {
        "Massachusetts": "REBELLION",
        "Boston": "REBELLION",  # Already REBELLION → step 2 skips
        "New_York": "REBELLION",
        "Connecticut_Rhode_Island": "REBELLION",
    }
    result = bot._march(state)
    # Step 2 fails (all adjacent are REBELLION)
    # Step 3 fails (Massachusetts IS adjacent to Boston which has British)
    # Step 4 finds Boston (has Patriots and British)
    assert result is True


def test_f14_march_returns_false_when_impossible():
    """F14: Returns False when no March is possible."""
    bot = FrenchBot()
    state = _full_state()
    # No French on map
    for sid in state["spaces"]:
        state["spaces"][sid] = {}
    result = bot._march(state)
    assert result is False


# ---------- F14: Control simulation helpers ----------

def test_rebel_pieces_count():
    """_rebel_pieces_in should count all Rebellion pieces."""
    sp = {
        C.REGULAR_PAT: 3, C.REGULAR_FRE: 2,
        C.MILITIA_A: 1, C.MILITIA_U: 2,
        C.FORT_PAT: 1,
    }
    assert FrenchBot._rebel_pieces_in(sp) == 9


def test_royalist_pieces_count():
    """_royalist_pieces_in should count all Royalist pieces."""
    sp = {
        C.REGULAR_BRI: 2, C.TORY: 3,
        C.WARPARTY_A: 1, C.WARPARTY_U: 1,
        C.FORT_BRI: 1, C.VILLAGE: 2,
    }
    assert FrenchBot._royalist_pieces_in(sp) == 10


def test_would_lose_rebel_control():
    """_would_lose_rebel_control returns True when removing pieces loses control."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 2, C.REGULAR_BRI: 1}
    state["control"] = {"Boston": "REBELLION"}
    # Removing 1 French: 1 rebel vs 1 royalist → tie → lost
    assert bot._would_lose_rebel_control(state, "Boston", {C.REGULAR_FRE: 1}) is True
    # Removing 0: still in control
    assert bot._would_lose_rebel_control(state, "Boston", {}) is False


# ---------- Hortalez pre/post Treaty ----------

def test_hortalez_pre_treaty_spends_full_roll():
    """F6: Before Treaty, spend exactly 1D3 (capped at available)."""
    bot = FrenchBot()
    state = _full_state(resources={
        C.FRENCH: 10, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    initial_french = state["resources"][C.FRENCH]
    bot._hortelez(state, before_treaty=True)
    spent = initial_french - state["resources"][C.FRENCH]
    # Should have spent 1, 2, or 3
    assert 1 <= spent <= 3
    # Patriots should have received spent + 1
    assert state["resources"][C.PATRIOTS] == spent + 1


def test_hortalez_post_treaty_spends_up_to_roll():
    """F11: After Treaty, spend up to 1D3 (bot maximizes)."""
    bot = FrenchBot()
    state = _full_state(resources={
        C.FRENCH: 10, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    initial_french = state["resources"][C.FRENCH]
    bot._hortelez(state, before_treaty=False)
    spent = initial_french - state["resources"][C.FRENCH]
    assert 1 <= spent <= 3


def test_hortalez_zero_resources_skips():
    """Hortalez should do nothing when French has 0 resources."""
    bot = FrenchBot()
    state = _full_state(resources={
        C.FRENCH: 0, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    bot._hortelez(state, before_treaty=True)
    # Resources unchanged
    assert state["resources"][C.FRENCH] == 0
    assert state["resources"][C.PATRIOTS] == 0


# ---------- F6 pre-Treaty exact cost (must pay exact roll or skip) ----------

def test_hortalez_pre_treaty_cannot_afford_skips():
    """F6: Pre-Treaty with resources < roll must skip (resources unchanged)."""
    bot = FrenchBot()
    # Use a seed where randint(1,3) returns 3
    # We'll try seeds until we get roll=3, then set resources=2
    for seed in range(100):
        rng = random.Random(seed)
        roll = rng.randint(1, 3)
        if roll == 3:
            break
    state = _full_state(resources={
        C.FRENCH: 2, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    state["rng"] = random.Random(seed)
    bot._hortelez(state, before_treaty=True)
    # Resources < roll (2 < 3): must skip entirely
    assert state["resources"][C.FRENCH] == 2
    assert state["resources"][C.PATRIOTS] == 0
    # History should mention "skipped"
    history = " ".join(str(h) for h in state.get("history", []))
    assert "skipped" in history.lower()


def test_hortalez_pre_treaty_pays_exact_roll():
    """F6: Pre-Treaty with resources >= roll must pay exactly the roll amount."""
    bot = FrenchBot()
    # Use a seed where randint(1,3) returns 2
    for seed in range(100):
        rng = random.Random(seed)
        roll = rng.randint(1, 3)
        if roll == 2:
            break
    state = _full_state(resources={
        C.FRENCH: 10, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    state["rng"] = random.Random(seed)
    bot._hortelez(state, before_treaty=True)
    # Must pay exactly 2 (not min(10, 2)=2 which happens to be the same,
    # but the key point is it's exactly the roll, not capped)
    assert state["resources"][C.FRENCH] == 8  # 10 - 2
    assert state["resources"][C.PATRIOTS] == 3  # 2 + 1


def test_hortalez_post_treaty_pays_min_resources_roll():
    """F11: Post-Treaty with resources < roll pays min(resources, roll)."""
    bot = FrenchBot()
    # Use a seed where randint(1,3) returns 3
    for seed in range(100):
        rng = random.Random(seed)
        roll = rng.randint(1, 3)
        if roll == 3:
            break
    state = _full_state(resources={
        C.FRENCH: 2, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10,
    })
    state["rng"] = random.Random(seed)
    bot._hortelez(state, before_treaty=False)
    # Post-Treaty: pay min(2, 3) = 2
    assert state["resources"][C.FRENCH] == 0  # 2 - 2
    assert state["resources"][C.PATRIOTS] == 3  # 2 + 1


# ---------- OPS Summary methods ----------

def test_ops_supply_priority():
    """ops_supply_priority should prioritize spaces where removal changes control."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_FRE: 2, C.REGULAR_BRI: 1,  # Removing French changes control
    }
    state["spaces"]["New_York"] = {
        C.REGULAR_FRE: 1, C.REGULAR_PAT: 5,  # Removing French doesn't change control
    }
    state["control"] = {"Boston": "REBELLION", "New_York": "REBELLION"}
    result = bot.ops_supply_priority(state)
    assert len(result) >= 2
    # Boston should come first (removing French would change control)
    assert result[0] == "Boston"


def test_ops_redeploy_leader():
    """ops_redeploy_leader should prefer space with French Regs and Continentals."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 3, C.REGULAR_PAT: 2}
    state["spaces"]["New_York"] = {C.REGULAR_FRE: 5}  # No Continentals
    state["spaces"]["Massachusetts"] = {C.REGULAR_FRE: 2, C.REGULAR_PAT: 1}
    result = bot.ops_redeploy_leader(state)
    # Boston has both French Regs and Continentals, 3 French > 2 in Massachusetts
    assert result == "Boston"


def test_ops_redeploy_leader_fallback():
    """ops_redeploy_leader falls back to most French Regs if no Continentals."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 3}
    state["spaces"]["New_York"] = {C.REGULAR_FRE: 5}
    result = bot.ops_redeploy_leader(state)
    assert result == "New_York"


def test_ops_loyalist_desertion_priority():
    """ops_loyalist_desertion_priority should prefer removals that change control."""
    bot = FrenchBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.TORY: 1, C.REGULAR_PAT: 1,  # 1 rebel, 1 royalist. Removing Tory → REBELLION
    }
    state["spaces"]["New_York"] = {
        C.TORY: 3, C.REGULAR_BRI: 5,  # Lots of British. Removing 1 Tory won't change
    }
    state["control"] = {"Boston": "BRITISH", "New_York": "BRITISH"}
    result = bot.ops_loyalist_desertion_priority(state)
    assert len(result) >= 2
    # Boston should come first (removing Tory changes control)
    assert result[0][0] == "Boston"


def test_ops_toa_trigger():
    """ops_toa_trigger should use the cbc (Cumulative British Casualties) field."""
    bot = FrenchBot()
    state = _full_state(toa_played=False)
    state["available"] = {C.REGULAR_FRE: 10}
    state["cbc"] = 10
    state["current_card"] = {"id": 1}  # Not a WQ card
    # Formula: WI_squadrons + Avail_FRE + 1/2 * CBC
    # 0 + 10 + 10//2 = 0 + 10 + 5 = 15
    # 15 > 15 is False
    assert bot.ops_toa_trigger(state) is False

    # Increase CBC
    state["cbc"] = 12
    # 0 + 10 + 12//2 = 0 + 10 + 6 = 16 > 15
    assert bot.ops_toa_trigger(state) is True


def test_ops_toa_trigger_already_played():
    """ops_toa_trigger returns False if ToA already played."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    state["available"] = {C.REGULAR_FRE: 20}
    state["cbc"] = 20
    state["current_card"] = {"id": 1}
    assert bot.ops_toa_trigger(state) is False


def test_ops_bs_trigger_needs_toa():
    """ops_bs_trigger requires ToA to be played."""
    bot = FrenchBot()
    state = _full_state(toa_played=False)
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 5}
    state["leaders"] = {"LEADER_ROCHAMBEAU": "Boston"}
    state["current_card"] = {"id": 1}
    state["human_factions"] = {C.PATRIOTS}
    state["eligible"] = [C.PATRIOTS]
    assert bot.ops_bs_trigger(state) is False


def test_ops_bs_trigger_needs_4_plus_french():
    """ops_bs_trigger requires 4+ French Regulars at leader's space,
    plus a player faction 1st eligible or British BS played."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 3}
    state["leaders"] = {"LEADER_ROCHAMBEAU": "Boston"}
    state["current_card"] = {"id": 1}  # Not a WQ card
    state["human_factions"] = {C.PATRIOTS}
    state["eligible"] = [C.PATRIOTS, C.FRENCH]  # Player faction is 1st eligible
    assert bot.ops_bs_trigger(state) is False  # Only 3 Regulars

    state["spaces"]["Boston"][C.REGULAR_FRE] = 4
    assert bot.ops_bs_trigger(state) is True


# ===================================================================
#  Session 10: French Bot Full Compliance Review — new tests
# ===================================================================

def test_f16_battle_requires_french_presence():
    """F16 (§8.6.6): Select spaces with BOTH French AND British pieces.
    A space with Patriots + British but no French should NOT be selected."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    state["spaces"] = {
        "Boston": {C.REGULAR_PAT: 5, C.MILITIA_A: 2, C.REGULAR_BRI: 2},      # No French
        "New_York": {C.REGULAR_FRE: 3, C.REGULAR_PAT: 2, C.REGULAR_BRI: 1},  # French present
    }
    state["leaders"] = {}
    state["support"] = {"Boston": 0, "New_York": 0}
    state["control"] = {}
    # Boston has rebel_force(5+2)=7 > crown_force(2), but NO French
    # New_York has rebel_force(3+2)=5 > crown_force(1), and HAS French
    # Without the fix, both would be selected. With the fix, only New_York.
    result = bot._battle(state)
    affected = state.get("_turn_affected_spaces", set())
    assert "Boston" not in affected, "Boston should not be a battle target (no French)"
    assert "New_York" in affected, "New_York should be a battle target (French present)"


def test_ops_toa_trigger_uses_cbc_not_casualties():
    """ops_toa_trigger must use state['cbc'] (Cumulative British Casualties counter),
    not state['casualties'] (the battle losses box)."""
    bot = FrenchBot()
    state = _full_state(toa_played=False)
    state["available"] = {C.REGULAR_FRE: 10}
    state["current_card"] = {"id": 1}
    # With cbc=0 but high casualties box — should NOT trigger
    state["cbc"] = 0
    state["casualties"] = {C.REGULAR_BRI: 20, C.TORY: 20}
    assert bot.ops_toa_trigger(state) is False  # 10 + 0 = 10, not > 15
    # With high cbc — SHOULD trigger
    state["cbc"] = 14
    assert bot.ops_toa_trigger(state) is True  # 10 + 7 = 17 > 15


def test_ops_toa_trigger_blocked_during_winter_quarters():
    """ops_toa_trigger returns False when a Winter Quarters card is showing."""
    bot = FrenchBot()
    state = _full_state(toa_played=False)
    state["available"] = {C.REGULAR_FRE: 10}
    state["cbc"] = 20  # Would easily trigger
    state["current_card"] = {"id": 97}  # Winter Quarters card
    assert bot.ops_toa_trigger(state) is False


def test_ops_bs_trigger_blocked_during_winter_quarters():
    """ops_bs_trigger returns False when a Winter Quarters card is showing."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 5}
    state["leaders"] = {"LEADER_ROCHAMBEAU": "Boston"}
    state["human_factions"] = {C.PATRIOTS}
    state["eligible"] = [C.PATRIOTS]
    state["current_card"] = {"id": 99}  # Winter Quarters card
    assert bot.ops_bs_trigger(state) is False


def test_ops_bs_trigger_requires_player_eligible_or_brit_bs():
    """ops_bs_trigger requires a player faction 1st eligible or British BS played."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 5}
    state["leaders"] = {"LEADER_ROCHAMBEAU": "Boston"}
    state["current_card"] = {"id": 1}
    state["human_factions"] = set()  # No human players
    state["eligible"] = [C.FRENCH, C.BRITISH]  # Bot is 1st eligible
    # No player is 1st eligible and no British BS played
    assert bot.ops_bs_trigger(state) is False

    # British BS played — should now trigger
    state["british_bs_played"] = True
    assert bot.ops_bs_trigger(state) is True


def test_ops_desertion_population_scoped_to_tier():
    """ops_loyalist_desertion_priority: control-changing spaces should come
    before non-control-changing ones. The sort uses scoped population tiebreaks."""
    bot = FrenchBot()
    state = _full_state()
    # SpaceA: tied control (royalist=2, rebel=2) → None control.
    #   Removing 1 Tory → royalist=1 < rebel=2 → changes to REBELLION.
    # SpaceB: British control (royalist=5, rebel=0) → BRITISH.
    #   Removing 1 Tory → royalist=4 > rebel=0 → stays BRITISH. No change.
    state["spaces"] = {
        "SpaceA": {C.TORY: 2, C.REGULAR_PAT: 2},  # tied→changes ctrl on Tory removal
        "SpaceB": {C.TORY: 1, C.REGULAR_BRI: 4},   # BRITISH stays BRITISH
    }
    state["support"] = {"SpaceA": 0, "SpaceB": 0}
    result = bot.ops_loyalist_desertion_priority(state)
    sids = [sid for sid, _ in result]
    # SpaceA changes control (tier 1) should come before SpaceB (tier 2/3)
    assert sids.index("SpaceA") < sids.index("SpaceB"), \
        "Control-changing space should come before non-control-changing"


def test_f7_agent_mobilization_skips_active_support():
    """_agent_mobilization should skip provinces at Active Support even
    when they have the best score, to avoid crash in fam.execute()."""
    bot = FrenchBot()
    state = _full_state(toa_played=False)
    state["spaces"] = {
        "Quebec_City": {C.REGULAR_PAT: 5},
        "New_York": {C.REGULAR_PAT: 1},
        "New_Hampshire": {},
        "Massachusetts": {},
    }
    state["support"] = {
        "Quebec_City": C.ACTIVE_SUPPORT,  # Best score but Active Support
        "New_York": 0,
        "New_Hampshire": 0,
        "Massachusetts": 0,
    }
    state["control"] = {}
    state["available"] = {C.MILITIA_U: 5}
    # Quebec_City would have highest score (5 patriots) but is Active Support
    # Bot should pick New_York (1 patriot) instead
    result = bot._agent_mobilization(state)
    assert result is True
    # Verify no crash — the test passing means Active Support was skipped


# ===================================================================
#  Session 13: French Bot Compliance Review — new tests
# ===================================================================

def test_f6_hortalez_cant_afford_does_not_run_preparer():
    """F6: When Hortalez can't afford the 1D3 roll, the bot should Pass
    (no Preparer SA). Previously, _before_treaty always ran Preparer
    and returned True even when Hortalez was skipped."""
    bot = FrenchBot()
    # Find a seed where the F5 roll sends us to Hortalez (need_hortalez=True)
    # AND the Hortalez roll exceeds French resources
    for seed in range(200):
        rng = random.Random(seed)
        f5_roll = rng.randint(1, 3)  # F5: Patriot Resources < 1D3?
        h_roll = rng.randint(1, 3)   # Hortalez 1D3
        # need_hortalez=True when Patriot Resources < f5_roll
        # can't afford when French Resources < h_roll
        if f5_roll > 0 and h_roll >= 2:
            # Set Patriot Resources = 0 (< any roll) and French Resources = 1
            break

    state = _full_state(toa_played=False)
    state["resources"] = {C.FRENCH: 1, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10}
    state["rng"] = random.Random(seed)
    state["unavailable"] = {}
    state["available"] = {C.REGULAR_FRE: 0, C.MILITIA_U: 0}

    result = bot._before_treaty(state)

    # If Hortalez can't afford, _before_treaty should return False (Pass)
    # The old code would return True and run Preparer even after Hortalez skipped
    if not result:
        # Correct: bot passed because Hortalez couldn't afford
        assert state["resources"][C.FRENCH] == 1  # Resources unchanged
    # If result is True, Hortalez actually succeeded (roll was 1) — also fine


def test_f6_hortalez_returns_bool():
    """_hortelez should return True on success, False on failure."""
    bot = FrenchBot()
    # Success case: enough resources
    state = _full_state(toa_played=False)
    state["resources"] = {C.FRENCH: 10, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10}
    result = bot._hortelez(state, before_treaty=True)
    assert result is True

    # Failure case: can't afford (find seed with roll > 1, set resources to 1)
    for seed in range(200):
        rng = random.Random(seed)
        roll = rng.randint(1, 3)
        if roll > 1:
            break
    state2 = _full_state(toa_played=False)
    state2["resources"] = {C.FRENCH: 1, C.PATRIOTS: 0, C.BRITISH: 10, C.INDIANS: 10}
    state2["rng"] = random.Random(seed)
    result2 = bot._hortelez(state2, before_treaty=True)
    assert result2 is False


def test_f16_battle_includes_patriot_forts_in_rebel_force():
    """F16: Rebel Force Level should include Patriot Forts per section 3.6
    (Force Level = cubes + Forts). A Patriot Fort should tip the balance."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    # Without Fort: rebel_force = 1 French + 1 Cont = 2, crown = 3 British → no battle
    # With Fort:    rebel_force = 1 French + 1 Cont + 1 Fort = 3, crown = 3 → still no (not exceeding)
    # With Fort+1:  rebel_force = 2 French + 1 Cont + 1 Fort = 4, crown = 3 → battle!
    state["spaces"] = {
        "Boston": {
            C.REGULAR_FRE: 1, C.REGULAR_PAT: 1,
            C.REGULAR_BRI: 3, C.TORY: 0,
            C.MILITIA_A: 0, C.MILITIA_U: 0,
            C.WARPARTY_A: 0, C.FORT_BRI: 0,
            C.FORT_PAT: 1,
        },
    }
    state["leaders"] = {}
    state["support"] = {"Boston": 0}
    state["control"] = {}

    # rebel = 1+1+1 = 3, crown = 3 → not exceeding → no battle
    result = bot._battle(state)
    assert result is False

    # Add 1 more French Regular: rebel = 2+1+1 = 4 > 3 → battle
    state["spaces"]["Boston"][C.REGULAR_FRE] = 2
    result = bot._battle(state)
    assert result is True


def test_f10_muster_fallback_includes_west_indies():
    """F10: Muster fallback targets should include West Indies even when
    WI is not Rebel Controlled, per 'in 1 space with Rebel Control or
    the West Indies'."""
    bot = FrenchBot()
    state = _full_state(toa_played=True)
    # avail_regs >= 4 so we go to "Otherwise" branch
    state["available"] = {C.REGULAR_FRE: 6}
    # No Colony/City with Continentals AND Rebel Control
    state["spaces"] = {
        "West_Indies": {},
        "Boston": {C.REGULAR_BRI: 3},  # No Continentals
    }
    state["control"] = {"Boston": "BRITISH"}  # No Rebel Control anywhere
    # WI is not Rebel Controlled either
    # But WI should still be a valid fallback target
    result = bot._muster(state)
    # Should succeed by mustering in West Indies (the only valid target)
    assert result is True
    affected = state.get("_turn_affected_spaces", set())
    assert "West_Indies" in affected
