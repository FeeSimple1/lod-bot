#!/usr/bin/env python3
"""
Batch smoke test with diagnostic data capture.

Run 20 zero-player games per scenario (60 total) and capture detailed
diagnostic data including victory margins, pass behavior, resource levels,
and Treaty of Alliance timing.

Usage:
    python -m lod_ai.tools.batch_smoke          # full 60-game batch
    python -m lod_ai.tools.batch_smoke --single  # single game sanity check

Records per-game results and prints an aggregate summary table plus
diagnostic analysis sections.

Writes:
  - batch_results.json              (legacy format)
  - batch_results_diagnostic.json   (enhanced with diagnostics)
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

# Redirect stdin to /dev/null so any accidental interactive prompt
# raises EOFError instead of blocking.
_DEVNULL = open(os.devnull, "r")
sys.stdin = _DEVNULL

from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.victory import _summarize_board, _british_margin, _patriot_margin, _french_margin, _indian_margin
from lod_ai import rules_consts as C

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCENARIOS = ["1775", "1776", "1778"]
SEEDS_PER_SCENARIO = 20
CARD_SAFETY_LIMIT = 200
RESULTS_PATH = Path(__file__).resolve().parent / "batch_results.json"
DIAG_RESULTS_PATH = Path(__file__).resolve().parent / "batch_results_diagnostic.json"
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


# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------

def _empty_faction_passes() -> Dict[str, Any]:
    """Return a fresh pass-tracking dict for one faction."""
    return {
        'total': 0,
        'resource_gate': 0,
        'no_valid_command': 0,
        'illegal_action': 0,
        'bot_error': 0,
        'other': 0,
        'as_1st': 0,
        'as_2nd': 0,
        'as_3rd_plus': 0,
        'current_streak': 0,
        'max_streak': 0,
        'streaks': [],
    }


def _empty_faction_eligible() -> Dict[str, int]:
    """Return a fresh eligible-turn tracking dict for one faction."""
    return {
        'total': 0,
        'as_1st': 0,
        'as_2nd': 0,
        'as_3rd_plus': 0,
        'acted': 0,
        'passed': 0,
    }


def _empty_diagnostics() -> Dict[str, Any]:
    """Create an empty per-game diagnostics structure."""
    return {
        'wq_margins': [],
        'passes': {f: _empty_faction_passes() for f in FACTIONS},
        'eligible_turns': {f: _empty_faction_eligible() for f in FACTIONS},
        'final_resources': {},
        'treaty_played': False,
        'treaty_card_number': None,
        'total_pieces_on_map': {},
    }


_VICTORY_CHECK_RE = re.compile(
    r'Victory Check\s+[–—-]\s+'
    r'BRI\((-?\d+),(-?\d+)\)\s+'
    r'PAT\((-?\d+),(-?\d+)\)\s+'
    r'FRE\((-?\d+),(-?\d+)\)\s+'
    r'IND\((-?\d+),(-?\d+)\)'
)


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
    """Scan new history entries for victory checks and Treaty events.
    Returns new offset."""
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
    """Finalize diagnostic data at end of game."""
    # Close out pass streaks
    for f in FACTIONS:
        pd = diag['passes'][f]
        streak = pd['current_streak']
        if streak > 0:
            pd['streaks'].append(streak)
            pd['current_streak'] = 0
        pd['max_streak'] = max(pd['streaks']) if pd['streaks'] else 0

    # Final resources
    diag['final_resources'] = dict(state.get('resources', {}))

    # Treaty status (double-check from state)
    if not diag['treaty_played']:
        diag['treaty_played'] = bool(
            state.get('toa_played') or state.get('treaty_of_alliance')
        )

    # Total pieces on map
    diag['total_pieces_on_map'] = _count_pieces_on_map(state)


# ---------------------------------------------------------------------------
# Single-game runner
# ---------------------------------------------------------------------------

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


def run_one_game(scenario: str, seed: int) -> Dict[str, Any]:
    """Run a single zero-player game with diagnostic data capture."""
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

    try:
        state = build_state(scenario, seed=seed)
        engine = Engine(initial_state=state, use_cli=False)
        engine.set_human_factions([])  # all bots

        cards_played = 0
        history_offset = len(engine.state.get('history', []))

        while cards_played < CARD_SAFETY_LIMIT:
            card = engine.draw_card()
            if card is None:
                result["end_reason"] = "DECK_EXHAUSTED"
                break

            engine.play_card(card, human_decider=None)
            cards_played += 1

            # Process turn log for pass/eligible tracking
            _process_card_turn_log(diag, engine.state)

            # Scan history for victory margins and treaty events
            history = engine.state.get('history', [])
            history_offset = _scan_history_for_events(
                diag, history, history_offset, cards_played
            )

            winner = _check_game_over(engine.state)
            if winner:
                result["winner"] = winner
                result["end_reason"] = "WINNER"
                break
        else:
            result["end_reason"] = "TIMEOUT"

        result["cards_played"] = cards_played
        _finalize_diagnostics(diag, engine.state)

    except EOFError:
        result["end_reason"] = "INTERACTIVE_PROMPT"
        result["error"] = "Engine tried to read interactive input in zero-player mode"
        result["traceback"] = traceback.format_exc()
    except Exception as exc:
        result["end_reason"] = "CRASH"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()

    result["diagnostics"] = diag
    return result


# ---------------------------------------------------------------------------
# Summary table (legacy)
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]], label: str) -> None:
    """Print a summary table for a list of game results."""
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


# ---------------------------------------------------------------------------
# Diagnostic analysis
# ---------------------------------------------------------------------------

def _print_victory_margin_analysis(by_scenario: Dict[str, List[Dict]]) -> None:
    """Print average victory margins per faction per scenario at each WQ check."""
    print(f"\n{'=' * 70}")
    print("  VICTORY MARGIN ANALYSIS")
    print(f"{'=' * 70}")

    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        # Gather margins by WQ index
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
    """Print how often each faction had BOTH victory conditions positive."""
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
    """Print whether non-Patriot margins are improving or declining over the game."""
    print(f"\n{'=' * 70}")
    print("  MARGIN TRENDS (non-Patriot sum-of-margins by WQ)")
    print(f"{'=' * 70}")

    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        # For each game, track how non-Patriot combined margins change
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


def _print_resource_analysis(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    """Print average resources per faction at game end."""
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

    # Overall
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
    """Print detailed pass analysis per faction per scenario."""
    print(f"\n{'=' * 70}")
    print("  PASS ANALYSIS")
    print(f"{'=' * 70}")

    for scenario in SCENARIOS:
        results = by_scenario.get(scenario, [])
        print(f"\n  Scenario {scenario}:")
        print(f"  {'-' * 66}")

        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            total_eligible = 0
            total_passes = 0
            reason_counts: Counter[str] = Counter()
            passes_1st = 0
            passes_2nd = 0
            eligible_1st = 0
            eligible_2nd = 0
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

            # Breakdown by reason
            if total_passes > 0:
                print(f"      By reason:")
                for key in PASS_REASON_KEYS:
                    cnt = reason_counts[key]
                    if cnt > 0:
                        pct = cnt / total_passes * 100
                        print(f"        {key:<20} {cnt:>4} ({pct:.1f}%)")

            # 1st vs 2nd eligible
            print(f"      As 1st eligible: {passes_1st}/{eligible_1st}"
                  f" ({pass_1st_rate:.1f}%)")
            print(f"      As 2nd eligible: {passes_2nd}/{eligible_2nd}"
                  f" ({pass_2nd_rate:.1f}%)")

            # Streak analysis
            print(f"      Consecutive pass streaks: avg={avg_streak:.1f}"
                  f"  max={max_streak}  avg-max={avg_max_streak:.1f}")

        # Cross-faction comparison
        print(f"\n  Cross-faction pass rate comparison (Scenario {scenario}):")
        print(f"  {'Faction':<10} {'Pass Rate':>10} {'Resource':>10} {'No Cmd':>10} {'Flag':>12}")
        for f in FACTIONS:
            abbrev = FACTION_ABBREV[f]
            total_eligible = 0
            total_passes = 0
            res_gate = 0
            no_cmd = 0
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
    """Print average pieces on map at game end per faction."""
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
    """Print Treaty of Alliance statistics."""
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


def _print_all_diagnostics(all_results: List[Dict], by_scenario: Dict[str, List[Dict]]) -> None:
    """Print all diagnostic analysis sections."""
    _print_victory_margin_analysis(by_scenario)
    _print_both_conditions_analysis(by_scenario)
    _print_margin_trends(by_scenario)
    _print_resource_analysis(all_results, by_scenario)
    _print_treaty_analysis(by_scenario)
    _print_pieces_analysis(by_scenario)
    _print_pass_analysis(by_scenario)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    single_mode = "--single" in sys.argv

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

    print(f"Running batch smoke test: {len(SCENARIOS)} scenarios x {SEEDS_PER_SCENARIO} seeds "
          f"= {len(SCENARIOS) * SEEDS_PER_SCENARIO} games")
    print(f"Safety limit: {CARD_SAFETY_LIMIT} cards per game\n")

    all_results: List[Dict[str, Any]] = []
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for scenario in SCENARIOS:
        for seed in range(1, SEEDS_PER_SCENARIO + 1):
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

    # Per-scenario summaries
    for scenario in SCENARIOS:
        _print_summary(by_scenario[scenario], f"Scenario {scenario}")

    # Overall summary
    _print_summary(all_results, "Overall")

    # Diagnostic analysis sections
    _print_all_diagnostics(all_results, by_scenario)

    # Write legacy JSON results
    serialisable = []
    for r in all_results:
        entry = dict(r)
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        # Don't include full diagnostics in legacy format
        entry.pop("diagnostics", None)
        serialisable.append(entry)

    RESULTS_PATH.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    print(f"\nLegacy results written to {RESULTS_PATH}")

    # Write enhanced diagnostic JSON
    diag_serialisable = []
    for r in all_results:
        entry = dict(r)
        if entry.get("traceback"):
            entry["traceback"] = entry["traceback"][:2000]
        # Convert pass streaks lists and tuples for JSON serialization
        diag = entry.get("diagnostics", {})
        for f in FACTIONS:
            pd = diag.get("passes", {}).get(f, {})
            # streaks are already lists of ints, fine for JSON
            wq = diag.get("wq_margins", [])
            # wq margins contain tuples that need to be lists for JSON
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
