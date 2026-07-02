"""Source-of-truth drift test (agents.md; TRACEABILITY.md T2).

`card reference full.txt` ICON lines are the authority for §8.1/§8.3.1
Sword (auto-ignore) and Brown Bess Musket (special instructions) icons.
This test re-parses the reference and asserts:

1. `lod_ai/cards/data.json` `faction_icons` match it exactly, per card.
2. The per-faction `event_instructions` dicts key exactly the Musket-icon
   cards — no missing directives, no unreachable extras.

(The CONTENT of each directive cannot be audited in-repo: the Event
Instructions sheet text is not in Reference Documents. See QUESTIONS.md.)
"""
import json
import re
from pathlib import Path

from lod_ai.bots import event_instructions as EI

_ROOT = Path(__file__).resolve().parents[2]
_REF = _ROOT / "Reference Documents" / "card reference full.txt"
_DATA = _ROOT / "lod_ai" / "cards" / "data.json"

_LET = {"B": "BRITISH", "P": "PATRIOTS", "F": "FRENCH", "I": "INDIANS"}


def _reference_icons():
    txt = _REF.read_text(encoding="utf-8")
    out = {}
    for chunk in re.split(r"CARD #:\s*", txt)[1:]:
        cid = int(chunk.split()[0])
        m = re.search(r"^ICON:\s*(.+)$", chunk, re.M)
        if not m or m.group(1).strip().lower() == "none":
            out[cid] = {}
            continue
        entry = {}
        for part in m.group(1).split(","):
            pm = re.match(r"\s*([BPFI])\s*[–-]\s*(Sword|Musket)", part)
            assert pm, f"card {cid}: unparsed ICON part {part!r}"
            entry[_LET[pm.group(1)]] = pm.group(2).upper()
        out[cid] = entry
    return out


def test_data_json_faction_icons_match_reference():
    ref = _reference_icons()
    cards = json.loads(_DATA.read_text(encoding="utf-8"))
    if isinstance(cards, dict):
        cards = cards.get("cards", cards)
    checked = 0
    for c in cards:
        cid = c.get("id")
        if cid not in ref:
            continue
        have = {k: v.upper() for k, v in (c.get("faction_icons") or {}).items()}
        assert have == ref[cid], (
            f"card {cid}: data.json faction_icons {have} != reference {ref[cid]}"
        )
        checked += 1
    assert checked == len(ref) == 109


def test_event_instruction_keys_match_musket_icons():
    ref = _reference_icons()
    for fac, dic in (("BRITISH", EI.BRITISH), ("PATRIOTS", EI.PATRIOTS),
                     ("FRENCH", EI.FRENCH), ("INDIANS", EI.INDIANS)):
        musket = {cid for cid, e in ref.items() if e.get(fac) == "MUSKET"}
        assert set(dic) == musket, (
            f"{fac}: directives {sorted(set(dic))} != musket icons "
            f"{sorted(musket)} (missing={sorted(musket - set(dic))}, "
            f"unreachable-extra={sorted(set(dic) - musket)})"
        )


def test_sword_cards_never_underlie_directives():
    ref = _reference_icons()
    for fac, dic in (("BRITISH", EI.BRITISH), ("PATRIOTS", EI.PATRIOTS),
                     ("FRENCH", EI.FRENCH), ("INDIANS", EI.INDIANS)):
        sword = {cid for cid, e in ref.items() if e.get(fac) == "SWORD"}
        assert not (sword & set(dic))


def test_sword_icon_auto_ignores_event(monkeypatch):
    """§8.1: a sword under the faction's symbol means the Non-player
    automatically ignores the Event and continues with the flowchart —
    before directives, the 8.3.3 test, or flowchart conditions run."""
    from lod_ai.bots.base_bot import BaseBot

    bot = BaseBot()
    bot.faction = "BRITISH"
    monkeypatch.setattr(
        bot, "_execute_event",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    card = {"id": 66, "dual": True,
            "faction_icons": {"BRITISH": "SWORD", "FRENCH": "MUSKET"}}
    assert bot._choose_event_vs_flowchart({}, card) is False
