#!/usr/bin/env python3
"""
Batch smoke test with diagnostic data capture.

Modes:
    python -m lod_ai.tools.batch_smoke          # default 60-game batch (20/scenario)
    python -m lod_ai.tools.batch_smoke --single  # single game sanity check
    python -m lod_ai.tools.batch_smoke --large   # 150-game batch (50/scenario) with rich stats

Writes:
  default mode  → batch_results.json / batch_results_diagnostic.json
  --large mode  → lod_ai/tools/batch_results_large.json  (full per-game data)
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Redirect stdin to /dev/null so any accidental interactive prompt
# raises EOFError instead of blocking.
_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.victory import (
    _summarize_board, _british_margin, _patriot_margin,
    _french_margin, _indian_margin,
)
from lod_ai import rules_consts as C

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCENARIOS = ["1775", "1776", "1778"]
SEEDS_PER_SCENARIO = 20
LARGE_SEEDS_PER_SCENARIO = 50
CARD_SAFETY_LIMIT = 200
RESULTS_PATH = Path(__file__).resolve().parent / "batch_results.json"
DIAG_RESULTS_PATH = Path(__file__).resolve().parent / "batch_results_diagnostic.json"
LARGE_RESULTS_PATH = Path(__file__).resolve().parent / "batch_results_large.json"
FACTIONS = [C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH]
FACTION_ABBREV = {C.BRITISH: "BRI", C.PATRIOTS: "PAT", C.INDIANS: "IND", C.FRENCH: "FRE"}
ABBREV_TO_FACTION = {"BRI": C.BRITISH, "PAT": C.PATRIOTS, "IND": C.INDIANS, "FRE": C.FRENCH}

# Piece tags per faction for counting pieces on the map
FACTION_PIECE_TAGS = {
    C.BRITISH: [C.REGULAR_BRI, C.TORY, C.FORT_BRI],
    C.PATRIOTS: [C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT],
    C.FRENCH: [C.REGULAR_FRE],
    C.INDIANS: [C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE],
}

PASS_REASON_KEYS = ['resource_gate', 'no_valid_command', 'illegal_action', 'bot_error', 'other']

# SA names as they appear in history messages → canonical key
SA_HISTORY_NAMES = {
    "SKIRMISH": "skirmish",
    "NAVAL_PRESSURE": "naval_pressure",
    "PREPARER": "preparer",
    "PARTISANS": "partisans",
    "TRADE": "trade",
    "COMMON_CAUSE": "common_cause",
    "WAR_PATH": "war_path",
    "PERSUASION": "persuasion",
    "PLUNDER": "plunder",
}

# Regex patterns for history parsing
_VICTORY_CHECK_RE = re.compile(
    r'Victory Check\s+[–—-]\s+'
    r'BRI\((-?\d+),(-?\d+)\)\s+'
    r'PAT\((-?\d+),(-?\d+)\)\s+'
    r'FRE\((-?\d+),(-?\d+)\)\s+'
    r'IND\((-?\d+),(-?\d+)\)'
)
_BATTLE_ANNOUNCE_RE = re.compile(r'^(\w+) BATTLE in (.+)$')
_BATTLE_RESULT_RE = re.compile(
    r'BATTLE (\S+): (\w+)-loss=(\d+), (\w+)-loss=(\d+), winner=(\w+|NONE)'
)
_FINAL_SCORING_RE = re.compile(r'Final Scoring')
_FINAL_SCORE_PAIR_RE = re.compile(r'(\w+):(-?[\dinf.]+)')


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _count_pieces_on_map(state: dict) -> Dict[str, int]:
    """Count total pieces on map per faction."""
    counts = {}
    for faction, tags in FACTION_PIECE_TAGS.items():
        total = 0
        for sp in state.get('spaces', {}).values():
            for tag in tags:
                total += sp.get(tag, 0)
        counts[faction] = total
    return counts


def _count_controlled_spaces(state: dict) -> Dict[str, int]:
    """Count spaces controlled by each side."""
    ctrl = state.get("control", {})
    counts = {C.BRITISH: 0, "REBELLION": 0}
    for sid, owner in ctrl.items():
        if owner == C.BRITISH:
            counts[C.BRITISH] += 1
        elif owner == "REBELLION":
            counts["REBELLION"] += 1
    return counts


def _support_opposition_totals(state: dict) -> Tuple[int, int]:
    """Return (total_support, total_opposition) across all spaces."""
    sup = 0
    opp = 0
    for lvl in state.get("support", {}).values():
        if lvl > 0:
            sup += lvl
        elif lvl < 0:
            opp += abs(lvl)
    return sup, opp


def _count_forts_villages(state: dict) -> Tuple[int, int, int]:
    """Return (british_forts, patriot_forts, villages)."""
    bf = pf = vil = 0
    for sp in state.get("spaces", {}).values():
        bf += sp.get(C.FORT_BRI, 0)
        pf += sp.get(C.FORT_PAT, 0)
        vil += sp.get(C.VILLAGE, 0)
    return bf, pf, vil


def _compute_margins(state: dict) -> Dict[str, Tuple[int, int]]:
    """Compute victory margins for all 4 factions."""
    tallies = _summarize_board(state)
    return {
        C.BRITISH: _british_margin(tallies),
        C.PATRIOTS: _patriot_margin(tallies),
        C.FRENCH: _french_margin(tallies),
        C.INDIANS: _indian_margin(tallies),
    }


def _determine_winner_from_margins(state: dict) -> str:
    """Use the victory margin functions to determine which faction won."""
    tallies = _summarize_board(state)
    brit1, brit2 = _british_margin(tallies)
    pat1, pat2 = _patriot_margin(tallies)
    fre1, fre2 = _french_margin(tallies)
    ind1, ind2 = _indian_margin(tallies)

    if brit1 > 0 and brit2 > 0:
        return C.BRITISH
    if pat1 > 0 and pat2 > 0:
        return C.PATRIOTS
    if tallies["treaty_of_alliance"] and fre1 > 0 and fre2 > 0:
        return C.FRENCH
    if ind1 > 0 and ind2 > 0:
        return C.INDIANS
    return "UNKNOWN"


def _check_game_over(state: dict) -> str | None:
    """Scan history for a winner or victory message. Return winner or None."""
    history = state.get("history", [])
    for entry in reversed(history[-40:]):
        msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
        if "Winner:" in msg:
            parts = msg.split("Winner:")
            if len(parts) >= 2:
                faction = parts[1].strip().split()[0].strip("()")
                return faction
        if "Victory achieved" in msg:
            return _determine_winner_from_margins(state)
    return None


def _parse_victory_margins(msg: str) -> Dict[str, tuple] | None:
    """Parse 'Victory Check – BRI(x,y) PAT(x,y) FRE(x,y) IND(x,y)' into a dict."""
    m = _VICTORY_CHECK_RE.search(msg)
    if not m:
        return None
    return {
        'BRI': (int(m.group(1)), int(m.group(2))),
        'PAT': (int(m.group(3)), int(m.group(4))),
        'FRE': (int(m.group(5)), int(m.group(6))),
        'IND': (int(m.group(7)), int(m.group(8))),
    }


# ---------------------------------------------------------------------------
# Legacy diagnostic data (kept for default mode backward compat)
# ---------------------------------------------------------------------------

def _empty_faction_passes() -> Dict[str, Any]:
    return {
        'total': 0, 'resource_gate': 0, 'no_valid_command': 0,
        'illegal_action': 0, 'bot_error': 0, 'other': 0,
        'as_1st': 0, 'as_2nd': 0, 'as_3rd_plus': 0,
        'current_streak': 0, 'max_streak': 0, 'streaks': [],
    }


def _empty_faction_eligible() -> Dict[str, int]:
    return {'total': 0, 'as_1st': 0, 'as_2nd': 0, 'as_3rd_plus': 0, 'acted': 0, 'passed': 0}


def _empty_diagnostics() -> Dict[str, Any]:
    return {
        'wq_margins': [],
        'passes': {f: _empty_faction_passes() for f in FACTIONS},
        'eligible_turns': {f: _empty_faction_eligible() for f in FACTIONS},
        'final_resources': {},
        'treaty_played': False, 'treaty_card_number': None,
        'total_pieces_on_map': {},
    }


def _process_card_turn_log(diag: Dict, state: dict) -> None:
    """Process _card_turn_log from state to update pass/eligible tracking."""
    for entry in state.get('_card_turn_log', []):
        faction = entry.get('faction')
        if faction not in FACTIONS:
            continue
        action = entry.get('action')
        pos = entry.get('eligible_position', 0)

        et = diag['eligible_turns'][faction]
        et['total'] += 1
        if pos == 1:
            et['as_1st'] += 1
        elif pos == 2:
            et['as_2nd'] += 1
        else:
            et['as_3rd_plus'] += 1

        if action == 'pass':
            et['passed'] += 1
            pd = diag['passes'][faction]
            pd['total'] += 1
            reason = entry.get('pass_reason') or 'other'
            if reason in pd:
                pd[reason] += 1
            else:
                pd['other'] += 1
            if pos == 1:
                pd['as_1st'] += 1
            elif pos == 2:
                pd['as_2nd'] += 1
            else:
                pd['as_3rd_plus'] += 1
            pd['current_streak'] += 1
        else:
            et['acted'] += 1
            pd = diag['passes'][faction]
            streak = pd['current_streak']
            if streak > 0:
                pd['streaks'].append(streak)
                pd['current_streak'] = 0


def _scan_history_for_events(diag: Dict, history: list, history_offset: int,
                             cards_played: int) -> int:
    for entry in history[history_offset:]:
        msg = entry.get('msg', '') if isinstance(entry, dict) else str(entry)
        if msg.startswith('Victory Check'):
            margins = _parse_victory_margins(msg)
            if margins:
                diag['wq_margins'].append(margins)
        if 'Treaty of Alliance' in msg and not diag['treaty_played']:
            diag['treaty_played'] = True
            diag['treaty_card_number'] = cards_played
    return len(history)


def _finalize_diagnostics(diag: Dict, state: dict) -> None:
    for f in FACTIONS:
        pd = diag['passes'][f]
        streak = pd['current_streak']
        if streak > 0:
            pd['streaks'].append(streak)
            pd['current_streak'] = 0
        pd['max_streak'] = max(pd['streaks']) if pd['streaks'] else 0
    diag['final_resources'] = dict(state.get('resources', {}))
    if not diag['treaty_played']:
        diag['treaty_played'] = bool(
            state.get('toa_played') or state.get('treaty_of_alliance')
        )
    diag['total_pieces_on_map'] = _count_pieces_on_map(state)


# ---------------------------------------------------------------------------
# Enhanced (large mode) data structures and helpers
# ---------------------------------------------------------------------------

def _empty_large_data() -> Dict[str, Any]:
    """Create the comprehensive per-game data structure for --large mode."""
    return {
        # Winner detail
        "victory_type": None,        # "victory_condition" | "final_scoring"
        "wq_win_number": None,       # which WQ check (1-based) for VC wins
        "campaign_year": None,       # actual year string
        "final_scores": {},          # {faction: score} for final_scoring games
        "final_margins": {},         # {faction_abbrev: [m1, m2]} for ALL games

        # Faction action profiles
        "faction_actions": {f: {
            "commands": {},            # {cmd_type: count}
            "events_played": [],       # [card_id, ...]
            "events_count": 0,
            "special_activities": {},   # {sa_type: count}
            "sa_count": 0,
            "passes_total": 0,
            "passes_resource_gate": 0,
            "passes_no_valid_command": 0,
        } for f in FACTIONS},

        # Game tempo
        "total_cards": 0,
        "cards_per_campaign": [],      # [count_for_year_0, count_for_year_1, ...]
        "ending_campaign_year": None,
        "wq_count": 0,

        # WQ snapshots
        "wq_snapshots": [],

        # Combat stats
        "battles_total": 0,
        "battles_as_attacker": {f: 0 for f in FACTIONS},
        "battle_losses": {"ROYALIST": 0, "REBELLION": 0},
        "cbc_final": 0,
        "crc_final": 0,
    }


def _capture_wq_snapshot(state: dict, wq_number: int) -> Dict[str, Any]:
    """Capture board state at a Winter Quarters resolution."""
    margins = _compute_margins(state)
    pieces = _count_pieces_on_map(state)
    ctrl = _count_controlled_spaces(state)
    sup, opp = _support_opposition_totals(state)
    bf, pf, vil = _count_forts_villages(state)

    return {
        "wq_number": wq_number,
        "margins": {
            FACTION_ABBREV[f]: list(margins[f]) for f in FACTIONS
        },
        "pieces_on_map": dict(pieces),
        "spaces_controlled": dict(ctrl),
        "support_total": sup,
        "opposition_total": opp,
        "resources": dict(state.get("resources", {})),
        "fni_level": state.get("fni_level", 0),
        "treaty_status": bool(
            state.get("toa_played") or state.get("treaty_of_alliance")
        ),
        "forts_british": bf,
        "forts_patriot": pf,
        "villages": vil,
    }


def _process_turn_log_large(data: Dict, state: dict, card_id: int | None) -> None:
    """Process _card_turn_log entries to update faction action profiles."""
    for entry in state.get('_card_turn_log', []):
        faction = entry.get('faction')
        if faction not in FACTIONS:
            continue
        action = entry.get('action')
        fa = data["faction_actions"][faction]

        if action == 'pass':
            fa["passes_total"] += 1
            reason = entry.get('pass_reason', 'other')
            if reason == 'resource_gate':
                fa["passes_resource_gate"] += 1
            elif reason == 'no_valid_command':
                fa["passes_no_valid_command"] += 1

        elif action == 'command':
            cmd = entry.get('command_type') or 'UNKNOWN'
            fa["commands"][cmd] = fa["commands"].get(cmd, 0) + 1
            if entry.get('used_special'):
                fa["sa_count"] += 1

        elif action == 'event':
            eid = entry.get('event_card_id') or card_id
            if eid is not None:
                fa["events_played"].append(eid)
            fa["events_count"] += 1


def _scan_history_large(data: Dict, history: list, offset: int,
                        cards_played: int) -> int:
    """Scan new history entries for battles, SAs, treaty, and victory checks."""
    for entry in history[offset:]:
        msg = entry.get('msg', '') if isinstance(entry, dict) else str(entry)

        # Victory check margins (WQ)
        if msg.startswith('Victory Check'):
            margins = _parse_victory_margins(msg)
            if margins:
                # Stored in wq_snapshots instead; keep for quick access
                pass

        # Battle announcements: "{FACTION} BATTLE in {spaces}"
        m = _BATTLE_ANNOUNCE_RE.match(msg)
        if m:
            att_faction = m.group(1).upper()
            data["battles_total"] += 1
            if att_faction in data["battles_as_attacker"]:
                data["battles_as_attacker"][att_faction] += 1

        # Battle results: "BATTLE {sid}: {side}-loss={n}, {side}-loss={n}, winner={w}"
        m = _BATTLE_RESULT_RE.search(msg)
        if m:
            side1, loss1 = m.group(2), int(m.group(3))
            side2, loss2 = m.group(4), int(m.group(5))
            if side1 in data["battle_losses"]:
                data["battle_losses"][side1] += loss1
            if side2 in data["battle_losses"]:
                data["battle_losses"][side2] += loss2

        # Special activities: "{FACTION} {SA_NAME} ..."
        for sa_name, sa_key in SA_HISTORY_NAMES.items():
            if sa_name in msg:
                # Determine which faction used it
                for f in FACTIONS:
                    if msg.startswith(f"{f} {sa_name}"):
                        fa = data["faction_actions"][f]
                        fa["special_activities"][sa_key] = (
                            fa["special_activities"].get(sa_key, 0) + 1
                        )
                        break

        # Treaty of Alliance detection (for timing)
        if 'Treaty of Alliance played' in msg:
            data.setdefault("_treaty_card_number", cards_played)

        # Final Scoring: parse faction scores
        if _FINAL_SCORING_RE.search(msg):
            pairs = _FINAL_SCORE_PAIR_RE.findall(msg)
            for faction_str, score_str in pairs:
                try:
                    score = float(score_str)
                except ValueError:
                    score = float('-inf')
                data["final_scores"][faction_str] = score

    return len(history)


def _determine_victory_detail(data: Dict, state: dict,
                              wq_count: int, scenario: str,
                              winner: str | None, end_reason: str | None) -> None:
    """Fill in victory_type, wq_win_number, campaign_year, final_margins."""
    start_year = int(scenario)

    # Final margins for ALL games
    margins = _compute_margins(state)
    data["final_margins"] = {
        FACTION_ABBREV[f]: list(margins[f]) for f in FACTIONS
    }

    # CBC / CRC
    data["cbc_final"] = state.get("cbc", 0)
    data["crc_final"] = state.get("crc", 0)

    if end_reason == "WINNER" and winner:
        # Was it a mid-game victory condition or final scoring?
        history = state.get("history", [])
        is_final_scoring = False
        for entry in reversed(history[-40:]):
            msg = entry.get("msg", "") if isinstance(entry, dict) else str(entry)
            if "Final Scoring" in msg:
                is_final_scoring = True
                break

        if is_final_scoring:
            data["victory_type"] = "final_scoring"
            data["campaign_year"] = str(start_year + wq_count - 1)
        else:
            data["victory_type"] = "victory_condition"
            data["wq_win_number"] = wq_count
            data["campaign_year"] = str(start_year + wq_count - 1)

    data["wq_count"] = wq_count
    data["ending_campaign_year"] = str(start_year + wq_count - 1) if wq_count > 0 else str(start_year)


# ---------------------------------------------------------------------------
# Game runner (supports both default and detailed modes)
# ---------------------------------------------------------------------------

def run_one_game(scenario: str, seed: int, *, detailed: bool = False) -> Dict[str, Any]:
    """Run a single zero-player game.

    If *detailed* is True, collects the comprehensive data for --large mode.
    """
    result: Dict[str, Any] = {
        "scenario": scenario,
        "seed": seed,
        "winner": None,
        "end_reason": None,
        "cards_played": 0,
        "error": None,
        "traceback": None,
    }
    diag = _empty_diagnostics()
    large_data = _empty_large_data() if detailed else None

    try:
        state = build_state(scenario, seed=seed)
        engine = Engine(initial_state=state, use_cli=False)
        engine.set_human_factions([])  # all bots

        cards_played = 0
        history_offset = len(engine.state.get('history', []))
        wq_count = 0
        current_campaign_cards = 0

        while cards_played < CARD_SAFETY_LIMIT:
            card = engine.draw_card()
            if card is None:
                result["end_reason"] = "DECK_EXHAUSTED"
                break

            is_wq = bool(card.get("winter_quarters"))

            # Pre-card resource snapshot (for delta tracking)
            pre_resources = dict(engine.state.get("resources", {})) if detailed else None

            engine.play_card(card, human_decider=None)
            cards_played += 1
            current_campaign_cards += 1

            # Process turn log
            _process_card_turn_log(diag, engine.state)
            if detailed:
                _process_turn_log_large(large_data, engine.state, card.get("id"))

            # Scan history
            history = engine.state.get('history', [])
            prev_offset = history_offset
            history_offset = _scan_history_for_events(
                diag, history, history_offset, cards_played
            )
            if detailed:
                _scan_history_large(
                    large_data, history, prev_offset, cards_played
                )

            # WQ handling
            if is_wq:
                wq_count += 1
                if detailed:
                    snapshot = _capture_wq_snapshot(engine.state, wq_count)
                    large_data["wq_snapshots"].append(snapshot)
                    large_data["cards_per_campaign"].append(current_campaign_cards)
                current_campaign_cards = 0

            # Check game over
            winner = _check_game_over(engine.state)
            if winner:
                result["winner"] = winner
                result["end_reason"] = "WINNER"
                break
        else:
            result["end_reason"] = "TIMEOUT"

        result["cards_played"] = cards_played
        _finalize_diagnostics(diag, engine.state)

        if detailed:
            # Add remaining campaign cards if game didn't end at WQ
            if current_campaign_cards > 0:
                large_data["cards_per_campaign"].append(current_campaign_cards)
            large_data["total_cards"] = cards_played
            _determine_victory_detail(
                large_data, engine.state, wq_count, scenario,
                result.get("winner"), result.get("end_reason"),
            )

    except EOFError:
        result["end_reason"] = "INTERACTIVE_PROMPT"
        result["error"] = "Engine tried to read interactive input in zero-player mode"
        result["traceback"] = traceback.format_exc()
    except Exception as exc:
        result["end_reason"] = "CRASH"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()

    result["diagnostics"] = diag
    if detailed:
        result["large_data"] = large_data
    return result


# ---------------------------------------------------------------------------
# Legacy summary printing (kept for default mode)
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]], label: str) -> None:
    total = len(results)
    if total == 0:
        return
    wins: Counter[str] = Counter()
    end_reasons: Counter[str] = Counter()
    total_cards = 0
    for r in results:
        end_reasons[r["end_reason"] or "UNKNOWN"] += 1
        if r["winner"] and r["end_reason"] == "WINNER":
            wins[r["winner"]] += 1
        total_cards += r.get("cards_played", 0)
    avg_cards = total_cards / total if total else 0
    print(f"\n{'=' * 60}")
    print(f"  {label}  ({total} games)")
    print(f"{'=' * 60}")
    print(f"  {'Faction':<16} {'Wins':>6}")
    print(f"  {'-' * 24}")
    for faction in ["BRITISH", "PATRIOTS", "INDIANS", "FRENCH", "VICTORY"]:
        if wins[faction]:
            print(f"  {faction:<16} {wins[faction]:>6}")
    draws = end_reasons.get("DRAW", 0)
    if draws:
        print(f"  {'DRAW':<16} {draws:>6}")
    print(f"  {'-' * 24}")
    print(f"  {'Deck exhausted':<16} {end_reasons.get('DECK_EXHAUSTED', 0):>6}")
    print(f"  {'Timeouts':<16} {end_reasons.get('TIMEOUT', 0):>6}")
    print(f"  {'Crashes':<16} {end_reasons.get('CRASH', 0):>6}")
    print(f"  {'Interactive hang':<16} {end_reasons.get('INTERACTIVE_PROMPT', 0):>6}")
    print(f"  {'Avg cards played':<16} {avg_cards:>6.1f}")
    print()


def _print_victory_margin_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  VICTORY MARGIN ANALYSIS")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        wq_data: Dict[int, Dict[str, List[tuple]]] = defaultdict(lambda: defaultdict(list))
        for r in results:
            diag = r.get('diagnostics', {})
            for i, wq in enumerate(diag.get('wq_margins', [])):
                for abbrev, margins in wq.items():
                    wq_data[i][abbrev].append(margins)
        if not wq_data:
            print(f"\n  Scenario {scenario}: no WQ data")
            continue
        print(f"\n  Scenario {scenario}:")
        for wq_idx in sorted(wq_data.keys()):
            print(f"    WQ{wq_idx + 1}:")
            for abbrev in ['BRI', 'PAT', 'FRE', 'IND']:
                margins = wq_data[wq_idx].get(abbrev, [])
                if margins:
                    avg_m1 = sum(m[0] for m in margins) / len(margins)
                    avg_m2 = sum(m[1] for m in margins) / len(margins)
                    both_pos = sum(1 for m in margins if m[0] > 0 and m[1] > 0)
                    print(f"      {abbrev}: avg({avg_m1:+.1f}, {avg_m2:+.1f})"
                          f"  both>0: {both_pos}/{len(margins)}")


def _print_both_conditions_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  BOTH CONDITIONS POSITIVE (even if another faction won first)")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        both_pos: Counter[str] = Counter()
        total_checks = 0
        for r in results:
            diag = r.get('diagnostics', {})
            for wq in diag.get('wq_margins', []):
                total_checks += 1
                for abbrev, (m1, m2) in wq.items():
                    if m1 > 0 and m2 > 0:
                        both_pos[abbrev] += 1
        if total_checks == 0:
            print(f"\n  Scenario {scenario}: no WQ data")
            continue
        print(f"\n  Scenario {scenario} ({total_checks} total WQ checks):")
        for abbrev in ['BRI', 'PAT', 'FRE', 'IND']:
            count = both_pos[abbrev]
            pct = count / total_checks * 100
            print(f"    {abbrev}: {count}/{total_checks} ({pct:.1f}%)")


def _print_margin_trends(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  MARGIN TRENDS (non-Patriot sum-of-margins by WQ)")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        wq_avgs: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for r in results:
            diag = r.get('diagnostics', {})
            for i, wq in enumerate(diag.get('wq_margins', [])):
                for abbrev in ['BRI', 'FRE', 'IND']:
                    if abbrev in wq:
                        m1, m2 = wq[abbrev]
                        wq_avgs[i][abbrev].append(m1 + m2)
        if not wq_avgs:
            print(f"\n  Scenario {scenario}: no WQ data")
            continue
        print(f"\n  Scenario {scenario}:")
        for abbrev in ['BRI', 'FRE', 'IND']:
            values_by_wq = []
            for wq_idx in sorted(wq_avgs.keys()):
                vals = wq_avgs[wq_idx].get(abbrev, [])
                if vals:
                    values_by_wq.append(sum(vals) / len(vals))
                else:
                    values_by_wq.append(None)
            parts = []
            for idx, v in enumerate(values_by_wq):
                if v is not None:
                    parts.append(f"WQ{idx+1}={v:+.1f}")
                else:
                    parts.append(f"WQ{idx+1}=n/a")
            if len(values_by_wq) >= 2:
                valid = [v for v in values_by_wq if v is not None]
                if len(valid) >= 2:
                    trend = valid[-1] - valid[0]
                    direction = "IMPROVING" if trend > 0 else "DECLINING" if trend < 0 else "FLAT"
                    parts.append(f"({direction} {trend:+.1f})")
            print(f"    {abbrev}: {' -> '.join(parts)}")


def _print_resource_analysis(all_results, by_scenario) -> None:
    print(f"\n{'=' * 70}")
    print("  AVERAGE RESOURCES AT GAME END")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        res_totals: Dict[str, List[int]] = defaultdict(list)
        for r in results:
            diag = r.get('diagnostics', {})
            for f in FACTIONS:
                val = diag.get('final_resources', {}).get(f, 0)
                res_totals[f].append(val)
        if not res_totals:
            continue
        print(f"\n  Scenario {scenario}:")
        for f in FACTIONS:
            vals = res_totals[f]
            if vals:
                avg = sum(vals) / len(vals)
                lo, hi = min(vals), max(vals)
                print(f"    {FACTION_ABBREV[f]}: avg={avg:.1f}  min={lo}  max={hi}")
    res_totals_all: Dict[str, List[int]] = defaultdict(list)
    for r in all_results:
        diag = r.get('diagnostics', {})
        for f in FACTIONS:
            val = diag.get('final_resources', {}).get(f, 0)
            res_totals_all[f].append(val)
    print(f"\n  Overall:")
    for f in FACTIONS:
        vals = res_totals_all[f]
        if vals:
            avg = sum(vals) / len(vals)
            print(f"    {FACTION_ABBREV[f]}: avg={avg:.1f}")


def _print_pass_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  PASS ANALYSIS")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        print(f"\n  Scenario {scenario}:")
        print(f"  {'-' * 66}")
        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            total_eligible = total_passes = 0
            reason_counts: Counter[str] = Counter()
            passes_1st = passes_2nd = eligible_1st = eligible_2nd = 0
            all_streaks: List[int] = []
            max_streaks: List[int] = []
            for r in results:
                diag = r.get('diagnostics', {})
                et = diag.get('eligible_turns', {}).get(f, {})
                pd = diag.get('passes', {}).get(f, {})
                total_eligible += et.get('total', 0)
                total_passes += pd.get('total', 0)
                eligible_1st += et.get('as_1st', 0)
                eligible_2nd += et.get('as_2nd', 0)
                passes_1st += pd.get('as_1st', 0)
                passes_2nd += pd.get('as_2nd', 0)
                for key in PASS_REASON_KEYS:
                    reason_counts[key] += pd.get(key, 0)
                all_streaks.extend(pd.get('streaks', []))
                ms = pd.get('max_streak', 0)
                if ms > 0:
                    max_streaks.append(ms)
            pass_rate = total_passes / total_eligible * 100 if total_eligible else 0
            pass_1st_rate = passes_1st / eligible_1st * 100 if eligible_1st else 0
            pass_2nd_rate = passes_2nd / eligible_2nd * 100 if eligible_2nd else 0
            avg_streak = sum(all_streaks) / len(all_streaks) if all_streaks else 0
            max_streak = max(max_streaks) if max_streaks else 0
            avg_max_streak = sum(max_streaks) / len(max_streaks) if max_streaks else 0
            flag = " *** HIGH PASS RATE ***" if pass_rate > 40 else ""
            print(f"\n    {abbrev}: {total_passes}/{total_eligible} eligible turns passed"
                  f" ({pass_rate:.1f}%){flag}")
            if total_passes > 0:
                print(f"      By reason:")
                for key in PASS_REASON_KEYS:
                    cnt = reason_counts[key]
                    if cnt > 0:
                        pct = cnt / total_passes * 100
                        print(f"        {key:<20} {cnt:>4} ({pct:.1f}%)")
            print(f"      As 1st eligible: {passes_1st}/{eligible_1st}"
                  f" ({pass_1st_rate:.1f}%)")
            print(f"      As 2nd eligible: {passes_2nd}/{eligible_2nd}"
                  f" ({pass_2nd_rate:.1f}%)")
            print(f"      Consecutive pass streaks: avg={avg_streak:.1f}"
                  f"  max={max_streak}  avg-max={avg_max_streak:.1f}")

        print(f"\n  Cross-faction pass rate comparison (Scenario {scenario}):")
        print(f"  {'Faction':<10} {'Pass Rate':>10} {'Resource':>10} {'No Cmd':>10} {'Flag':>12}")
        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            total_eligible = total_passes = res_gate = no_cmd = 0
            for r in results:
                diag = r.get('diagnostics', {})
                et = diag.get('eligible_turns', {}).get(f, {})
                pd = diag.get('passes', {}).get(f, {})
                total_eligible += et.get('total', 0)
                total_passes += pd.get('total', 0)
                res_gate += pd.get('resource_gate', 0)
                no_cmd += pd.get('no_valid_command', 0)
            rate = total_passes / total_eligible * 100 if total_eligible else 0
            rg_pct = res_gate / total_passes * 100 if total_passes else 0
            nc_pct = no_cmd / total_passes * 100 if total_passes else 0
            flag = "ISSUE?" if rate > 40 else ""
            print(f"  {abbrev:<10} {rate:>9.1f}% {rg_pct:>9.1f}% {nc_pct:>9.1f}%"
                  f" {flag:>12}")


def _print_pieces_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  PIECES ON MAP AT GAME END")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        piece_totals: Dict[str, List[int]] = defaultdict(list)
        for r in results:
            diag = r.get('diagnostics', {})
            for f in FACTIONS:
                val = diag.get('total_pieces_on_map', {}).get(f, 0)
                piece_totals[f].append(val)
        if not piece_totals:
            continue
        print(f"\n  Scenario {scenario}:")
        for f in FACTIONS:
            vals = piece_totals[f]
            if vals:
                avg = sum(vals) / len(vals)
                print(f"    {FACTION_ABBREV[f]}: avg={avg:.1f}  min={min(vals)}  max={max(vals)}")


def _print_treaty_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 70}")
    print("  TREATY OF ALLIANCE")
    print(f"{'=' * 70}")
    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        played_count = 0
        card_numbers: List[int] = []
        for r in results:
            diag = r.get('diagnostics', {})
            if diag.get('treaty_played'):
                played_count += 1
                cn = diag.get('treaty_card_number')
                if cn is not None:
                    card_numbers.append(cn)
        total = len(results)
        pct = played_count / total * 100 if total else 0
        avg_card = sum(card_numbers) / len(card_numbers) if card_numbers else 0
        print(f"\n  Scenario {scenario}: played in {played_count}/{total} games ({pct:.1f}%)")
        if card_numbers:
            print(f"    Average card #: {avg_card:.1f}"
                  f"  earliest: {min(card_numbers)}  latest: {max(card_numbers)}")


def _print_all_diagnostics(all_results, by_scenario) -> None:
    _print_victory_margin_analysis(by_scenario)
    _print_both_conditions_analysis(by_scenario)
    _print_margin_trends(by_scenario)
    _print_resource_analysis(all_results, by_scenario)
    _print_treaty_analysis(by_scenario)
    _print_pieces_analysis(by_scenario)
    _print_pass_analysis(by_scenario)


# ===========================================================================
# LARGE MODE: Comprehensive summary printing (Sections A-E)
# ===========================================================================

def _safe_avg(vals: list, default=0.0) -> float:
    return sum(vals) / len(vals) if vals else default


def _safe_pct(num: int, denom: int) -> float:
    return num / denom * 100.0 if denom else 0.0


# --- A. WINNERS TABLE ------------------------------------------------------

def _print_winners_table(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 74}")
    print("  A. WINNERS TABLE")
    print(f"{'=' * 74}")

    for label, results in [*[(f"Scenario {s}", by_scenario[s]) for s in SCENARIOS],
                           ("Overall", all_results)]:
        total = len(results)
        if total == 0:
            continue
        # Tally by faction × victory_type
        vc_wins: Counter[str] = Counter()
        fs_wins: Counter[str] = Counter()
        unresolved = 0
        crashes = 0

        for r in results:
            ld = r.get("large_data", {})
            winner = r.get("winner")
            end_reason = r.get("end_reason")
            vtype = ld.get("victory_type")

            if end_reason in ("CRASH", "INTERACTIVE_PROMPT", "TIMEOUT"):
                crashes += 1
                continue
            if not winner or winner == "UNKNOWN":
                unresolved += 1
                continue
            if vtype == "victory_condition":
                vc_wins[winner] += 1
            elif vtype == "final_scoring":
                fs_wins[winner] += 1
            else:
                # Fallback: count as VC
                vc_wins[winner] += 1

        print(f"\n  {label} ({total} games):")
        print(f"  {'Faction':<12} {'VC Wins':>8} {'FS Wins':>8} {'Total':>7} {'Pct':>7}")
        print(f"  {'-' * 44}")
        for f in FACTIONS:
            vc = vc_wins.get(f, 0)
            fs = fs_wins.get(f, 0)
            t = vc + fs
            pct = _safe_pct(t, total)
            if t > 0:
                print(f"  {f:<12} {vc:>8} {fs:>8} {t:>7} {pct:>6.1f}%")
        if unresolved:
            print(f"  {'Unresolved':<12} {'-':>8} {'-':>8} {unresolved:>7}"
                  f" {_safe_pct(unresolved, total):>6.1f}%")
        if crashes:
            print(f"  {'Errors':<12} {'-':>8} {'-':>8} {crashes:>7}"
                  f" {_safe_pct(crashes, total):>6.1f}%")


# --- B. AVERAGE GAME LENGTH -----------------------------------------------

def _print_avg_game_length(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 74}")
    print("  B. AVERAGE GAME LENGTH")
    print(f"{'=' * 74}")
    print(f"  {'Scenario':<12} {'Avg Cards':>10} {'Avg WQ':>8} {'Avg End Year':>14}")
    print(f"  {'-' * 46}")

    for label, results in [*[(s, by_scenario[s]) for s in SCENARIOS],
                           ("Overall", all_results)]:
        cards_list = []
        wq_list = []
        year_list = []
        for r in results:
            cards_list.append(r.get("cards_played", 0))
            ld = r.get("large_data", {})
            wq_list.append(ld.get("wq_count", 0))
            ey = ld.get("ending_campaign_year")
            if ey:
                try:
                    year_list.append(int(ey))
                except (ValueError, TypeError):
                    pass
        avg_c = _safe_avg(cards_list)
        avg_wq = _safe_avg(wq_list)
        avg_y = _safe_avg(year_list) if year_list else 0
        year_str = f"{avg_y:.1f}" if avg_y else "n/a"
        print(f"  {label:<12} {avg_c:>10.1f} {avg_wq:>8.1f} {year_str:>14}")


# --- C. FACTION PERFORMANCE -----------------------------------------------

def _print_faction_performance(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 90}")
    print("  C. FACTION PERFORMANCE")
    print(f"{'=' * 90}")

    for label, results in [*[(f"Scenario {s}", by_scenario[s]) for s in SCENARIOS],
                           ("Overall", all_results)]:
        total = len(results)
        if total == 0:
            continue
        print(f"\n  {label} ({total} games):")
        print(f"  {'Fact':<5} {'WinRate':>8} {'AvgMargin':>14} {'TopCmd':>10}"
              f" {'PassRate':>9} {'AvgRes':>7} {'AvgPcs':>7} {'AvgEvents':>10}")
        print(f"  {'-' * 72}")

        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            wins = sum(1 for r in results if r.get("winner") == f)
            win_rate = _safe_pct(wins, total)

            # Average final margins
            m1s = []
            m2s = []
            for r in results:
                ld = r.get("large_data", {})
                fm = ld.get("final_margins", {}).get(abbrev)
                if fm and len(fm) == 2:
                    m1s.append(fm[0])
                    m2s.append(fm[1])
            avg_m1 = _safe_avg(m1s)
            avg_m2 = _safe_avg(m2s)

            # Most common command
            all_cmds: Counter[str] = Counter()
            total_eligible = 0
            total_passes = 0
            total_events = 0
            total_res = []
            total_pcs = []

            for r in results:
                ld = r.get("large_data", {})
                fa = ld.get("faction_actions", {}).get(f, {})
                for cmd, cnt in fa.get("commands", {}).items():
                    all_cmds[cmd] += cnt
                total_passes += fa.get("passes_total", 0)
                total_events += fa.get("events_count", 0)

                # From diagnostics
                diag = r.get("diagnostics", {})
                et = diag.get("eligible_turns", {}).get(f, {})
                total_eligible += et.get("total", 0)

                # Resources at end
                res_val = diag.get("final_resources", {}).get(f, 0)
                total_res.append(res_val)

                # Pieces at end
                pcs_val = diag.get("total_pieces_on_map", {}).get(f, 0)
                total_pcs.append(pcs_val)

            top_cmd = all_cmds.most_common(1)[0][0] if all_cmds else "n/a"
            pass_rate = _safe_pct(total_passes, total_eligible)
            avg_res = _safe_avg(total_res)
            avg_pcs = _safe_avg(total_pcs)
            avg_evts = total_events / total if total else 0

            print(f"  {abbrev:<5} {win_rate:>7.1f}% ({avg_m1:+.0f},{avg_m2:+.0f})"
                  f"      {top_cmd:>10} {pass_rate:>8.1f}% {avg_res:>7.1f}"
                  f" {avg_pcs:>7.1f} {avg_evts:>10.1f}")


# --- D. GAME DYNAMICS ------------------------------------------------------

def _print_game_dynamics(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 74}")
    print("  D. GAME DYNAMICS")
    print(f"{'=' * 74}")

    # Average victory turn for non-deck-exhaustion games
    vc_cards = [r["cards_played"] for r in all_results
                if r.get("large_data", {}).get("victory_type") == "victory_condition"]
    if vc_cards:
        print(f"\n  Average victory turn (VC wins only): {_safe_avg(vc_cards):.1f} cards")

    # WQ leadership: who leads at each WQ?
    print(f"\n  WQ Leadership (faction closest to victory at each WQ check):")
    max_wq = 0
    for r in all_results:
        ld = r.get("large_data", {})
        n = len(ld.get("wq_snapshots", []))
        if n > max_wq:
            max_wq = n

    if max_wq > 0:
        # Header
        hdr = f"  {'Faction':<8}"
        for wqi in range(1, max_wq + 1):
            hdr += f"  {'WQ' + str(wqi):>6}"
        print(hdr)
        print(f"  {'-' * (8 + 8 * max_wq)}")

        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            row = f"  {abbrev:<8}"
            for wqi in range(max_wq):
                lead_count = 0
                total_with_wq = 0
                for r in all_results:
                    ld = r.get("large_data", {})
                    snaps = ld.get("wq_snapshots", [])
                    if wqi >= len(snaps):
                        continue
                    total_with_wq += 1
                    snap = snaps[wqi]
                    marg = snap.get("margins", {})
                    # Leader = faction with highest sum of margins
                    best_f = None
                    best_sum = float('-inf')
                    for fa in FACTIONS:
                        fa_abbrev = FACTION_ABBREV[fa]
                        ms = marg.get(fa_abbrev, [0, 0])
                        s = ms[0] + ms[1]
                        if s > best_sum:
                            best_sum = s
                            best_f = fa
                    if best_f == f:
                        lead_count += 1
                pct = _safe_pct(lead_count, total_with_wq)
                row += f"  {pct:>5.0f}%"
            print(row)

    # Treaty of Alliance timing
    toa_cards = []
    toa_count = 0
    for r in all_results:
        ld = r.get("large_data", {})
        tc = ld.get("_treaty_card_number")
        if tc:
            toa_cards.append(tc)
            toa_count += 1
        elif ld.get("wq_snapshots"):
            # Check snapshots for treaty status
            for snap in ld.get("wq_snapshots", []):
                if snap.get("treaty_status"):
                    toa_count += 1
                    break

    total = len(all_results)
    toa_pct = _safe_pct(toa_count, total)
    avg_toa_card = _safe_avg(toa_cards)
    print(f"\n  Treaty of Alliance:")
    print(f"    Fires in {toa_count}/{total} games ({toa_pct:.1f}%)")
    if toa_cards:
        print(f"    Average card #: {avg_toa_card:.1f}"
              f"  earliest: {min(toa_cards)}  latest: {max(toa_cards)}")


# --- E. BALANCE INDICATORS -------------------------------------------------

def _print_balance_indicators(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    print(f"\n{'=' * 74}")
    print("  E. BALANCE INDICATORS")
    print(f"{'=' * 74}")

    # Faction Dominance Index: % of WQ checks where both conditions positive
    print(f"\n  Faction Dominance Index (% of WQ checks with both conditions > 0):")
    total_checks = 0
    both_pos: Counter[str] = Counter()
    for r in all_results:
        ld = r.get("large_data", {})
        for snap in ld.get("wq_snapshots", []):
            total_checks += 1
            marg = snap.get("margins", {})
            for abbrev in ['BRI', 'PAT', 'FRE', 'IND']:
                ms = marg.get(abbrev, [0, 0])
                if ms[0] > 0 and ms[1] > 0:
                    both_pos[abbrev] += 1

    if total_checks:
        for abbrev in ['BRI', 'PAT', 'FRE', 'IND']:
            pct = _safe_pct(both_pos[abbrev], total_checks)
            print(f"    {abbrev}: {both_pos[abbrev]}/{total_checks} ({pct:.1f}%)")
    else:
        print("    No WQ data available")

    # Comeback frequency: how often does WQ3 leader differ from WQ1 leader?
    comebacks = 0
    games_with_both = 0
    for r in all_results:
        ld = r.get("large_data", {})
        snaps = ld.get("wq_snapshots", [])
        if len(snaps) < 3:
            continue
        games_with_both += 1

        def _leader_at(snap):
            marg = snap.get("margins", {})
            best_f = None
            best_sum = float('-inf')
            for abbrev in ['BRI', 'PAT', 'FRE', 'IND']:
                ms = marg.get(abbrev, [0, 0])
                s = ms[0] + ms[1]
                if s > best_sum:
                    best_sum = s
                    best_f = abbrev
            return best_f

        wq1_leader = _leader_at(snaps[0])
        wq3_leader = _leader_at(snaps[2])
        if wq1_leader != wq3_leader:
            comebacks += 1

    print(f"\n  Comeback frequency (WQ3 leader differs from WQ1 leader):")
    if games_with_both:
        pct = _safe_pct(comebacks, games_with_both)
        print(f"    {comebacks}/{games_with_both} games ({pct:.1f}%)")
    else:
        print(f"    Not enough games reached WQ3")

    # Competitiveness: average margin between 1st and 2nd place at final scoring
    margins_1st_2nd = []
    for r in all_results:
        ld = r.get("large_data", {})
        if ld.get("victory_type") != "final_scoring":
            continue
        scores = ld.get("final_scores", {})
        valid_scores = sorted(
            [v for v in scores.values() if v != float('-inf')],
            reverse=True
        )
        if len(valid_scores) >= 2:
            margins_1st_2nd.append(valid_scores[0] - valid_scores[1])

    print(f"\n  Competitiveness (avg margin between 1st/2nd at final scoring):")
    if margins_1st_2nd:
        avg = _safe_avg(margins_1st_2nd)
        print(f"    Average: {avg:.1f}  ({len(margins_1st_2nd)} final-scoring games)")
    else:
        print(f"    No final-scoring games to analyze")

    # Combat summary
    print(f"\n  Combat Summary:")
    total_battles = sum(r.get("large_data", {}).get("battles_total", 0) for r in all_results)
    n_games = len(all_results) or 1
    print(f"    Total battles: {total_battles} ({total_battles / n_games:.1f}/game)")
    for f in FACTIONS:
        abbrev = FACTION_ABBREV[f]
        att = sum(r.get("large_data", {}).get("battles_as_attacker", {}).get(f, 0)
                  for r in all_results)
        print(f"    {abbrev} as attacker: {att} ({att / n_games:.1f}/game)")

    roy_loss = sum(r.get("large_data", {}).get("battle_losses", {}).get("ROYALIST", 0)
                   for r in all_results)
    reb_loss = sum(r.get("large_data", {}).get("battle_losses", {}).get("REBELLION", 0)
                   for r in all_results)
    print(f"    ROYALIST battle losses: {roy_loss} ({roy_loss / n_games:.1f}/game)")
    print(f"    REBELLION battle losses: {reb_loss} ({reb_loss / n_games:.1f}/game)")

    avg_cbc = _safe_avg([r.get("large_data", {}).get("cbc_final", 0) for r in all_results])
    avg_crc = _safe_avg([r.get("large_data", {}).get("crc_final", 0) for r in all_results])
    print(f"    Average CBC at game end: {avg_cbc:.1f}")
    print(f"    Average CRC at game end: {avg_crc:.1f}")


# ===========================================================================
# JSON serialization for large results
# ===========================================================================

def _serialize_large_results(all_results: List[Dict]) -> List[Dict]:
    """Prepare large results for JSON serialization."""
    serialisable = []
    for r in all_results:
        entry = dict(r)
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        # Remove legacy diagnostics from large output to reduce size
        entry.pop("diagnostics", None)
        # Convert sets and tuples in large_data
        ld = entry.get("large_data", {})
        # WQ snapshot margins are already lists
        # Ensure final_scores handles -inf
        fs = ld.get("final_scores", {})
        for k, v in fs.items():
            if v == float('-inf') or v == float('inf'):
                fs[k] = None
        serialisable.append(entry)
    return serialisable


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    single_mode = "--single" in sys.argv
    large_mode = "--large" in sys.argv

    # ------------------------------------------------------------------
    # Single mode
    # ------------------------------------------------------------------
    if single_mode:
        print("Running single sanity-check game: scenario=1775, seed=1 ...")
        result = run_one_game("1775", 1)
        print(f"  end_reason={result['end_reason']}, winner={result['winner']}, "
              f"cards_played={result['cards_played']}")
        if result["error"]:
            print(f"  ERROR: {result['error']}")
            if result["traceback"]:
                print(result["traceback"])
        diag = result.get('diagnostics', {})
        if diag.get('wq_margins'):
            print(f"  WQ margins: {diag['wq_margins']}")
        for f in FACTIONS:
            pd = diag.get('passes', {}).get(f, {})
            et = diag.get('eligible_turns', {}).get(f, {})
            if et.get('total', 0) > 0:
                parts = []
                for key in PASS_REASON_KEYS:
                    val = pd.get(key, 0)
                    if val > 0:
                        parts.append(f"{key}={val}")
                reason_str = ', '.join(parts) if parts else 'none'
                print(f"  {FACTION_ABBREV[f]}: {pd.get('total',0)} passes / "
                      f"{et.get('total',0)} eligible  ({reason_str})")
        print(f"  Final resources: {diag.get('final_resources', {})}")
        print(f"  Treaty played: {diag.get('treaty_played', False)}")
        print(f"  Pieces on map: {diag.get('total_pieces_on_map', {})}")
        return

    # ------------------------------------------------------------------
    # Large mode (50 seeds x 3 scenarios = 150 games)
    # ------------------------------------------------------------------
    if large_mode:
        seeds = LARGE_SEEDS_PER_SCENARIO
        total_games = len(SCENARIOS) * seeds
        print(f"Running LARGE batch: {len(SCENARIOS)} scenarios x {seeds} seeds"
              f" = {total_games} games")
        print(f"Safety limit: {CARD_SAFETY_LIMIT} cards per game\n")

        all_results: List[Dict[str, Any]] = []
        by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for scenario in SCENARIOS:
            for seed in range(1, seeds + 1):
                tag = f"[{scenario} seed={seed:>2}]"
                sys.stdout.write(f"  {tag} ... ")
                sys.stdout.flush()

                result = run_one_game(scenario, seed, detailed=True)
                all_results.append(result)
                by_scenario[scenario].append(result)

                status = result["end_reason"] or "?"
                extra = ""
                if result["winner"]:
                    extra = f" -> {result['winner']}"
                ld = result.get("large_data", {})
                vt = ld.get("victory_type", "")
                if vt:
                    extra += f" ({vt})"
                if result["error"]:
                    extra += f"  ERR: {result['error'][:60]}"
                print(f"{status} ({result['cards_played']} cards){extra}")

        # --- Print legacy per-scenario summaries ---
        for scenario in SCENARIOS:
            _print_summary(by_scenario[scenario], f"Scenario {scenario}")
        _print_summary(all_results, "Overall")

        # --- Print comprehensive summary sections A-E ---
        _print_winners_table(all_results, by_scenario)
        _print_avg_game_length(all_results, by_scenario)
        _print_faction_performance(all_results, by_scenario)
        _print_game_dynamics(all_results, by_scenario)
        _print_balance_indicators(all_results, by_scenario)

        # --- Write JSON ---
        serialisable = _serialize_large_results(all_results)
        LARGE_RESULTS_PATH.write_text(
            json.dumps(serialisable, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nFull results written to {LARGE_RESULTS_PATH}")
        return

    # ------------------------------------------------------------------
    # Default mode (20 seeds x 3 scenarios = 60 games)
    # ------------------------------------------------------------------
    seeds = SEEDS_PER_SCENARIO
    total_games = len(SCENARIOS) * seeds
    print(f"Running batch smoke test: {len(SCENARIOS)} scenarios x {seeds} seeds "
          f"= {total_games} games")
    print(f"Safety limit: {CARD_SAFETY_LIMIT} cards per game\n")

    all_results: List[Dict[str, Any]] = []
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for scenario in SCENARIOS:
        for seed in range(1, seeds + 1):
            tag = f"[{scenario} seed={seed:>2}]"
            sys.stdout.write(f"  {tag} ... ")
            sys.stdout.flush()

            result = run_one_game(scenario, seed)
            all_results.append(result)
            by_scenario[scenario].append(result)

            status = result["end_reason"] or "?"
            extra = ""
            if result["winner"]:
                extra = f" -> {result['winner']}"
            if result["error"]:
                extra += f"  ERR: {result['error'][:60]}"
            print(f"{status} ({result['cards_played']} cards){extra}")

    for scenario in SCENARIOS:
        _print_summary(by_scenario[scenario], f"Scenario {scenario}")
    _print_summary(all_results, "Overall")
    _print_all_diagnostics(all_results, by_scenario)

    # Write legacy JSON
    serialisable = []
    for r in all_results:
        entry = dict(r)
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        entry.pop("diagnostics", None)
        serialisable.append(entry)
    RESULTS_PATH.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    print(f"\nLegacy results written to {RESULTS_PATH}")

    diag_serialisable = []
    for r in all_results:
        entry = dict(r)
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        diag = entry.get("diagnostics", {})
        for f in FACTIONS:
            wq = diag.get("wq_margins", [])
            diag["wq_margins"] = [
                {k: list(v) for k, v in m.items()} for m in wq
            ]
        diag_serialisable.append(entry)
    DIAG_RESULTS_PATH.write_text(
        json.dumps(diag_serialisable, indent=2), encoding="utf-8"
    )
    print(f"Diagnostic results written to {DIAG_RESULTS_PATH}")


if __name__ == "__main__":
    main()
