#!/usr/bin/env python3
"""
build_cards.py
--------------
Parse “card reference.txt” and write lod_ai/cards/data.json.

Each card record in the JSON contains:
  id              int
  title           str
  years           list[int]       # 1775-1780, [] for WQ / Brilliant Stroke
  order_icons     str             # e.g. "PBFI"
  ops_icon        str | None      # "P – Musket", "I – Sword", or None
  winter_quarters bool
  type            str             # "EVENT" | "BRILLIANT_STROKE"
  dual            bool            # True for normal events
"""
import json
import pathlib
import re

# -----------------------------------------------------------------------------#
# Paths (relative to repo root)
# -----------------------------------------------------------------------------#
SRC = pathlib.Path("Reference Documents/card reference full.txt")
DEST = pathlib.Path("lod_ai/cards/data.json")
ENC = "utf-8"                     # force UTF-8 so Windows won’t choke

# -----------------------------------------------------------------------------#
# Regex helpers
# -----------------------------------------------------------------------------#
card_pat = re.compile(r"^CARD #:\s*(\d+)")
key_pat = re.compile(r"^(TITLE|YEARS|ORDER|ICON|WINTER_QUARTERS|TYPE):\s*(.*)")
range_pat = re.compile(r"(\d{4})(?:\s*[–-]\s*(\d{2,4}))?")  # 1777 or 1777-80

# -----------------------------------------------------------------------------#
# Parse the reference text
# -----------------------------------------------------------------------------#
cards: list[dict] = []
cur: dict | None = None

for line in SRC.read_text(encoding=ENC).splitlines():
    if m := card_pat.match(line):
        if cur:
            cards.append(cur)          # flush previous card
        cur = {
            "id": int(m.group(1)),
            "title": "",
            "years": [],
            "order_icons": "",
            "ops_icon": None,
            "winter_quarters": False,
            "type": "EVENT",
        }
        continue

    if not cur:
        continue                       # ignore header junk before first card

    if m := key_pat.match(line):
        key, val = m.groups()
        val = val.strip()

        match key:
            # ------------------------------------------------ simple fields --
            case "TITLE":
                cur["title"] = val

            case "ORDER":
                cur["order_icons"] = val

            case "ICON":
                cur["ops_icon"] = None if val.lower() == "none" else val

            case "WINTER_QUARTERS":
                cur["winter_quarters"] = True

            case "TYPE":
                cur["type"] = val.split()[0]        # strip comment tails

            # ------------------------------------------------ YEAR parser ----
            case "YEARS":
                years: list[int] = []
                for y_match in range_pat.finditer(val):
                    start = int(y_match.group(1))
                    end_raw = y_match.group(2)
                    if end_raw:
                        end = (
                            int(end_raw)
                            if len(end_raw) == 4
                            else (start // 100) * 100 + int(end_raw)
                        )
                        years.extend(range(start, end + 1))
                    else:
                        years.append(start)
                cur["years"] = sorted(set(years))

# flush final card
if cur:
    cards.append(cur)

# -----------------------------------------------------------------------------#
# Post-process: add “dual” flag
# -----------------------------------------------------------------------------#
for c in cards:
    c["dual"] = (
        c["type"] == "EVENT" and not c["winter_quarters"]
    )

# -----------------------------------------------------------------------------#
# Write JSON
# -----------------------------------------------------------------------------#
DEST.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(cards)} cards → {DEST}")
