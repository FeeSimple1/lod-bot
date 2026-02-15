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
    "places_british_pieces",
    "places_patriot_militia_u",
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
    assert all(v is False for v in s.values())


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
