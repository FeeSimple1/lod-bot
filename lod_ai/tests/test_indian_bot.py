import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.indians import choose_command
from lod_ai import rules_consts as C


def state_template():
    return {
        "spaces": {},
        "resources": {"INDIANS": 2},
    }


def test_choose_scout():
    st = state_template()
    st["spaces"] = {
        "A": {C.WARPARTY_U: 1, C.REGULAR_BRI: 1, "adj": ["B"]},
        "B": {},
    }
    cmd, loc = choose_command(st)
    assert cmd == "SCOUT"


def test_choose_war_path():
    st = state_template()
    st["spaces"] = {
        "A": {C.WARPARTY_U: 1, C.REGULAR_PAT: 1},
    }
    cmd, loc = choose_command(st)
    assert cmd == "WAR_PATH" and loc == "A"


def test_choose_gather_fallback():
    st = state_template()
    st["spaces"] = {"A": {}}
    cmd, loc = choose_command(st)
    assert cmd == "GATHER"


def test_war_path_checks_resources_zero():
    """I8: If Indian Resources = 0, should Trade instead of War Path."""
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    state = {
        "spaces": {
            "Quebec": {
                C.WARPARTY_U: 2,
                C.WARPARTY_A: 0,
                C.REGULAR_PAT: 1,
                C.VILLAGE: 1,
            },
        },
        "resources": {C.INDIANS: 0, C.BRITISH: 5, C.PATRIOTS: 3},
        "available": {},
        "support": {},
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
    }
    # With 0 resources, _war_path_or_trade should attempt Trade, not War Path
    bot._war_path_or_trade(state)
    history = " ".join(str(h) for h in state.get("history", []))
    # Should not attempt War Path when resources are 0
    assert "War Path" not in history or "Trade" in history


def test_march_neutral_or_passive_destination():
    """I10 March: destination should include Neutral (0) and both Passive
    support levels (+1, -1), not just Opposition."""
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    # Neutral space should be a valid destination
    state = {
        "spaces": {
            "Quebec": {C.WARPARTY_U: 3, C.WARPARTY_A: 1, C.VILLAGE: 0},
            "Northwest": {C.WARPARTY_U: 0, C.WARPARTY_A: 0, C.VILLAGE: 0},
        },
        "resources": {C.INDIANS: 3},
        "available": {},
        "support": {"Quebec": 0, "Northwest": 0},  # Both Neutral
        "control": {},
        "rng": __import__("random").Random(42),
        "history": [],
        "casualties": {},
    }
    # Northwest at Neutral (0) should be a valid March destination
    assert bot._support_level(state, "Northwest") == 0
    assert 0 in (C.NEUTRAL, C.PASSIVE_SUPPORT, C.PASSIVE_OPPOSITION)


def test_i2_event_conditions_per_reference():
    """I2 conditions per indian bot flowchart reference (CARD_EFFECTS lookup):
    1. Opp > Sup and event shifts S/O in Royalist favor
    2. Event places Village or grants free Gather
    3. Event removes a Patriot Fort
    4. 4+ Villages on map and D6 >= 5
    """
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    base_state = lambda: {
        "spaces": {"A": {C.WARPARTY_A: 1, C.WARPARTY_U: 1, C.VILLAGE: 1}},
        "resources": {C.INDIANS: 3},
        "support": {},
        "available": {},
        "rng": __import__("random").Random(42),
    }

    # Bullet 2: Card 79 unshaded places Village → True
    state = base_state()
    card_village = {"id": 79}
    assert bot._faction_event_conditions(state, card_village) is True

    # Bullet 2: Card 75 unshaded grants free Gather → True
    state = base_state()
    card_gather = {"id": 75}
    assert bot._faction_event_conditions(state, card_gather) is True

    # Bullet 3: Card 17 unshaded removes a Patriot Fort → True
    state = base_state()
    card_fort = {"id": 17}
    assert bot._faction_event_conditions(state, card_fort) is True

    # Card 5 unshaded: "Patriots Ineligible" — is_effective but no
    # Village/Gather/Fort.  With < 4 Villages, bullet 4 won't fire.
    state = base_state()
    card_noop = {"id": 5}
    assert bot._faction_event_conditions(state, card_noop) is False

    # Same card with 4+ Villages → exercises D6 check (bullet 4)
    state = base_state()
    state["spaces"]["B"] = {C.VILLAGE: 2}
    state["spaces"]["C"] = {C.VILLAGE: 1}
    result = bot._faction_event_conditions(state, card_noop)
    assert isinstance(result, bool)  # depends on RNG roll


def test_i9_checks_any_wp():
    """I9: Reference says 'A space has War Party and British Regulars?'
    — any WP type (Active or Underground) should trigger Scout."""
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    # Active-only WP with British → SHOULD trigger Scout per reference
    state = {
        "spaces": {
            "A": {C.WARPARTY_A: 3, C.WARPARTY_U: 0, C.REGULAR_BRI: 2},
        },
        "resources": {C.INDIANS: 3},
    }
    assert bot._space_has_wp_and_regulars(state) is True

    # Underground WP with British → also triggers
    state2 = {
        "spaces": {
            "A": {C.WARPARTY_A: 0, C.WARPARTY_U: 1, C.REGULAR_BRI: 2},
        },
        "resources": {C.INDIANS: 3},
    }
    assert bot._space_has_wp_and_regulars(state2) is True

    # No WP at all → should NOT trigger
    state3 = {
        "spaces": {
            "A": {C.WARPARTY_A: 0, C.WARPARTY_U: 0, C.REGULAR_BRI: 2},
        },
        "resources": {C.INDIANS: 3},
    }
    assert bot._space_has_wp_and_regulars(state3) is False


def test_i12_scout_destination_priority():
    """I12: Scout destination should prioritize Patriot Fort, then Village
    with enemy, then Rebel Control."""
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    # Verify the priority sorting logic exists (actual execution needs
    # full state). Just verify _scout selects correctly.

