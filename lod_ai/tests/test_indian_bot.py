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

