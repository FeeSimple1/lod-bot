"""
Queue and pop “free” Commands or Special Activities granted by cards.

Each tuple in state["free_ops"] is
    (FACTION, op_name, location)
      • FACTION  : upper-case key used everywhere else (“PATRIOTS”, …)
      • op_name  : 'march', 'battle', 'march_battle', 'rally', 'war_path', …
      • location : None = anywhere; otherwise a single space id (e.g. "west_indies")
"""

def queue_free_op(state, faction: str, op: str,
                  loc: str | None = None) -> None:
    state.setdefault("free_ops", []).append((faction.upper(), op, loc))

def pop_free_ops(state, faction: str):
    """Return and remove every queued op for *faction* (FIFO order)."""
    q = state.get("free_ops", [])
    taken = [t for t in q if t[0] == faction.upper()]
    state["free_ops"] = [t for t in q if t[0] != faction.upper()]
    return taken