"""
lod_ai.cli_display
===================
Display helpers for the Liberty or Death interactive CLI.

All functions here are read-only: they inspect state and print formatted
output but never mutate game state.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Dict, List, Tuple

from lod_ai import rules_consts as RC
from lod_ai.map import adjacency as map_adj
from lod_ai.victory import _summarize_board, _british_margin, _patriot_margin, _french_margin, _indian_margin

# ---------------------------------------------------------------------------
# Piece abbreviation map for compact display
# ---------------------------------------------------------------------------
_PIECE_ABBREV = {
    RC.REGULAR_BRI: "BrReg",
    RC.TORY: "Tory",
    RC.FORT_BRI: "BrFort",
    RC.REGULAR_PAT: "Cont",
    RC.MILITIA_A: "Mil(A)",
    RC.MILITIA_U: "Mil(U)",
    RC.FORT_PAT: "PatFort",
    RC.REGULAR_FRE: "FrReg",
    RC.WARPARTY_A: "WP(A)",
    RC.WARPARTY_U: "WP(U)",
    RC.VILLAGE: "Vil",
}

_ROYALIST_TAGS = {RC.REGULAR_BRI, RC.TORY, RC.FORT_BRI}
_REBELLION_TAGS = {RC.REGULAR_PAT, RC.MILITIA_A, RC.MILITIA_U, RC.FORT_PAT, RC.REGULAR_FRE}
_INDIAN_TAGS = {RC.WARPARTY_A, RC.WARPARTY_U, RC.VILLAGE}

_SUPPORT_LABELS = {
    2: "Active Sup",
    1: "Passive Sup",
    0: "Neutral",
    -1: "Passive Opp",
    -2: "Active Opp",
}


def _support_label(level: int) -> str:
    return _SUPPORT_LABELS.get(level, f"Lvl {level}")


def _control_label(ctrl: str | None) -> str:
    if ctrl == "BRITISH":
        return "British"
    if ctrl == "REBELLION":
        return "Rebellion"
    return "None"


def _pieces_str(sp: Dict[str, Any], tags: set[str]) -> str:
    parts = []
    for tag in sorted(tags):
        count = sp.get(tag, 0)
        if count > 0:
            abbrev = _PIECE_ABBREV.get(tag, tag)
            parts.append(f"{count} {abbrev}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# 1. Full board state display (status command)
# ---------------------------------------------------------------------------

def display_board_state(state: Dict[str, Any]) -> None:
    """Print the full board state in a compact format."""
    print()
    print("=" * 70)
    print("  BOARD STATE")
    print("=" * 70)

    # --- Score Track / Global State ---
    res = state.get("resources", {})
    print(f"\nResources:  British={res.get(RC.BRITISH, 0)}  "
          f"Patriots={res.get(RC.PATRIOTS, 0)}  "
          f"Indians={res.get(RC.INDIANS, 0)}  "
          f"French={res.get(RC.FRENCH, 0)}")

    # Support/Opposition totals
    sup_total = 0
    opp_total = 0
    for sid in state.get("spaces", {}):
        lvl = state.get("support", {}).get(sid, 0)
        if lvl > 0:
            sup_total += lvl
        elif lvl < 0:
            opp_total += abs(lvl)
    print(f"Support Total: {sup_total}  |  Opposition Total: {opp_total}")

    fni = state.get("fni_level", 0)
    cbc = state.get("cbc", 0)
    crc = state.get("crc", 0)
    print(f"FNI Level: {fni}  |  British Casualties(CBC): {cbc}  |  Rebellion Casualties(CRC): {crc}")

    # French Preparations / Treaty
    toa = state.get("toa_played", state.get("treaty_of_alliance", False))
    if toa:
        print("Treaty of Alliance: PLAYED")
    else:
        fp = state.get("french_preparations", 0)
        print(f"French Preparations: {fp}  |  Treaty of Alliance: NOT PLAYED")

    # Leaders with locations
    leaders = state.get("leaders", {})
    leader_locs = state.get("leader_locs", {})
    leader_parts = []
    for fac in (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH):
        name = leaders.get(fac, "?")
        loc = leader_locs.get(name, "?")
        leader_parts.append(f"{fac}={name} @{loc}")
    print(f"Leaders:  {', '.join(leader_parts)}")

    # Eligibility
    elig = state.get("eligible", {})
    elig_parts = []
    for fac in (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH):
        status = "Eligible" if elig.get(fac, True) else "Ineligible"
        elig_parts.append(f"{fac}={status}")
    print(f"Eligibility:  {', '.join(elig_parts)}")

    # Brilliant Stroke
    bs_played = state.get("bs_played", {})
    bs_parts = []
    for fac in (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH):
        if bs_played.get(fac):
            bs_parts.append(f"{fac}: played")
        else:
            bs_parts.append(f"{fac}: held")
    print(f"Brilliant Stroke:  {', '.join(bs_parts)}")

    # --- Available / Unavailable / Casualties ---
    print("\n--- Pools ---")
    for box_name in ("available", "unavailable", "casualties"):
        box = state.get(box_name, {})
        if box:
            items = [f"{v} {_PIECE_ABBREV.get(k, k)}" for k, v in sorted(box.items()) if v > 0]
            print(f"  {box_name.capitalize():14s}: {', '.join(items)}")
        else:
            print(f"  {box_name.capitalize():14s}: (empty)")

    # --- Markers ---
    print("\n--- Markers ---")
    markers = state.get("markers", {})
    for tag in (RC.PROPAGANDA, RC.RAID, RC.BLOCKADE):
        entry = markers.get(tag, {"pool": 0, "on_map": set()})
        pool = entry.get("pool", 0)
        on_map = entry.get("on_map", set())
        if on_map:
            spaces_str = ", ".join(sorted(on_map))
            print(f"  {tag:12s}: Pool={pool}, On map: {spaces_str}")
        else:
            print(f"  {tag:12s}: Pool={pool}, On map: (none)")

    # --- Per-space summary ---
    print("\n--- Spaces ---")
    header = f"  {'Space':<25s} {'Sup/Opp':<12s} {'Control':<10s} {'Pop':>3s}  Pieces"
    print(header)
    print("  " + "-" * 68)

    control_map = state.get("control", {})
    for sid in sorted(state.get("spaces", {})):
        sp = state["spaces"][sid]
        meta = map_adj.space_meta(sid) or {}
        pop = meta.get("population", sp.get("pop", 0))
        sup_lvl = state.get("support", {}).get(sid, 0)
        ctrl = control_map.get(sid)

        # Build piece strings with separators
        roy_str = _pieces_str(sp, _ROYALIST_TAGS)
        reb_str = _pieces_str(sp, _REBELLION_TAGS)
        ind_str = _pieces_str(sp, _INDIAN_TAGS)

        piece_parts = [p for p in (roy_str, reb_str, ind_str) if p]
        pieces_display = " | ".join(piece_parts) if piece_parts else "-"

        print(f"  {sid:<25s} {_support_label(sup_lvl):<12s} {_control_label(ctrl):<10s} {pop:>3d}  {pieces_display}")

    # --- Current/Upcoming cards ---
    current = state.get("current_card")
    upcoming = state.get("upcoming_card")
    if current or upcoming:
        print("\n--- Cards ---")
        if current:
            cid = current.get("id", "?")
            ctitle = current.get("title", "Unknown")
            order = current.get("order") or current.get("order_icons") or "?"
            print(f"  Current:  #{cid} {ctitle}  (Order: {order})")
        if upcoming:
            uid = upcoming.get("id", "?")
            utitle = upcoming.get("title", "Unknown")
            print(f"  Upcoming: #{uid} {utitle}")

    print("=" * 70)
    print()


# ---------------------------------------------------------------------------
# 2. Card display (fancy box)
# ---------------------------------------------------------------------------

def display_card(card: Dict[str, Any], upcoming: Dict[str, Any] | None = None,
                 eligible: Dict[str, bool] | None = None) -> None:
    """Display the current card in a bordered box."""
    cid = card.get("id", "?")
    title = card.get("title", "Unknown")
    order = card.get("order", [])
    order_str = ", ".join(str(f) for f in order) if order else str(card.get("order_icons", ""))

    # Determine eligible factions
    elig = eligible or {}
    elig_facs = [f for f in order if elig.get(f, True)] if order else []
    first_elig = elig_facs[0] if len(elig_facs) > 0 else "?"
    second_elig = elig_facs[1] if len(elig_facs) > 1 else "?"

    # Sword icon info
    sword = card.get("sword", False)
    sword_str = "  [Sword: must skip Event]" if sword else ""

    content_lines = [
        f"  Card {cid}: {title}",
        f"  Order: {order_str}",
        f"  1st Eligible: {first_elig}",
        f"  2nd Eligible: {second_elig}",
    ]
    if sword_str:
        content_lines.append(sword_str)

    if card.get("winter_quarters"):
        content_lines.append("  ** WINTER QUARTERS **")

    max_width = max(len(line) for line in content_lines) + 4

    print()
    print("\u2554" + "\u2550" * max_width + "\u2557")
    for line in content_lines:
        print("\u2551" + f" {line:<{max_width - 1}}" + "\u2551")
    print("\u255A" + "\u2550" * max_width + "\u255D")

    if upcoming:
        uid = upcoming.get("id", "?")
        utitle = upcoming.get("title", "Unknown")
        wq_flag = " [Winter Quarters]" if upcoming.get("winter_quarters") else ""
        print(f"  Upcoming: Card {uid} -- {utitle}{wq_flag}")
    print()


# ---------------------------------------------------------------------------
# 3. Event display
# ---------------------------------------------------------------------------

def display_event(card: Dict[str, Any], side: str | None = None) -> None:
    """Display event text for the given card side."""
    cid = card.get("id", "?")
    title = card.get("title", "Unknown")

    if side == "shaded" or side is None:
        text = card.get("shaded_event", "")
        if text:
            print(f"\nEvent: {title} (Shaded)")
            print(f'  "{text}"')
    if side == "unshaded" or side is None:
        text = card.get("unshaded_event", "")
        if text:
            print(f"\nEvent: {title} (Unshaded)")
            print(f'  "{text}"')
    print()


def display_event_choice(card: Dict[str, Any]) -> None:
    """Display both shaded and unshaded text for a human choosing."""
    cid = card.get("id", "?")
    title = card.get("title", "Unknown")
    print(f"\n--- Event: Card {cid} - {title} ---")
    unshaded = card.get("unshaded_event", "")
    shaded = card.get("shaded_event", "")
    if unshaded:
        print(f"  UNSHADED: {unshaded}")
    if shaded:
        print(f"  SHADED:   {shaded}")
    print()


# ---------------------------------------------------------------------------
# 4. Bot turn summary
# ---------------------------------------------------------------------------

def _snapshot_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Take a lightweight snapshot for diffing after a bot turn."""
    snap = {
        "resources": dict(state.get("resources", {})),
        "control": dict(state.get("control", {})),
        "support": dict(state.get("support", {})),
        "history_len": len(state.get("history", [])),
        "cbc": state.get("cbc", 0),
        "crc": state.get("crc", 0),
        "fni_level": state.get("fni_level", 0),
        "pieces": {},
    }
    for sid, sp in state.get("spaces", {}).items():
        piece_counts = {}
        for tag in list(_PIECE_ABBREV.keys()):
            count = sp.get(tag, 0)
            if count > 0:
                piece_counts[tag] = count
        if piece_counts:
            snap["pieces"][sid] = piece_counts
    return snap


