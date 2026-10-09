"""Save boundaries must retain the current card and completed faction turns."""

from copy import deepcopy
import pytest

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.save_game import load_game, save_game
from lod_ai.state.setup_state import build_state
from lod_ai.state.setup_state import _card_from_id


class SavedAtPrompt(Exception):
    pass


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setattr("lod_ai.save_game.SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(Engine, "_resolve_brilliant_stroke_interrupt",
                        lambda *args, **kwargs: False)
    result = Engine(build_state("1775", seed=1))
    result.set_human_factions({C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS})
    return result


def _reload(state, engine):
    path = save_game(state, engine.human_factions, filename="resume")
    loaded, humans = load_game(path)
    resumed = Engine(loaded)
    resumed.set_human_factions(humans)
    return resumed


def _pass(faction, card, allowed, engine):
    return {"action": "pass", "used_special": False}, True, None, None


def _command(faction, card, allowed, engine):
    def runner(state, ctx):
        state["_turn_affected_spaces"] = {"Boston"}
        state["resources"][faction] -= 1
        return {"action": "command", "used_special": False}
    return engine.simulate_action(faction, card, allowed, runner)


def test_reload_after_reveal_preserves_current_upcoming_and_rng(engine):
    card = engine.draw_card()
    upcoming = deepcopy(engine.state.get("upcoming_card"))
    remaining = deepcopy(engine.state["deck"])
    rng = engine.state["rng"].getstate()

    resumed = _reload(engine.state_for_save(), engine)

    assert resumed.next_card() == card
    assert resumed.state.get("upcoming_card") == upcoming
    assert resumed.state["deck"] == remaining
    assert resumed.state["rng"].getstate() == rng


def test_reload_between_turns_keeps_first_action_and_slot_restrictions(engine):
    card = {"id": 9001, "order": [C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS]}
    saved = []
    starting = deepcopy(engine.state["resources"])

    def after_first(faction, result, card):
        saved.append(engine.state_for_save())
        raise SavedAtPrompt()

    with pytest.raises(SavedAtPrompt):
        engine.play_card(card, human_decider=_command, post_turn_callback=after_first)

    resumed = _reload(saved[0], engine)
    calls = []

    def second(faction, card, allowed, eng):
        calls.append((faction, allowed))
        return _command(faction, card, allowed, eng)

    actions = resumed.play_card(resumed.next_card(), human_decider=second)

    assert [fac for fac, _ in actions] == [C.BRITISH, C.PATRIOTS]
    assert [fac for fac, _ in calls] == [C.PATRIOTS]
    assert calls[0][1]["limited_only"] is True
    assert calls[0][1]["event_allowed"] is False
    assert resumed.state["resources"][C.BRITISH] == starting[C.BRITISH] - 1
    assert resumed.state["resources"][C.PATRIOTS] == starting[C.PATRIOTS] - 1
    assert resumed.state["ineligible_next"] == {C.BRITISH, C.PATRIOTS}
    assert resumed.state["played_cards"].count(card["id"]) == 1


def test_pass_callback_and_reload_do_not_repeat_pass_or_claim_first_slot(engine):
    card = {"id": 9002, "order": [C.BRITISH, C.PATRIOTS]}
    saved = []
    calls = []
    starting = engine.state["resources"][C.BRITISH]

    def after_pass(faction, result, card):
        calls.append((faction, result["action"]))
        saved.append(engine.state_for_save())
        raise SavedAtPrompt()

    with pytest.raises(SavedAtPrompt):
        engine.play_card(card, human_decider=_pass, post_turn_callback=after_pass)
    assert calls == [(C.BRITISH, "pass")]
    assert saved[0]["resources"][C.BRITISH] == starting + 2
    assert saved[0]["_card_progress"]["first_action"] is None

    resumed = _reload(saved[0], engine)
    next_allowed = []

    def decide(faction, card, allowed, eng):
        assert faction == C.PATRIOTS
        next_allowed.append(allowed)
        return _pass(faction, card, allowed, eng)

    resumed.play_card(resumed.next_card(), human_decider=decide)
    assert next_allowed[0]["limited_only"] is False
    assert next_allowed[0]["event_allowed"] is True
    assert resumed.state["resources"][C.BRITISH] == starting + 2
    assert C.BRITISH in resumed.state["eligible_next"]
    assert resumed.state["_card_turn_log"][0]["eligible_position"] == 1
    assert resumed.state["_card_turn_log"][1]["eligible_position"] == 2


