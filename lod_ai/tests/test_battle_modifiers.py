"""Tests for battle loss modifiers per S3.6.5 and S3.6.6.

These tests exercise _defender_loss_mods and _attacker_loss_mods directly
to verify every modifier in the rules is applied correctly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.commands.battle import (
    _defender_loss_mods, _attacker_loss_mods, _side_has_leader,
)
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


# ======== S3.6.5 Defender Loss Level modifiers ========

class TestDefenderLossMods:
    """S3.6.5: modifiers applied to attacker's roll to determine defender loss."""

    def test_half_regulars_royalist_positive(self):
        """+1 if at least half Attacking Cubes are Regulars: British 3 Regs + 2 Tories."""
        state = _base_state()
        sp = {C.REGULAR_BRI: 3, C.TORY: 2}
        # 3 regs / 5 cubes = 60% >= 50% -> +1
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        # Only the half-regulars modifier applies (no leaders, no forts, etc.)
        assert mods == 1

    def test_half_regulars_royalist_negative(self):
        """No +1 if less than half Attacking Cubes are Regulars."""
        state = _base_state()
        sp = {C.REGULAR_BRI: 1, C.TORY: 4}
        # 1 reg / 5 cubes = 20% < 50% -> no modifier
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 0

    def test_half_regulars_rebellion_always(self):
        """+1 for Rebellion: all cubes are Regulars/Continentals."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 2, C.REGULAR_FRE: 1}
        # 3/3 = 100% >= 50% -> +1
        mods = _defender_loss_mods(state, sp, "Virginia", "REBELLION", "ROYALIST", 0)
        assert mods == 1

    def test_half_regulars_no_cubes(self):
        """No modifier if attacking side has no cubes."""
        state = _base_state()
        sp = {C.WARPARTY_A: 3}
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 0

    def test_underground_royalist(self):
        """+1 if at least one Underground War Party on attacking ROYALIST side."""
        state = _base_state()
        sp = {C.REGULAR_BRI: 1, C.WARPARTY_U: 2}
        # +1 half regs (1/1), +1 underground
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 2

    def test_underground_rebellion(self):
        """+1 if at least one Underground Militia on attacking REBELLION side."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 2, C.MILITIA_U: 1}
        # +1 half regs, +1 underground
        mods = _defender_loss_mods(state, sp, "Virginia", "REBELLION", "ROYALIST", 0)
        assert mods == 2

    def test_attacking_leader(self):
        """+1 if at least one Attacking Leader in space."""
        state = _base_state()
        state["leader_locs"] = {"LEADER_HOWE": "Boston"}
        sp = {C.REGULAR_BRI: 3}
        # +1 half regs, +1 leader
        mods = _defender_loss_mods(state, sp, "Boston", "ROYALIST", "REBELLION", 0)
        assert mods == 2

    def test_lauzun_bonus(self):
        """+1 if Attacking includes French with Lauzun (separate from leader mod)."""
        state = _base_state()
        state["leader_locs"] = {"LEADER_LAUZUN": "New_York_City"}
        sp = {C.REGULAR_PAT: 2, C.REGULAR_FRE: 1}
        # +1 half regs, +1 attacking leader (Lauzun), +1 French with Lauzun
        mods = _defender_loss_mods(state, sp, "New_York_City", "REBELLION", "ROYALIST", 0)
        assert mods == 3

    def test_blockaded_city_royalist_attacking(self):
        """-1 if British Attacking in Blockaded City."""
        state = _base_state()
        state["markers"][C.BLOCKADE]["on_map"] = {"Boston"}
        sp = {C.REGULAR_BRI: 4}
        # +1 half regs, -1 blockade
        mods = _defender_loss_mods(state, sp, "Boston", "ROYALIST", "REBELLION", 0)
        assert mods == 0

    def test_west_indies_squadron_royalist_attacking(self):
        """-1 if British Attacking in West Indies with Squadron."""
        state = _base_state()
        state["markers"][C.BLOCKADE]["pool"] = 2  # Squadrons in WI
        sp = {C.REGULAR_BRI: 4}
        # +1 half regs, -1 WI squadron
        mods = _defender_loss_mods(state, sp, C.WEST_INDIES_ID, "ROYALIST", "REBELLION", 0)
        assert mods == 0

    def test_defending_fort_minus(self):
        """-1 per Defending Fort in S3.6.5."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 3, C.FORT_PAT: 2, C.REGULAR_BRI: 1}
        # ROYALIST attacks, REBELLION defends with 2 Forts
        # +1 half regs (royalist 1 reg / 1 cube), -2 defending forts
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == -1

    def test_indians_defending_in_reserve(self):
        """-1 if Indians Defending in Indian Reserve."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 3, C.WARPARTY_A: 2}
        # REBELLION attacks in Reserve, ROYALIST defends with War Parties
        # +1 half regs (rebellion all regs), -1 Indians in reserve
        mods = _defender_loss_mods(state, sp, "Northwest", "REBELLION", "ROYALIST", 0)
        assert mods == 0  # +1 -1 = 0

    def test_washington_defending(self):
        """-1 if Patriots/French Defending with Washington."""
        state = _base_state()
        state["leader_locs"] = {"LEADER_WASHINGTON": "Virginia"}
        sp = {C.REGULAR_PAT: 3, C.REGULAR_BRI: 4}
        # ROYALIST attacks, REBELLION defends with Washington
        # +1 half regs, -1 Washington defending
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 0

    def test_common_cause_wp_as_tories(self):
        """Common Cause War Parties count as Tory cubes (non-Regulars)."""
        state = _base_state()
        # 2 Regulars, 1 Tory, 3 CC WP = 2 regs / 6 cubes = 33% < 50%
        sp = {C.REGULAR_BRI: 2, C.TORY: 1}
        mods = _defender_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", cc_wp=3)
        assert mods == 0  # half regs fails


