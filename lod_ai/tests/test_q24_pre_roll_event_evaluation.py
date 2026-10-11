"""Q24 ruling: known-board Event choices never inspect future Battle rolls."""
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.board.control import refresh_control
from lod_ai.board.pieces import add_piece, remove_piece
from lod_ai.bots.base_bot import BaseBot
from lod_ai.cards import CARD_HANDLERS
from lod_ai.commands import battle
from lod_ai.engine import Engine
from lod_ai.map.adjacency import population
from lod_ai.save_game import _serialize_state
from lod_ai.state.setup_state import build_state
from lod_ai.tools.invariants import _rules_property_violations
from lod_ai.util.event_audit import record_choice, support_difference


def _known_board():
    state = build_state("1778", seed=24)
    for sid, space in state["spaces"].items():
        for tag in Engine._CROWN_SIDE + Engine._REBEL_SIDE:
            remove_piece(state, tag, sid, space.get(tag, 0), to="available")
    state["support"] = dict.fromkeys(state["spaces"], C.NEUTRAL)
    state["leaders"] = dict.fromkeys(state["leaders"])
    state["history"] = []
    refresh_control(state)
    return state


def _snapshot(state):
    encoded = _serialize_state(state, set())
    encoded.pop("_save_meta", None)
    return encoded


def _bot(faction):
    bot = BaseBot()
    bot.faction = faction
    bot._faction_event_conditions = lambda state, card: True
    bot._follow_flowchart = lambda state: pytest.fail("a committed Event cannot pivot")
    return bot


def _event_violations(state):
    return [problem for problem in _rules_property_violations(state, None)
            if "S8.3.3" in problem]


@pytest.mark.parametrize("faction,own_tag", [
    (C.BRITISH, C.REGULAR_BRI),
    (C.PATRIOTS, C.REGULAR_PAT),
    (C.FRENCH, C.REGULAR_FRE),
])
def test_preview_battle_stops_before_dice_fees_activations_and_callbacks(monkeypatch, faction, own_tag):
    state = _known_board()
    enemy_tag = C.REGULAR_PAT if faction == C.BRITISH else C.REGULAR_BRI
    add_piece(state, own_tag, "Boston", 6)
    add_piece(state, enemy_tag, "Boston", 6)
    state["_event_pre_roll_preview"] = True
    before = _snapshot(state)
    monkeypatch.setattr(battle, "_resolve_space", lambda *args, **kwargs:
                        pytest.fail("preview must not resolve a Battle"))
    monkeypatch.setattr(battle, "_roll_d3", lambda *args:
                        pytest.fail("preview must not inspect a future D3"))
    ctx = {}

    battle.execute(state, faction, ctx, ["Boston"], free=False,
                   win_callback=lambda *args: pytest.fail("no predicted Win-the-Day choice"))

    assert ctx == {}
    assert state["_event_preview_battles"]
    state.pop("_event_preview_battles")
    assert _snapshot(state) == before


@pytest.mark.parametrize("own_present,enemy_present", [(False, True), (True, False), (False, False)])
def test_impossible_battle_does_not_count_as_an_available_effect(own_present, enemy_present):
    state = _known_board()
    if own_present:
        add_piece(state, C.REGULAR_PAT, "Boston", 3)
    if enemy_present:
        add_piece(state, C.REGULAR_BRI, "Boston", 3)
    state["_event_pre_roll_preview"] = True
    battle.execute(state, C.PATRIOTS, {}, ["Boston"], free=True)
    assert not state.get("_event_preview_battles")
    assert not state.get("_battle_dice_rolled")


@pytest.mark.parametrize("faction,fort_tag,enemy_tag", [
    (C.BRITISH, C.FORT_BRI, C.REGULAR_PAT),
    (C.PATRIOTS, C.FORT_PAT, C.REGULAR_BRI),
])
def test_direct_battle_preview_accepts_printed_own_piece_requirement(faction, fort_tag, enemy_tag):
    """§3.2.4/§3.3.3 say own pieces, not only movable units."""
    state = _known_board()
    add_piece(state, fort_tag, "Boston", 1)
    add_piece(state, enemy_tag, "Boston", 3)
    state["_event_pre_roll_preview"] = True
    battle.execute(state, faction, {}, ["Boston"], free=True)
    assert state["_event_preview_battles"]
    assert not state.get("_battle_commands_executed")
    assert not state.get("_battle_dice_rolled")


@pytest.mark.parametrize("level,rejected", [
    (C.PASSIVE_SUPPORT, False), (C.NEUTRAL, False), (C.PASSIVE_OPPOSITION, True),
])
def test_real_waxhaws_judges_neutral_shift_on_known_board_even_with_available_battle(monkeypatch, level, rejected):
    state = _known_board()
    add_piece(state, C.REGULAR_PAT, "New_York", 10)
    add_piece(state, C.REGULAR_BRI, "Pennsylvania", 4)
    state["support"]["Pennsylvania"] = level
    state["_event_q_spaces"] = {"Pennsylvania"}
    before = _snapshot(state)
    monkeypatch.setattr(battle, "_resolve_space", lambda *args, **kwargs:
                        pytest.fail("queued Battle must not be resolved during choice"))
    bot = _bot(C.PATRIOTS)

    assert bot._is_ineffective_event({"id": 1, "dual": True}, state) is rejected

    preview = bot._event_choice_preview
    known_shift = -1 if level > 0 else (1 if level < 0 else 0)
    assert preview["d_after"] - preview["d_before"] == known_shift * population("Pennsylvania")
    assert preview["battle_possible"] is True
    assert preview["evaluation"] == "pre_roll"
    assert preview["battle_dice"] == 0
    assert preview["pending_free_ops"] is False
    assert _snapshot(state) == before


