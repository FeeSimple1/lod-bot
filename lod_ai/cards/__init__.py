"""Card registry and effect loader"""

from importlib import import_module
from pathlib import Path
import json
from typing import Callable, Dict

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

__all__ = ["CARD_REGISTRY", "CARD_HANDLERS", "register"]