# ======== S3.6.6 Attacker Loss Level modifiers ========

class TestAttackerLossMods:
    """S3.6.6: modifiers applied to defender's roll to determine attacker loss."""

    def test_half_regulars_defending(self):
        """+1 if at least half Defending Cubes are Regulars."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 3, C.REGULAR_BRI: 1}
        # Rebellion defends, 3 regs / 3 cubes -> +1
        mods = _attacker_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 1

    def test_underground_defending(self):
        """+1 if at least one Defending side piece Underground."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 2, C.MILITIA_U: 3, C.REGULAR_BRI: 1}
        # Rebellion defends with underground Militia
        # +1 half regs, +1 underground
        mods = _attacker_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 2

    def test_defending_leader(self):
        """+1 if at least one Defending Leader."""
        state = _base_state()
        state["leader_locs"] = {"LEADER_WASHINGTON": "Virginia"}
        sp = {C.REGULAR_PAT: 2, C.REGULAR_BRI: 1}
        # +1 half regs, +1 leader
        mods = _attacker_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 2

    def test_british_defending_blockaded_city(self):
        """-1 if British Defending in Blockaded City."""
        state = _base_state()
        state["markers"][C.BLOCKADE]["on_map"] = {"Boston"}
        sp = {C.REGULAR_BRI: 4, C.REGULAR_PAT: 1}
        # Royalist defends in blockaded Boston
        # +1 half regs, -1 blockade
        mods = _attacker_loss_mods(state, sp, "Boston", "REBELLION", "ROYALIST", 0)
        assert mods == 0

    def test_defending_fort_plus(self):
        """+1 per Defending Fort in S3.6.6."""
        state = _base_state()
        sp = {C.REGULAR_PAT: 2, C.FORT_PAT: 2, C.REGULAR_BRI: 1}
        # Rebellion defends with 2 Forts
        # +1 half regs, +2 forts
        mods = _attacker_loss_mods(state, sp, "Virginia", "ROYALIST", "REBELLION", 0)
        assert mods == 3

    def test_no_lauzun_or_washington_in_attacker_mods(self):
        """S3.6.6 has no Lauzun/Washington modifiers (those are S3.6.5 only)."""
        state = _base_state()
        state["leader_locs"] = {"LEADER_LAUZUN": "Virginia"}
        sp = {C.REGULAR_FRE: 2, C.REGULAR_BRI: 3}
        # Rebellion attacks, Royalist defends. Lauzun is Rebellion leader.
        # Lauzun is on attacking side, NOT defending side.
        # Royalist defending: +1 half regs (3/3), no leader mod since no royalist leader
        mods = _attacker_loss_mods(state, sp, "Virginia", "REBELLION", "ROYALIST", 0)
        assert mods == 1  # only half-regulars


# ======== Side leader helper ========

class TestSideHasLeader:
    def test_royalist_leader(self):
        state = _base_state()
        state["leader_locs"] = {"LEADER_HOWE": "Boston"}
        assert _side_has_leader(state, "Boston", "ROYALIST") is True
        assert _side_has_leader(state, "Boston", "REBELLION") is False

    def test_rebellion_leader(self):
        state = _base_state()
        state["leader_locs"] = {"LEADER_WASHINGTON": "Virginia"}
        assert _side_has_leader(state, "Virginia", "REBELLION") is True
        assert _side_has_leader(state, "Virginia", "ROYALIST") is False

    def test_indian_leader_counts_as_royalist(self):
        state = _base_state()
        state["leader_locs"] = {"LEADER_BRANT": "Northwest"}
        assert _side_has_leader(state, "Northwest", "ROYALIST") is True

    def test_no_leader(self):
        state = _base_state()
        assert _side_has_leader(state, "Virginia", "ROYALIST") is False
        assert _side_has_leader(state, "Virginia", "REBELLION") is False
