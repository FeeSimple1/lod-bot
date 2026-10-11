"""
Queue and pop “free” Commands or Special Activities granted by cards.

Each tuple in state["free_ops"] is
    (FACTION, op_name, location)
      • FACTION  : upper-case key used everywhere else (“PATRIOTS”, …)
      • op_name  : 'march', 'battle', 'rally', 'war_path', 'partisans', …
                   'march_then_battle' links one March destination to an
                   optional Battle there (card 48).
      • location : None = anywhere; otherwise a single space id (e.g. "West_Indies")
"""

def queue_free_op(state, faction: str, op: str,
                  loc: str | None = None) -> None:
    state.setdefault("free_ops", []).append((faction.upper(), op, loc))


def queue_after_free_ops(state, effect: str, **params) -> None:
    """Schedule printed effects that follow immediate Commands (§5.1/5.3).

    Explicit records, not callbacks, keep the pending event saveable.
    """
    if effect not in {"place_marker", "shift_support_toward"}:
        raise ValueError(f"Unsupported free-operation follow-up: {effect}")
    state.setdefault("free_op_followups", []).append({"effect": effect, **params})


def resolve_after_free_ops(state) -> None:
    """Apply and consume the remaining printed event effects in FIFO order."""
    from lod_ai.board.pieces import place_marker
    from lod_ai.cards.effects.shared import shift_support
    from lod_ai.util.history import push_history

    for entry in state.pop("free_op_followups", []):
        sid = entry["space"]
        if entry["effect"] == "place_marker":
            placed = place_marker(state, entry["marker"], sid, entry["quantity"])
            push_history(state, f"Event follow-up: placed {placed} {entry['marker']} in {sid}")
        elif entry["effect"] == "shift_support_toward":
            level = state.get("support", {}).get(sid, 0)
            target, steps = entry["target"], entry["steps"]
            delta = max(-steps, min(steps, target - level))
            shift_support(state, sid, delta)
            push_history(state, f"Event follow-up: {sid} shifts {delta:+} toward {target}")
        else:
            raise ValueError(f"Unknown free-operation follow-up: {entry['effect']}")

def pop_free_ops(state, faction: str):
    """
    Return and remove every queued op for *faction* (FIFO order).
    Also normalizes any legacy 'march_battle' entries into the
    intended two separate ops: 'march' then 'battle'.
    """
    q = state.get("free_ops", [])
    taken = [t for t in q if t[0] == faction.upper()]
    state["free_ops"] = [t for t in q if t[0] != faction.upper()]

    normalized = []
    for fac, op, loc in taken:
        if op == "march_battle":            # defensive shim
            normalized.append((fac, "march",  loc))
            normalized.append((fac, "battle", loc))
        else:
            normalized.append((fac, op, loc))
    return normalized
