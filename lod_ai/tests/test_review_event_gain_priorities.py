"""Cards 1/16/21: printed §8.3.5–8.3.6 priorities and §1.9 scoring."""

import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.cards.effects import late_war
from lod_ai.engine import Engine


def _state(spaces, support, *, active=C.BRITISH, blockaded=()):
    return {
        "spaces": spaces,
        "support": support,
        "active": active,
        "available": {},
        "unavailable": {},
        "casualties": {},
        "control": {},
        "resources": {f: 0 for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)},
        "markers": {
            C.BLOCKADE: {"pool": 0, "on_map": set(blockaded)},
            C.PROPAGANDA: {"pool": C.MAX_PROPAGANDA, "on_map": {}},
        },
        "rng": random.Random(0),
        "history": [],
    }


def test_waxhaws_unshaded_ignores_blockaded_support_gain_and_executes_effects():
    """Equal removals: Norfolk gains Support, Blockaded Boston does not."""
    state = _state(
        {sid: {C.REGULAR_BRI: 1, C.REGULAR_PAT: 2} for sid in ("Boston", "Norfolk")},
        {"Boston": C.NEUTRAL, "Norfolk": C.NEUTRAL},
        blockaded={"Boston"},
    )

    # This direct invocation also guards the formerly missing ACTIVE_SUPPORT.
    late_war.evt_001_waxhaws(state, shaded=False)

    assert state["support"] == {"Boston": C.NEUTRAL, "Norfolk": C.PASSIVE_SUPPORT}
    assert state["spaces"]["Boston"][C.REGULAR_PAT] == 2
    assert state["spaces"]["Norfolk"].get(C.REGULAR_PAT, 0) == 0
    assert state["casualties"][C.REGULAR_PAT] == 2
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Norfolk": 2}


def test_waxhaws_prioritizes_support_gain_before_opposition_loss_and_removals():
    """§8.3.5 puts removals within §8.3.6's ordered shift priorities."""
    state = _state(
        {"New_York_City": {C.REGULAR_BRI: 1, C.REGULAR_PAT: 2},
         "Georgia": {C.REGULAR_BRI: 1}},
        {"New_York_City": C.ACTIVE_OPPOSITION, "Georgia": C.NEUTRAL},
    )

    late_war.evt_001_waxhaws(state, shaded=False)

    assert state["support"]["Georgia"] == C.PASSIVE_SUPPORT
    assert state["support"]["New_York_City"] == C.ACTIVE_OPPOSITION
    assert state["spaces"]["New_York_City"][C.REGULAR_PAT] == 2


def test_waxhaws_maximizes_continental_removals_within_equal_shift_gains():
    state = _state(
        {"Boston": {C.REGULAR_BRI: 1},
         "Norfolk": {C.REGULAR_BRI: 1, C.REGULAR_PAT: 2}},
        {"Boston": C.NEUTRAL, "Norfolk": C.NEUTRAL},
    )

    late_war.evt_001_waxhaws(state, shaded=False)

    assert state["support"]["Norfolk"] == C.PASSIVE_SUPPORT
    assert state["support"]["Boston"] == C.NEUTRAL
    assert state["casualties"][C.REGULAR_PAT] == 2


def test_waxhaws_counts_opposition_loss_in_a_blockaded_city():
    state = _state(
        {sid: {C.REGULAR_BRI: 1} for sid in ("Boston", "New_York_City")},
        {"Boston": C.ACTIVE_OPPOSITION, "New_York_City": C.NEUTRAL},
        blockaded={"Boston", "New_York_City"},
    )

    late_war.evt_001_waxhaws(state, shaded=False)

    assert state["support"]["Boston"] == C.PASSIVE_OPPOSITION
    assert state["support"]["New_York_City"] == C.NEUTRAL


@pytest.mark.parametrize("british_piece", [C.TORY, C.FORT_BRI])
def test_waxhaws_unshaded_accepts_british_presence_without_regulars(british_piece):
    state = _state(
        {"Boston": {british_piece: 1, C.REGULAR_PAT: 2}},
        {"Boston": C.NEUTRAL},
    )

    late_war.evt_001_waxhaws(state, shaded=False)

    assert state["support"]["Boston"] == C.PASSIVE_SUPPORT
    assert state["spaces"]["Boston"].get(C.REGULAR_PAT, 0) == 0
    assert state["casualties"][C.REGULAR_PAT] == 2
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Boston": 2}


