"""
lod_ai.special_activities
=========================
Package marker and convenience imports so engine.py can do:

    from lod_ai.special_activities import skirmish, war_path, partisans, common_cause
"""

from importlib import import_module
from pathlib   import Path

# --- auto-import every .py in this folder (except __init__.py) -----------
_pkg_path = Path(__file__).parent
for file in _pkg_path.glob("*.py"):
    if file.stem == "__init__":
        continue
    import_module(f"{__name__}.{file.stem}")

# Optional: expose main SAs at package level for easy import
from . import skirmish, war_path, partisans, common_cause  # noqa: E402
