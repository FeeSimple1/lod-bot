"""Regression tests for the two previously-orphaned OPS methods.

Before this change:
  * BritishBot.bot_indian_trade existed and was unit-tested but no
    engine/bot code called it.  IndianBot._trade computed the British
    offer inline and was missing the OPS-reference "Indian Resources <
    British Resources" gate, so British offered even when Indians had
    more Resources.
  * BritishBot.bot_leader_movement existed but no code applied its
    result, so British leaders never followed marches.

After this change both methods are static, IndianBot._trade delegates
to BritishBot.bot_indian_trade, and BritishBot._march invokes
_follow_leaders_after_march to apply leader-movement to each British
leader's largest-group destination.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from unittest.mock import patch

from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.indians import IndianBot
from lod_ai import rules_consts as C
from lod_ai.special_activities import trade as trade_mod


# ---------------------------------------------------------------------------
# bot_indian_trade
# ---------------------------------------------------------------------------

def _make_indian_trade_state(*, indian_res: int, british_res: int):
    """State that exercises the Indian Trade gate decisions."""
    return {
        "spaces": {
            "Quebec": {
                C.WARPARTY_U: 1,
                C.WARPARTY_A: 0,
                C.VILLAGE: 1,
                "adj": [],
            },
        },
        "resources": {C.BRITISH: british_res, C.PATRIOTS: 0,
                      C.FRENCH: 0, C.INDIANS: indian_res},
        "available": {C.WARPARTY_U: 0, C.WARPARTY_A: 0, C.VILLAGE: 0},
        "rng": random.Random(0),
        "rng_log": [],
        "history": [],
        "support": {"Quebec": C.NEUTRAL},
        "control": {"Quebec": ""},
        "markers": {C.RAID: {"on_map": set()},
                    C.PROPAGANDA: {"on_map": set()}},
        "casualties": {},
    }


def test_bot_indian_trade_offers_zero_when_indian_resources_exceed_british():
    """OPS gate: 'If Indians request Trade and Indian Resources <
    British Resources' — i.e. if Indians have at least as many
    Resources as British, British offers nothing."""
    state = _make_indian_trade_state(indian_res=5, british_res=3)
    assert BritishBot.bot_indian_trade(state) == 0


def test_bot_indian_trade_can_be_called_without_instance():
    """The method is a staticmethod so the Indian bot can call it
    without instantiating a BritishBot."""
    state = _make_indian_trade_state(indian_res=0, british_res=5)
    offer = BritishBot.bot_indian_trade(state)
    assert offer >= 0
    # Also reachable via instance for backwards compatibility:
    offer2 = BritishBot().bot_indian_trade(state)
    assert isinstance(offer2, int)


def test_indian_bot_trade_delegates_to_british_for_offer():
    """IndianBot._trade now consults BritishBot.bot_indian_trade for
    the offer instead of computing it inline (and missing the gate)."""
    state = _make_indian_trade_state(indian_res=5, british_res=3)

    bot = IndianBot()
    bot.faction = C.INDIANS

    # Spy on BritishBot.bot_indian_trade to verify it gets called.
    called = {"n": 0}
    orig = BritishBot.bot_indian_trade

    def spy(st):
        called["n"] += 1
        return orig(st)

    # Spy on trade.execute to capture the transfer that was passed.
    captured = {}
    def trade_spy(state_, faction, ctx, space_id, *, transfer=0):
        captured["transfer"] = transfer
        return {}

    with patch.object(BritishBot, "bot_indian_trade", staticmethod(spy)), \
         patch.object(trade_mod, "execute", side_effect=trade_spy):
        bot._trade(state)

    assert called["n"] == 1, (
        "IndianBot._trade should delegate to BritishBot.bot_indian_trade"
    )
    # Indian (5) >= British (3), so offer must be 0.
    assert captured.get("transfer") == 0, (
        f"With Indian>=British, transfer should be 0; got "
        f"{captured.get('transfer')}"
    )


# ---------------------------------------------------------------------------
# bot_leader_movement
# ---------------------------------------------------------------------------

def test_bot_leader_movement_follows_largest_destination():
    """If 5 British units move New_York -> Pennsylvania and 2 to
    Boston while 1 stays in New_York, the leader should follow to
    Pennsylvania (5 > 2 > 1)."""
    state = {
        "spaces": {
            "New_York": {C.REGULAR_BRI: 1, C.TORY: 0, "adj": []},
            "Pennsylvania": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
            "Boston": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
    }
    spaces_with_moves = {"Pennsylvania": 5, "Boston": 2}
    dest = BritishBot.bot_leader_movement(state, "LEADER_HOWE", spaces_with_moves)
    assert dest == "Pennsylvania", (
        f"Leader should follow largest group to Pennsylvania, not {dest}"
    )


def test_bot_leader_movement_stays_when_staying_group_is_largest():
    """If 8 units stay in New_York and 3 move to Pennsylvania,
    the leader stays in New_York."""
    state = {
        "spaces": {
            "New_York": {C.REGULAR_BRI: 8, C.TORY: 0, "adj": []},
            "Pennsylvania": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
    }
    spaces_with_moves = {"Pennsylvania": 3}
    dest = BritishBot.bot_leader_movement(state, "LEADER_HOWE", spaces_with_moves)
    assert dest == "New_York"


def test_bot_leader_movement_returns_none_when_leader_not_on_map():
    """An off-map leader gets None back."""
    state = {"spaces": {}, "leaders": {"LEADER_GAGE": None}}
    assert BritishBot.bot_leader_movement(state, "LEADER_GAGE", {}) is None


def test_follow_leaders_after_march_updates_state():
    """The post-march helper actually mutates state['leaders'] when a
    leader follows to a new destination."""
    state = {
        "spaces": {
            # After hypothetical march: New_York is empty, Pennsylvania
            # received 4 British units.  bot_leader_movement should
            # send LEADER_HOWE to Pennsylvania.
            "New_York": {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
            "Pennsylvania": {C.REGULAR_BRI: 4, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
        "history": [],
    }
    bot = BritishBot()
    plan = [
        {"src": "New_York", "dst": "Pennsylvania",
         "pieces": {C.REGULAR_BRI: 4}},
    ]
    bot._follow_leaders_after_march(state, plan)
    assert state["leaders"]["LEADER_HOWE"] == "Pennsylvania"


def test_follow_leaders_after_march_ignores_moves_not_from_leader_space():
    """If a march moves units between spaces that don't include the
    leader's space, the leader doesn't move."""
    state = {
        "spaces": {
            "New_York": {C.REGULAR_BRI: 2, C.TORY: 0, "adj": []},
            "Boston":   {C.REGULAR_BRI: 0, C.TORY: 0, "adj": []},
            "Pennsylvania": {C.REGULAR_BRI: 4, C.TORY: 0, "adj": []},
        },
        "leaders": {"LEADER_HOWE": "New_York"},
        "history": [],
    }
    bot = BritishBot()
    # Move only Pennsylvania units; New_York not involved.
    plan = [
        {"src": "Pennsylvania", "dst": "Boston",
         "pieces": {C.REGULAR_BRI: 4}},
    ]
    bot._follow_leaders_after_march(state, plan)
    assert state["leaders"]["LEADER_HOWE"] == "New_York", (
        "Leader should not move when no march originated from its space"
    )
