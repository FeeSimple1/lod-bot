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
