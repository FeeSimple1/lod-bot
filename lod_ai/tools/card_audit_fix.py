from __future__ import annotations

"""Audit and repair card data against reference documents.

Usage
-----
python -m lod_ai.tools.card_audit_fix --card-ref "reference_docs/card reference full.txt" \
    --rules-ref "reference_docs/rules_consts.py" [--write]

The script parses the authoritative card reference file, enforces the card
schema used by the engine/bots, removes forbidden fields (for example, any
ops/ops_value variants), and repairs ``lod_ai/cards/data.json`` plus the card
grouping constants in ``lod_ai/rules_consts.py``.  When ``--write`` is **not**
passed it only reports mismatches.
"""

import argparse
import ast
import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "lod_ai" / "cards" / "data.json"
RULES_TARGET = REPO_ROOT / "lod_ai" / "rules_consts.py"

FACTION_ICON_MAP = {
    "P": "PATRIOTS",
    "B": "BRITISH",
    "F": "FRENCH",
    "I": "INDIANS",
}

# ---------------------------------------------------------------------------
# Schema definition used for validation + rewrite
# ---------------------------------------------------------------------------
CARD_FIELDS: Sequence[str] = (
    "id",
    "title",
    "type",
    "years",
    "order_icons",
    "order",
    "faction_icons",
    "musket",
    "sword",
    "winter_quarters",
    "dual",
    "unshaded_event",
    "shaded_event",
    "effect",
    "note",
)

CARD_SCHEMA: Dict[str, str] = {
    "id": "int (required)",
    "title": "str (required)",
    "type": "str (required; EVENT or BRILLIANT_STROKE)",
    "years": "list[int] (required; may be empty for Winter Quarters/BS)",
    "order_icons": "str (required; empty string if none)",
    "order": "list[str] faction codes derived from order_icons",
    "faction_icons": "dict[faction->icon] where icon is MUSKET or SWORD",
    "musket": "bool aggregate flag (any MUSKET icons present)",
    "sword": "bool aggregate flag (SWORD present and no MUSKET)",
    "winter_quarters": "bool",
    "dual": "bool (True when both shaded/unshaded text apply)",
    "unshaded_event": "str | None (required when dual)",
    "shaded_event": "str | None (required when dual)",
    "effect": "str | None (used for single-sided cards)",
    "note": "str | None (reference notes)",
}


@dataclass
class CardDiff:
    card_id: int
    title: str
    issues: List[str]


def _resolve_path(path_str: str, description: str, fallback: Path | None = None) -> Path:
    """Resolve *path_str* relative to the repo, tolerating the legacy
    "Reference Documents" directory name.
    """

    raw = Path(path_str)
    candidates: List[Path] = []

    def _append(p: Path) -> None:
        if p not in candidates:
            candidates.append(p)

    _append(raw)
    if not raw.is_absolute():
        _append(REPO_ROOT / raw)

    if "reference_docs" in raw.parts:
        alt_parts = ["Reference Documents" if part == "reference_docs" else part for part in raw.parts]
        alt = Path(*alt_parts)
        _append(alt)
        if not alt.is_absolute():
            _append(REPO_ROOT / alt)

    for cand in candidates:
        if cand.exists():
            return cand

    if fallback and fallback.exists():
        return fallback

    raise FileNotFoundError(f"{description} not found: {path_str}")


def _clean_text(lines: Iterable[str]) -> str:
    joined = "\n".join(line.strip() for line in lines if line.strip())
    text = joined.strip()
    if text.startswith("\"") and text.endswith("\"") and len(text) >= 2:
        text = text[1:-1].strip()
    return text


def _parse_icon_map(raw: str | None) -> Dict[str, str]:
    if not raw or raw.strip().lower() == "none":
        return {}

    mapping: Dict[str, str] = {}
    for chunk in raw.split(','):
        part = chunk.strip()
        match = re.match(r"([BPIF])\s*[\u2013-]\s*(Musket|Sword)", part, flags=re.IGNORECASE)
        if not match:
            mapping[part or "UNKNOWN"] = "UNKNOWN"
            continue
        faction = FACTION_ICON_MAP[match.group(1).upper()]
        mapping[faction] = match.group(2).upper()
    return {k: mapping[k] for k in sorted(mapping)}


