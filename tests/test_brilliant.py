"""
pytest for Milestone-3: Brilliant Stroke logic
Run with:
    pytest -q
"""

import json, pathlib, importlib, copy

SRC = pathlib.Path(__file__).parent.parent   # project root

# JSON snapshot with a leader already on-map (Washington in Massachusetts)
BASE = SRC / "1776_medium.json"


def _fresh_state():
    """Load baseline scenario and build a tiny 2-card deck: 105 + dummy."""
    mod = importlib.import_module("lod_ai_helper_m1to3")
    st  = mod.load_state(BASE)
    st["deck"] = [105, 1]        # Brilliant Stroke then harmless event
    return st, mod


def test_resources_unchanged():
    st, mod = _fresh_state()
    res_before = copy.deepcopy(st["resources"])

    mod.run_turn(st, ["PATRIOTS","BRITISH","INDIANS","FRENCH"])

    # card 105 executed, now at dummy card → resources should match
    assert st["resources"] == res_before


def test_leader_involved_if_present():
    st, mod = _fresh_state()
    # Washington starts on map in baseline JSON

    mod.run_turn(st, ["PATRIOTS"])

    # check Brilliant-Stroke log mentions the space Washington ended in
    leader_space = st["leaders"]["WASHINGTON"]
    if leader_space:                                   # only verify if on map
        assert any(leader_space in line for line in st.get("log", []))

def test_all_eligible_after_stroke():
    st, mod = _fresh_state()

    mod.run_turn(st, ["PATRIOTS"])
    assert st["ineligible"] == set()
    assert st["ineligible_next"] == set()