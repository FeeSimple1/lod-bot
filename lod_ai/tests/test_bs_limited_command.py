"""Tests for get_bs_limited_command() on each bot subclass.

Each bot's method walks its faction's flowchart to find the first valid
Limited Command that can involve the faction's Leader in the Leader's
current space.  These tests verify the flowchart priority ordering and
edge cases (no leader, no pieces, no resources, etc.).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.indians import IndianBot
from lod_ai.bots.french import FrenchBot
from lod_ai import rules_consts as C


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    """Minimal valid state for bot tests."""
    s = {
        "spaces": {},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {
            C.REGULAR_BRI: 5, C.TORY: 5, C.FORT_BRI: 2,
            C.REGULAR_PAT: 5, C.MILITIA_U: 5, C.MILITIA_A: 0, C.FORT_PAT: 2,
            C.REGULAR_FRE: 5,
            C.WARPARTY_U: 5, C.WARPARTY_A: 0, C.VILLAGE: 5,
        },
        "unavailable": {},
        "support": {},
        "control": {},
        "casualties": {},
        "rng": random.Random(42),
        "history": [],
        "leaders": {},
        "leader_locs": {},
        "markers": {},
        "fni": 0,
        "toa_played": True,  # BS requires ToA
    }
    s.update(overrides)
    return s


def _sp(**pieces):
    """Build a space dict using constant-keyed pieces.

    Usage: _sp(**{C.REGULAR_BRI: 5, C.TORY: 2})
    """
    base = {
        C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0,
        C.REGULAR_PAT: 0, C.MILITIA_A: 0, C.MILITIA_U: 0, C.FORT_PAT: 0,
        C.REGULAR_FRE: 0,
        C.WARPARTY_A: 0, C.WARPARTY_U: 0, C.VILLAGE: 0,
        C.BLOCKADE: 0,
    }
    base.update(pieces)
    return base


# ===========================================================================
#  BRITISH BOT -- get_bs_limited_command
# ===========================================================================

class TestBritishBsLimCom:
    """Flowchart: B3 -> B4 (Garrison) -> B6 (Muster) -> B9 (Battle) -> B10 (March)."""

    def test_returns_none_when_no_leader(self):
        """No British leader on the map -> None."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_BRI: 5})},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_leader_below_threshold(self):
        """Leader present but fewer than 4 Regulars -> None."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_BRI: 3})},
            leader_locs={"LEADER_CLINTON": "Boston"},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_no_resources(self):
        """B3: Resources <= 0 -> None."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_BRI: 5})},
            leader_locs={"LEADER_CLINTON": "Boston"},
            resources={C.BRITISH: 0, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_muster_when_available_pieces(self):
        """B6: Available Regulars/Tories exist -> muster (Boston is a City)."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_BRI: 5})},
            leader_locs={"LEADER_CLINTON": "Boston"},
            control={"Boston": C.BRITISH},
        )
        assert bot.get_bs_limited_command(state) == "muster"

    def test_battle_when_enemies_outnumbered(self):
        """B9: 2+ Active Rebels outnumbered by Regulars -> battle."""
        bot = BritishBot()
        state = _base_state(
            spaces={"Boston": _sp(**{
                C.REGULAR_BRI: 5, C.MILITIA_A: 2, C.REGULAR_PAT: 1,
            })},
            leader_locs={"LEADER_CLINTON": "Boston"},
            control={"Boston": C.BRITISH},
            available={C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        )
        # Available pieces are 0 -> muster skipped -> battle check
        assert bot.get_bs_limited_command(state) == "battle"

    def test_march_as_fallback(self):
        """B10: No muster (no available, not City/Colony) and no battle -> march."""
        bot = BritishBot()
        # Leader in a Reserve (not City/Colony -> can't muster), no enemies -> march
        state = _base_state(
            spaces={"Northwest": _sp(**{C.REGULAR_BRI: 5})},
            leader_locs={"LEADER_CLINTON": "Northwest"},
            control={"Northwest": C.BRITISH},
            available={C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        )
        assert bot.get_bs_limited_command(state) == "march"

    def test_garrison_when_leader_in_rebellion_city(self):
        """B4: Leader in a Rebellion-controlled City without Rebel Fort,
        and 10+ Regulars on map -> garrison.
        The leader's city must have more rebels than royalists (so refresh_control
        keeps it REBELLION) and we still need 4+ British Regulars for the BS
        threshold.  Put extra regulars in another space to reach 10+."""
        bot = BritishBot()
        state = _base_state(
            spaces={
                # Boston: 4 Regs (BS threshold) but 6 Rebel cubes → REBELLION
                "Boston": _sp(**{C.REGULAR_BRI: 4, C.REGULAR_PAT: 5, C.MILITIA_A: 1}),
                "New_York_City": _sp(**{C.REGULAR_BRI: 7}),
            },
            leader_locs={"LEADER_CLINTON": "Boston"},
            available={C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        )
        # 4 + 7 = 11 Regulars on map, Boston is Rebellion city w/o Rebel Fort
        assert bot.get_bs_limited_command(state) == "garrison"


# ===========================================================================
#  PATRIOT BOT -- get_bs_limited_command
# ===========================================================================

class TestPatriotBsLimCom:
    """Flowchart: P3 -> P6 (Battle) -> P9 (Rally) -> P10 (Rabble) -> P5 (March)."""

    def test_returns_none_when_no_leader(self):
        """No Washington on the map -> None."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_PAT: 5})},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_leader_below_threshold(self):
        """Washington present but fewer than 4 Continentals -> None."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_PAT: 3})},
            leader_locs={"LEADER_WASHINGTON": "Boston"},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_no_resources(self):
        """P3: Resources <= 0 -> None."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_PAT: 5})},
            leader_locs={"LEADER_WASHINGTON": "Boston"},
            resources={C.BRITISH: 5, C.PATRIOTS: 0, C.FRENCH: 5, C.INDIANS: 5},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_battle_when_rebels_outnumber(self):
        """P6: Rebel cubes + Leader > Active Royal pieces -> battle."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{
                C.REGULAR_PAT: 5, C.REGULAR_BRI: 3, C.TORY: 1,
            })},
            leader_locs={"LEADER_WASHINGTON": "Boston"},
            control={"Boston": "REBELLION"},
        )
        # Rebel cubes (5) + leader (1) = 6 > Royal (3+1=4)
        assert bot.get_bs_limited_command(state) == "battle"

    def test_rally_when_fort_possible(self):
        """P9: Rally would place Fort (4+ rebels, Fort available) -> rally."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{
                C.REGULAR_PAT: 5, C.MILITIA_A: 1,
            })},
            leader_locs={"LEADER_WASHINGTON": "Boston"},
            control={"Boston": "REBELLION"},
        )
        # No enemies -> not battle.  6 rebels, Fort available -> rally
        assert bot.get_bs_limited_command(state) == "rally"

    def test_rally_preferred_over_rabble(self):
        """Rally appears before Rabble-Rousing in the flowchart."""
        bot = PatriotBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_PAT: 5})},
            leader_locs={"LEADER_WASHINGTON": "Boston"},
            control={"Boston": "REBELLION"},
            support={"Boston": 1},  # Support -- rabble could shift
        )
        # Rally check: rebel_group >= 4 -> rally
        assert bot.get_bs_limited_command(state) == "rally"


