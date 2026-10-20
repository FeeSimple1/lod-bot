"""Live Crown-seat regression: §1.10 human Leader choices and BS origins."""
from copy import deepcopy

import pytest

from lod_ai import cli_utils as U
from lod_ai import interactive_cli as cli
from lod_ai import rules_consts as C
from lod_ai.board.pieces import add_piece
from lod_ai.engine import Engine
from lod_ai.leaders import leader_location
from lod_ai.state.setup_state import build_state
from lod_ai.util.normalize_state import normalize_state


@pytest.fixture(autouse=True)
def restore_input():
    previous = U.get_input_provider()
    yield
    U.set_input_provider(previous)


def crown_engine():
    engine = Engine(initial_state=build_state("1776", seed=21))
    engine.set_human_factions({C.INDIANS})
    state = engine.state
    # The live trial's unrelated Florida stack is larger than the marching
    # New York group. All two New York WP leave Brant's origin.
    add_piece(state, C.WARPARTY_U, "Florida", 4 - state["spaces"]["Florida"].get(C.WARPARTY_U, 0))
    state["bs_free"] = True
    return engine


class CrownChoices:
    def __init__(self, leader_choice="Pennsylvania", move_count=2):
        self.leader_choice = leader_choice
        self.move_count = move_count
        self.origin_chosen = False
        self.leader_menus = []
        self.bs_steps = 0

    def prompt(self, label, menu):
        prompt = menu["prompt"]
        options = menu.get("options", [])
        if "Brilliant Stroke — choose next step" in prompt:
            self.bs_steps += 1
            return "1" if self.bs_steps <= 2 else str(len(options))
        if prompt.startswith("Bring escorts"):
            return "1"
        if prompt.startswith("Select March destinations"):
            return str(options.index("Pennsylvania") + 1)
        if prompt.startswith("Select origins"):
            if self.origin_chosen:
                return "0"
            self.origin_chosen = True
            return str(options.index("New_York") + 1)
        if prompt.startswith("Move how many Indian_WP_U"):
            return str(self.move_count)
        if prompt.startswith("INDIANS: move LEADER_BRANT"):
            self.leader_menus.append(deepcopy(menu))
            label = ("Move to Available Forces" if self.leader_choice is None
                     else next(o for o in options if self.leader_choice in o))
            return str(options.index(label) + 1)
        if prompt.startswith("Select Gather Provinces"):
            return str(options.index("Pennsylvania") + 1)
        if prompt.startswith("Choose Gather action"):
            return "2"  # Replace the two just-marched WP with a Village.
        raise AssertionError(f"Unexpected prompt: {prompt}")


@pytest.mark.parametrize("destination", ["Pennsylvania", None])
def test_emptied_origin_human_chooses_follow_or_available(destination):
    engine = crown_engine()
    provider = CrownChoices(leader_choice=destination)
    U.set_input_provider(provider)
    runner = cli._march_wizard(engine, C.INDIANS, True,
                               allowed_spaces={"Pennsylvania"})
    ctx = {}
    runner(engine.state, ctx)
    normalize_state(engine.state)
    assert leader_location(engine.state, "LEADER_BRANT") == destination
    assert len(provider.leader_menus) == 1
    assert "Move to Florida" in provider.leader_menus[0]["options"]
    assert "Move to Available Forces" in provider.leader_menus[0]["options"]
    assert ctx["_march_moves"] == [{"src": "New_York", "dst": "Pennsylvania",
                                    "tag": C.WARPARTY_U, "n": 2}]


def test_human_can_follow_smaller_group_or_stay_with_remaining_own_pieces():
    engine = crown_engine()
    provider = CrownChoices(leader_choice="Pennsylvania", move_count=1)
    U.set_input_provider(provider)
    runner = cli._march_wizard(engine, C.INDIANS, True,
                               allowed_spaces={"Pennsylvania"})
    runner(engine.state, {})
    assert leader_location(engine.state, "LEADER_BRANT") == "Pennsylvania"
    assert provider.leader_menus[0]["options"] == [
        "Stay in New_York", "Follow own units to Pennsylvania"]
    assert engine.state["spaces"]["New_York"][C.WARPARTY_U] == 1


def test_human_march_from_another_origin_does_not_move_leader():
    engine = crown_engine()

    class NorthwestChoices(CrownChoices):
        def prompt(self, label, menu):
            if menu["prompt"].startswith("Select origins"):
                if self.origin_chosen:
                    return "0"
                self.origin_chosen = True
                return str(menu["options"].index("Northwest") + 1)
            if menu["prompt"].startswith("Move how many"):
                return "1"
            return super().prompt(label, menu)

    provider = NorthwestChoices()
    U.set_input_provider(provider)
    runner = cli._march_wizard(engine, C.INDIANS, True,
                               allowed_spaces={"Pennsylvania"})
    runner(engine.state, {})
    assert leader_location(engine.state, "LEADER_BRANT") == "New_York"
    assert provider.leader_menus == []


def test_village_counts_as_remaining_own_piece_for_human_stay_choice():
    engine = crown_engine()
    add_piece(engine.state, C.VILLAGE, "New_York", 1)
    provider = CrownChoices(leader_choice="New_York")
    U.set_input_provider(provider)
    runner = cli._march_wizard(engine, C.INDIANS, True,
                               allowed_spaces={"Pennsylvania"})
    runner(engine.state, {})
    normalize_state(engine.state)
    assert leader_location(engine.state, "LEADER_BRANT") == "New_York"
    assert provider.leader_menus[0]["options"] == [
        "Stay in New_York", "Follow own units to Pennsylvania"]


def test_human_brilliant_stroke_counts_march_origin_as_leader_involvement(monkeypatch):
    engine = crown_engine()
    provider = CrownChoices()
    U.set_input_provider(provider)
    wizards = iter([cli._march_wizard, cli._gather_wizard])

    def choose_command(faction, engine, limited):
        return next(wizards)(engine, faction, limited,
                             allowed_spaces={"Pennsylvania"})

    monkeypatch.setattr(cli, "_command_runner_for", choose_command)
    assert engine._execute_human_bs_interactive(C.INDIANS)
    assert engine.state["spaces"]["Pennsylvania"][C.VILLAGE] == 1
    assert engine.state["spaces"]["New_York"].get(C.WARPARTY_U, 0) == 0
    assert any("Brilliant Stroke executed (human plan)" in h["msg"]
               for h in engine.state["history"])
