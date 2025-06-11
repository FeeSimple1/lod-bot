import json
import re
from lod_ai.state import setup_state


def _id_from_val(val):
    m = re.match(r"(?:Card_)?(\d{1,3})$", str(val))
    return int(m.group(1)) if m else None


def test_build_state_initial_deck(tmp_path, monkeypatch):
    scen = {
        "scenario": "Test",
        "spaces": {},
        "resources": {"BRITISH": 0, "PATRIOTS": 0, "FRENCH": 0, "INDIANS": 0},
        "current_event": "Card_001",
        "upcoming_event": "Card_002",
        "deck": ["Card_002", "Card_003", "Card_004"],
    }
    path = tmp_path / "scen.json"
    path.write_text(json.dumps(scen))
    monkeypatch.setattr(setup_state, "_DATA_DIR", tmp_path)

    state = setup_state.build_state(path.name, seed=1)

    assert state["upcoming_card"]["id"] == 2
    orig_order = [_id_from_val(c) for c in scen["deck"] if _id_from_val(c) != 2]
    deck_ids = [c["id"] for c in state["deck"]]
    assert deck_ids != orig_order

