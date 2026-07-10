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

from lod_ai.cli_utils import choose_count, choose_multiple, choose_one_or_back
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

_FACTIONS = (BRITISH, PATRIOTS, FRENCH, INDIANS)
_ENEMIES = {BRITISH: (PATRIOTS, FRENCH), INDIANS: (PATRIOTS, FRENCH),
            PATRIOTS: (BRITISH, INDIANS), FRENCH: (BRITISH, INDIANS)}
_PIECE_TAGS = {
    BRITISH: (REGULAR_BRI, TORY, FORT_BRI),
    PATRIOTS: (REGULAR_PAT, MILITIA_U, MILITIA_A, FORT_PAT),
    FRENCH: (REGULAR_FRE,),
    INDIANS: (WARPARTY_U, WARPARTY_A, VILLAGE),
}
_UNIT_TAGS = {
    BRITISH: (REGULAR_BRI, TORY),
    PATRIOTS: (REGULAR_PAT, MILITIA_U, MILITIA_A),
    FRENCH: (REGULAR_FRE,),
    INDIANS: (WARPARTY_U, WARPARTY_A),
}


@dataclass(frozen=True)
class Step:
    key: str                       # override suffix: card<N>_<key>
    prompt: str
    options: OptionsFn
    side: Optional[bool] = None    # None = both sides; True shaded; False unshaded
    kind: str = "one"              # "one" | "multi" | "repeat" | "mix" | "map"
    # None = the executing faction decides; a faction constant, or a
    # callable (state, executor, picks) -> faction for pick-dependent
    # deciders (e.g. card 80: the targeted faction places its removals).
    decider: Any = None
    min_sel: int = 1               # "multi" only
    max_sel: Optional[int] = None  # "multi" only; None = no cap
    exact: bool = False            # "multi": pick exactly min(max_sel, len(opts))
    count: int = 1                 # "repeat": picks (repetition OK); "mix": total
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
        decider = step.decider(state, executor, picks) if callable(step.decider) \
            else (step.decider or executor)
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
        elif step.kind == "mix":
            # opts = [(label_a, tag_a), (label_b, tag_b)]; the value is a
            # {tag: count} dict summing to step.count (the handler's shape).
            (lab_a, tag_a), (lab_b, tag_b) = opts[0], opts[1]
            n = choose_count(f"{label} — how many {lab_a}? (rest: {lab_b})",
                             min_val=0, max_val=step.count)
            value = {tag_a: n, tag_b: step.count - n}
        elif step.kind == "map":
            # opts = [(origin, (dest, dest, ...)), ...]; the value maps each
            # origin to a chosen destination (e.g. card 88's destinations).
            value = {}
            for origin, dests in opts:
                if not dests:
                    continue
                value[origin] = choose_one_or_back(
                    f"{label} — from {origin}, move to:",
                    [(d, d) for d in dests])
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


def _c14_dests(state, executor, picks):
    return _ids(s for s in ("North_Carolina", "Southwest") if s in _spaces(state))


def _c14_scout_srcs(state, dest):
    out = []
    for s in _adj_in_play(state, dest):
        if _is_city(s):
            continue
        if _sp(state, s).get(REGULAR_BRI, 0) and _has_any(
                state, s, (WARPARTY_U, WARPARTY_A)):
            out.append(s)
    return out


def _c14_march_srcs(state, dest):
    return [s for s in _adj_in_play(state, dest)
            if _has_any(state, s, (WARPARTY_U, WARPARTY_A))]


def _c14_ops(state, executor, picks):
    dest = picks.get("dest")
    if not dest:
        return []
    out = []
    if _c14_scout_srcs(state, dest):
        out.append(("Scout (1 War Party + 1 British Regular)", "SCOUT"))
    if _c14_march_srcs(state, dest):
        out.append(("March (1 War Party)", "MARCH"))
    return out


def _c14_srcs(state, executor, picks):
    dest = picks.get("dest")
    if not dest:
        return []
    if picks.get("op") == "SCOUT":
        return _ids(_c14_scout_srcs(state, dest))
    return _ids(_c14_march_srcs(state, dest))


def _c14_followups(state, executor, picks):
    return [("Indians War Path", "WAR_PATH"),
            ("British free Battle", "BRITISH_BATTLE")]


