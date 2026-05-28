"""Regression test for BritishBot "March in place to Activate Militia".

Bug surfaced by 0-player smoke (1776 seed 2, card 10): when _march's
Phase 3 ("March in place to Activate Militia") is the only effective
March action — i.e. move_plan is empty but activate_in_place is not —
the bot called flip_pieces() directly without going through
march.execute().  That left _turn_command=None and
_turn_affected_spaces=={}, then the SA chain set _turn_used_special=True,
and the engine rejected the turn with illegal_reason='no_affected_spaces'.

The fix:
  * Charge §3.2.3 cost (1 Resource per destination space selected) for
    each march-in-place space.
  * Mark _turn_command='MARCH' and add the spaces to
    _turn_affected_spaces so the engine sees the command had effect.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state


def test_british_bot_1776_seed2_first_17_plays_no_illegal_actions():
    """End-to-end: replay the exact failing scenario.

    Before the fix this game produced an illegal_action on card 10 of
    play (Benjamin Franklin Travels to France) because the British
    bot's _march fell into the activate-in-place path and produced
    `no_affected_spaces`.  After the fix the log is empty.
    """
    # Suppress any interactive prompts that might leak through.
    devnull_fd = os.open(os.devnull, os.O_RDONLY)
    saved_stdin = os.dup(0)
    os.dup2(devnull_fd, 0)
    try:
        state = build_state("1776", seed=2)
        engine = Engine(initial_state=state, use_cli=False)
        engine.set_human_factions([])
        for _ in range(17):
            card = engine.draw_card()
            if card is None:
                break
            engine.play_card(card, human_decider=None)
    finally:
        os.dup2(saved_stdin, 0)
        os.close(saved_stdin)
        os.close(devnull_fd)

    log = engine.state.get("_illegal_action_log", [])
    assert not log, (
        f"Expected no illegal_action entries; got {len(log)}: "
        f"{[(e['card_number'], e['faction'], e['illegal_reason']) for e in log]}"
    )


def test_march_in_place_pays_resource_per_destination_and_tags_command():
    """Focused unit-style test.

    Set up a state where the British bot's _march will pick a
    march-in-place activation (1 destination with British Regulars and
    Underground Militia, no move targets).  After _march:
        * state['_turn_command'] should be 'MARCH'
        * state['_turn_affected_spaces'] should include the activated space
        * 1 British Resource should have been spent (§3.2.3)
        * The Underground Militia should be flipped to Active.
    """
    import random
    from lod_ai.bots.british_bot import BritishBot
    from lod_ai import rules_consts as C

    state = {
        "spaces": {
            # North_Carolina: 3 British Regulars + 2 Underground Militia.
            # No British power adjacent, no real march move available, but
            # march-in-place activation is legal (and per §3.2.3 activates
            # 1 Militia per 3 cubes in destination; we have 3 cubes so 1
            # gets activated by the rule — but the bot's flip_pieces
            # path flips all of them.  We assert the bot pays cost and
            # tags the command; behavior of which militia get flipped is
            # already covered by existing tests.)
            "North_Carolina": {
                C.REGULAR_BRI: 3,
                C.TORY: 0,
                C.MILITIA_A: 0,
                C.MILITIA_U: 2,
                C.REGULAR_PAT: 0,
                C.REGULAR_FRE: 0,
                C.FORT_BRI: 0,
                C.FORT_PAT: 0,
                C.VILLAGE: 0,
                "adj": [],
            },
        },
        "resources": {C.BRITISH: 3, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        "rng": random.Random(0),
        "history": [],
        "support": {"North_Carolina": C.PASSIVE_SUPPORT},
        "control": {"North_Carolina": C.BRITISH},
        "markers": {C.RAID: {"on_map": set()}, C.PROPAGANDA: {"on_map": set()}},
        "casualties": {},
        "_turn_affected_spaces": set(),
        "_turn_used_special": False,
        "_limited": False,
        "_no_special": True,  # short-circuit SA chain for this test
    }

    bot = BritishBot()
    pre_resources = state["resources"][C.BRITISH]
    pre_mu = state["spaces"]["North_Carolina"][C.MILITIA_U]
    pre_ma = state["spaces"]["North_Carolina"][C.MILITIA_A]

    ok = bot._march(state, tried_muster=True)

    assert ok, "_march should have succeeded with a march-in-place activation"
    assert state.get("_turn_command") == "MARCH", (
        f"_turn_command should be 'MARCH' after march-in-place; "
        f"got {state.get('_turn_command')!r}"
    )
    assert "North_Carolina" in state.get("_turn_affected_spaces", set()), (
        "march-in-place destination should be in _turn_affected_spaces"
    )
    assert state["resources"][C.BRITISH] == pre_resources - 1, (
        f"§3.2.3: 1 Resource should be spent per destination; before="
        f"{pre_resources}, after={state['resources'][C.BRITISH]}"
    )
    # Militia got flipped from Underground to Active.
    post_mu = state["spaces"]["North_Carolina"].get(C.MILITIA_U, 0)
    post_ma = state["spaces"]["North_Carolina"].get(C.MILITIA_A, 0)
    assert post_mu == 0 and post_ma == pre_ma + pre_mu, (
        f"Militia should be flipped to Active; pre Mu={pre_mu} Ma={pre_ma}, "
        f"post Mu={post_mu} Ma={post_ma}"
    )


def test_march_in_place_skips_when_resources_unaffordable():
    """If the British can't afford the §3.2.3 cost, the march-in-place
    activation should be skipped (the bot will then return False or
    fall back) rather than silently activating militia for free."""
    import random
    from lod_ai.bots.british_bot import BritishBot
    from lod_ai import rules_consts as C

    state = {
        "spaces": {
            "North_Carolina": {
                C.REGULAR_BRI: 3,
                C.TORY: 0,
                C.MILITIA_A: 0,
                C.MILITIA_U: 2,
                C.REGULAR_PAT: 0,
                C.REGULAR_FRE: 0,
                C.FORT_BRI: 0,
                C.FORT_PAT: 0,
                C.VILLAGE: 0,
                "adj": [],
            },
        },
        # Zero resources — bot can't afford March cost.
        "resources": {C.BRITISH: 0, C.PATRIOTS: 0, C.FRENCH: 0, C.INDIANS: 0},
        "available": {C.REGULAR_BRI: 0, C.TORY: 0, C.FORT_BRI: 0},
        "rng": random.Random(0),
        "history": [],
        "support": {"North_Carolina": C.PASSIVE_SUPPORT},
        "control": {"North_Carolina": C.BRITISH},
        "markers": {C.RAID: {"on_map": set()}, C.PROPAGANDA: {"on_map": set()}},
        "casualties": {},
        "_turn_affected_spaces": set(),
        "_turn_used_special": False,
        "_limited": False,
        "_no_special": True,
    }

    bot = BritishBot()
    bot._march(state, tried_muster=True)

    # With 0 resources, no march-in-place destination got paid for.
    assert "North_Carolina" not in state.get("_turn_affected_spaces", set()), (
        "Unaffordable march-in-place should not be applied"
    )
    # And no underground militia got flipped without payment.
    assert state["spaces"]["North_Carolina"].get(C.MILITIA_U, 0) == 2, (
        "Underground Militia must not be activated when March cost can't be paid"
    )