def _parse_years(raw: str | None) -> List[int]:
    if not raw:
        return []
    nums = []
    for chunk in raw.replace(' ', '').split('-'):
        if chunk.isdigit():
            nums.append(int(chunk))
    return nums


def _parse_reference_cards(path: Path) -> List[Dict]:
    raw = path.read_text(encoding="utf-8").replace("\r", "")
    blocks = re.split(r"\n(?=CARD #:)", raw.strip())
    cards: List[Dict] = []

    for block in blocks:
        lines = block.strip().splitlines()
        card: Dict[str, object] = {}
        active_field: str | None = None
        buffer: List[str] = []

        def flush() -> None:
            nonlocal active_field, buffer
            if active_field:
                card[active_field] = _clean_text(buffer)
                buffer = []
                active_field = None

        for raw_line in lines:
            line = raw_line.strip()
            if line.startswith("CARD #:"):
                flush()
                card["id"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("TITLE:"):
                flush()
                card["title"] = line.split(":", 1)[1].strip()
            elif line.startswith("YEARS:"):
                flush()
                card["years_raw"] = line.split(":", 1)[1].strip()
            elif line.startswith("ORDER:"):
                flush()
                card["order_icons"] = line.split(":", 1)[1].strip()
            elif line.startswith("ICON:"):
                flush()
                card["icon_raw"] = line.split(":", 1)[1].strip()
            elif line.startswith("WINTER_QUARTERS:"):
                flush()
                val = line.split(":", 1)[1].strip().lower()
                card["winter_quarters"] = val.startswith("y")
            elif line.startswith("TYPE:"):
                flush()
                card["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("UNSHADED:"):
                flush()
                active_field = "unshaded_event"
            elif line.startswith("SHADED:"):
                flush()
                active_field = "shaded_event"
            elif line.startswith("EFFECT:"):
                flush()
                active_field = "effect"
            elif line.startswith("NOTE:"):
                flush()
                active_field = "note"
            else:
                if active_field:
                    buffer.append(raw_line)

        flush()
        cards.append(card)

    return cards


def _enforce_schema(card: Dict) -> tuple[Dict, set[str]]:
    extras = set(card.keys()) - set(CARD_FIELDS)
    cleaned: Dict[str, object] = {}

    cleaned["id"] = int(card.get("id", 0))
    cleaned["title"] = str(card.get("title", "UNKNOWN"))
    cleaned["type"] = str(card.get("type", "EVENT"))

    years_raw = card.get("years") or []
    cleaned["years"] = [int(y) for y in years_raw if isinstance(y, (int, float, str)) and str(y).isdigit()]

    cleaned["order_icons"] = str(card.get("order_icons", "") or "")
    order_list = card.get("order") or []
    cleaned["order"] = [str(f).upper() for f in order_list if f]

    icons = card.get("faction_icons") or {}
    if isinstance(icons, dict):
        cleaned["faction_icons"] = {str(k): str(v) for k, v in sorted(icons.items())}
    else:
        cleaned["faction_icons"] = {}

    cleaned["musket"] = bool(card.get("musket", False))
    cleaned["sword"] = bool(card.get("sword", False))
    cleaned["winter_quarters"] = bool(card.get("winter_quarters", False))
    cleaned["dual"] = bool(card.get("dual", False))

    cleaned["unshaded_event"] = card.get("unshaded_event") if cleaned["dual"] else None
    cleaned["shaded_event"] = card.get("shaded_event") if cleaned["dual"] else None
    cleaned["effect"] = None if cleaned["dual"] else card.get("effect")
    cleaned["note"] = card.get("note")

    return cleaned, extras


def _build_expected_cards(ref_cards: List[Dict]) -> tuple[List[Dict], List[str]]:
    expected: List[Dict] = []
    warnings: List[str] = []

    for ref in ref_cards:
        cid = int(ref.get("id", 0))
        years = _parse_years(str(ref.get("years_raw", "") or ""))
        order_icons = str(ref.get("order_icons", "") or "")
        order = [FACTION_ICON_MAP[ch] for ch in order_icons if ch in FACTION_ICON_MAP]
        faction_icons = _parse_icon_map(str(ref.get("icon_raw", "") or ""))
        has_musket = any(v == "MUSKET" for v in faction_icons.values())
        has_sword = any(v == "SWORD" for v in faction_icons.values()) and not has_musket

        dual = bool(ref.get("unshaded_event") and ref.get("shaded_event"))
        ref_type = str(ref.get("type", "EVENT")).strip().upper()
        is_brilliant = ref_type.startswith("BRILLIANT_STROKE")
        is_wq = bool(ref.get("winter_quarters", False))
        dual = dual and not is_brilliant and not is_wq

        card = {
            "id": cid,
            "title": str(ref.get("title", "UNKNOWN")),
            "type": "BRILLIANT_STROKE" if is_brilliant else "EVENT",
            "years": years,
            "order_icons": order_icons,
            "order": order,
            "faction_icons": faction_icons,
            "musket": has_musket,
            "sword": has_sword,
            "winter_quarters": is_wq,
            "dual": dual,
            "unshaded_event": ref.get("unshaded_event") if dual else None,
            "shaded_event": ref.get("shaded_event") if dual else None,
            "effect": None if dual else ref.get("effect"),
            "note": ref.get("note"),
        }

        cleaned, extras = _enforce_schema(card)
        expected.append(cleaned)

        for field in extras:
            warnings.append(f"Card {cid} has unsupported reference field '{field}' (ignored)")

    expected.sort(key=lambda c: c["id"])
    return expected, warnings


def _diff_cards(expected: List[Dict], current: List[Dict]) -> tuple[List[CardDiff], List[int], List[int], List[str]]:
    expected_map = {c["id"]: c for c in expected}
    current_map = {c["id"]: c for c in current}

    missing_ids = sorted(set(expected_map) - set(current_map))
    extra_ids = sorted(set(current_map) - set(expected_map))
    diffs: List[CardDiff] = []
    field_warnings: List[str] = []

    for cid, expected_card in expected_map.items():
        current_card = current_map.get(cid)
        if not current_card:
            continue

        issues: List[str] = []
        current_extras = set(current_card.keys()) - set(CARD_FIELDS)
        for extra in sorted(current_extras):
            issues.append(f"unexpected field '{extra}' present")

        for field in CARD_FIELDS:
            if expected_card.get(field) != current_card.get(field):
                issues.append(
                    f"{field}: expected {expected_card.get(field)!r} != {current_card.get(field)!r}"
                )

        if issues:
            diffs.append(CardDiff(card_id=cid, title=str(expected_card.get("title", "")), issues=issues))

    if not current:
        field_warnings.append("Current data.json is empty or malformed")

    return diffs, missing_ids, extra_ids, field_warnings


def _load_current_cards() -> List[Dict]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    current: List[Dict] = []
    for entry in data if isinstance(data, list) else []:
        cleaned, _ = _enforce_schema(entry)
        current.append(cleaned)
    current.sort(key=lambda c: c["id"])
    return current


def _load_handlers() -> set[int]:
    import lod_ai.cards as cards  # import inside to avoid side effects at module import

    cards.CARD_HANDLERS.clear()
    modules = [
        "lod_ai.cards.effects.early_war",
        "lod_ai.cards.effects.middle_war",
        "lod_ai.cards.effects.late_war",
        "lod_ai.cards.effects.winter_quarters",
        "lod_ai.cards.effects.brilliant_stroke",
    ]

    for mod in modules:
        importlib.import_module(mod)

    return set(cards.CARD_HANDLERS)


def _read_rules_sets(path: Path) -> Dict[str, set[int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: Dict[str, set[int]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "WINTER_QUARTERS_CARDS",
                    "BRILLIANT_STROKE_CARDS",
                }:
                    values = {
                        int(elt.n)
                        for elt in getattr(node.value, "elts", [])
                        if isinstance(elt, ast.Constant) and isinstance(elt.n, (int, float))
                    }
                    found[target.id] = values
    return found


def _apply_rules_fixes(text: str, name: str, values: Iterable[int]) -> tuple[str, bool]:
    replacement = f"{name} = {{{', '.join(str(v) for v in sorted(set(values)))}}}"
    pattern = re.compile(rf"{name}\s*=\s*\{{[^\}}]*\}}")
    new_text, count = pattern.subn(replacement, text, count=1)
    changed = bool(count and new_text != text)
    return (new_text if count else text, changed)


def _write_cards(cards: List[Dict]) -> None:
    ordered_cards: List[Dict] = []
    for card in cards:
        ordered = {field: card.get(field) for field in CARD_FIELDS}
        ordered_cards.append(ordered)

    DATA_PATH.write_text(json.dumps(ordered_cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit and repair lod_ai card data")
    parser.add_argument("--card-ref", required=True, help="Path to card reference file")
    parser.add_argument("--rules-ref", required=True, help="Path to reference rules_consts.py")
    parser.add_argument("--write", action="store_true", help="Apply fixes to data.json and rules_consts.py")
    args = parser.parse_args(argv)

    card_ref_path = _resolve_path(args.card_ref, "Card reference")
    rules_ref_path = _resolve_path(args.rules_ref, "Rules reference", fallback=RULES_TARGET)

    ref_cards = _parse_reference_cards(card_ref_path)
    expected_cards, schema_warnings = _build_expected_cards(ref_cards)
    current_cards = _load_current_cards()

    diffs, missing_ids, extra_ids, field_warnings = _diff_cards(expected_cards, current_cards)
    handler_ids = _load_handlers()
    missing_handlers = [c["id"] for c in expected_cards if c["id"] not in handler_ids]

    rules_ref_sets = _read_rules_sets(rules_ref_path)
    expected_wq = {c["id"] for c in expected_cards if c.get("winter_quarters")}
    expected_bs = {c["id"] for c in expected_cards if c.get("type") == "BRILLIANT_STROKE"}

    target_rules_text = RULES_TARGET.read_text(encoding="utf-8")
    new_rules_text, wq_changed = _apply_rules_fixes(target_rules_text, "WINTER_QUARTERS_CARDS", expected_wq)
    new_rules_text, bs_changed = _apply_rules_fixes(new_rules_text, "BRILLIANT_STROKE_CARDS", expected_bs)

    if args.write:
        _write_cards(expected_cards)
        if wq_changed or bs_changed:
            RULES_TARGET.write_text(new_rules_text, encoding="utf-8")

    # --- Report ----------------------------------------------------------
    print(f"Reference cards: {len(ref_cards)} | Current data entries: {len(current_cards)} | Expected schema fields: {len(CARD_FIELDS)}")
    print(f"Card reference path: {card_ref_path}")
    print(f"Rules reference path: {rules_ref_path}")

    for warning in (*schema_warnings, *field_warnings):
        print(f"WARNING: {warning}")

    if missing_ids:
        print(f"Missing card IDs in data.json: {missing_ids}")
    if extra_ids:
        print(f"Extra card IDs in data.json: {extra_ids}")

    if diffs:
        print("\nMISMATCHES (Expected vs Implemented):")
        for diff in diffs:
            print(f"- Card {diff.card_id} – {diff.title}")
            for issue in diff.issues:
                print(f"    • {issue}")
    else:
        print("\nAll card fields match reference.")

    if missing_handlers:
        print("\nCards missing effect handlers:")
        print(", ".join(str(cid) for cid in missing_handlers))
    else:
        print("\nAll cards have registered effect handlers.")

    if rules_ref_sets:
        for name, values in sorted(rules_ref_sets.items()):
            print(f"Reference {name}: {sorted(values)}")

    if wq_changed or bs_changed:
        print("Rules constants updated to match reference sets." if args.write else "Rules constants would be updated to match reference sets.")
    else:
        print("Rules constants already match expected sets.")


if __name__ == "__main__":
    main()
