from __future__ import annotations

import sys
from datetime import datetime
from typing import Iterable, List, Tuple, TypeVar

T = TypeVar("T")


class BackException(Exception):
    """Raised when the user selects 'Back' in a menu."""
    pass


class UndoException(Exception):
    """Raised when undo is triggered to restart the current card."""
    pass


# ---------------------------------------------------------------------------
# Global state reference for meta-commands (set by interactive_cli.main)
# ---------------------------------------------------------------------------
_game_state = None
_engine_ref = None  # optional Engine reference for bug reports
_undo_checkpoint = None


def set_game_state(state, engine=None) -> None:
    """Register the live game state so meta-commands can access it."""
    global _game_state, _engine_ref
    _game_state = state
    _engine_ref = engine


def set_undo_checkpoint(state_copy) -> None:
    """Store a deep copy of the game state as an undo checkpoint."""
    global _undo_checkpoint
    _undo_checkpoint = state_copy


def get_undo_checkpoint():
    """Return the current undo checkpoint (or None)."""
    return _undo_checkpoint


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
    """Check for status/history/victory/bug/help/quit meta-commands. Returns True if handled."""
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
            from lod_ai.rules_consts import FORT_PAT, VILLAGE
            print("\n  --- Victory Margins ---")
            display_victory_margins(_game_state)

            # Show raw numbers that feed into the margins
            sup_total = 0
            opp_total = 0
            for sid, lvl in _game_state.get("support", {}).items():
                if lvl > 0:
                    sup_total += lvl
                elif lvl < 0:
                    opp_total += abs(lvl)
            cbc = _game_state.get("cbc", 0)
            crc = _game_state.get("crc", 0)

            forts = sum(
                sp.get(FORT_PAT, 0)
                for sp in _game_state.get("spaces", {}).values()
            )
            villages = sum(
                sp.get(VILLAGE, 0)
                for sp in _game_state.get("spaces", {}).values()
            )

            print(f"\n  Support Total: {sup_total}  |  Opposition Total: {opp_total}")
            print(f"  CBC: {cbc}  |  CRC: {crc}")
            print(f"  Patriot Forts: {forts}  |  Indian Villages: {villages}")
            print()
        else:
            print("(No game state available yet.)")
        return True
    if cmd in ("deck", "d"):
        if _game_state is not None:
            deck = _game_state.get("deck", [])
            played = _game_state.get("played_cards", [])

            # Find next Winter Quarters card
            wq_distance = None
            for i, c in enumerate(deck):
                if isinstance(c, dict) and c.get("winter_quarters"):
                    wq_distance = i + 1  # +1 because 0-indexed
                    break

            # Count remaining WQ cards
            wq_remaining = sum(
                1 for c in deck
                if isinstance(c, dict) and c.get("winter_quarters")
            )

            print(f"\n  --- Deck ---")
            print(f"  Cards played: {len(played)}")
            print(f"  Cards remaining: {len(deck)}")
            mode = _game_state.get("_deck_display_mode", "exact")
            if wq_distance is not None:
                if mode == "fuzzy":
                    if wq_distance <= 4:
                        print(f"  Next Winter Quarters: within the next 4 cards")
                    else:
                        print(f"  Next Winter Quarters: at least {wq_distance - 3} cards away")
                else:
                    print(f"  Next Winter Quarters: in {wq_distance} card{'s' if wq_distance != 1 else ''}")
            else:
                print(f"  Next Winter Quarters: none remaining in deck")
            print(f"  Winter Quarters cards left: {wq_remaining}")
            print()
        else:
            print("(No game state available yet.)")
        return True
    if cmd in ("undo", "u"):
        if _undo_checkpoint is not None and _engine_ref is not None:
            import copy
            restored = copy.deepcopy(_undo_checkpoint)
            _engine_ref.state.clear()
            _engine_ref.state.update(restored)
            print("  Undone! Replaying current card...")
            raise UndoException()
        else:
            print("(No undo checkpoint available.)")
        return True
    if cmd in ("bug", "b"):
        _save_bug_report()
        return True
    if cmd in ("save", "w"):
        if _engine_ref is not None:
            from lod_ai.save_game import save_game
            filepath = save_game(_engine_ref.state, _engine_ref.human_factions)
            print(f"  Game saved to: {filepath}")
        else:
            print("(No game in progress to save.)")
        return True
    if cmd in ("help", "?"):
        print("\n  Available commands (can be typed at any prompt):")
        print("    status  / s  — Show full board state")
        print("    victory / v  — Show victory margins for all factions")
        print("    deck    / d  — Show cards played/remaining and next Winter Quarters")
        print("    history / h  — Show game log")
        print("    undo    / u  — Revert to start of current card")
        print("    bug     / b  — File a bug report")
        print("    save    / w  — Save game to file")
        print("    help    / ?  — Show this help")
        print("    quit    / q  — Exit game")
        print()
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


def choose_one_or_back(prompt: str, options: Iterable[Tuple[str, T]]) -> T:
    """Like choose_one but raises BackException if user selects Back."""
    result = choose_one(prompt, options, allow_back=True)
    if result is None:
        raise BackException()
    return result


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
    exact_count = max_sel is not None and min_sel == max_sel
    while True:
        remaining = [item for item in opts if item[1] not in chosen]
        picks_left = (max_sel - len(chosen)) if max_sel is not None else None
        if exact_count:
            header = f"{prompt} (pick {picks_left})"
            _print_menu(header, remaining, allow_back=False)
        else:
            header = f"{prompt} (select 0 when done)"
            _print_menu(header, remaining, allow_back=True, back_label="Done")
        raw = _prompt_input()
        if raw == "0" and not exact_count:
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
