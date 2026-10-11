"""Card 48 permits Battle only in the single free March destination."""
import json

import pytest

from lod_ai import interactive_cli as cli
from lod_ai import rules_consts as C
from lod_ai.cards.effects.late_war import evt_048_god_save_king
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.board.control import refresh_control


def _engine():
    state = build_state("1778", seed=48)
    tags = Engine._CROWN_SIDE + Engine._REBEL_SIDE
    for space in state["spaces"].values():
        for tag in tags:
            space.pop(tag, None)
    state["spaces"]["Massachusetts"][C.REGULAR_BRI] = 8
    state["spaces"]["Boston"][C.REGULAR_PAT] = 1
    state["spaces"]["New_York_City"].update({C.REGULAR_BRI: 9, C.REGULAR_PAT: 6})
    state["resources"][C.BRITISH] = 0
    refresh_control(state)
    return Engine(initial_state=state)


def _history(state):
    return [row.get("msg", "") if isinstance(row, dict) else str(row)
            for row in state["history"]]


def test_card48_queue_preserves_serializable_link():
    engine = _engine()
    evt_048_god_save_king(engine.state)
    queue = engine.state["free_ops"]
    assert queue == [(C.BRITISH, "march_then_battle", None)]
    engine.state["free_ops"] = json.loads(json.dumps(queue))
    engine._drain_free_ops(engine.state, 48)
    assert not engine.state.get("_free_op_error_log")
    assert "FREE MARCH by BRITISH in Boston" in _history(engine.state)
    assert "FREE BATTLE by BRITISH in Boston" in _history(engine.state)
    assert "FREE BATTLE by BRITISH in New_York_City" not in _history(engine.state)
    assert engine.state["resources"][C.BRITISH] == 0
    assert not engine.state.get("bs_free")


def test_card48_does_not_battle_elsewhere_if_destination_has_no_enemy(monkeypatch):
    engine = _engine()
    engine.state["spaces"]["Boston"].pop(C.REGULAR_PAT)
    planner = engine._plan_bot_free_op
    monkeypatch.setattr(engine, "_plan_bot_free_op", lambda st, fac, op, loc, card_id:
                        planner(st, fac, op, "Boston" if op == "march" else loc, card_id))
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert engine.state["spaces"]["New_York_City"][C.REGULAR_PAT] == 6
    assert "FREE MARCH by BRITISH in Boston" in _history(engine.state)
    assert "FREE BATTLE by BRITISH — declined (no legal plan)" in _history(engine.state)
    assert not engine.state.get("_free_op_error_log")


def test_card48_without_british_pieces_has_no_march_or_battle():
    engine = _engine()
    for space in engine.state["spaces"].values():
        for tag in (C.REGULAR_BRI, C.TORY, C.FORT_BRI):
            space.pop(tag, None)
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert engine.state["spaces"]["New_York_City"][C.REGULAR_PAT] == 6
    assert not any("FREE BATTLE" in row for row in _history(engine.state))


def _no_movement_engine():
    engine = _engine()
    for space in engine.state["spaces"].values():
        space.pop(C.REGULAR_BRI, None)
        space.pop(C.REGULAR_PAT, None)
    for sid in ("Boston", "New_York_City"):
        engine.state["spaces"][sid].update({C.TORY: 3, C.REGULAR_PAT: 6})
    refresh_control(engine.state)
    return engine


def test_card48_no_moving_regulars_can_march_in_place_and_battle_there():
    engine = _no_movement_engine()
    assert engine._plan_bot_free_op(engine.state, C.BRITISH, "march", None, 48) is None
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    history = _history(engine.state)
    march = next(msg for msg in history if msg.startswith("FREE MARCH by BRITISH in "))
    destination = march.removeprefix("FREE MARCH by BRITISH in ")
    assert f"FREE BATTLE by BRITISH in {destination}" in history
    other = "New_York_City" if destination == "Boston" else "Boston"
    assert engine.state["spaces"][other][C.REGULAR_PAT] == 6
    assert engine.state["spaces"][other][C.TORY] == 3
    assert not engine.state.get("_free_op_error_log")


def test_card48_in_place_activation_prefers_support_then_battles_same_space(monkeypatch):
    engine = _no_movement_engine()
    for sid in ("Boston", "New_York_City"):
        engine.state["spaces"][sid][C.MILITIA_U] = 1
    engine.state["support"].update({"Boston": C.PASSIVE_SUPPORT,
                                   "New_York_City": C.NEUTRAL})
    execute = engine.dispatcher.execute

    def observe(op, **kwargs):
        if op == "battle":
            assert kwargs["space"] == "Boston"
            assert engine.state["spaces"]["Boston"].get(C.MILITIA_U, 0) == 0
            assert engine.state["spaces"]["Boston"][C.MILITIA_A] == 1
            assert engine.state["spaces"]["New_York_City"][C.MILITIA_U] == 1
        return execute(op, **kwargs)

    monkeypatch.setattr(engine.dispatcher, "execute", observe)
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert "FREE BATTLE by BRITISH in Boston" in _history(engine.state)
    assert not engine.state.get("_free_op_error_log")


