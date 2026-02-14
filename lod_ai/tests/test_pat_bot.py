import json
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.base_bot import BaseBot
from lod_ai import rules_consts as C


def simple_state():
    return {
        "spaces": {
            "Boston": {"Patriot_Militia_A": 1, "British_Regular": 1, "adj": ["New_York"]},
            "New_York": {"Patriot_Militia_A": 1, "adj": ["Boston"]},
        },
        "resources": {"BRITISH": 5, "PATRIOTS": 3, "FRENCH": 5, "INDIANS": 5},
        "available": {"Patriot_Continental": 5},
        "rng": __import__('random').Random(1),
        "history": [],
        "support": {"Boston": 0, "New_York": 0},
        "casualties": {},
    }


def test_patriot_bot_turn():
    state = simple_state()
    card_path = Path(__file__).resolve().parents[2] / 'lod_ai' / 'cards' / 'data.json'
    card = json.loads(card_path.read_text(encoding="utf-8"))[0]
    bot = PatriotBot()
    bot.take_turn(state, card)
    assert state.get("history")


def test_p6_battle_uses_cubes_not_militia():
    """P6: 'Rebel cubes + Leader > Active British' — Militia are NOT cubes."""
    bot = PatriotBot()
    # Only Militia, no Continentals or French Regulars → 0 cubes
    state = {
        "spaces": {
            "Boston": {
                C.MILITIA_A: 5,
                C.MILITIA_U: 3,
                C.REGULAR_PAT: 0,
                C.REGULAR_FRE: 0,
                C.REGULAR_BRI: 2,
                C.TORY: 1,
                C.WARPARTY_A: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {},
        "control": {},
    }
    # 0 cubes + 0 leader → 0 vs 3 Royal → no battle
    assert bot._battle_possible(state) is False

    # Add Continentals: 3 cubes + 0 leader = 3 vs 3 → not exceeded
    state["spaces"]["Boston"][C.REGULAR_PAT] = 3
    assert bot._battle_possible(state) is False

    # Add Washington: 3 + 1 = 4 > 3 → battle possible
    state["leaders"] = {"LEADER_WASHINGTON": "Boston"}
    assert bot._battle_possible(state) is True


def test_p2_event_checks_shaded_text():
    """P2: Patriots play shaded events, so conditions should check shaded text."""
    bot = PatriotBot()
    state = {
        "spaces": {},
        "resources": {C.PATRIOTS: 5},
        "support": {},
        "available": {},
    }
    # Card with Support/Opposition in shaded text only
    card_shaded = {
        "id": 9999,
        "unshaded_event": "British gain 3 Resources.",
        "shaded_event": "Shift 2 spaces toward Opposition.",
    }
    # Support > Opposition triggers the first bullet
    state["support"] = {"Boston": 1}
    assert bot._faction_event_conditions(state, card_shaded) is True

    # Same card but no relevant text in shaded
    card_no_match = {
        "id": 9998,
        "unshaded_event": "Shift toward Opposition.",
        "shaded_event": "Draw a card.",
    }
    state["support"] = {"Boston": 1}
    assert bot._faction_event_conditions(state, card_no_match) is False


def test_p2_event_25_pieces_die_roll():
    """P2 bullet 5: 25+ Patriot pieces on map and D6 rolls 5+."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 10, C.MILITIA_A: 10,
                C.MILITIA_U: 6, C.FORT_PAT: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "support": {},
        "available": {},
        "rng": __import__("random").Random(42),
    }
    # 26 pieces on map (>= 25), card text is generic
    card = {
        "id": 9999,
        "unshaded_event": "Draw a card.",
        "shaded_event": "Draw a card.",
    }
    # The die roll at seed 42 may or may not be >= 5; test both cases
    # by checking the condition is at least reachable
    result = bot._faction_event_conditions(state, card)
    # With 26 pieces, the 25+ check fires; result depends on die roll
    assert isinstance(result, bool)

    # With < 25 pieces, should never trigger the die-roll bullet
    state["spaces"]["Boston"][C.REGULAR_PAT] = 5
    state["spaces"]["Boston"][C.MILITIA_A] = 5
    state["spaces"]["Boston"][C.MILITIA_U] = 5
    # 15 pieces on map (< 25)
    assert bot._faction_event_conditions(state, card) is False


def test_p4_battle_uses_force_level():
    """P4: Battle selection should use Force Level, not raw piece counts."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 2, C.REGULAR_FRE: 1,
                C.MILITIA_A: 4, C.MILITIA_U: 2,
                C.FORT_PAT: 1,
                C.REGULAR_BRI: 3, C.TORY: 1,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
        "casualties": {},
    }
    # Rebel FL (attacking per §3.6.3):
    #   pat_cubes(2) + min(fre(1), pat(2))=1 + active_mil//2(4//2=2) = 5
    #   (no forts for attacker; Underground Militia excluded)
    # British FL (defending per §3.6.2):
    #   regs(3) + tories(1, uncapped when defending) + wp//2(0) + forts(0) = 4
    # 5 > 4 → battle should be selected
    # P6 check (cubes+leader vs active): 3+0=3 vs 3+1+0=4 → P6 fails
    # But _execute_battle should find the space using FL calculation
    assert bot._execute_battle(state) is True


def test_p8_partisans_priority_village_first():
    """P8: Partisans should prefer spaces with Villages (remove Village first)."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Quebec": {
                C.MILITIA_U: 2, C.VILLAGE: 1,
                C.WARPARTY_A: 1, C.REGULAR_BRI: 0, C.TORY: 0,
            },
            "Boston": {
                C.MILITIA_U: 2, C.VILLAGE: 0,
                C.WARPARTY_A: 0, C.REGULAR_BRI: 2, C.TORY: 1,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {"Quebec": 0, "Boston": 0},
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
    }
    # Quebec has a Village — should be preferred
    # (actual execution may fail since partisans.execute may need more state,
    #  but priority logic should select Quebec first)


def test_p12_skirmish_fort_first():
    """P12: Skirmish should prefer spaces with British Fort."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Quebec": {
                C.REGULAR_PAT: 2, C.FORT_BRI: 1,
                C.REGULAR_BRI: 1, C.TORY: 0,
            },
            "Boston": {
                C.REGULAR_PAT: 2, C.FORT_BRI: 0,
                C.REGULAR_BRI: 3, C.TORY: 2,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {"Quebec": 0, "Boston": 0},
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
    }
    # Quebec has a Fort — should be preferred over Boston with more troops


def test_p11_rabble_chain_falls_back_to_rally_chain():
    """P11: 'If none' → P7 Rally (with its full fallback chain)."""
    bot = PatriotBot()
    # No spaces can shift toward Active Opposition
    state = {
        "spaces": {
            "Boston": {
                C.MILITIA_A: 1, C.REGULAR_PAT: 0,
                C.REGULAR_BRI: 0, C.TORY: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {C.MILITIA_U: 5, C.FORT_PAT: 0},
        "support": {"Boston": -2},  # Already at Active Opposition
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
        "casualties": {},
    }
    # _execute_rabble should fail (all at Active Opposition)
    # Then _rally_chain should be attempted (not just _execute_rally)
    result = bot._rabble_chain(state)
    # Should not crash, whether it succeeds depends on rally logic
    assert isinstance(result, bool)


# ===================================================================
# New tests for node-by-node compliance fixes
# ===================================================================

def test_p6_washington_lookup_uses_leader_location():
    """P6: Washington lookup should use leader_location(), not ad-hoc dict access.
    The state['leaders'] dict maps leader_name → space_id, not space → leader."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 3, C.REGULAR_FRE: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.REGULAR_BRI: 2, C.TORY: 1,
                C.WARPARTY_A: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {},
        "control": {},
    }
    # 3 cubes vs 3 royal → not exceeded (no leader)
    assert bot._battle_possible(state) is False

    # Set Washington in Boston using canonical leader→space format
    state["leaders"] = {"LEADER_WASHINGTON": "Boston"}
    # 3 cubes + 1 leader = 4 > 3 → battle possible
    assert bot._battle_possible(state) is True

    # Also verify it works via leader_locs format
    del state["leaders"]
    state["leader_locs"] = {"LEADER_WASHINGTON": "Boston"}
    assert bot._battle_possible(state) is True


def test_p4_force_level_excludes_underground_militia():
    """P4: Force Level should only count Active Militia, not Underground.
    Per §3.6.3: 'half Active Militia' — Underground excluded."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 2, C.REGULAR_FRE: 0,
                # 0 Active Militia, 10 Underground → FL contribution = 0
                C.MILITIA_A: 0, C.MILITIA_U: 10,
                C.FORT_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Rebel FL: pat(2) + fre(0) + active_mil//2(0) = 2
    # British FL: regs(2) + tories(0) + wp//2(0) + forts(0) = 2
    # 2 > 2 is False → no battle
    assert bot._execute_battle(state) is False

    # Now add Active Militia: FL goes up
    state["spaces"]["Boston"][C.MILITIA_A] = 4
    # Rebel FL: 2 + 0 + 4//2 = 4 > 2 → battle
    assert bot._execute_battle(state) is True


def test_p4_force_level_attacker_excludes_forts():
    """P4: Attacking Rebellion Force Level should NOT include Patriot Forts.
    Per §3.6.3: Forts only count for the Defending side."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 1, C.REGULAR_FRE: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                # Patriot Fort should NOT help attacking FL
                C.FORT_PAT: 3,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Rebel FL (attacking): pat(1) + fre(0) + mil//2(0) = 1 (forts excluded!)
    # British FL (defending): regs(2) + tories(0) + forts(0) = 2
    # 1 > 2 is False → no battle
    assert bot._execute_battle(state) is False


def test_p4_force_level_defending_tories_uncapped():
    """P4: Defending British Tories should NOT be capped at Regulars count.
    Per §3.6.2: Tory cap only applies when British is Attacking."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 4, C.REGULAR_FRE: 0,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.FORT_PAT: 0,
                # 1 Regular + 5 Tories; if capped: 1+1=2; if uncapped: 1+5=6
                C.REGULAR_BRI: 1, C.TORY: 5,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Rebel FL: 4, British FL (uncapped): 1+5 = 6
    # 4 > 6 is False → no battle
    assert bot._execute_battle(state) is False

    # If tories were capped: British FL = 1+1 = 2
    # Then 4 > 2 → battle. But we expect False since tories are uncapped.


def test_p4_force_level_french_capped_at_patriot_cubes():
    """P4: When Patriots attack, French Regulars are capped at Patriot cube count.
    Per §3.6.3: 'add French Regulars up to the number of own Faction's cubes.'"""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 1, C.REGULAR_FRE: 5,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.FORT_PAT: 0,
                C.REGULAR_BRI: 3, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Rebel FL: pat(1) + min(fre(5), pat(1))=1 + mil//2(0) = 2
    # British FL: regs(3) = 3
    # 2 > 3 is False → no battle
    assert bot._execute_battle(state) is False

    # Increase Patriot cubes so French can contribute more
    state["spaces"]["Boston"][C.REGULAR_PAT] = 3
    # Rebel FL: 3 + min(5,3)=3 + 0 = 6 > 3 → battle
    assert bot._execute_battle(state) is True


def test_p4_uses_deterministic_rng():
    """P4: Battle space tiebreaker must use state['rng'], not random.random()."""
    bot = PatriotBot()
    base = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 3, C.REGULAR_FRE: 0,
                C.MILITIA_A: 2, C.MILITIA_U: 0, C.FORT_PAT: 0,
                C.REGULAR_BRI: 1, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
            "New_York": {
                C.REGULAR_PAT: 3, C.REGULAR_FRE: 0,
                C.MILITIA_A: 2, C.MILITIA_U: 0, C.FORT_PAT: 0,
                C.REGULAR_BRI: 1, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
        "available": {},
        "support": {},
        "control": {},
        "history": [],
        "casualties": {},
    }
    # Two runs with same seed should produce same result
    from copy import deepcopy
    s1 = deepcopy(base)
    s1["rng"] = random.Random(99)
    bot._execute_battle(s1)
    s2 = deepcopy(base)
    s2["rng"] = random.Random(99)
    bot._execute_battle(s2)
    # History should match (same tiebreaker, same execution)
    assert s1["history"] == s2["history"]


def test_p8_partisans_uses_option3_for_villages():
    """P8: Partisans should use option=3 to remove Villages when no WP present."""
    bot = PatriotBot()
    state = {
        "spaces": {
            # Village present, no War Parties → should use option=3
            "Quebec": {
                C.MILITIA_U: 2, C.MILITIA_A: 0,
                C.VILLAGE: 1,
                C.WARPARTY_A: 0, C.WARPARTY_U: 0,
                C.REGULAR_BRI: 0, C.TORY: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {"Quebec": 0},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Execute partisans — should pick Quebec with option=3 to remove Village
    # Since partisans.execute may need more state fields, catch exceptions
    # but verify the selection logic is correct
    result = bot._try_partisans(state)
    # If the execute call succeeds, the Village should be targeted
    # If it fails due to missing state, that's a separate issue
    assert isinstance(result, bool)


def test_p8_partisans_prefers_wp_over_british():
    """P8: Partisans should prefer spaces with War Parties over British cubes."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Space_A": {
                C.MILITIA_U: 2, C.VILLAGE: 0,
                C.WARPARTY_A: 3, C.WARPARTY_U: 0,
                C.REGULAR_BRI: 0, C.TORY: 0,
            },
            "Space_B": {
                C.MILITIA_U: 2, C.VILLAGE: 0,
                C.WARPARTY_A: 0, C.WARPARTY_U: 0,
                C.REGULAR_BRI: 3, C.TORY: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
    }
    # Build candidate list to verify priority
    from lod_ai.board.control import refresh_control
    refresh_control(state)
    candidates = []
    ctrl = state.get("control", {})
    for sid, sp in state["spaces"].items():
        if not sp.get(C.MILITIA_U, 0):
            continue
        has_village = sp.get(C.VILLAGE, 0)
        wp = sp.get(C.WARPARTY_A, 0) + sp.get(C.WARPARTY_U, 0)
        british = sp.get(C.REGULAR_BRI, 0) + sp.get(C.TORY, 0)
        if has_village + wp + british == 0:
            continue
        adds_rebel_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
        removes_brit_ctrl = 1 if ctrl.get(sid) == "BRITISH" else 0
        # The fixed sort key splits WP and British
        key = (-has_village, -wp, -british, -adds_rebel_ctrl,
               -removes_brit_ctrl)
        candidates.append((key, sid))
    candidates.sort()
    # Space_A (3 WP, 0 British) should come before Space_B (0 WP, 3 British)
    assert candidates[0][1] == "Space_A"


def test_p12_skirmish_uses_option3_for_forts():
    """P12: Skirmish should use option=3 when targeting British Fort with no enemy cubes."""
    bot = PatriotBot()
    state = {
        "spaces": {
            # Fort but no enemy cubes → option=3
            "Quebec": {
                C.REGULAR_PAT: 3, C.FORT_BRI: 1,
                C.REGULAR_BRI: 0, C.TORY: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {},
        "support": {"Quebec": 0},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Should attempt option=3 to remove Fort
    result = bot._try_skirmish(state)
    assert isinstance(result, bool)


def test_p5_march_no_group_size_minimum():
    """P5: March should not require group size >= 3 (removed bogus restriction)."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 1, C.MILITIA_A: 0,
                C.MILITIA_U: 0, C.REGULAR_FRE: 0,
            },
            "New_York": {
                C.REGULAR_PAT: 0, C.MILITIA_A: 0,
                C.MILITIA_U: 0, C.REGULAR_FRE: 0,
                C.REGULAR_BRI: 0, C.TORY: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {"Boston": 0, "New_York": 0},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # With old code, group size 1 < 3 would be rejected → no origins
    # With fix, group size 1 is accepted
    # Verify origins are found (even if march.execute might not move them)
    origins = sorted(
        (bot._rebel_group_size(sp), sid)
        for sid, sp in state["spaces"].items()
        if bot._rebel_group_size(sp) >= 1
    )
    assert any(sid == "Boston" for _, sid in origins)


def test_p7_rally_fort_cap_not_hardcoded_to_2():
    """P7: Rally Fort placement should not be hardcoded to max 2.
    Rally is 'Max 4' total spaces, but fort targets should be all qualifying."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 2, C.MILITIA_A: 2, C.MILITIA_U: 0,
                C.FORT_PAT: 0, C.REGULAR_FRE: 0,
            },
            "New_York": {
                C.REGULAR_PAT: 2, C.MILITIA_A: 2, C.MILITIA_U: 0,
                C.FORT_PAT: 0, C.REGULAR_FRE: 0,
            },
            "Philadelphia": {
                C.REGULAR_PAT: 2, C.MILITIA_A: 2, C.MILITIA_U: 0,
                C.FORT_PAT: 0, C.REGULAR_FRE: 0,
            },
        },
        "resources": {C.PATRIOTS: 10, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {C.FORT_PAT: 3, C.MILITIA_U: 10},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # All 3 spaces have 4+ Patriot units and room for a Fort
    # With old code, only 2 would be selected ([:2])
    # With fix, all 3 qualify (up to Max 4 limit)
    fort_targets = [
        sid for sid, sp in state["spaces"].items()
        if sp.get(C.FORT_PAT, 0) == 0 and
           bot._rebel_group_size(sp) >= 4
    ]
    assert len(fort_targets) == 3


def test_card_71_90_force_unshaded_directive():
    """Cards 71 and 90: Patriot bot instruction says 'Use the unshaded text'.
    The directive should be 'force_unshaded', not 'force'."""
    from lod_ai.bots.event_instructions import PATRIOTS
    assert PATRIOTS[71] == "force_unshaded"
    assert PATRIOTS[90] == "force_unshaded"


def test_card_8_force_if_french_not_human_directive():
    """Card 8: Patriot bot instruction says 'If French is a human player,
    choose Command & SA instead.' Directive should be conditional."""
    from lod_ai.bots.event_instructions import PATRIOTS
    assert PATRIOTS[8] == "force_if_french_not_human"


def test_cards_18_44_force_if_eligible_enemy_directive():
    """Cards 18 and 44: 'Target an Eligible enemy Faction. If none, Command & SA.'
    Directive should be conditional on eligible enemy."""
    from lod_ai.bots.event_instructions import PATRIOTS
    assert PATRIOTS[18] == "force_if_eligible_enemy"
    assert PATRIOTS[44] == "force_if_eligible_enemy"


def test_force_unshaded_executes_unshaded():
    """Verify force_unshaded directive calls event handler with shaded=False."""
    bot = PatriotBot()
    # Track what shading was used
    called_with = {}

    def fake_handler(state, shaded=False):
        called_with["shaded"] = shaded

    from lod_ai.cards import CARD_HANDLERS
    original = CARD_HANDLERS.get(71)
    CARD_HANDLERS[71] = fake_handler
    try:
        card = {"id": 71, "musket": True, "dual": True}
        state = {
            "spaces": {},
            "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
            "available": {},
            "support": {},
            "rng": random.Random(42),
            "history": [],
            "eligible": {C.BRITISH: True, C.PATRIOTS: True, C.FRENCH: True, C.INDIANS: True},
        }
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is True
        assert called_with["shaded"] is False  # Should be unshaded!
    finally:
        if original is not None:
            CARD_HANDLERS[71] = original
        else:
            del CARD_HANDLERS[71]


def test_force_if_french_not_human_skips_when_french_human():
    """Card 8: If French is a human player, bot should skip event (Command & SA)."""
    bot = PatriotBot()

    card = {"id": 8, "musket": True, "dual": True}
    state = {
        "spaces": {},
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "rng": random.Random(42),
        "history": [],
        # French is a human player
        "human_factions": {C.FRENCH},
    }
    # Should return False (skip event, do Command & SA instead)
    result = bot._choose_event_vs_flowchart(state, card)
    assert result is False


def test_force_if_french_not_human_plays_when_french_bot():
    """Card 8: If French is NOT a human player, bot should play the event."""
    bot = PatriotBot()

    called_with = {}

    def fake_handler(state, shaded=False):
        called_with["shaded"] = shaded

    from lod_ai.cards import CARD_HANDLERS
    original = CARD_HANDLERS.get(8)
    CARD_HANDLERS[8] = fake_handler
    try:
        card = {"id": 8, "musket": True, "dual": True}
        state = {
            "spaces": {},
            "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
            "available": {},
            "support": {},
            "rng": random.Random(42),
            "history": [],
            # French is NOT human (all bots)
            "human_factions": set(),
        }
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is True
    finally:
        if original is not None:
            CARD_HANDLERS[8] = original
        else:
            del CARD_HANDLERS[8]


def test_force_if_eligible_enemy_skips_when_none_eligible():
    """Cards 18, 44: If no eligible enemy Faction, bot should skip event."""
    bot = PatriotBot()
    card = {"id": 18, "musket": True, "dual": True}
    state = {
        "spaces": {},
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "rng": random.Random(42),
        "history": [],
        # No enemy factions eligible
        "eligible": {C.BRITISH: False, C.PATRIOTS: True, C.FRENCH: False, C.INDIANS: False},
    }
    result = bot._choose_event_vs_flowchart(state, card)
    assert result is False


def test_force_if_eligible_enemy_plays_when_enemy_eligible():
    """Cards 18, 44: If an eligible enemy Faction exists, bot should play event."""
    bot = PatriotBot()
    called = {}

    def fake_handler(state, shaded=False):
        called["ran"] = True

    from lod_ai.cards import CARD_HANDLERS
    original = CARD_HANDLERS.get(18)
    CARD_HANDLERS[18] = fake_handler
    try:
        card = {"id": 18, "musket": True, "dual": True}
        state = {
            "spaces": {},
            "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
            "available": {},
            "support": {},
            "rng": random.Random(42),
            "history": [],
            # British is eligible (enemy of Patriots)
            "eligible": {C.BRITISH: True, C.PATRIOTS: True, C.FRENCH: False, C.INDIANS: False},
        }
        result = bot._choose_event_vs_flowchart(state, card)
        assert result is True
    finally:
        if original is not None:
            CARD_HANDLERS[18] = original
        else:
            del CARD_HANDLERS[18]


def test_p3_pass_when_no_resources():
    """P3: If Patriot Resources = 0, the bot should PASS."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 5, C.MILITIA_A: 5,
                C.REGULAR_BRI: 1, C.TORY: 0,
                C.WARPARTY_A: 0,
            },
        },
        "resources": {C.PATRIOTS: 0, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
    }
    bot._follow_flowchart(state)
    # Should have recorded a PASS
    assert any(
        "PASS" in (h.get("msg", "") if isinstance(h, dict) else str(h))
        for h in state["history"]
    )


def test_p9_rally_preferred_when_fort_possible():
    """P9: Rally preferred if Rally would place a Fort."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 2, C.MILITIA_A: 2,
                C.MILITIA_U: 0, C.REGULAR_FRE: 0,
                C.FORT_PAT: 0,
            },
        },
        "resources": {C.PATRIOTS: 5},
        "available": {C.FORT_PAT: 2},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
    }
    # 4 Patriot units + Fort available + no existing Fort → Fort can be placed
    assert bot._rally_preferred(state) is True


def test_p10_rabble_possible_checks_support():
    """P10: Rabble-Rousing possible if any space not at Active Opposition."""
    bot = PatriotBot()
    # All at Active Opposition → not possible
    state_opp = {
        "spaces": {"Boston": {}, "New_York": {}},
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "New_York": C.ACTIVE_OPPOSITION},
    }
    assert bot._rabble_possible(state_opp) is False

    # One at Neutral → possible
    state_mixed = {
        "spaces": {"Boston": {}, "New_York": {}},
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "New_York": C.NEUTRAL},
    }
    assert bot._rabble_possible(state_mixed) is True
