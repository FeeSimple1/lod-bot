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
