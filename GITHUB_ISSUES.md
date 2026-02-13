# Suggested GitHub Issues for Claude Code Task Backlog
# =====================================================
# Copy each of these into GitHub Issues. Claude Code can then be
# pointed at them with "@claude" or they can be worked through
# sequentially in the terminal.
#
# Issues are ordered by the priority phases in CLAUDE.md.


## PHASE 1: Label Compliance

### Issue: Audit all files for non-canonical string literals
**Labels:** phase-1, audit, labels

@claude Audit every `.py` file in `lod_ai/` (excluding `rules_consts.py` itself and files in `Reference Documents/`). Find every string literal that refers to a game piece, faction, marker, leader, or space ID and verify it matches a constant defined in `lod_ai/rules_consts.py`.

Produce a report listing:
- File, line number, the offending string
- What it should be replaced with (the correct `rules_consts` constant)

Write the report to `label_audit.md` in the repo root. Do not make fixes yet — just the audit.

Reference: The canonical labels are defined in `lod_ai/rules_consts.py`. See CLAUDE.md for the full list.

---

### Issue: Fix all label violations found in audit
**Labels:** phase-1, fix, labels

@claude Using the audit in `label_audit.md`, fix every non-canonical string literal:
1. Replace string literals with the appropriate constant import from `rules_consts.py`
2. Add `from lod_ai.rules_consts import ...` where needed
3. Run `pytest -q` after each file to ensure no regressions
4. Commit per-file or per-module

If any label appears to have no matching constant in `rules_consts.py` and you believe one should exist, note it in `QUESTIONS.md` and skip that instance.

---


## PHASE 2: Card Compliance

### Issue: Full card audit — all cards vs card reference full.txt
**Labels:** phase-2, audit, cards

@claude For every card handler in `lod_ai/cards/effects/` (early_war.py, middle_war.py, late_war.py, brilliant_stroke.py, winter_quarters.py):

1. Read the handler implementation
2. Compare it line-by-line against `Reference Documents/card reference full.txt`
3. Document every mismatch in `audit_report.md` (append a new section, do not overwrite existing sections)

For each mismatch, note:
- Card number and title
- What the reference says (quote the relevant text)
- What the code does instead
- Severity (wrong behavior vs missing behavior vs crash risk)

Do not make fixes in this issue — just the audit.

---

### Issue: Fix early war card mismatches (cards in early_war.py)
**Labels:** phase-2, fix, cards

@claude Using `audit_report.md`, fix all card handler mismatches in `lod_ai/cards/effects/early_war.py`.

For each card:
1. Re-read the reference text in `Reference Documents/card reference full.txt`
2. Fix the implementation to match exactly
3. Use only constants from `rules_consts.py`
4. Use board/pieces helpers, not direct dict manipulation
5. Add a test in `lod_ai/tests/` that verifies the fix
6. Run `pytest -q` — all tests must pass

Commit per card or per small group of related cards. Reference card numbers in commit messages.

If any card text is ambiguous, add the question to `QUESTIONS.md` and skip that card.

---

### Issue: Fix middle war card mismatches (cards in middle_war.py)
**Labels:** phase-2, fix, cards

(Same instructions as early war, targeting `lod_ai/cards/effects/middle_war.py`)

---

### Issue: Fix late war card mismatches (cards in late_war.py)
**Labels:** phase-2, fix, cards

(Same instructions as early war, targeting `lod_ai/cards/effects/late_war.py`)

---

### Issue: Fix Brilliant Stroke / Treaty of Alliance
**Labels:** phase-2, fix, cards, complex

@claude The Brilliant Stroke and Treaty of Alliance mechanics are known to be incomplete. Reference `audit_report.md` and `Reference Documents/card reference full.txt` (cards 105-109) plus `Manual Ch 6.txt` for the full rules.

This is complex — it involves interrupt mechanics, a trump chain, leader involvement, eligibility resets, and card return. Implement it step by step:
1. Document exactly what the rules require
2. Identify what's currently implemented vs missing
3. Implement missing pieces one at a time with tests
4. If anything is ambiguous, add to `QUESTIONS.md`

---


## PHASE 3: Rules Compliance

### Issue: Verify British bot flowchart implementation
**Labels:** phase-3, bots, british

