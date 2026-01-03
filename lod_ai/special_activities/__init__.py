"""Special Activities package."""

from importlib import import_module

_MODULES = [
    "common_cause",
    "naval_pressure",
    "partisans",
    "persuasion",
    "plunder",
    "preparer",
    "skirmish",
    "trade",
    "war_path",
]


def _import_all() -> None:
    """Eagerly import activity modules so attribute access works."""
    for name in _MODULES:
        globals()[name] = import_module(f"{__name__}.{name}")


_import_all()

__all__ = _MODULES
