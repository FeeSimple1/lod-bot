"""Session 49 — event_eval / Event-or-Command bullet audit regressions."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai.cards.effects import early_war
from lod_ai import rules_consts as C


def _st(**extra):
    st = {
        "spaces": {},
        "available": {},
        "unavailable": {},
        "casualties": {},
        "markers": {},
        "support": {},
        "control": {},
        "resources": {"BRITISH": 5, "PATRIOTS": 5, "INDIANS": 5, "FRENCH": 5},
        "rng": random.Random(5),
        "history": [],
    }
    st.update(extra)
    return st


def test_b2_bullet2_reads_real_unavailable_keys():
    """§8.4 bullet 2 was dead: it read C.BRIT_UNAVAIL, but real states key
    the box by REGULAR_BRI/TORY (same class as the S30 French F2 bug)."""
    bot = BritishBot()
    st = _st(unavailable={C.REGULAR_BRI: 3})
    # Card 30 unshaded places Regulars from Unavailable
    card = {"id": 30}
    assert CARD_EFFECTS[30]["unshaded"]["places_british_from_unavailable"]
    assert bot._faction_event_conditions(st, card) is True

    st = _st(unavailable={})
    assert bot._faction_event_conditions(st, card) is False


def test_b2_bullet1_blockade_removal_needs_support_city():
    """§8.4 bullet 1 parenthetical: 'removing a Blockade from a Support
    City by reducing FNI' — needs an actual Blockade on a City at
    Support (card 64 lowers FNI; flags fixed Session 49)."""
    bot = BritishBot()
    card = {"id": 64}
    assert CARD_EFFECTS[64]["unshaded"]["removes_blockade"]

    # Opposition > Support, blockade on a Support city → play
    st = _st(spaces={"Boston": {}},
             support={"Boston": 1, "Virginia": -2, "Pennsylvania": -2},
             markers={C.BLOCKADE: {"pool": 0, "on_map": {"Boston"}}})
    st["spaces"].update({"Virginia": {}, "Pennsylvania": {}})
    assert bot._faction_event_conditions(st, card) is True

    # Same but no blockade anywhere (pre-ToA norm) → bullet 1 must not fire
    st = _st(spaces={"Boston": {}, "Virginia": {}, "Pennsylvania": {}},
             support={"Boston": 1, "Virginia": -2, "Pennsylvania": -2},
             markers={})
    assert bot._faction_event_conditions(st, card) is False

    # Blockade on a NON-Support city → still no
    st = _st(spaces={"Boston": {}, "Virginia": {}, "Pennsylvania": {}},
             support={"Boston": -1, "Virginia": -2, "Pennsylvania": -2},
             markers={C.BLOCKADE: {"pool": 0, "on_map": {"Boston"}}})
    assert bot._faction_event_conditions(st, card) is False


def test_card72_royalist_prefers_war_party_reserve():
    """§8.7 I2 note: place the Village in a space that already has War
    Parties if possible."""
    st = _st(
        spaces={
            "Northwest": {},
            "Southwest": {C.WARPARTY_U: 2},
        },
        available={C.VILLAGE: 2, C.WARPARTY_U: 5, C.TORY: 5,
                   C.REGULAR_BRI: 5},
        active=C.INDIANS,
    )
    early_war.evt_072_french_settlers(st, shaded=False)
    assert st["spaces"]["Southwest"].get(C.VILLAGE, 0) == 1
    assert st["spaces"]["Northwest"].get(C.VILLAGE, 0) == 0


def test_p2_fni_raise_clause_dynamic():
    """§8.5 bullet 1 "(including by increasing FNI)": card 34 shaded
    raises FNI — playable only when a Blockade could land on a Support
    City (post-ToA, ceiling headroom, unblockaded Support City)."""
    from lod_ai.bots.patriot import PatriotBot
    bot = PatriotBot()
    # Card 34 shaded raises FNI and does nothing else P2 cares about
    # (card 7 also adds +5 Patriot Resources, so bullet 4 would fire).
    card = {"id": 34}
    assert CARD_EFFECTS[34]["shaded"]["raises_fni"]

    def base(toa):
        return _st(
            spaces={"Boston": {}, "Virginia": {}},
            # Support (Boston 2x1) must exceed Opposition (none) for
            # P2 bullet 1 to be reachable at all.
            support={"Boston": 2, "Virginia": 0},
            markers={C.BLOCKADE: {"pool": 2, "on_map": set()}},
            toa_played=toa, fni_level=0,
        )

    st = base(True)
    assert bot._faction_event_conditions(st, card) is True
    st = base(False)                      # pre-ToA: FNI stuck at 0
    assert bot._faction_event_conditions(st, card) is False


def test_i2_fni_lower_clause_needs_blockaded_support_city():
    """§8.7 bullet 1 "(including by reducing FNI)": card 64 lowers FNI;
    Indians play it only with a Blockade sitting on a Support City."""
    from lod_ai.bots.indians import IndianBot
    bot = IndianBot()
    card = {"id": 64}

    st = _st(spaces={"Boston": {}, "Virginia": {}, "Pennsylvania": {}},
             support={"Boston": 1, "Virginia": -2, "Pennsylvania": -2},
             markers={C.BLOCKADE: {"pool": 0, "on_map": {"Boston"}}})
    assert bot._faction_event_conditions(st, card) is True

    st = _st(spaces={"Boston": {}, "Virginia": {}, "Pennsylvania": {}},
             support={"Boston": 1, "Virginia": -2, "Pennsylvania": -2},
             markers={})
    assert bot._faction_event_conditions(st, card) is False
