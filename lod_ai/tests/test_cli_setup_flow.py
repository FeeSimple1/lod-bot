"""Regression tests for the CLI setup-flow Phase 4 fixes.

Two issues surfaced during the Phase 4 CLI audit:

  1. _choose_seed silently auto-generated a random integer instead of
     presenting the 1-5 + Random menu the README documents.  This
     prevented reproducible games (testing, sharing, debugging).

  2. The setup choice order in main() was Scenario+Deck -> Humans ->
     Seed, but the README documents Scenario -> Deck+Seed -> Humans.
     The re-select branch had the same inconsistency.

Both fixes are tested by scripting stdin against the actual CLI
functions and asserting on the resulting prompts / return values.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import io
import builtins
from contextlib import redirect_stdout


def _script_input(values):
    """Install a fake builtins.input that returns successive values."""
    it = iter(values)
    captured = {"prompts": []}

    def fake(prompt=""):
        captured["prompts"].append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise EOFError("scripted input exhausted")

    orig = builtins.input
    builtins.input = fake

    def restore():
        builtins.input = orig

    return captured, restore


def test_choose_seed_presents_menu_for_numeric_choice():
    """Selecting menu option 3 should return seed=3."""
    from lod_ai.interactive_cli import _choose_seed

    captured, restore = _script_input(["3"])
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            seed = _choose_seed()
        out = buf.getvalue()
    finally:
        restore()

    assert seed == 3, f"Expected seed=3, got {seed}"
    # Menu should advertise the choices
    assert "Select RNG seed:" in out
    assert "1. 1" in out
    assert "5. 5" in out
    assert "Random" in out


def test_choose_seed_random_option_returns_an_int():
    """Selecting the Random option (6) should return a generated int."""
    from lod_ai.interactive_cli import _choose_seed

    captured, restore = _script_input(["6"])
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            seed = _choose_seed()
    finally:
        restore()

    assert isinstance(seed, int)
    assert seed >= 1 and seed <= 10_000


def test_setup_flow_order_scenario_then_seed_then_humans():
    """Walk the new game start through to the confirmation menu and
    assert the prompts appear in README-documented order:
    Scenario -> Deck method -> Seed -> Human count -> Faction."""
    from lod_ai.interactive_cli import main as cli_main
    captured, restore = _script_input([
        "1",  # Start: New Game (skipped if no saves; here we need to
              # tolerate either path — but the autosave from prior
              # tests may exist, so allow the choice)
        "1",  # Scenario
        "1",  # Deck method
        "1",  # Seed
        "1",  # Human count
        "1",  # Faction
        "1",  # Confirm: Yes
        # Game start; further prompts will run.  EOF here is fine
        # because the deck-display prompt is the only thing left
        # before play_card; we don't need to play.
    ])
    try:
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                cli_main()
        except (EOFError, SystemExit):
            pass  # expected — we ran out of scripted input or game ended
        out = buf.getvalue()
    finally:
        restore()

    # Look at the prompts emitted, in order.
    scen_pos = out.find("Select a scenario:")
    deck_pos = out.find("Deck method:")
    seed_pos = out.find("Select RNG seed:")
    humans_pos = out.find("Number of human players:")

    # All four must have been prompted
    assert scen_pos != -1, "scenario prompt missing"
    assert deck_pos != -1, "deck method prompt missing"
    assert seed_pos != -1, "seed prompt missing"
    assert humans_pos != -1, "human count prompt missing"

    # And in this order
    assert scen_pos < deck_pos < seed_pos < humans_pos, (
        f"Prompt order wrong: scenario@{scen_pos}, deck@{deck_pos}, "
        f"seed@{seed_pos}, humans@{humans_pos}.  Expected README order "
        f"Scenario -> Deck -> Seed -> Humans."
    )
