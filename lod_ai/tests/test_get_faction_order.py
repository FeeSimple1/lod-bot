import json
from pathlib import Path

from lod_ai.cards import get_faction_order
from lod_ai import rules_consts


def test_get_faction_order_standard():
    path = Path(__file__).resolve().parents[1] / "cards" / "data.json"
    first_card = json.loads(path.read_text(encoding="utf-8"))[0]
    order = get_faction_order(first_card)
    assert order == [
        rules_consts.PATRIOTS,
        rules_consts.BRITISH,
        rules_consts.FRENCH,
        rules_consts.INDIANS,
    ]


def test_get_faction_order_empty():
    assert get_faction_order({"order_icons": ""}) == []
