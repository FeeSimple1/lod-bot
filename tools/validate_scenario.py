#!/usr/bin/env python3
"""
validate_scenario.py
────────────────────
Milestone-1 integrity checks for Liberty or Death scenario JSON files.

 • Loads each file            → cleans it in-memory via clean_scenario.clean_scenario
 • Verifies the 22 canonical map spaces (no extras, no missing)
 • Confirms card-ID fields are "Card_###" strings
 • Checks Resources, FNI, Forts, Villages, etc. do not exceed MAX_* caps
 • Reports ALL problems, then exits with code 1 if any scenario fails

CLI
───
python -m tools.validate_scenario data/1775_long.json
python -m tools.validate_scenario data/177*.json
"""

from __future__ import annotations
import argparse, json, re, sys, pathlib
from typing import Any, Dict, List

# ----------------------------------------------------------------------
#  Project helpers
# ----------------------------------------------------------------------
from map_loader import load_map
from tools.clean_scenario import clean_scenario
import rules_consts as C          # holds MAX_* constants per Milestone-0

MAP         = load_map()          # 22-space dict
MAP_SPACES  = set(MAP.keys())
CARD_RX     = re.compile(r"Card_\d{3}$")

# ----------------------------------------------------------------------
def _as_int(val) -> int:
    try:
        return int(val)
    except Exception:
        return -999999          # force failure later

# ----------------------------------------------------------------------
def _check_caps(state: Dict[str, Any], errs: List[str]):
    """
    Verify the global caps declared in rules_consts.py
    Expected names (per Milestone 0):  MAX_RESOURCES  MAX_FNI  MAX_FORTS  …
    We treat any attr that starts with 'MAX_' and is an int as a global cap.
    """
    for attr in dir(C):
        if not attr.startswith("MAX_"):
            continue
        cap = getattr(C, attr)
        if not isinstance(cap, int):
            continue

        field = attr[4:].lower()          # e.g. 'RESOURCES' → 'resources'
        if field not in state:
            continue                      # not present in this snapshot

        value = _as_int(state[field])
        if value > cap:
            errs.append(f"{field} {value} exceeds {attr}={cap}")

# ----------------------------------------------------------------------
def validate(data: Dict[str, Any]) -> List[str]:
    """
    Return a list of validation-error strings (empty → file is OK).
    """
    errs: List[str] = []

    # ---------- map completeness -------------------------------------
    file_spaces = set(data["spaces"])
    missing = MAP_SPACES - file_spaces
    extras  = file_spaces - MAP_SPACES
    if missing:
        errs.append(f"missing space keys: {', '.join(sorted(missing))}")
    if extras:
        errs.append(f"unknown space keys: {', '.join(sorted(extras))}")

    # ---------- card-ID sanity ---------------------------------------
    for field in ("current_event", "upcoming_event"):
        if not CARD_RX.fullmatch(data[field]):
            errs.append(f"{field}='{data[field]}' not in 'Card_###' form")

    seen: set[str] = set()
    for cid in data["deck"]:
        if not CARD_RX.fullmatch(cid):
            errs.append(f"deck entry '{cid}' not in 'Card_###' form")
        if cid in seen:
            errs.append(f"deck contains duplicate '{cid}'")
        seen.add(cid)

    # ---------- numeric caps (Resources, FNI, forts, villages …) -----
    _check_caps(data, errs)

    return errs

# ----------------------------------------------------------------------
#  CLI
# ----------------------------------------------------------------------
def _parse_cli():
    p = argparse.ArgumentParser(prog="tools.validate_scenario")
    p.add_argument("files", nargs="+", help="scenario JSON paths (glob ok)")
    return p.parse_args()

def main():
    args = _parse_cli()
    any_fail = False

    for fn in args.files:
        path  = pathlib.Path(fn)
        raw   = json.loads(path.read_text(encoding="utf-8"))
        clean = clean_scenario(raw)           # canonicalise in-memory

        errs = validate(clean)
        if errs:
            any_fail = True
            print(f"\n✗ {path.name} failed:")
            for e in errs:
                print(f"   • {e}")
        else:
            print(f"✓ {path.name}  OK")

    if any_fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