def test_save_inside_simulation_restarts_only_pending_turn(engine):
    card = {"id": 9003, "order": [C.BRITISH, C.PATRIOTS]}
    starting = deepcopy(engine.state["resources"])
    saved = []
    expected_roll = []

    def decide(faction, card, allowed, eng):
        if faction == C.BRITISH:
            return _pass(faction, card, allowed, eng)

        def runner(state, ctx):
            expected_roll.append(state["rng"].randint(1, 1000000))
            state["resources"][faction] -= 3
            saved.append(eng.state_for_save())
            raise SavedAtPrompt()

        return eng.simulate_action(faction, card, allowed, runner)

    with pytest.raises(SavedAtPrompt):
        engine.play_card(card, human_decider=decide)

    resumed = _reload(saved[0], engine)
    assert resumed.state["_resume_boundary"] == {"kind": "turn", "faction": C.PATRIOTS}
    assert resumed.state["resources"][C.PATRIOTS] == starting[C.PATRIOTS]
    assert resumed.state["resources"][C.BRITISH] == starting[C.BRITISH] + 2
    assert resumed.state["_card_progress"]["queue"] == [C.PATRIOTS]
    assert resumed.state["rng"].randint(1, 1000000) == expected_roll[0]
    resumed.play_card(resumed.next_card(), human_decider=_command)
    assert resumed.state["resources"][C.PATRIOTS] == starting[C.PATRIOTS] - 1
    assert resumed.state["resources"][C.BRITISH] == starting[C.BRITISH] + 2


def test_save_during_winter_quarters_restarts_without_double_spend(engine, monkeypatch):
    card = {"id": 9004, "winter_quarters": True}
    saved = []
    before = engine.state["resources"][C.BRITISH]
    rng_before = engine.state["rng"].getstate()

    def pending_winter(state, **kwargs):
        state["resources"][C.BRITISH] -= 2
        state["rng"].random()
        saved.append(engine.state_for_save())
        raise SavedAtPrompt()

    monkeypatch.setattr("lod_ai.engine.resolve_year_end", pending_winter)
    with pytest.raises(SavedAtPrompt):
        engine.play_card(card)

    resumed = _reload(saved[0], engine)
    assert resumed.state["_resume_boundary"] == {"kind": "winter_quarters"}
    assert resumed.state["resources"][C.BRITISH] == before
    assert resumed.state["rng"].getstate() == rng_before

    def complete_winter(state, **kwargs):
        state["resources"][C.BRITISH] -= 2

    monkeypatch.setattr("lod_ai.engine.resolve_year_end", complete_winter)
    resumed.play_card(resumed.next_card())
    assert resumed.state["resources"][C.BRITISH] == before - 2
    assert resumed.state["played_cards"].count(card["id"]) == 1


def test_completed_card_does_not_replay_after_save(engine):
    card = engine.draw_card()
    engine.play_card(card, human_decider=_pass)
    expected = engine.state["upcoming_card"]
    resumed = _reload(engine.state_for_save(), engine)
    assert resumed.next_card() == expected
    assert resumed.state["played_cards"].count(card["id"]) == 1


def test_undo_checkpoint_replays_current_card_without_reinserting_it(engine):
    card = engine.draw_card()
    checkpoint = deepcopy(engine.state)
    upcoming = deepcopy(engine.state.get("upcoming_card"))
    deck = deepcopy(engine.state["deck"])
    engine.play_card(card, human_decider=_pass)
    engine.state.clear()
    engine.state.update(checkpoint)
    assert engine.next_card() == card
    assert engine.state.get("upcoming_card") == upcoming
    assert engine.state["deck"] == deck


@pytest.mark.parametrize("card_id", sorted(C.WINTER_QUARTERS_CARDS))
def test_real_winter_callback_survives_mid_resolution_save(engine, monkeypatch, card_id):
    card = _card_from_id(card_id)
    saved = []

    def pending_winter(state, **kwargs):
        state["resources"][C.BRITISH] -= 1
        saved.append(engine.state_for_save())
        raise SavedAtPrompt()

    monkeypatch.setattr("lod_ai.engine.resolve_year_end", pending_winter)
    with pytest.raises(SavedAtPrompt):
        engine.play_card(card)

    resumed = _reload(saved[0], engine)
    assert callable(resumed.state["winter_card_event"])
    assert resumed.state["history"] == saved[0]["history"]
    before = deepcopy(saved[0])
    after = deepcopy(resumed.state)
    # Compare actual card effects, including random removal on 102/103.
    before["human_factions"] = after["human_factions"] = set()
    before.pop("winter_card_event")(before)
    after.pop("winter_card_event")(after)
    assert before["resources"] == after["resources"]
    assert before["spaces"] == after["spaces"]
    assert before["cbc"] == after["cbc"]
    assert before["crc"] == after["crc"]
    assert before["rng"].getstate() == after["rng"].getstate()


