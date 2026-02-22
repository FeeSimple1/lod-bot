#!/usr/bin/env python3
"""
Menu-driven CLI for Liberty or Death.

All selections are presented as numbered menus (spaces, actions, counts).
Upgraded with board state display, bot summaries, card display, crash/bug
reports, autosave, game stats tracking, legal move logging, and
meta-commands (status/history/victory/bug/quit) at every input prompt.
"""

from __future__ import annotations

import traceback
from collections import Counter
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

from lod_ai import rules_consts as RC
from lod_ai.cli_utils import choose_count, choose_multiple, choose_one, set_game_state
from lod_ai.cli_display import (
    display_board_state,
    display_card,
    display_event_choice,
    display_bot_summary,
    display_turn_context,
    display_game_end,
    display_game_report,
    display_setup_confirmation,
    display_winter_quarters_header,
    display_wq_phase,
    display_victory_margins,
    display_history,
    pause_for_player,
    _snapshot_state,
)
from lod_ai.engine import Engine
from lod_ai.map import adjacency as map_adj
from lod_ai.state.setup_state import build_state
from lod_ai.leaders import leader_location
from lod_ai.tools.state_serializer import (
    build_crash_report,
    build_autosave,
    build_game_report,
    save_report,
    serialize_state,
)

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
# Game stats accumulator
# ---------------------------------------------------------------------------

_ALL_FACTIONS = (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH)


def _new_game_stats(human_factions: set) -> Dict[str, Any]:
    """Create a fresh game stats accumulator."""
    faction_stats = {}
    for fac in _ALL_FACTIONS:
        faction_stats[fac] = {
            "is_human": fac in human_factions,
            "commands": Counter(),
            "events_played": [],
            "special_activities": Counter(),
            "passes": 0,
            "pass_reasons": Counter(),
        }
    return {
        "cards_played": 0,
        "wq_count": 0,
        "campaign_years": "",
        "winner": None,
        "victory_type": None,
        "wq_margins": [],
        "faction_stats": faction_stats,
    }


