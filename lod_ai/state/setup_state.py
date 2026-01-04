from __future__ import annotations
"""lod_ai.state.setup_state
================================================
Builds the initial *state* dictionary for the Liberty‑or‑Death helper.
This is a clean rewrite that folds in Propaganda marker support and
removes the erroneous top‑level `state[...]` manipulation from the
previous draft.  It mirrors the original structure but now places all
marker pools inside the `state` literal returned by `build_state()`.
"""

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple
from lod_ai.util.normalize_state import normalize_state

# ── constants from rules_consts ──────────────────────────────────────────
from lod_ai.rules_consts import (
    # pool caps
    MAX_REGULAR_BRI, MAX_TORY, MAX_REGULAR_FRE,
    MAX_REGULAR_PAT, MAX_MILITIA, MAX_WAR_PARTY,
    MAX_FORT_BRI, MAX_FORT_PAT, MAX_VILLAGE,
    MAX_PROPAGANDA, MAX_RAID,

    # piece tags
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY, MILITIA_A, MILITIA_U, WARPARTY_A, WARPARTY_U,
    FORT_BRI, FORT_PAT, VILLAGE,

    # marker tags
    PROPAGANDA, RAID, BLOCKADE,

    # factions
    BRITISH, PATRIOTS, FRENCH, INDIANS, SQUADRON,
)

# deck helpers
try:
    from lod_ai.cards import CARD_REGISTRY as _CARD_REGISTRY  # preferred
except Exception:
    import importlib.resources as _ires  # Python 3.9+
    _CARD_REGISTRY = {}
    try:
        _data = (_ires.files("lod_ai.cards") / "data.json").read_text(encoding="utf-8")
        _CARD_REGISTRY = {int(c["id"]): c for c in json.loads(_data)}
    except Exception:
        _CARD_REGISTRY = {}

# ----------------------------------------------------------------------- #
# 1️⃣  POOLS                                                               #
# ----------------------------------------------------------------------- #

def init_available() -> Dict[str, int]:
    """Return full counts for every piece family in the Available box at game start."""
    return {
        # British
        REGULAR_BRI: MAX_REGULAR_BRI,
        TORY:        MAX_TORY,
        FORT_BRI:    MAX_FORT_BRI,

        # French
        REGULAR_FRE: MAX_REGULAR_FRE,

        # Patriots
        REGULAR_PAT: MAX_REGULAR_PAT,
        MILITIA_U:   MAX_MILITIA,
        MILITIA_A:   0,

        # Indians
        WARPARTY_U:  MAX_WAR_PARTY,
        WARPARTY_A:  0,
        VILLAGE:     MAX_VILLAGE,

        # forts
        FORT_PAT:    MAX_FORT_PAT,
    }

# Backwards compatibility for any older callers
init_pools = init_available

# ----------------------------------------------------------------------- #
# 2️⃣  SCENARIO FILES & ALIASES                                            #
# ----------------------------------------------------------------------- #

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_ALIAS = {
    # numeric aliases – let callers use “1775”, “1776”, “1778”
    "1775":  "1775_long.json",
    "1776":  "1776_medium.json",
    "1778":  "1778_short.json",

    # descriptive aliases – unchanged
    "long":   "1775_long.json",
    "medium": "1776_medium.json",
    "short":  "1778_short.json",
}


def load_scenario(name: str) -> Dict[str, Any]:
    """Load and parse a scenario JSON file by alias or filename."""
    filename = _ALIAS.get(name.lower(), name)
    path = _DATA_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Scenario file not found: {filename}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    data["file_name"] = filename
    return data

# ----------------------------------------------------------------------- #
# 3️⃣  MAP‑TAG → POOL‑TAG & RECONCILE                                      #
# ----------------------------------------------------------------------- #