@pytest.mark.parametrize("card_id,faction", [(1, C.PATRIOTS), (5, C.PATRIOTS), (48, C.BRITISH)])
def test_real_direct_and_linked_battle_event_previews_do_not_read_future_dice(monkeypatch, card_id, faction):
    state = _known_board()
    if faction == C.BRITISH:
        add_piece(state, C.REGULAR_BRI, "Massachusetts", 8)
        add_piece(state, C.REGULAR_PAT, "Boston", 1)
    else:
        add_piece(state, C.REGULAR_PAT, "Massachusetts", 8)
        add_piece(state, C.REGULAR_BRI, "Boston", 4)
    if card_id == 5:
        state.update(card5_src="Massachusetts", card5_dest="Boston")
    before = _snapshot(state)
    bot = _bot(faction)
    monkeypatch.setattr(battle, "_roll_d3", lambda *args:
                        pytest.fail("no future Battle dice may inform an Event decision"))

    assert not bot._is_ineffective_event({"id": card_id, "dual": True}, state)

    assert bot._event_choice_preview["battle_possible"] is True
    assert bot._event_choice_preview["battle_dice"] == 0
    assert not bot._event_choice_preview["pending_free_ops"]
    assert _snapshot(state) == before


@pytest.mark.parametrize("future_roll", [1, 3])
def test_event_choice_is_independent_of_hidden_future_battle_rolls(monkeypatch, future_roll):
    state = _known_board()
    add_piece(state, C.REGULAR_PAT, "Boston", 3)
    add_piece(state, C.REGULAR_BRI, "Boston", 3)
    card = {"id": 9924, "dual": False}
    reads = []

    def future_d3(state):
        reads.append(future_roll)
        return future_roll

    monkeypatch.setattr(battle, "_roll_d3", future_d3)
    monkeypatch.setitem(CARD_HANDLERS, card["id"], lambda state, **kwargs:
                        battle.execute(state, C.PATRIOTS, {}, ["Boston"], free=True))
    bot = _bot(C.PATRIOTS)
    assert not bot._is_ineffective_event(card, state)
    assert reads == []
    assert bot._event_choice_preview["d_before"] == bot._event_choice_preview["d_after"]


@pytest.mark.parametrize("dice", [False, True])
def test_real_adverse_battle_cannot_make_bot_pivot_and_is_observed_not_illegal(monkeypatch, dice):
    state = _known_board()
    add_piece(state, C.REGULAR_PAT, "Boston", 3 if dice else 2)
    add_piece(state, C.REGULAR_BRI, "Boston", 3 if dice else 1)
    add_piece(state, C.FORT_BRI, "Boston", 1)
    if not dice:
        # Both Force Levels remain 2. The Underground defender and Fort
        # add Loss modifiers that remove a Continental and Active Militia.
        add_piece(state, C.MILITIA_A, "Boston", 1)
        add_piece(state, C.WARPARTY_U, "Boston", 1)
    if dice:
        # First Patriot loss-level roll is 1; British defender's is 3.
        # The normal roller records these as actual combat dice.
        class CombatRandom(random.Random):
            def randint(self, low, high):
                if (low, high) == (1, 3):
                    return next(self.combat_rolls)
                return super().randint(low, high)

        state["rng"] = CombatRandom(24)
        state["rng"].combat_rolls = iter([1, 3])
    card = {"id": 9925, "dual": False}
    monkeypatch.setitem(CARD_HANDLERS, card["id"], lambda state, **kwargs:
                        battle.execute(state, C.PATRIOTS, {}, ["Boston"], free=True))
    before = support_difference(state)
    result = _bot(C.PATRIOTS).take_turn(state, card)

    assert result["action"] == "event"
    assert support_difference(state) > before
    entry = state["event_choice_audit"][0]
    assert entry["preview"]["d_before"] == entry["preview"]["d_after"]
    assert entry["battle_commands"] == 1
    assert bool(entry["battle_dice"]) is dice
    assert _event_violations(state) == []
    assert state["event_outcome_observations"][0]["battle_commands"] == 1
    assert "_event_pre_roll_preview" not in state
    assert "_event_preview_battles" not in state


def test_available_battle_without_actual_battle_does_not_hide_deterministic_mismatch():
    state = _known_board()
    before = support_difference(state)
    state["support"]["Boston"] = C.PASSIVE_SUPPORT
    record_choice(state, C.PATRIOTS, {"id": 9926}, before, 0,
                  {"evaluation": "pre_roll", "d_before": before,
                   "d_after": before, "battle_possible": True})
    assert any("completed deterministic" in problem for problem in _event_violations(state))
