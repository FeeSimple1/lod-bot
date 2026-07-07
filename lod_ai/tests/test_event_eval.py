"""Tests for lod_ai.bots.event_eval — CARD_EFFECTS lookup table."""
import pytest

from lod_ai.bots.event_eval import CARD_EFFECTS
from lod_ai.rules_consts import WINTER_QUARTERS_CARDS, BRILLIANT_STROKE_CARDS


# All 96 non-WQ, non-BS card IDs
_ALL_CARD_IDS = set(range(1, 97))

# Sanity check: none of our 96 overlap with special cards
assert _ALL_CARD_IDS & WINTER_QUARTERS_CARDS == set()
assert _ALL_CARD_IDS & BRILLIANT_STROKE_CARDS == set()

# Expected fields in each side's dict
_EXPECTED_FIELDS = {
    "shifts_support_royalist",
    "shifts_support_rebel",
    "raises_fni",
    "places_british_pieces",
    "places_patriot_militia_u",
    "tories_in",  # S60: B2-3 fixed placement space(s), None = choose
    "regulars_in",  # S63: B2-3c fixed Regular placement space(s)
    "places_patriot_fort",
    "places_french_from_unavailable",
    "places_french_on_map",
    "places_village",
    "removes_patriot_fort",
    "removes_village",
    "adds_british_resources_3plus",
    "adds_patriot_resources_3plus",
    "adds_french_resources",
    "inflicts_british_casualties",
    "grants_free_gather",
    "is_effective",
    # B2 bullet flags (Session 6)
    "inflicts_rebel_casualties",
    "places_british_from_unavailable",
    "places_tories",
    "places_british_fort",
    "places_british_regulars",
    "removes_blockade",
}


def test_all_96_cards_present():
    """Every non-WQ non-BS card ID (1-96) has an entry in CARD_EFFECTS."""
    missing = _ALL_CARD_IDS - set(CARD_EFFECTS.keys())
    assert missing == set(), f"Missing card IDs in CARD_EFFECTS: {sorted(missing)}"


def test_no_extra_cards():
    """CARD_EFFECTS contains no WQ or BS card IDs."""
    extra_wq = set(CARD_EFFECTS.keys()) & WINTER_QUARTERS_CARDS
    extra_bs = set(CARD_EFFECTS.keys()) & BRILLIANT_STROKE_CARDS
    assert extra_wq == set(), f"WQ cards in CARD_EFFECTS: {extra_wq}"
    assert extra_bs == set(), f"BS cards in CARD_EFFECTS: {extra_bs}"


@pytest.mark.parametrize("card_id", sorted(_ALL_CARD_IDS))
def test_card_has_both_sides(card_id):
    """Each card entry has 'unshaded' and 'shaded' dicts."""
    entry = CARD_EFFECTS[card_id]
    assert "unshaded" in entry, f"Card {card_id} missing 'unshaded'"
    assert "shaded" in entry, f"Card {card_id} missing 'shaded'"


@pytest.mark.parametrize("card_id", sorted(_ALL_CARD_IDS))
def test_card_fields_complete(card_id):
    """Each side has exactly the expected set of boolean fields."""
    for side in ("unshaded", "shaded"):
        flags = CARD_EFFECTS[card_id][side]
        actual = set(flags.keys())
        missing = _EXPECTED_FIELDS - actual
        extra = actual - _EXPECTED_FIELDS
        assert missing == set(), (
            f"Card {card_id} {side} missing fields: {missing}"
        )
        assert extra == set(), (
            f"Card {card_id} {side} has extra fields: {extra}"
        )


@pytest.mark.parametrize("card_id", sorted(_ALL_CARD_IDS))
def test_card_values_are_booleans(card_id):
    """All field values are booleans."""
    for side in ("unshaded", "shaded"):
        flags = CARD_EFFECTS[card_id][side]
        for key, val in flags.items():
            if key in ("tories_in", "regulars_in"):
                # S60/S63: placement-target fields — None, a tuple of
                # space ids, or a "CITIES"/"COLONIES" sentinel.
                assert val is None or val in ("CITIES", "COLONIES") or (
                    isinstance(val, tuple)
                    and all(isinstance(x, str) for x in val)
                ), f"Card {card_id} {side}[{key}] = {val!r}"
                continue
            assert isinstance(val, bool), (
                f"Card {card_id} {side}[{key!r}] = {val!r} (not bool)"
            )


