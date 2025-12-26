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
    BRITISH, PATRIOTS, FRENCH, INDIANS,
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
        return json.load(fh)

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

    # French unavailable Regulars
    if fr := unavail.get("FRENCH_REGULARS"):
        if available.get(REGULAR_FRE, 0) < fr:
            raise ValueError(f"Scenario unavailable overdraw: {fr} {REGULAR_FRE} requested")
        available[REGULAR_FRE] -= fr
        if available[REGULAR_FRE] == 0:
            del available[REGULAR_FRE]
        unavailable[REGULAR_FRE] = unavailable.get(REGULAR_FRE, 0) + fr

    # French unavailable Squadrons/Blockades (logged only for now)
    if sq := unavail.get("FRENCH_SQUADRONS"):
        state.setdefault("log", []).append(
            f"(setup) {sq} French Squadrons/Blockades unavailable in port"
        )

    # British unavailable Regulars
    if br := unavail.get("BRITISH_REGULARS"):
        if available.get(REGULAR_BRI, 0) < br:
            raise ValueError(f"Scenario unavailable overdraw: {br} {REGULAR_BRI} requested")
        available[REGULAR_BRI] -= br
        if available[REGULAR_BRI] == 0:
            del available[REGULAR_BRI]
        unavailable[REGULAR_BRI] = unavailable.get(REGULAR_BRI, 0) + br

    # British unavailable Tories
    if bt := unavail.get("BRITISH_TORIES"):
        if available.get(TORY, 0) < bt:
            raise ValueError(f"Scenario unavailable overdraw: {bt} {TORY} requested")
        available[TORY] -= bt
        if available[TORY] == 0:
            del available[TORY]
        unavailable[TORY] = unavailable.get(TORY, 0) + bt


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
    _default_to_underground(scen.get("spaces", {}))
    _force_start_underground(scen.get("spaces", {}))

    state: Dict[str, Any] = {
        "scenario":  scen["scenario"],
        "spaces":    scen["spaces"],
        "resources": scen["resources"],
        "treaty":    scen.get("treaty", 3),   # Treaty of Alliance step marker
        "leaders":   scen.get("leaders", {}),
        "available":    init_available(),
        "unavailable":  {},
        "casualties":   {},
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
        "setup_method": setup_method,
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
    _init_deck(state, scen, setup_method=setup_method)
    normalize_state(state)
    return state
