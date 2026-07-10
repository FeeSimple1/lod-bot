"""§8.3.5 Non-player "Who gets benefits / who is harmed" faction ordering.

Manual §8.3.5, "Events: Who, What, and Where" — unless the Event text or
an Event Instruction (§8.3.1) says otherwise:

  • When there is a choice of who gets Event BENEFITS (Resources, free
    Commands, placing pieces): select the executing Faction, then the
    other friendly Faction, then a random enemy, Non-player first.
  • When the Event effects are HARMFUL (removing pieces, Activating War
    Parties or Militia, or similar): select a random enemy, player first.

Factions are not on the Random Spaces table, so equal-rank ties AMONG
factions are resolved by a seeded roll (Q22: never embedded in a sort
key), not the space table.  "player" / "Non-player" refers to whether an
enemy seat is human (state["human_factions"]) — in an all-bot game every
enemy is Non-player, so the player/NP split is a no-op and only the
seeded order among enemies applies.
"""
from lod_ai import rules_consts as C

_ALLY = {
    C.BRITISH: C.INDIANS, C.INDIANS: C.BRITISH,
    C.PATRIOTS: C.FRENCH, C.FRENCH: C.PATRIOTS,
}
_ENEMIES = {
    C.BRITISH: (C.PATRIOTS, C.FRENCH), C.INDIANS: (C.PATRIOTS, C.FRENCH),
    C.PATRIOTS: (C.BRITISH, C.INDIANS), C.FRENCH: (C.BRITISH, C.INDIANS),
}


def _humans(state):
    return set(state.get("human_factions", set()) or set())


def _seeded_order(state, factions):
    """Seeded random order over *factions* (a faction tie, not a space
    tie — Q22).  rng-less states fall back to sorted order."""
    fs = sorted(factions)
    rng = state.get("rng")
    if rng is None or len(fs) <= 1:
        return fs
    out = []
    while fs:
        out.append(fs.pop(rng.randrange(len(fs))))
    return out


def beneficiary_order(state, executing_faction, candidates=None):
    """§8.3.5 benefit order: executing Faction, then the other friendly
    Faction, then a random enemy (Non-player first).  *candidates*
    optionally restricts to factions that can actually receive it."""
    e = str(executing_faction).upper()
    humans = _humans(state)
    enemies = list(_ENEMIES.get(e, ()))
    nps = [x for x in enemies if x not in humans]
    players = [x for x in enemies if x in humans]
    # Unknown executor (bare test states without "active"): no friendly
    # ordering exists -- fall through to the caller's default.
    head = [e, _ALLY[e]] if e in _ALLY else []
    order = head + _seeded_order(state, nps) + _seeded_order(state, players)
    if candidates is not None:
        cand = {str(f).upper() for f in candidates}
        order = [f for f in order if f in cand]
    return order


def harm_target_order(state, executing_faction, candidates=None):
    """§8.3.5 harm order: a random enemy, player (human) first.  Only
    enemy factions are eligible; *candidates* optionally restricts (e.g.
    to enemies that actually have removable pieces present)."""
    e = str(executing_faction).upper()
    humans = _humans(state)
    enemies = list(_ENEMIES.get(e, ()))
    players = [x for x in enemies if x in humans]
    nps = [x for x in enemies if x not in humans]
    order = _seeded_order(state, players) + _seeded_order(state, nps)
    if candidates is not None:
        cand = {str(f).upper() for f in candidates}
        order = [f for f in order if f in cand]
    return order


def first_beneficiary(state, executing_faction, candidates=None, default=None):
    order = beneficiary_order(state, executing_faction, candidates)
    return order[0] if order else default


def first_harm_target(state, executing_faction, candidates=None, default=None):
    order = harm_target_order(state, executing_faction, candidates)
    return order[0] if order else default