def display_bot_summary(faction: str, state: Dict[str, Any],
                        pre_snapshot: Dict[str, Any],
                        result: Dict[str, Any] | None = None) -> None:
    """Print a structured summary of what a bot did by diffing state snapshots."""
    print()
    print(f"\u2501\u2501\u2501 {faction} BOT \u2501\u2501\u2501")

    # Part 1: Plain English from history entries added during this turn
    history = state.get("history", [])
    pre_len = pre_snapshot.get("history_len", 0)
    new_entries = history[pre_len:]

    if new_entries:
        for entry in new_entries:
            msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
            if msg and msg != "\u2014":
                print(f"  {msg}")
    else:
        action = (result or {}).get("action", "pass")
        print(f"  {faction} chose to {action}.")

    # Part 2: Structured changes
    print()

    # Resource changes
    pre_res = pre_snapshot.get("resources", {})
    cur_res = state.get("resources", {})
    res_changes = []
    for fac in (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH):
        old_val = pre_res.get(fac, 0)
        new_val = cur_res.get(fac, 0)
        if old_val != new_val:
            diff = new_val - old_val
            sign = "+" if diff > 0 else ""
            res_changes.append(f"{fac} {old_val}\u2192{new_val} ({sign}{diff})")
    if res_changes:
        print(f"  Resource changes: {', '.join(res_changes)}")

    # Control changes
    pre_ctrl = pre_snapshot.get("control", {})
    cur_ctrl = state.get("control", {})
    ctrl_changes = []
    for sid in sorted(set(list(pre_ctrl.keys()) + list(cur_ctrl.keys()))):
        old_c = pre_ctrl.get(sid)
        new_c = cur_ctrl.get(sid)
        if old_c != new_c:
            ctrl_changes.append(f"{sid} {_control_label(old_c)}\u2192{_control_label(new_c)}")
    if ctrl_changes:
        print(f"  Control changes: {', '.join(ctrl_changes)}")

    # Support changes
    pre_sup = pre_snapshot.get("support", {})
    cur_sup = state.get("support", {})
    sup_changes = []
    for sid in sorted(set(list(pre_sup.keys()) + list(cur_sup.keys()))):
        old_s = pre_sup.get(sid, 0)
        new_s = cur_sup.get(sid, 0)
        if old_s != new_s:
            sup_changes.append(f"{sid} {_support_label(old_s)}\u2192{_support_label(new_s)}")
    if sup_changes:
        print(f"  Support changes: {', '.join(sup_changes)}")

    # CBC/CRC/FNI changes
    misc_changes = []
    for key, label in (("cbc", "CBC"), ("crc", "CRC"), ("fni_level", "FNI")):
        old_v = pre_snapshot.get(key, 0)
        new_v = state.get(key, 0)
        if old_v != new_v:
            diff = new_v - old_v
            sign = "+" if diff > 0 else ""
            misc_changes.append(f"{label} {old_v}\u2192{new_v} ({sign}{diff})")
    if misc_changes:
        print(f"  Other changes: {', '.join(misc_changes)}")

    print()