@claude Compare `lod_ai/bots/british_bot.py` against `Reference Documents/british bot flowchart and reference.txt` node by node.

For each flowchart node (B1, B2, B3, etc.):
1. Verify the decision condition matches
2. Verify the edges/branches match
3. Verify the action logic matches (for process nodes)
4. Check that tie-breaking and priority ordering match exactly

Document mismatches, fix them, and add tests. Same rules: use `rules_consts.py` labels, don't guess on ambiguities.

---

### Issue: Verify Patriot bot flowchart implementation
**Labels:** phase-3, bots, patriot

(Same approach, targeting `lod_ai/bots/patriot.py` vs `Reference Documents/patriot bot flowchart and reference.txt`)

---

### Issue: Verify Indian bot flowchart implementation
**Labels:** phase-3, bots, indian

(Same approach, targeting `lod_ai/bots/indians.py` vs `Reference Documents/indian bot flowchart and reference.txt`)

---

### Issue: Verify French bot flowchart implementation
**Labels:** phase-3, bots, french

(Same approach, targeting `lod_ai/bots/french.py` vs `Reference Documents/french bot flowchart and reference.txt`)

---

### Issue: Verify commands against Manual Ch 3
**Labels:** phase-3, commands

@claude Compare each command implementation in `lod_ai/commands/` against the corresponding rules in `Reference Documents/Manual Ch 3.txt`. Verify:
- Battle, March, Muster, Rally, Garrison, Gather, Scout
- Rabble-Rousing, Raid
- All special activity implementations in `lod_ai/special_activities/`

Document and fix mismatches. Add tests.

---

### Issue: Verify game engine flow against sequence of play
**Labels:** phase-3, engine

@claude Compare `lod_ai/engine.py` and `lod_ai/dispatcher.py` against `Reference Documents/Manual Ch 2.txt` for:
- Sequence of play
- Faction eligibility tracking (eligible, ineligible next card, ineligible through next card)
- Event vs Command vs Pass decision flow
- Card draw and deck management
- 1st/2nd eligible mechanics

---

### Issue: Verify victory conditions
**Labels:** phase-3, victory

@claude Compare `lod_ai/victory.py` against `Reference Documents/Manual Ch 7.txt`. Verify all victory condition checks are correct.

---

### Issue: Verify year-end / Winter Quarters
**Labels:** phase-3, year-end

@claude Compare `lod_ai/util/year_end.py` against the Winter Quarters rules in the manual and `Reference Documents/card reference full.txt` (cards 97-104). Verify all year-end procedures are correctly implemented.

---

### Issue: Verify scenario setup
**Labels:** phase-3, setup

@claude Compare `lod_ai/state/setup_state.py` and `data/*.json` against:
- `Reference Documents/setup instructions.txt`
- `Reference Documents/1775 Scenario Reference.txt`
- `Reference Documents/1776 Scenario Reference.txt`
- `Reference Documents/1778 Scenario Reference.txt`

Verify all initial piece placements, resource levels, support/opposition levels, and other setup values.

---

### Issue: Build comprehensive test suite
**Labels:** phase-3, testing

@claude The current test suite has 86 tests but many are thin. Build out comprehensive tests:

1. For each bot flowchart, test each decision node with state that triggers each branch
2. For each card, test both shaded and unshaded effects
3. For each command, test legal/illegal usage and edge cases
4. For game engine flow, test eligibility transitions across multiple cards
5. For victory, test each faction's victory condition at boundary values

Tests should be grounded in the Reference Documents — verify that the code produces the outcome the rules specify, not just that the code doesn't crash.

---


## PHASE 4: UI

### Issue: Ensure zero-player mode works end to end
**Labels:** phase-4, ui

@claude Run a zero-player game (all four factions bot-controlled) from start through at least 5 full card plays. Fix any crashes, infinite loops, or incorrect behavior. The game should be able to run unattended with all decisions made by the bots.

---

### Issue: Clean up CLI for 0-3 human player modes
**Labels:** phase-4, ui

@claude Review `lod_ai/interactive_cli.py` and ensure:
- 0 human players: fully automated, game runs to completion or a reasonable stopping point
- 1-3 human players: human-controlled factions get menu prompts, bot factions run automatically
- Game state display is clear and complete after each action
- Illegal moves are rejected with helpful messages
- No free-text input required for game actions — everything is menu-driven