def test_waxhaws_shaded_uses_free_command_target_without_british_presence(monkeypatch):
    """Patriots can March from New York to Battle Indians in Pennsylvania."""
    state = _state(
        {"New_York": {C.REGULAR_PAT: 4}, "Pennsylvania": {C.WARPARTY_A: 1}},
        {"New_York": C.NEUTRAL, "Pennsylvania": C.PASSIVE_SUPPORT},
        active=C.PATRIOTS,
    )
    engine = Engine(initial_state=state)

    late_war.evt_001_waxhaws(state, shaded=True)

    assert state["free_ops"] == [
        (C.PATRIOTS, "march", "Pennsylvania"),
        (C.PATRIOTS, "battle", "Pennsylvania"),
    ]
    assert state["support"]["Pennsylvania"] == C.PASSIVE_SUPPORT
    assert state["markers"][C.PROPAGANDA]["on_map"] == {}

    command_results = []
    execute = engine.dispatcher.execute

    def observe_real_command(command, **kwargs):
        assert state["markers"][C.PROPAGANDA]["on_map"] == {}
        result = execute(command, **kwargs)
        command_results.append((command, state["support"]["Pennsylvania"]))
        return result

    monkeypatch.setattr(engine.dispatcher, "execute", observe_real_command)
    engine._drain_free_ops(state, card_id=1)

    assert [command for command, _ in command_results] == ["march", "battle"]
    # Removing one War Party does not qualify for Win the Day (§3.6.8).
    assert command_results[-1][1] == C.PASSIVE_SUPPORT
    assert state["support"]["Pennsylvania"] == C.NEUTRAL
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Pennsylvania": 2}
    history = [entry["msg"] for entry in state["history"]]
    battle_done = next(i for i, line in enumerate(history)
                       if line.startswith("FREE BATTLE by PATRIOTS"))
    markers_placed = history.index("2 Propaganda placed in Pennsylvania")
    assert battle_done < markers_placed
    assert not state.get("_free_op_error_log")


def test_waxhaws_aftermath_follows_actual_win_the_day_support_shift(monkeypatch):
    """Four Tory losses shift +1 to −1, then the Event shifts −1 to Neutral."""
    state = _state(
        {"New_York": {C.REGULAR_PAT: 10}, "Pennsylvania": {C.TORY: 4}},
        {"New_York": C.NEUTRAL, "Pennsylvania": C.PASSIVE_SUPPORT},
        active=C.PATRIOTS,
    )
    engine = Engine(initial_state=state)
    late_war.evt_001_waxhaws(state, shaded=True)
    command_results = []
    execute = engine.dispatcher.execute

    def observe_real_command(command, **kwargs):
        assert state["markers"][C.PROPAGANDA]["on_map"] == {}
        result = execute(command, **kwargs)
        command_results.append((command, state["support"]["Pennsylvania"]))
        return result

    monkeypatch.setattr(engine.dispatcher, "execute", observe_real_command)
    engine._drain_free_ops(state, card_id=1)

    assert command_results == [
        ("march", C.PASSIVE_SUPPORT), ("battle", C.PASSIVE_OPPOSITION)]
    assert state["casualties"][C.TORY] == 4
    assert state["support"]["Pennsylvania"] == C.NEUTRAL
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Pennsylvania": 2}
    assert not state.get("_free_op_error_log")


def test_waxhaws_aftermath_uses_support_result_of_battle(monkeypatch):
    """The Neutral shift must read the level after Battle, not at card choice."""
    state = _state(
        {"Boston": {C.REGULAR_BRI: 1}},
        {"Boston": C.PASSIVE_SUPPORT}, active=C.PATRIOTS,
    )
    engine = Engine(initial_state=state)
    late_war.evt_001_waxhaws(state, shaded=True)
    calls = []

    monkeypatch.setattr(engine, "_plan_bot_free_op",
                        lambda *args: {"space": "Boston"})

    def resolve_command(command, **kwargs):
        calls.append(command)
        assert state["support"]["Boston"] == C.PASSIVE_SUPPORT
        assert state["markers"][C.PROPAGANDA]["on_map"] == {}
        if command == "battle":
            state["support"]["Boston"] = C.ACTIVE_OPPOSITION

    monkeypatch.setattr(engine.dispatcher, "execute", resolve_command)
    engine._drain_free_ops(state, card_id=1)

    assert calls == ["march", "battle"]
    assert state["support"]["Boston"] == C.PASSIVE_OPPOSITION
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Boston": 2}
    assert not state.get("free_op_followups")
    assert not state.get("_free_op_error_log")


def test_waxhaws_aftermath_still_applies_when_both_free_commands_decline():
    """§5.1.3: with no Patriot units, execute the remaining possible effects."""
    state = _state({"Boston": {}}, {"Boston": C.PASSIVE_SUPPORT}, active=C.PATRIOTS)
    engine = Engine(initial_state=state)
    late_war.evt_001_waxhaws(state, shaded=True)

    engine._drain_free_ops(state, card_id=1)

    assert state["support"]["Boston"] == C.NEUTRAL
    assert state["markers"][C.PROPAGANDA]["on_map"] == {"Boston": 2}
    history = [entry["msg"] for entry in state["history"]]
    march_declined = history.index("FREE MARCH by PATRIOTS — declined (no legal plan)")
    battle_declined = history.index("FREE BATTLE by PATRIOTS — declined (no legal plan)")
    markers_placed = history.index("2 Propaganda placed in Boston")
    assert march_declined < battle_declined < markers_placed
    assert not state.get("free_op_followups")
    assert not state.get("_free_op_error_log")


