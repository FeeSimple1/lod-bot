from __future__ import annotations

import sys
from typing import Iterable, List, Tuple, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Global state reference for meta-commands (set by interactive_cli.main)
# ---------------------------------------------------------------------------
_game_state = None


def set_game_state(state) -> None:
    """Register the live game state so meta-commands can access it."""
    global _game_state
    _game_state = state


def _handle_meta_command(raw: str) -> bool:
    """Check for status/history/quit meta-commands. Returns True if handled."""
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


def _print_menu(prompt: str, options: List[Tuple[str, T]], *, allow_back: bool) -> None:
    print(prompt)
    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")
    if allow_back:
        print("  0. Back")


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
        _print_menu(prompt + " (select 0 when done)", remaining, allow_back=True)
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
    numbers = list(range(min_val, max_val + 1))
    options = [(str(n), n) for n in numbers]
    if default is not None and default in numbers:
        prompt = f"{prompt} (default {default})"
    while True:
        _print_menu(prompt, options, allow_back=False)
        raw = _prompt_input()
        if raw == "" and default is not None:
            return default
        try:
            idx = int(raw)
        except ValueError:
            print("Enter a number from the list.")
            continue
        if 1 <= idx <= len(options):
            return options[idx - 1][1]
        print("Invalid choice.")
