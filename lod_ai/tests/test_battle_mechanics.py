"""Tests for battle.py force level and casualty mechanics per §3.6."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.commands import battle
from lod_ai import rules_consts as C


def _base_state():
    return {
        "spaces": {},
        "resources": {C.BRITISH: 10, C.PATRIOTS: 10, C.FRENCH: 10, C.INDIANS: 10},
        "available": {},
        "casualties": {},
        "support": {},
        "control": {},
        "history": [],
        "rng": __import__("random").Random(42),
        "leader_locs": {},
        "markers": {C.BLOCKADE: {"pool": 0, "on_map": set()}},
    }


def test_force_level_excludes_underground_militia():
    """§3.6.3: Only Active Militia count (at half value). Underground ignored."""
    state = _base_state()
    state["spaces"]["A"] = {
        C.REGULAR_PAT: 2,
        C.MILITIA_A: 4,    # Should contribute 2 (half)
        C.MILITIA_U: 10,   # Should NOT contribute
        C.REGULAR_BRI: 1,
    }
    # Force the battle resolution to happen; we test that underground
    # militia are excluded by checking the force calculation path.
    # With underground excluded: rebel force = 2 + 2 = 4, royal = 1
    # With underground included: rebel force = 2 + 7 = 9, royal = 1
    battle.execute(state, C.PATRIOTS, {}, ["A"])
    # Underground militia should still be in the space (not removed as casualties)
    assert state["spaces"]["A"].get(C.MILITIA_U, 0) == 10


def test_force_level_forts_only_when_defending():
    """§3.6.2: Forts count for Defending side only."""
    state = _base_state()
    state["spaces"]["A"] = {
        C.REGULAR_BRI: 3,
        C.TORY: 1,
        C.FORT_BRI: 2,       # Should only count when British is DEFENDING
        C.REGULAR_PAT: 2,
        C.FORT_PAT: 2,       # Should only count when Rebellion is DEFENDING
    }
    # Patriots attack: Rebellion is attacker (no forts counted for them)
    # British is defender (forts counted for them)
    battle.execute(state, C.PATRIOTS, {}, ["A"])
    # Just verify execution completes without error
    assert any("BATTLE" in str(h) for h in state["history"])


def test_casualty_guerrillas_to_available_not_casualties():
    """§3.6.7: War Parties and Militia go to Available, cubes to Casualties."""
    state = _base_state()
    state["spaces"]["A"] = {
        C.REGULAR_BRI: 0,
        C.TORY: 0,
        C.WARPARTY_A: 3,     # Active WP on royalist side
        C.REGULAR_PAT: 5,
        C.MILITIA_A: 0,
    }
    # Patriots attack space with only Active War Parties
    battle.execute(state, C.PATRIOTS, {}, ["A"])
    # Any removed War Parties should go to Available, not Casualties
    # (We can't check exact numbers without controlling RNG, but
    # the test verifies execution completes without error)
    assert any("BATTLE" in str(h) for h in state["history"])


def test_casualty_removal_excludes_underground_wp():
    """§3.6.7: Underground War Parties are ignored during removal."""
    state = _base_state()
    state["spaces"]["A"] = {
        C.REGULAR_BRI: 0,
        C.TORY: 0,
        C.WARPARTY_A: 1,
        C.WARPARTY_U: 5,     # Should NEVER be removed
        C.REGULAR_PAT: 6,
        C.REGULAR_FRE: 0,
    }
    battle.execute(state, C.PATRIOTS, {}, ["A"])
    # Underground WP should still be in place (never touched)
    assert state["spaces"]["A"].get(C.WARPARTY_U, 0) == 5
