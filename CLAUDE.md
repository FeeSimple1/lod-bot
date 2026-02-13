# CLAUDE.md — Liberty or Death Bot Engine

## Project Summary

This is an automation engine for the non-player bot flowcharts in **Liberty or Death** (GMT Games, COIN Series Vol. V). It handles 0–4 bot-controlled factions (British, Patriots, Indians, French) via an interactive CLI. The goal is faithful implementation of the published flowcharts — not a variation, not a reinterpretation, not a "simplified" version.

**Language:** Python (100%). ~15,400 LOC across ~60 files.
**Tests:** pytest. 86 tests currently passing.
**No external game references.** Do not consult BoardGameGeek, other COIN games, other GMT titles, or any historical sources outside the Reference Documents.

---

## Source of Truth (Strict Hierarchy)

These are **read-only**. Never modify them. All other code must conform to them.

### 1. `lod_ai/rules_consts.py` — Canonical Labels
Every string label for factions, pieces, markers, leaders, and space IDs used anywhere in the codebase **must** come from this file. If a label doesn't exist here, it is wrong.

**Canonical piece tags:**
```
British_Regular, British_Tory, British_Fort, British_Regular_Unavailable, British_Tory_Unavailable
Patriot_Continental, Patriot_Militia_A, Patriot_Militia_U, Patriot_Fort
French_Regular, French_Regular_Unavailable
Indian_WP_A, Indian_WP_U
Village, Squadron, Blockade, Propaganda, Raid
```

**Faction strings:** `BRITISH`, `PATRIOTS`, `INDIANS`, `FRENCH`

**If you encounter a string literal in the code that doesn't match one of these** (e.g., `"Continental"`, `"Militia"`, `"British_cube"`, `"Tory"` used as a piece tag, `"fort"`, etc.), it is a bug. Replace it with the correct constant from `rules_consts.py`.

### 2. `Reference Documents/card reference full.txt` — Card Behavior
The authoritative definition of every card's unshaded and shaded effects. Card handler implementations in `lod_ai/cards/effects/` must match this file exactly — same targets, same piece types, same destinations ("to Casualties" vs "to Available" vs "remove"), same conditions.

### 3. `Reference Documents/` — Everything Else
All files in the `Reference Documents/` directory are source-of-truth materials. Always check the full directory contents rather than relying solely on this list. Key files include but are not limited to:

- `*bot flowchart and reference.txt` — Non-player decision trees (one per faction)
- `Manual Ch 1.txt` through `Manual Ch 8.txt` — Full rules
- `Manual Glossary.txt` — Definitions
- `leader_capabilities.txt` — Leader special abilities
- `1775 Scenario Reference.txt`, `1776 Scenario Reference.txt`, `1778 Scenario Reference.txt` — Setup data
- `map_base.csv` — Map topology (CSV; the only non-.txt reference file)
- `setup instructions.txt` — Scenario setup procedure
- `random spaces map.txt`, `random spaces table.txt` — Random space selection tables

If a file exists in `Reference Documents/` and is not listed above, it is still authoritative. Any file added to this directory in the future is automatically a source of truth.

All files are plain text (except `map_base.csv`). No PDFs, no images.

---

## Project Structure

