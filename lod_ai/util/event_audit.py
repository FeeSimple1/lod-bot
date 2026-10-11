"""Evidence for §8.3.3 decisions, separate from contingent Battle outcomes.

Free Commands belong to event resolution (§5.3), so the handler boundary is
not necessarily the event boundary. Random Spaces rolls are target selection,
not stochastic combat outcomes, and deliberately do not exempt a net shift.
"""
from lod_ai import rules_consts as C
from lod_ai.map.adjacency import population
from lod_ai.util.naval import effective_population


def support_difference(state):
    total = 0
    for sid, level in state.get("support", {}).items():
        pop = population(sid)
        total += level * (effective_population(state, sid, pop)
                          if level > 0 else pop)
    return total


def favors_enemy(faction, before, after):
    return ((faction in (C.BRITISH, C.INDIANS) and after < before)
            or (faction in (C.PATRIOTS, C.FRENCH) and after > before))


def record_choice(state, faction, card, before, dice_before, preview, *, battles_before=None):
    """Record independent preview measurements and the actual partial result."""
    if battles_before is None:
        battles_before = state.get("_battle_commands_executed", 0)
    entry = {
        "faction": faction, "card": int(card.get("id", 0)),
        "d_before": before, "d_after": support_difference(state),
        "battle_dice_before": dice_before,
        "battle_dice": state.get("_battle_dice_rolled", 0) - dice_before,
        "battle_commands_before": battles_before,
        "battle_commands": state.get("_battle_commands_executed", 0) - battles_before,
        "complete": not bool(state.get("free_ops") or state.get("free_op_followups")),
        "preview": dict(preview) if preview is not None else None,
    }
    state.setdefault("event_choice_audit", []).append(entry)


def complete_choices(state):
    """Called only after all of the event's queued free operations resolve."""
    if state.get("free_ops") or state.get("free_op_followups"):
        return
    for entry in state.get("event_choice_audit", []):
        if entry.get("complete") is False:
            entry["d_after"] = support_difference(state)
            entry["battle_dice"] = (state.get("_battle_dice_rolled", 0)
                                    - entry["battle_dice_before"])
            if "battle_commands_before" in entry:
                entry["battle_commands"] = (state.get("_battle_commands_executed", 0)
                                             - entry["battle_commands_before"])
            entry["complete"] = True
