# map_loader.py
import json
from pathlib import Path

_MAP = None

def load_map():
    """Return the canonical 22-space map dict (cached)."""
    global _MAP
    if _MAP is None:
        path = Path(__file__).resolve().parents[1] / "map" / "data" / "map.json"
        _MAP = json.loads(path.read_text(encoding="utf-8"))
    return _MAP