def pause_for_player() -> str:
    """Pause and wait for player to press Enter. Returns any typed command."""
    raw = input("[Press Enter to continue, or type 'status' for board state] ").strip().lower()
    return raw


# ---------------------------------------------------------------------------
# 5. Human turn context line
# ---------------------------------------------------------------------------

def display_turn_context(faction: str, state: Dict[str, Any],
                         slot: str = "", card: Dict[str, Any] | None = None) -> None:
    """Print a brief context line before human action selection."""
    res = state.get("resources", {}).get(faction, 0)
    card_title = (card or {}).get("title", "?")
    print(f"\n{faction} turn ({slot}) | Resources: {res} | Card: {card_title}")


# ---------------------------------------------------------------------------
# 6. History display
# ---------------------------------------------------------------------------

def display_history(state: Dict[str, Any], count: int = 10) -> None:
    """Show the last N history entries."""
    history = state.get("history", [])
    recent = history[-count:] if len(history) > count else history
    print(f"\n--- Last {len(recent)} History Entries ---")
    for entry in recent:
        seq = entry.get("seq", "?") if isinstance(entry, dict) else "?"
        msg = entry.get("msg", str(entry)) if isinstance(entry, dict) else str(entry)
        print(f"  [{seq}] {msg}")
    print()


# ---------------------------------------------------------------------------
# 7. Winter Quarters display
# ---------------------------------------------------------------------------

