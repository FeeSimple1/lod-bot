from lod_ai.rules_consts import MAX_RESOURCES, MIN_RESOURCES

def clamp_all(state):
    """Clamp every faction’s Resources to the 0–MAX_RESOURCES band."""
    res_map = state.setdefault("resources", {})
    for fac, val in list(res_map.items()):
        res_map[fac] = max(MIN_RESOURCES, min(MAX_RESOURCES, val))

def add(state, faction, n):
    res = state.setdefault("resources", {})
    res[faction] = max(MIN_RESOURCES, min(MAX_RESOURCES, res.get(faction, 0) + n))

def spend(state, faction, n, *, ignore_free: bool = False):
    res = state.setdefault("resources", {})
    if state.get("bs_free") and not ignore_free:
        return
    if res.get(faction, 0) < n:
        raise ValueError(f"{faction} cannot afford {n} Resources")
    res[faction] = max(MIN_RESOURCES, res.get(faction, 0) - n)

def can_afford(state, faction, n, *, ignore_free: bool = False) -> bool:
    """Return True if the faction has ≥ n Resources."""
    if state.get("bs_free") and not ignore_free:
        return True
    return state["resources"][faction] >= n