```
lod_ai/
├── __init__.py, __main__.py     # Entry point: python -m lod_ai
├── rules_consts.py              # SOURCE OF TRUTH — canonical labels
├── engine.py                    # Main game loop / turn sequencing
├── interactive_cli.py           # Human player menus
├── cli_utils.py                 # CLI helper functions
├── dispatcher.py                # Routes faction turns to bot or human
├── victory.py                   # Victory condition checks
├── bots/                        # Non-player bot logic (flowcharts)
│   ├── base_bot.py              # Shared bot infrastructure
│   ├── british_bot.py           # British flowchart implementation
│   ├── patriot.py               # Patriot flowchart implementation
│   ├── indians.py               # Indian flowchart implementation
│   ├── french.py                # French flowchart implementation
│   ├── event_instructions.py    # Per-card bot special instructions
│   └── random_spaces.py         # Random space selection
├── cards/
│   ├── __init__.py              # Card registry and lookup
│   ├── data.json                # Card metadata (titles, order, icons, years)
│   └── effects/                 # Card effect handlers
│       ├── early_war.py         # Cards from 1775-1776
│       ├── middle_war.py        # Cards from 1777-1778
│       ├── late_war.py          # Cards from 1779-1780
│       ├── brilliant_stroke.py  # Brilliant Stroke / Treaty of Alliance
│       ├── winter_quarters.py   # Winter Quarters special cards
│       └── shared.py            # Common card helper functions
├── commands/                    # Game operations
│   ├── battle.py, march.py, muster.py, rally.py
│   ├── garrison.py, gather.py, scout.py
│   ├── rabble_rousing.py, raid.py
│   ├── hortelez.py              # Hortalez et Cie (French supply)
│   └── french_agent_mobilization.py
├── special_activities/          # Special activities per faction
│   ├── common_cause.py, skirmish.py, naval_pressure.py  # British
│   ├── partisans.py, persuasion.py, common_cause.py     # Patriot (shares Common Cause)
│   ├── war_path.py, trade.py, plunder.py                # Indian
│   └── preparer.py                                       # French
├── board/                       # Board state management
│   ├── pieces.py                # Piece placement, removal, movement
│   └── control.py               # Space control calculations
├── state/
│   ├── setup_state.py           # Scenario initialization
│   └── map_loader.py            # Map data loading
├── map/
│   ├── adjacency.py             # Adjacency calculations
│   ├── control.py               # Map-level control queries
│   └── data/map.json            # Processed map data
├── economy/
│   └── resources.py             # Resource tracking
├── leaders/
│   └── __init__.py              # Leader placement, movement, capabilities
├── util/                        # Shared utilities
│   ├── caps.py                  # Piece cap enforcement
│   ├── eligibility.py           # Faction eligibility tracking
│   ├── year_end.py              # Year-end / Winter Quarters procedures
│   ├── naval.py                 # Naval/squadron/blockade logic
│   ├── validate.py              # State validation
│   ├── normalize_state.py       # State normalization
│   ├── piece_kinds.py           # Piece type queries
│   ├── loss_mod.py              # Loss modification
│   ├── free_ops.py              # Free operation handling
│   ├── history.py               # Game history tracking
│   └── adjacency.py, normalize.py
├── tools/
│   ├── card_audit_fix.py        # Audit tool for card compliance
│   └── smoke_test.py            # Quick smoke test
└── tests/                       # pytest test suite
    ├── test_*.py                # Various test files
    └── commands/test_*.py       # Command-specific tests
```

---

## Known Issues (from ChatGPT era)

The file `audit_report.md` in the repo root documents **dozens** of known card implementation bugs. The most pervasive patterns are:

1. **Wrong labels / string literals.** ChatGPT repeatedly invented piece tags like `"Continental"`, `"Militia"`, `"Tory"`, `"fort"` instead of using the constants from `rules_consts.py`. Every string literal that refers to a game piece, faction, or marker must be checked against the canonical list above.

2. **Card effects don't match `card reference full.txt`.** Hardcoded locations instead of player/bot selection, inverted shaded/unshaded effects, wrong destinations ("to Casualties" when reference says "to Available" or vice versa), missing conditions, incomplete implementations.

3. **Eligibility field confusion.** Some cards use `ineligible_next` when the reference says "Ineligible through the next card" (which should be `ineligible_through_next`). These are different durations.

4. **Queued free ops instead of immediate execution.** Several cards queue free operations that should execute immediately per the card text.

5. **Brilliant Stroke / Treaty of Alliance incomplete.** The interrupt/trump chain, leader involvement, eligibility reset, and card return mechanics are not fully implemented.