def display_winter_quarters_header() -> None:
    """Print the Winter Quarters header."""
    print()
    print("\u2550" * 3 + " WINTER QUARTERS " + "\u2550" * 3)


def display_wq_phase(phase_num: int, phase_name: str) -> None:
    """Print a Winter Quarters phase header."""
    print(f"\nPhase {phase_num}: {phase_name}")


def display_victory_margins(state: Dict[str, Any]) -> None:
    """Print victory margins for all factions."""
    t = _summarize_board(state)
    brit1, brit2 = _british_margin(t)
    pat1, pat2 = _patriot_margin(t)
    fre1, fre2 = _french_margin(t)
    ind1, ind2 = _indian_margin(t)

    print(f"  British:  margins ({brit1}, {brit2})" +
          (" -- MET!" if brit1 > 0 and brit2 > 0 else " -- not met"))
    print(f"  Patriots: margins ({pat1}, {pat2})" +
          (" -- MET!" if pat1 > 0 and pat2 > 0 else " -- not met"))

    toa = t.get("treaty_of_alliance", False)
    fre_label = " -- MET!" if (toa and fre1 > 0 and fre2 > 0) else " -- not met"
    if not toa:
        fre_label = " -- (ToA not played)"
    print(f"  French:   margins ({fre1}, {fre2}){fre_label}")
    print(f"  Indians:  margins ({ind1}, {ind2})" +
          (" -- MET!" if ind1 > 0 and ind2 > 0 else " -- not met"))


