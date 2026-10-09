"""Human decisions assigned by Winter Quarters rules (Manual chapter 6)."""
from __future__ import annotations

from lod_ai import rules_consts as C
from lod_ai.cli_utils import choose_one, choose_count, get_input_provider
from lod_ai.board import control
from lod_ai.board.pieces import remove_piece, marker_count
from lod_ai.economy import resources
from lod_ai.map import adjacency
from lod_ai.util.history import push_history
from lod_ai.leaders import leader_location
from lod_ai.util.leader_state import GAGE


def humans(state, supplied=None):
    return set(state.get("human_factions", ())) if supplied is None else set(supplied)


def _context(state, faction, prompt):
    from lod_ai.cli_display import display_board_state, display_history
    control.refresh_control(state)
    hook = getattr(get_input_provider(), "begin_turn", None)
    if callable(hook):
        hook(faction, state.get("current_card", {}), {})
    print(f"\n[{faction}] {prompt}")
    display_board_state(state)
    display_history(state, count=5)


def pick(state, faction, prompt, options):
    _context(state, faction, prompt)
    return choose_one(prompt, options)


def count(state, faction, prompt, maximum):
    _context(state, faction, prompt)
    return choose_count(prompt, min_val=0, max_val=maximum)


def ordered_spaces(state, faction, spaces, human_factions):
    """Let the owning player decide which supply cost to resolve first."""
    remaining = list(spaces)
    while remaining:
        sid = (pick(state, faction, "Choose the next space to supply:",
                    [(s, s) for s in sorted(remaining)])
               if faction in human_factions and len(remaining) > 1
               else remaining[0])
        remaining.remove(sid)
        yield sid


def remove_units(state, faction, sid, tags, amount, prompt):
    """Select exactly the required number, including Active/Underground choice."""
    for _ in range(amount):
        options = [(f"{tag} in {sid} ({state['spaces'][sid].get(tag, 0)})", tag)
                   for tag in tags if state['spaces'][sid].get(tag, 0)]
        tag = pick(state, faction, prompt, options)
        remove_piece(state, tag, sid, 1, to="available")


def choose_deserter(state, faction, tags, prompt):
    options = [(f"{tag} in {sid} ({sp[tag]})", (sid, tag))
               for sid, sp in sorted(state["spaces"].items())
               for tag in tags if sp.get(tag, 0)]
    return pick(state, faction, prompt, options)


def nearest(state, origin, destinations):
    reachable = [(len(path), sid) for sid in destinations
                 if (path := adjacency.shortest_path(origin, sid))]
    if not reachable:
        return []
    distance = min(n for n, _ in reachable)
    return sorted(sid for n, sid in reachable if n == distance)


def support(state, faction):
    """A player may stop, remove markers only, or buy up to two shifts/space."""
    shifts = {}
    british = faction == C.BRITISH
    target = C.ACTIVE_SUPPORT if british else C.ACTIVE_OPPOSITION
    direction = 1 if british else -1
    tags = (C.RAID, C.PROPAGANDA) if british else (C.RAID,)
    title = "Reward Loyalty" if british else "Committees of Correspondence"
    while True:
        options = [("Done — keep remaining Resources", None)]
        for sid, sp in sorted(state["spaces"].items()):
            if adjacency.space_type(sid) not in ("City", "Colony"):
                continue
            eligible = ((state["control"].get(sid) == C.BRITISH
                         and sp.get(C.REGULAR_BRI) and sp.get(C.TORY)) if british else
                        (state["control"].get(sid) == "REBELLION"
                         and any(sp.get(t) for t in (C.REGULAR_PAT, C.MILITIA_A,
                                                    C.MILITIA_U, C.FORT_PAT))))
            if not eligible:
                continue
            markers = [tag for tag in tags if marker_count(state, tag, sid)]
            free_shift = british and leader_location(state, GAGE) == sid and shifts.get(sid, 0) == 0
            if markers and resources.can_afford(state, faction, 1):
                options.extend((f"{sid}: remove one {tag} (1 Resource)", (sid, tag))
                               for tag in markers)
            elif (not markers and shifts.get(sid, 0) < 2
                  and state["support"].get(sid, 0) != target
                  and (free_shift or resources.can_afford(state, faction, 1))):
                cost = "free — Gage" if free_shift else "1 Resource"
                options.append((f"{sid}: shift one level ({cost})", (sid, None)))
        if len(options) == 1:
            break
        choice = pick(state, faction, f"{title}: choose spending or finish:", options)
        if choice is None:
            break
        sid, marker = choice
        free_shift = (not marker and british and leader_location(state, GAGE) == sid
                      and shifts.get(sid, 0) == 0)
        if not free_shift:
            resources.spend(state, faction, 1)
        if marker:
            remove_piece(state, marker, sid, 1, to="available")
            push_history(state, f"{title} — removed {marker} in {sid}")
        else:
            state["support"][sid] = state["support"].get(sid, 0) + direction
            shifts[sid] = shifts.get(sid, 0) + 1
            push_history(state, f"{title} — shifted {sid} one level")