def _c14_shaded_srcs(state, executor, picks):
    dest = picks.get("dest")
    if not dest:
        return []
    return _ids(s for s in _adj_in_play(state, dest)
                if _has_any(state, s, _PATRIOT_UNITS))


def _c26_srcs(state, executor, picks):
    if "North_Carolina" not in _spaces(state):
        return []
    return _ids(s for s in _adj_in_play(state, "North_Carolina")
                if _has_any(state, s, _PATRIOT_UNITS))


def _c26_choices(state, executor, picks):
    return [("Place 1 British Fort", "FORT"), ("Place 2 Tories", "TORIES")]


def _c38_shaded_choices(state, executor, picks):
    if "New_York" not in _spaces(state):
        return []
    return [("3 Militia in New York", "MILITIA"),
            ("3 War Parties in New York", "WARPARTY")]


def _c38_spaces(state, executor, picks):
    return _ids(s for s in ("Quebec", "New_York") if s in _spaces(state))


def _mix_bri_tory(state, executor, picks):
    return [("British Regulars", REGULAR_BRI), ("Tories", TORY)]


def _c52_options(state, executor, picks):
    # The removal branch only exists for a BRITISH executor (sheets
    # P52/F52 skip it; the handler checks executor == BRITISH).
    if executor != BRITISH:
        return []
    return [("Remove up to 4 French Regulars (max, priority spaces)", False),
            ("Remove none", True)]


def _c55_options(state, executor, picks):
    return [("Yes — free Battle in West Indies", True), ("No", False)]


def _c62_shaded_choices(state, executor, picks):
    out = []
    if "Quebec" in _spaces(state):
        out.append(("3 French Regulars in Quebec", "FRENCH_QUEBEC"))
    if "Northwest" in _spaces(state):
        out.append(("3 Militia in Northwest", "MILITIA_NORTHWEST"))
    return out


def _c62_targets(state, executor, picks):
    return _ids(s for s in ("New_York", "Quebec", "Northwest")
                if s in _spaces(state))


def _c62_unshaded_choices(state, executor, picks):
    return [("3 War Parties", "WARPARTY"), ("3 Tories", "TORIES")]


def _c4_bases(state, executor, picks):
    return [("Patriot Fort", "FORT_PAT"), ("British Fort", "FORT_BRI"),
            ("Village", "VILLAGE")]


def _c4_units(state, executor, picks):
    return [("3 Militia", "MILITIA"), ("3 War Parties", "WARPARTY")]


def _all_factions(state, executor, picks):
    return [(f.title(), f) for f in _FACTIONS]


def _c48_factions(state, executor, picks):
    out = []
    for fac in (PATRIOTS, FRENCH, INDIANS):
        tags = _UNIT_TAGS[fac]
        if any(sp.get(REGULAR_BRI, 0) and any(sp.get(t, 0) for t in tags)
               for sp in _spaces(state).values()):
            out.append((fac.title(), fac))
    return out


def _c66_factions(state, executor, picks):
    return [("French", FRENCH), ("Patriots", PATRIOTS)]


def _c66_targets(state, executor, picks):
    return _ids(s for s in ("Florida", "Southwest") if s in _spaces(state))


def _c67_factions(state, executor, picks):
    if state.get("toa_played"):
        fr = "French (free Muster)"
    else:
        fr = "French (pre-Treaty: benefit passes to Patriots)"
    return [(fr, FRENCH), ("Patriots (free Rally)", PATRIOTS)]


def _c74_recipients(state, executor, picks):
    return [("Indians", INDIANS), ("British", BRITISH)]


def _c74_spaces(state, executor, picks):
    out = []
    for sid, sp in _spaces(state).items():
        wp = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
        mil = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0)
        if wp >= 1 and mil >= 1 and wp + mil >= 3:
            out.append(sid)
    return _ids(out)


def _fac_pieces_on_map(state, fac):
    tags = _PIECE_TAGS[fac]
    return sum(sp.get(t, 0) for sp in _spaces(state).values() for t in tags)