# ===========================================================================
#  INDIAN BOT -- get_bs_limited_command
# ===========================================================================

class TestIndianBsLimCom:
    """Flowchart: I3 -> I4 (Raid) / I6 (Gather) -> I9 (Scout) -> I10 (March)."""

    def test_returns_none_when_no_leader(self):
        """No Indian leader on the map -> None."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Northwest": _sp(**{C.WARPARTY_A: 3, C.WARPARTY_U: 1})},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_leader_below_threshold(self):
        """Leader present but fewer than 3 War Parties -> None."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Northwest": _sp(**{C.WARPARTY_A: 1, C.WARPARTY_U: 1})},
            leader_locs={"LEADER_BRANT": "Northwest"},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_raid_in_opposition_colony(self):
        """I4: Leader in Opposition Colony with Underground WP -> raid."""
        bot = IndianBot()
        state = _base_state(
            spaces={"South_Carolina": _sp(**{C.WARPARTY_A: 2, C.WARPARTY_U: 2})},
            leader_locs={"LEADER_BRANT": "South_Carolina"},
            support={"South_Carolina": -1},  # Passive Opposition
        )
        assert bot.get_bs_limited_command(state) == "raid"

    def test_gather_when_available_wp(self):
        """I6: Available WP exist and space has room -> gather."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Northwest": _sp(**{C.WARPARTY_A: 2, C.WARPARTY_U: 1})},
            leader_locs={"LEADER_BRANT": "Northwest"},
            support={"Northwest": 0},  # Neutral (not Opposition -> raid skipped)
        )
        # Northwest is a Reserve (not Colony) -> can't raid.
        # Available WP > 0 -> gather
        assert bot.get_bs_limited_command(state) == "gather"

    def test_scout_when_wp_and_british_regs(self):
        """I9: Leader's space has WP and British Regulars -> scout."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Northwest": _sp(**{
                C.WARPARTY_A: 2, C.WARPARTY_U: 1, C.REGULAR_BRI: 2,
            })},
            leader_locs={"LEADER_BRANT": "Northwest"},
            support={"Northwest": 0},
            available={
                C.WARPARTY_U: 0, C.WARPARTY_A: 0, C.VILLAGE: 0,
                C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0,
                C.REGULAR_PAT: 0, C.MILITIA_U: 0, C.MILITIA_A: 0, C.FORT_PAT: 0,
                C.REGULAR_FRE: 0,
            },
        )
        # No available WP/Villages -> gather skipped
        # WP + British Regulars -> scout
        assert bot.get_bs_limited_command(state) == "scout"

    def test_march_as_fallback(self):
        """I10: WP in space but no other conditions -> march."""
        bot = IndianBot()
        state = _base_state(
            spaces={"Northwest": _sp(**{C.WARPARTY_A: 2, C.WARPARTY_U: 1})},
            leader_locs={"LEADER_BRANT": "Northwest"},
            support={"Northwest": 0},
            available={
                C.WARPARTY_U: 0, C.WARPARTY_A: 0, C.VILLAGE: 0,
                C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0,
                C.REGULAR_PAT: 0, C.MILITIA_U: 0, C.MILITIA_A: 0, C.FORT_PAT: 0,
                C.REGULAR_FRE: 0,
            },
        )
        # No available WP/Villages -> gather skipped
        # No British Regulars -> scout skipped
        # WP in space -> march
        assert bot.get_bs_limited_command(state) == "march"


