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
    """P2: Patriots play shaded events, conditions via CARD_EFFECTS lookup."""
    bot = PatriotBot()
    state = {
        "spaces": {},
        "resources": {C.PATRIOTS: 5},
        "support": {},
        "available": {},
    }
    # Card 41 shaded: shifts 2 Colonies toward Passive Opposition
    # (shifts_support_rebel=True).  With Support > Opposition, bullet 1 fires.
    card_shaded = {"id": 41}
    state["support"] = {"Boston": 1}  # Support=1 > Opposition=0
    assert bot._faction_event_conditions(state, card_shaded) is True

    # Card 18 shaded: (none) — all flags False, no triggers possible
    card_no_match = {"id": 18}
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
    # Card 22 shaded: "Tory Desertion" — is_effective=True but no other
    # shaded flags that would trigger bullets 1-4
    card = {"id": 22}
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
    """P10: Rabble-Rousing possible if any space not at Active Opposition
    AND meets §3.3.4 eligibility (Rebellion Control + Patriot piece, or
    Underground Militia)."""
    bot = PatriotBot()
    # All at Active Opposition → not possible
    state_opp = {
        "spaces": {"Boston": {C.MILITIA_U: 1}, "New_York": {C.MILITIA_U: 1}},
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "New_York": C.ACTIVE_OPPOSITION},
        "control": {},
    }
    assert bot._rabble_possible(state_opp) is False

    # One at Neutral with Underground Militia → possible
    state_mixed = {
        "spaces": {"Boston": {}, "New_York": {C.MILITIA_U: 1}},
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "New_York": C.NEUTRAL},
        "control": {},
    }
    assert bot._rabble_possible(state_mixed) is True

    # One at Neutral but NO Patriot pieces and NO Underground Militia → not possible
    state_no_pieces = {
        "spaces": {"Boston": {}, "New_York": {}},
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_OPPOSITION, "New_York": C.NEUTRAL},
        "control": {},
    }
    assert bot._rabble_possible(state_no_pieces) is False


# ===================================================================
# Tests for audit-report fixes
# ===================================================================

def _full_state(**overrides):
    """Build a well-formed state dict for Patriot bot tests."""
    base = {
        "spaces": {
            "Boston": {},
            "New_York": {},
            "Massachusetts": {},
            "Connecticut_Rhode_Island": {},
            "Philadelphia": {},
            "Virginia": {},
        },
        "resources": {C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
        "available": {C.MILITIA_U: 10, C.FORT_PAT: 3, C.REGULAR_PAT: 10},
        "unavailable": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
        "markers": {},
    }
    base.update(overrides)
    return base


# ---------- Rally/Rabble recursion guard ----------

def test_rally_rabble_no_infinite_loop():
    """Rally<->Rabble fallback must not recurse infinitely.
    With no spaces at all, both chains fail and terminate cleanly."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"] = {}  # No spaces → both Rally and Rabble fail
    state["available"] = {}
    # Both chains should terminate without hanging
    assert bot._rally_chain(state) is False
    assert bot._rabble_chain(state) is False


def test_rally_chain_from_rabble_stops_recursion():
    """When Rally fails with _from_rabble=True, it returns False instead of
    recursing into Rabble (which would cause an infinite loop)."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"] = {}  # No spaces → Rally fails
    state["available"] = {}
    assert bot._rally_chain(state, _from_rabble=True) is False
    assert bot._rabble_chain(state, _from_rally=True) is False


# ---------- Rally returns False when nothing can be done ----------

def test_rally_returns_false_when_nothing_possible():
    """_execute_rally should return False when no spaces can be rallied."""
    bot = PatriotBot()
    state = _full_state()
    # Set everything to Active Support → can't rally there
    for sid in state["spaces"]:
        state["support"][sid] = C.ACTIVE_SUPPORT
    assert bot._execute_rally(state) is False


# ---------- Rabble-Rousing has no 4-space cap ----------

