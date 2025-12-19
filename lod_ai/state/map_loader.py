# map_loader.py
import json
from pathlib import Path

_MAP = None

def load_map():
    """Return the canonical map dict (cached)."""
    global _MAP
    if _MAP is None:
        path = Path(__file__).resolve().parent / "data" / "map.json"
        with path.open("r", encoding="utf-8") as fh:
            _MAP = json.load(fh)
    return _MAP