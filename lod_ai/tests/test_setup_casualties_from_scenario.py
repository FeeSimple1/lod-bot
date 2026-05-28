"""Regression test: setup_state reads cumulative casualty counters from
the scenario JSON instead of hardcoding 0.

Before the fix lod_ai/state/setup_state.py wrote `"cbc": 0, "crc": 0`
unconditionally.  The 1776 scenario reference (Reference Documents/
1776 Scenario Reference.txt) specifies "Cumulative British Casualties:
1" and "Cumulative Rebellion Casualties: 3", which the data file
encodes as british_casualties=1 / patriot_casualties=3.  Resetting to
0 silently moved:
  * British Margin 2 (CRC - CBC) from +2 to 0
  * French Margin 2 (CBC - CRC) from -2 to 0
  * French Preparations (§2.3.9 includes +CBC) by -1

Fix: read scen['british_casualties'] / scen['patriot_casualties'].
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.state.setup_state import build_state


def test_1776_starts_with_cbc_1_and_crc_3():
    """1776 Scenario Reference: CBC=1, CRC=3 at start."""
    state = build_state("1776", seed=1)
    assert state["cbc"] == 1, (
        f"1776 CBC should be 1 per Scenario Reference; got {state['cbc']}"
    )
    assert state["crc"] == 3, (
        f"1776 CRC should be 3 per Scenario Reference; got {state['crc']}"
    )


def test_1775_starts_with_zero_casualties():
    """1775 Scenario Reference doesn't list cumulative casualties, so
    they default to 0.  Verifies the fix doesn't break 1775."""
    state = build_state("1775", seed=1)
    assert state["cbc"] == 0
    assert state["crc"] == 0


def test_1778_starts_with_scenario_casualties():
    """1778 scenario should also use whatever the JSON specifies."""
    import json
    fn = Path(__file__).resolve().parents[2] / "data" / "1778_short.json"
    d = json.loads(fn.read_text())
    state = build_state("1778", seed=1)
    assert state["cbc"] == d.get("british_casualties", 0), (
        f"1778 CBC should match scenario JSON ({d.get('british_casualties', 0)}); "
        f"got {state['cbc']}"
    )
    assert state["crc"] == d.get("patriot_casualties", 0), (
        f"1778 CRC should match scenario JSON ({d.get('patriot_casualties', 0)}); "
        f"got {state['crc']}"
    )