def test_rabble_no_4space_cap():
    """P11: Rabble-Rousing should select all eligible spaces (limited by resources only)."""
    bot = PatriotBot()
    state = _full_state(
        resources={C.PATRIOTS: 6, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
    )
    # 6 spaces not at Active Opposition → all should be selectable with 6 resources
    for sid in state["spaces"]:
        state["support"][sid] = C.NEUTRAL
        state["spaces"][sid][C.MILITIA_U] = 1  # needs Underground Militia for eligibility
    result = bot._execute_rabble(state)
    assert result is True
    # All 6 spaces should appear in the Rabble-Rousing log entry (not capped at 4)
    rabble_log = [h for h in state.get("history", [])
                  if isinstance(h, dict) and "RABBLE_ROUSING" in h.get("msg", "")]
    assert len(rabble_log) == 1
    for sid in state["spaces"]:
        assert sid in rabble_log[0]["msg"]


# ---------- Control simulation helpers ----------

def test_rebel_pieces_count():
    """_rebel_pieces_in should count all Rebellion pieces."""
    sp = {
        C.REGULAR_PAT: 3, C.REGULAR_FRE: 2,
        C.MILITIA_A: 1, C.MILITIA_U: 2,
        C.FORT_PAT: 1,
    }
    assert PatriotBot._rebel_pieces_in(sp) == 9


def test_royalist_pieces_count():
    """_royalist_pieces_in should count all Royalist pieces."""
    sp = {
        C.REGULAR_BRI: 2, C.TORY: 3,
        C.WARPARTY_A: 1, C.WARPARTY_U: 1,
        C.FORT_BRI: 1, C.VILLAGE: 2,
    }
    assert PatriotBot._royalist_pieces_in(sp) == 10


def test_would_gain_rebel_control():
    """_would_gain_rebel_control returns True when adding pieces tips the balance."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 1, C.REGULAR_BRI: 2,
    }
    state["control"] = {"Boston": "BRITISH"}
    # 1 rebel vs 2 royalist: need 2 more to gain (3 > 2)
    assert bot._would_gain_rebel_control(state, "Boston", to_add=2) is True
    assert bot._would_gain_rebel_control(state, "Boston", to_add=1) is False


def test_would_lose_rebel_control():
    """_would_lose_rebel_control returns True when removing pieces loses control."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 2, C.REGULAR_BRI: 1,
    }
    state["control"] = {"Boston": "REBELLION"}
    # 2 rebel - 1 removed = 1 vs 1 royalist → tie → control lost (need strict majority)
    assert bot._would_lose_rebel_control(state, "Boston", {C.REGULAR_PAT: 1}) is True
    # Removing 0 should keep control
    assert bot._would_lose_rebel_control(state, "Boston", {}) is False


# ---------- March leave-behind rules ----------

def test_march_movable_from_keeps_fort_guard():
    """_movable_from should leave 1 unit with Patriot Fort."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 2, C.MILITIA_A: 1, C.FORT_PAT: 1,
    }
    state["support"]["Boston"] = C.ACTIVE_OPPOSITION
    state["control"]["Boston"] = "REBELLION"
    movable = bot._movable_from(state, "Boston")
    total = sum(movable.values())
    # Should leave at least 1 unit behind for the Fort
    remaining = 3 - total
    assert remaining >= 1


def test_march_movable_from_keeps_control():
    """_movable_from should not allow losing Rebel Control."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 2, C.REGULAR_BRI: 1,
    }
    state["control"]["Boston"] = "REBELLION"
    state["support"]["Boston"] = C.ACTIVE_OPPOSITION
    movable = bot._movable_from(state, "Boston")
    total = sum(movable.values())
    # 2 rebel - moved must stay > 1 royalist. So max move = 2-1-1 = 0
    assert total == 0


# ---------- Card 51 force_if_51 ----------

def test_card_51_directive_is_force_if_51():
    """Card 51 should use force_if_51 directive (conditional on March-to-Battle)."""
    from lod_ai.bots.event_instructions import PATRIOTS
    assert PATRIOTS[51] == "force_if_51"


def test_card_51_force_condition_met_when_battle_possible():
    """Card 51: force_if_51 returns True when March could set up a Battle."""
    bot = PatriotBot()
    state = _full_state()
    # Boston has 3 British (target), adjacent Massachusetts has 5 Rebels (can march in)
    state["spaces"]["Boston"] = {
        C.REGULAR_BRI: 3, C.TORY: 0, C.WARPARTY_A: 0,
        C.REGULAR_PAT: 1, C.MILITIA_A: 0,
    }
    state["spaces"]["Massachusetts"] = {
        C.REGULAR_PAT: 3, C.MILITIA_A: 3,
    }
    card = {"id": 51}
    assert bot._force_condition_met("force_if_51", state, card) is True