def _reconcile_on_map(state: Dict[str, Any]) -> None:
    """Subtract pieces already seated on the map from Available counts.

    Note: Active/Underground variants draw from the same physical pool,
    so MILITIA_A consumes MILITIA_U capacity and WARPARTY_A consumes WARPARTY_U.
    """
    available, spaces = state["available"], state["spaces"]
    used: Counter[str] = Counter()

    pool_family = {
        MILITIA_A: MILITIA_U,
        MILITIA_U: MILITIA_U,
        WARPARTY_A: WARPARTY_U,
        WARPARTY_U: WARPARTY_U,
    }

    for sp in spaces.values():
        for tag, n in sp.items():
            if not isinstance(n, int) or n <= 0:
                continue
            pool_tag = pool_family.get(tag, tag)
            if pool_tag in available:
                used[pool_tag] += n

    for tag, n_used in used.items():
        available[tag] -= n_used
        if available[tag] < 0:
            raise ValueError(
                f"Scenario overdraw: {-available[tag]} extra {tag} pieces on map"
            )
        if available[tag] == 0:
            del available[tag]


def _apply_unavailable_block(state: Dict[str, Any], scenario: Dict[str, Any]) -> None:
    """Move counts from scenario['unavailable'] into state['unavailable'].""" 
    unavail = scenario.get("unavailable", {})
    available = state["available"]
    unavailable = state["unavailable"]

    key_map = {
        "French_Regular_Unavailable": REGULAR_FRE,
        "British_Regular_Unavailable": REGULAR_BRI,
        "British_Tory_Unavailable": TORY,
        "FRENCH_REGULARS": REGULAR_FRE,
        "BRITISH_REGULARS": REGULAR_BRI,
        "BRITISH_TORIES": TORY,
        "Squadron": SQUADRON,
        "FRENCH_SQUADRONS": SQUADRON,
    }

    for json_key, qty in unavail.items():
        if not qty:
            continue

        if json_key in available:
            tag = json_key
        else:
            tag = key_map.get(json_key)

        if not tag:
            state.setdefault("log", []).append(f"(setup) Unrecognised unavailable pool: {json_key}")
            continue

        if tag not in available:
            state.setdefault("log", []).append(f"(setup) Unavailable pool not modelled: {json_key} ({qty})")
            continue

        if available.get(tag, 0) < qty:
            raise ValueError(f"Scenario unavailable overdraw: {qty} {tag} requested")

        available[tag] -= qty
        if available[tag] == 0:
            available.pop(tag, None)
        unavailable[tag] = unavailable.get(tag, 0) + qty

    # French unavailable Squadrons/Blockades (logged only for now)
    if sq := unavail.get("FRENCH_SQUADRONS"):
        state.setdefault("log", []).append(
            f"(setup) {sq} French Squadrons/Blockades unavailable in port"
        )


def _default_to_underground(spaces: Dict[str, Dict[str, int]]) -> None:
    """Convert any generic Militia/WP tags in *spaces* to their Underground state."""
    for sp in spaces.values():
        for src, dst in (("Patriot_Militia", MILITIA_U), ("Indian_War_Party", WARPARTY_U)):
            if src in sp:
                sp[dst] = sp.get(dst, 0) + int(sp.pop(src) or 0)


def _force_start_underground(spaces: Dict[str, Dict[str, int]]) -> None:
    """
    Ensure all Militia and War Parties begin Underground during scenario setup.
    Any Active counts are shifted into their Underground variants.
    """
    for sp in spaces.values():
        if sp.get(MILITIA_A, 0):
            sp[MILITIA_U] = sp.get(MILITIA_U, 0) + sp.pop(MILITIA_A, 0)
        if sp.get(WARPARTY_A, 0):
            sp[WARPARTY_U] = sp.get(WARPARTY_U, 0) + sp.pop(WARPARTY_A, 0)


