# lod_ai/cards/__init__.py
"""
Event registry & helpers for the card system.

Exports
-------
- CARD_HANDLERS : dict[int, Callable]
- register(card_id) -> decorator to register a handler
- determine_eligible_factions(state, card) -> (first, second)

This module also auto-imports the per-era handler modules so their
@register decorators run at import time.
"""

from __future__ import annotations
from typing import Callable, Dict, Iterable, Optional, Tuple
import importlib
from lod_ai import rules_consts as C

# ---------------------------------------------------------------------------
# Global registry of card-id -> handler(state, shaded=False)
# ---------------------------------------------------------------------------
CARD_HANDLERS: Dict[int, Callable] = {}


def register(card_id: int) -> Callable[[Callable], Callable]:
    """
    Decorator used by card-effect modules to register a handler.

        @register(42)
        def evt_042_attack_danbury(state, shaded=False):
            ...

    If a handler for the same id already exists, raise ValueError.
    """
    def _decorator(func: Callable) -> Callable:
        if card_id in CARD_HANDLERS:
            raise ValueError(f"Card {card_id} already has a registered handler")
        CARD_HANDLERS[card_id] = func
        return func
    return _decorator


# ---------------------------------------------------------------------------
# Eligibility helper the Engine expects (see engine.py)
# ---------------------------------------------------------------------------
def determine_eligible_factions(state: dict, card: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (first, second) eligible factions for *card*.

    Reads state['eligible'] (bool flags set by Engine) and accepts several
    card shapes:
      - card['order'] = ['BRITISH','PATRIOTS',...]
      - card['first'] / card['second']  (or '*_faction')
      - otherwise falls back to default rotation.
    """
    flags = state.get("eligible", {})

    # Winter Quarters cards: queue their reset-phase effect now.
    # Engine resolves year_end directly for Winter Quarters cards and does not call handle_event,
    # so without this, Winter Quarters card effects (97–104) never execute.
    if card.get("winter_quarters"):
        cid = card.get("id")
        if isinstance(cid, int) and cid in CARD_HANDLERS:
            # Winter Quarters cards have no shaded/unshaded choice; pass False.
            CARD_HANDLERS[cid](state, False)

    # 1) Preferred: explicit order on the card
    if isinstance(card.get("order"), (list, tuple)) and card["order"]:
        base_order = [str(f).upper() for f in card["order"]]
    elif card.get("order_icons"):
        base_order = get_faction_order(card)
    else:
        # 2) Common alternates
        first = (card.get("first") or card.get("first_faction"))
        second = (card.get("second") or card.get("second_faction"))
        base_order = [f for f in [first, second] if f]
        base_order = [str(f).upper() for f in base_order if f]

        # 3) Fallback: full roster to guarantee we can pick two if eligible
        for f in ("BRITISH", "PATRIOTS", "INDIANS", "FRENCH"):
            if f not in base_order:
                base_order.append(f)

    def is_eligible(f: str) -> bool:
        # default to True if not explicitly marked otherwise
        return flags.get(f, True)

    first = next((f for f in base_order if is_eligible(f)), None)
    second = next((f for f in base_order if f != first and is_eligible(f)), None)
    return first, second


# ---------------------------------------------------------------------------
# Ensure handlers are imported so @register calls execute
# ---------------------------------------------------------------------------
def _ensure_handlers_imported() -> None:
    """
    Import handler modules (safe if absent). This causes their @register
    decorators to run and populate CARD_HANDLERS.
    """
    modules: Iterable[str] = (
        "lod_ai.cards.effects.early_war",
        "lod_ai.cards.effects.middle_war",
        "lod_ai.cards.effects.late_war",
        "lod_ai.cards.effects.winter_quarters",
        "lod_ai.cards.effects.brilliant_stroke",
    )
    for mod in modules:
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:
            # Some scenarios may omit certain eras; that's fine.
            continue


# Import at module load so registry is ready for bots/engine.
_ensure_handlers_imported()

__all__ = ["CARD_HANDLERS", "register", "determine_eligible_factions", "get_faction_order"]


# ---------------------------------------------------------------------------
# Order-icon helper used by tests and setup tools
# ---------------------------------------------------------------------------
_ICON_MAP = {
    "P": C.PATRIOTS,
    "B": C.BRITISH,
    "F": C.FRENCH,
    "I": C.INDIANS,
}


def get_faction_order(card: dict) -> list[str]:
    """Return the turn order encoded in a card's ``order_icons`` field."""
    icons = str(card.get("order_icons", "") or "").strip()
    return [_ICON_MAP[ch] for ch in icons if ch in _ICON_MAP]
