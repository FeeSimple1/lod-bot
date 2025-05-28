#!/usr/bin/env python3
"""
build_map.py
  • default      : read data/map_base.csv  →  write lod_ai/map/data/map.json
  • --template   : recreate a blank CSV with correct headers
"""

import csv, glob, json, sys
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
CSV_PATH   = ROOT / "data" / "map_base.csv"
JSON_PATH  = ROOT / "lod_ai" / "map" / "data" / "map.json"

# --------------------------------------------------------------------
def _collect_space_names() -> list[str]:
    names = set()
    for fn in glob.glob(str(ROOT / "data" / "177*.json")):
        names.update(json.load(open(fn))["spaces"].keys())
    return sorted(names)

# --------------------------------------------------------------------
def _parse_csv() -> dict[str, dict]:
    if not CSV_PATH.exists():
        sys.exit(f"ERROR: {CSV_PATH} not found")

    spaces: dict[str, dict] = {}
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Accept either 'space' or legacy 'name' as the first column
        cols = set(reader.fieldnames or [])
        if "space" not in cols and "name" in cols:
            reader.fieldnames[reader.fieldnames.index("name")] = "space"
            cols = set(reader.fieldnames)

        required = {"space", "type", "adj"}
        if not required.issubset(cols):
            sys.exit(f"ERROR: {CSV_PATH} must contain columns {sorted(required)}")

        for row in reader:
            name = row["space"].strip()
            if not name:
                continue
            spaces[name] = {
                "type": row["type"].strip(),
                "adj": [n.strip() for n in row["adj"].replace(";", ",").split(",") if n.strip()],
            }
    return spaces

# --------------------------------------------------------------------
def _write_json(spaces: dict):
    JSON_PATH.write_text(json.dumps(spaces, indent=2))
    print(f"✓ Wrote {len(spaces)} spaces to {JSON_PATH.relative_to(ROOT)}")

def _write_template(names: list[str]):
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["space", "type", "adj"])
        for n in names:
            w.writerow([n, "", ""])
    print(f"✓ Created blank {CSV_PATH.relative_to(ROOT)} with {len(names)} rows")

# --------------------------------------------------------------------
if __name__ == "__main__":
    if "--template" in sys.argv:
        _write_template(_collect_space_names())
    else:
        _write_json(_parse_csv())