def test_undo_from_inside_sandbox_restores_committed_state(engine):
    from lod_ai.cli_utils import UndoException

    card = {"id": 9005, "order": [C.BRITISH, C.PATRIOTS]}
    engine.state["current_card"] = card
    checkpoint = deepcopy(engine.state)

    def decide(faction, card, allowed, eng):
        if faction == C.BRITISH:
            return _pass(faction, card, allowed, eng)

        def runner(state, ctx):
            state["resources"][C.PATRIOTS] -= 3
            ctx["discard_after_undo"] = True
            eng.restore_checkpoint(checkpoint)
            raise UndoException()

        return eng.simulate_action(faction, card, allowed, runner)

    with pytest.raises(UndoException):
        engine.play_card(card, human_decider=decide)
    assert engine.state["resources"] == checkpoint["resources"]
    assert engine.state["rng"].getstate() == checkpoint["rng"].getstate()
    assert engine.ctx == {}
    assert engine.next_card() == card


def test_brilliant_stroke_save_restarts_declaration_boundary(engine, monkeypatch):
    card = {"id": 9006, "order": [C.BRITISH, C.PATRIOTS]}
    saved = []
    initial = engine.state["resources"][C.BRITISH]

    def pending_bs(card, **kwargs):
        engine.state["resources"][C.BRITISH] -= 2
        saved.append(engine.state_for_save())
        raise SavedAtPrompt()

    monkeypatch.setattr(engine, "_resolve_brilliant_stroke_interrupt", pending_bs)
    with pytest.raises(SavedAtPrompt):
        engine.play_card(card, human_decider=_pass)
    resumed = _reload(saved[0], engine)
    assert resumed.state["_resume_boundary"] == {"kind": "brilliant_stroke"}
    assert resumed.state["resources"][C.BRITISH] == initial
    assert resumed.state["_card_progress"]["phase"] == "interrupt"
    resumed.play_card(resumed.next_card(), human_decider=_pass)
    assert resumed.state["resources"][C.BRITISH] == initial + 2


def test_real_cli_save_at_second_faction_resumes_that_faction(engine, monkeypatch, tmp_path):
    """Drive the actual save meta-command and card loop through a provider."""
    from lod_ai import cli_utils, interactive_cli
    from lod_ai.save_game import list_saves

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "")
    engine.state.pop("current_card", None)
    engine.state.pop("upcoming_card", None)
    card = _card_from_id(62)
    card["order"] = [C.BRITISH, C.PATRIOTS]
    engine.state["deck"] = [card]
    initial = deepcopy(engine.state["resources"])

    class Provider:
        def __init__(self, save_and_quit):
            self.save_and_quit = save_and_quit
            self.saved = False
            self.turns = []

        def prompt(self, label, menu):
            prompt = (menu or {}).get("prompt", "")
            if "turn. Choose action" in prompt:
                faction = prompt.strip().split()[0]
                if faction == C.PATRIOTS and self.save_and_quit:
                    if not self.saved:
                        self.saved = True
                        return "save"
                    return "quit"
                self.turns.append(faction)
                return "1"  # Pass
            raise AssertionError(f"Unexpected prompt: {prompt!r}")

    first = Provider(True)
    cli_utils.set_game_state(engine.state, engine=engine)
    cli_utils.set_input_provider(first)
    try:
        with pytest.raises(SystemExit):
            interactive_cli._game_loop(engine, interactive_cli._new_game_stats(engine.human_factions))
        manual = [entry for entry in list_saves() if entry["filename"] != "autosave.json"]
        assert len(manual) == 1
        state, humans = load_game(manual[0]["filepath"])
        resumed = Engine(state)
        resumed.set_human_factions(humans)
        remaining = Provider(False)
        cli_utils.set_game_state(resumed.state, engine=resumed)
        cli_utils.set_input_provider(remaining)
        interactive_cli._game_loop(resumed, interactive_cli._new_game_stats(humans))
    finally:
        cli_utils.set_input_provider(None)
        cli_utils.set_game_state(None)
        cli_utils.set_undo_checkpoint(None)

    assert first.turns == [C.BRITISH]
    assert remaining.turns == [C.PATRIOTS]
    assert resumed.state["resources"][C.BRITISH] == initial[C.BRITISH] + 2
    assert resumed.state["resources"][C.PATRIOTS] == initial[C.PATRIOTS] + 1
    assert resumed.state["played_cards"] == [card["id"]]