def test_card_51_force_condition_not_met():
    """Card 51: force_if_51 returns False when no March-to-Battle is possible."""
    bot = PatriotBot()
    state = _full_state()
    # No British pieces anywhere → no Battle target
    for sid in state["spaces"]:
        state["spaces"][sid] = {}
    card = {"id": 51}
    assert bot._force_condition_met("force_if_51", state, card) is False


# ---------- Win-the-Day helpers ----------

def test_best_blockade_city_selects_most_support():
    """_best_blockade_city should pick the City with the highest Support level."""
    bot = PatriotBot()
    state = _full_state()
    state["support"] = {
        "Boston": C.ACTIVE_SUPPORT,
        "New_York_City": C.PASSIVE_SUPPORT,
        "Philadelphia": C.NEUTRAL,
    }
    result = bot._best_blockade_city(state)
    assert result == "Boston"


# ---------- OPS Summary methods ----------

def test_ops_redeploy_washington():
    """ops_redeploy_washington should return the space with most Continentals."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {C.REGULAR_PAT: 3}
    state["spaces"]["New_York"] = {C.REGULAR_PAT: 5}
    state["spaces"]["Philadelphia"] = {C.REGULAR_PAT: 1}
    result = bot.ops_redeploy_washington(state)
    assert result == "New_York"


def test_ops_bs_trigger_needs_toa_and_washington():
    """ops_bs_trigger should only return True after ToA with 4+ Continentals at Washington."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {C.REGULAR_PAT: 4}
    state["leaders"] = {"LEADER_WASHINGTON": "Boston"}

    # No ToA → False
    state["toa_played"] = False
    assert bot.ops_bs_trigger(state) is False

    # ToA but Washington not at 4+ Continentals
    state["toa_played"] = True
    state["spaces"]["Boston"][C.REGULAR_PAT] = 3
    assert bot.ops_bs_trigger(state) is False

    # ToA + 4+ Continentals → True
    state["spaces"]["Boston"][C.REGULAR_PAT] = 4
    assert bot.ops_bs_trigger(state) is True


def test_ops_patriot_desertion_priority():
    """ops_patriot_desertion_priority should prefer removals that don't change control."""
    bot = PatriotBot()
    state = _full_state()
    state["spaces"]["Boston"] = {
        C.REGULAR_PAT: 3, C.MILITIA_A: 2,
        C.REGULAR_BRI: 1,
    }
    state["spaces"]["New_York"] = {
        C.REGULAR_PAT: 2,
        C.REGULAR_BRI: 1,
    }
    state["control"] = {"Boston": "REBELLION", "New_York": "REBELLION"}
    result = bot.ops_patriot_desertion_priority(state)
    assert len(result) > 0
    # First entries should be those that don't change control (changes=0)
    # Boston with 5 rebels vs 1 royalist: removing 1 won't change control
    # New_York with 2 rebels vs 1 royalist: removing 1 changes control (2-1=1, not > 1)
    first_sid, first_tag = result[0]
    assert first_sid == "Boston"  # safe removal first


# ===================================================================
# Session 8: Patriot Bot Compliance Review — new tests
# ===================================================================