def _record_turn_stats(game_stats: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Parse the engine's _card_turn_log and accumulate stats."""
    card_turn_log = state.get("_card_turn_log", [])
    for entry in card_turn_log:
        faction = entry.get("faction")
        if faction not in _ALL_FACTIONS:
            continue
        fs = game_stats["faction_stats"][faction]
        action = entry.get("action")
        if action == "pass":
            fs["passes"] += 1
            reason = entry.get("pass_reason", "unknown")
            fs["pass_reasons"][reason] += 1
        elif action == "command":
            cmd_type = entry.get("command_type", "unknown")
            fs["commands"][cmd_type] += 1
            if entry.get("used_special"):
                # SA type tracked as command_meta if available
                fs["special_activities"]["(with command)"] += 1
        elif action == "event":
            card_id = entry.get("event_card_id")
            if card_id is not None:
                fs["events_played"].append(card_id)


def _record_wq_margins(game_stats: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Extract the latest victory check margins from history."""
    history = state.get("history", [])
    for entry in reversed(history[-30:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Victory Check" in msg and "BRI(" in msg:
            game_stats["wq_margins"].append(msg)
            break
    game_stats["wq_count"] += 1


def _detect_winner(game_stats: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Parse history for winner and victory type."""
    history = state.get("history", [])
    for entry in reversed(history[-40:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Winner:" in msg:
            game_stats["winner"] = msg
            if "Rule 7.3" in msg:
                game_stats["victory_type"] = "final_scoring"
            else:
                game_stats["victory_type"] = "victory_condition"
            break
        elif "Victory achieved" in msg:
            game_stats["winner"] = msg
            game_stats["victory_type"] = "victory_condition"
            break


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


def _log_wizard_filter(state: Dict[str, Any], command: str, total: int, shown: int,
                       filtered: List[Dict[str, str]]) -> None:
    """Record what a wizard filtered out."""
    state.setdefault("_cli_wizard_log", []).append({
        "command": command,
        "total_spaces": total,
        "shown_spaces": shown,
        "filtered_out": filtered,
    })


def _log_empty_menu(state: Dict[str, Any], faction: str, command: str) -> None:
    """Record when a wizard finds zero legal options."""
    state.setdefault("_cli_wizard_log", []).append({
        "command": command,
        "faction": faction,
        "no_legal_options": True,
    })
    print(f"  No legal options for {command} -- this may indicate a bug. Type 'bug' to report.")


# ---------------------------------------------------------------------------
# Command wizards
# ---------------------------------------------------------------------------

def _march_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    bring = choose_one("Bring escorts?", [("No", False), ("Yes", True)])
    sources = _movable_sources(engine.state, faction, bring_escorts=bring)
    if not sources:
        _log_empty_menu(engine.state, faction, "March")
        raise ValueError("No pieces available to March.")
    all_space_ids = map_adj.all_space_ids()
    dest_options = set()
    filtered_out = []
    for src in sources:
        for dst in all_space_ids:
            if map_adj.is_adjacent(src, dst):
                if faction == RC.INDIANS and map_adj.space_type(dst) == "City":
                    filtered_out.append({"space": dst, "reason": "Indians cannot march to City"})
                    continue
                dest_options.add(dst)
    _log_wizard_filter(engine.state, "March", len(all_space_ids), len(dest_options), filtered_out)
    if not dest_options:
        _log_empty_menu(engine.state, faction, "March (destinations)")
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
        _log_empty_menu(engine.state, faction, "Battle")
        raise ValueError("No legal Battle spaces.")
    _log_wizard_filter(engine.state, "Battle", len(engine.state.get("spaces", {})), len(candidates), [])
    spaces = choose_multiple(
        "Select Battle spaces:",
        [(s, s) for s in candidates],
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: battle.execute(s, faction, c, spaces=spaces, free=False)


def _rally_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    all_spaces = list(engine.state.get("spaces", {}).keys())
    filtered_out = []
    valid = []
    for sid in sorted(all_spaces):
        sup = engine.state.get("support", {}).get(sid, 0)
        if sup >= RC.ACTIVE_SUPPORT:
            filtered_out.append({"space": sid, "reason": f"already Active Support ({sup})"})
        else:
            valid.append((sid, sid))
    _log_wizard_filter(engine.state, "Rally", len(all_spaces), len(valid), filtered_out)
    if not valid:
        _log_empty_menu(engine.state, faction, "Rally")
        raise ValueError("No spaces available for Rally.")
    selected = choose_multiple(
        "Select Rally spaces:",
        valid,
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
    state = engine.state
    support_ok = {RC.NEUTRAL, RC.PASSIVE_SUPPORT, RC.PASSIVE_OPPOSITION}
    avail_wp = state.get("available", {}).get(RC.WARPARTY_U, 0)
    avail_villages = state.get("available", {}).get(RC.VILLAGE, 0)
    remaining_wp_on_map = {
        sid: sp.get(RC.WARPARTY_U, 0) + sp.get(RC.WARPARTY_A, 0)
        for sid, sp in state.get("spaces", {}).items()
    }

    def _has_adjacent_wp(prov: str) -> bool:
        return any(
            remaining_wp_on_map.get(src, 0) > 0 and map_adj.is_adjacent(src, prov)
            for src in state.get("spaces", {})
        )

    def _gather_choices_for(prov: str) -> List[str]:
        sp = state["spaces"][prov]
        if state.get("support", {}).get(prov, 0) not in support_ok:
            return []
        if prov == RC.WEST_INDIES_ID:
            return []
        options: List[str] = []
        base_total = sp.get(RC.VILLAGE, 0) + sp.get(RC.FORT_BRI, 0) + sp.get(RC.FORT_PAT, 0)
        wp_total = sp.get(RC.WARPARTY_U, 0) + sp.get(RC.WARPARTY_A, 0)
        if avail_wp > 0:
            options.append("place_one")
        if wp_total >= 2 and base_total < 2 and avail_villages > 0:
            options.append("build_village")
        if sp.get(RC.VILLAGE, 0) > 0 and avail_wp > 0:
            options.append("bulk_place")
        if _has_adjacent_wp(prov):
            options.append("move_plan")
        return options

    all_spaces = list(state.get("spaces", {}).keys())
    filtered_out = []
    province_options = []
    for sid in all_spaces:
        choices = _gather_choices_for(sid)
        if choices:
            province_options.append((sid, sid))
        else:
            sup = state.get("support", {}).get(sid, 0)
            if sup not in support_ok:
                filtered_out.append({"space": sid, "reason": f"support level {sup} not in {support_ok}"})
            elif sid == RC.WEST_INDIES_ID:
                filtered_out.append({"space": sid, "reason": "West Indies excluded"})
            else:
                filtered_out.append({"space": sid, "reason": "no available gather actions"})
    _log_wizard_filter(engine.state, "Gather", len(all_spaces), len(province_options), filtered_out)

    if not province_options:
        _log_empty_menu(engine.state, faction, "Gather")
        raise ValueError("No legal Provinces for Gather.")

    selected = choose_multiple(
        "Select Gather Provinces:",
        sorted(province_options),
        min_sel=1,
        max_sel=1 if limited else 4,
    )

    place_one: set[str] = set()
    build_village: set[str] = set()
    bulk_place: Dict[str, int] = {}
    move_plan: List[tuple[str, str, int]] = []

    remaining_available_wp = avail_wp
    remaining_available_villages = avail_villages

    for prov in selected:
        sp = state["spaces"][prov]
        base_total = sp.get(RC.VILLAGE, 0) + sp.get(RC.FORT_BRI, 0) + sp.get(RC.FORT_PAT, 0)
        wp_total = sp.get(RC.WARPARTY_U, 0) + sp.get(RC.WARPARTY_A, 0)
        choices = []
        if remaining_available_wp > 0:
            choices.append(("Place 1 War Party", "place_one"))
        if wp_total >= 2 and base_total < 2 and remaining_available_villages > 0:
            choices.append(("Build Village (replace 2 WP)", "build_village"))
        if sp.get(RC.VILLAGE, 0) > 0 and remaining_available_wp > 0:
            max_bulk = min(remaining_available_wp, sp.get(RC.VILLAGE, 0) + 1)
            if max_bulk > 0:
                choices.append(("Bulk place War Parties", ("bulk_place", max_bulk)))
        adj_sources = [
            sid for sid, total in remaining_wp_on_map.items()
            if total > 0 and map_adj.is_adjacent(sid, prov)
        ]
        if adj_sources:
            choices.append(("Move War Parties in", ("move_plan", adj_sources)))

        if not choices:
            raise ValueError(f"No legal Gather actions remain for {prov}.")

        choice = choose_one(f"Choose Gather action for {prov}:", choices)

        if choice == "place_one":
            place_one.add(prov)
            remaining_available_wp -= 1
        elif choice == "build_village":
            build_village.add(prov)
            remaining_available_villages -= 1
            remaining_wp_on_map[prov] = max(0, remaining_wp_on_map.get(prov, 0) - 2)
        elif isinstance(choice, tuple) and choice[0] == "bulk_place":
            max_bulk = choice[1]
            n_place = choose_count(
                f"How many War Parties to place in {prov}? (1-{max_bulk})",
                min_val=1,
                max_val=max_bulk,
            )
            bulk_place[prov] = n_place
            remaining_available_wp -= n_place
        elif isinstance(choice, tuple) and choice[0] == "move_plan":
            mp_sources = choice[1]
            selected_sources = choose_multiple(
                f"Select sources to move War Parties into {prov}:",
                [(s, s) for s in mp_sources],
                min_sel=1,
                max_sel=None,
            )
            for src in selected_sources:
                max_move = remaining_wp_on_map.get(src, 0)
                n_move = choose_count(
                    f"Move how many War Parties from {src} to {prov}?",
                    min_val=1,
                    max_val=max_move,
                )
                remaining_wp_on_map[src] -= n_move
                move_plan.append((src, prov, n_move))
        else:
            raise ValueError("Unknown Gather choice.")

    return lambda s, c: gather.execute(
        s,
        faction,
        c,
        selected,
        place_one=place_one or None,
        build_village=build_village or None,
        bulk_place=bulk_place or None,
        move_plan=move_plan or None,
        limited=limited,
    )


def _muster_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state)
    if not options:
        _log_empty_menu(engine.state, faction, "Muster")
        raise ValueError("No spaces available for Muster.")
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
    if not options:
        _log_empty_menu(engine.state, faction, "Scout")
        raise ValueError("No War Parties available for Scout.")
    src = choose_one("Select Scout source:", options)
    dest_options = _space_options(engine.state, lambda sid, _sp: map_adj.is_adjacent(src, sid))
    if not dest_options:
        raise ValueError("No adjacent destinations for Scout.")
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
    state = engine.state
    support_ok = {RC.ACTIVE_OPPOSITION, RC.PASSIVE_OPPOSITION}
    remaining_underground = {
        sid: sp.get(RC.WARPARTY_U, 0)
        for sid, sp in state.get("spaces", {}).items()
    }
    dragging_loc = leader_location(state, "LEADER_DRAGGING_CANOE")

    def _sources_for(dest: str) -> List[str]:
        sources_list: List[str] = []
        for sid, count in remaining_underground.items():
            if count <= 0:
                continue
            path = map_adj.shortest_path(sid, dest)
            distance = len(path) - 1 if path else None
            if distance == 1:
                sources_list.append(sid)
            elif dragging_loc and sid == dragging_loc and distance is not None and distance <= 2:
                sources_list.append(sid)
        return sources_list

    all_spaces = list(state.get("spaces", {}).keys())
    filtered_out = []
    valid_options = []
    for sid in sorted(all_spaces):
        sp = state["spaces"][sid]
        if sid == RC.WEST_INDIES_ID:
            filtered_out.append({"space": sid, "reason": "West Indies excluded"})
            continue
        sup = state.get("support", {}).get(sid, 0)
        if sup not in support_ok:
            filtered_out.append({"space": sid, "reason": f"support level {sup} not Opposition"})
            continue
        underground_here = remaining_underground.get(sid, 0) > 0
        if underground_here or bool(_sources_for(sid)):
            valid_options.append((sid, sid))
        else:
            filtered_out.append({"space": sid, "reason": "no underground WP here or adjacent"})
    _log_wizard_filter(state, "Raid", len(all_spaces), len(valid_options), filtered_out)

    if not valid_options:
        _log_empty_menu(state, faction, "Raid")
        raise ValueError("No legal Provinces for Raid.")

    selected = choose_multiple(
        "Select Raid Provinces:",
        valid_options,
        min_sel=1,
        max_sel=1 if limited else 3,
    )

    move_plan: List[tuple[str, str]] = []
    for dest in selected:
        underground_here = remaining_underground.get(dest, 0) > 0
        sources_list = _sources_for(dest)
        if not underground_here and not sources_list:
            raise ValueError(f"{dest} has no accessible Underground War Party.")

        should_move = False
        if underground_here:
            if sources_list:
                should_move = choose_one(f"Move an Underground War Party into {dest}?", [("No", False), ("Yes", True)])
            else:
                should_move = False
        else:
            should_move = True

        if should_move:
            src = choose_one(
                f"Select source for 1 Underground War Party into {dest}:",
                [(s, s) for s in sources_list],
            )
            move_plan.append((src, dest))
            remaining_underground[src] -= 1

    return lambda s, c: raid.execute(s, faction, c, selected, move_plan=move_plan or None)


def _garrison_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    all_spaces = list(engine.state.get("spaces", {}).keys())
    filtered_out = []
    src_options = []
    for sid in sorted(all_spaces):
        sp = engine.state["spaces"][sid]
        if sp.get(RC.REGULAR_BRI, 0) > 0:
            src_options.append((sid, sid))
        else:
            filtered_out.append({"space": sid, "reason": "no British Regulars"})
    _log_wizard_filter(engine.state, "Garrison", len(all_spaces), len(src_options), filtered_out)
    if not src_options:
        _log_empty_menu(engine.state, faction, "Garrison")
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
    state = engine.state
    all_spaces = list(state.get("spaces", {}).keys())
    filtered_out = []
    valid_options = []

    for sid in sorted(all_spaces):
        sp = state["spaces"][sid]
        ctrl = state.get("control", {}).get(sid)
        if ctrl != "REBELLION":
            filtered_out.append({"space": sid, "reason": f"control={ctrl}, not REBELLION"})
            continue
        has_patriot_piece = any(
            sp.get(tag, 0) > 0
            for tag in (RC.REGULAR_PAT, RC.MILITIA_A, RC.MILITIA_U, RC.FORT_PAT)
        )
        if has_patriot_piece or sp.get(RC.MILITIA_U, 0) > 0:
            valid_options.append((sid, sid))
        else:
            filtered_out.append({"space": sid, "reason": "no Patriot pieces despite REBELLION control"})

    _log_wizard_filter(state, "Rabble-Rousing", len(all_spaces), len(valid_options), filtered_out)
    if not valid_options:
        _log_empty_menu(state, faction, "Rabble-Rousing")
        raise ValueError("No eligible spaces for Rabble-Rousing.")
    selected = choose_multiple(
        "Select Rabble-Rousing spaces:",
        valid_options,
        min_sel=1,
        max_sel=1 if limited else None,
    )
    return lambda s, c: rabble_rousing.execute(s, faction, c, selected, limited=limited)


def _agent_mobilization_wizard(engine: Engine, faction: str, limited: bool) -> Callable[[dict, dict], Any]:
    options = _space_options(engine.state)
    if not options:
        _log_empty_menu(engine.state, faction, "Agent Mobilization")
        raise ValueError("No spaces available for Agent Mobilization.")
    province = choose_one("Select Province for Agent Mobilization:", options)
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
    sa_log = state.setdefault("_cli_sa_log", [])

    def _legal_space_list(sa_name: str, builder: Callable[[dict, dict, str], Any]) -> List[Tuple[str, str]]:
        legal: List[Tuple[str, str]] = []
        for sid, _ in _space_options(state):
            test_state = deepcopy(state)
            test_ctx: dict = {}
            try:
                builder(test_state, test_ctx, sid)
            except Exception as exc:  # noqa: BLE001
                sa_log.append({
                    "sa_name": sa_name,
                    "space": sid,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                })
                continue
            legal.append((sid, sid))
        return legal

    options: List[Tuple[str, Callable[[dict, dict], Any] | None]] = []

    if faction == RC.BRITISH:
        naval_spaces = _legal_space_list("Naval Pressure", lambda s, c, sid: naval_pressure.execute(s, RC.BRITISH, c, city_choice=sid))
        if naval_spaces:
            options.append((
                "Naval Pressure",
                lambda s, c: naval_pressure.execute(s, RC.BRITISH, c, city_choice=choose_one("Select City for Naval Pressure:", naval_spaces)),
            ))
        skirmish_spaces = _legal_space_list("Skirmish", lambda s, c, sid: skirmish.execute(s, RC.BRITISH, c, sid, option=1))
        if skirmish_spaces:
            options.append((
                "Skirmish",
                lambda s, c: skirmish.execute(s, RC.BRITISH, c, choose_one("Skirmish space:", skirmish_spaces), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3)),
            ))
        cc_spaces = _legal_space_list("Common Cause", lambda s, c, sid: common_cause.execute(s, RC.BRITISH, c, [sid]))
        if cc_spaces:
            options.append((
                "Common Cause",
                lambda s, c: common_cause.execute(
                    s,
                    RC.BRITISH,
                    c,
                    [v for v in choose_multiple("Spaces for Common Cause:", cc_spaces, min_sel=1)],
                ),
            ))
    elif faction == RC.PATRIOTS:
        part_spaces = _legal_space_list("Partisans", lambda s, c, sid: partisans.execute(s, RC.PATRIOTS, c, sid, option=1))
        if part_spaces:
            options.append((
                "Partisans",
                lambda s, c: partisans.execute(s, RC.PATRIOTS, c, choose_one("Partisans space:", part_spaces), option=choose_count("Option (1-3):", min_val=1, max_val=3)),
            ))
        persuasion_spaces = _legal_space_list("Persuasion", lambda s, c, sid: persuasion.execute(s, RC.PATRIOTS, c, spaces=[sid]))
        if persuasion_spaces:
            options.append((
                "Persuasion",
                lambda s, c: persuasion.execute(
                    s,
                    RC.PATRIOTS,
                    c,
                    spaces=[v for v in choose_multiple("Spaces for Persuasion (up to 3):", persuasion_spaces, min_sel=1, max_sel=3)],
                ),
            ))
        skirmish_spaces = _legal_space_list("Skirmish", lambda s, c, sid: skirmish.execute(s, RC.PATRIOTS, c, sid, option=1))
        if skirmish_spaces:
            options.append((
                "Skirmish",
                lambda s, c: skirmish.execute(s, RC.PATRIOTS, c, choose_one("Skirmish space:", skirmish_spaces), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3)),
            ))
    elif faction == RC.INDIANS:
        plunder_spaces = _legal_space_list("Plunder", lambda s, c, sid: plunder.execute(s, RC.INDIANS, c, sid))
        if plunder_spaces:
            options.append((
                "Plunder",
                lambda s, c: plunder.execute(s, RC.INDIANS, c, choose_one("Province to Plunder:", plunder_spaces)),
            ))
        trade_spaces = _legal_space_list("Trade", lambda s, c, sid: trade.execute(s, RC.INDIANS, c, sid, transfer=0))
        if trade_spaces:
            options.append((
                "Trade",
                lambda s, c: trade.execute(s, RC.INDIANS, c, choose_one("Province to Trade in:", trade_spaces), transfer=choose_count("Resource transfer (0=roll D3):", min_val=0, max_val=3)),
            ))
        war_path_spaces = _legal_space_list("War Path", lambda s, c, sid: war_path.execute(s, RC.INDIANS, c, sid, option=1))
        if war_path_spaces:
            options.append((
                "War Path",
                lambda s, c: war_path.execute(s, RC.INDIANS, c, choose_one("Province for War Path:", war_path_spaces), option=choose_count("Option (1-3):", min_val=1, max_val=3)),
            ))
    elif faction == RC.FRENCH:
        skirmish_spaces = _legal_space_list("Skirmish", lambda s, c, sid: skirmish.execute(s, RC.FRENCH, c, sid, option=1))
        if skirmish_spaces:
            options.append((
                "Skirmish",
                lambda s, c: skirmish.execute(s, RC.FRENCH, c, choose_one("Skirmish space:", skirmish_spaces), option=choose_count("Skirmish option (1-3):", min_val=1, max_val=3)),
            ))
        bloc = state.setdefault("markers", {}).setdefault(RC.BLOCKADE, {"pool": 0, "on_map": set()})
        naval_spaces = _legal_space_list("Naval Pressure", lambda s, c, sid: naval_pressure.execute(s, RC.FRENCH, c, city_choice=sid))
        if naval_spaces or bloc.get("pool", 0) == 0 and bloc.get("on_map"):
            def _french_naval_runner(s: dict, c: dict) -> Any:
                current_bloc = s.setdefault("markers", {}).setdefault(RC.BLOCKADE, {"pool": 0, "on_map": set()})
                if current_bloc.get("pool", 0) > 0:
                    city = choose_one("City to receive Blockade:", naval_spaces)
                    return naval_pressure.execute(s, RC.FRENCH, c, city_choice=city, rearrange_map=None)
                existing = list(current_bloc.get("on_map", set()))
                if not existing:
                    raise ValueError("No Blockades available for Naval Pressure.")
                cities = _space_options(s)
                selection = choose_multiple(
                    f"Select {len(existing)} cities to host Blockades after rearrange:",
                    cities,
                    min_sel=len(existing),
                    max_sel=len(existing),
                )
                rearrange_map = {cid: 1 for cid in selection}
                return naval_pressure.execute(s, RC.FRENCH, c, city_choice=None, rearrange_map=rearrange_map)

            options.append(("Naval Pressure", _french_naval_runner))
        prep_choices: List[Tuple[str, str]] = []
        for label, val in [("BLOCKADE", "BLOCKADE"), ("REGULARS", "REGULARS"), ("RESOURCES", "RESOURCES")]:
            test_state = deepcopy(state)
            try:
                preparer.execute(test_state, RC.FRENCH, {}, choice=val)
            except Exception as exc:  # noqa: BLE001
                sa_log.append({
                    "sa_name": "Preparer la Guerre",
                    "choice": val,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                })
                continue
            prep_choices.append((label, val))
        if prep_choices:
            options.append((
                "Preparer la Guerre",
                lambda s, c: preparer.execute(s, RC.FRENCH, c, choice=choose_one("Choose Preparer option:", prep_choices)),
            ))

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

    if not options:
        _log_empty_menu(engine.state, faction, "(any command)")
        raise ValueError(f"No commands available for {faction}.")

    runner_factory = choose_one("Select Command:", options)
    return runner_factory(engine, faction, limited)


def _human_decider(faction: str, card: dict, allowed: Dict[str, Any], engine: Engine) -> Tuple[dict, bool, dict | None, dict | None]:
    """Interactive handler for a human-controlled faction."""
    # Determine slot label
    first_action = engine.state.get("_first_action_this_card")
    slot = "1st Eligible" if first_action is None else "2nd Eligible"
    display_turn_context(faction, engine.state, slot=slot, card=card)

    # Show event text before the action menu so the player can make an informed choice
    faction_icons = card.get("faction_icons", {})
    can_play_event = allowed.get("event_allowed", False) and "event" in allowed.get("actions", set())
    has_sword = faction_icons.get(faction) == "SWORD"
    if can_play_event and not has_sword:
        unshaded = card.get("unshaded_event", "")
        shaded = card.get("shaded_event", "")
        if unshaded or shaded:
            print()
            print(f"  Event: {card.get('title', '?')}")
            if unshaded:
                print(f"    Unshaded: {unshaded}")
            if shaded:
                print(f"    Shaded:   {shaded}")
            print()

    while True:
        actions = []
        if "pass" in allowed["actions"]:
            actions.append(("Pass", "pass"))
        if "event" in allowed["actions"] and allowed.get("event_allowed", False):
            actions.append(("Event", "event"))
        if "command" in allowed["actions"]:
            label = "Command (Limited)" if allowed.get("limited_only") else "Command"
            if allowed.get("special_allowed") and not allowed.get("limited_only"):
                label += " + Special Activity"
            actions.append((label, "command"))

        choice = choose_one(f"\n{faction} turn. Choose action:", actions)

        if choice == "pass":
            return {"action": "pass", "used_special": False}, True, None, None

        if choice == "event":
            # Show event text
            if card.get("dual"):
                display_event_choice(card)
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
                print(f"  Cannot execute: {exc}")
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

        # Take snapshot before simulating for summary
        pre_snap = _snapshot_state(engine.state)

        try:
            result, legal, sim_state, sim_ctx = engine.simulate_action(faction, card, allowed, runner)
        except Exception as exc:  # noqa: BLE001
            print(f"Action failed: {exc}")
            continue

        if legal:
            # Show structured summary of what the human action did
            if sim_state:
                display_bot_summary(faction, sim_state, pre_snap, result)
            return result, True, sim_state, sim_ctx

        # Log rejection details
        illegal_reason = (sim_state or {}).get("_illegal_reason", "unknown")
        rejection_entry = {
            "faction": faction,
            "action_type": result.get("action"),
            "rejection_reason": illegal_reason,
        }
        engine.state.setdefault("_cli_rejection_log", []).append(rejection_entry)

        # Show specific rejection reason
        reason_msgs = {
            "action_type_not_allowed": "That action type is not allowed in this slot.",
            "event_not_allowed": "Events are not allowed as 2nd Eligible after a Command.",
            "limited_used_special": "Limited Command does not allow a Special Activity.",
            "special_forbidden": "Special Activities are not allowed in this slot.",
            "no_affected_spaces": "Action affected 0 spaces -- at least 1 required.",
        }
        if "limited_wrong_count" in illegal_reason:
            msg = "Limited Command allows only 1 space."
        else:
            msg = reason_msgs.get(illegal_reason, f"Not legal for this slot: {illegal_reason}")
        print(f"  {msg} Please choose again.")


# ---------------------------------------------------------------------------
# Autosave helper
# ---------------------------------------------------------------------------

def _do_autosave(state: Dict[str, Any], seed: int, scenario: str, deck_method: str,
                 human_factions: set) -> None:
    """Overwrite autosave.json with current state."""
    try:
        report = build_autosave(
            state,
            seed=seed,
            scenario=scenario,
            setup_method=deck_method,
            human_factions=human_factions,
        )
        save_report(report, "lod_ai/reports/autosave.json")
    except Exception:  # noqa: BLE001
        pass  # autosave failure is non-fatal


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
        (RC.BRITISH, RC.BRITISH),
        (RC.PATRIOTS, RC.PATRIOTS),
        (RC.FRENCH, RC.FRENCH),
        (RC.INDIANS, RC.INDIANS),
    ]
    humans = choose_multiple(
        "Select human-controlled factions:",
        factions,
        min_sel=num,
        max_sel=num,
    )
    return humans


def _choose_seed() -> int:
    import random
    seed = random.randint(1, 10_000)
    print(f"  RNG seed: {seed}")
    return seed


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    print("Liberty or Death -- Interactive CLI")
    print("Commands at any prompt:")
    print("  status/s  - board state    history/h - log")
    print("  victory/v - margins        bug/b     - file bug report")
    print("  quit/q    - exit game")
    print()

    scenario, deck_method = _choose_scenario()
    human_factions = _choose_humans()
    seed = _choose_seed()

    # Setup confirmation loop
    while True:
        display_setup_confirmation(scenario, deck_method, seed, human_factions)
        confirm = choose_one("Start game?", [("Yes", True), ("No - re-select", False)])
        if confirm:
            break
        scenario, deck_method = _choose_scenario()
        human_factions = _choose_humans()
        seed = _choose_seed()

    initial_state = build_state(scenario, seed=seed, setup_method=deck_method)
    # Store setup metadata in state for reports
    initial_state["_seed"] = seed
    initial_state["_scenario"] = scenario
    initial_state["_setup_method"] = deck_method

    engine = Engine(initial_state=initial_state, use_cli=True)
    engine.set_human_factions(human_factions)

    # Register state for meta-commands (pass engine too for bug reports)
    set_game_state(engine.state, engine=engine)

    # Initialize game stats tracker
    game_stats = _new_game_stats(engine.human_factions)

    print(f"\nGame start! (seed={seed}, method={deck_method})")

    game_ended = False

    while not game_ended:
        card = engine.draw_card()
        if not card:
            print("No more cards in deck.")
            _detect_winner(game_stats, engine.state)
            display_game_end(engine.state)
            game_ended = True
            break

        # Display the card
        display_card(
            card,
            upcoming=engine.state.get("upcoming_card"),
            eligible=engine.state.get("eligible", {}),
        )

        # Winter Quarters handling
        if card.get("winter_quarters"):
            display_winter_quarters_header()

            # Phase 1: Victory Check
            display_wq_phase(1, "Victory Check")
            display_victory_margins(engine.state)

            raw = pause_for_player()
            if raw in ("status", "s"):
                display_board_state(engine.state)

            # Run the full WQ resolution via play_card
            pre_snap = _snapshot_state(engine.state)
            try:
                engine.play_card(card, human_decider=_human_decider)
            except Exception as exc:
                tb_str = traceback.format_exc()
                print(f"\nCRASH during Winter Quarters: {exc}")
                report = build_crash_report(
                    engine.state, exc, tb_str,
                    human_factions=engine.human_factions,
                    seed=seed, scenario=scenario, setup_method=deck_method,
                )
                ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                saved = save_report(report, f"lod_ai/reports/crash_{ts}.json")
                print(f"Crash report saved to {saved}")
                raise

            # Record WQ stats
            _record_wq_margins(game_stats, engine.state)
            game_stats["cards_played"] += 1

            # Show what changed
            print("\nWinter Quarters complete.")
            display_bot_summary("WINTER QUARTERS", engine.state, pre_snap)

            raw = pause_for_player()
            if raw in ("status", "s"):
                display_board_state(engine.state)

            # Autosave after WQ
            _do_autosave(engine.state, seed, scenario, deck_method, engine.human_factions)

            # Check if game ended
            history = engine.state.get("history", [])
            for entry in reversed(history[-20:]):
                msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
                if "Winner:" in msg or "Victory achieved" in msg:
                    _detect_winner(game_stats, engine.state)
                    display_game_end(engine.state)
                    game_ended = True
                    break
            continue

        # Normal card play
        # Snapshot before bot turns (updated after each turn in callback)
        pre_snap = _snapshot_state(engine.state)

        # Store first action marker for human context display
        engine.state["_first_action_this_card"] = None

        def _post_turn_cb(faction, result, card):
            nonlocal pre_snap
            if faction not in engine.human_factions:
                display_bot_summary(faction, engine.state, pre_snap, result)
                raw = pause_for_player()
                if raw in ("status", "s"):
                    display_board_state(engine.state)
            # Track first action
            if engine.state.get("_first_action_this_card") is None:
                engine.state["_first_action_this_card"] = result
            # Update snapshot so the next turn's diff is accurate
            pre_snap = _snapshot_state(engine.state)

        try:
            actions = engine.play_card(card, human_decider=_human_decider, post_turn_callback=_post_turn_cb)
        except Exception as exc:
            tb_str = traceback.format_exc()
            print(f"\nCRASH during play_card: {exc}")
            report = build_crash_report(
                engine.state, exc, tb_str,
                human_factions=engine.human_factions,
                seed=seed, scenario=scenario, setup_method=deck_method,
            )
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            saved = save_report(report, f"lod_ai/reports/crash_{ts}.json")
            print(f"Crash report saved to {saved}")
            raise

        # Record stats from this card
        _record_turn_stats(game_stats, engine.state)
        game_stats["cards_played"] += 1

        # Clean up temp marker
        engine.state.pop("_first_action_this_card", None)

        # Autosave after every card
        _do_autosave(engine.state, seed, scenario, deck_method, engine.human_factions)

    # --- End of game: generate and save game report ---
    if game_stats.get("winner") is None:
        _detect_winner(game_stats, engine.state)

    # Display the game report
    display_game_report(game_stats, engine.state)

    # Save game report JSON
    try:
        report = build_game_report(
            engine.state, game_stats,
            seed=seed, scenario=scenario, setup_method=deck_method,
            human_factions=engine.human_factions,
        )
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        saved = save_report(report, f"lod_ai/reports/game_report_{ts}.json")
        print(f"Game report saved to {saved}")
    except Exception:  # noqa: BLE001
        print("(Could not save game report)")

    print("Thanks for playing!")


if __name__ == "__main__":
    main()
