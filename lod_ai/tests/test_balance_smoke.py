"""Canary for bot-balance drift.

Replays 3 fixed-seed bot-only games per scenario in a hash-seed-pinned
subprocess and compares winners to lod_ai/tools/balance_baseline.json.
Any flip fails (band 0.30 < 1/3): with a pinned hash seed the engine is
deterministic, so a flip means a code change altered game outcomes.

If your change is INTENDED to alter outcomes (rules fix, bot change),
refresh the baseline and commit it:

    python -m lod_ai.tools.balance_smoke --update
"""
import subprocess
import sys
from pathlib import Path

import pytest

_BASELINE = Path(__file__).resolve().parents[1] / "tools" / "balance_baseline.json"


@pytest.mark.skipif(not _BASELINE.exists(), reason="no balance baseline committed")
def test_bot_balance_canary():
    proc = subprocess.run(
        [sys.executable, "-m", "lod_ai.tools.balance_smoke",
         "--seeds", "1-3", "--band", "0.30"],
        capture_output=True, text=True, timeout=300,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode == 0, (
        "Bot balance drifted from baseline (see output below). If this is an "
        "intended rules/bot change, run "
        "'python -m lod_ai.tools.balance_smoke --update' and commit the "
        "refreshed baseline.\n\n" + proc.stdout[-2000:] + proc.stderr[-500:]
    )
