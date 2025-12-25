"""Adapter package to load modules from the legacy 'special activities' folder."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_LEGACY_DIR = Path(__file__).resolve().parents[1] / "special activities"
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


def _load(name: str):
    path = _LEGACY_DIR / f"{name}.py"
    spec = spec_from_file_location(f"lod_ai.special_activities.{name}", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    sys.modules[f"lod_ai.special_activities.{name}"] = module
    return module


for _mod in _MODULES:
    globals()[_mod] = _load(_mod)

__all__ = _MODULES