# ----------------------------------------------------------------------- #
# Support normalisation (derive state['support'] from per‑space fields)    #
# ----------------------------------------------------------------------- #
def _normalize_support(state: Dict[str, Any]) -> None:
    """
    Populate state['support'] as {space_id: -2..+2} by reading each space's
    'Support' or 'Opposition' fields from state['spaces']. If neither is
    present, default to 0 (Neutral).
    """
    sup: Dict[str, int] = {}
    for sid, sp in state.get("spaces", {}).items():
        if "Support" in sp:
            sup[sid] = int(sp.pop("Support", 0))
        elif "Opposition" in sp:
            sup[sid] = -int(sp.pop("Opposition", 0))
        elif "support" in sp:
            sup[sid] = int(sp.pop("support", 0))
        else:
            sup[sid] = 0
    state["support"] = sup


# ----------------------------------------------------------------------- #
# 4️⃣  DECK INITIALISATION                                                 #
# ----------------------------------------------------------------------- #

_CARD_RX = re.compile(r"(?:Card_)?(\d{1,3})$")


def _card_from_id(value: int | str) -> dict:
    """Return card metadata for integer or 'Card_###' id."""
    m = _CARD_RX.match(str(value).strip())
    if not m:
        raise ValueError(f"Unrecognised card id: {value}")
    cid = int(m.group(1))
    try:
        return _CARD_REGISTRY[cid]
    except KeyError:
        raise KeyError(f"Card id {cid} not found in registry")


def _campaign_count(scenario_name: str) -> int:
    scen = scenario_name.lower()
    if "1775" in scen or "long" in scen:
        return 6
    if "1776" in scen or "medium" in scen:
        return 4
    if "1778" in scen or "short" in scen:
        return 3
    return 6


def _period_piles(duration: int) -> List[Tuple[str, int]]:
    """Return ordered (bucket, count) tuples for Period Events."""
    if duration == 6:
        return [("1775-1776", 2), ("1777-1778", 2), ("1779-1780", 2)]
    if duration == 4:
        return [("1775-1776", 1), ("1777-1778", 2), ("1779-1780", 1)]
    return [("1777-1778", 1), ("1779-1780", 2)]


def _bucket_for_card(card: dict) -> str:
    years = card.get("years") or []
    min_year = min(years) if years else 1775
    if min_year <= 1776:
        return "1775-1776"
    if min_year <= 1778:
        return "1777-1778"
    return "1779-1780"


def _insert_wq(pile: list[dict], wq_card: dict, rng: random.Random) -> list[dict]:
    """Insert *wq_card* into the bottom 5 cards of *pile*."""
    if not pile:
        return [wq_card]
    bottom = min(4, len(pile))
    top_cards = pile[:-bottom]
    bottom_cards = pile[-bottom:]
    bottom_cards.append(wq_card)
    rng.shuffle(bottom_cards)
    return top_cards + bottom_cards


def _build_standard_deck(rng: random.Random, duration: int) -> list[dict]:
    """Construct the Standard deck per rules."""
    cards = [c for c in _CARD_REGISTRY.values() if not c.get("winter_quarters") and c.get("type") != "BRILLIANT_STROKE"]
    rng.shuffle(cards)
    wq = [c for c in _CARD_REGISTRY.values() if c.get("winter_quarters")]
    rng.shuffle(wq)

    piles: list[list[dict]] = []
    for _ in range(duration):
        pile = cards[:10]
        cards = cards[10:]
        if not pile:
            raise ValueError("Not enough Event cards to build the requested deck.")
        wq_card = wq.pop(0) if wq else None
        if wq_card:
            pile = _insert_wq(pile, wq_card, rng)
        piles.append(pile)

    deck: list[dict] = []
    for pile in piles:
        deck.extend(pile)
    return deck


