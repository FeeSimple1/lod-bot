from __future__ import annotations

import sys
from datetime import datetime
from typing import Iterable, List, Tuple, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Global state reference for meta-commands (set by interactive_cli.main)
# ---------------------------------------------------------------------------
_game_state = None
_engine_ref = None  # optional Engine reference for bug reports


def set_game_state(state, engine=None) -> None:
    """Register the live game state so meta-commands can access it."""
    global _game_state, _engine_ref
    _game_state = state
    _engine_ref = engine


def _save_bug_report() -> None:
    """Prompt for description and save a bug report snapshot."""
    if _game_state is None:
        print("(No game state available yet.)")
        return

    from lod_ai.tools.state_serializer import build_bug_report, save_report

    description = input("Describe the bug (one line): ").strip()
    if not description:
        description = "(no description)"

    human_factions = None
    seed = None
    scenario = None
    setup_method = None
    if _engine_ref is not None:
        human_factions = getattr(_engine_ref, "human_factions", None)
    seed = _game_state.get("_seed")
    scenario = _game_state.get("_scenario")
    setup_method = _game_state.get("_setup_method")

    # Gather diagnostic logs from state
    wizard_log = _game_state.get("_cli_wizard_log")
    sa_log = _game_state.get("_cli_sa_log")
    rejection_log = _game_state.get("_cli_rejection_log")

    report = build_bug_report(
        _game_state,
        description,
        human_factions=human_factions,
        seed=seed,
        scenario=scenario,
        setup_method=setup_method,
        wizard_log=wizard_log,
        sa_log=sa_log,
        rejection_log=rejection_log,
    )

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = f"lod_ai/reports/bug_{ts}.json"
    saved = save_report(report, filepath)
    print(f"Bug report saved to {saved}")


def _handle_meta_command(raw: str) -> bool:
    """Check for status/history/victory/bug/quit meta-commands. Returns True if handled."""
    cmd = raw.strip().lower()
    if cmd in ("status", "s"):
        if _game_state is not None:
            from lod_ai.cli_display import display_board_state
            display_board_state(_game_state)
        else:
            print("(No game state available yet.)")
        return True
    if cmd in ("history", "h"):
        if _game_state is not None:
            from lod_ai.cli_display import display_history
            display_history(_game_state)
        else:
            print("(No game state available yet.)")
        return True
    if cmd in ("victory", "v"):
        if _game_state is not None:
            from lod_ai.cli_display import display_victory_margins
            print()
            display_victory_margins(_game_state)
            print()
        else:
            print("(No game state available yet.)")
        return True
    if cmd in ("bug", "b"):
        _save_bug_report()
        return True
    if cmd in ("quit", "q"):
        print("\nExiting game. Goodbye!")
        sys.exit(0)
    return False


def _prompt_input(label: str = "Select: ") -> str:
    """Read input, handling meta-commands transparently."""
    while True:
        raw = input(label).strip()
        if _handle_meta_command(raw):
            continue
        return raw


def _print_menu(prompt: str, options: List[Tuple[str, T]], *, allow_back: bool,
                 back_label: str = "Back") -> None:
    print(prompt)
    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")
    if allow_back:
        print(f"  0. {back_label}")


def choose_one(prompt: str, options: Iterable[Tuple[str, T]], *, allow_back: bool = False) -> T | None:
    opts = list(options)
    if not opts:
        raise ValueError("No options available.")
    while True:
        _print_menu(prompt, opts, allow_back=allow_back)
        raw = _prompt_input()
        if allow_back and raw == "0":
            return None
        try:
            idx = int(raw)
        except ValueError:
            print("Enter a number from the list.")
            continue
        if 1 <= idx <= len(opts):
            return opts[idx - 1][1]
        print("Invalid choice.")


def choose_multiple(
    prompt: str,
    options: Iterable[Tuple[str, T]],
    *,
    min_sel: int = 0,
    max_sel: int | None = None,
) -> List[T]:
    opts = list(options)
    if not opts:
        raise ValueError("No options available.")
    chosen: List[T] = []
    while True:
        remaining = [item for item in opts if item[1] not in chosen]
        _print_menu(prompt + " (select 0 when done)", remaining, allow_back=True,
                     back_label="Done")
        raw = _prompt_input()
        if raw == "0":
            if len(chosen) < min_sel:
                print(f"Select at least {min_sel} option(s).")
                continue
            return chosen
        try:
            idx = int(raw)
        except ValueError:
            print("Enter a number from the list.")
            continue
        if 1 <= idx <= len(remaining):
            value = remaining[idx - 1][1]
            chosen.append(value)
            if max_sel and len(chosen) >= max_sel:
                return chosen
        else:
            print("Invalid choice.")


def choose_count(prompt: str, *, min_val: int = 0, max_val: int = 10, default: int | None = None) -> int:
    default_hint = f" (default {default})" if default is not None else ""
    while True:
        print(f"{prompt}{default_hint} [{min_val}-{max_val}]")
        raw = _prompt_input()
        if raw == "" and default is not None:
            return default
        try:
            val = int(raw)
        except ValueError:
            print(f"Enter a number from {min_val} to {max_val}.")
            continue
        if min_val <= val <= max_val:
            return val
        print(f"Enter a number from {min_val} to {max_val}.")