def _c80_factions(state, executor, picks):
    # "Select one Faction" — any Faction with removable pieces; enemies
    # of the executor listed first (the only picks a player would want).
    enemies = _ENEMIES.get(executor, ())
    ordered = list(enemies) + [f for f in _FACTIONS if f not in enemies]
    return [(f"{f.title()} ({_fac_pieces_on_map(state, f)} pieces on map)", f)
            for f in ordered if _fac_pieces_on_map(state, f)]


def _c80_spaces(state, executor, picks):
    fac = picks.get("faction")
    if not fac:
        return []
    tags = _PIECE_TAGS[fac]
    return _ids(s for s in _spaces(state) if _has_any(state, s, tags))


def _c80_decider(state, executor, picks):
    # "That Faction must remove two of its own pieces in each of two
    # spaces" — the targeted faction chooses where (own-piece removal).
    return picks.get("faction") or executor


def _c85_choices(state, executor, picks):
    return [("2 Militia", "MILITIA"), ("2 Continentals", "CONTINENTAL")]


def _c87_pieces(state, executor, picks):
    sp = _sp(state, "Pennsylvania")
    order = (WARPARTY_U, WARPARTY_A, MILITIA_U, MILITIA_A, REGULAR_PAT,
             REGULAR_BRI, REGULAR_FRE, TORY, FORT_BRI, FORT_PAT, VILLAGE)
    return [(f"{t} (x{sp.get(t, 0)})", t) for t in order if sp.get(t, 0)]


def _c88_factions(state, executor, picks):
    my_tags = _UNIT_TAGS.get(executor, ())
    out = []
    for fac in _ENEMIES.get(executor, ()):
        fac_tags = _PIECE_TAGS[fac]
        if any(_has_any(state, sid, my_tags) and _has_any(state, sid, fac_tags)
               for sid in _spaces(state)):
            out.append((fac.title(), fac))
    return out


def _c88_dest_map(state, executor, picks):
    # One (origin, destinations) entry per space shared with the chosen
    # faction: the engine moves from ONE §8.2-random shared origin, so
    # the player pre-picks a destination for each possible origin.
    fac = picks.get("target_faction")
    if not fac:
        return []
    my_tags = _UNIT_TAGS.get(executor, ())
    fac_tags = _PIECE_TAGS[fac]
    out = []
    for sid in _spaces(state):
        if _has_any(state, sid, my_tags) and _has_any(state, sid, fac_tags):
            dests = tuple(_adj_in_play(state, sid))
            if dests:
                out.append((sid, dests))
    return out


# ---------------------------------------------------------------------------
# The wired registry (Piece 7: all 43 choice-bearing cards —
# batch 1 space-selection, batch 2 sub-option, batch 3 faction/mix)
# ---------------------------------------------------------------------------

