"""
lod_ai.leaders
==============
Implements the nine Leader Capabilities on Reference Card #110
(card #110 is a reference, not an Event).  Each capability is
registered to run at a specific **hook** such as "pre_battle",
"pre_skirmish", etc.

The engine (or a command resolver) should call
    apply_leader_modifiers(state, faction, hook, ctx)
right before executing the gameplay step for that hook.

state["leaders"] must be structured as:
    {
        "BRITISH": ["Howe", "Clinton"],
        "PATRIOTS": ["Washington"],
        …
    }
"""

from typing import Dict, Callable, Any

from lod_ai.map import adjacency as map_adj

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
State   = Dict[str, Any]
Context = Dict[str, Any]
Modifier = Callable[[State, Context], None]

# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------
_LEADER_REGISTRY: Dict[str, Dict[str, Modifier]] = {}


def _register(name: str, hook: str) -> Callable[[Modifier], Modifier]:
    """Decorator registering *func* as a modifier for *name* at *hook*."""
    def decorator(func: Modifier) -> Modifier:
        _LEADER_REGISTRY.setdefault(name, {})[hook] = func
        return func
    return decorator


# ---------------------------------------------------------------------------
#  PATRIOTS
# ---------------------------------------------------------------------------
@_register("Washington", "pre_battle")
def _washington(state: State, ctx: Context) -> None:
    """Double Win-the-Day shift; –1 Defender Loss when Rebellion defends."""
    ctx["washington_double_win"] = True
    ctx["defender_loss_mod"] = ctx.get("defender_loss_mod", 0) - 1


# ---------------------------------------------------------------------------
#  FRENCH
# ---------------------------------------------------------------------------
@_register("Rochambeau", "pre_command")
def _rochambeau(state: State, ctx: Context) -> None:
    """French may March/Battle with Patriot Command at 0 cost."""
    ctx["rochambeau_free_with_pats"] = True


@_register("Lauzun", "pre_battle")
def _lauzun(state: State, ctx: Context) -> None:
    """+1 Defender Loss when French are attacking."""
    ctx["attacker_defender_loss_bonus"] = ctx.get("attacker_defender_loss_bonus", 0) + 1


# ---------------------------------------------------------------------------
#  BRITISH
# ---------------------------------------------------------------------------
@_register("Gage", "pre_reward_loyalty")
def _gage(state: State, ctx: Context) -> None:
    """First shift of Reward Loyalty in the space is free."""
    ctx["reward_loyalty_free"] = True


@_register("Howe", "pre_special_activity")
def _howe(state: State, ctx: Context) -> None:
    """Lower FNI by 1 before executing any British SA."""
    fni = state.get("fni", 0)
    if fni > 0:
        state["fni"] = fni - 1
        ctx["howe_lowered_fni"] = True


@_register("Clinton", "pre_skirmish")
def _clinton(state: State, ctx: Context) -> None:
    """Skirmish removes one extra Militia in the space."""
    ctx["skirmish_extra_militia"] = ctx.get("skirmish_extra_militia", 0) + 1


# ---------------------------------------------------------------------------
#  INDIANS
# ---------------------------------------------------------------------------
@_register("Brant", "pre_war_path")
def _brant(state: State, ctx: Context) -> None:
    """War Path removes one extra Militia in the space."""
    ctx["war_path_extra_militia"] = ctx.get("war_path_extra_militia", 0) + 1


@_register("Cornplanter", "pre_gather")
def _cornplanter(state: State, ctx: Context) -> None:
    """Gather builds a Village for only 1 War Party in the space."""
    ctx["village_cost_war_parties"] = 1


@_register("Dragging Canoe", "pre_raid")
def _dragging_canoe(state: State, ctx: Context) -> None:
    """Raid may move 1 extra space if it originated here."""
    ctx["raid_extra_range"] = 1


# ---------------------------------------------------------------------------
#  Public helper
# ---------------------------------------------------------------------------
def apply_leader_modifiers(state: State, faction: str, hook: str, ctx: Context) -> Context:
    """
    Run all leader modifiers for *faction* at *hook* and return the mutated ctx.
    The engine decides which hook to call based on the action being executed.
    """
    for leader in state.get("leaders", {}).get(faction, []):
        modifier = _LEADER_REGISTRY.get(leader, {}).get(hook)
        if modifier:
            modifier(state, ctx)
    return ctx


_LEADER_ALIASES = {
    "WASHINGTON": {"WASHINGTON", "LEADER_WASHINGTON"},
    "ROCHAMBEAU": {"ROCHAMBEAU", "LEADER_ROCHAMBEAU"},
    "LAUZUN": {"LAUZUN", "LEADER_LAUZUN"},
    "GAGE": {"GAGE", "LEADER_GAGE"},
    "HOWE": {"HOWE", "LEADER_HOWE"},
    "CLINTON": {"CLINTON", "LEADER_CLINTON"},
    "BRANT": {"BRANT", "LEADER_BRANT"},
    "CORNPLANTER": {"CORNPLANTER", "LEADER_CORNPLANTER"},
    "DRAGGING_CANOE": {"DRAGGING_CANOE", "LEADER_DRAGGING_CANOE"},
}


def _leader_keys(leader_id: str) -> set[str]:
    base = leader_id.replace("LEADER_", "")
    return _LEADER_ALIASES.get(base, {leader_id, base})


def leader_location(state: State, leader_id: str) -> str | None:
    """
    Best-effort lookup for the current location of *leader_id*.
    Supports either state['leader_locs'] or state['leaders'] storing locations.
    """
    valid_spaces = set(map_adj.all_space_ids())
    for key in _leader_keys(leader_id):
        # explicit location map
        loc = state.get("leader_locs", {}).get(key)
        if isinstance(loc, str) and loc in valid_spaces:
            return loc
        # scenario-style leaders dict mapping leader -> location
        loc = state.get("leaders", {}).get(key)
        if isinstance(loc, str) and loc in valid_spaces:
            return loc
    # fall back to scanning spaces for leader token
    for key in _leader_keys(leader_id):
        for sid, sp in state.get("spaces", {}).items():
            if sp.get(key, 0):
                return sid
            if sp.get("leader") == key:
                return sid
    return None