@pytest.mark.parametrize("take_battle", [False, True])
def test_card48_human_one_destination_and_optional_battle_there(monkeypatch, take_battle):
    engine = _engine()
    engine.set_human_factions({C.BRITISH})
    monkeypatch.setattr(engine, "_interactive_input", lambda: True)
    menus = []

    def one(prompt, options, **kwargs):
        if prompt == "Bring escorts?":
            return False
        assert "optional FREE BATTLE in Boston" in prompt
        menus.append("offer")
        return take_battle

    def multiple(prompt, options, **kwargs):
        values = [value for _, value in options]
        if prompt == "Select March destinations:":
            assert kwargs["max_sel"] == 1
            assert "Boston" in values
            return ["Boston"]
        if prompt == "Select origins marching to Boston:":
            return ["Massachusetts"]
        assert prompt == "Select Battle spaces:"
        assert kwargs["max_sel"] == 1
        assert values == ["Boston"]
        menus.append("battle")
        return ["Boston"]

    monkeypatch.setattr(cli, "choose_one", one)
    monkeypatch.setattr(cli, "choose_multiple", multiple)
    monkeypatch.setattr(cli, "choose_count", lambda *args, **kwargs: min(4, kwargs["max_val"]))
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert menus == (["offer", "battle"] if take_battle else ["offer"])
    assert engine.state["spaces"]["New_York_City"][C.REGULAR_PAT] == 6
    assert engine.state["spaces"]["Massachusetts"][C.REGULAR_BRI] == 4
    assert engine.state["resources"][C.BRITISH] == 0
    assert not engine.state.get("_free_op_error_log")
    if not take_battle:
        assert engine.state["spaces"]["Boston"][C.REGULAR_PAT] == 1
        assert "FREE BATTLE by BRITISH — declined (player choice)" in _history(engine.state)


@pytest.mark.parametrize("take_battle", [False, True])
def test_card48_human_without_moving_cubes_selects_one_destination(monkeypatch, take_battle):
    engine = _no_movement_engine()
    engine.set_human_factions({C.BRITISH})
    monkeypatch.setattr(engine, "_interactive_input", lambda: True)

    def one(prompt, options, **kwargs):
        return False if prompt == "Bring escorts?" else take_battle

    def multiple(prompt, options, **kwargs):
        if prompt == "Select origins marching to Boston:":
            assert kwargs["min_sel"] == 0
            return []
        assert kwargs["max_sel"] == 1
        if prompt == "Select Battle spaces:":
            assert options == [("Boston", "Boston")]
        else:
            assert prompt == "Select March destinations:"
        return ["Boston"]

    monkeypatch.setattr(cli, "choose_one", one)
    monkeypatch.setattr(cli, "choose_multiple", multiple)
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert "FREE MARCH by BRITISH in Boston" in _history(engine.state)
    assert ("FREE BATTLE by BRITISH in Boston" in _history(engine.state)) == take_battle
    assert engine.state["spaces"]["New_York_City"][C.REGULAR_PAT] == 6
    assert engine.state["resources"][C.BRITISH] == 0
    assert not engine.state.get("_free_op_error_log")


def test_card48_actual_human_menu_handles_no_movement_origins(monkeypatch):
    from lod_ai import cli_utils
    engine = _no_movement_engine()
    engine.set_human_factions({C.BRITISH})
    monkeypatch.setattr(engine, "_interactive_input", lambda: True)
    # No escorts; Boston destination; decline the optional Battle.
    answers = iter(["1", "1", "1"])
    monkeypatch.setattr(cli_utils, "_prompt_input", lambda: next(answers))
    evt_048_god_save_king(engine.state)
    engine._drain_free_ops(engine.state, 48)
    assert "FREE MARCH by BRITISH in Boston" in _history(engine.state)
    assert "FREE BATTLE by BRITISH — declined (player choice)" in _history(engine.state)
    assert not engine.state.get("_free_op_error_log")


@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize("free", [False, True])
def test_british_in_place_march_charges_selected_destination_once(interactive, free):
    from lod_ai.commands import march
    engine = _no_movement_engine()
    state = engine.state
    state["spaces"]["Boston"][C.MILITIA_U] = 2
    state["resources"][C.BRITISH] = 5
    checkpoints = []
    ctx = ({"_command_checkpoint": lambda s, c, label, sid: checkpoints.append((label, sid))}
           if interactive else {})
    march.execute(state, C.BRITISH, ctx, [], ["Boston"],
                  move_plan=[], limited=True, free=free)
    assert state["spaces"]["Boston"][C.MILITIA_U] == 1
    assert state["spaces"]["Boston"][C.MILITIA_A] == 1
    assert state["resources"][C.BRITISH] == (5 if free else 4)
    if interactive:
        assert checkpoints.count(("Before March destination", "Boston")) == 1
        assert checkpoints.count(("Before March Militia activation", "Boston")) == 1
