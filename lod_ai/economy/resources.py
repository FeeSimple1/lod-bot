MAX_RESOURCES = 50

def add(state, faction, n):
    state["resources"][faction] = min(
        MAX_RESOURCES, state["resources"][faction] + n
    )

def spend(state, faction, n):
    if state["resources"][faction] < n:
        raise ValueError(f"{faction} cannot afford {n} Resources")
    state["resources"][faction] -= n

def can_afford(state, faction, n) -> bool:
    """Return True if the faction has ≥ n Resources."""
    return state["resources"][faction] >= n