def test_real_cli_undo_inside_command_discards_sandbox_and_replays_card(engine, monkeypatch, tmp_path):
    from lod_ai import cli_utils, interactive_cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "")
    engine.state.pop("current_card", None)
    engine.state.pop("upcoming_card", None)
    card = _card_from_id(62)
    card["order"] = [C.BRITISH, C.PATRIOTS]
    engine.state["deck"] = [card]
    before = deepcopy(engine.state["resources"])

    class Provider:
        undone = False
        turns = []

        def prompt(self, label, menu):
            prompt = (menu or {}).get("prompt", "")
            if "turn. Choose action" in prompt:
                faction = prompt.strip().split()[0]
                self.turns.append(faction)
                options = menu["options"]
                choice = "Command Only" if faction == C.PATRIOTS and not self.undone else "Pass"
                return str(options.index(choice) + 1)
            if prompt == "Select Command:" and not self.undone:
                self.undone = True
                return "undo"
            raise AssertionError(f"Unexpected prompt: {prompt!r}")

    provider = Provider()
    cli_utils.set_game_state(engine.state, engine=engine)
    cli_utils.set_input_provider(provider)
    try:
        interactive_cli._game_loop(engine, interactive_cli._new_game_stats(engine.human_factions))
    finally:
        cli_utils.set_input_provider(None)
        cli_utils.set_game_state(None)
        cli_utils.set_undo_checkpoint(None)

    assert provider.undone
    assert provider.turns == [C.BRITISH, C.PATRIOTS, C.BRITISH, C.PATRIOTS]
    assert engine.state["resources"][C.BRITISH] == before[C.BRITISH] + 2
    assert engine.state["resources"][C.PATRIOTS] == before[C.PATRIOTS] + 1
    assert engine.state["played_cards"] == [card["id"]]
    assert engine.ctx == {}


def test_status_uses_live_preview_while_save_uses_committed_boundary(engine, monkeypatch):
    from lod_ai import cli_utils

    card = {"id": 9007, "order": [C.PATRIOTS]}
    starting = engine.state["resources"][C.PATRIOTS]
    displayed = []
    saved = []
    monkeypatch.setattr("lod_ai.cli_display.display_board_state",
                        lambda state: displayed.append(state["resources"][C.PATRIOTS]))

    def decide(faction, card, allowed, eng):
        def runner(state, ctx):
            state["resources"][C.PATRIOTS] -= 1
            state["_turn_affected_spaces"] = {"Boston"}
            cli_utils._handle_meta_command("status")
            saved.append(eng.state_for_save())
            return {"action": "command", "used_special": False}
        return eng.simulate_action(faction, card, allowed, runner)

    cli_utils.set_game_state(engine.state, engine=engine)
    try:
        engine.play_card(card, human_decider=decide)
        assert cli_utils._game_state is engine.state
    finally:
        cli_utils.set_game_state(None)
    assert displayed == [starting - 1]
    assert saved[0]["resources"][C.PATRIOTS] == starting
    assert engine.state["resources"][C.PATRIOTS] == starting - 1


@pytest.mark.parametrize("outcome", ["victory", "stalemate"])
def test_reload_after_terminal_winter_quarters_cannot_advance_deck(engine, outcome):
    engine.draw_card()
    engine.state["victory_result"] = {"type": "final_scoring", "outcome": outcome,
                                      "winner": C.PATRIOTS if outcome == "victory" else None}
    remaining = deepcopy(engine.state["deck"])
    upcoming = deepcopy(engine.state.get("upcoming_card"))
    resumed = _reload(engine.state_for_save(), engine)
    assert resumed.next_card() is None
    assert resumed.draw_card() is None
    assert resumed.state["deck"] == remaining
    assert resumed.state.get("upcoming_card") == upcoming


def test_undo_during_bot_brilliant_stroke_limited_command_propagates(engine):
    from lod_ai.cli_utils import UndoException

    class Bot:
        def _battle(self, state):
            raise UndoException()

    with pytest.raises(UndoException):
        engine._run_bot_limcom(Bot(), C.BRITISH, "battle")
    assert not engine.state.get("bs_free")
    assert not engine.state.get("_limited")


def test_new_action_clears_previous_turn_accompaniment_trace(engine):
    keys = ("_turn_battle_spaces", "_turn_muster_spaces",
            "_turn_march_sources", "_turn_garrison_destinations")
    for key in keys:
        engine.state[key] = {"Boston"}

    def runner(state, ctx):
        assert not any(key in state for key in keys)
        state["_turn_affected_spaces"] = {"Boston"}
        return {"action": "command"}

    _, legal, _, _ = engine.simulate_action(
        C.PATRIOTS, {}, engine._options_for_slot(None), runner)
    assert legal