EVENT_CHOICES: Dict[int, Tuple[Step, ...]] = {
    4: (
        Step("base", "Place which base in Massachusetts?", _c4_bases,
             side=True, min_options=3),
        Step("units", "Place which units in Massachusetts?", _c4_units,
             side=True, min_options=2),
    ),
    5: (
        Step("dest", "Free March + Battle: destination space", _c5_dests,
             side=True, decider=PATRIOTS),
        Step("src", "March from which adjacent space?", _c5_srcs, side=True,
             decider=PATRIOTS),
    ),
    7: (
        Step("dest", "Move up to 2 British Regulars from Available to",
             _c7_dests, side=False),
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
    14: (
        # Shaded: Patriots free March to NC/SW, then free Battle there.
        Step("dest", "Free March + Battle: destination", _c14_dests,
             side=True, decider=PATRIOTS),
        Step("src", "March from which adjacent space?", _c14_shaded_srcs,
             side=True, decider=PATRIOTS),
        # Unshaded: Indians free Scout or March to NC/SW, then a follow-up.
        Step("dest", "Indian Scout/March destination", _c14_dests,
             side=False, decider=INDIANS),
        Step("op", "Which operation?", _c14_ops, side=False, decider=INDIANS),
        Step("src", "From which adjacent space?", _c14_srcs, side=False,
             decider=INDIANS),
        Step("followup", "Then:", _c14_followups, side=False),
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
    18: (
        Step("target_faction", "Make which Faction Ineligible through next card?",
             _all_factions, side=False, min_options=4),
    ),
    19: (
        Step("targets", "Place 3 Militia (spaces may repeat)", _c19_targets,
             side=True, kind="repeat", count=3),
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
    26: (
        Step("src", "Free March to North Carolina from which space?",
             _c26_srcs, side=True, decider=PATRIOTS),
        Step("choice", "In North Carolina:", _c26_choices, side=False,
             decider=BRITISH, min_options=2),
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
    38: (
        Step("shaded_choice", "Place in New York:", _c38_shaded_choices,
             side=True, min_options=2),
        Step("unshaded_space", "Reinforce which space?", _c38_spaces,
             side=False, decider=BRITISH),
        Step("unshaded_mix", "Place 4 British cubes", _mix_bri_tory,
             side=False, kind="mix", count=4, decider=BRITISH, min_options=2),
    ),
    35: (
        Step("target", "Remove 2 Patriot pieces + Activate Militia where?",
             _c35_targets, side=False),
        Step("shaded_target", "Remove all Tories in New York or one adjacent space",
             _c35_shaded_targets, side=True),
    ),
    44: (
        Step("target_faction", "Make which Faction Ineligible through next card?",
             _all_factions, side=False, min_options=4),
    ),
    47: (
        Step("colony", "Place 3 Tories in which British-controlled Colony?",
             _c47_unshaded, side=False),
        Step("colony", "Replace all Tories (+2 Propaganda) in which Colony?",
             _c47_shaded, side=True),
    ),
    48: (
        Step("faction", "Which non-British Faction moves its units?",
             _c48_factions, side=True),
    ),
    50: (
        Step("colony", "Place 2 Continentals + 2 French Regulars in which Colony?",
             _c50_colonies, side=True),
    ),
    52: (
        Step("no_remove_french", "French Regulars:", _c52_options,
             side=False, min_options=2),
    ),
    55: (
        Step("do_battle", "French free Battle in West Indies?", _c55_options,
             side=False, decider=FRENCH, min_options=2),
    ),
    59: (
        Step("space", "Remove 2 Continentals + 2 French Regulars from which space?",
             _c59_spaces, side=False),
    ),
    62: (
        Step("shaded_choice", "Place which?", _c62_shaded_choices, side=True),
        Step("target", "Place 3 pieces in which space?", _c62_targets,
             side=False),
        Step("unshaded_choice", "Which pieces?", _c62_unshaded_choices,
             side=False, min_options=2),
    ),
    66: (
        Step("shaded_faction", "Free March + Battle (+2) in Florida for whom?",
             _c66_factions, side=True, min_options=2),
        Step("target", "Place 6 British cubes in which space?", _c66_targets,
             side=False),
        Step("mix", "Place 6 British cubes", _mix_bri_tory, side=False,
             kind="mix", count=6, min_options=2),
    ),
    67: (
        Step("faction", "Free Rally/Muster + stay Eligible for whom?",
             _c67_factions, side=True, min_options=2),
    ),
    74: (
        Step("recipient", "Who gains 1 Resource per 2 Villages?",
             _c74_recipients, side=False, min_options=2),
        Step("spaces", "Remove War Party/Militia mix in 2 spaces",
             _c74_spaces, side=True, kind="multi", max_sel=2, exact=True),
    ),
    80: (
        Step("faction", "Select one Faction (removes 2 own pieces in each of 2 spaces)",
             _c80_factions, side=False),
        Step("spaces", "Remove its pieces in which 2 spaces?", _c80_spaces,
             side=False, kind="multi", max_sel=2, exact=True,
             decider=_c80_decider),
    ),
    85: (
        Step("shaded_choice", "Place which with the 2 French Regulars?",
             _c85_choices, side=True, min_options=2),
        Step("mix", "Place 3 British cubes in Southwest", _mix_bri_tory,
             side=False, kind="mix", count=3, decider=BRITISH, min_options=2),
    ),
    87: (
        Step("piece", "Remove which piece in Pennsylvania?", _c87_pieces,
             side=False),
    ),
    88: (
        Step("target_faction", "Disengage from which enemy Faction?",
             _c88_factions, side=False),
        Step("destinations", "Destinations per possible origin",
             _c88_dest_map, side=False, kind="map"),
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