6. **One fix introduces one new bug.** This was a persistent pattern — be vigilant about regression. Always run the full test suite after changes.

---

## Task Priorities (in order)

### Phase 1: Label Compliance
Audit every `.py` file in `lod_ai/` for string literals that should be constants from `rules_consts.py`. Fix all violations. This includes:
- Piece tags, faction names, marker names, space IDs
- Any string comparison or dictionary key that references a game concept

### Phase 2: Card Compliance
For every card handler in `lod_ai/cards/effects/`:
1. Compare implementation against `Reference Documents/card reference full.txt`
2. Document mismatches (update `audit_report.md`)
3. Fix each mismatch
4. Add/update tests that verify the fix against the reference text

### Phase 3: Rules Compliance & Functionality
- Verify bot flowchart implementations against the four `*bot flowchart and reference.txt` files
- Verify commands and special activities against `Manual Ch 3.txt` and `Manual Ch 4.txt`
- Verify game engine flow (sequence of play, eligibility, event/command choice) against `Manual Ch 2.txt`
- Verify victory conditions against `Manual Ch 7.txt`
- Verify year-end / Winter Quarters against rules
- Verify scenario setup against the scenario reference files
- Ensure zero-player mode works (all four factions bot-controlled)

### Phase 4: UI / Usability
- Clean, simple CLI that supports 0–4 human players
- Clear display of game state, current card, upcoming card
- Menu-driven choices — no free-text input for game actions
- Illegal moves rejected before committing

---

## Critical Rules

### Never Guess
If the Reference Documents are ambiguous, contradictory, or silent on a question:
1. **STOP** working on that specific issue
2. Document the question in `QUESTIONS.md` (create if missing), including:
   - What you were trying to implement
   - What the reference says (quote it)
   - What's ambiguous or contradictory
   - What options you see
3. Move on to other work
4. Do **not** implement a "best guess" — wait for the user to answer

### Rules-Accurate Over Simple
When faced with a choice between a simpler implementation and one that faithfully follows the rules, **always choose rules-accurate**. The flowcharts are complex on purpose. Do not simplify tie-breaking logic, do not skip edge cases, do not collapse decision branches that the flowchart keeps separate.

### No Outside References
- Do NOT consult BoardGameGeek.com
- Do NOT reference other GMT games or other COIN series titles
- Do NOT do historical research
- Do NOT consult any GitHub repository other than this one
- The Reference Documents folder is the complete universe of source material

### Testing
- Run `pytest -q` before every commit
- All tests must pass
- When fixing a bug, add a test that would have caught it
- When implementing a flowchart branch, add a test that exercises it
- Tests should verify behavior against the Reference Documents, not against assumed behavior

### Commit Discipline
- One logical change per commit
- Commit message should reference what was changed and why (e.g., "Fix card 24: unshaded was inverted vs reference")
- Never commit with failing tests

---

## Conventions

- **Python 3.10+** assumed
- **Imports:** Always import constants from `rules_consts.py` rather than using string literals
- **State:** Game state is a dictionary passed through functions. Do not use global state.
- **Map queries:** Use helpers in `lod_ai/map/` and `lod_ai/board/` — do not access space dictionaries directly with string keys like `sp.get("type")` or `sp.get("British_Control")`
- **Piece operations:** Use `lod_ai/board/pieces.py` for placement/removal — do not manipulate piece lists directly
- **Caps:** Use `lod_ai/util/caps.py` for piece cap enforcement
- **Control:** Use `lod_ai/board/control.py` for control calculations

---

## How to Run

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run the game
python -m lod_ai

# Run tests
pytest -q
```

---

## For the Maintainer

This project was substantially built with ChatGPT assistance, which introduced systematic issues (see Known Issues above). The primary remaining work is correctness — making the implementation faithfully match the Reference Documents. Speed, optimization, and architectural elegance are secondary to rules accuracy.

When in doubt, read the Reference Documents again. Then read them one more time.