def test_mercy_warren_prefers_actual_support_loss_after_equal_opposition_gain():
    state = _state(
        {"Boston": {}, "Norfolk": {}},
        {"Boston": C.ACTIVE_SUPPORT, "Norfolk": C.PASSIVE_SUPPORT},
        active=C.PATRIOTS, blockaded={"Boston"},
    )

    late_war.evt_016_mercy_warren(state, shaded=True)

    assert state["support"]["Norfolk"] == C.PASSIVE_OPPOSITION
    assert state["support"]["Boston"] == C.ACTIVE_SUPPORT


@pytest.mark.parametrize("blockaded", [(), ("New_York_City",)])
def test_mercy_warren_prioritizes_opposition_gain_before_support_loss(blockaded):
    """Printed Population still weights Opposition in a Blockaded City."""
    state = _state(
        {"Boston": {}, "New_York_City": {}},
        {"Boston": C.ACTIVE_SUPPORT, "New_York_City": C.NEUTRAL},
        active=C.PATRIOTS, blockaded=blockaded,
    )

    late_war.evt_016_mercy_warren(state, shaded=True)

    assert state["support"]["New_York_City"] == C.PASSIVE_OPPOSITION
    assert state["support"]["Boston"] == C.ACTIVE_SUPPORT


def test_mercy_warren_explicit_choice_moves_fully_to_passive_opposition():
    state = _state(
        {"Boston": {}, "New_York_City": {}},
        {"Boston": C.ACTIVE_SUPPORT, "New_York_City": C.NEUTRAL},
        active=C.PATRIOTS,
    )
    state["card16_city"] = "Boston"

    late_war.evt_016_mercy_warren(state, shaded=True)

    assert state["support"]["Boston"] == C.PASSIVE_OPPOSITION
    assert state["support"]["New_York_City"] == C.NEUTRAL


def test_mercy_warren_avoids_losing_opposition_when_a_neutral_city_exists():
    state = _state(
        {"Boston": {}, "New_York_City": {}},
        {"Boston": C.NEUTRAL, "New_York_City": C.ACTIVE_OPPOSITION},
        active=C.PATRIOTS,
    )

    late_war.evt_016_mercy_warren(state, shaded=True)

    assert state["support"]["Boston"] == C.PASSIVE_OPPOSITION
    assert state["support"]["New_York_City"] == C.ACTIVE_OPPOSITION


@pytest.mark.parametrize("active", [C.BRITISH, C.INDIANS])
def test_sumter_prioritizes_support_gain_before_opposition_loss(active):
    state = _state(
        {"South_Carolina": {}, "Georgia": {}},
        {"South_Carolina": C.ACTIVE_OPPOSITION, "Georgia": C.NEUTRAL},
        active=active,
    )

    late_war.evt_021_sumter(state, shaded=False)

    assert state["support"]["Georgia"] == C.ACTIVE_SUPPORT
    assert state["support"]["South_Carolina"] == C.ACTIVE_OPPOSITION


def test_sumter_preserves_indian_non_village_instruction_before_gain_priorities():
    state = _state(
        {"South_Carolina": {}, "Georgia": {C.VILLAGE: 1}},
        {"South_Carolina": C.ACTIVE_OPPOSITION, "Georgia": C.NEUTRAL},
        active=C.INDIANS,
    )

    late_war.evt_021_sumter(state, shaded=False)

    assert state["support"]["South_Carolina"] == C.NEUTRAL
    assert state["support"]["Georgia"] == C.NEUTRAL


def test_sumter_preserves_explicit_choice():
    state = _state(
        {"South_Carolina": {}, "Georgia": {}},
        {"South_Carolina": C.ACTIVE_OPPOSITION, "Georgia": C.NEUTRAL},
    )
    state["card21_target"] = "South_Carolina"

    late_war.evt_021_sumter(state, shaded=False)

    assert state["support"]["South_Carolina"] == C.NEUTRAL
    assert state["support"]["Georgia"] == C.NEUTRAL


@pytest.mark.parametrize("handler,shaded,active,question,other,initial,final", [
    (late_war.evt_001_waxhaws, False, C.BRITISH,
     "Boston", "New_York_City", C.NEUTRAL, C.PASSIVE_SUPPORT),
    (late_war.evt_016_mercy_warren, True, C.PATRIOTS,
     "Boston", "New_York_City", C.NEUTRAL, C.PASSIVE_OPPOSITION),
    (late_war.evt_021_sumter, False, C.BRITISH,
     "Georgia", "South_Carolina", C.NEUTRAL, C.ACTIVE_SUPPORT),
])
def test_event_question_space_precedes_larger_gain(
        handler, shaded, active, question, other, initial, final):
    """§8.3.5's deciding-question bullet precedes shift-space priorities."""
    state = _state(
        {sid: {C.REGULAR_BRI: 1} for sid in (question, other)},
        {question: initial, other: initial}, active=active,
    )
    state["_event_q_spaces"] = {question}

    handler(state, shaded=shaded)

    assert state["support"][question] == final
    assert state["support"][other] == initial
