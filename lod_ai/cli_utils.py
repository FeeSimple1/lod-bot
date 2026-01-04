from __future__ import annotations

from typing import Iterable, List, Tuple, TypeVar

T = TypeVar("T")


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
        raw = input("Select: ").strip()
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
        raw = input("Select: ").strip()
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
        raw = input("Select: ").strip()
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