# Spot-check a few known cards for correct flag values

def test_card_2_unshaded_places_british_and_resources():
    """Card 2 unshaded places British pieces and adds 3+ British Resources."""
    u = CARD_EFFECTS[2]["unshaded"]
    assert u["places_british_pieces"] is True
    assert u["adds_british_resources_3plus"] is True


def test_card_2_shaded_shifts_rebel():
    """Card 2 shaded shifts toward Active Opposition."""
    s = CARD_EFFECTS[2]["shaded"]
    assert s["shifts_support_rebel"] is True


def test_card_75_unshaded_grants_free_gather():
    """Card 75 unshaded grants free Gather."""
    u = CARD_EFFECTS[75]["unshaded"]
    assert u["grants_free_gather"] is True


def test_card_18_shaded_is_none():
    """Card 18 shaded is (none) — all False."""
    s = CARD_EFFECTS[18]["shaded"]
    # placement-target fields default to None (not flags)
    assert all(v is False for k, v in s.items()
               if k not in ("tories_in", "regulars_in"))
    assert s["tories_in"] is None and s["regulars_in"] is None


def test_card_6_shaded_inflicts_british_casualties():
    """Card 6 shaded removes British pieces to Casualties."""
    s = CARD_EFFECTS[6]["shaded"]
    assert s["inflicts_british_casualties"] is True


def test_card_49_shaded_french_from_unavailable():
    """Card 49 shaded moves French Regs from Unavailable to Available."""
    s = CARD_EFFECTS[49]["shaded"]
    assert s["places_french_from_unavailable"] is True


def test_card_50_shaded_french_on_map():
    """Card 50 shaded places French Regs on map."""
    s = CARD_EFFECTS[50]["shaded"]
    assert s["places_french_on_map"] is True


# --- Session 6: spot-checks for new B2 bullet flags ---

# inflicts_rebel_casualties
def test_card_1_unshaded_inflicts_rebel_casualties():
    """Card 1 unshaded removes Continentals to Casualties."""
    u = CARD_EFFECTS[1]["unshaded"]
    assert u["inflicts_rebel_casualties"] is True


def test_card_9_unshaded_inflicts_rebel_casualties():
    """Card 9 unshaded grants British free Skirmish."""
    u = CARD_EFFECTS[9]["unshaded"]
    assert u["inflicts_rebel_casualties"] is True


def test_card_45_unshaded_no_rebel_casualties():
    """Card 45 unshaded only adds British Resources — no Rebel casualties."""
    u = CARD_EFFECTS[45]["unshaded"]
    assert u["inflicts_rebel_casualties"] is False


# places_british_from_unavailable
def test_card_30_unshaded_from_unavailable():
    """Card 30 unshaded places Regulars from Available or Unavailable."""
    u = CARD_EFFECTS[30]["unshaded"]
    assert u["places_british_from_unavailable"] is True


def test_card_46_unshaded_from_unavailable():
    """Card 46 unshaded places Tories from Unavailable or Available."""
    u = CARD_EFFECTS[46]["unshaded"]
    assert u["places_british_from_unavailable"] is True


def test_card_2_unshaded_not_from_unavailable():
    """Card 2 unshaded places British pieces but not from Unavailable."""
    u = CARD_EFFECTS[2]["unshaded"]
    assert u["places_british_from_unavailable"] is False


# places_tories
def test_card_15_unshaded_places_tories():
    """Card 15 unshaded places 2 Tories in Virginia."""
    u = CARD_EFFECTS[15]["unshaded"]
    assert u["places_tories"] is True


def test_card_7_unshaded_no_tories():
    """Card 7 unshaded places British Regulars, not Tories."""
    u = CARD_EFFECTS[7]["unshaded"]
    assert u["places_tories"] is False


# places_british_fort
def test_card_26_unshaded_places_fort():
    """Card 26 unshaded can place 1 British Fort in NC."""
    u = CARD_EFFECTS[26]["unshaded"]
    assert u["places_british_fort"] is True


def test_card_31_unshaded_places_fort():
    """Card 31 unshaded places 1 British Fort in SC or GA."""
    u = CARD_EFFECTS[31]["unshaded"]
    assert u["places_british_fort"] is True


