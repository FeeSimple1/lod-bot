#!/usr/bin/env python3
"""
clean_scenario.py
─────────────────
Normalise Liberty-or-Death scenario JSONs so **all** of them share
the same structure before validation or play.

 • Fix card IDs  → always strings "Card_###" (3-digit, zero-padded)
 • Insert or prune spaces so file has *exactly* the 22 canonical names
 • Canonicalise piece-tag aliases (see _TAG_ALIASES below)
 • Optionally overwrite in-place   ( --inplace flag )

CLI
───
python -m tools.clean_scenario data/1775_long.json
python -m tools.clean_scenario --inplace data/*.json
"""

from __future__ import annotations
import json, re, sys, pathlib, argparse, copy
from typing import Any, Dict, List

# ----------------------------------------------------------------------
#  Map loader  – uses the helper we already added in lod_ai_helper_m1to3
# ----------------------------------------------------------------------
from map_loader import load_map
CANON_SPACES = list(load_map().keys())           # 22 space names, stable order
CANON_SPACE_SET = set(CANON_SPACES)

# ----------------------------------------------------------------------
#  Card-ID helpers
# ----------------------------------------------------------------------
_CARD_RX = re.compile(r"(?:Card_)?(\d{1,3})$")

def _canon_card_id(val: int | str) -> str:
    """
    Accepts 38  or  "Card_038"  →  returns "Card_038"
    """
    m = _CARD_RX.match(str(val).strip())
    if not m:
        raise ValueError(f"Unrecognised card id: {val}")
    return f"Card_{int(m.group(1)):03d}"

def _canon_card_list(card_list: List[int | str]) -> List[str]:
    return [_canon_card_id(c) for c in card_list]

# ----------------------------------------------------------------------
#  Piece-tag aliases  (expand as needed)
# ----------------------------------------------------------------------
_TAG_ALIASES = {
    "_Militia_U": "Patriot_Militia_U",
    "_Militia_A": "Patriot_Militia_A",
    "_WP_U":      "Indian_WarParty_U",
    "_WP_A":      "Indian_WarParty_A",
}

def _canon_piece_tag(tag: str) -> str:
    return _TAG_ALIASES.get(tag, tag)

def _canon_space_dict(space_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonicalise every key in one space entry
    """
    fixed: Dict[str, Any] = {}
    for k, v in space_dict.items():
        fixed[_canon_piece_tag(k)] = v
    return fixed

# ----------------------------------------------------------------------
#  Core cleaning function
# ----------------------------------------------------------------------
def clean_scenario(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = copy.deepcopy(data)

    # ---- cards -------------------------------------------------------
    cleaned["current_event"]  = _canon_card_id(cleaned["current_event"])
    cleaned["upcoming_event"] = _canon_card_id(cleaned["upcoming_event"])
    cleaned["deck"]           = _canon_card_list(cleaned["deck"])

    # ---- spaces ------------------------------------------------------
    spaces_in_file = set(cleaned["spaces"].keys())

    # add any missing spaces with empty dicts
    for s in CANON_SPACES:
        cleaned["spaces"].setdefault(s, {})

    # remove extraneous / misspelled spaces
    for extra in spaces_in_file - CANON_SPACE_SET:
        cleaned["spaces"].pop(extra, None)

    # canonicalise every piece tag in every space
    for s in CANON_SPACES:
        cleaned["spaces"][s] = _canon_space_dict(cleaned["spaces"][s])

    # retain the original space order for readability
    cleaned["spaces"] = {s: cleaned["spaces"][s] for s in CANON_SPACES}
    return cleaned

# ----------------------------------------------------------------------
#  CLI
# ----------------------------------------------------------------------
def _parse_cli():
    p = argparse.ArgumentParser(prog="tools.clean_scenario")
    p.add_argument("--inplace", action="store_true",
                   help="overwrite each file instead of creating *_clean.json")
    p.add_argument("files", nargs="+", help="scenario JSON files")
    return p.parse_args()

def _main():
    args = _parse_cli()
    for path_str in args.files:
        path = pathlib.Path(path_str)
        data = json.loads(path.read_text(encoding="utf-8"))
        cleaned = clean_scenario(data)

        if args.inplace:
            out_path = path
        else:
            out_path = path.with_stem(path.stem + "_clean")

        out_path.write_text(json.dumps(cleaned, indent=2))
        print(f"✓ cleaned {path.name} → {out_path.name}")

if __name__ == "__main__":
    _main()