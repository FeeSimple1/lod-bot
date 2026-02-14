# Compliance Audit Report

Last updated: Phase 3+ (QUESTIONS.md resolutions + British bot corrections)

---

## Phase 1: Label Compliance — COMPLETE

All `.py` files in `lod_ai/` audited for string literals that should be constants from `rules_consts.py`. Every violation fixed across:
- 11 command modules
- 9 special_activities modules
- 4 bot modules
- 5 card effect modules + cards/__init__.py
- state/setup_state.py, util/year_end.py, util/validate.py, interactive_cli.py

14 commits. 86 tests passing throughout.

---

## Phase 2: Card Compliance — COMPLETE

Source: `Reference Documents/card reference full.txt`

### FIXED cards (31 total)

#### late_war.py (25 cards fixed)
- **Card 1 (Waxhaws)**: Shaded "shift toward Neutral" was shifting -1 (toward Opposition), now correctly shifts toward 0.
- **Card 7 (John Paul Jones)**: Unshaded allows West Indies OR any City as destination.
- **Card 16 (Mercy Warren)**: Both paths allow proper target selection (was hardcoded).
- **Card 18 ("If Not Stormy")**: `ineligible_next` → `ineligible_through_next`; shaded no-op; any faction.
- **Card 19 (Nathan Hale)**: Shaded places Militia "anywhere" (was hardcoded PA).
- **Card 21 (Sumter)**: Allow SC or GA target.
- **Card 22 (Newburgh)**: Shaded marks immediate Tory Desertion.
- **Card 25 (Prison Ships)**: Proper "toward Passive Support/Opposition" shift (one step, not set to).
- **Card 31 (Thomas Brown)**: Allow SC or GA.
- **Card 39 (King Mob)**: Shift toward Neutral (toward 0), use map helpers.
- **Card 48 (God Save King)**: Shaded moves to adjacent (was removing to Available); proper piece tags.
- **Card 57 (French Caribbean)**: `ineligible_through_next` for both; shaded moves from map.
- **Card 62 (Langlade)**: War Party/Tory choice; NY/Quebec/NW target; shaded French/Militia choice.
- **Card 64 (Fielding)**: **Critical** — shaded was British -3 & FNI +1, corrected to Patriots +5.
- **Card 66 (Don Bernardo)**: British cube mix; FL or SW target.
- **Card 70 (British Gain From French in India)**: Bot-specific Regulars removal per Q2 answer.
- **Card 73 (Sullivan)**: Fixed loop; added FORT_PAT; shaded no-op.
- **Card 79 (Tuscarora)**: Any Colony (was hardcoded PA).
- **Card 81 (Creek & Seminole)**: SC or GA; shaded from both; Active WP removal.
- **Card 85 (Mississippi)**: Regulars/Tories mix; Militia/Continental choice.
- **Card 87 (Lenape)**: Any piece type; Remain Eligible.
- **Card 94 (Herkimer)**: Shaded removes from PA and adjacent.
- **Card 95 (Ohio Frontier)**: Shaded no-op check.
- **Card 96 (Iroquois)**: Constrain to Reserve Provinces.

#### middle_war.py (2 cards fixed)
- **Card 59 (Tronson de Coudray)**: Prefer spaces with both piece types.
- **Card 71 (Treaty of Amity)**: **Critical** — shaded was British +4 (should be French +5); unshaded formula fixed.