def _build_period_deck(rng: random.Random, duration: int) -> list[dict]:
    """Construct the Period Events deck per rules."""
    events = [c for c in _CARD_REGISTRY.values() if not c.get("winter_quarters") and c.get("type") != "BRILLIANT_STROKE"]
    buckets: Dict[str, List[dict]] = {"1775-1776": [], "1777-1778": [], "1779-1780": []}
    for card in events:
        buckets[_bucket_for_card(card)].append(card)
    for cards in buckets.values():
        rng.shuffle(cards)

    wq = [c for c in _CARD_REGISTRY.values() if c.get("winter_quarters")]
    rng.shuffle(wq)
    piles: list[list[dict]] = []
    for bucket_name, count in _period_piles(duration):
        for _ in range(count):
            bucket_cards = buckets[bucket_name]
            pile = bucket_cards[:10]
            buckets[bucket_name] = bucket_cards[10:]
            if not pile:
                raise ValueError(f"Not enough cards to build Period pile for {bucket_name}")
            wq_card = wq.pop(0) if wq else None
            if wq_card:
                pile = _insert_wq(pile, wq_card, rng)
            piles.append(pile)

    deck: list[dict] = []
    for pile in piles:
        deck.extend(pile)
    return deck


def _init_deck(
    state: Dict[str, Any], scenario: Dict[str, Any], *, setup_method: str
) -> None:
    """Populate state['deck'] and state['upcoming_card'] from scenario data."""
    scenario_name = scenario.get("file_name", scenario.get("scenario", "long")).lower()
    duration = _campaign_count(scenario_name)

    upcoming = scenario.get("upcoming_event")
    current = scenario.get("current_event")
    if current is not None:
        state["current_card"] = _card_from_id(current)

    method = setup_method.lower()
    if method in {"period", "period_events", "historical"}:
        deck_cards = _build_period_deck(state["rng"], duration)
    else:
        deck_cards = _build_standard_deck(state["rng"], duration)

    upcoming_card = _card_from_id(upcoming) if upcoming is not None else None
    if upcoming_card:
        deck_cards = [c for c in deck_cards if c["id"] != upcoming_card["id"]]
        state["upcoming_card"] = upcoming_card

    state["deck"] = deck_cards

# ----------------------------------------------------------------------- #
# 5️⃣  TOP‑LEVEL BUILDER                                                   #
# ----------------------------------------------------------------------- #

def build_state(
    scenario: str = "long", *, seed: int = 1, setup_method: str = "standard"
) -> Dict[str, Any]:
    """Return a fully‑initialised *state* for the given scenario alias."""
    scen = load_scenario(scenario)
    method = setup_method.lower()
    _default_to_underground(scen.get("spaces", {}))
    _force_start_underground(scen.get("spaces", {}))

    state: Dict[str, Any] = {
        "scenario":  scen["scenario"],
        "spaces":    scen["spaces"],
        "resources": scen["resources"],
        "treaty":    scen.get("treaty", 3),   # Treaty of Alliance step marker
        "campaign_year": scen.get("campaign_year", 1775),
        "fni_level": scen.get("fni_level", 0),
        "toa_played": bool(scen.get("toa_played", False)),
        "treaty_of_alliance": bool(scen.get("toa_played", False)),
        "bs_played": scen.get("bs_played", {}),
        "leaders":   scen.get("leaders", {}),
        "available":    init_available(),
        "unavailable":  {},
        "casualties":   scen.get("casualties", {}),
        # 🔹 Marker pools -------------------------------------------------
        "markers":   {
            PROPAGANDA: {"pool": MAX_PROPAGANDA, "on_map": set()},
            RAID:       {"pool": MAX_RAID, "on_map": set()},
            BLOCKADE:   {"pool": 0, "on_map": set()},
            # add further marker families here
        },
        # ---------------------------------------------------------------
        "rng":       random.Random(seed),
        "rng_log":   [],
        "history":   [],
        "log":       [],
        "setup_method": method,
        "seed": seed,
        "eligible": {
            BRITISH: True,
            PATRIOTS: True,
            FRENCH: True,
            INDIANS: True,
        },
    }

    _normalize_support(state)
    _apply_unavailable_block(state, scen)
    _reconcile_on_map(state)
    _init_deck(state, scen, setup_method=method)
    normalize_state(state)
    return state
