"""P2 bullet-2 target-awareness (S75 — the S63 "card-42 class" fix
applied to the Patriot Event-or-Command list).

Manual §8.5: "The Event places Underground Militia in at least one
Active Support or Village space that has none already."  The bullet
must test the spaces where THIS card's Militia can actually land
(event_eval `militia_in` / `militia_via_tory`), and "none" scopes to
Underground Militia (a space holding only Active Militia qualifies).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.rules_consts as C
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.event_eval import CARD_EFFECTS


def _card(cid):
    return {"id": cid, "dual": True, "title": f"c{cid}"}


def _state(spaces, support=None):
    return {
        "spaces": spaces,
        "support": support or {},
        "available": {C.MILITIA_U: 5},
        "unavailable": {}, "resources": {C.PATRIOTS: 5},
        "control": {}, "markers": {}, "played_cards": [],
    }


def test_card62_fires_only_where_its_militia_can_land():
    """Card 62's Militia can ONLY go to Northwest — an Active Support
    space elsewhere must not fire the bullet (pre-S75 it did)."""
    bot = PatriotBot()
    st = _state({"Boston": {}, "Northwest": {}},
                support={"Boston": C.ACTIVE_SUPPORT})
    assert not bot._faction_event_conditions(st, _card(62)), (
        "Boston qualifies generically but card 62 cannot place there")
    # A Village in Northwest (no Underground Militia) DOES qualify.
    st["spaces"]["Northwest"][C.VILLAGE] = 1
    assert bot._faction_event_conditions(st, _card(62))
    assert st.get("_event_q_spaces") == {"Northwest"}


def test_replacement_cards_need_a_tory():
    """Card 89 places Militia only by replacing Tories."""
    bot = PatriotBot()
    st = _state({"Boston": {}}, support={"Boston": C.ACTIVE_SUPPORT})
    assert not bot._faction_event_conditions(st, _card(89)), (
        "no Tory to replace -> the card cannot place Militia there")
    st["spaces"]["Boston"][C.TORY] = 1
    assert bot._faction_event_conditions(st, _card(89))


def test_active_militia_does_not_block_the_bullet():
    """'has none already' scopes to Underground Militia (§8.5).
    Card 24 places Militia anywhere and, with the Fort pool empty and
    <25 pieces, fires ONLY via bullet 2 — unlike card 19, whose +3
    Resources trip bullet 4 regardless."""
    bot = PatriotBot()
    st = _state({"Boston": {C.MILITIA_A: 2}},
                support={"Boston": C.ACTIVE_SUPPORT})
    assert bot._faction_event_conditions(st, _card(24)), (
        "Active Militia present but no Underground -> still qualifies")
    st["spaces"]["Boston"][C.MILITIA_U] = 1
    st.pop("_event_q_spaces", None)
    assert not bot._faction_event_conditions(st, _card(24))


def test_card13_no_longer_carries_the_underground_flag():
    """Card 13 shaded adds ACTIVE Militia — it must not fire P2-2."""
    assert not CARD_EFFECTS[13]["shaded"]["places_patriot_militia_u"]


def test_free_french_battle_cards_fire_f4():
    """Manual §8.6 bullet 4: 'inflicts British Casualties (including a
    free French Battle...)' — cards 52 and 66-shaded must carry it."""
    assert CARD_EFFECTS[52]["unshaded"]["inflicts_british_casualties"]
    assert CARD_EFFECTS[66]["shaded"]["inflicts_british_casualties"]