# ---------------------------------------------------------------------------
# 8. Game end display
# ---------------------------------------------------------------------------

def display_game_end(state: Dict[str, Any]) -> None:
    """Print the game-end screen with final scoring and victory margins."""
    print()
    print("=" * 70)
    print("  GAME OVER")
    print("=" * 70)

    # Detect victory type from history
    history = state.get("history", [])
    winner_msg = None
    victory_type = None
    final_scoring_msg = None
    for entry in reversed(history[-40:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Winner:" in msg:
            winner_msg = msg
            if "Rule 7.3" in msg:
                victory_type = "final_scoring"
            elif victory_type is None:
                victory_type = "victory_condition"
        elif "Victory achieved" in msg:
            if winner_msg is None:
                winner_msg = msg
            victory_type = "victory_condition"
        elif "Final Scoring" in msg:
            final_scoring_msg = msg

    if victory_type == "final_scoring":
        print("\n  Game ended by FINAL SCORING (Rule 7.3)")
    elif victory_type == "victory_condition":
        print("\n  Game ended by VICTORY CONDITION at Winter Quarters")
    else:
        print("\n  Game ended (deck exhausted or manual stop)")

    if winner_msg:
        print(f"  {winner_msg}")
    if final_scoring_msg:
        print(f"  {final_scoring_msg}")

    print("\nFinal Victory Margins:")
    display_victory_margins(state)

    print("\nFinal Resources:")
    res = state.get("resources", {})
    for fac in (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH):
        print(f"  {fac}: {res.get(fac, 0)}")

    # Final board snapshot
    cbc = state.get("cbc", 0)
    crc = state.get("crc", 0)
    fni = state.get("fni_level", 0)
    toa = state.get("toa_played", state.get("treaty_of_alliance", False))
    print(f"\nCBC: {cbc}  CRC: {crc}  FNI: {fni}  ToA: {'PLAYED' if toa else 'not played'}")
    print(f"Cards played: {len(state.get('played_cards', []))}")

    print()
    raw = input("Type 'status' to see final board state, or Enter to finish: ").strip().lower()
    if raw in ("status", "s"):
        display_board_state(state)

    print("\nThanks for playing Liberty or Death!")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 9. Setup confirmation display
# ---------------------------------------------------------------------------

def display_setup_confirmation(scenario: str, deck_method: str, seed: int,
                               human_factions: List[str]) -> None:
    """Display setup confirmation and ask for approval."""
    all_factions = [RC.BRITISH, RC.PATRIOTS, RC.FRENCH, RC.INDIANS]
    print(f"\n  Scenario: {scenario}")
    for fac in all_factions:
        role = "HUMAN" if fac in human_factions else "BOT"
        print(f"  {fac}: {role}")
    print(f"  Seed: {seed}")
    print(f"  Deck method: {deck_method}")
    print()


# ---------------------------------------------------------------------------
# 10. End-of-game report display
# ---------------------------------------------------------------------------

_ALL_FACTIONS = (RC.BRITISH, RC.PATRIOTS, RC.INDIANS, RC.FRENCH)


def display_game_report(game_stats: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Print a concise end-of-game summary report."""
    print()
    print("=" * 70)
    print("  GAME SUMMARY REPORT")
    print("=" * 70)

    # --- Winner & Victory ---
    winner = game_stats.get("winner", "Unknown")
    victory_type = game_stats.get("victory_type", "unknown")
    print(f"\n  Winner: {winner} ({victory_type})")

    print("\n  Victory Margins:")
    display_victory_margins(state)

    # --- Game Tempo ---
    print(f"\n  Cards played: {game_stats.get('cards_played', 0)}")
    print(f"  Winter Quarters resolved: {game_stats.get('wq_count', 0)}")
    print(f"  Campaign years: {game_stats.get('campaign_years', '?')}")

    # --- Faction Performance ---
    print("\n  --- Faction Performance ---")
    faction_stats = game_stats.get("faction_stats", {})
    for fac in _ALL_FACTIONS:
        fs = faction_stats.get(fac, {})
        role = "HUMAN" if fs.get("is_human") else "BOT"
        print(f"\n  {fac} ({role})")

        # Commands executed
        cmds = fs.get("commands", {})
        if cmds:
            cmd_parts = [f"{cmd}={count}" for cmd, count in sorted(cmds.items()) if count > 0]
            if cmd_parts:
                print(f"    Commands: {', '.join(cmd_parts)}")

        # Events
        events = fs.get("events_played", [])
        if events:
            print(f"    Events played: {len(events)} (cards: {', '.join(str(e) for e in events)})")

        # Special activities
        sas = fs.get("special_activities", {})
        if sas:
            sa_parts = [f"{sa}={count}" for sa, count in sorted(sas.items()) if count > 0]
            if sa_parts:
                print(f"    Special Activities: {', '.join(sa_parts)}")

        # Passes
        passes = fs.get("passes", 0)
        if passes:
            reasons = fs.get("pass_reasons", {})
            reason_parts = [f"{r}={c}" for r, c in sorted(reasons.items()) if c > 0]
            reason_str = f" ({', '.join(reason_parts)})" if reason_parts else ""
            print(f"    Passes: {passes}{reason_str}")

    # --- Combat & Casualties ---
    print(f"\n  --- Final State ---")
    print(f"  CBC: {state.get('cbc', 0)}  CRC: {state.get('crc', 0)}")
    print(f"  FNI: {state.get('fni_level', 0)}")
    toa = state.get("toa_played", state.get("treaty_of_alliance", False))
    print(f"  Treaty of Alliance: {'PLAYED' if toa else 'not played'}")

    # --- Victory Margin Trajectory ---
    trajectory = game_stats.get("wq_margins", [])
    if trajectory:
        print("\n  --- Victory Margin Trajectory (at each WQ) ---")
        for entry in trajectory:
            print(f"    {entry}")

    print()
    print("=" * 70)
