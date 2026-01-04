#!/usr/bin/env python3
"""
Menu-driven CLI for Liberty or Death.

All selections are presented as numbered menus (spaces, actions, counts).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Tuple

from lod_ai import rules_consts as RC
from lod_ai.cli_utils import choose_count, choose_multiple, choose_one
from lod_ai.engine import Engine
from lod_ai.map import adjacency as map_adj
from lod_ai.state.setup_state import build_state

from lod_ai.commands import (
    march,
    rally,
    battle,
    gather,
    muster,
    scout,
    raid,
    garrison,
    rabble_rousing,
    french_agent_mobilization,
    hortelez,
)
from lod_ai.special_activities import (
    naval_pressure,
    common_cause,
    partisans,
    persuasion,
    plunder,
    preparer,
    skirmish,
    trade,
    war_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _space_options(state: Dict[str, Any], filter_fn: Callable[[str, Dict[str, int]], bool] | None = None) -> List[Tuple[str, str]]:
    options: List[Tuple[str, str]] = []
    for sid in sorted(state.get("spaces", {})):
        sp = state["spaces"][sid]
        if filter_fn and not filter_fn(sid, sp):
            continue
        options.append((sid, sid))
    return options


def _friendly_tags(faction: str) -> set[str]:
    return {
        RC.BRITISH: {RC.REGULAR_BRI, RC.TORY, RC.FORT_BRI},
        RC.PATRIOTS: {RC.REGULAR_PAT, RC.MILITIA_A, RC.MILITIA_U, RC.FORT_PAT, RC.REGULAR_FRE},
        RC.FRENCH: {RC.REGULAR_FRE},
        RC.INDIANS: {RC.WARPARTY_A, RC.WARPARTY_U, RC.VILLAGE},
    }.get(faction, set())


def _battle_candidates(state: Dict[str, Any], faction: str) -> List[str]:
    friendly = _friendly_tags(faction)
    candidates = []
    for sid, sp in state.get("spaces", {}).items():
        friendly_count = sum(v for k, v in sp.items() if k in friendly)
        enemy_count = sum(v for k, v in sp.items() if k not in friendly and isinstance(v, int) and v > 0)
        if friendly_count > 0 and enemy_count > 0:
            candidates.append(sid)
    return sorted(candidates)


def _movable_sources(state: Dict[str, Any], faction: str, bring_escorts: bool = False) -> Dict[str, Dict[str, int]]:
    tags = {
        RC.BRITISH: [RC.REGULAR_BRI, RC.TORY, RC.WARPARTY_U, RC.WARPARTY_A] if bring_escorts else [RC.REGULAR_BRI],
        RC.PATRIOTS: [RC.REGULAR_PAT, RC.MILITIA_U, RC.MILITIA_A, RC.WARPARTY_U, RC.WARPARTY_A] + ([RC.REGULAR_FRE] if bring_escorts else []),
        RC.INDIANS: [RC.WARPARTY_U, RC.WARPARTY_A],
        RC.FRENCH: [RC.REGULAR_FRE] + ([RC.REGULAR_PAT] if bring_escorts else []),
    }[faction]
    sources: Dict[str, Dict[str, int]] = {}
    for sid, sp in state.get("spaces", {}).items():
        counts = {tag: sp.get(tag, 0) for tag in tags if sp.get(tag, 0) > 0}
        if counts:
            sources[sid] = counts
    return sources


def _display_cards(engine: Engine, current: Dict[str, Any]) -> None:
    upcoming = engine.state.get("upcoming_card")
    print("\n================ CURRENT CARD ================")
    print(f"{current.get('id')}: {current.get('title')} | Order: {current.get('order') or current.get('order_icons')}")
    if current.get("winter_quarters"):
        print("Winter Quarters")
    if upcoming:
        print("---------------- UPCOMING ----------------")
        print(f"{upcoming.get('id')}: {upcoming.get('title')} | Order: {upcoming.get('order') or upcoming.get('order_icons')}")
        if upcoming.get("winter_quarters"):
            print("Winter Quarters")
    print("=============================================")


# ---------------------------------------------------------------------------
# Command wizards
# ---------------------------------------------------------------------------

def _march_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    bring = choose_one("Bring escorts?", [("No", False), ("Yes", True)])
    sources = _movable_sources(engine.state, faction, bring_escorts=bring)
    if not sources:
        raise ValueError("No pieces available to March.")
    dest_options = set()
    for src in sources:
        for dst in map_adj.all_space_ids():
            if map_adj.is_adjacent(src, dst):
                if faction == RC.INDIANS and map_adj.space_type(dst) == "City":
                    continue
                dest_options.add(dst)
    if not dest_options:
        raise ValueError("No legal destinations.")
    dests = choose_multiple(
        "Select March destinations:",
        [(d, d) for d in sorted(dest_options)],
        min_sel=1,
        max_sel=1 if limited else None,
    )
    move_plan: List[Dict[str, Any]] = []
    for dest in dests:
        origin_candidates = [s for s in sources if map_adj.is_adjacent(s, dest)]
        origins = choose_multiple(
            f"Select origins marching to {dest}:",
            [(o, o) for o in origin_candidates],
            min_sel=1,
        )
        for origin in origins:
            pieces = {}
            for tag, available in sources[origin].items():
                count = choose_count(f"Move how many {tag} from {origin} to {dest}?", min_val=0, max_val=available)
                if count:
                    pieces[tag] = count
            if pieces:
                move_plan.append({"src": origin, "dst": dest, "pieces": pieces})
    if not move_plan:
        raise ValueError("March must move at least one piece.")

    return lambda s, c: march.execute(
        s,
        faction,
        c,
        [],
        dests,
        bring_escorts=bring,
        limited=limited,
        move_plan=move_plan,
    )


def _battle_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    candidates = _battle_candidates(engine.state, faction)
    if not candidates:
        raise ValueError("No legal Battle spaces.")
    spaces = choose_multiple(
        "Select Battle spaces:",
        [(s, s) for s in candidates],
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: battle.execute(s, faction, c, spaces=spaces, free=False)


def _rally_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state, lambda sid, _sp: engine.state.get("support", {}).get(sid, 0) < RC.ACTIVE_SUPPORT)
    if not options:
        raise ValueError("No spaces available for Rally.")
    selected = choose_multiple(
        "Select Rally spaces:",
        options,
        min_sel=1,
        max_sel=1 if limited else None,
    )
    build_fort = choose_one("Build a Fort in any selected space?", [("No", False), ("Yes", True)])
    build_set = set(selected) if build_fort else set()
    return lambda s, c: rally.execute(
        s,
        faction,
        c,
        selected,
        build_fort=build_set if build_set else None,
        limited=limited,
    )


def _gather_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state)
    selected = choose_multiple(
        "Select Gather Provinces:",
        options,
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: gather.execute(s, faction, c, selected, limited=limited)


def _muster_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state)
    if faction == RC.BRITISH:
        selected = choose_multiple(
            "Select Muster spaces:",
            options,
            min_sel=1,
            max_sel=1 if limited else None,
        )
        reg_space = choose_one("Place Regulars in which space?", [(s, s) for s in selected])
        available_regs = engine.state["available"].get(RC.REGULAR_BRI, 0)
        reg_num = choose_count("How many British Regulars to place? (max 6)", min_val=1, max_val=min(6, available_regs))
        tory_plan: Dict[str, int] = {}
        for sp in selected:
            max_tory = 2
            count = choose_count(f"Tories to place in {sp} (0-{max_tory}):", min_val=0, max_val=max_tory)
            if count:
                tory_plan[sp] = count
        fort_or_loyalty = choose_one(
            "Fort or Reward Loyalty?",
            [("None", "none"), ("Build Fort", "fort"), ("Reward Loyalty", "loyalty")],
        )
        reward_levels = 0
        build_fort = False
        if fort_or_loyalty == "fort":
            build_fort = True
        elif fort_or_loyalty == "loyalty":
            reward_levels = choose_count("Reward Loyalty levels (0-2):", min_val=0, max_val=2)
        return lambda s, c: muster.execute(
            s,
            faction,
            c,
            selected,
            regular_plan={"space": reg_space, "n": reg_num},
            tory_plan=tory_plan or None,
            build_fort=build_fort,
            reward_levels=reward_levels,
        )
    else:
        selected = [choose_one("Select City/Colony for French Muster:", options)]
        return lambda s, c: muster.execute(s, faction, c, selected)


def _scout_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state, lambda sid, sp: sp.get(RC.WARPARTY_U, 0) + sp.get(RC.WARPARTY_A, 0) > 0)
    src = choose_one("Select Scout source:", options)
    dest_options = _space_options(engine.state, lambda sid, _sp: map_adj.is_adjacent(src, sid))
    dst = choose_one("Select Scout destination:", dest_options)
    wp_avail = engine.state["spaces"][src].get(RC.WARPARTY_U, 0) + engine.state["spaces"][src].get(RC.WARPARTY_A, 0)
    n_wp = choose_count("War Parties to move:", min_val=1, max_val=wp_avail)
    n_reg = choose_count("British Regulars to move:", min_val=0, max_val=engine.state["spaces"][src].get(RC.REGULAR_BRI, 0))
    n_tory = choose_count("Tories to move:", min_val=0, max_val=engine.state["spaces"][src].get(RC.TORY, 0))
    use_skirmish = choose_one("Skirmish after Scout?", [("No", False), ("Yes", True)])
    return lambda s, c: scout.execute(
        s,
        faction,
        c,
        src,
        dst,
        n_warparties=n_wp,
        n_regulars=n_reg,
        n_tories=n_tory,
        skirmish=use_skirmish,
    )


def _raid_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state, lambda sid, sp: sp.get(RC.WARPARTY_A, 0) + sp.get(RC.WARPARTY_U, 0) > 0)
    selected = choose_multiple(
        "Select Raid Provinces:",
        options,
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: raid.execute(s, faction, c, selected, move_plan=None)


def _garrison_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    src_options = _space_options(engine.state, lambda sid, sp: sp.get(RC.REGULAR_BRI, 0) > 0)
    if not src_options:
        raise ValueError("No Regulars available for Garrison.")
    moves: Dict[str, Dict[str, int]] = {}
    max_moves = 1 if limited else 3
    num_moves = choose_count("Number of Garrison moves:", min_val=1, max_val=max_moves)
    for idx in range(num_moves):
        src = choose_one(f"Garrison move {idx+1} - Source City:", src_options)
        dst = choose_one(f"Garrison move {idx+1} - Destination City:", _space_options(engine.state))
        max_reg = engine.state["spaces"][src].get(RC.REGULAR_BRI, 0)
        qty = choose_count(f"Regulars to move from {src} to {dst}:", min_val=1, max_val=max_reg)
        moves.setdefault(src, {})[dst] = qty
    return lambda s, c: garrison.execute(s, faction, c, moves, limited=limited)


def _rabble_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state)
    selected = choose_multiple(
        "Select Rabble-Rousing spaces:",
        options,
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: rabble_rousing.execute(s, faction, c, selected, limited=limited)


def _agent_mobilization_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    province = choose_one("Select Province for Agent Mobilization:", _space_options(engine.state))
    place_continental = choose_one("Place Continental instead of Militia?", [("No", False), ("Yes", True)])
    return lambda s, c: french_agent_mobilization.execute(s, faction, c, province, place_continental=place_continental)


def _hortelez_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    max_pay = max(1, engine.state["resources"].get(faction, 0))
    pay = choose_count("Resources to pay (>=1):", min_val=1, max_val=max_pay)
    return lambda s, c: hortelez.execute(s, faction, c, pay)


# ---------------------------------------------------------------------------
# Special activities
# ---------------------------------------------------------------------------

def _special_wizard(state: Dict[str, Any], faction: str) -> Callable[[dict, dict], Any] | None:
    options: List[Tuple[str, Callable[[dict, dict], Any] | None]] = []

    spaces_all = _space_options(state)
    if faction == RC.BRITISH:
        options.extend([
            ("Naval Pressure", lambda s, c: naval_pressure.execute(s, RC.BRITISH, c, city_choice=choose_one("Select City for Naval Pressure:", spaces_all))),
            ("Skirmish", lambda s, c: skirmish.execute(s, RC.BRITISH, c, choose_one("Skirmish space:", spaces_all), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3))),
            ("Common Cause", lambda s, c: common_cause.execute(
                s,
                RC.BRITISH,
                c,
                [v for v in choose_multiple("Spaces for Common Cause:", spaces_all, min_sel=1)],
            )),
        ])
    elif faction == RC.PATRIOTS:
        options.extend([
            ("Partisans", lambda s, c: partisans.execute(s, RC.PATRIOTS, c, choose_one("Partisans space:", spaces_all), option=choose_count("Option (1-3):", min_val=1, max_val=3))),
            ("Persuasion", lambda s, c: persuasion.execute(s, RC.PATRIOTS, c, spaces=[v for v in choose_multiple("Spaces for Persuasion (up to 3):", spaces_all, min_sel=1, max_sel=3)])),
            ("Skirmish", lambda s, c: skirmish.execute(s, RC.PATRIOTS, c, choose_one("Skirmish space:", spaces_all), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3))),
        ])
    elif faction == RC.INDIANS:
        options.extend([
            ("Plunder", lambda s, c: plunder.execute(s, RC.INDIANS, c, choose_one("Province to Plunder:", spaces_all))),
            ("Trade", lambda s, c: trade.execute(s, RC.INDIANS, c, choose_one("Province to Trade in:", spaces_all), transfer=choose_count("Resource transfer (0=roll D3):", min_val=0, max_val=3))),
            ("War Path", lambda s, c: war_path.execute(s, RC.INDIANS, c, choose_one("Province for War Path:", spaces_all), option=choose_count("Option (1-3):", min_val=1, max_val=3))),
        ])
    elif faction == RC.FRENCH:
        options.extend([
            ("Skirmish", lambda s, c: skirmish.execute(s, RC.FRENCH, c, choose_one("Skirmish space:", spaces_all), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3))),
            ("Naval Pressure", lambda s, c: naval_pressure.execute(s, RC.FRENCH, c, city_choice=choose_one("City to receive Blockade:", spaces_all), rearrange_map=None)),
            ("Préparer la Guerre", lambda s, c: preparer.execute(s, RC.FRENCH, c, choice=choose_one("Choose Préparer option:", [("BLOCKADE", "BLOCKADE"), ("REGULARS", "REGULARS"), ("RESOURCES", "RESOURCES")]))),
        ])

    if not options:
        return None

    options.append(("No Special Activity", None))
    choice = choose_one("Select a Special Activity:", options)
    return choice


# ---------------------------------------------------------------------------
# Action selection
# ---------------------------------------------------------------------------

def _command_runner_for(faction: str, engine: Engine, limited: bool) -> Callable[[dict, dict], Any]:
    toa_played = bool(engine.state.get("toa_played"))
    options: List[Tuple[str, Callable[[Engine, str, bool], Callable[[dict, dict], Any]]]] = []

    if faction == RC.BRITISH:
        options = [
            ("Muster", _muster_wizard),
            ("Garrison", _garrison_wizard),
            ("March", _march_wizard),
            ("Battle", _battle_wizard),
        ]
    elif faction == RC.PATRIOTS:
        options = [
            ("Rally", _rally_wizard),
            ("March", _march_wizard),
            ("Battle", _battle_wizard),
            ("Rabble-Rousing", _rabble_wizard),
        ]
    elif faction == RC.INDIANS:
        options = [
            ("Gather", _gather_wizard),
            ("March", _march_wizard),
            ("Scout", _scout_wizard),
            ("Raid", _raid_wizard),
        ]
    elif faction == RC.FRENCH:
        if not toa_played:
            options = [
                ("French Agent Mobilization", _agent_mobilization_wizard),
                ("Hortelez", _hortelez_wizard),
            ]
        else:
            options = [
                ("Hortelez", _hortelez_wizard),
                ("Muster", _muster_wizard),
                ("March", _march_wizard),
                ("Battle", _battle_wizard),
            ]

    runner_factory = choose_one("Select Command:", options)
    return runner_factory(engine, faction, limited)


def _human_decider(faction: str, card: dict, allowed: Dict[str, Any], engine: Engine) -> Tuple[dict, bool, dict | None, dict | None]:
    """Interactive handler for a human-controlled faction."""
    while True:
        actions = []
        if "pass" in allowed["actions"]:
            actions.append(("Pass", "pass"))
        if "event" in allowed["actions"] and allowed.get("event_allowed", False):
            actions.append(("Event", "event"))
        if "command" in allowed["actions"]:
            label = "Command (Limited)" if allowed.get("limited_only") else "Command"
            actions.append((label, "command"))

        choice = choose_one(f"\n{faction} turn. Choose action:", actions)

        if choice == "pass":
            return {"action": "pass", "used_special": False}, True, None, None

        if choice == "event":
            shaded = None
            if card.get("dual"):
                sides = []
                if card.get("unshaded_event"):
                    sides.append(("Unshaded", False))
                if card.get("shaded_event"):
                    sides.append(("Shaded", True))
                if len(sides) == 1:
                    shaded = sides[0][1]
                else:
                    shaded = choose_one("Select event side:", sides)
            runner = lambda s, c: engine.handle_event(faction, card, state=s, shaded=shaded)
        else:  # command
            try:
                command_runner = _command_runner_for(faction, engine, allowed.get("limited_only", False))
            except ValueError as exc:
                print(exc)
                continue

            special_runner: Callable[[dict, dict], Any] | None = None
            if allowed.get("special_allowed", False) and not allowed.get("limited_only", False):
                preview_state = deepcopy(engine.state)
                preview_ctx = deepcopy(engine.ctx)
                try:
                    command_runner(preview_state, preview_ctx)
                    special_runner = _special_wizard(preview_state, faction)
                except Exception as exc:  # noqa: BLE001
                    print(f"Unable to add Special Activity: {exc}")
                    special_runner = None

            def _runner(state: dict, ctx: dict) -> Any:
                result = command_runner(state, ctx)
                if special_runner:
                    special_runner(state, ctx)
                return result

            runner = _runner

        try:
            result, legal, sim_state, sim_ctx = engine.simulate_action(faction, card, allowed, runner)
        except Exception as exc:  # noqa: BLE001
            print(f"Action failed: {exc}")
            continue

        if legal:
            return result, True, sim_state, sim_ctx
        print("That action was not legal for this slot. Please choose again.")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _choose_scenario() -> Tuple[str, str]:
    options = [
        ("1775 Long", "1775"),
        ("1776 Medium", "1776"),
        ("1778 Short", "1778"),
    ]
    scenario = choose_one("Select a scenario:", options)
    deck_method = choose_one("Deck method:", [("Standard", "standard"), ("Period Events", "period")])
    return scenario, deck_method


def _choose_humans() -> List[str]:
    num = choose_count("Number of human players:", min_val=0, max_val=4, default=1)
    if num == 0:
        return []
    factions = [
        ("BRITISH", RC.BRITISH),
        ("PATRIOTS", RC.PATRIOTS),
        ("FRENCH", RC.FRENCH),
        ("INDIANS", RC.INDIANS),
    ]
    humans = choose_multiple(
        "Select human-controlled factions:",
        factions,
        min_sel=num,
        max_sel=num,
    )
    return humans


def _choose_seed() -> int:
    seeds = [(str(s), s) for s in (1, 2, 3, 4, 5)]
    seeds.append(("Random (based on time)", None))
    choice = choose_one("Select RNG seed:", seeds)
    if choice is None:
        import random

        return random.randint(1, 10_000)
    return int(choice)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    print("Liberty or Death — Interactive CLI")
    scenario, deck_method = _choose_scenario()
    seed = _choose_seed()
    human_factions = _choose_humans()

    initial_state = build_state(scenario, seed=seed, setup_method=deck_method)
    engine = Engine(initial_state=initial_state, use_cli=True)
    engine.set_human_factions(human_factions)

    print(f"\nGame start! (seed={seed}, method={deck_method})")
    while True:
        card = engine.draw_card()
        if not card:
            print("No more cards in deck. Game over.")
            break
        _display_cards(engine, card)
        engine.play_card(card, human_decider=_human_decider)

    print("Thanks for playing!")


if __name__ == "__main__":
    main()