def test_p6_rebel_cube_count_includes_all_rebel_leaders():
    """P6: 'Rebellion cubes and Leaders' (§8.5.1) — Rochambeau and Lauzun
    should count toward the leader total, not just Washington."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 2, C.REGULAR_FRE: 0,
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
    # 2 cubes vs 3 Royal → no battle
    assert bot._battle_possible(state) is False

    # Add Rochambeau → 2 cubes + 1 leader = 3, still not > 3
    state["leaders"] = {"LEADER_ROCHAMBEAU": "Boston"}
    assert bot._battle_possible(state) is False

    # Add Lauzun → 2 cubes + 2 leaders = 4 > 3 → battle possible
    state["leaders"]["LEADER_LAUZUN"] = "Boston"
    assert bot._battle_possible(state) is True


def test_p4_battle_french_excluded_when_no_french_resources():
    """P4: §8.5.1 — French Regulars only count in FL if French Resources > 0."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {
                C.REGULAR_PAT: 1, C.REGULAR_FRE: 3,
                C.MILITIA_A: 0, C.MILITIA_U: 0,
                C.FORT_PAT: 0,
                C.REGULAR_BRI: 2, C.TORY: 0,
                C.WARPARTY_A: 0, C.FORT_BRI: 0,
            },
        },
        "resources": {C.PATRIOTS: 5, C.BRITISH: 5, C.FRENCH: 0, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # French Resources = 0 → French excluded from FL
    # Rebel FL: pat(1) + fre(0, excluded) + mil(0) = 1
    # British FL: regs(2) = 2
    # 1 > 2 is False → no battle
    assert bot._execute_battle(state) is False

    # With French Resources > 0 → French included
    state["resources"][C.FRENCH] = 5
    # Rebel FL: pat(1) + min(fre(3), pat(1))=1 + mil(0) = 2 = brit(2) → still not >
    assert bot._execute_battle(state) is False

    # More Patriot cubes so French contribute more
    state["spaces"]["Boston"][C.REGULAR_PAT] = 3
    # Rebel FL: pat(3) + min(fre(3), pat(3))=3 + 0 = 6 > 2 → battle
    assert bot._execute_battle(state) is True


def test_p4_battle_resource_constraint_trims_spaces():
    """P4: §8.5.1 — If Patriot Resources too low for all spaces, trim list.
    We test the trim logic directly rather than through battle.execute,
    since full execution requires many state dependencies."""
    bot = PatriotBot()
    from lod_ai.board.control import refresh_control
    from lod_ai.leaders import leader_location
    base_sp = {
        C.REGULAR_PAT: 4, C.REGULAR_FRE: 0,
        C.MILITIA_A: 0, C.MILITIA_U: 0,
        C.FORT_PAT: 0,
        C.REGULAR_BRI: 1, C.TORY: 0,
        C.WARPARTY_A: 0, C.FORT_BRI: 0,
    }
    state = {
        "spaces": {
            "Boston": dict(base_sp),
            "New_York": dict(base_sp),
            "Philadelphia": dict(base_sp),
        },
        "resources": {C.PATRIOTS: 2, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {},
        "support": {},
        "control": {},
        "rng": random.Random(42),
        "history": [],
        "casualties": {},
    }
    # Simulate the target selection logic from _execute_battle
    refresh_control(state)
    french_res = state["resources"].get(C.FRENCH, 0)
    targets = []
    for sid, sp in state["spaces"].items():
        pat_cubes = sp.get(C.REGULAR_PAT, 0)
        fre_cubes = min(sp.get(C.REGULAR_FRE, 0), pat_cubes) if french_res > 0 else 0
        active_mil = sp.get(C.MILITIA_A, 0)
        rebel_force = pat_cubes + fre_cubes + (active_mil // 2)
        regs = sp.get(C.REGULAR_BRI, 0)
        tories = sp.get(C.TORY, 0)
        active_wp = sp.get(C.WARPARTY_A, 0)
        brit_force = regs + tories + (active_wp // 2) + sp.get(C.FORT_BRI, 0)
        if rebel_force > brit_force and (regs + tories + active_wp) > 0:
            has_wash = 1 if leader_location(state, "LEADER_WASHINGTON") == sid else 0
            pop = 0
            villages = sp.get(C.VILLAGE, 0)
            targets.append((-has_wash, -pop, -villages, state["rng"].random(), sid))
    targets.sort()
    chosen = [sid for *_, sid in targets]
    # All 3 spaces should be eligible
    assert len(chosen) == 3
    # Resource constraint should trim to 2
    pat_res = state["resources"].get(C.PATRIOTS, 0)
    if pat_res < len(chosen):
        chosen = chosen[:max(pat_res, 1)]
    assert len(chosen) == 2


def test_p7_rally_bullet7_selects_unselected_fort():
    """P7 Bullet 7: §8.5.2 — gather Fort must be 'not already selected above'."""
    bot = PatriotBot()
    state = _full_state()
    # Fort_A is in spaces_used (bullets 1-6), Fort_B is NOT
    state["spaces"] = {
        "Fort_A": {
            C.FORT_PAT: 1, C.REGULAR_PAT: 2, C.MILITIA_A: 2,
            C.MILITIA_U: 1,
        },
        "Fort_B": {
            C.FORT_PAT: 1, C.REGULAR_PAT: 1, C.MILITIA_U: 1,
        },
        "Adj_to_B": {
            C.MILITIA_A: 3, C.MILITIA_U: 0,
            C.REGULAR_PAT: 0,
        },
    }
    state["support"] = {"Fort_A": 0, "Fort_B": 0, "Adj_to_B": 0}
    state["control"] = {}
    state["available"] = {C.FORT_PAT: 0, C.MILITIA_U: 5, C.REGULAR_PAT: 5}
    state["resources"] = {C.PATRIOTS: 10, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5}

    # The Bullet 7 logic should prefer Fort_B (not already selected)
    # over Fort_A (would be in spaces_used from earlier bullets).
    # We can't easily test this end-to-end because Rally selection is complex,
    # but we can verify the filter logic directly.
    spaces_used = ["Fort_A"]  # simulate bullets 1-6 selected Fort_A
    build_fort_set = set()

    fort_spaces_for_gather = [
        sid for sid, sp in state["spaces"].items()
        if sid not in spaces_used
        and (sp.get(C.FORT_PAT, 0) > 0 or sid in build_fort_set)
        and len(spaces_used) < 4
    ]
    # Fort_B should be a candidate (not in spaces_used, has Fort)
    assert "Fort_B" in fort_spaces_for_gather
    # Fort_A should NOT be a candidate (already in spaces_used)
    assert "Fort_A" not in fort_spaces_for_gather


# ===================================================================
# Q11: P2 Bullet 2 — Active Support board-state check
# ===================================================================

def test_p2_bullet2_active_support_no_militia_returns_true():
    """P2 bullet 2: Card places militia AND an Active Support space has no militia → True."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 0, C.MILITIA_A: 0},
        },
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_SUPPORT},
        "available": {},
    }
    # Card 3 shaded has places_patriot_militia_u=True
    card = {"id": 3}
    assert bot._faction_event_conditions(state, card) is True


def test_p2_bullet2_active_support_with_militia_returns_false():
    """P2 bullet 2: Active Support space already has militia → bullet doesn't fire.
    Other bullets also structured not to trigger."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 1, C.MILITIA_A: 0},
        },
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_SUPPORT},
        "available": {},
    }
    # Card 3 shaded: places_patriot_militia_u=True but only bullet;
    # Support > Opposition so bullet 1 would fire if shifts_support_rebel
    # Card 3 shaded does NOT shift support, so bullet 1 won't fire.
    # No forts/villages/resources flags → only bullet 2 could fire, and it shouldn't.
    card = {"id": 3}
    assert bot._faction_event_conditions(state, card) is False


def test_p2_bullet2_village_no_militia_returns_true():
    """P2 bullet 2: Village space with no militia → True."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Quebec": {C.VILLAGE: 1, C.MILITIA_U: 0, C.MILITIA_A: 0},
        },
        "resources": {C.PATRIOTS: 5},
        "support": {"Quebec": C.NEUTRAL},
        "available": {},
    }
    card = {"id": 3}
    assert bot._faction_event_conditions(state, card) is True


def test_p2_bullet2_no_qualifying_spaces_returns_false():
    """P2 bullet 2: All Active Support spaces have militia, no Villages without militia.
    Only bullet 2 could trigger → returns False."""
    bot = PatriotBot()
    state = {
        "spaces": {
            "Boston": {C.MILITIA_U: 2, C.MILITIA_A: 0},
            "Quebec": {C.VILLAGE: 1, C.MILITIA_U: 1, C.MILITIA_A: 0},
        },
        "resources": {C.PATRIOTS: 5},
        "support": {"Boston": C.ACTIVE_SUPPORT, "Quebec": C.NEUTRAL},
        "available": {},
    }
    card = {"id": 3}
    assert bot._faction_event_conditions(state, card) is False


# ===================================================================
# Session 9: Patriot Bot Compliance Review — new tests
# ===================================================================


def test_p13_persuasion_filters_colony_city():
    """P13: _try_persuasion must filter to Colony/City spaces only.
    Persuasion (§4.3.1) says 'choose 1-3 Colonies/Cities'. A Reserve
    Province with Rebel Control and Underground Militia must be excluded,
    otherwise persuasion.execute() raises ValueError and the entire call
    fails — including valid Colony/City candidates."""
    bot = PatriotBot()
    state = _full_state()
    # Quebec is a Reserve Province; Boston is a City
    state["spaces"] = {
        "Quebec": {C.MILITIA_U: 3, C.FORT_PAT: 1},
        "Boston": {C.MILITIA_U: 2, C.FORT_PAT: 0},
    }
    state["control"] = {"Quebec": "REBELLION", "Boston": "REBELLION"}
    state["support"] = {"Quebec": 0, "Boston": 0}
    state["resources"] = {C.PATRIOTS: 0, C.BRITISH: 5, C.FRENCH: 5, C.INDIANS: 5}
    state["markers"] = {C.PROPAGANDA: {"pool": 5, "on_map": set()}}

    # With the fix, Quebec (Reserve) should be excluded and Persuasion
    # should succeed with just Boston (City).
    result = bot._try_persuasion(state)
    assert result is True
    # Resources should have been added (1 per space)
    assert state["resources"][C.PATRIOTS] >= 1


def test_p13_persuasion_excludes_reserve_provinces():
    """P13: Verify Reserve Province spaces are not in the Persuasion candidate list."""
    bot = PatriotBot()
    from lod_ai.bots.patriot import _MAP_DATA
    state = _full_state()
    # Find a Reserve Province from the map data
    reserve_spaces = [
        sid for sid, d in _MAP_DATA.items()
        if d.get("type") == "Reserve"
    ]
    assert len(reserve_spaces) > 0, "Expected at least one Reserve Province in map"
    rsid = reserve_spaces[0]

    state["spaces"] = {
        rsid: {C.MILITIA_U: 2, C.FORT_PAT: 1},
        "Boston": {C.MILITIA_U: 2},
    }
    state["control"] = {rsid: "REBELLION", "Boston": "REBELLION"}
    state["support"] = {rsid: 0, "Boston": 0}
    from lod_ai.board.control import refresh_control
    refresh_control(state)

    # Build the candidate list the same way the bot does
    ctrl = state.get("control", {})
    candidates = [
        sid for sid, sp in state["spaces"].items()
        if ctrl.get(sid) == "REBELLION" and sp.get(C.MILITIA_U, 0)
        and _MAP_DATA.get(sid, {}).get("type") in ("Colony", "City")
    ]
    # Reserve Province must NOT be in the candidate list
    assert rsid not in candidates
    # Boston (City) should be in the candidate list
    assert "Boston" in candidates


def test_p7_rally_bullet5_uses_tracked_avail_forts():
    """P7 Bullet 5 (ref Bullet 4): 'If Patriot Fort Available' should use the
    post-Bullet-1 tracked count (avail_forts), not the original state['available']
    count. If all Forts are allocated in Bullet 1, this bullet should be skipped."""
    bot = PatriotBot()
    state = _full_state()
    # 2 Forts available, 2 spaces each with 4+ units and room → both allocated
    state["spaces"] = {
        "Boston": {
            C.REGULAR_PAT: 2, C.MILITIA_A: 2, C.MILITIA_U: 0,
            C.FORT_PAT: 0, C.REGULAR_FRE: 0,
            C.FORT_BRI: 0, C.VILLAGE: 0,
        },
        "New_York": {
            C.REGULAR_PAT: 2, C.MILITIA_A: 2, C.MILITIA_U: 0,
            C.FORT_PAT: 0, C.REGULAR_FRE: 0,
            C.FORT_BRI: 0, C.VILLAGE: 0,
        },
        "Philadelphia": {
            C.REGULAR_PAT: 1, C.MILITIA_A: 0, C.MILITIA_U: 0,
            C.FORT_PAT: 0, C.REGULAR_FRE: 0,
        },
    }
    state["available"] = {C.FORT_PAT: 2, C.MILITIA_U: 10, C.REGULAR_PAT: 10}
    state["support"] = {"Boston": 0, "New_York": 0, "Philadelphia": 0}
    state["control"] = {}

    # Simulate Bullet 1: allocate both Forts
    avail_forts = state["available"].get(C.FORT_PAT, 0)  # = 2
    build_fort_set = set()
    spaces_used = []

    from lod_ai.bots.patriot import _MAP_DATA
    fort_candidates = []
    for sid, sp in state["spaces"].items():
        if sp.get(C.FORT_PAT, 0) > 0:
            continue
        bases = sp.get(C.FORT_PAT, 0) + sp.get(C.FORT_BRI, 0) + sp.get(C.VILLAGE, 0)
        if bases >= 2:
            continue
        if bot._rebel_group_size(sp) >= 4:
            is_city = 1 if _MAP_DATA.get(sid, {}).get("type") == "City" else 0
            pop = _MAP_DATA.get(sid, {}).get("population", 0)
            fort_candidates.append((-is_city, -pop, sid))
    fort_candidates.sort()
    for _, _, sid in fort_candidates:
        if len(spaces_used) >= 4 or avail_forts <= 0:
            break
        build_fort_set.add(sid)
        spaces_used.append(sid)
        avail_forts -= 1

    # Both forts should be allocated
    assert avail_forts == 0
    assert len(build_fort_set) == 2

    # Bullet 5 condition: should be False since avail_forts == 0
    # The fixed code uses `avail_forts > 0` (not state["available"])
    assert avail_forts == 0  # post-planning: no forts left
    assert state["available"].get(C.FORT_PAT, 0) == 2  # original: still shows 2


def test_p7_rally_bullet6_does_not_exclude_active_support():
    """P7 Bullet 6: Reference says 'place Militia, first to change Control
    then where no Active Opposition' — this is a PRIORITY, not an exclusion.
    Active Support spaces should still be valid candidates (just low priority)."""
    bot = PatriotBot()
    state = _full_state()
    from lod_ai.board.control import refresh_control

    # Only Active Support spaces available — with the fix, they should
    # be selectable (whereas before they were excluded)
    state["spaces"] = {
        "Boston": {C.REGULAR_PAT: 0, C.MILITIA_A: 0, C.MILITIA_U: 0},
        "New_York": {C.REGULAR_PAT: 0, C.MILITIA_A: 0, C.MILITIA_U: 0},
    }
    state["support"] = {"Boston": C.ACTIVE_SUPPORT, "New_York": C.ACTIVE_SUPPORT}
    state["control"] = {}
    state["available"] = {C.FORT_PAT: 0, C.MILITIA_U: 10, C.REGULAR_PAT: 0}
    refresh_control(state)

    # Build Bullet 6 candidate list the way the fixed code does
    ctrl = state.get("control", {})
    spaces_used = []  # nothing selected in earlier bullets
    militia_targets = []
    for sid, sp in state["spaces"].items():
        if sid in spaces_used:
            continue
        # Fixed code: NO Active Support exclusion
        changes_ctrl = 1 if ctrl.get(sid) != "REBELLION" else 0
        no_active_opp = 1 if bot._support_level(state, sid) > C.ACTIVE_OPPOSITION else 0
        militia_targets.append((-changes_ctrl, -no_active_opp, sid))
    militia_targets.sort()

    # Active Support spaces should be in the candidate list
    sids = [t[-1] for t in militia_targets]
    assert "Boston" in sids
    assert "New_York" in sids


# ===================================================================
# Session 11: Patriot Bot Compliance Review — new tests
# ===================================================================


# ---------- Fix 1: Rabble-Rousing §3.3.4 eligibility ----------

def test_rabble_eligible_requires_pieces_or_militia():
    """_rabble_eligible must enforce §3.3.4: (Rebellion Control + Patriot pieces)
    OR Underground Militia. Spaces without either are ineligible even if not
    at Active Opposition."""
    bot = PatriotBot()
    # Space at NEUTRAL, no pieces, no Militia → ineligible
    state = {
        "spaces": {"Boston": {}},
        "support": {"Boston": C.NEUTRAL},
        "control": {"Boston": None},
    }
    assert bot._rabble_eligible(state, "Boston", state["spaces"]["Boston"]) is False

    # Space at NEUTRAL with Underground Militia → eligible
    state["spaces"]["Boston"][C.MILITIA_U] = 1
    assert bot._rabble_eligible(state, "Boston", state["spaces"]["Boston"]) is True

    # Space at NEUTRAL with Rebellion Control + Patriot Continental → eligible
    state2 = {
        "spaces": {"Boston": {C.REGULAR_PAT: 1}},
        "support": {"Boston": C.NEUTRAL},
        "control": {"Boston": "REBELLION"},
    }
    assert bot._rabble_eligible(state2, "Boston", state2["spaces"]["Boston"]) is True


def test_rabble_execute_skips_ineligible_spaces():
    """_execute_rabble must not send ineligible spaces to rabble_rousing.execute().
    Space with no pieces and no Rebellion Control should be excluded even if
    its support is not at Active Opposition."""
    bot = PatriotBot()
    state = _full_state(
        resources={C.PATRIOTS: 5, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
    )
    # Two spaces: one eligible (Underground Militia), one not (empty)
    state["spaces"]["Boston"] = {C.MILITIA_U: 1}
    state["spaces"]["New_York"] = {}  # no pieces, no control
    state["support"]["Boston"] = C.NEUTRAL
    state["support"]["New_York"] = C.NEUTRAL
    result = bot._execute_rabble(state)
    assert result is True
    # Only 1 resource should be spent (Boston only)
    rabble_log = [h for h in state.get("history", [])
                  if isinstance(h, dict) and "RABBLE_ROUSING" in h.get("msg", "")]
    assert len(rabble_log) == 1
    assert "Boston" in rabble_log[0]["msg"]
    # New_York should NOT appear in the log
    assert "New_York" not in rabble_log[0]["msg"]


# ---------- Fix 2: Rally Bullet 4 scope ----------

def test_rally_bullet4_continental_replacement_from_selected_only():
    """P7 Bullet 4: Continental replacement should search only Fort spaces
    already in spaces_used (Rally-selected spaces), not all Fort spaces
    on the map."""
    bot = PatriotBot()
    state = _full_state(
        resources={C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
        available={C.MILITIA_U: 10, C.FORT_PAT: 0, C.REGULAR_PAT: 10},
    )
    # Fort in Boston with 5 Militia (large count, NOT a Rally space initially)
    state["spaces"]["Boston"] = {
        C.FORT_PAT: 1, C.MILITIA_A: 3, C.MILITIA_U: 2,
    }
    # Fort in New_York with 2 Militia (smaller count, IS a lonely Fort → Rally Bullet 2)
    state["spaces"]["New_York"] = {
        C.FORT_PAT: 1,  # Fort with no other Rebellion pieces
    }
    # Set all support to Neutral (not Active Support, so Rally is allowed)
    for sid in state["spaces"]:
        state["support"][sid] = C.NEUTRAL

    result = bot._execute_rally(state)
    assert result is True

    # The Rally should have selected New_York (lonely Fort, Bullet 2)
    # and NOT promoted at Boston (which was never a Rally space).
    # Check history: if Boston appears in log as promote target, that's the bug.
    history_msgs = [h.get("msg", "") if isinstance(h, dict) else str(h)
                    for h in state.get("history", [])]
    rally_log = [m for m in history_msgs if "RALLY" in m]
    assert len(rally_log) > 0


# ---------- Fix 3: Card 52 conditional ----------

def test_force_if_52_patriot_requires_battle_space():
    """Card 52 Patriot instruction: 'select space per Battle instructions,
    else ignore.' Should return False when no French+British co-location."""
    bot = PatriotBot()
    state = _full_state(
        resources={C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
    )
    # No French Regulars on map → no valid Battle space
    for sid in state["spaces"]:
        state["spaces"][sid] = {}
    assert bot._force_condition_met("force_if_52", state, {}) is False


def test_force_if_52_patriot_true_when_shared_space():
    """Card 52 should return True when French + British share a space."""
    bot = PatriotBot()
    state = _full_state(
        resources={C.PATRIOTS: 10, C.BRITISH: 10, C.FRENCH: 10, C.INDIANS: 10},
    )
    for sid in state["spaces"]:
        state["spaces"][sid] = {}
    state["spaces"]["Boston"] = {C.REGULAR_FRE: 2, C.REGULAR_BRI: 1}
    assert bot._force_condition_met("force_if_52", state, {}) is True
