#!/usr/bin/env python3
"""
Menu-driven CLI for Liberty or Death.

Run with:
    python -m lod_ai.interactive_cli
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Tuple

from lod_ai.engine import Engine
from lod_ai import rules_consts as RC
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


def _prompt_int(prompt: str, *, min_val: int | None = None, max_val: int | None = None, default: int | None = None) -> int:
    while True:
        raw = input(f"{prompt} ").strip()
        if raw == "" and default is not None:
            return default
        try:
            val = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if min_val is not None and val < min_val:
            print(f"Value must be at least {min_val}.")
            continue
        if max_val is not None and val > max_val:
            print(f"Value must be at most {max_val}.")
            continue
        return val


def _prompt_yes_no(prompt: str, *, default: bool | None = None) -> bool:
    suffix = " [y/n]" if default is None else (" [Y/n]" if default else " [y/N]")
    while True:
        raw = input(f"{prompt}{suffix} ").strip().lower()
        if raw == "" and default is not None:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please enter y or n.")


def _prompt_list(prompt: str, *, allow_empty: bool = False) -> List[str]:
    while True:
        raw = input(f"{prompt} ").strip()
        if raw == "" and allow_empty:
            return []
        items = [r.strip() for r in raw.split(",") if r.strip()]
        if not items and not allow_empty:
            print("Please enter at least one item.")
            continue
        return items


def _display_card(card: dict, engine: Engine) -> None:
    order = card.get("order") or card.get("order_icons") or card.get("order_list")
    preview = deepcopy(engine.state)
    elig_flags = preview.setdefault("eligible", {})
    for fac in preview.pop("eligible_next", set()):
        elig_flags[fac] = True
    for fac in preview.pop("ineligible_next", set()):
        elig_flags[fac] = False
    for fac in preview.pop("ineligible_through_next", set()):
        elig_flags[fac] = False
    eligible_now = [fac for fac, flag in elig_flags.items() if flag]
    print("\n====================================")
    print(f"Card {card.get('id')}: {card.get('title')}")
    print(f"Order: {order}")
    print(f"Currently eligible: {', '.join(eligible_now) if eligible_now else 'None'}")
    print("====================================")


def _choose_scenario() -> str:
    options = {
        1: ("1775", "Long"),
        2: ("1776", "Medium"),
        3: ("1778", "Short"),
    }
    print("Select a scenario:")
    for idx, (year, label) in options.items():
        print(f"  {idx}. {year} ({label})")
    choice = _prompt_int("Enter scenario number:", min_val=1, max_val=len(options))
    return options[choice][0]


def _choose_humans() -> List[str]:
    factions = {
        1: RC.BRITISH,
        2: RC.PATRIOTS,
        3: RC.FRENCH,
        4: RC.INDIANS,
    }
    num = _prompt_int("Number of human players (0-4):", min_val=0, max_val=4)
    humans: List[str] = []
    if num == 0:
        return humans
    print("Select human-controlled factions:")
    for idx, name in factions.items():
        print(f"  {idx}. {name}")
    while len(humans) < num:
        choice = _prompt_int(f"Choose faction #{len(humans)+1}:", min_val=1, max_val=4)
        fac = factions.get(choice)
        if fac in humans:
            print("Faction already chosen.")
            continue
        humans.append(fac)
    return humans


def _prompt_special(faction: str) -> Callable[[dict, dict], Any] | None:
    specials: Dict[str, List[Tuple[str, Callable[[dict, dict], Any]]]] = {}

    def wrap(func: Callable[[dict, dict], Any]) -> Callable[[dict, dict], Any]:
        return func

    specials[RC.BRITISH] = [
        ("Naval Pressure", lambda s, c: naval_pressure.execute(s, RC.BRITISH, c, city_choice=input("City to pull blockade from (blank for auto): ").strip() or None)),
        ("Skirmish", lambda s, c: skirmish.execute(s, RC.BRITISH, c, input("Space for Skirmish: ").strip(), option=_prompt_int("Option (1-3):", min_val=1, max_val=3))),
        ("Common Cause", lambda s, c: common_cause.execute(s, RC.BRITISH, c, _prompt_list("Spaces for Common Cause (comma-separated):"), destinations=_prompt_list("March destinations (optional, blank for none):", allow_empty=True) or None)),
    ]
    specials[RC.PATRIOTS] = [
        ("Partisans", lambda s, c: partisans.execute(s, RC.PATRIOTS, c, input("Space for Partisans: ").strip(), option=_prompt_int("Option (1-3):", min_val=1, max_val=3))),
        ("Persuasion", lambda s, c: persuasion.execute(s, RC.PATRIOTS, c, spaces=_prompt_list("Spaces for Persuasion (1-3, comma-separated):"))),
        ("Skirmish", lambda s, c: skirmish.execute(s, RC.PATRIOTS, c, input("Space for Skirmish: ").strip(), option=_prompt_int("Option (1-3):", min_val=1, max_val=3))),
    ]
    specials[RC.INDIANS] = [
        ("Plunder", lambda s, c: plunder.execute(s, RC.INDIANS, c, input("Province to Plunder: ").strip())),
        ("Trade", lambda s, c: trade.execute(s, RC.INDIANS, c, input("Province to Trade in: ").strip(), transfer=_prompt_int("Resource transfer (0=roll D3):", min_val=0))),
        ("War Path", lambda s, c: war_path.execute(s, RC.INDIANS, c, input("Province for War Path: ").strip(), option=_prompt_int("Option (1-3):", min_val=1, max_val=3))),
    ]
    specials[RC.FRENCH] = [
        ("Skirmish", lambda s, c: skirmish.execute(s, RC.FRENCH, c, input("Space for Skirmish: ").strip(), option=_prompt_int("Option (1-3):", min_val=1, max_val=3))),
        ("Naval Pressure", lambda s, c: naval_pressure.execute(s, RC.FRENCH, c, city_choice=input("City to receive Blockade: ").strip(), rearrange_map=None)),
        ("Préparer la Guerre", lambda s, c: preparer.execute(s, RC.FRENCH, c, choice=input("Choice (BLOCKADE/REGULARS/RESOURCES): ").strip())),
    ]

    options = specials.get(faction, [])
    if not options:
        return None
    print("Special Activities:")
    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")
    choice = _prompt_int("Select a Special (0 to skip):", min_val=0, max_val=len(options))
    if choice == 0:
        return None
    return options[choice - 1][1]


def _runner_battle(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    spaces = _prompt_list("Battle spaces (comma-separated):")
    return lambda s, c: battle.execute(s, faction, c, spaces, free=False)


def _runner_march(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    sources = _prompt_list("March sources (comma-separated):")
    dests = _prompt_list("March destinations (comma-separated):")
    escorts = _prompt_yes_no("Bring escorts?", default=False)
    return lambda s, c: march.execute(s, faction, c, sources, dests, bring_escorts=escorts, limited=limited)


def _runner_rally(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    selected = _prompt_list("Rally spaces (comma-separated):")
    build_fort = set(_prompt_list("Build Fort in (comma-separated, blank for none):", allow_empty=True))
    bulk_raw = _prompt_list("Bulk place entries (space:n, comma-separated, blank for none):", allow_empty=True)
    bulk_place: Dict[str, int] = {}
    for entry in bulk_raw:
        if ":" in entry:
            sp, num = entry.split(":", 1)
            try:
                bulk_place[sp.strip()] = int(num)
            except ValueError:
                continue
    promote = input("Promote space (blank for none): ").strip() or None
    return lambda s, c: rally.execute(
        s,
        faction,
        c,
        selected,
        build_fort=set(build_fort) if build_fort else set(),
        bulk_place=bulk_place or None,
        promote_space=promote,
        limited=limited,
    )


def _runner_gather(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    selected = _prompt_list("Gather Provinces (comma-separated):")
    build_village = set(_prompt_list("Build Village in (comma-separated, blank for none):", allow_empty=True))
    bulk_raw = _prompt_list("Bulk place entries (space:n, comma-separated, blank for none):", allow_empty=True)
    bulk_place: Dict[str, int] = {}
    for entry in bulk_raw:
        if ":" in entry:
            sp, num = entry.split(":", 1)
            try:
                bulk_place[sp.strip()] = int(num)
            except ValueError:
                continue
    move_raw = _prompt_list("Moves (src>dst:n, comma-separated, blank for none):", allow_empty=True)
    move_plan = []
    for entry in move_raw:
        if ">" in entry and ":" in entry:
            src_part, rest = entry.split(">", 1)
            dst_part, num = rest.split(":", 1)
            try:
                move_plan.append((src_part.strip(), dst_part.strip(), int(num)))
            except ValueError:
                continue
    return lambda s, c: gather.execute(
        s,
        faction,
        c,
        selected,
        build_village=set(build_village) if build_village else set(),
        bulk_place=bulk_place or None,
        move_plan=move_plan or None,
        limited=limited,
    )


def _runner_raid(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    selected = _prompt_list("Raid Provinces (comma-separated):")
    move_raw = _prompt_list("Move plan entries (src>dst, comma-separated, blank for none):", allow_empty=True)
    move_plan = []
    for entry in move_raw:
        if ">" in entry:
            src, dst = entry.split(">", 1)
            move_plan.append((src.strip(), dst.strip()))
    return lambda s, c: raid.execute(s, faction, c, selected, move_plan=move_plan or None)


def _runner_scout(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    src = input("Scout source: ").strip()
    dst = input("Scout destination: ").strip()
    n_wp = _prompt_int("War Parties to move:", min_val=1)
    n_reg = _prompt_int("British Regulars to move:", min_val=1)
    n_tory = _prompt_int("Tories to move (0+):", min_val=0)
    use_skirmish = _prompt_yes_no("Skirmish after Scout?", default=False)
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


def _runner_muster(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    if faction == RC.BRITISH:
        selected = _prompt_list("Muster spaces (comma-separated):")
        reg_space = input("Space to receive Regulars: ").strip()
        reg_num = _prompt_int("Number of British Regulars to place (1-6):", min_val=1, max_val=6)
        tory_raw = _prompt_list("Tory placements (space:n, comma-separated, blank for none):", allow_empty=True)
        tory_plan: Dict[str, int] = {}
        for entry in tory_raw:
            if ":" in entry:
                sp, num = entry.split(":", 1)
                try:
                    tory_plan[sp.strip()] = int(num)
                except ValueError:
                    continue
        build_fort = _prompt_yes_no("Build a Fort?", default=False)
        reward_levels = 0 if build_fort else _prompt_int("Reward Loyalty levels (0-2):", min_val=0, max_val=2, default=0)
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
    # French muster
    space = input("City/Colony to Muster in: ").strip()
    return lambda s, c: muster.execute(s, faction, c, [space])


def _runner_garrison(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    moves = _prompt_int("Number of Garrison moves to enter:", min_val=1)
    move_map: Dict[str, Dict[str, int]] = {}
    for idx in range(moves):
        print(f"Move #{idx+1}:")
        src = input("  Source City: ").strip()
        dst = input("  Destination City: ").strip()
        qty = _prompt_int("  Regulars to move:", min_val=1)
        move_map.setdefault(src, {})[dst] = qty
    return lambda s, c: garrison.execute(s, faction, c, move_map, limited=limited)


def _runner_rabble(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    selected = _prompt_list("Rabble-Rousing spaces (comma-separated):")
    return lambda s, c: rabble_rousing.execute(s, faction, c, selected, limited=limited)


def _runner_agent_mobilization(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    province = input("Province for Agent Mobilization: ").strip()
    place_continental = _prompt_yes_no("Place Continental instead of Militia?", default=False)
    return lambda s, c: french_agent_mobilization.execute(s, faction, c, province, place_continental=place_continental)


def _runner_hortelez(faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    pay = _prompt_int("Resources to pay (>=1):", min_val=1)
    return lambda s, c: hortelez.execute(s, faction, c, pay)


def _command_runner_for(faction: str, engine: Engine, limited: bool) -> Callable[[dict, dict], Any]:
    toa_played = bool(engine.state.get("toa_played"))
    options: List[Tuple[str, Callable[[str, bool], Callable[[dict, dict], Any]]]] = []

    if faction == RC.BRITISH:
        options = [
            ("Muster", _runner_muster),
            ("Garrison", _runner_garrison),
            ("March", _runner_march),
            ("Battle", _runner_battle),
        ]
    elif faction == RC.PATRIOTS:
        options = [
            ("Rally", _runner_rally),
            ("March", _runner_march),
            ("Battle", _runner_battle),
            ("Rabble-Rousing", _runner_rabble),
        ]
    elif faction == RC.INDIANS:
        options = [
            ("Gather", _runner_gather),
            ("March", _runner_march),
            ("Scout", _runner_scout),
            ("Raid", _runner_raid),
        ]
    elif faction == RC.FRENCH:
        if not toa_played:
            options = [
                ("French Agent Mobilization", _runner_agent_mobilization),
                ("Hortelez", _runner_hortelez),
            ]
        else:
            options = [
                ("Hortelez", _runner_hortelez),
                ("Muster", _runner_muster),
                ("March", _runner_march),
                ("Battle", _runner_battle),
            ]

    if not options:
        raise ValueError(f"No commands defined for {faction}")

    print("Commands:")
    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")
    choice = _prompt_int("Select Command:", min_val=1, max_val=len(options))
    runner_factory = options[choice - 1][1]
    return runner_factory(faction, limited)


def _human_decider(faction: str, card: dict, allowed: Dict[str, Any], engine: Engine) -> Tuple[dict, bool, dict | None, dict | None]:
    """Interactive handler for a human-controlled faction."""
    while True:
        print(f"\n{faction} turn. Allowed actions: {', '.join(sorted(allowed['actions']))}")
        opts = []
        if "pass" in allowed["actions"]:
            opts.append("P) Pass")
        if "event" in allowed["actions"] and allowed.get("event_allowed", False):
            opts.append("E) Event")
        if "command" in allowed["actions"]:
            opts.append("C) Command" + (" (Limited)" if allowed.get("limited_only") else ""))
        print(" | ".join(opts))
        choice = input("Choose action: ").strip().upper()
        if choice == "P":
            return {"action": "pass", "used_special": False}, True, None, None
        if choice == "E" and "event" in allowed["actions"] and allowed.get("event_allowed", False):
            runner = lambda s, c: engine.handle_event(faction, card, state=s)
        elif choice == "C" and "command" in allowed["actions"]:
            try:
                command_runner = _command_runner_for(faction, engine, allowed.get("limited_only", False))
            except ValueError as exc:
                print(exc)
                continue
            special_runner: Callable[[dict, dict], Any] | None = None
            if allowed.get("special_allowed", False) and not allowed.get("limited_only", False):
                if _prompt_yes_no("Add a Special Activity?", default=False):
                    special_runner = _prompt_special(faction)

            def _runner(state: dict, ctx: dict) -> Any:
                result = command_runner(state, ctx)
                if special_runner:
                    special_runner(state, ctx)
                return result

            runner = _runner
        else:
            print("Invalid choice.")
            continue

        try:
            result, legal, sim_state, sim_ctx = engine.simulate_action(faction, card, allowed, runner)
        except Exception as exc:  # noqa: BLE001
            print(f"Action failed: {exc}")
            continue

        if legal:
            return result, True, sim_state, sim_ctx
        print("That action was not legal for this slot. Please choose again.")


def main() -> None:
    print("Liberty or Death — Interactive CLI")
    scenario = _choose_scenario()
    human_factions = _choose_humans()

    engine = Engine()
    engine.setup_scenario(scenario)
    engine.set_human_factions(human_factions)

    print("\nGame start!")
    while True:
        card = engine.draw_card()
        if not card:
            print("No more cards in deck. Game over.")
            break
        _display_card(card, engine)
        engine.play_card(card, human_decider=_human_decider)

    print("Thanks for playing!")


if __name__ == "__main__":
    main()
