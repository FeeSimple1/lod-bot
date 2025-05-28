#!/usr/bin/env python3
"""
build_map.py
  • default      : validate lod_ai/map/data/map.json
  • --template   : create data/map_template.csv with correct headers
"""

import csv, glob, json, sys
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
JSON_PATH   = ROOT / "lod_ai" / "map" / "data" / "map.json"
TEMPLATE_CSV = ROOT / "data" / "map_template.csv"

# --------------------------------------------------------------------
def _collect_space_names() -> list[str]:
    names = set()
    for fn in glob.glob(str(ROOT / "data" / "177*.json")):
        names.update(json.load(open(fn))["spaces"].keys())
    return sorted(names)

# --------------------------------------------------------------------
def _validate_json() -> dict[str, dict]:
    if not JSON_PATH.exists():
        sys.exit(f"ERROR: {JSON_PATH} not found")

    spaces: dict[str, dict] = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    required = {"type", "adj"}
    for name, info in spaces.items():
        if not required.issubset(info):
            sys.exit(f"ERROR: {name} missing {sorted(required)}")

    print(f"✓ Validated {len(spaces)} spaces in {JSON_PATH.relative_to(ROOT)}")
    return spaces

# --------------------------------------------------------------------
def _write_template(names: list[str]):
    with TEMPLATE_CSV.open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["space", "type", "adj"])
        for n in names:
            w.writerow([n, "", ""])
    print(f"✓ Created blank {TEMPLATE_CSV.relative_to(ROOT)} with {len(names)} rows")

# --------------------------------------------------------------------
if __name__ == "__main__":
    if "--template" in sys.argv:
        _write_template(_collect_space_names())
    else:
        _validate_json()
