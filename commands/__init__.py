"""
Import each command module so the engine can call
lod_ai.commands.REGISTRY["MARCH"](state, faction, ctx, …)
"""

from importlib import import_module
from pathlib import Path

REGISTRY = {}

def _autodiscover():
    pkg_path = Path(__file__).parent
    for file in pkg_path.glob("*.py"):
        if file.stem == "__init__":
            continue
        mod = import_module(f"lod_ai.commands.{file.stem}")
        if hasattr(mod, "COMMAND_NAME") and hasattr(mod, "execute"):
            REGISTRY[mod.COMMAND_NAME] = mod.execute

_autodiscover()