# ===========================================================================
#  FRENCH BOT -- get_bs_limited_command
# ===========================================================================

class TestFrenchBsLimCom:
    """Flowchart (post-Treaty): F3 -> F9 (Muster) -> F13 (Battle) -> F14 (March)."""

    def test_returns_none_when_no_leader(self):
        """No French leader on the map -> None."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"West_Indies": _sp(**{C.REGULAR_FRE: 5})},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_leader_below_threshold(self):
        """Leader present but fewer than 4 Regulars -> None."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"West_Indies": _sp(**{C.REGULAR_FRE: 3})},
            leader_locs={"LEADER_ROCHAMBEAU": "West_Indies"},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_returns_none_when_no_resources(self):
        """F3: Resources <= 0 -> None."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"West_Indies": _sp(**{C.REGULAR_FRE: 5})},
            leader_locs={"LEADER_ROCHAMBEAU": "West_Indies"},
            resources={C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 0, C.INDIANS: 5},
        )
        assert bot.get_bs_limited_command(state) is None

    def test_muster_when_available_regulars(self):
        """F9/F10: Available French Regulars > 0 -> muster."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"West_Indies": _sp(**{C.REGULAR_FRE: 5})},
            leader_locs={"LEADER_ROCHAMBEAU": "West_Indies"},
        )
        assert bot.get_bs_limited_command(state) == "muster"

    def test_battle_when_rebels_exceed_british(self):
        """F13: Rebel cubes + Leader > British pieces -> battle."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": _sp(**{
                C.REGULAR_FRE: 4, C.REGULAR_PAT: 2, C.REGULAR_BRI: 3,
            })},
            leader_locs={"LEADER_ROCHAMBEAU": "Boston"},
            available={C.REGULAR_FRE: 0},
        )
        # Rebel cubes (4+2) + leader_bonus (1 for Rochambeau) = 7
        # British = 3.  7 > 3 -> battle
        # But first check: avail French Regs = 0 -> muster skipped
        assert bot.get_bs_limited_command(state) == "battle"

    def test_march_as_fallback(self):
        """F14: French Regulars in space, no muster or battle -> march."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": _sp(**{C.REGULAR_FRE: 5})},
            leader_locs={"LEADER_ROCHAMBEAU": "Boston"},
            available={C.REGULAR_FRE: 0},
        )
        # No available -> muster skipped
        # No British -> battle skipped
        # French Regs in space -> march
        assert bot.get_bs_limited_command(state) == "march"

    def test_muster_preferred_over_battle(self):
        """Even when battle is possible, muster comes first per flowchart."""
        bot = FrenchBot()
        state = _base_state(
            spaces={"Boston": _sp(**{
                C.REGULAR_FRE: 5, C.REGULAR_BRI: 2,
            })},
            leader_locs={"LEADER_ROCHAMBEAU": "Boston"},
            available={C.REGULAR_FRE: 3},  # muster possible
        )
        # Available Regs > 0 -> muster (even though battle would also work)
        assert bot.get_bs_limited_command(state) == "muster"
