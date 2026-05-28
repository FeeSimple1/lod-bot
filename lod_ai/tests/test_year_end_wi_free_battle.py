"""Regression test for Manual §6.2.2 Free Battle in West Indies.

The Year-End Winter Quarters Supply phase resolves a forced French vs.
British battle in the West Indies when both factions have pieces there
and the Treaty of Alliance has been played.  Per Manual §6.2.2 this
Battle is explicitly *free* (no Resource cost to French).

Before the fix, _supply_phase called battle.execute() without
free=True, which made battle.execute() try to spend 1 Resource from
French.  When French had 0 Resources at year-end (surfaced by 1778
seed 48 in the --large 150-game smoke), the spend() helper raised
ValueError and crashed the whole game during year-end resolution.

The full-game seed-48 replay is sensitive to global state accumulated
by earlier seeds in the batch and does not reproduce reliably in
isolation, so the regression is captured here by a focused unit test
that exercises _supply_phase directly with the crash-triggering
preconditions: French at 0 Resources, both French and British
Regulars in West Indies, TOA played.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random

from lod_ai import rules_consts as C


def test_supply_phase_wi_battle_runs_with_zero_french_resources():
    """Focused unit test: French at 0 Resources + British and French
    Regulars in West Indies + TOA played → _supply_phase must run the
    free WI Battle without raising and without driving French
    Resources negative."""
    from lod_ai.util.year_end import _supply_phase

    state = {
        "spaces": {
            C.WEST_INDIES_ID: {
                C.REGULAR_FRE: 2,
                C.REGULAR_BRI: 2,
                C.BLOCKADE: 0,
                C.SQUADRON: 0,
                C.FORT_BRI: 0,
            },
        },
        "available": {
            C.REGULAR_FRE: 0,
            C.REGULAR_BRI: 0,
            C.SQUADRON: 0,
            C.BLOCKADE: 0,
        },
        "casualties": {},
        "resources": {
            C.FRENCH: 0,      # crucial: cannot afford 1 Resource
            C.BRITISH: 5,
            C.PATRIOTS: 5,
            C.INDIANS: 5,
        },
        "support": {},
        "control": {},
        "history": [],
        "markers": {C.RAID: {"on_map": set()}, C.PROPAGANDA: {"on_map": set()}},
        "rng": random.Random(0),
        "toa_played": True,
        "leaders": {},
        "fni": 0,
    }

    # Must not raise — Manual §6.2.2 says the WI Battle is free.
    _supply_phase(state)

    # French Resources must still be >= 0 (the spend(...) helper would
    # have raised before reaching this assertion if the bug were
    # still present; this is a belt-and-suspenders check).
    assert state["resources"][C.FRENCH] >= 0
