"""Session 54 — §8.4 British pass: Muster SA order + Loyalist Desertion."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.british_bot import BritishBot
from lod_ai import rules_consts as C


def test_loyalist_desertion_rescored_per_tory():
    """§8.4.10: least Control change, spare last Tory — re-scored per
    piece.  A 2-Tory stack whose second removal flips Control must not
    be bulk-emptied while a safe big stack exists."""
    bot = BritishBot()
    st = {
        "spaces": {
            # Removing BOTH Tories here flips BRITISH → none (2v1 → 1v1);
            # removing one is safe.
            "Virginia": {C.TORY: 2, C.MILITIA_U: 1},
            # Big safe stack: removals never change Control.
            "Pennsylvania": {C.TORY: 6},
        },
        "resources": {}, "available": {}, "support": {}, "control": {},
        "rng": random.Random(4), "history": [],
    }
    removals = bot.bot_loyalist_desertion(st, 4)
    assert sum(n for _, n in removals) == 4
    va = sum(n for s, n in removals if s == "Virginia")
    # At most 1 from Virginia (the 2nd would change Control AND strip
    # the last Tory while Pennsylvania still has safe ones)
    assert va <= 1


def test_muster_sa_order_is_skirmish_first():
    """§8.4.2: "also Skirmish ... or, if that is not possible, Naval
    Pressure" — source-level guard against re-inverting (Session 31
    had applied Garrison's §8.4.1 NP-first order to Muster)."""
    import inspect
    from lod_ai.bots import british_bot
    src = inspect.getsource(british_bot.BritishBot._muster)
    assert "_skirmish_then_naval" in src
    assert "_naval_then_skirmish" not in src
