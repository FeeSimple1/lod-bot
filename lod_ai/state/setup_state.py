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
from typing import Dict, Any

# ── constants from rules_consts ──────────────────────────────────────────
from lod_ai.rules_consts import (
    # pool caps
    MAX_REGULAR_BRI, MAX_TORY, MAX_REGULAR_FRE,
    MAX_REGULAR_PAT, MAX_MILITIA, MAX_WAR_PARTY,
    # piece tags
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT,
    TORY, MILITIA_A, MILITIA_U, WARPARTY_A, WARPARTY_U,
    # unavailable tags
    BRIT_UNAVAIL, FRENCH_UNAVAIL, TORY_UNAVAIL,
    # new marker support
    PROPAGANDA,
    RAID,
    BRITISH,
    PATRIOTS,
    FRENCH,
    INDIANS,
)

# deck helpers
from lod_ai.cards import CARD_REGISTRY

# ----------------------------------------------------------------------- #
# 1️⃣  POOLS                                                               #
# ----------------------------------------------------------------------- #

def init_pools() -> Dict[str, int]:
    """Return full counts for every piece family at game start."""
    return {
        # British
        REGULAR_BRI:  MAX_REGULAR_BRI,
        BRIT_UNAVAIL: 0,
        TORY:         MAX_TORY,
        TORY_UNAVAIL: 0,
        # French
        REGULAR_FRE:  MAX_REGULAR_FRE,
        FRENCH_UNAVAIL: 0,
        # Patriots
        REGULAR_PAT:  MAX_REGULAR_PAT,
        MILITIA_A:    MAX_MILITIA,  # *available* militia start Active
        MILITIA_U:    0,                # underground militia are created later
        # Indians
        WARPARTY_A:   MAX_WAR_PARTY,
        WARPARTY_U:   0,
    }

