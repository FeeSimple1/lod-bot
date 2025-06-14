import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.indians import choose_command
from lod_ai import rules_consts as C


def state_template():
    return {
        "spaces": {},
        "resources": {"INDIANS": 2},
    }


def test_choose_scout():
    st = state_template()
    st["spaces"] = {
        "A": {C.WARPARTY_U: 1, C.REGULAR_BRI: 1, "adj": ["B"]},
        "B": {},
    }
    cmd, loc = choose_command(st)
    assert cmd == "SCOUT"


def test_choose_war_path():
    st = state_template()
    st["spaces"] = {
        "A": {C.WARPARTY_U: 1, C.REGULAR_PAT: 1},
    }
    cmd, loc = choose_command(st)
    assert cmd == "WAR_PATH" and loc == "A"


def test_choose_gather_fallback():
    st = state_template()
    st["spaces"] = {"A": {}}
    cmd, loc = choose_command(st)
    assert cmd == "GATHER"

