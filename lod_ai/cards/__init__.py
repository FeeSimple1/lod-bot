"""Card registry and effect loader"""

from importlib import import_module
from pathlib import Path
import json
from typing import Callable, Dict, List
from lod_ai import rules_consts

# ---------------------------------------------------------------------------
# Data registry loaded from data.json
# ---------------------------------------------------------------------------
CARD_REGISTRY: Dict[int, dict] = {}
CARD_HANDLERS: Dict[int, Callable] = {}

_data_path = Path(__file__).parent / "data.json"
with _data_path.open("r", encoding="utf-8") as fh:
    for entry in json.load(fh):
        CARD_REGISTRY[entry["id"]] = entry

# ---------------------------------------------------------------------------
# Decorator for event handlers
# ---------------------------------------------------------------------------
def register(card_id: int):
    def _wrap(func: Callable) -> Callable:
        CARD_HANDLERS[card_id] = func
        return func
    return _wrap

# ---------------------------------------------------------------------------
# Autodiscover effect modules so decorators run on import
# ---------------------------------------------------------------------------
def _autodiscover() -> None:
    effects_path = Path(__file__).parent / "effects"
    for file in effects_path.glob("*.py"):
        if file.stem.startswith("_"):
            continue
        import_module(f"lod_ai.cards.effects.{file.stem}")

_autodiscover()

_ICON_MAP = {
    "P": rules_consts.PATRIOTS,
    "B": rules_consts.BRITISH,
    "F": rules_consts.FRENCH,
    "I": rules_consts.INDIANS,
}


def get_faction_order(card: dict) -> List[str]:
    """Return the order that factions act on this card.

    Parameters
    ----------
    card : dict
        Card entry as stored in :data:`CARD_REGISTRY`.

    Returns
    -------
    list[str]
        Sequence of faction identifiers from :mod:`rules_consts`.
    """

    icons = card.get("order_icons", "") or ""
    return [_ICON_MAP[c] for c in icons if c in _ICON_MAP]


__all__ = [
    "CARD_REGISTRY",
    "CARD_HANDLERS",
    "register",
    "get_faction_order",
]