# ----------------------------------------------------------------------- #
# 2️⃣  SCENARIO FILES & ALIASES                                            #
# ----------------------------------------------------------------------- #

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_ALIAS = {
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
        return json.load(fh)

# ----------------------------------------------------------------------- #
# 3️⃣  MAP‑TAG → POOL‑TAG & RECONCILE                                      #
# ----------------------------------------------------------------------- #

def _reconcile_on_map(state: Dict[str, Any]) -> None:
    """Subtract pieces already seated on the map from each pool."""
    pool, spaces = state["pool"], state["spaces"]
    used: Counter[str] = Counter()

    for sp in spaces.values():
        for tag, n in sp.items():
            if n and tag in pool:
                used[tag] += n

    for pool_tag, n_used in used.items():
        pool[pool_tag] -= n_used
        if pool[pool_tag] < 0:
            raise ValueError(
                f"Scenario overdraw: {-pool[pool_tag]} extra {pool_tag} pieces on map"
            )


def _apply_unavailable_block(state: Dict[str, Any], scenario: Dict[str, Any]) -> None:
    """Move counts from scenario['unavailable'] into the dedicated *unavailable* pools."""
    unavail = scenario.get("unavailable", {})
    pool = state["pool"]

    # French unavailable Regulars/Squadrons
    if fr := unavail.get("FRENCH_REGULARS"):
        pool[REGULAR_FRE]    -= fr
        pool[FRENCH_UNAVAIL] += fr
    if sq := unavail.get("FRENCH_SQUADRONS"):
        state.setdefault("log", []).append(
            f"(setup) {sq} French Squadrons unavailable in port"
        )

    # British unavailable blocks
    if br := unavail.get("BRITISH_REGULARS"):
        pool[REGULAR_BRI]   -= br
        pool[BRIT_UNAVAIL]  += br
    if bt := unavail.get("BRITISH_TORIES"):
        pool[TORY]          -= bt
        pool[TORY_UNAVAIL]  += bt


# ----------------------------------------------------------------------- #
# 4️⃣  DECK INITIALISATION                                                 #
# ----------------------------------------------------------------------- #

_CARD_RX = re.compile(r"(?:Card_)?(\d{1,3})$")


def _card_from_id(value: int | str) -> dict:
    """Return CARD_REGISTRY entry for integer or 'Card_###' id."""
    m = _CARD_RX.match(str(value).strip())
    if not m:
        raise ValueError(f"Unrecognised card id: {value}")
    return CARD_REGISTRY[int(m.group(1))]


def _build_deck_standard(cards: list[dict], rng: random.Random) -> list[dict]:
    """Return *cards* shuffled for the Standard setup."""
    rng.shuffle(cards)
    return cards


def _build_deck_historical(
    cards: list[dict], start_year: int, rng: random.Random
) -> list[dict]:
    """Return cards ordered by earliest year with Winter Quarters inserted."""
    wq_cards = [c for c in cards if c.get("winter_quarters")]
    event_cards = [c for c in cards if not c.get("winter_quarters")]

    groups: dict[int, list[dict]] = {}
    for c in event_cards:
        year = min(c.get("years") or [start_year])
        groups.setdefault(year, []).append(c)

    deck: list[dict] = []
    wq_idx = 0
    for year in sorted(groups):
        group = sorted(groups[year], key=lambda d: d["id"])
        deck.extend(group)
        if wq_idx < len(wq_cards):
            deck.append(wq_cards[wq_idx])
            wq_idx += 1

    deck.extend(wq_cards[wq_idx:])
    return deck


def _init_deck(
    state: Dict[str, Any], scenario: Dict[str, Any], *, setup_method: str
) -> None:
    """Populate state['deck'] and state['upcoming_card'] from *scenario*."""
    deck_ids = list(scenario.get("deck", []))
    upcoming = scenario.get("upcoming_event")
    current = scenario.get("current_event")

    if current is not None:
        state["current_card"] = _card_from_id(current)

    upcoming_card = _card_from_id(upcoming) if upcoming is not None else None
    if upcoming_card:
        state["upcoming_card"] = upcoming_card

    deck_cards = [_card_from_id(cid) for cid in deck_ids]
    if upcoming_card:
        deck_cards = [c for c in deck_cards if c["id"] != upcoming_card["id"]]

    if setup_method == "historical":
        deck_cards = _build_deck_historical(
            deck_cards, scenario.get("campaign_year", 1775), state["rng"]
        )
    else:
        deck_cards = _build_deck_standard(deck_cards, state["rng"])

    state["deck"] = deck_cards

# ----------------------------------------------------------------------- #
# 5️⃣  TOP‑LEVEL BUILDER                                                   #
# ----------------------------------------------------------------------- #

def build_state(
    scenario: str = "long", *, seed: int = 1, setup_method: str = "standard"
) -> Dict[str, Any]:
    """Return a fully‑initialised *state* for the given scenario alias."""
    scen = load_scenario(scenario)

    state: Dict[str, Any] = {
        "scenario":  scen["scenario"],
        "spaces":    scen["spaces"],
        "resources": scen["resources"],
        "treaty":    scen.get("treaty", 3),   # Treaty of Alliance step marker
        "leaders":   scen.get("leaders", {}),
        "pool":      init_pools(),
        # 🔹 Marker pools -------------------------------------------------
        "markers":   {
            PROPAGANDA: set(),   # Rabble‑Rousing populates these
            RAID: set()
            # add further marker families (Raid, Fort‑destroyed, etc.) here
        },
        # ---------------------------------------------------------------
        "rng":       random.Random(seed),
        "rng_log":   [],
        "history":   [],
        "log":       [],
        "setup_method": setup_method,
        "eligible": {
            BRITISH: True,
            PATRIOTS: True,
            FRENCH: True,
            INDIANS: True,
        },
    }

    _apply_unavailable_block(state, scen)
    _reconcile_on_map(state)
    _init_deck(state, scen, setup_method=setup_method)
    return state
