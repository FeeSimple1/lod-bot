"""Current leader identity and location, including a leader held in Available."""
from lod_ai import rules_consts as C
from lod_ai.leaders import leader_location

(WASHINGTON, ROCHAMBEAU, LAUZUN, GAGE, HOWE, CLINTON,
 BRANT, CORNPLANTER, DRAGGING_CANOE) = C.LEADERS

FACTION_LEADERS = {
    C.BRITISH: (GAGE, HOWE, CLINTON),
    C.PATRIOTS: (WASHINGTON,),
    C.FRENCH: (ROCHAMBEAU, LAUZUN),
    C.INDIANS: (BRANT, CORNPLANTER, DRAGGING_CANOE),
}


def current_leader(state, faction):
    candidates = FACTION_LEADERS[faction]
    leaders = state.setdefault("leaders", {})
    # Read actual map placement first for compatibility with Event handlers.
    current = next((lid for lid in candidates if leader_location(state, lid)), None)
    current = current or state.get("active_leaders", {}).get(faction)
    legacy = leaders.get(faction)
    if current is None and legacy in candidates:
        current = legacy
    if current is None:
        # Scenario starting leaders remain current even when all pieces have
        # left the map. Persist identity before any later redeployment.
        scenario = str(state.get("scenario", "1775"))
        if faction == C.BRITISH:
            current = CLINTON if "1778" in scenario else HOWE if "1776" in scenario else GAGE
        elif faction == C.INDIANS:
            current = CORNPLANTER if "1778" in scenario else BRANT
        else:
            current = candidates[0]
    state.setdefault("active_leaders", {})[faction] = current
    return current


def set_location(state, leader, destination):
    destination = destination if destination in state.get("spaces", {}) else None
    leaders = state.setdefault("leaders", {})
    for key, value in list(leaders.items()):
        if value == leader and key in state.get("spaces", {}):
            leaders.pop(key)
    leaders[leader] = destination
    if "leader_locs" in state:
        state["leader_locs"][leader] = destination or "Available"
    for sp in state.get("spaces", {}).values():
        sp.pop(leader, None)


def change(state, faction):
    old = current_leader(state, faction)
    new = C.LEADER_CHAIN.get(old)
    if not new:
        return None
    destination = leader_location(state, old)
    set_location(state, old, None)
    set_location(state, new, destination)
    state["active_leaders"][faction] = new
    if faction in state["leaders"]:  # tolerated legacy input
        state["leaders"][faction] = new
    return old, new
