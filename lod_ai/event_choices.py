"""ROADMAP Piece 7 — CLI event-choice collection layer.

The interactive CLI historically executed Events without collecting any
card-specific choices, so a human seat fell through to the non-player
handler default for every choice-bearing card (docs/human_mode_audit.md,
Session 72).  This module is the missing *collection* layer: it maps each
card to the prompts a human answers BEFORE the handler runs, and writes
the answers to the ``state["card<N>_<key>"]`` overrides the handlers
already honor.

Design rules:

* Handlers stay the single source of truth for execution.  Every value
  collected here is re-validated by the handler; a stale or illegal pick
  degrades to the handler's rules-faithful default, never a crash.
* Each prompt's candidate list mirrors the handler's own legality filter
  (same predicates, same exclusions), so a human is only offered picks
  the handler will actually honor.
* A step may belong to one card side only (``side=True`` shaded /
  ``False`` unshaded / ``None`` both).
* A step may belong to a specific *deciding* faction where the card text
  names one (e.g. card 5 shaded "Patriots free March + Battle": the
  Patriot player decides).  If the decider is a non-executing BOT the
  step is skipped — the handler default (§8.3.x-faithful since T7/Q22)
  decides, exactly as when a bot executes the event.  If the decider is
  a human seat (hot-seat play), the prompt is labelled with that faction.
* Empty candidate lists skip the prompt (handler default applies), so
  "implement what you can" (§5.1.3) is preserved.

Wired so far (Piece 7 batch 1): the 26 space-selection cards
5, 7, 9, 11, 15, 16, 17, 19, 21, 23, 25, 27, 29, 31, 35, 47, 50, 59,
73, 76, 77, 79, 81, 83, 84, 93.
(Audit-table correction, noted in docs/human_mode_audit.md: card 29's
value is a FACTION name — PATRIOTS or INDIANS — not a space id; it is
collected here as a two-option pick.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from lod_ai.cli_utils import choose_multiple, choose_one_or_back
from lod_ai.map import adjacency as map_adj
from lod_ai.board import control
from lod_ai.rules_consts import (
    BRITISH, PATRIOTS, FRENCH, INDIANS,
    REGULAR_BRI, REGULAR_FRE, REGULAR_PAT, TORY,
    MILITIA_A, MILITIA_U, WARPARTY_A, WARPARTY_U,
    FORT_BRI, FORT_PAT, VILLAGE,
    WEST_INDIES_ID,
)

# ---------------------------------------------------------------------------
# Shared predicates (mirror the handlers' own filters)
# ---------------------------------------------------------------------------

_PATRIOT_UNITS = (REGULAR_PAT, MILITIA_U, MILITIA_A)


def _spaces(state: dict) -> dict:
    return state.get("spaces", {})


def _sp(state: dict, sid: str) -> dict:
    return state.get("spaces", {}).get(sid, {})


def _has_any(state: dict, sid: str, tags) -> bool:
    sp = _sp(state, sid)
    return any(sp.get(t, 0) for t in tags)


def _is_city(sid: str) -> bool:
    return map_adj.space_type(sid) == "City"


def _is_colony(sid: str) -> bool:
    return map_adj.space_type(sid) == "Colony"


def _is_reserve(sid: str) -> bool:
    return map_adj.space_type(sid) == "Reserve"


def _adj_in_play(state: dict, sid: str) -> List[str]:
    return [s for s in map_adj.adjacent_spaces(sid) if s in _spaces(state)]


def _control_map(state: dict) -> dict:
    control.refresh_control(state)
    return state.get("control", {})


def _ids(sids) -> List[Tuple[str, str]]:
    """Space-id options in the (label, value) shape the pickers expect."""
    return [(s, s) for s in sorted(sids)]


# ---------------------------------------------------------------------------
# Step / registry machinery
# ---------------------------------------------------------------------------

# options callable: (state, executor, picks) -> [(label, value), ...]
OptionsFn = Callable[[dict, str, Dict[str, Any]], List[Tuple[str, Any]]]


@dataclass(frozen=True)
class Step:
    key: str                       # override suffix: card<N>_<key>
    prompt: str
    options: OptionsFn
    side: Optional[bool] = None    # None = both sides; True shaded; False unshaded
    kind: str = "one"              # "one" | "multi" | "repeat"
    decider: Optional[str] = None  # None = the executing faction decides
    min_sel: int = 1               # "multi" only
    max_sel: Optional[int] = None  # "multi" only; None = no cap
    exact: bool = False            # "multi": pick exactly min(max_sel, len(opts))
    count: int = 1                 # "repeat": number of picks (repetition OK)
    min_options: int = 1           # skip the step below this many candidates


def _pick_repeat(prompt: str, options: List[Tuple[str, Any]], count: int) -> List[Any]:
    """*count* picks from *options*, repetition allowed (e.g. stack 3 Militia)."""
    picks: List[Any] = []
    for i in range(count):
        picks.append(choose_one_or_back(f"{prompt} (pick {i + 1}/{count}):", options))
    return picks


def collect_event_choices(engine, executor: str, card: dict, shaded: bool) -> Dict[str, Any]:
    """Prompt the human for every choice this card side presents.

    Returns the ``{"card<N>_<key>": value}`` override dict to apply to the
    event-execution state.  Raises BackException if the player backs out.
    """
    card_id = card.get("id")
    steps = EVENT_CHOICES.get(card_id, ())
    if not steps:
        return {}

    state = engine.state
    humans = getattr(engine, "human_factions", set()) or set()
    overrides: Dict[str, Any] = {}
    picks: Dict[str, Any] = {}
    header_shown = False

    for step in steps:
        if step.side is not None and step.side != shaded:
            continue
        decider = step.decider or executor
        if decider != executor and decider not in humans:
            # The choice belongs to a bot faction -> its rules-faithful
            # handler default decides, same as on a bot-executed event.
            continue
        opts = step.options(state, executor, picks)
        if len(opts) < max(1, step.min_options):
            continue
        if not header_shown:
            print(f"\n  Event choices — [{card_id}] {card.get('title', '')}"
                  f" ({'shaded' if shaded else 'unshaded'})")
            header_shown = True
        label = f"[{decider}] {step.prompt}"
        if step.kind == "multi":
            # Cap the pick count at the number of candidates so the menu
            # can never run empty before the cap is reached.
            cap = min(step.max_sel, len(opts)) if step.max_sel else len(opts)
            if step.exact:
                value = choose_multiple(label, opts, min_sel=cap, max_sel=cap)
            else:
                value = choose_multiple(label, opts,
                                        min_sel=min(step.min_sel, cap),
                                        max_sel=cap)
        elif step.kind == "repeat":
            value = _pick_repeat(label, opts, step.count)
        else:
            value = choose_one_or_back(f"{label}:", opts)
        overrides[f"card{card_id}_{step.key}"] = value
        picks[step.key] = value

    return overrides


# ---------------------------------------------------------------------------
# Candidate builders (one per card where non-trivial)
# ---------------------------------------------------------------------------

def _c5_dests(state, executor, picks):
    # Any space with an adjacent source holding Patriot units (handler
    # marches 1 unit src -> dest, then Battles in dest).
    out = []
    for dest in _spaces(state):
        if any(_has_any(state, s, _PATRIOT_UNITS) for s in _adj_in_play(state, dest)):
            out.append(dest)
    return _ids(out)


def _c5_srcs(state, executor, picks):
    dest = picks.get("dest")
    if not dest:
        return []
    return _ids(s for s in _adj_in_play(state, dest)
                if _has_any(state, s, _PATRIOT_UNITS))


def _c7_dests(state, executor, picks):
    # West Indies or any City (handler validates the same).
    out = [WEST_INDIES_ID] if WEST_INDIES_ID in _spaces(state) else []
    out += [s for s in _spaces(state) if _is_city(s)]
    return _ids(out)


def _c9_spaces(actor):
    def _options(state, executor, picks):
        out = []
        for sid in _spaces(state):
            sp = _sp(state, sid)
            if actor == BRITISH:
                if not sp.get(REGULAR_BRI, 0):
                    continue
                enemy = (sp.get(REGULAR_PAT, 0) + sp.get(REGULAR_FRE, 0)
                         + sp.get(MILITIA_A, 0))
            else:
                if not sp.get(REGULAR_PAT, 0):
                    continue
                enemy = sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)
            if enemy > 0:
                out.append(sid)
        return _ids(out)
    return _options


def _c11_spaces(state, executor, picks):
    ctrl = _control_map(state)
    return _ids(s for s in _spaces(state)
                if ctrl.get(s) == "REBELLION"
                and _has_any(state, s, _PATRIOT_UNITS))


def _c15_colonies(state, executor, picks):
    return _ids(s for s in _spaces(state) if _is_colony(s))


def _c16_cities(state, executor, picks):
    return _ids(s for s in _spaces(state) if _is_city(s))


def _c16_targets(state, executor, picks):
    return _ids(s for s in _spaces(state) if s != WEST_INDIES_ID)


def _c17_spaces(state, executor, picks):
    return _ids(s for s in _spaces(state)
                if _is_reserve(s) and _sp(state, s).get(FORT_PAT, 0))


def _c19_targets(state, executor, picks):
    return _ids(s for s in _spaces(state) if s != WEST_INDIES_ID)


def _sc_ga(state, executor, picks):
    return _ids(s for s in ("South_Carolina", "Georgia") if s in _spaces(state))


def _c23_shaded_targets(state, executor, picks):
    return _ids(s for s in ("North_Carolina", "South_Carolina")
                if s in _spaces(state) and _has_any(state, s, (MILITIA_U, MILITIA_A)))


def _c23_srcs(state, executor, picks):
    return _ids(s for s in ("North_Carolina", "South_Carolina")
                if s in _spaces(state) and _has_any(state, s, _PATRIOT_UNITS))


def _c23_dsts(state, executor, picks):
    src = picks.get("src")
    if not src:
        return []
    moving_militia = _has_any(state, src, (MILITIA_A, MILITIA_U))
    out = []
    for s in _adj_in_play(state, src):
        stype = map_adj.space_type(s)
        if stype == "City":
            continue
        if stype == "Reserve" and moving_militia:
            continue
        out.append(s)
    return _ids(out)


def _cities(state, executor, picks):
    return _ids(s for s in _spaces(state) if _is_city(s))


def _c27_colonies(state, executor, picks):
    ctrl = _control_map(state)
    return _ids(s for s in _spaces(state)
                if _is_colony(s) and ctrl.get(s) == BRITISH)


def _c29_factions(state, executor, picks):
    return [("Patriots (activate Militia)", PATRIOTS),
            ("Indians (activate War Parties)", INDIANS)]


def _c35_targets(state, executor, picks):
    return _ids(s for s in ("New_York", "New_York_City") if s in _spaces(state))


def _c35_shaded_targets(state, executor, picks):
    out = ["New_York"] if "New_York" in _spaces(state) else []
    out += _adj_in_play(state, "New_York")
    return _ids(set(out))


def _c47_unshaded(state, executor, picks):
    ctrl = _control_map(state)
    return _ids(s for s in _spaces(state)
                if _is_colony(s) and ctrl.get(s) == BRITISH)


def _c47_shaded(state, executor, picks):
    return [(f"{s} ({_sp(state, s).get(TORY, 0)} Tories)", s)
            for s in sorted(_spaces(state)) if _is_colony(s)]


def _c50_colonies(state, executor, picks):
    return _ids(s for s in _spaces(state) if _is_colony(s))


def _c59_spaces(state, executor, picks):
    return _ids(s for s in _spaces(state)
                if _sp(state, s).get(REGULAR_PAT, 0) or _sp(state, s).get(REGULAR_FRE, 0))


def _c73_spaces(state, executor, picks):
    return _ids(s for s in ("New_York", "Northwest", "Quebec")
                if s in _spaces(state)
                and _has_any(state, s, (FORT_BRI, FORT_PAT, VILLAGE)))


def _c76_spaces(state, executor, picks):
    return _ids(s for s in _spaces(state)
                if s != WEST_INDIES_ID and not _is_city(s)
                and (_sp(state, s).get(MILITIA_U, 0)
                     + _sp(state, s).get(MILITIA_A, 0)) >= 3)


def _c77_spaces(state, executor, picks):
    return _ids(s for s in _spaces(state)
                if _has_any(state, s, (REGULAR_BRI, TORY, FORT_BRI))
                and _has_any(state, s, (WARPARTY_A, WARPARTY_U, VILLAGE)))


def _c79_unshaded(state, executor, picks):
    out = []
    for s in _spaces(state):
        if not _is_colony(s):
            continue
        sp = _sp(state, s)
        bases = sp.get(FORT_BRI, 0) + sp.get(FORT_PAT, 0) + sp.get(VILLAGE, 0)
        if bases < 2:
            out.append(s)
    return _ids(out)


def _c79_shaded(state, executor, picks):
    return _ids(s for s in _spaces(state)
                if _is_colony(s)
                and _has_any(state, s, (VILLAGE, WARPARTY_U, WARPARTY_A)))


def _c83_targets(state, executor, picks):
    return _ids(s for s in ("Quebec", "Quebec_City") if s in _spaces(state))


def _c84_colonies(state, executor, picks):
    # Mirror the handler's Indian free-Gather legality (§3.4.1, Colony-only).
    from lod_ai.commands.gather import SUPPORT_OK

    def _wp(sid):
        sp = _sp(state, sid)
        return sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)

    out = []
    for sid in _spaces(state):
        if not _is_colony(sid) or sid == WEST_INDIES_ID:
            continue
        if state.get("support", {}).get(sid, 0) not in SUPPORT_OK:
            continue
        if _wp(sid) or any(_wp(n) for n in _adj_in_play(state, sid)):
            out.append(sid)
    return _ids(out)


def _c93_targets(state, executor, picks):
    def _adj_reserve(sid):
        return any(_is_reserve(n) for n in map_adj.adjacent_spaces(sid))
    return _ids(s for s in _spaces(state) if _is_colony(s) and _adj_reserve(s))


# ---------------------------------------------------------------------------
# The wired registry (Piece 7 batch 1: 26 space-selection cards)
# ---------------------------------------------------------------------------

EVENT_CHOICES: Dict[int, Tuple[Step, ...]] = {
    5: (
        Step("dest", "Free March + Battle: destination space", _c5_dests,
             side=True, decider=PATRIOTS),
        Step("src", "March from which adjacent space?", _c5_srcs, side=True,
             decider=PATRIOTS),
    ),
    7: (
        Step("dest", "Move up to 2 Regulars from Available to", _c7_dests,
             side=False, decider=BRITISH),
    ),
    9: (
        Step("spaces", "Skirmish in up to 3 spaces", _c9_spaces(BRITISH),
             side=False, kind="multi", min_sel=1, max_sel=3, decider=BRITISH),
        Step("spaces", "Skirmish in up to 3 spaces", _c9_spaces(PATRIOTS),
             side=True, kind="multi", min_sel=1, max_sel=3, decider=PATRIOTS),
    ),
    11: (
        Step("spaces", "Replace a Patriot unit with a Fort in up to 2 spaces",
             _c11_spaces, side=True, kind="multi", min_sel=1, max_sel=2,
             decider=PATRIOTS),
    ),
    15: (
        Step("colony", "Free March / Battle / Partisans: which Colony?",
             _c15_colonies, side=True, decider=PATRIOTS),
    ),
    16: (
        Step("city", "Shift which City to Passive Opposition?", _c16_cities,
             side=True),
        Step("target", "Place 2 Tories in which space?", _c16_targets,
             side=False),
    ),
    17: (
        Step("space", "Remove a Patriot Fort from which Reserve?", _c17_spaces,
             side=False),
    ),
    19: (
        Step("targets", "Place 3 Militia (spaces may repeat)", _c19_targets,
             side=True, kind="repeat", count=3, decider=PATRIOTS),
    ),
    21: (
        Step("target", "Shift which space 2 levels toward Active Support?",
             _sc_ga, side=False),
        Step("target", "Free March + Battle in which space?", _sc_ga,
             side=True, decider=PATRIOTS),
    ),
    23: (
        Step("target", "Remove 4 British units from which space (Militia present)?",
             _c23_shaded_targets, side=True),
        Step("src", "Move all Patriot units FROM which space?", _c23_srcs,
             side=False),
        Step("dst", "Move them INTO which adjacent Province?", _c23_dsts,
             side=False),
    ),
    25: (
        Step("cities", "Choose 2 Cities", _cities, kind="multi", max_sel=2,
             exact=True),
    ),
    27: (
        Step("cities", "Shift + place Militia in 2 Cities", _cities,
             side=True, kind="multi", max_sel=2, exact=True),
        Step("colonies", "Place 2 Tories each in 2 British-controlled Colonies",
             _c27_colonies, side=False, kind="multi", max_sel=2, exact=True),
    ),
    29: (
        Step("target", "Which faction must Activate half its pieces?",
             _c29_factions, side=False),
    ),
    31: (
        Step("target", "Fort + 2 Tories in which space?", _sc_ga, side=False),
        Step("target", "2 Militia + Partisans in which space?", _sc_ga,
             side=True, decider=PATRIOTS),
    ),
    35: (
        Step("target", "Remove 2 Patriot pieces + Activate Militia where?",
             _c35_targets, side=False),
        Step("shaded_target", "Remove all Tories in New York or one adjacent space",
             _c35_shaded_targets, side=True),
    ),
    47: (
        Step("colony", "Place 3 Tories in which British-controlled Colony?",
             _c47_unshaded, side=False),
        Step("colony", "Replace all Tories (+2 Propaganda) in which Colony?",
             _c47_shaded, side=True),
    ),
    50: (
        Step("colony", "Place 2 Continentals + 2 French Regulars in which Colony?",
             _c50_colonies, side=True),
    ),
    59: (
        Step("space", "Remove 2 Continentals + 2 French Regulars from which space?",
             _c59_spaces, side=False),
    ),
    73: (
        Step("space", "Remove a Fort/Village in which space?", _c73_spaces,
             side=False),
    ),
    76: (
        Step("space", "Replace 3 Militia with 3 Tories in which Province?",
             _c76_spaces, side=False, decider=BRITISH),
    ),
    77: (
        Step("space", "Place a Village in which space?", _c77_spaces,
             side=False),
    ),
    79: (
        Step("colony", "Place Village + 2 War Parties in which Colony?",
             _c79_unshaded, side=False),
        Step("colony", "Remove Village + 2 War Parties in which Colony?",
             _c79_shaded, side=True),
    ),
    81: (
        Step("target", "War Parties + Raid + Village in which space?", _sc_ga,
             side=False),
    ),
    83: (
        Step("target", "Place up to 3 pieces in which space?", _c83_targets,
             side=True),
    ),
    84: (
        Step("colonies", "Indians free Gather in 2 Colonies", _c84_colonies,
             side=False, kind="multi", max_sel=2, exact=True, min_options=2,
             decider=INDIANS),
    ),
    93: (
        Step("targets", "Shift toward Neutral + Raid marker in up to 3 Colonies",
             _c93_targets, side=False, kind="multi", min_sel=1, max_sel=3),
    ),
}