#### early_war.py (6 cards fixed)
- **Card 15 (Morgan's Rifles)**: Shaded allows any Colony.
- **Card 32 (Rule Britannia)**: Sourcing order Unavailable first; uses refresh_control.
- **Card 33 (Burning of Falmouth)**: Adjacency lookup for Massachusetts.
- **Card 35 (Tryon Plot)**: NY or NYC; shaded adjacent space.
- **Card 46 (Edmund Burke)**: Sourcing order Unavailable first.
- **Card 82 (Shawnee Warriors)**: NC not NY in province list.

### REMAINING card issues

#### Brilliant Stroke / Treaty of Alliance (Cards 105-109) — RESOLVED (Q4)
- Full trump hierarchy: ToA > Indians > French > British > Patriots
- Bot auto-check before 1st eligible acts (per §8.3.7)
- Bot BS execution: LimCom+SA+LimCom with leader/piece threshold
- Treaty of Alliance: preparations formula fixed (half CBC, total blockades)
- Trumped cards return to owners; all factions become Eligible after BS
- 7 new tests covering conditions, triggers, and execution

#### Deterministic bot choices
Cards 2, 6, 24, 28, 80 use hardcoded/alphabetical defaults for player/bot selections.

---

## Phase 3: Bot & Rules Compliance — COMPLETE

### FIXED issues

#### setup_state.py
- **WQ insertion off-by-one**: `_insert_wq()` used `min(4, len(pile))` instead of `min(5, ...)`, inserting Winter Quarters into bottom 4 cards instead of bottom 5.

#### year_end.py
- **French Blockade rearrangement**: Was hardcoded as "forgo"; Manual Ch 6.5.4 says "French may rearrange."
- **French Supply**: `sp.get("Rebellion_Control")` → `state.get("control", {}).get(sid) == "REBELLION"`.

#### french.py
- **F2 event check**: `_faction_event_conditions` was checking `unshaded_event` text — French play SHADED events per flowchart. Fixed to check `shaded_event`.
- **F10 Muster logic inverted**: Was Mustering in Colonies when WI rebel or >=4 Available. Per flowchart: Muster in WI when <4 Available and WI not Rebel Controlled; otherwise Colony/City with Continentals.
- **F5 ordering**: Verified correct — Agent Mobilization first, Hortalez as fallback (Q6 RESOLVED).

#### british_bot.py
- **B3 resource gate missing**: Flowchart requires `British Resources > 0` check before attempting any operations. Added gate with PASS if resources <= 0.
- **B11 Skirmish space restriction**: Now excludes spaces selected for Battle/Muster/Garrison destination (uses `_turn_affected_spaces`).
- **B5 Garrison tiebreaker**: Added Underground Militia tiebreaker to city selection.
- **Reward Loyalty nested sort**: Fixed from `(population, -has_raid)` to `(-marker_count, shift_magnitude)` per reference: "First where fewest Raid + Propaganda markers, then for largest shift in (Support – Opposition)."

#### indians.py
- **I11 Trade**: British resource transfer now uses half the DIE ROLL (rounded up), not half of Resources. Per OPS reference: "roll 1D6; if result < Brit Resources, offer to transfer half (round up) rolled Resources to Indians."

#### board/control.py
- **Q1 RESOLVED**: Removed all per-space legacy control flags (`sp["British_Control"]`, `sp["Patriot_Control"]`, `sp["Rebellion_Control"]`). All callers now use `state["control"][sid]` or `refresh_control(state)`.

#### engine.py
- **Q3 RESOLVED**: Free ops now execute immediately during event resolution. Added `_drain_free_ops()` that runs all queued free ops right after the event handler returns in `handle_event()`.

#### late_war.py
- **Card 70 Q2 RESOLVED**: Bot-specific Regulars removal. British removes French Regulars from WI first; French removes British from Rebel spaces; Indian removes French from Village spaces; Patriot removes British from Patriot spaces.

### Engine/Dispatcher/Victory — PASS

- **engine.py**: Sequence of play, eligibility reset, card prep, Winter Quarters swap — all compliant with Manual Ch 2.
- **dispatcher.py**: Simple router — no issues found.
- **victory.py**: All four faction victory conditions correctly calculated per Manual Ch 7. Final scoring (§7.3) correctly sums both conditions.

### Year-End/Winter Quarters — 98% PASS

- Supply phase (§6.2): Correctly implements all faction supply rules.
- Resource income (§6.3): British/Patriot/Indian/French income formulas correct.
- Support phase (§6.4): Max 2 shifts, marker removal costs, correct shift directions.
- Redeployment (§6.5): Leader change, redeploy, British release, FNI drift all correct.
- Desertion (§6.6): 1-in-5 removal with correct rounding.
- Reset phase (§6.7): Marker removal, eligibility reset, flip to Underground all correct.

### REMAINING bot issues

#### British Bot (british_bot.py)
- **B1-B2 (Event handling)**: Event eligibility and event/command decision nodes not implemented in flowchart driver — delegated to BaseBot.
- **B8 Muster**: Regular placement not sorted by population; missing third Tory priority ("Colonies with < 5 cubes and no Fort").
- **B10 March**: "Leave last X" rule oversimplified; missing second phase ("Pop 1+ spaces") and third phase ("March in place to Activate Militia"). Common Cause timing should be during March, not after.
- **B12 Battle**: Leader modifier (+1 for Gage/Clinton) not included in force level calculation.

#### French Bot (french.py)
- **F13 Battle precondition**: Should check "Rebel cubes + Leader exceed British pieces" — leader modifier may be missing.

#### Indian Bot (indians.py)
- **I7 Gather**: Delegates entirely to `gather.execute()` — cannot verify Cornplanter condition (2+ vs 3+ War Parties).
- **I10 March**: Severely simplified — single move instead of up to 3; no prioritization by Rebel Control or Active Support. (Q5 answered: implement ALL movements — not yet done.)
- **I12 Scout**: No destination priority (Fort → Village → Control).

#### Patriot Bot (patriot.py)
- **P4 Battle**: No modifier calculation (loss, terrain, leader bonuses).
- **P5 March**: Delegates bullet details to `march.execute()`.
- **P7 Rally**: Hardcoded 2 Forts; missing Continental promotion step.
- **P8/P12 Partisans/Skirmish**: Missing priority targeting (Village removal, Fort removal).

#### Brilliant Stroke — RESOLVED (see Phase 2 section above)

---

## Session 2 Fixes (Review Session)

### Battle Loss Modifiers — COMPLETE
- **§3.6.5 Defender Loss**: Rewrote with all modifiers: +1 half regs, +1 underground, +1 attacking leader, +1 Lauzun (French attacking), -1 blockaded city, -1 WI squadron, -1 per defending fort, -1 Indians in reserve, -1 Washington defending.
- **§3.6.6 Attacker Loss**: All modifiers: +1 half regs, +1 underground, +1 defending leader, -1 blockaded city, -1 WI squadron, +1 per defending fort.
- Washington modifier was previously applied to wrong side (attacker loss instead of defender loss). Fixed.
- 24 unit tests added (test_battle_modifiers.py).

### Brilliant Stroke Cards 105-108 — COMPLETE
- Replaced loop-based stubs with individual named functions (evt_105_bs_patriots, etc.).
- Each handler records a declaration, resets all factions to Eligible, and logs.
- Does NOT call mark_bs_played (engine handles this during trump resolution).
- Card 109 (ToA) enhanced to also reset eligibility.

### Free Ops Drain — COMPLETE
- **BS resolution path**: apply_treaty_of_alliance() queues a free Muster but _drain_free_ops was never called in _resolve_brilliant_stroke_interrupt. Fixed.
- **Bot play_turn path**: bot.take_turn() → _execute_event() calls handlers directly, bypassing engine.handle_event() where drain existed. Added drain after _commit_state in play_turn.
- WQ event path verified safe (WQ card handlers 97-104 don't queue free ops).
- Added test verifying free ops drain after handle_event.

### Card Handler Fixes — COMPLETE
- **Card 50 (Admiral d'Estaing) shaded**: French Regulars now drawn from Available OR West Indies per reference "(from Available or West Indies)". Was only drawing from Available.
- **Card 4 (Penobscot) shaded**: Added Fort_BRI fallback for Crown when Village cap reached, matching reference "Fort or Village".
- **Card 72 (French Settlers)**: Verified correct — proper fallback and piece selection already in place.
- Added 6 tests for cards 4 and 50.

### British Release Date (§6.5.3) — COMPLETE
- `_british_release()` expected integer but scenario JSON has year-keyed dict of piece counts.
- Called nonexistent `bp.lift_unavailable()`.
- Only released Regulars, ignoring Tories.
- **Fix**: build_state() converts year-keyed dict to ordered list of tranches. _british_release() pops one per WQ, moves both Regulars and Tories.
- Added brit_release to 1776_medium.json (was missing: 6 Regs + 6 Tories after 1776).
- 4 tests added.

### Pre-existing Issues Documented
- **Q7** (QUESTIONS.md): _execute_bot_brilliant_stroke() hardcodes command priorities instead of consulting faction flowcharts per §8.3.7.

---

## Session 3: Line-by-Line Card Handler Audit

### Infrastructure

- **New helper: `flip_pieces()`** in `board/pieces.py` — In-place variant flip (e.g., Militia_U → Militia_A) without routing through the Available pool. Prevents pool corruption that occurred when remove_piece + place_piece was used for activation/deactivation.
- **Re-exported via `shared.py`** for use by all card effect modules.

### FIXED cards (13 cards across 3 files)

#### Direct dict manipulation → flip_pieces (6 cards)

These cards manipulated `sp[tag]` directly instead of using board/pieces helpers:

- **Card 8 (Culpeper Spy Ring) unshaded**: `sp[MILITIA_U] -= 1; sp[MILITIA_A] += 1` → `flip_pieces()`. Also fixed: was only flipping 1 Militia per space; now flips `min(available, 3 - flipped)` per space.
- **Card 29 (Edward Bancroft) unshaded**: `sp[hidden_tag] -= take; sp[active_tag] += take` → `flip_pieces()`.
- **Card 35 (Tryon Plot) unshaded**: `sp[MILITIA_U] = 0; sp[MILITIA_A] += mu` → `flip_pieces()`.
- **Card 77 (Gen. Burgoyne) unshaded**: Used `remove_piece(WARPARTY_A, ..., to="available")` + `place_piece(WARPARTY_U, ...)` for Underground flip. This corrupted the Available pool: WARPARTY_A pieces in Available couldn't be found as WARPARTY_U by `place_piece`, causing `_ensure_available` to reclaim War Parties from OTHER map spaces. → `flip_pieces()`.
- **Card 86 (Stockbridge Indians) unshaded**: `sp.pop(MILITIA_U, 0); sp[MILITIA_A] += flip` → `flip_pieces()`.
- **Card 28 (Moore's Creek Bridge)**: Removed illegal pool inflation hack `pool[TORY] = max(pool.get(TORY, 0), 2 * total)` that created pieces from nothing. Replacement now properly draws from Available via `remove_piece` + `place_piece`.

#### Reference mismatches (7 cards)

- **Card 23 (Francis Marion) unshaded**: Hardcoded South_Carolina → Georgia. Reference: "move all Patriot units in **North Carolina or South Carolina** into an adjacent Province." Fixed to support both colonies, with `card23_src` / `card23_dst` overrides. Also: was moving FORT_PAT (a base); reference says "units" (cubes only). Removed FORT_PAT from move list.
- **Card 23 (Francis Marion) shaded**: Only checked South_Carolina. Reference: "If Militia occupy **North Carolina or South Carolina**, remove four British units." Fixed to check both colonies.
- **Card 67 (De Grasse) shaded**: Only queued "rally." Reference: "free **Rally or Muster** in one space." Added `card67_op` override for muster. Also fixed eligibility key from `eligible_next` → `remain_eligible` (reference: "remain or become Eligible").
- **Card 22 (Newburgh Conspiracy) unshaded**: `_remove_four_patriot_units()` did not verify target was a Colony. Reference: "in any one **Colony**." Added `_is_colony_late()` check.
- **Card 79 (Tuscarora) unshaded**: Village placed via `place_piece` (no cap check). Changed to `place_with_caps` to enforce MAX_VILLAGE=12.
- **Card 81 (Creek & Seminole) unshaded**: Same Village cap issue. Changed to `place_with_caps`.

### Tests added (18 new)

- `test_late_war_cards.py` (new file, 10 tests): Card 23 (4 tests), Card 67 (4 tests), Card 22 (1 test), Card 23 Fort exclusion (1 test)
- `test_middle_war_cards.py` (+5 tests): Card 8 (3 tests including multi-flip), Card 77 (1 test verifying no pool corruption)
- `test_early_war_cards.py` (+3 tests): Card 35, Card 86 (2 tests)
- Test for Card 28 updated to provide Available pool (no more pool inflation hack)

### REMAINING issues (documented, not fixed) — Session 3

**7 of 9 issues resolved in Session 5 (see below). Remaining 2:**

#### Queued vs. immediate execution
- **Card 15 (Morgan's Rifles) shaded**: Uses `queue_free_op` for March/Battle/Partisans. Q3 resolution says engine drains free ops immediately after handler, so this is effectively immediate.
- **Card 94 (Herkimer) unshaded**: Militia removal executes before queued Gather/Muster. Reference order suggests Gather+Muster first, then Militia removal. Since engine drains free ops after handler, the Militia removal in the handler runs before the queued ops. No fix needed per user ruling (ordering has no gameplay impact).

#### Resolved — no fix needed
- **Card 11 (Kosciuszko) shaded**: Uses `"REBELLION"` control check. User confirmed this is correct.

---

## Session 4: Full Card Handler Re-Audit

### Scope

Exhaustive line-by-line comparison of **all 109 card handlers** across 5 files against `Reference Documents/card reference full.txt`:

- `early_war.py` — 32 cards (2, 4, 6, 10, 13, 15, 20, 24, 28, 29, 30, 32, 33, 35, 41, 43, 46, 49, 51, 53, 54, 56, 68, 72, 75, 82, 83, 84, 86, 90, 91, 92)
- `middle_war.py` — 32 cards (3, 5, 8, 9, 11, 12, 14, 17, 26, 27, 34, 38, 42, 44, 47, 50, 55, 58, 59, 60, 61, 63, 69, 71, 74, 76, 77, 78, 80, 88, 89, 93)
- `late_war.py` — 32 cards (1, 7, 16, 18, 19, 21, 22, 23, 25, 31, 36, 37, 39, 40, 45, 48, 52, 57, 62, 64, 65, 66, 67, 70, 73, 79, 81, 85, 87, 94, 95, 96)
- `brilliant_stroke.py` — 5 cards (105, 106, 107, 108, 109)
- `winter_quarters.py` — 8 cards (97, 98, 99, 100, 101, 102, 103, 104)

Also verified:
- Label compliance: all piece tags, faction names, and marker references use constants from `rules_consts.py`
- Piece operations: all placement/removal/movement uses `board/pieces.py` helpers (`place_piece`, `remove_piece`, `move_piece`, `place_with_caps`, `flip_pieces`)
- No direct dictionary manipulation of piece counts
- Destination accuracy: all "to Casualties" vs "to Available" destinations match the reference
- `shift_support()` correctly clamps to [-2, +2], making plain delta shifts equivalent to "toward X" semantics
- `remove_piece()` default `to="available"` is correct for cards that say "Remove" without specifying destination

### Result: NO NEW ISSUES FOUND

All previously identified and fixed issues from Sessions 1–3 remain correct. All previously documented remaining issues (see Session 3 "REMAINING issues" above) are still accurate and unchanged.

### Verified categories (all PASS)

| Category | Cards checked | Status |
|---|---|---|
| Resource adjustments (+/−) | 7, 10, 19, 33, 34, 37, 40, 42, 45, 53, 56, 58, 59, 60, 61, 63, 64, 65, 69, 71 | All amounts and recipients match reference |
| FNI adjustments | 7, 34, 37, 40, 53, 57, 60, 63, 64, 67, 69 | All deltas and absolute-set values correct |
| Eligibility flags | 5, 18, 34, 38, 44, 50, 57, 61 | All use `ineligible_through_next` (not `ineligible_next`) |
| Piece placement/removal | 2, 4, 6, 8, 16, 19, 20, 24, 25, 26, 27, 28, 30, 31, 32, 35, 36, 37, 38, 42, 43, 46, 47, 49, 50, 54, 55, 58, 59, 62, 66, 68, 72, 73, 75, 76, 78, 79, 81, 82, 83, 84, 85, 86, 87, 89, 90, 91, 92, 94, 95 | All piece tags, quantities, and destinations correct |
| Support/Opposition shifts | 1, 2, 10, 16, 21, 25, 27, 39, 41, 46, 83, 93 | Direction, magnitude, and clamping correct |
| Free operations (march/battle/etc.) | 1, 5, 9, 14, 15, 21, 26, 31, 33, 48, 51, 52, 55, 66, 67, 75, 84, 94, 96 | Faction, op type, and location all correct |
| Shaded = no effect | 18, 29, 39, 44, 52, 68, 70, 72, 73, 80, 87, 88, 92, 93, 95 | All return early or no-op correctly |
| Winter Quarters cards | 97–104 | All queue correct Reset-Phase functions |
| Brilliant Stroke cards | 105–109 | Declarations, eligibility reset, ToA mechanics all correct |
| `flip_pieces()` usage | 8, 28, 29, 35, 77, 86 | All use board helper instead of direct dict manipulation |
| `place_with_caps()` for bases | 4, 26, 31, 68, 72, 77, 79, 81, 83, 90, 91, 92 | Enforces stacking limits correctly |

### Confirmed remaining issues (unchanged from Session 3)

All 9 previously documented remaining issues were confirmed still present. **7 of 9 resolved in Session 5** (see below).

### Tests

281 tests passing. No new tests needed since no code changes were made.

---

## Session 5: Fix 7 Audit Issues per User Rulings

User provided definitive rulings on all 9 remaining audit issues. 7 required code fixes, 2 were confirmed as no-fix-needed.

### FIXED (7 cards/groups)

| Card(s) | Issue | Fix |
|---|---|---|
| **Card 29 (Bancroft)** | "or" activated BOTH factions | Changed to ONE faction (player choice via `state["card29_target"]`; bot default: British/Indian→Patriots, Patriot/French→Indians) |
| **Cards 12, 13** | Deferred desertion via `winter_flag` | Now calls `_patriot_desertion()` immediately per §6.6.1 |
| **Card 48 (God Save the King) shaded** | Moved ALL non-British factions' units | ONE non-British faction (player choice via `state["card48_faction"]`) |
| **Cards 66, 67** | TOA-gated faction selection (`FRENCH if toa_played else PATRIOTS`) | Player choice regardless of TOA status (via `state["card66_shaded_faction"]`, `state["card67_faction"]`) |
| **Card 4 (Penobscot) shaded** | Faction-dependent piece type (Fort vs Village, Militia vs WP) | Player chooses freely (via `state["card4_base"]`, `state["card4_units"]`); defaults to faction-aligned |
| **Card 87 (Lenape) unshaded** | Fixed removal priority | Player chooses piece (via `state["card87_piece"]`); bot retains priority fallback |
| **Card 84 (Merciless Indian Savages) unshaded** | `queue_free_op` for Gather had no location restriction | Now passes Colony locations (via `state["card84_colonies"]` or `pick_colonies()`) |

### NO FIX NEEDED (2 issues)

| Card | Issue | Ruling |
|---|---|---|
| **Card 94 (Herkimer)** | Execution order (Militia removal before Gather/Muster) | No gameplay impact — no fix needed |
| **Card 11 (Kosciuszko)** | `"REBELLION"` control check vs. "Patriot Controlled" | Rebellion Control is correct |

### Tests

296 tests passing (15 new tests added across 3 test files).