def test_card_47_unshaded_no_fort():
    """Card 47 unshaded places Tories only, no Fort."""
    u = CARD_EFFECTS[47]["unshaded"]
    assert u["places_british_fort"] is False


# places_british_regulars
def test_card_32_unshaded_places_regulars():
    """Card 32 unshaded places Regulars and Tories in Colony."""
    u = CARD_EFFECTS[32]["unshaded"]
    assert u["places_british_regulars"] is True


def test_card_16_unshaded_no_regulars():
    """Card 16 unshaded places Tories only, no Regulars."""
    u = CARD_EFFECTS[16]["unshaded"]
    assert u["places_british_regulars"] is False


# removes_blockade
def test_card_54_unshaded_removes_blockade():
    """S65 REVERSED: card 54 unshaded moves a Squadron/Blockade from the
    WEST INDIES POOL to Unavailable — no City Blockade is removed and
    FNI does not drop, so the B2 bullet-1 clause ("removing a Blockade
    from a Support City by reducing FNI") does not apply."""
    u = CARD_EFFECTS[54]["unshaded"]
    assert u["removes_blockade"] is False


def test_card_34_unshaded_removes_blockade_via_fni():
    """§1.9: "For each level the FNI is lowered the British remove one
    Blockade to the West Indies" — card 34 unshaded lowers FNI, so it
    CAN remove a Blockade (B2 bullet-1 parenthetical; Session 49
    rewrote the old no-Blockade expectation)."""
    u = CARD_EFFECTS[34]["unshaded"]
    assert u["removes_blockade"] is True


def test_s63_target_aware_bullet3_examples():
    """S63 sweep (card-42 class): fixed-target cards must test THEIR
    spaces in B2 bullet 3, not the whole map."""
    from lod_ai.bots.british_bot import BritishBot
    import lod_ai.rules_consts as C
    from lod_ai.state.setup_state import build_state
    bot = BritishBot()
    state = build_state("1776", seed=1)
    # Card 85 places Regulars only in Southwest (a Reserve): bullet 3c
    # must NOT fire even though Cities exist on the map.
    eff = CARD_EFFECTS[85]["unshaded"]
    assert eff["regulars_in"] == ("Southwest",)
    # Card 66: both targets are Reserves.
    assert CARD_EFFECTS[66]["unshaded"]["regulars_in"] == ("Florida", "Southwest")
    # Card 2's Tories can only reach Cities; card 32's only Colonies.
    assert CARD_EFFECTS[2]["unshaded"]["tories_in"] == "CITIES"
    assert CARD_EFFECTS[32]["unshaded"]["tories_in"] == "COLONIES"
    # Behavioral check with card 85 (Southwest-only placements —
    # a Reserve, and Reserves are Always Neutral): with no Opposition
    # lead, no AO anywhere, and empty Unavailable, NO bullet may fire —
    # the old map-wide 3c scan returned True on any map with a City.
    for sid in state["spaces"]:
        state["support"][sid] = 0
    state["unavailable"] = {}
    card85 = {"id": 85, "dual": True}
    assert bot._faction_event_conditions(state, card85) is False, (
        "card 85 places only in the Southwest Reserve — bullet 3c must "
        "not fire off unrelated Cities, 3a has no reachable AO space"
    )
    # And card 2 (Regulars into any one City) legitimately fires 3c.
    card2 = {"id": 2, "dual": True}
    assert bot._faction_event_conditions(state, card2) is True


def test_s65_fni_flag_audit_examples():
    """S65 flag audit: card 40's absolute FNI settings and card 54's
    pool-move were mis-flagged."""
    # "FNI to 0" removes every City Blockade (§1.9)
    assert CARD_EFFECTS[40]["unshaded"]["removes_blockade"] is True
    # "FNI to 3" is a raise whenever FNI < 3 — flag set, the dynamic
    # Support-City check in the faction bullets governs
    assert CARD_EFFECTS[40]["shaded"]["raises_fni"] is True
    # Moving a Squadron/Blockade from the WEST INDIES POOL to Unavailable
    # removes no City Blockade and does not reduce FNI
    assert CARD_EFFECTS[54]["unshaded"]["removes_blockade"] is False
    # Sanity: the Lower-FNI family keeps the flag (§1.9 marker return)
    for cid in (7, 34, 53, 60, 64, 69):
        assert CARD_EFFECTS[cid]["unshaded"]["removes_blockade"] is True, cid
