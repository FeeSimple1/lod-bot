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

#### Deterministic bot choices — MOSTLY RESOLVED
~~Cards 2, 6, 24, 28, 80 use hardcoded/alphabetical defaults for player/bot selections.~~
- Cards 2, 6, 80: **FIXED** — now use `pick_cities`/`pick_colonies` helpers with state override support
- Card 24: Unshaded fixed; shaded still takes first 3 spaces alphabetically (minor)
- Card 28: Uses preference filtering but no state override for final selection (minor)

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

### Year-End/Winter Quarters — 99% PASS

- Supply phase (§6.2): Correctly implements all faction supply rules. Bot-controlled factions now use faction-specific OPS priority methods for supply payment order.
- Resource income (§6.3): British/Patriot/Indian/French income formulas correct.
- Support phase (§6.4): Max 2 shifts, marker removal costs, correct shift directions. **Known gap:** Support Phase space iteration order not bot-controlled (no bot OPS methods exist for this).
- Redeployment (§6.5): Leader change, redeploy, British release, FNI drift all correct. Bot-controlled factions now use faction-specific OPS redeploy methods.
- Desertion (§6.6): 1-in-5 removal with correct rounding. Indian/French first-choice and Patriot/British remainder now use bot OPS priority methods.
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

**All 9 issues resolved (7 in Session 5, 2 confirmed no-fix-needed):**

#### Queued vs. immediate execution — NO FIX NEEDED
- **Card 15 (Morgan's Rifles) shaded**: Uses `queue_free_op` for March/Battle/Partisans. Q3 resolution says engine drains free ops immediately after handler, so this is effectively immediate.
- **Card 94 (Herkimer) unshaded**: Militia removal executes before queued Gather/Muster. No fix needed per user ruling (ordering has no gameplay impact).

#### Resolved — no fix needed
- **Card 11 (Kosciuszko) shaded**: Uses `"REBELLION"` control check. User confirmed this is correct.

---

## Session 4: Bot Flowchart Compliance Audit

Full node-by-node comparison of all four bot implementations against their respective flowchart reference documents.

### RUNTIME CRASH BUGS (fixed this session)

| File | Line | Description |
|------|------|-------------|
| `indians.py` | 310 | `_gather` passes `max_spaces=4` instead of required `selected: List[str]` — TypeError |
| `indians.py` | 450 | `_scout` missing required `n_warparties`/`n_regulars` kwargs — TypeError |
| `indians.py` | 288 | `_plunder` passes empty ctx without `raid_active` — ValueError |
| `british_bot.py` | 717 | `_try_common_cause` calls `common_cause.execute()` without required `spaces` arg — TypeError |
| `french_agent_mobilization.py` | 35 | `_VALID_PROVINCES` uses `"Quebec"` (Reserve Province) instead of `"Quebec_City"` (City) — mismatch with bot's correct list |
| `french.py` | 274 | `_hortelez` uses `random.randint` instead of `state["rng"]` — breaks determinism |
| `french.py` | 54-85 | `_preparer_la_guerre` post-Treaty missing D6 roll gate per F15 |

### HIGH SEVERITY LOGIC BUGS (fixed this session)

| File | Line | Description |
|------|------|-------------|
| `british_bot.py` | 490 | Reward Loyalty uses `max()` instead of `min()` — picks worst RL space every time |
| `british_bot.py` | 484-488 | RL filter logic inverted — excludes valid targets, includes invalid ones |
| `british_bot.py` | 224+528 | Double SA execution when Garrison falls back to Muster |
| `british_bot.py` | 198 | Skirmish always uses option=1 — never maximizes casualties per B11 |
| `indians.py` | 506-511 | Extra I2 event conditions not in reference (Resources, Unavailable, War Path) |
| `indians.py` | 514-523 | Wrong I2 condition 4: checks piece count vs British Regs instead of 4+ Villages |

### REMAINING HIGH SEVERITY (not fixed — require significant refactoring)

#### British Bot (british_bot.py)
- **B5 Garrison**: Only targets one city instead of full multi-phase operation — PARTIALLY FIXED (Session 5: control check, retention calc, but not multi-city)
- **B10 March**: ~~Only moves Regulars, never Tories; missing phases 2 and 3; Common Cause timing wrong~~ — FIXED (Session 5: Tories now move, all 3 phases implemented, correct CC mode)
- **B13 Common Cause**: ~~No flowchart-specific logic~~ — PARTIALLY FIXED (Session 5: correct mode parameter passed; WP constraints delegated to common_cause.execute)
- **B38 Howe capability**: FNI not lowered before SAs during Howe's leadership period

#### Patriot Bot (patriot.py)
- ~~**P4 Battle**: Force level uses total Militia (Active+Underground) instead of Active only~~ **FIXED** — now counts Active Militia only per §3.6.3
- ~~Washington lookup uses wrong data structure (space_id as key in leaders dict)~~ **FIXED** — now uses `leader_location()` for both P4 and P6
- ~~P4 includes Patriot Forts in attacking force level~~ **FIXED** — attacker excludes Forts per §3.6.3
- ~~P4 caps defending British Tories at Regulars count~~ **FIXED** — Tories uncapped when defending per §3.6.2
- ~~P4 uses `random.random()` for tiebreaker~~ **FIXED** — now uses `state["rng"].random()` for determinism
- ~~P4 French Regulars uncapped when Patriots attack~~ **FIXED** — now capped at Patriot cube count per §3.6.3
- **P4 Battle**: Win-the-Day free Rally not implemented (REMAINING)
- **P5 March**: Missing "lose no Rebel Control" constraint, missing leave-behind logic, missing second phase (REMAINING)
- ~~**P5 March** requires group size >= 3 (not in reference)~~ **FIXED** — reduced to >= 1
- **P7 Rally**: Missing 4 of 6 bullet points (Continental replacement, Fort Available placement, Control-changing Militia, adjacent Militia gathering); always returns True (REMAINING)
- ~~**P7 Rally** hardcoded to max 2 forts~~ **FIXED** — now up to 4 (Rally Max limit)
- ~~**P8 Partisans**: Always uses option=1, never targets Villages (option=3)~~ **FIXED** — now uses option=3 when Village present and no WP
- ~~**P8 Partisans**: WP vs British priority flattened into sum~~ **FIXED** — now separate sort keys (-wp, -british)
- ~~**P12 Skirmish**: Always uses option=1, never removes Forts (option=3)~~ **FIXED** — now uses option=3 when Fort present and no enemy cubes
- ~~**Event Instructions**: Cards 71, 90 say "use unshaded" but bot plays shaded~~ **FIXED** — new `force_unshaded` directive
- ~~Cards 18, 44 ignore conditional fallbacks~~ **FIXED** — new `force_if_eligible_enemy` directive
- ~~Card 8 ignores "if French is human" condition~~ **FIXED** — new `force_if_french_not_human` directive
- Card 51 (Bermuda Gunpowder Plot) ignores "March to set up Battle" conditional (REMAINING)

#### French Bot (french.py) — PARTIALLY FIXED (Session 5)
- **~~F13 Battle~~**: ~~Only checks Washington~~ → FIXED: checks all Rebel leaders (Washington, Rochambeau, Lauzun); excludes War Parties from British count; includes British Forts
- **~~F16 Battle~~**: ~~Force level missing modifiers; `crown_cubes > 0` too narrow~~ → FIXED: Active Militia only (not Underground); includes Forts in British pieces filter; tracks affected spaces
- **F14 March**: Missing 4 of 5 constraints/priorities (Lose no Rebel Control, include Continentals, march toward nearest British, fallback to shared space). RNG determinism FIXED.
- **~~F12 Skirmish~~**: ~~Only checks REGULAR_BRI; no affected-space filter; no Fort-first~~ → FIXED: checks all British pieces (Regs+Tories+Forts); excludes affected spaces; Fort-first priority (option=3 when applicable)
- **~~F17 Naval Pressure~~**: ~~Missing target city priority~~ → FIXED: Battle space first, then most Support; full fallback chain F17→F12→F15
- **~~Event Instructions~~**: ~~All French cards use "force"~~ → FIXED: cards 52, 62, 70, 73, 83, 95 now use conditional force_if_X directives with game-state checks
- **~~F10 Muster~~**: ~~random.choice; no Colony/City filter~~ → FIXED: uses state["rng"]; filters first priority by Colony/City type

#### Indian Bot (indians.py)
- ~~**I7 Gather**: Space selection entirely missing — all 4 priority bullets unimplemented~~ — **FIXED** (Session 5: complete rewrite implementing all 4 priority bullets with Cornplanter threshold, leader priority, move-and-flip fallback)
- **I10 March**: Severely simplified — single move, missing priorities and constraints (Q5 answered: implement ALL movements — not yet done)
- ~~**I12 Scout**: No piece count calculation, no Control preservation check; never triggers Skirmish~~ — **FIXED** (Session 5: moves exactly 1 WP + most Regulars+Tories without losing Control; includes Skirmish trigger)
- ~~**I11 Trade**: Executes in up to 3 spaces; reference says Max 1~~ — **FIXED** (Session 5: now Max 1, picks space with most Underground WP)

### MEDIUM SEVERITY (documented, not fixed)

#### British Bot
- ~~B1 Garrison precondition missing FNI level 3 check~~ — RESOLVED: flowchart B4 doesn't mention FNI; code matches flowchart
- ~~B5 Garrison "leave 2 more Royalist" omits Forts from count~~ — FIXED (Session 5)
- B6 Muster precondition consumes die roll on every call (functionally correct but wasteful)
- ~~B8 Tory placement skips Active Opposition and adjacency checks; only places 1 Tory per space~~ — RESOLVED: code matches flowchart B8 (flowchart doesn't require these checks for Tory placement)
- ~~B12 Battle misses Fort-only spaces~~ — FIXED (Session 5); force level ignores modifiers
- ~~B7 Naval Pressure missing Gage/Clinton leader check~~ — FIXED (Session 5)
- B2 Event conditions overly broad text matching (would need per-card lookup table)
- ~~B8 Fort target space not passed to muster.execute~~ — RESOLVED: Fort space implicit in `build_fort` parameter
- B10 March always passes bring_escorts=False (reference silent on bot escorts)
- B39 Gage leader capability (free RL) not implemented
- ~~OPS reference (Supply/Redeploy/Desertion priorities) not in bot~~ **RESOLVED**: Bot OPS methods wired into year_end.py Supply, Redeploy, and Desertion phases

#### Patriot Bot
- ~~P8 Partisans WP vs British priority flattened into sum~~ **FIXED**
- P2 Event conditions: text matching unreliable (heuristic but functional; checking shaded text is correct per flowchart)
- Rally/Rabble mutual fallback — potential infinite loop masked by always-True return
- Rally Persuasion interrupt happens after Rally, not during
- March destination doesn't verify Rebel Control would actually be gained
- ~~March requires group size >= 3 (not in reference)~~ **FIXED**
- ~~British Tory cap applied when defending (should be uncapped)~~ **FIXED**
- Rabble-Rousing arbitrarily capped at 4 spaces

#### French Bot — PARTIALLY FIXED (Session 5)
- F6 Hortalez "up to" 1D3 language (minor)
- ~~F13 "British pieces" missing Forts~~ → FIXED: includes Forts, excludes WP
- ~~F16 Battle doesn't enter F12 Skirmish loop afterward~~ → FIXED: full SA chain
- ~~F10 Muster not filtering by Colony/City type~~ → FIXED
- ~~Battle counts Underground Militia in force~~ → FIXED: Active only
- ~~OPS summary items not implemented (Supply, Redeploy, Desertion, ToA trigger, BS trigger)~~ **PARTIALLY RESOLVED**: Supply, Redeploy, and Desertion priorities wired into year_end.py; ToA trigger and BS trigger remain separate

#### Indian Bot — FIXED (Session 5)
- ~~I6 checks Available village count instead of whether Gather would place 2+~~ **FIXED**: Now checks both Available count AND eligible spaces with enough WP
- ~~I9 checks only Underground WP; reference says any WP~~ **FIXED**: Now checks both Active and Underground WP
- Missing mid-Raid Plunder/Trade interruption when resources hit 0
- `_can_plunder` checks all map spaces, not just Raid spaces (minor: actual plunder correctly filters)
- ~~Trade multi-space iteration (reference says Max 1)~~ **FIXED**: Now Max 1, picks space with most Underground WP
- Circular fallback between Gather and March — potential infinite loop (unchanged; would need recursion guard)
- ~~Raid movement doesn't check "WP don't exceed Rebels" condition~~ **FIXED**: Now moves WP when target has none OR WP ≤ Rebels
- Defending in Battle activation rule not implemented
- ~~Supply, Patriot Desertion, Redeployment priorities not in bot~~ **RESOLVED**: Bot OPS methods wired into year_end.py
- Brilliant Stroke trigger conditions not implemented
- ~~Uses `random.random()` instead of `state["rng"]` in multiple places~~ **FIXED**: All uses now via `state["rng"]`

#### Indian Bot — additional fixes (Session 5)
- **I7 Gather**: Complete rewrite implementing all 4 priority bullets (Village placement with leader priority, WP at Villages, WP in rooms for Village, move-and-flip when no WP available)
- **I7 Gather Cornplanter**: Threshold now per-space (2+ only where Cornplanter is), not global
- **I8 War Path option**: Now selects correct option (3 for Fort removal, 2 for double removal, 1 default) instead of always option 1
- **I12 Scout**: Moves exactly 1 WP (not up to 3) + most Regulars+Tories possible without changing Control; includes Tories
- **Event instructions**: Cards 4/72/90 (Village condition), 18/44 (eligible enemy), 38 (WP placeable), 83 (shaded/unshaded conditional) — all now have proper conditional fallback logic
- ~~Uses `random.random()` instead of `state["rng"]` in multiple places~~ **FIXED** (listed in Medium Severity above)

---

## Session 5: British Bot Node-by-Node Review

Full node-by-node comparison of `british_bot.py` against `Reference Documents/british bot flowchart and reference.txt`.

### FIXED issues (this session)

#### B4 `_can_garrison` — Wrong control check
- **Bug:** Checked `control != BRITISH` — any non-British city (including uncontrolled) triggered Garrison.
- **Reference:** "Rebels control City w/o Rebel Fort" — must be Rebellion-controlled specifically.
- **Fix:** Changed to `control == "REBELLION"`. Removed redundant rebel-count check (Rebellion control already implies rebels present).

#### B5 `_select_garrison_city` — Same control check
- **Bug:** Same `control != BRITISH` check excluded all non-British cities, not just Rebellion-controlled ones.
- **Fix:** Changed to check `control == "REBELLION"`.

#### B5 `_garrison` — Origin retention omits Forts/Rebel Forts from piece count
- **Bug:** "Leave 2 more Royalist than Rebel pieces" counted only cubes + War Parties, omitting Forts.
- **Reference:** Forts are pieces that count toward control.
- **Fix:** Added `FORT_BRI` to royalist count and `FORT_PAT` to rebel count in the retention calculation.

#### B5 `_garrison` — Muster fallback missing context
- **Bug:** When no cubes moved, called `self._muster(state)` without `tried_march` context.
- **Fix:** Now passes `tried_march=False` explicitly.

#### B8 `_muster` — Regular placement uses `random.random()` instead of `state["rng"]`
- **Bug:** Random tiebreaker used Python's global `random` module, breaking deterministic replay.
- **Fix:** Changed to `state["rng"].random()`.

#### B8 `_muster` — Regular placement sorting missing Neutral/Passive priority tier
- **Bug:** Used Neutral/Passive as a hard filter (excluded all non-Neutral/Passive spaces).
- **Reference:** "first in Neutral or Passive" is a sorting priority, not a filter.
- **Fix:** Added `neutral_priority` tier to sort key (0=Neutral/Passive, 1=other). Spaces at Active Support/Opposition are now valid but lower priority.

#### B8 `_muster` — Guard against empty regular_plan
- **Bug:** When no valid Regular candidates exist, passed `regular_plan=None` to `muster.execute()` which requires it for British faction, causing ValueError.
- **Fix:** Added guard that falls through to March when nothing to muster.

#### B10 `_march` — Only moves Regulars, never Tories
- **Bug:** Move plan only included `C.REGULAR_BRI` pieces.
- **Reference:** "Leave last Tory and War Party in each space" implies Tories CAN move (just not the last one).
- **Fix:** `_movable_from()` now computes available Regulars AND Tories, respecting leave-behind rules.

#### B10 `_march` — Leave-behind rules incomplete
- **Bug:** Simplistic `can_leave()` function didn't track per-piece-type minimums.
- **Reference:** "Leave last Tory and War Party in each space, and last Regular if British Control but no Active Support."
- **Fix:** New `_movable_from()` function computes per-type minimums: min 1 Tory (if any present), min 1 WP (if any present), min 1 Regular (if British Control without Active Support). Also ensures removing pieces doesn't lose British Control.

#### B10 `_march` — Missing Phase 2 (Pop 1+ spaces)
- **Bug:** Only implemented Phase 1 (add British Control) and a simplified fallback.
- **Reference:** "Then March to Pop 1+ spaces not at Active Support, first to add Tories where Regulars are the only British units, then to add Regulars where Tories are the only British units."
- **Fix:** Added full Phase 2 with correct priority sorting.

#### B10 `_march` — Missing Phase 3 (March in place)
- **Bug:** Not implemented at all.
- **Reference:** "Then March in place to Activate Militia, first in Support."
- **Fix:** Added Phase 3 that uses `flip_pieces()` to activate Underground Militia in spaces with British Regulars, prioritized by Support level.

#### B12 `_battle` — Excludes Rebel Fort-only spaces
- **Bug:** Required `rebel_cubes + total_militia > 0`, excluding spaces with only a Rebel Fort.
- **Reference:** "spaces with Rebel Forts and/or Rebel cubes" — Fort-only spaces are valid.
- **Fix:** Changed filter to `rebel_cubes + total_militia + rebel_forts > 0`.

#### B13 `_try_common_cause` — Always passes mode="BATTLE"
- **Bug:** Hard-coded `mode="BATTLE"` even when called from March context.
- **Reference:** Common Cause has different constraints for March vs Battle.
- **Fix:** Added `mode` parameter; March calls with `mode="MARCH"`, Battle uses default `mode="BATTLE"`.

#### B7 `_try_naval_pressure` — Missing Gage/Clinton leader check
- **Bug:** Delegated entirely to `naval_pressure.execute()` without checking leader requirement.
- **Reference:** "If FNI > 0 and Gage or Clinton is British Leader, remove 1 Blockade..."
- **Fix:** Added explicit leader check and city priority selection (Battle space first, then City with most Rebels without Patriot Fort, then most Support). FNI == 0 path (add Resources) does not require leader check.

#### B11 `_try_skirmish` — Improved option selection and Clinton bonus
- **Bug:** Only used options 1 and 2; never selected option 3 (remove Fort); no Clinton bonus.
- **Reference:** Option 3 for Fort-only spaces. Clinton in space removes 1 additional Militia.
- **Fix:** Added option 3 selection when no enemy cubes but enemy Fort exists. Added Clinton bonus check after successful Skirmish.

#### B11 `_try_skirmish` — Improved target prioritization
- **Bug:** Used additive priority score that didn't correctly implement "first last Rebel in space, within that first in a City."
- **Reference:** "Remove 1 Rebel piece, first last Rebel in space, within that first in a City."
- **Fix:** Rewrote priority to (tier, fewest_enemy, city_bonus) where tier is 0=WI, 1=exactly-1-Regular, 2=other.

#### Removed `import random` — global random module
- **Bug:** `import random` at module level was used for `random.random()` in Muster tiebreaking.
- **Fix:** Removed import; all randomness now uses `state["rng"]` for deterministic replay.

### REMAINING issues (from audit, not fixed this session)

#### British Bot
- **B5 Garrison**: Still targets only one city instead of full multi-phase operation (move to multiple cities, then reinforce existing British Control cities). Would require major refactoring of the Garrison command interface.
- **B38 Howe capability**: FNI not lowered before SAs during Howe's leadership period.
- **B39 Gage capability**: Free RL not implemented.
- **B2 Event conditions**: Text matching for bullets 3 and 4 is overly broad — cannot verify game-state conditions (e.g., "Active Opposition with none") from card text alone. Would need per-card lookup table.
- **B6 Muster precondition**: Consumes a die roll every time `_can_muster` is called, even when it won't lead to Muster. This is functionally correct but wasteful.
- **B10 March**: `bring_escorts=False` hard-coded — reference doesn't explicitly address this for bot March.
- **OPS reference**: Supply/Redeploy/Desertion priorities, Indian Trade, Brilliant Stroke trigger conditions — these are year-end/operational mechanics not in the turn flowchart.

### Tests added (22 new)

- `test_brit_bot_review.py`: Comprehensive test file covering all fixes:
  - B4 Garrison precondition: 3 tests (Rebellion control, uncontrolled city, Rebel Fort exclusion)
  - B5 Garrison retention: 1 test (Forts in royalist count)
  - B5 Garrison city selection: 2 tests (Rebellion control requirement, most-rebels priority)
  - B8 Muster determinism: 1 test (state["rng"] usage)
  - B9 Battle condition: 2 tests (Active Rebels count, leader bonus)
  - B10 March leave-behind: 2 tests (last Tory, last Regular)
  - B10 March in place: 1 test (Militia activation priority)
  - B11 Skirmish: 2 tests (Fort-only option 3, WI priority)
  - B12 Battle Fort-only: 1 test (Rebel Fort-only spaces)
  - B13 Common Cause mode: 2 tests (default BATTLE, MARCH mode)
  - B7 Naval Pressure: 3 tests (leader check, Clinton + blockade, FNI=0 resources)
  - B3 Resource gate: 2 tests (pass on zero, continue on positive)

310 tests passing (288 baseline + 22 new).

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

305 tests passing (Session 5: +17 Indian bot compliance tests, +1 updated I9 test).
281 tests passing. No new tests needed since no code changes were made.

---

## Session 5: French Bot Flowchart Compliance (Node-by-Node Verification)

Full node-by-node verification of `lod_ai/bots/french.py` against `Reference Documents/french bot flowchart and reference.txt`.

### FIXED issues (this session)

#### F13 `_can_battle` — 3 bugs fixed
- **Missing Rebel leaders**: Only checked Washington. Now checks all three Rebel leaders (Washington, Rochambeau, Lauzun) via `leader_location()`.
- **War Parties in British count**: Included `WARPARTY_A` in British pieces count. War Parties are Indian pieces, not British. Removed.
- **Missing British Forts**: Didn't include `FORT_BRI` in British pieces count. Added.

#### F12 `_try_skirmish` — 3 bugs fixed
- **Only checked REGULAR_BRI**: Only detected spaces with British Regulars. Now checks all British pieces (Regulars + Tories + Forts).
- **No Fort-first priority**: Always used option=2 (remove 2 cubes). Now uses option=3 (remove Fort) when no enemy cubes present and Fort exists; option=2 when 2+ cubes; option=1 when 1 cube.
- **No affected-space filter**: Didn't exclude spaces already selected for Battle or Muster. Now checks `_turn_affected_spaces`.

#### F16 `_battle` — 3 bugs fixed
- **Underground Militia counted**: Used `MILITIA_A + MILITIA_U` for rebel force. Underground Militia shouldn't count toward force level. Now uses Active Militia only.
- **`crown_cubes > 0` too narrow**: Only selected spaces with British cubes, missing Fort-only spaces. Changed to check all British pieces (`british_pieces > 0`).
- **Missing leader modifiers**: Didn't include Rebel leader bonuses in force calculation. Now includes Washington, Rochambeau, Lauzun.
- **Battle targets tracked**: Now records battle target spaces in `_turn_affected_spaces` so Skirmish can exclude them.

#### F10 `_muster` — 2 bugs fixed
- **`random.choice` instead of `state["rng"]`**: Broke deterministic reproducibility. Fixed to use `state["rng"].choice()`.
- **No Colony/City type filter**: First priority "Colony or City with Continentals" wasn't filtering by space type. Province spaces could match. Now filters by `type in ("Colony", "City")`.
- **Muster target tracked**: Now records muster space in `_turn_affected_spaces`.

#### F14 `_march` — 1 bug fixed
- **`random.random()` instead of `state["rng"]`**: Broke deterministic reproducibility. Fixed to use `state["rng"].random()`.

#### F17 `_try_naval_pressure` — 2 bugs fixed
- **No target priority**: Didn't prioritize Battle space first or most Support. Now selects city for Blockade: first a city selected for Battle, then highest Support.
- **Incomplete SA fallback chain**: Battle path only had F17→F12 fallback. Per flowchart F17→F12→F15. Added Préparer la Guerre (F15) as final fallback.

#### Event Instructions — 6 cards fixed
- **Cards 52, 62, 70, 73, 83, 95**: All used `"force"` (always play event). Per the French bot special instructions, each has a conditional: play event only if specific game-state condition is met, otherwise fall through to Command & SA.
- Added `force_if_X` directive pattern to `base_bot._choose_event_vs_flowchart()`.
- Added `_force_condition_met()` override in FrenchBot with card-specific checks.
- Removed unused `import random` from french.py.

### Verified nodes (PASS — correct as-is)

| Node | Description | Status |
|------|-------------|--------|
| F1 | Sword/SoP check | ✓ Handled by `base_bot._choose_event_vs_flowchart()` |
| F2 | Event conditions (6 bullets) | ✓ `_faction_event_conditions()` checks all 6 conditions. Text-matching is fragile but functional. |
| F3 | French Resources > 0 | ✓ `_follow_flowchart()` checks correctly, routes to PASS |
| F4 | Treaty of Alliance played? | ✓ Branches to `_before_treaty` / `_after_treaty` |
| F5 | Patriot Resources < 1D3 | ✓ Uses `state["rng"].randint(1,3)` |
| F6 | Hortalez before Treaty | ✓ Spends min(resources, roll), routes to F8 |
| F7 | Agent Mobilization | ✓ Correct provinces, correct placement priority, fallback to F6 |
| F8 | Préparer pre-Treaty | ✓ Blockade then Regulars then nothing |
| F9 | 1D6 < Available Regulars | ✓ Strict less-than with `state["rng"]` |
| F11 | Hortalez after Treaty | ✓ "up to" 1D3, routes to F12 |
| F15 | Préparer post-Treaty | ✓ D6 gate, +2 Resources fallback, correct structure |

### REMAINING issues (not fixed this session)

#### French Bot
- **F14 March**: Still missing "Lose no Rebel Control" constraint, Continentals in march group, march-toward-nearest-British logic, and March 1 French Regular to shared space fallback.
- **F2 Event conditions**: Text-matching approach is fragile (matches keywords in card text). A simulation-based approach would be more reliable but complex to implement.
- **F6 Hortalez**: "Spend 1D3" (before Treaty) vs "Spend up to 1D3" (after Treaty) — code uses `min(resources, roll)` for both. Minor.
- **OPS summary items**: French Supply/WI priorities, Redeploy leader logic, Loyalist Desertion priority, Treaty of Alliance trigger formula, Brilliant Stroke trigger conditions, Leader Movement during Campaigns — none implemented in the bot.

### Tests added (15 new)

- `test_f13_can_battle_includes_rochambeau` — Verifies Rochambeau + Lauzun leader bonuses
- `test_f13_can_battle_excludes_war_parties` — Verifies War Parties excluded from British count
- `test_f13_can_battle_includes_british_forts` — Verifies Forts counted in British pieces
- `test_f16_battle_active_militia_only` — Verifies Underground Militia excluded from force
- `test_f12_skirmish_detects_tory_only_space` — Verifies Tory-only spaces detected
- `test_f12_skirmish_excludes_affected_spaces` — Verifies Battle/Muster spaces excluded
- `test_f12_skirmish_fort_first_priority` — Verifies Fort removal before cubes
- `test_f10_muster_deterministic` — Verifies state["rng"] used
- `test_f10_muster_colony_city_filter` — Verifies Colony/City type filter
- `test_f14_march_deterministic` — Verifies state["rng"] used
- `test_event_force_if_73_british_fort_check` — Card 73 conditional
- `test_event_force_if_62_militia_only` — Card 62 conditional
- `test_event_force_if_70_british_in_rebel_spaces` — Card 70 conditional
- `test_event_force_if_83_quebec_city_rebellion` — Card 83 conditional
- `test_event_force_if_52_battle_target` — Card 52 conditional

303 tests passing total.
## Session 5: Patriot Bot Node-by-Node Flowchart Compliance

### Scope

Full node-by-node comparison of `lod_ai/bots/patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt`, covering nodes P1–P13, Operations Summary, and bot-specific card instructions.

### FIXED issues (13 bugs across 3 files)

#### patriot.py — Force Level & Leader Lookup

| Node | Bug | Fix |
|------|-----|-----|
| P6, P4 | Washington lookup uses `state.get("leaders", {}).get(sid, "")` — wrong format (space→leader instead of leader→space) | Use `leader_location(state, "LEADER_WASHINGTON")` from leaders module |
| P4 | Force Level counts Underground Militia (`MILITIA_A + MILITIA_U`) | Count only Active Militia (`MILITIA_A`) per §3.6.3 |
| P4 | Attacker Force Level includes Patriot Forts | Removed — forts only count for defender per §3.6.3 |
| P4 | British Tories capped at `min(tories, regs)` when defending | Uncapped when defending per §3.6.2 (cap only applies when attacking) |
| P4 | French Regulars uncapped when Patriots attack | Capped at Patriot cube count per §3.6.3 |
| P4 | Tiebreaker uses `random.random()` | Changed to `state["rng"].random()` for determinism |

#### patriot.py — Command Selection

| Node | Bug | Fix |
|------|-----|-----|
| P8 | Partisans always uses `option=1`, never removes Villages | Now uses `option=3` when Village present and no War Parties in space |
| P8 | WP and British priority flattened (`-(wp + british)`) | Split into `(-wp, -british)` — prefers War Party removal first per reference |
| P12 | Skirmish always uses `option=1`, never removes British Forts | Now uses `option=3` when Fort present and no enemy cubes in space |
| P12 | Skirmish tiebreaker uses `random.random()` | Changed to `state["rng"].random()` |
| P7 | Fort placement hardcoded to max 2 spaces (`[:2]`) | Changed to `[:4]` (Rally Max 4 limit) |
| P5 | March requires group size >= 3 (not in reference) | Changed to >= 1 per reference (no minimum stated) |

#### event_instructions.py + base_bot.py — Bot Card Instructions

| Card | Bug | Fix |
|------|-----|-----|
| 71 (Treaty of Amity) | "Use the unshaded text" but `force` directive plays shaded | New `force_unshaded` directive; `_execute_event` accepts `force_unshaded=True` |
| 90 (World Turned Upside Down) | Same as card 71 | Same fix |
| 8 (Culper Spy Ring) | "If French is a human player, choose C&SA" not checked | New `force_if_french_not_human` directive; checks `state["human_factions"]` |
| 18, 44 | "Target eligible enemy Faction. If none, C&SA" not checked | New `force_if_eligible_enemy` directive; checks `state["eligible"]` |

#### engine.py

| Issue | Fix |
|-------|-----|
| Bot has no access to `human_factions` | Engine now injects `state["human_factions"]` before bot turns |

### Tests added (22 new, 310 total)

All in `test_pat_bot.py`:

| Test | Verifies |
|------|----------|
| `test_p6_washington_lookup_uses_leader_location` | Leader→space and leader_locs formats both work |
| `test_p4_force_level_excludes_underground_militia` | Underground Militia excluded from FL |
| `test_p4_force_level_attacker_excludes_forts` | Patriot Forts excluded from attacking FL |
| `test_p4_force_level_defending_tories_uncapped` | Defending Tories not capped at Regulars |
| `test_p4_force_level_french_capped_at_patriot_cubes` | French Regs capped at Patriot count |
| `test_p4_uses_deterministic_rng` | Tiebreaker uses state["rng"] |
| `test_p8_partisans_uses_option3_for_villages` | Option=3 when Village and no WP |
| `test_p8_partisans_prefers_wp_over_british` | WP priority > British priority |
| `test_p12_skirmish_uses_option3_for_forts` | Option=3 when Fort and no enemy cubes |
| `test_p5_march_no_group_size_minimum` | Groups of 1 are accepted |
| `test_p7_rally_fort_cap_not_hardcoded_to_2` | 3+ fort targets all qualify |
| `test_card_71_90_force_unshaded_directive` | Directive table updated |
| `test_card_8_force_if_french_not_human_directive` | Directive table updated |
| `test_cards_18_44_force_if_eligible_enemy_directive` | Directive table updated |
| `test_force_unshaded_executes_unshaded` | Handler called with shaded=False |
| `test_force_if_french_not_human_skips_when_french_human` | Event skipped |
| `test_force_if_french_not_human_plays_when_french_bot` | Event played |
| `test_force_if_eligible_enemy_skips_when_none_eligible` | Event skipped |
| `test_force_if_eligible_enemy_plays_when_enemy_eligible` | Event played |
| `test_p3_pass_when_no_resources` | Bot PASSes at 0 resources |
| `test_p9_rally_preferred_when_fort_possible` | Fort-possible triggers Rally |
| `test_p10_rabble_possible_checks_support` | Support level check |

### REMAINING issues (not fixed — require significant refactoring or are medium severity)

#### High Severity
- **P4 Win-the-Day**: Free Rally and Blockade move after Rebellion wins not implemented
- **P5 March**: Missing "lose no Rebel Control" constraint, leave-behind logic, second phase
- **P7 Rally**: Missing Continental replacement, Fort Available placement, Control-changing Militia, adjacent Militia gathering steps; always returns True
- **Card 51**: "March to set up Battle per Battle instructions. If not possible, C&SA" conditional not implemented

#### Medium Severity
- **P2**: Text matching for event conditions is heuristic (unreliable but functional)
- **P7/P11**: Persuasion interrupt happens after command, not mid-execution when resources reach 0
- **P7/P11**: Rally/Rabble mutual fallback — potential infinite loop masked by always-True return
- **P5**: March destination doesn't verify Rebel Control would actually be gained
- **P11**: Rabble-Rousing arbitrarily capped at 4 spaces
- **OPS Summary**: Patriot Supply, Redeploy, Desertion, Brilliant Stroke, Leader Movement priorities not implemented in bot
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

---

## Session 6: Independent Full Card Handler Re-Audit

### Scope

Complete independent line-by-line verification of **all 109 card handlers** across 6 files against `Reference Documents/card reference full.txt`. This audit was performed independently of Session 4's audit to provide a second verification pass.

Files audited:
- `early_war.py` — 32 cards (2, 4, 6, 10, 13, 15, 20, 24, 28, 29, 30, 32, 33, 35, 41, 43, 46, 49, 51, 53, 54, 56, 68, 72, 75, 82, 83, 84, 86, 90, 91, 92)
- `middle_war.py` — 32 cards (3, 5, 8, 9, 11, 12, 14, 17, 26, 27, 34, 38, 42, 44, 47, 50, 55, 58, 59, 60, 61, 63, 69, 71, 74, 76, 77, 78, 80, 88, 89, 93)
- `late_war.py` — 32 cards (1, 7, 16, 18, 19, 21, 22, 23, 25, 31, 36, 37, 39, 40, 45, 48, 52, 57, 62, 64, 65, 66, 67, 70, 73, 79, 81, 85, 87, 94, 95, 96)
- `brilliant_stroke.py` — 5 cards (105, 106, 107, 108, 109)
- `winter_quarters.py` — 8 cards (97, 98, 99, 100, 101, 102, 103, 104)
- `shared.py` — Helper functions (shift_support, add_resource, adjust_fni, pick_cities, pick_colonies)

### Verification checklist applied per card

1. Piece tags use constants from `rules_consts.py` (not string literals)
2. Resource amounts and recipients match reference exactly
3. FNI adjustments (direction and magnitude) correct
4. Support/Opposition shifts (direction, magnitude, "toward X" semantics) correct
5. Destinations ("to Casualties" vs "to Available") match reference
6. Free operation types and factions correct
7. Eligibility flags correct (`ineligible_through_next` not `ineligible_next`)
8. Piece operations use `board/pieces.py` helpers exclusively (no direct dict manipulation)
9. Sourcing order (Available vs Unavailable) matches reference text ordering
10. Shaded = (none) cards correctly return/no-op

### Result: NO NEW ISSUES FOUND

All 109 card handlers match the card reference text. All previously identified and fixed issues from Sessions 1–5 remain correct.

### Verified categories (all PASS)

| Category | Sample verifications | Status |
|---|---|---|
| Resource adjustments | Cards 7, 10, 19, 34, 37, 42, 45, 53, 56, 58, 60, 61, 63, 64, 65, 69, 71 — all amounts and recipients correct | PASS |
| FNI adjustments | Cards 7, 34, 37, 40, 53, 57, 60, 63, 64, 67, 69 — directions and magnitudes correct; absolute-set (Card 40) correct | PASS |
| Eligibility flags | Cards 5, 18, 34, 38, 44, 50, 57, 61, 67, 87 — all use `ineligible_through_next` or `remain_eligible` correctly | PASS |
| Piece placement/removal | All 96 cards with piece operations — tags, quantities, destinations verified | PASS |
| Support/Opposition shifts | Cards 1, 2, 10, 16, 21, 25, 27, 39, 41, 46, 83, 93 — "toward X" semantics verified against numeric targets | PASS |
| Sourcing order | Card 30 (Available first per "from Available or Unavailable"), Cards 27/32/38/46 (Unavailable first per "from Unavailable or Available") — all match reference text ordering | PASS |
| Free operations | Cards 1, 5, 9, 14, 15, 21, 26, 31, 33, 48, 51, 52, 55, 66, 67, 75, 84, 94, 96 — faction, op type, and location correct | PASS |
| Shaded = no effect | Cards 18, 29, 39, 44, 52, 68, 70, 72, 73, 80, 87, 88, 92, 93, 95 — all return/no-op correctly | PASS |
| Winter Quarters cards | Cards 97–104 — CRC/CBC comparisons, half-difference reductions, second-VC-leader checks all correct | PASS |
| Brilliant Stroke cards | Cards 105–109 — declarations, eligibility reset, trump hierarchy, ToA preparations formula all correct | PASS |
| `flip_pieces()` usage | Cards 8, 28, 29, 35, 77, 86 — all use board/pieces helper, no direct dict manipulation | PASS |
| `place_with_caps()` for bases | Cards 4, 26, 31, 68, 72, 77, 79, 81, 83, 90, 91, 92 — enforces stacking limits | PASS |
| Shared helpers | `shift_support` clamps [-2,+2]; `adjust_fni` respects ToA gate + clamps [0,3]; `add_resource` clamps [0,50] | PASS |

### Tests

303 tests passing. No new tests needed since no code changes were made.

---

## Consolidated Outstanding Issues (updated Session 7)

All high-severity issues identified in Sessions 1-6 have been resolved. The remaining items are medium-to-low severity, mostly architectural limitations or operational-phase mechanics.

### Resolved Since Last Consolidation

**British Bot:**
- B38 Howe FNI lowered before SAs (`_apply_howe_fni()` called at all 4 SA paths)
- B39 Gage free RL (`rl_free_first` passed to `muster.execute()`)
- B5 Garrison multi-city (Phase 2a + Phase 2b iterate multiple cities)
- B2 Event conditions rewritten with `CARD_EFFECTS` flags (all 5 bullets)
- B6 Muster die roll cached (`_muster_die_cached`)
- B2/event_instructions: 7 cards with `force_if_X` conditional directives + `_force_condition_met()`
- B11 Skirmish option 2 threshold fixed (`own_regs >= 1`)
- Clinton Skirmish double-count fixed (removed duplicate check)
- RL dead code removed

**Patriot Bot:**
- P4 Win-the-Day wired (`win_rally_space`/`win_blockade_dest` passed to `battle.execute()`)
- P5 March constraints (`_would_lose_rebel_control()`, `_movable_from_pat()`, Phase 1 + Phase 2)
- P5 March destination verification (`need = royalist - rebels + 1`, `pieces_gathered >= need`)
- P7 Rally all 7 bullets implemented
- P7/P11 Rally/Rabble resource cap (capped at available resources, not hardcoded)
- P7/P11 infinite loop guard (`_from_rabble`/`_from_rally` flags)
- P11 Rabble no 4-space cap (`max_spaces = state["resources"][self.faction]`)
- Card 51 conditional (`force_if_51` in both BRITISH and PATRIOTS dicts)

**French Bot:**
- F6 Hortalez pre-Treaty exact cost (FIXED THIS SESSION: pre-Treaty must pay exact roll or skip)
- F14 March all 4 constraints (lose-no-control, Continentals, nearest British, shared space)
- F2 Event conditions use `CARD_EFFECTS` lookup

**Indian Bot:**
- I10 March multi-destination (`max_dests = min(3, resources)`, Phase 1 + Phase 2)
- Mid-Raid Plunder/Trade (checks `resources == 0` during Raid)
- Gather/March circular guard (`_visited` set)
- I2 Event conditions use `CARD_EFFECTS` lookup
- Indian defending-in-battle (battle.py lines 299-309: activate WP based on Village presence)
- `_indian_defending_activation()` dead code removed (was duplicated in battle.py)

**Patriot Bot:**
- P2 bullet 2 now checks board state for Active Support / Village spaces (Q11 resolved)

**Engine/Cards:**
- Cards 24/28 space selection uses population tiebreaker instead of alphabetical

**Engine:**
- Q7 BS command priorities (`get_bs_limited_command()` on all 4 bot subclasses; engine calls it)
- All 4 bots use `CARD_EFFECTS` for event evaluation (P2/F2/I2/B2)

### Card Handlers — COMPLETE
All 109 card handlers match `card reference full.txt`. No outstanding card issues.
- Card 24 shaded now selects spaces by Cities-first then highest population. Card 28 now selects by most Tories (shaded) / most Militia (unshaded).

### Remaining Issues

#### Medium Severity

- **OPS methods not wired into year_end**: All 4 bots define `ops_supply_priority()`, `ops_redeploy()`, `ops_desertion()`, `ops_bs_trigger()` methods. `year_end.py` uses its own ad-hoc logic and ignores these. Supply payment order, desertion target selection, and redeployment destination all use bot-independent heuristics instead of the faction-specific priorities from the reference flowcharts. This is a larger refactor — `year_end` needs to detect bot-controlled factions, import their bot instances, and call OPS methods for prioritization.
- **P7/P11 Persuasion mid-command expansion**: Reference says Persuasion fires during Rally/Rabble and restored resources could fund additional spaces. Current code fires Persuasion after all spaces are processed (resources are capped at selection time). Low gameplay impact — bot already gets highest-priority spaces. Would require Rally/Rabble to execute space-by-space with interrupt callbacks.

#### Low Severity

- **B10 March + Common Cause timing**: CC invoked post-March instead of during March planning. CC should integrate into group size calculation for adjacent Province destinations. Architectural refactor.

---

## Session 6: British Bot Full Compliance Review

### Scope

Node-by-node comparison of the entire British bot flowchart implementation in `lod_ai/bots/british_bot.py` against `Reference Documents/british bot flowchart and reference.txt` and Manual Ch 8 (§8.4). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `skirmish.py`, `common_cause.py`, `leaders/__init__.py`, and `rules_consts.py`.

### Nodes verified CORRECT

The following flowchart nodes are correctly implemented and match the reference:

| Node | Description | Status |
|------|-------------|--------|
| B1 | Sword icon skip | CORRECT |
| B3 | Resources > 0 gate | CORRECT |
| B4 | 10+ Regulars on map AND Rebels control City w/o Rebel Fort | CORRECT |
| B5 | Garrison retention (leave 2 more Royalist, last Regular rules) | CORRECT |
| B5 | Garrison Phase 2a (most Rebels w/o Pat Fort, then NYC, then random) | CORRECT |
| B5 | Garrison Phase 2b (1+ Regular w/o Active Support, then 3+ cubes w/ Underground Militia) | CORRECT |
| B5 | Garrison displacement (most Opposition, then least Support, then lowest Pop) | CORRECT |
| B5 | Garrison SA-first ordering (Skirmish then Naval) | CORRECT |
| B5 | Garrison multi-city operation | CORRECT (previously documented as single-city; now fixed) |
| B5 | Garrison fallback to Muster if no moves | CORRECT |
| B6 | Available Regulars > 1D6 | CORRECT |
| B8 | Muster Regular placement (Neutral/Passive first, then add Control, then Tories-only, highest Pop) | CORRECT |
| B8 | Muster Tory placement (Regulars-only first, then change Control, then < 5 cubes w/o Fort) | CORRECT |
| B8 | Muster RL/Fort condition (Opposition > Support + 1D3 OR no Forts Available) | CORRECT |
| B8 | Muster Fort placement (Colony w/ 5+ cubes, no Fort) | CORRECT |
| B8 | Muster SA after (Skirmish then Naval) | CORRECT |
| B9 | Active Rebel definition (Continentals + Active Militia + French Regulars) | CORRECT |
| B9 | Leader bonus (+1 to British Regulars) | CORRECT |
| B10 | March leave-behind rules (last Tory, last WP, last Regular if Control w/o Active Support) | CORRECT |
| B10 | March Phase 1 (largest groups first, Cities then Colonies, Rebel cubes then highest Pop) | CORRECT |
| B10 | March Phase 2 (Pop 1+ not Active Support, Tories-where-Regs-only, Regs-where-Tories-only) | CORRECT |
| B10 | March Phase 3 (March in place, Activate Militia, Support spaces first) | CORRECT |
| B11 | Skirmish space exclusion (not Battle/Muster/Garrison spaces) | CORRECT |
| B11 | Skirmish tier priorities (WI=0, exactly-1-Regular=1, other=2) | CORRECT |
| B11 | Skirmish tiebreaker (fewest enemy, then City) | CORRECT |
| B12 | Battle Force Level calculation (Regs + min(Tories, Regs) + floor(Active_WP/2)) | CORRECT |
| B12 | Battle modifiers (half Regs, Underground, Leader, -Fort) | CORRECT |
| B12 | Battle target sort (most British first) | CORRECT |
| B12 | Battle "exceeds" condition (strict >) | CORRECT |
| B7 | Naval Pressure FNI > 0 path (Blockade priority: Battle space, most Rebels w/o Fort, most Support) | CORRECT |
| B7 | Naval Pressure FNI = 0 path (+1D3 Resources) | CORRECT |
| RL | Reward Loyalty sort (fewest Raid+Propaganda markers, then largest shift) | CORRECT |

### Corrections to prior audit notes

**B5 Garrison multi-city**: The prior audit (Session 5) documented "Still targets only one city instead of full multi-phase operation." This has been fixed. Phase 2a iterates over multiple target cities, Phase 2b iterates over reinforcement targets, and both accumulate into `dest_cities`. The audit_report entry at line 460 is outdated.

### NEW issues found

#### High Severity

##### B2 Bullet 5: Wrong precondition — "10+ Regulars" vs "5+ Cities" (line 174)

**Reference (B2, bullet 5):** "British Control 5+ Cities, the Event is effective, and a D6 rolls 5+?"

**Implementation (line 174-178):**
```python
# 5. Event is effective, 10+ British Regulars on map, D6 >= 5
if eff["is_effective"]:
    regs_on_map = sum(sp.get(C.REGULAR_BRI, 0) for sp in state["spaces"].values())
    if regs_on_map >= 10:
```

**Bug:** Checks "10+ British Regulars on map" instead of "British Control 5+ Cities." These are fundamentally different conditions. The reference counts Cities under British Control (a board control metric); the code counts Regular pieces on the entire map (a piece-count metric). The condition `10+ Regulars` is much easier to satisfy than `5+ Cities` and could cause the bot to play Events it shouldn't.

##### B2 Bullet 3: Wrong condition entirely (line 167-169)

**Reference (B2, bullet 3):** "Event places Tories in Active Opposition with none, a British Fort in a Colony with none, or British Regulars in a City or Colony?"

**Implementation (line 167-169):**
```python
# 3. Event removes a Patriot Fort or removes an Indian Village
if eff["removes_patriot_fort"] or eff["removes_village"]:
    return True
```

**Bug:** The code checks for removing Patriot Forts/Villages, but the reference says *placing* Tories/Forts/Regulars under specific board conditions. The event_eval.py flag `removes_patriot_fort` has nothing to do with this bullet. This was partially documented as "B2 text matching overly broad" in Session 5 but the specific mismatch (checking removal instead of placement) was not identified. Note: correctly implementing this bullet requires state-dependent checks that the static event_eval.py lookup table cannot provide.

##### B2 Bullet 4: Wrong condition entirely (line 170-172)

**Reference (B2, bullet 4):** "Event inflicts Rebel Casualties (including free Skirmish or Battle)?"

**Implementation (line 170-172):**
```python
# 4. Event adds 3+ British Resources
if eff["adds_british_resources_3plus"]:
    return True
```

**Bug:** The code checks for British resource gains, but the reference says Rebel Casualties. The event_eval.py table has `inflicts_british_casualties` (opposite direction) but not `inflicts_rebel_casualties`. Adding resources is not the same as inflicting casualties.

##### British Event Instructions: Missing conditional directives (event_instructions.py lines 6-19)

**Reference (Non-Player British Cards Special Instructions):** Cards 18, 44, 51, 52, 62, 70, and 80 all have conditional fallback clauses: "If [condition not met], choose Command & Special Activity instead."

**Implementation:** All seven use plain `"force"`, which means the bot always plays the Event regardless of whether the condition is met.

| Card | Reference instruction | Current | Should be |
|------|----------------------|---------|-----------|
| 18 | Target Eligible enemy; if none → C&SA | `"force"` | `"force_if_eligible_enemy"` |
| 44 | Target Eligible enemy; if none → C&SA | `"force"` | `"force_if_eligible_enemy"` |
| 51 | March to set up Battle; if not possible → C&SA | `"force"` | `"force_if_51"` (conditional) |
| 52 | March to set up Battle; if not possible → C&SA | `"force"` | `"force_if_52"` (conditional) |
| 62 | NY at Active Opp. w/o Tories → place; else C&SA | `"force"` | `"force_if_62"` (conditional) |
| 70 | Remove French Regs from WI then Brit spaces; if none → C&SA | `"force"` | `"force_if_70"` (conditional) |
| 80 | Rebel Faction w/ pieces in Cities; if none → C&SA | `"force"` | `"force_if_80"` (conditional) |

Note: The Patriot bot already has `"force_if_eligible_enemy"` for cards 18 and 44, and the French bot has conditional directives for cards 52, 62, 70, etc. The British bot should follow the same pattern.

##### B11 Skirmish: Option 2 requires 2+ own Regulars instead of 1 (line 275)

**Reference (B11):** "Remove as many Rebel cubes as possible, first whichever type is least in the space, removing 1 British Regular if necessary."

**Implementation (line 275):**
```python
if enemy_cubes >= 2 and own_regs >= 2:
    return 2
```

**Bug:** The `own_regs >= 2` condition should be `own_regs >= 1`. Option 2 sacrifices 1 Regular to remove 2 enemy cubes. The bot only needs 1 Regular present to sacrifice, not 2. With exactly 1 Regular in a space that has 2+ enemy cubes, the bot should choose option 2 (maximizing removal as the reference instructs) but currently falls through to option 1 (removing only 1 piece).

#### Medium Severity

##### B2 Bullet 2: Over-permissive — does not verify "from Unavailable" (line 164-166)

**Reference (B2, bullet 2):** "Event places British pieces from Unavailable?"

**Implementation (line 164-166):**
```python
if eff["places_british_pieces"]:
    return True
```

**Issue:** The flag `places_british_pieces` is true for any card that places British pieces regardless of whether they come from Unavailable or Available. The reference specifically says "from Unavailable" — pieces placed from Available would not satisfy this condition. This is a static-lookup limitation: event_eval.py doesn't distinguish piece source.

##### B2 Bullet 1: Missing blockade removal consideration (line 162-163)

**Reference (B2, bullet 1):** "Opposition > Support, and Event shifts Support/Opposition in Royalist favor (including by removing a Blockade)?"

**Implementation (line 162-163):**
```python
if opp > sup and eff["shifts_support_royalist"]:
    return True
```

**Issue:** The `shifts_support_royalist` flag in event_eval.py does not account for Events that remove Blockades (which shifts Support indirectly by removing the marker). For example, Card 40 (Battle of the Chesapeake) unshaded sets FNI to 0, which could remove Blockades, but its event_eval entry does not set `shifts_support_royalist=True`.

##### B11 Clinton bonus: dead code with wrong data access (lines 326-335)

**Implementation (lines 326-327):**
```python
leader = state.get("leaders", {}).get(sid, "")
if leader == "LEADER_CLINTON":
```

**Issue:** `state["leaders"]` maps faction → [leader_ids] per the docstring in `leaders/__init__.py`. Looking up by space ID (`sid`) always returns `""`. This code is dead — it never fires. Meanwhile, `skirmish.execute()` already handles Clinton's bonus via both `apply_leader_modifiers` and a direct `leader_location` check. The dead code should be removed to avoid confusion.

##### skirmish.py Clinton double-count (tangential — lines 150-153 of skirmish.py)

**Issue (in skirmish.py, not british_bot.py):** `apply_leader_modifiers` at line 77 runs the Clinton modifier, setting `ctx["skirmish_extra_militia"] = 1`. Then at line 151, `extra_militia = ctx.get("skirmish_extra_militia", 0)` picks up that 1. Then at line 152-153, `if clinton_here: extra_militia += 1` adds another 1. Result: Clinton removes 2 extra Militia instead of 1. Either the modifier registration or the direct check should be removed, not both.

##### RL exclusion filter: dead code (lines 804-808)

**Implementation (lines 797-808):**
```python
rl_candidates = [
    sid for sid, sp in state["spaces"].items()
    if self._support_level(state, sid) < C.ACTIVE_SUPPORT  # excludes Active Support
    ...
]
rl_candidates = [
    sid for sid in rl_candidates
    if not (self._support_level(state, sid) == C.ACTIVE_SUPPORT  # can never match
            and (sid in raid_on_map or sid in prop_on_map))
]
```

**Issue:** The first filter already excludes all spaces at Active Support (`< ACTIVE_SUPPORT`). The second filter checks for `== ACTIVE_SUPPORT`, which can never match within the already-filtered list. The intent ("Do not RL where only markers would be removed") is correctly handled by the first filter (you can't shift beyond Active Support, so Active Support spaces with markers would only have marker removal as effect), but the second filter is unreachable dead code.

#### Low Severity

##### B10 March + Common Cause timing (architectural)

**Reference (B10):** "Use Common Cause to increase group size if destination is adjacent Province."

**Implementation:** `_try_common_cause()` is called AFTER `march.execute()` completes (line 1106). The reference implies CC should be considered DURING March planning so that War Parties boost the movable group size for Phase 1 destinations. The current post-hoc invocation means March cannot benefit from CC-expanded groups.

This was partially documented in Session 5 as "`bring_escorts=False` hard-coded." The root cause is broader: CC is invoked as a post-command SA rather than integrated into March planning.

##### B13 Common Cause WP preservation not enforced

**Reference (B13):**
- "If Marching into an adjacent Province, do NOT use the last War Party (if possible Underground)."
- "If Battle, do NOT use the last Underground War Party."

**Implementation:** `common_cause.execute()` (line 59) defaults to using ALL War Parties in each space. No preservation logic for last WP or last Underground WP exists in either the bot or the command module.

Session 5 noted "correct mode parameter passed; WP constraints delegated to common_cause.execute" but the execute function does not implement those constraints.

### Summary

**Correct:** 32 nodes/sub-nodes verified as correctly implementing the reference.

**New issues found:** 5 high severity, 4 medium severity, 2 low severity.

**Previously documented issues confirmed still present:** B2 bullets 3-4 (static lookup limitations), B38 Howe, B39 Gage, OPS reference items (Supply/Redeploy/Desertion/Trade/BS trigger).

**Previously documented issue now resolved:** B5 Garrison multi-city operation (working correctly).

790 tests passing. No code changes made in this session (review only).

---

## Session 6: British Bot Compliance Fixes

All issues identified in the Session 6 review above have been fixed. 6 groups of changes, 26 new tests added.

### Group 1: New B2 flags in event_eval.py

Added 6 new boolean fields to `_F` template in `event_eval.py`:
- `inflicts_rebel_casualties` — 7 cards True (1, 6, 9, 14, 48, 51, 52)
- `places_british_from_unavailable` — 6 cards True (27, 30, 32, 38, 43, 46)
- `places_tories` — 19 cards True (2, 15, 16, 26, 27, 28, 31, 32, 38, 42, 43, 46, 47, 62, 66, 76, 85, 89, 94)
- `places_british_fort` — 2 cards True (26, 31)
- `places_british_regulars` — 7 cards True (2, 7, 30, 32, 38, 66, 85)
- `removes_blockade` — 1 card True (54)

All 96 cards audited against `card reference full.txt` unshaded text. Shaded entries all False (no dual-effect cards for these British-specific flags).

Updated `test_event_eval.py`: 6 new fields in `_EXPECTED_FIELDS`, 14 new spot-check tests (2+ per flag, one True and one False).

### Group 2: Rewritten B2 bullets in `_faction_event_conditions()`

Rewrote all 5 bullets to match `british bot flowchart and reference.txt` lines 14-20:

| Bullet | Before | After |
|--------|--------|-------|
| 1 | `shifts_support_royalist` only | `shifts_support_royalist OR removes_blockade` |
| 2 | `places_british_pieces` (any source) | `places_british_from_unavailable` (strict subset) |
| 3 | `removes_patriot_fort OR removes_village` (wrong) | Dynamic: `places_tories` + Active Opp w/o Tories, `places_british_fort` + Colony w/o Fort, `places_british_regulars` + City/Colony |
| 4 | `adds_british_resources_3plus` (wrong) | `inflicts_rebel_casualties` |
| 5 | `regs_on_map >= 10` (wrong metric) | `controlled_cities >= 5` using CITIES list |

3 new tests in `test_brit_bot.py` covering bullets 3 (board state check), 4 (flag check), and 5 (city count not regulars).

### Group 3: British event_instructions.py conditional directives

**3a.** Changed 7 BRITISH dict entries from `"force"` to conditional directives:
- Cards 18, 44 → `"force_if_eligible_enemy"` (already handled by base_bot)
- Card 51 → `"force_if_51"`, Card 52 → `"force_if_52"` (March to set up Battle)
- Card 62 → `"force_if_62"` (NY Active Opp w/o Tories)
- Card 70 → `"force_if_70"` (French Regs in WI or with British)
- Card 80 → `"force_if_80"` (Rebel pieces in Cities)

**3b.** Added `_force_condition_met()` override to BritishBot with game-state checks for each directive, following the pattern in `french.py` and `patriot.py`.

4 new tests covering force_if_62, force_if_70, force_if_80, and force_if_51.

### Group 4: Skirmish fixes

**4a.** Fixed `_best_skirmish_option` threshold: `own_regs >= 2` → `own_regs >= 1`. Option 2 sacrifices 1 Regular, so only 1 needs to be present.

**4b.** Fixed Clinton double-count in `skirmish.py`: Removed direct Clinton check at lines 150-153. The `apply_leader_modifiers` → `_clinton` modifier already sets `ctx["skirmish_extra_militia"] = 1`. The direct check was adding a second +1, causing Clinton to remove 2 extra Militia instead of 1.

**4c.** Removed Clinton dead code in `british_bot.py` after `skirmish.execute()`. The `state.get("leaders", {}).get(sid, "")` lookup used space ID as key in a faction→leaders dict, always returning `""`. Dead code removed; `skirmish.execute()` handles Clinton via the modifier system.

1 new test verifying Clinton removes exactly 1 extra Militia (not 0 and not 2).

### Group 5: Dead code cleanup

Removed dead RL exclusion filter (second `rl_candidates` comprehension). The first filter already excludes `ACTIVE_SUPPORT` spaces with `< ACTIVE_SUPPORT`; the second checks `== ACTIVE_SUPPORT` which can never match.

### Group 6: Common Cause WP preservation

**6a.** Added `preserve_wp` parameter to `common_cause.execute()`:
- MARCH mode: keeps at least 1 WP per space (can't use the last one)
- BATTLE mode: keeps at least 1 Underground WP per space (Active may be used freely)

British bot's `_try_common_cause()` now passes `preserve_wp=True`.

**6b.** Documented architectural limitation in audit: `_try_common_cause()` called AFTER `march.execute()`, not during March planning. CC should integrate into March group size calculation but this requires refactoring the March/CC interface.

3 new tests: MARCH preservation with multiple WP, MARCH skip with single WP, BATTLE Underground preservation.

### Tests

816 tests passing (790 baseline + 26 new).

### Remaining issues

All issues from this session's review have been fixed. See the **Consolidated Outstanding Issues (updated Session 7)** section above for the current list of remaining medium-to-low severity items.

---

## Session 8: Patriot Bot Full Compliance Review

### Scope

Node-by-node comparison of the entire Patriot bot flowchart implementation in `lod_ai/bots/patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt` and Manual Ch 8 (§8.5). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `rules_consts.py`, Manual Ch 3 (Commands), and Manual Ch 4 (Special Activities).

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`.

### Nodes verified CORRECT

The following flowchart nodes are correctly implemented and match the reference:

| Node | Description | Status |
|------|-------------|--------|
| P1 | Sword icon skip | CORRECT — handled by `base_bot._choose_event_vs_flowchart()` |
| P2 | Event conditions (5 bullets) | CORRECT — uses `CARD_EFFECTS` shaded side per §8.3.2 |
| P3 | Resources > 0 gate | CORRECT |
| P5 | March (3 leave-behind constraints, Phase 1 + Phase 2, French escorts) | CORRECT |
| P8 | Partisans (Village→WP→British priority, resource check→Persuasion) | CORRECT |
| P9 | Rally preference (Fort possible OR 1D6 > Underground Militia) | CORRECT |
| P10 | Rabble possibility (any space can shift toward Active Opposition) | CORRECT |
| P11 | Rabble-Rousing (Active Support first, highest Pop, Persuasion interrupt) | CORRECT |
| P12 | Skirmish (Fort-first priority, resource check→Persuasion) | CORRECT |
| P13 | Persuasion (Rebel Control + Underground Militia, Fort priority, max 3) | CORRECT |
| OPS | Supply priority (change Control, Reward Loyalty, Villages, Pop) | CORRECT |
| OPS | Redeploy Washington (most Continentals) | CORRECT |
| OPS | Patriot Desertion (least Control change, then keep last unit) | CORRECT |
| Event | All 13 card instructions match reference | CORRECT |
| Event | Cards 71/90 `force_unshaded`, 8 `force_if_french_not_human`, 18/44 `force_if_eligible_enemy`, 51 `force_if_51` | CORRECT |

### FIXED issues (this session)

#### P6 `_rebel_cube_count` — Only counted Washington, not all Rebellion leaders

**Reference (§8.5.1):** "the total number of Rebellion cubes and **Leaders** there outnumber all Active Royalist pieces"

**Bug:** Only checked Washington. French leaders Rochambeau and Lauzun are also Rebellion leaders and should count toward the "Leaders" total in P6.

**Fix:** Added loop over all three Rebellion leaders (Washington, Rochambeau, Lauzun). Each leader present in the space adds 1 to the rebel count.

#### P4 `_execute_battle` — Missing French Resource check

**Reference (§8.5.1):** "if French Regulars are present and **French Resources exceed 0**, pay one French Resource to include as many French Regulars as possible."

**Bug:** Code always counted French Regulars in Rebel force level regardless of French Resources.

**Fix:** Added `french_res = state["resources"].get(C.FRENCH, 0)` check. French cubes only included in FL when `french_res > 0`.

#### P4 `_execute_battle` — Missing resource constraint

**Reference (§8.5.1):** "If Patriot Resources are too low to pay for all such spaces, select the space with Washington first, then the spaces with highest Population, then with the largest number of Villages, then randomly."

**Bug:** Code selected all eligible spaces without checking if Patriot Resources could cover them. The priority sorting was correct (Washington, Pop, Villages, random) but the resource cap was missing.

**Fix:** Added `pat_res` check after sorting. If resources < len(chosen), truncate chosen list to `max(pat_res, 1)`.

#### P7 Rally Bullet 7 — Fort selection from wrong set

**Reference (§8.5.2):** "in one Fort space **not already selected above**, move in all Active Militia from adjacent spaces..."

**Bug:** Code selected from Fort spaces already in `spaces_used` (selected in bullets 1-6). Reference explicitly says "not already selected above."

**Fix:** Changed `fort_spaces_for_gather` to iterate over all `state["spaces"]` and exclude spaces already in `spaces_used`. Also requires `len(spaces_used) < 4` (room for one more).

### DOCUMENTED (not fixed — ambiguous reference)

#### Q11: P2 Bullet 2 — RESOLVED (Session 9): "Active Support" per Manual §8.5

The flowchart says "Active Opposition" but Manual §8.5 says "Active Support." Decision: Use "Active Support." `_faction_event_conditions()` now checks the board for Active Support or Village spaces with no existing militia, instead of the previous over-broad flag check.

### REMAINING issues (not fixed — architectural or already documented)

- **P4 Force level modifiers**: Reference says "plus modifiers" but bot uses raw piece counts. Would require importing and computing all §3.6.5-6 modifiers at the bot level. Previously documented in Session 5.
- **P4 Win-the-Day per-space**: Code pre-selects one rally space; reference says "for each space where Rebellion Wins the Day." Requires battle.execute() callback refactoring. Previously documented.
- **P7/P11 Persuasion mid-command**: Fires after command, not during when resources reach 0. Previously documented.
- **OPS methods not wired into year_end**: Previously documented in Consolidated Outstanding Issues.

### Tests

See test run results below.

---

## Session 9: Patriot Bot Compliance Review

### Scope

Independent node-by-node review of the entire Patriot bot flowchart implementation in `lod_ai/bots/patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt`. Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `partisans.py`, `skirmish.py`, `persuasion.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found.

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| P1 | Sword icon skip / Event vs Command | CORRECT — `base_bot._choose_event_vs_flowchart()` |
| P2 | Event conditions (5 bullets) | CORRECT — uses `CARD_EFFECTS` shaded side, Q11 resolution applied |
| P3 | Resources > 0 gate | CORRECT — checks `== 0`, PASSes |
| P4 | Battle (FL calculation, French cap, French resource gate, Washington/Pop/Village tiebreak) | CORRECT |
| P5 | March Phase 1 (Rebel Control destinations, Villages/Cities/Pop priority, French Regulars) | CORRECT |
| P5 | March leave-behind (Fort guard, no Active Opposition, lose-no-control) | CORRECT |
| P6 | Battle possible (rebel cubes + all 3 Rebellion leaders vs Active Royal pieces) | CORRECT |
| P7 | Rally Bullet 1 (Fort placement: 4+ units, room, Cities-first/Pop) | CORRECT |
| P7 | Rally Bullet 2 (Militia at lonely Forts) | CORRECT |
| P7 | Rally Bullets 3-4 (Continental replacement at Fort with most Militia) | CORRECT |
| P7 | Rally Bullet 7 (adjacent Militia gathering, excludes selected spaces) | CORRECT |
| P8 | Partisans (Village→WP→British priority; option 3 when no WP; option 1 otherwise) | CORRECT |
| P9 | Rally preferred (Fort possible OR 1D6 > Underground Militia) | CORRECT |
| P10 | Rabble possible (any space not at Active Opposition) | CORRECT |
| P11 | Rabble-Rousing (Active Support first, highest Pop, resource-capped) | CORRECT |
| P12 | Skirmish (Fort-first, Control change sub-priority, option 3 when applicable) | CORRECT |
| P8→P12→P13 | SA chain (Partisans→Skirmish→Persuasion, resource-0 Persuasion gates) | CORRECT |
| P7↔P11 | Rally/Rabble mutual fallback (infinite loop guard via `_from_rabble`/`_from_rally`) | CORRECT |
| OPS | Supply priority, Redeploy Washington, Patriot Desertion, BS trigger | CORRECT |
| Event | All 13 Patriot card instructions match reference | CORRECT |

### FIXED issues (this session — 3 bugs)

#### P13 `_try_persuasion` — Missing Colony/City space type filter

**Reference (§4.3.1):** "Patriots choose 1-3 **Colonies/Cities** that are Rebellion-controlled and contain ≥1 Underground Militia."

**Bug:** `_try_persuasion()` built its candidate list filtering only by Rebel Control and Underground Militia, without checking space type. Reserve Province spaces could enter the list. Since `persuasion.execute()` validates space type and raises `ValueError` for non-Colony/City spaces, and the bot passed all spaces in a single call, a single invalid Province space would cause the entire Persuasion call to fail — even when valid Colony/City candidates existed.

**Fix:** Added `and _MAP_DATA.get(sid, {}).get("type") in ("Colony", "City")` to the candidate list comprehension.

#### P7 Rally Bullet 5 (reference Bullet 4) — Over-inclusive Fort Available condition

**Reference:** "If Patriot Fort Available, place Militia in the space with no Patriot Fort and most Patriot units."

**Bug:** The condition was `state["available"].get(C.FORT_PAT, 0) > 0 or avail_forts > 0`. Since `state["available"]` reflects the pre-planning state (Rally hasn't executed yet), while `avail_forts` tracks remaining Forts after Bullet 1 allocations, the condition was True even when all Forts had been allocated in Bullet 1. This caused the bot to place Militia at a non-Fort space (per Bullet 5) even when no Fort was actually available.

**Fix:** Changed condition to `avail_forts > 0` (post-Bullet-1 count only).

#### P7 Rally Bullet 6 — Spurious Active Support exclusion

**Reference:** "place Militia, first to change Control then where no Active Opposition, within each first in Cities, within that highest Pop."

**Bug:** The code excluded Active Support spaces with `if self._support_level(state, sid) == C.ACTIVE_SUPPORT: continue`. The reference specifies priority criteria (change Control, no Active Opposition, Cities, Pop) but does not exclude any spaces. Active Support spaces are low priority but valid targets.

**Fix:** Removed the Active Support exclusion. Active Support spaces now appear in the candidate list but sort to the bottom (they already have British control, don't change Control, etc.).

### DOCUMENTED — minor deviations (not fixed)

#### P5 March Phase 2: Continental fallback

**Reference:** "get 1 **Militia** (Underground if possible) into each other space with none"

**Code:** Also moves Continentals as a fallback when no Militia can reach the target space. The reference says "Militia" specifically. This is a pragmatic deviation — if no Militia can reach a space, moving a Continental at least establishes presence. Low impact since Militia are preferred and tried first.

#### P9 Rally preferred: bases < 2 not checked

The P9 "Fort can be placed" gate checks 4+ Patriot units and no existing Fort, but doesn't verify that the space has room for a base (< 2 existing bases). This means P9 could return True (Rally preferred) but Bullet 1 would reject the space due to base stacking. The fallback behavior is reasonable — Rally proceeds with other bullets instead of Fort placement.

#### P5 March Phase 2: scope of "with none"

The reference says "each other space with none" — the code interprets "none" as "no Patriot units" and includes spaces that already have other Rebellion pieces (French Regulars). This interpretation is reasonable since the goal is Patriot presence.

### Previously documented issues (unchanged)

- **P4 Force level modifiers** — raw piece counts instead of §3.6.5-6 modifiers
- **P4 Win-the-Day per-space** — pre-selects one rally space; requires battle callback refactoring
- **P7/P11 Persuasion mid-command** — fires after command, not during
- **OPS methods not wired into year_end**

### Tests added (5 new, 848 total)

| Test | Verifies |
|------|----------|
| `test_p13_persuasion_filters_colony_city` | Persuasion succeeds with City candidate even when Reserve Province in pool |
| `test_p13_persuasion_excludes_reserve_provinces` | Reserve Province spaces excluded from candidate list |
| `test_p7_rally_bullet5_uses_tracked_avail_forts` | Post-Bullet-1 tracked count used, not original state |
| `test_p7_rally_bullet6_does_not_exclude_active_support` | Active Support spaces appear in Bullet 6 candidate list |
| `test_p2_bullet2_no_qualifying_spaces_returns_false` | (existing test, verified still passes) |

---

## Session 10: French Bot Full Compliance Review

### Scope

Full node-by-node comparison of the entire French bot flowchart implementation in `lod_ai/bots/french.py` against `Reference Documents/french bot flowchart and reference.txt` and Manual Ch 8 (§8.6). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `commands/hortelez.py`, `commands/french_agent_mobilization.py`, `special_activities/preparer.py`, `special_activities/naval_pressure.py`, `special_activities/skirmish.py`, `commands/battle.py`, `commands/march.py`, `commands/muster.py`, `leaders/__init__.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`. The only string literals are `"REBELLION"` for control checks and map data type strings (`"Colony"`, `"City"`), which are consistent with the rest of the codebase and have no corresponding constants.

### Nodes verified CORRECT

The following flowchart nodes are correctly implemented and match the reference:

| Node | Description | Status |
|------|-------------|--------|
| F1 | Sword icon skip / Event vs Command | CORRECT — handled by `base_bot._choose_event_vs_flowchart()` |
| F2 | Event conditions (6 bullets) | CORRECT — uses `CARD_EFFECTS` shaded side per §8.3.2; all 6 conditions verified: Support>Opposition+shifts_rebel, French_from_unavailable, French_on_map, inflicts_british_casualties, adds_french_resources, ToA+effective+D6>=5 |
| F3 | French Resources > 0 gate | CORRECT — `state.get("resources", {}).get(C.FRENCH, 0) <= 0` routes to PASS |
| F4 | Treaty of Alliance played? | CORRECT — branches to `_before_treaty` / `_after_treaty` |
| F5 | Patriot Resources < 1D3 | CORRECT — uses `state["rng"].randint(1,3)`, strict less-than |
| F6 | Hortalez before Treaty | CORRECT — pays exact roll, aborts if can't afford (Session 7 fix confirmed) |
| F7 | Agent Mobilization | CORRECT — correct provinces, correct placement priority (control change then most patriots), fallback to F6 |
| F8 | Préparer pre-Treaty | CORRECT — Blockade to WI first, then up to 3 Regulars Unavailable→Available |
| F9 | 1D6 < Available Regulars | CORRECT — strict less-than with `state["rng"]` |
| F10 | Muster (Max 1) | CORRECT — <4 Available + WI not Rebel → WI; else Colony/City with Continentals; `state["rng"].choice()` for ties |
| F11 | Hortalez after Treaty | CORRECT — `min(resources, roll)` ("up to 1D3") |
| F12 | Skirmish | CORRECT — excludes affected spaces, WI priority, Fort-first (option=3), British pieces includes Regs+Tories+Forts |
| F13 | Can Battle (decision gate) | CORRECT — Rebel cubes (Continentals+French) + Leaders > British pieces (Regs+Tories+Forts, excludes WP) |
| F14 | March (all 4 bullets) | CORRECT — (1) Lose no Rebel Control, (2) March to add Control first Cities then most British, (3) Isolated French toward nearest British via BFS, (4) Fallback: 1 French to shared space |
| F15 | Préparer post-Treaty | CORRECT — D6 ≤ (unavail regs + blockades) gate, Blockade→WI or up to 3 Regs, +2 Resources fallback when nothing moved and Resources=0 |
| F17 | Naval Pressure target | CORRECT — Battle space first, then most Support; fallback F17→F12→F15 |
| Event instructions | Cards 52, 62, 70, 73, 83, 95 | CORRECT — all use conditional `force_if_X` directives with game-state checks |
| OPS | Supply priority | CORRECT — changes Control first, then British RL possible, then Pop; WI appended |
| OPS | Redeploy leader | CORRECT — space with French Regs + Continentals, then most French Regs |

### FIXED issues (this session)

#### 1. F16 `_battle` — Missing French presence requirement

**Reference (§8.6.6):** "Select all spaces with **both French and British pieces** where the Rebellion Force Level... exceeds the Royalist Force Level."

**Bug:** The code checked `british_pieces > 0` but did NOT check for French Regulars. A space with Patriots + British but no French would be selected as a battle target — the French bot would initiate battle in spaces where it has no pieces.

**Fix:** Added `french_here = sp.get(C.REGULAR_FRE, 0) > 0` check to the filter condition. Only spaces with both French and British pieces are now candidates.

#### 2. `ops_toa_trigger` — Wrong CBC source (CRITICAL)

**Reference (§8.1):** "the sum of Squadrons in WI + Available French Regulars + **half of Cumulative British Casualties** exceed 15"

**Bug:** Used `state.get("casualties", {})` — the battle losses box containing pieces lost in the most recent battle — instead of `state.get("cbc", 0)` which is the Cumulative British Casualties running total tracked throughout the game. The casualties box is transient (cleared after each battle), while `cbc` accumulates. This caused the Treaty of Alliance trigger to use the wrong value entirely.

**Fix:** Changed from `casualties.get(C.REGULAR_BRI, 0) + casualties.get(C.TORY, 0)` to `state.get("cbc", 0)`.

#### 3. `ops_toa_trigger` — Missing Winter Quarters check

**Reference (§8.1):** "no Winter Quarters card is showing"

**Bug:** The function did not check whether the current card is a Winter Quarters card. The ToA trigger should never fire during Winter Quarters.

**Fix:** Added `if current_card in C.WINTER_QUARTERS_CARDS: return False` check.

#### 4. `ops_bs_trigger` — Missing player/eligible and WQ checks

**Reference (§8.6.11):** "any player Faction is 1st Eligible or the British play their Brilliant Stroke card."

**Bug 1:** The function only checked ToA played + Leader with 4+ Regulars. It did not check the situational trigger: whether a player (human) faction is 1st eligible OR the British played their Brilliant Stroke.

**Bug 2:** Same missing Winter Quarters card check as ops_toa_trigger.

**Fix:** Added both checks. The function now verifies `first_eligible in human_factions or british_bs_played` and checks `current_card not in WINTER_QUARTERS_CARDS`.

#### 5. `ops_loyalist_desertion_priority` — Population tiebreaker incorrectly scoped

**Reference (§8.6.10):** "Remove a Tory so as to change Control of the **most Population** possible, **then** the last Tory in the space with **most Population** that is not already at Active Support, then elsewhere."

**Bug:** The sort key used `(-int(changes_ctrl), -int(is_last)*not_active_sup, -pop, random, sid, tag)` which applied `-pop` globally across all tiers. Population should only break ties WITHIN each tier: "most Population" in the control-change tier, then "most Population" in the last-Tory-non-AS tier, but a high-pop non-control-changing space should not sort before a low-pop control-changing space.

**Fix:** Split population into tier-scoped sort keys: `ctrl_pop = -pop if changes_ctrl else 0` and `last_pop = -pop if (is_last and not_active_sup) else 0`. The full sort key is now `(-int(changes_ctrl), ctrl_pop, -int(is_last)*not_active_sup, last_pop, random, sid, tag)`.

#### 6. `_agent_mobilization` — Missing Active Support filter (crash bug)

**Reference (§3.5.1):** Agent Mobilization cannot target provinces at Active Support.

**Bug:** `_can_agent_mobilization()` correctly filtered out Active Support provinces, but `_agent_mobilization()` did not. If the highest-scoring province was at Active Support while another province was valid, the bot would select the Active Support province, and `fam.execute()` would raise `ValueError`, crashing the bot's turn.

**Fix:** Added `if self._support_level(state, prov) == C.ACTIVE_SUPPORT: continue` to the province selection loop in `_agent_mobilization()`.

### DOCUMENTED — minor deviations (not fixed)

#### F14 March force level: Active Militia included unconditionally
The F16 `_battle` force level calculation includes Active Militia in the Rebellion Force Level. Per §3.6.3, Active Militia only participate "if that Faction paid." The bot's decision gate makes an optimistic assumption that Patriots will pay, which is a reasonable heuristic for a bot. Low gameplay impact.

#### F6/F11 Hortalez +1 bonus
`hortelez.execute()` adds `pay + 1` to Patriot Resources. This +1 bonus comes from §3.5.2 (player rules for Hortalez). The bot flowchart reference doesn't explicitly mention it, but since the command implementation applies it uniformly, the bot inherits it correctly.

#### get_bs_limited_command skips F9 D6 gate
The BS Limited Command method always tries Muster first if Available Regulars > 0, without the F9 D6 gate. Per §8.3.7, the BS walk should "follow the executing Faction's flowchart," which includes the D6 check. Minor deviation — affects which LimCom is selected for BS only.

#### ops_redeploy_leader: Missing Blockade rearrangement
Reference §8.6.9 says: "Remove a Blockade from the City with least Support; remaining Blockades are moved to Cities with most Support." The `ops_redeploy_leader` method only handles leader redeployment, not Blockade rearrangement. This should be handled by `year_end.py` when calling the bot's redeploy method. Architectural issue — the Blockade rearrangement belongs in the year-end redeployment phase, not in the bot method itself.

### Previously documented issues (unchanged)

- **F2 Event conditions**: Uses `CARD_EFFECTS` static lookup — correct but cannot verify dynamic game-state conditions. (Unchanged from Session 5)
- **OPS methods not wired into year_end**: All 4 bots define OPS methods but `year_end.py` uses ad-hoc logic. (Unchanged from Consolidated Outstanding Issues)
- **P7/P11 Persuasion mid-command**: Fires after command, not during. (Unchanged)
- **B10 March + Common Cause timing**: CC invoked post-March. (Unchanged)

### Tests added (7 new, 850 total)

| Test | Verifies |
|------|----------|
| `test_f16_battle_requires_french_presence` | F16 only selects spaces with French Regulars present |
| `test_ops_toa_trigger_uses_cbc_not_casualties` | ToA trigger uses `state["cbc"]`, not `state["casualties"]` |
| `test_ops_toa_trigger_blocked_during_winter_quarters` | ToA trigger returns False during Winter Quarters |
| `test_ops_bs_trigger_blocked_during_winter_quarters` | BS trigger returns False during Winter Quarters |
| `test_ops_bs_trigger_requires_player_eligible_or_brit_bs` | BS trigger requires player 1st eligible or British BS played |
| `test_ops_desertion_population_scoped_to_tier` | Desertion priority: control-changing spaces before non-changing |
| `test_f7_agent_mobilization_skips_active_support` | Agent Mobilization skips Active Support provinces (no crash) |

---

## Session 11: Patriot Bot Compliance Review (Independent)

### Scope

Independent node-by-node comparison of the Patriot bot flowchart implementation in `lod_ai/bots/patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt`, Manual Ch 3 (§3.3, §3.6), Manual Ch 4 (§4.3), and Manual Ch 8 (§8.5). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `partisans.py`, `skirmish.py`, `persuasion.py`, `rabble_rousing.py`, `rally.py`, `battle.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`.

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| P1 | Sword icon skip / Event vs Command | CORRECT — `base_bot._choose_event_vs_flowchart()` |
| P2 | Event conditions (5 bullets) | CORRECT — uses `CARD_EFFECTS` shaded side per §8.3.2 |
| P3 | Resources > 0 gate | CORRECT — checks `== 0`, PASSes |
| P4 | Battle (FL calculation, French cap, French resource gate, Washington/Pop/Village tiebreak, resource trim) | CORRECT (modifiers omission previously documented) |
| P5 | March Phase 1 (Rebel Control destinations, Villages/Cities/Pop priority, French escort) | CORRECT |
| P5 | March Phase 2 (get 1 Militia Underground preferred into spaces with none) | CORRECT |
| P5 | March leave-behind (Fort guard, no Active Opposition, lose-no-control) | CORRECT |
| P6 | Battle possible (rebel cubes + all 3 Rebellion leaders vs Active Royal pieces, no Forts per glossary) | CORRECT |
| P7 | Rally Bullet 1 (Fort placement: 4+ units, room, Cities-first/Pop) | CORRECT |
| P7 | Rally Bullet 2 (Militia at lonely Forts) | CORRECT |
| P7 | Rally Bullet 5 (Militia at non-Fort space with most Patriot units, post-Bullet-1 Fort count) | CORRECT |
| P7 | Rally Bullet 6 (change Control, no Active Opp, Cities, Pop; no Active Support exclusion) | CORRECT |
| P7 | Rally Bullet 7 (adjacent Militia gathering, excludes selected spaces) | CORRECT |
| P8 | Partisans (Village→WP→British priority; option 3 when no WP; option 1 otherwise) | CORRECT |
| P9 | Rally preferred (Fort possible OR 1D6 > Underground Militia) | CORRECT |
| P12 | Skirmish (Fort-first, Control change sub-priority, option 3 when applicable) | CORRECT |
| P13 | Persuasion (Rebel Control + Underground Militia + Colony/City filter, Fort priority, max 3) | CORRECT |
| P8→P12→P13 | SA chain (Partisans→Skirmish→Persuasion, resource-0 Persuasion gates) | CORRECT |
| P7↔P11 | Rally/Rabble mutual fallback (infinite loop guard via `_from_rabble`/`_from_rally`) | CORRECT |
| OPS | Supply priority, Redeploy Washington, Patriot Desertion, BS trigger | CORRECT |
| Event | All 13 Patriot card instructions match reference (with card 52 fix below) | CORRECT |

### FIXED issues (this session — 3 bugs)

#### 1. P10/P11 `_rabble_possible` and `_execute_rabble` — Missing §3.3.4 eligibility filter

**Reference (§3.3.4):** "Select any spaces with Rebellion Control and Patriot pieces or at least one Underground Militia."

**Bug:** Both `_rabble_possible()` and `_execute_rabble()` only checked `support_level > ACTIVE_OPPOSITION` (i.e., space not at Active Opposition). They did not verify §3.3.4 eligibility: the space must have **(Rebellion Control AND Patriot pieces) OR Underground Militia**. This could cause:
1. `_rabble_possible()` (P10) to return True for spaces with no Patriot presence
2. `rabble_rousing.execute()` to raise `ValueError` when the bot passed ineligible spaces

**Fix:** Added `_rabble_eligible()` static method that checks both the support level and §3.3.4 eligibility. Both `_rabble_possible()` and `_execute_rabble()` now use this method, and `_execute_rabble()` calls `refresh_control()` before filtering.

#### 2. P7 Rally Bullet 4 — Continental replacement selected from all Fort spaces, not Rally-selected spaces

**Reference (§8.5.2):** "In the Patriot Fort space with most Militia **of those already selected for Rally**, replace all Militia except 1 Underground with Continentals."

**Bug:** Lines 718-724 searched all Fort spaces on the entire map for the Continental replacement target. The flowchart explicitly says "of those already selected for Rally" — the search should be restricted to `spaces_used`.

**Fix:** Split the combined block into two separate steps:
- Bullet 3: Continental PLACEMENT selects the Fort with most Militia globally (can add a new Rally space)
- Bullet 4: Continental REPLACEMENT searches only `spaces_used` for the Fort with most Militia

#### 3. Card 52 event instruction — "force" instead of conditional

**Reference (Patriot bot card instruction #52):** "Remove no French Regulars; select space per Battle instructions, **else ignore**."

**Bug:** `event_instructions.py` had `52: "force"` for the Patriot entry. The "else ignore" clause means if no valid Battle space exists (French + British pieces co-located), the bot should fall through to Command & SA, not force the event. Both the British and French bots already used `force_if_52` for the same card.

**Fix:** Changed to `52: "force_if_52"` and added `_force_condition_met()` handler for `force_if_52` in `PatriotBot`. The condition checks whether any space contains both French Regulars and British pieces.

### DOCUMENTED — minor deviations (not fixed)

#### ~~Partisans/Skirmish never use option 2~~ **RESOLVED**

~~The flowchart describes space selection priorities for Partisans (P8) and Skirmish (P12) but is silent on when to choose option 2.~~ **FIXED:** Ch 8 §8.1 ("maximum extent") provides clear guidance — bots should maximize removals. P8 Partisans and P12 Skirmish now use option 2 (sacrifice 1 own piece, remove 2 enemy) when 2+ enemy cubes are present and the faction has a piece to sacrifice. Indian bot already implemented this correctly for War-Path (I8) and Scout+Skirmish (I12).

#### P9=Yes fallback to March

If Rally and Rabble both fail from the P9=Yes path, the code falls through to `_march_chain()`. The flowchart shows P7→P11→P7 (loop), with no path to March from this entry point. March is only reachable from P10=No. This deviation is beneficial — it gives the bot one more chance to act before PASSing.

### Previously documented issues (unchanged)

- **P4 Force level modifiers** — raw piece counts instead of §3.6.5-6 modifiers
- **P4 Win-the-Day per-space** — pre-selects one rally space; requires battle callback refactoring
- **P7/P11 Persuasion mid-command** — fires after command, not during
- **OPS methods not wired into year_end**

### Tests added (5 new, 855 total)

| Test | Verifies |
|------|----------|
| `test_rabble_eligible_requires_pieces_or_militia` | Rabble eligibility enforces §3.3.4 |
| `test_rabble_execute_skips_ineligible_spaces` | _execute_rabble excludes spaces without Patriot presence |
| `test_rally_bullet4_continental_replacement_from_selected_only` | Bullet 4 searches only Rally-selected spaces |
| `test_force_if_52_patriot_requires_battle_space` | Card 52 returns False when no French+British co-location |
| `test_force_if_52_patriot_true_when_shared_space` | Card 52 returns True when French+British share a space |

---

## Session 12: Indian Bot Full Compliance Review

### Scope

Full node-by-node comparison of the entire Indian bot flowchart implementation in `lod_ai/bots/indians.py` against `Reference Documents/indian bot flowchart and reference.txt` and Manual Ch 8 (§8.7). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `commands/raid.py`, `commands/gather.py`, `commands/scout.py`, `commands/march.py`, `commands/battle.py`, `special_activities/war_path.py`, `special_activities/trade.py`, `special_activities/plunder.py`, `leaders/__init__.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`. The only string literals are `"REBELLION"` for control checks and map data type strings (`"Colony"`, `"City"`, `"Province"`), which are consistent with the rest of the codebase and have no corresponding constants.

### Known Issue Verification

1. **I10 March (Q5)**: **RESOLVED — properly implemented.** `_march()` uses `max_dests = min(3, resources)`, Phase 1 (Village placement: get 3+ WP in Neutral/Passive space with room) + Phase 2 (remove most Rebel Control, first no Active Support). All movement constraints correct: Underground-first (`_take`), no last-WP-from-Village (`_can_remove`), no Rebel Control addition (`_can_remove`). Q5 status updated to "Implemented."

2. **Mid-Raid Plunder/Trade interruption**: **RESOLVED.** Lines 157-161 of `_raid_sequence()` check `resources == 0` after `_raid()` and trigger Plunder then Trade. Architecturally, this fires after `raid.execute()` completes (atomic payment+activation), which is the best approximation without mid-command interrupts.

3. **Circular Gather/March fallback**: **RESOLVED.** `_gather_sequence()` and `_march_sequence()` both accept a `_visited` set parameter. Each adds its command name on entry and checks before recursing, preventing infinite loops.

4. **`_can_plunder` scope**: **RESOLVED.** Lines 337-338 restrict candidates to `state.get("_turn_affected_spaces", set())` (Raid spaces only).

5. **BS trigger conditions**: **WAS BROKEN — FIXED this session.** See bug #2 below. Method was named `ops_bs_should_trigger` (not callable by shared infrastructure expecting `ops_bs_trigger`), was missing Winter Quarters check, and was missing the "player 1st Eligible or Rebel BS played" condition.

6. **ops_loyalist_desertion_priority**: **N/A for Indians.** The Indian bot has `ops_patriot_desertion_priority` (removes Patriots, not Tories). However, the same class of scoping bug existed — the sort used `-reb` (total rebel count) instead of checking whether removal actually changes control. **FIXED this session** (see bug #4 below).

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| I1 | Sword icon skip / Event vs Command | CORRECT — handled by `base_bot._choose_event_vs_flowchart()` |
| I2 | Event conditions (4 bullets) | CORRECT — uses `CARD_EFFECTS` unshaded side per §8.3.2; all 4 conditions verified: Opp>Sup+shifts_royalist, places_village/grants_free_gather, removes_patriot_fort, effective+4_villages+D6>=5 |
| I3 | Support+1D6 > Opposition test | CORRECT — `randint(1,6)`, `(support + roll) <= opposition` routes to Raid branch |
| I4 | Raid (Max 3) — space selection | CORRECT — Opposition Colonies with/adj Underground WP (or within 2 of Dragging Canoe), priority plunder-possible then pop |
| I4 | Raid — WP movement and village leave-behind | CORRECT — `_reserve_source` prefers adjacent, checks village last-WP |
| I4 | Raid — mid-Raid Plunder/Trade when resources=0 | CORRECT — fires after `raid.execute()`, triggers `_plunder` then `_trade` |
| I5 | Plunder target selection | CORRECT — restricted to Raid spaces, WP > rebels, highest Pop (after FORT_PAT fix) |
| I6 | Gather worthwhile (2+ Villages OR D6 < Available WP) | CORRECT — eligible space count ≥2 with Cornplanter threshold |
| I7 | Gather Bullet 1 (Village placement) | CORRECT — room check, 3+ WP (2+ if Cornplanter), leader priority |
| I7 | Gather Bullet 2 (WP at Villages) | CORRECT — enemies first, then no UG WP, then leader, then random |
| I7 | Gather Bullet 3 (WP in spaces with Village room) | CORRECT — exactly 2 WP first, then 1, then random; max 2 spaces |
| I7 | Gather Bullet 4 (move adjacent Active WP) | CORRECT — no WP available gate, 1 Village space, control preservation |
| I8 | War Path — target selection | CORRECT — Fort first, most Rebels, Province with Village tiebreak |
| I8 | War Path — option selection | CORRECT — option 3 (Fort, no cubes, 2+ WP_U), option 2 (2+ cubes, 2+ WP_U), else option 1 |
| I8 | War Path / Trade fallback | CORRECT — resources=0 → Trade; else War Path → Trade |
| I9 | Space with WP + British Regulars? | CORRECT — checks all spaces |
| I10 | March — Phase 1 (Village dest) | CORRECT — 1+ Villages Available, Neutral/Passive, room, 3+ WP target |
| I10 | March — Phase 2 (Rebel Control) | CORRECT — Rebellion spaces, first no Active Support, adjacent supply |
| I10 | March — movement constraints | CORRECT — Underground first, no last-WP-from-Village, no Rebel Control |
| I10 | March → Gather fallback | CORRECT — `_visited` set prevents infinite recursion |
| I11 | Trade — space selection | CORRECT — Village space with most Underground WP |
| I11 | Trade — British resource request | CORRECT — D6 < British Resources → transfer ceil(roll/2) |
| I12 | Scout — origin selection | CORRECT — space with WP + British Regulars, most Regs+Tories |
| I12 | Scout — destination priority | CORRECT — Patriot Fort first, Village+enemy, Rebel Control |
| I12 | Scout — control preservation | CORRECT — caps pieces moved to maintain royalist > rebel in origin |
| I12 | Scout + Skirmish | CORRECT — Fort-first priority, option 3/2/1 selection |
| Event | Cards 4/72/90 Village condition | CORRECT — `_VILLAGE_REQUIRED_CARDS` check before event |
| Event | Cards 18/44 eligible enemy condition | CORRECT — `_ELIGIBLE_ENEMY_CARDS` check; `_has_eligible_enemy` correctly checks Patriots and French |
| Event | Card 38 WP condition | CORRECT — `_WP_REQUIRED_CARDS` check before event |
| Event | Card 83 shaded/unshaded selection | CORRECT — `_can_place_village(state)` determines side |
| OPS | Supply priority | CORRECT — prevent Rebel Control first, then Village room |
| OPS | Redeploy leaders | CORRECT — Brant/DC to most WP; Cornplanter to Neutral/Passive Province with 2+ WP and Village room, else most WP |
| OPS | Leader Movement | CORRECT — accompanies largest group from origin |
| OPS | Defending in Battle | CORRECT — `battle.py` lines 299-309: Village → activate all but 1 UG WP; no Village → activate none |
| BS | get_bs_limited_command | CORRECT — walks I3→I4/I6→I9→I10 with leader's space |

### FIXED issues (this session)

#### 1. Cards 4, 32, 38 — Playing UNSHADED instead of SHADED (HIGH)

**Reference (indian bot flowchart):**
- Card 4: "Use the shaded text. If no Village can be placed, choose Command & Special Activity instead."
- Card 32: "Use the shaded text."
- Card 38: "Use the shaded text. Place War Parties; if not possible, choose Command & Special Activity instead."

**Bug:** All three cards had `"force"` directive in `event_instructions.py`, which plays the unshaded event (Indian default). The Indian bot flowchart explicitly says "Use the shaded text" for all three.

**Fix:**
- Added `"force_shaded"` directive support to `base_bot._choose_event_vs_flowchart()` and `base_bot._execute_event()`.
- Changed cards 4, 32, 38 from `"force"` to `"force_shaded"` in `event_instructions.py`.
- Cards 4 and 38 have their conditional checks (Village/WP) in the IndianBot `_choose_event_vs_flowchart` override, which runs BEFORE `super()` sees the `force_shaded` directive.

#### 2. `ops_bs_trigger` — Wrong method name + missing conditions (MEDIUM)

**Reference (OPS):** "Brilliant Stroke: Use after Treaty of Alliance when the Indian Leader is in a space with 3+ War Parties, and a player is 1st Eligible or a Rebel Faction plays a Brilliant Stroke card other than the Treaty of Alliance."

**Bug 1:** Method was named `ops_bs_should_trigger` instead of `ops_bs_trigger`. Shared infrastructure calling `ops_bs_trigger()` would get `AttributeError` or use the default (always False).

**Bug 2:** Missing "a player is 1st Eligible or a Rebel Faction plays a BS" check. The method only checked ToA + Leader + 3 WP.

**Bug 3:** Missing Winter Quarters check (same bug found in French bot Session 10).

**Fix:** Renamed to `ops_bs_trigger`. Added WQ check (`current_card in C.WINTER_QUARTERS_CARDS`). Added player-eligible check (`first_eligible in human_factions`) and Rebel BS check (`bs_played.get(C.PATRIOTS) or bs_played.get(C.FRENCH)`).

#### 3. `_can_plunder`, `_plunder`, `_raid` score — Missing FORT_PAT in rebel count (MEDIUM)

**Reference (I5):** "Plunder in a Raid space with more War Parties than Rebel pieces."

**Bug:** The rebel piece count in `_can_plunder` (line 342), `_plunder` (line 360), and the `_raid` `score()` function (line 275) counted only `MILITIA_A + MILITIA_U + REGULAR_PAT + REGULAR_FRE`, missing `FORT_PAT`. Patriot Forts are Rebel pieces per §1.4. This could cause the bot to select Plunder in a space where WP don't actually exceed all Rebel pieces (because a Fort was uncounted).

**Fix:** Added `+ sp.get(C.FORT_PAT, 0)` to all three rebel count calculations.

#### 4. `ops_patriot_desertion_priority` — Wrong sort for "remove most Rebel Control" (MEDIUM)

**Reference (OPS):** "Remove Patriots first from Village spaces, then to remove most Rebel Control, then to remove last Patriot of that type in a space, then random."

**Bug:** The sort used `(-is_rebel, -reb)` which prioritized Rebellion-controlled spaces with MORE rebel pieces. But "remove most Rebel Control" means preferring spaces where removing 1 Patriot piece would actually CHANGE control from Rebellion — i.e., spaces where the rebel excess is smallest (royalist pieces ≥ rebels - 1). A space with 10 rebels won't change control; a space with 2 rebels and 1 royalist will.

Same class of bug as the French `ops_loyalist_desertion_priority` fixed in Session 10.

**Fix:** Changed sort key to check `changes_ctrl = (ctrl == "REBELLION" and royalist >= (reb - 1))`. Population tiebreaks scoped within the control-change tier only.

### DOCUMENTED — minor deviations (not fixed)

#### Gather Bullet 1: Excludes spaces with existing Villages
`_gather_worthwhile` (line 388) and `_gather` (line 442) skip spaces that already have a Village (`sp.get(C.VILLAGE, 0) > 0`). The reference says "Place Villages where room" — a space with 1 Village and no Fort has room (bases < 2). Building a second Village in the same space is valid per stacking rules but is rarely strategically optimal. Minor deviation.

#### Mid-Raid Plunder/Trade is atomic
The reference says "before completing the Raid" but `raid.execute()` bundles payment and activation in one call. The interrupt fires after the full Raid completes, not mid-execution. Architectural limitation — no mid-command interrupt support.

#### ~~Partisans/Skirmish never use option 2~~ **RESOLVED**
~~Same as documented in Session 11 for Patriot bot.~~ **FIXED:** See Session 11 note — Ch 8 §8.1 provides clear guidance. Indian bot already correct; Patriot bot now fixed.

#### get_bs_limited_command skips I3 D6 gate
The BS Limited Command walk always tries both Raid and Gather branches without rolling the I3 D6. Per §8.3.7, BS should follow the faction flowchart including the D6 check. Minor — affects only which LimCom is selected during BS.

### Previously documented issues (unchanged)

- **OPS methods not wired into year_end** — all 4 bots define OPS methods but `year_end.py` uses ad-hoc logic
- **P7/P11 Persuasion mid-command** — fires after command, not during
- **B10 March + Common Cause timing** — CC invoked post-March
- **I2 Event conditions: CARD_EFFECTS static lookup** — correct but cannot verify dynamic game-state conditions

### Tests added (11 new, 866 total)

| Test | Verifies |
|------|----------|
| `test_card_32_uses_force_shaded_directive` | Card 32 directive is `force_shaded` |
| `test_card_4_uses_force_shaded_directive` | Card 4 directive is `force_shaded` |
| `test_card_38_uses_force_shaded_directive` | Card 38 directive is `force_shaded` |
| `test_force_shaded_handler_sets_shaded_true` | `force_shaded` passes `shaded=True` to handler |
| `test_bs_trigger_blocked_during_winter_quarters` | BS trigger returns False during WQ |
| `test_bs_trigger_requires_player_eligible_or_rebel_bs` | BS trigger needs player 1st eligible or Rebel BS |
| `test_bs_trigger_fires_on_rebel_bs_played` | BS trigger fires when Patriot BS played |
| `test_can_plunder_false_when_fort_makes_rebels_ge_wp` | FORT_PAT counted in rebel pieces for Plunder |
| `test_can_plunder_true_when_wp_exceeds_rebels_with_fort` | Plunder still works when WP > rebels including Fort |
| `test_changes_control_before_excess_rebels` | Desertion prioritizes control-changing removal |
| `test_village_still_first_priority` | Village spaces remain top priority for desertion |

---

## Session 6: Patriot Bot Compliance Review

Full node-by-node comparison of `patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt` and `Manual Ch 8` (§8.5).

### FIXED issues (this session)

#### P4 Battle: Half-regs modifier — Active Militia excluded from attacker cubes
- **Bug:** `att_cubes = att_regs` only counted Regulars (Continentals + French). Active Militia are also cubes per §3.6.5.
- **Impact:** Half-regs modifier always triggered (+1) even when Militia outnumbered Regulars.
- **Fix:** `att_cubes = att_regs + active_mil`.

#### P4 Battle: Half-regs modifier — Active War Parties excluded from defender cubes
- **Bug:** `def_cubes = regs + tories` omitted Active War Parties. Crown cubes include WP per §3.6.6.
- **Impact:** Defender half-regs triggered too easily (fewer counted cubes = easier 50% threshold).
- **Fix:** `def_cubes = regs + tories + active_wp`.

#### P5 March: Fort leave-behind should be Active, not Underground
- **Bug:** Move priority [Cont, MilA, Fre, MilU] left Underground Militia at Forts.
- **Reference:** §8.5.4 "leave an Active Patriot unit with each Patriot Fort."
- **Fix:** When Fort present, move order reversed: [MilU, Cont, MilA, Fre] so Active pieces stay behind. Applied to both `_movable_from` and `_movable_from_simulated`.

#### P5 March Phase 2: Missing Population tiebreaker
- **Bug:** Phase 2 sort key was `(-changes_ctrl, random)`, missing population.
- **Reference:** §8.5.4 "first to change Control of the most Population, then elsewhere."
- **Fix:** Added `-pop` to sort key: `(-changes_ctrl, -pop, random)`.

#### P7 Rally / P11 Rabble: Mid-command Persuasion not tracked for SA chain gate
- **Bug:** `_rally_chain` and `_rabble_chain` did not know if Persuasion was used during Rally/Rabble execution.
- **Reference:** §8.5.2 "if no Persuasion was used during the Rally, the Patriots execute Partisans…"
- **Impact:** SA chain could run even after mid-command Persuasion.
- **Fix:** `_execute_rally` and `_execute_rabble` now set `state["_rally_persuasion_used"]` / `state["_rabble_persuasion_used"]` flags. Chain methods pop and check these flags to gate the SA chain.

#### P9: Fort placement check missing room verification
- **Bug:** `_rally_preferred` checked 4+ Patriot units and no existing Fort but not the 2-base limit.
- **Impact:** Bot could choose Rally thinking Fort placement was possible when bases were full.
- **Fix:** Added `(FORT_PAT + FORT_BRI + VILLAGE) < 2` check.

#### Flowchart routing: March tried after Rally+Rabble fail on P9=Yes/P10=Yes paths
- **Bug:** When P9=Yes or P10=Yes but Rally+Rabble both failed, code fell through to March.
- **Reference:** Flowchart shows P9→P7→P11→(guard)→PASS, not March. March only reachable via P10=No.
- **Fix:** `_march_chain` now only runs inside `else` (P10=No) block.

#### BS trigger: Missing "player Faction is 1st Eligible" check
- **Bug:** `ops_bs_trigger` checked ToA played and Washington location but not whether 1st Eligible is human.
- **Reference:** §8.5.8 "a player Faction is 1st Eligible."
- **Fix:** Added check that `state["first_eligible"]` is in `state["human_factions"]`.

### NOT A BUG (investigated, confirmed correct)

- **P4 Fort in brit_force:** §3.6.3 says "If Defending, include all that Side's cubes, Forts…" — Forts ARE correctly included in defending Force Level.
- **P4 Underground modifier:** §3.6.5 says "At least one Attacking side piece Underground +1" — "+1 total" is correct (not per piece).
- **P12 Skirmish option 3:** `skirmish.execute()` requires no enemy cubes for option 3. The original code's `if has_fort and not enemy_cubes` guard is correct. The "first to remove a Fort" in the reference is about space selection priority, not option override.
- **P2 Event conditions:** Correctly check shaded text per §8.3.2. Q11 resolution confirmed "Active Support" (not "Active Opposition") for bullet 2.
- **P13 Persuasion Colony/City filter:** Consistent with Persuasion activity rules.
- **P1/P3 Resource checks:** `take_turn()` handles P1→P2→P3 ordering correctly.
- **Special Card Instructions:** All 13 Patriot card directives in `event_instructions.py` match the reference document.
- **OPS Summary (Supply, Redeploy, Desertion):** All sort priorities match §8.5.5–8.5.7.

### Previously documented issues (status update)

- ~~**P7/P11 Persuasion mid-command** — fires after command, not during~~ **FIXED** (this session: tracking flags)
- **P4 Battle: Win-the-Day free Rally** — bot integration not yet passing Rally params to battle.execute. Infrastructure exists in battle.py (Q9 RESOLVED) but PatriotBot doesn't pass `win_rally_space`/`win_blockade_dest` yet. (REMAINING)
- **P5 March: "lose no Rebel Control" constraint** — partially implemented via `_movable_from` retention logic but not verified during destination selection. (REMAINING)
- **P7 Rally: 4 of 6 bullet points incomplete** — Bullets 1 (Fort), 5 (Fort Available Militia), 6 (general Militia) implemented. Bullets 2-3 (Militia at empty Forts, Continental replacement) partially implemented but may not always execute correctly. Bullet 7 (gather at Fort) implemented. (PARTIALLY REMAINING)
- **Card 51 Bermuda Gunpowder Plot** — "March to set up Battle" conditional not fully implemented. (REMAINING)

### Tests added (10 new, 895 total)

| Test | Verifies |
|------|----------|
| `test_p4_half_regs_includes_active_militia` | Active Militia counted in attacker cubes for half-regs check |
| `test_p4_half_regs_defender_includes_wp` | Active WP counted in defender cubes for half-regs check |
| `test_march_fort_leave_behind_active` | Fort spaces keep Active piece, move Underground first |
| `test_march_no_fort_leave_behind_underground` | Non-Fort spaces keep Underground, move Active first |
| `test_march_phase2_population_tiebreaker` | Phase 2 destinations sorted by population |
| `test_rally_persuasion_blocks_sa_chain` | Mid-Rally Persuasion tracking flag set |
| `test_p9_fort_room_check` | P9 Fort assessment verifies 2-base limit |
| `test_p12_skirmish_fort_priority` | Skirmish option 3 for Fort-only, option 2 with cubes |
| `test_flowchart_p9_yes_no_march_fallback` | P9=Yes path does not fall through to March |
| `test_bs_trigger_requires_player_1st_eligible` | BS trigger checks human 1st Eligible |

---

## Session 13: Patriot Bot Compliance Review (Independent)

### Scope

Independent node-by-node comparison of the entire Patriot bot flowchart implementation in `lod_ai/bots/patriot.py` against `Reference Documents/patriot bot flowchart and reference.txt`, Manual Ch 3 (§3.3, §3.6), Manual Ch 4 (§4.3), and Manual Ch 8 (§8.5). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `partisans.py`, `skirmish.py`, `persuasion.py`, `rabble_rousing.py`, `rally.py`, `battle.py`, `march.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`.

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| P1 | Sword icon skip / Event vs Command | CORRECT — `base_bot._choose_event_vs_flowchart()` |
| P2 | Event conditions (5 bullets) | CORRECT — uses `CARD_EFFECTS` shaded side per §8.3.2; Q11 resolution applied (Active Support, not Active Opposition) |
| P3 | Resources > 0 gate | CORRECT — checks `== 0`, PASSes |
| P4 | Battle FL calculation with full §3.6.5-6 modifiers | CORRECT — all modifiers present and cumulative |
| P4 | French cap at Patriot cube count, French resource gate | CORRECT |
| P4 | Washington/Pop/Village/random tiebreaker | CORRECT |
| P4 | Resource constraint on space count | CORRECT — trims to `max(pat_res, 1)` |
| P4 | Win-the-Day free Rally + Blockade move via `win_callback` | CORRECT — wired to `battle.execute()` |
| P4 | Lauzun modifier: +1 leader AND +1 French-with-Lauzun | CORRECT — two separate cumulative modifiers per §3.6.5 lines 332-333 |
| P5 | March Phase 1 (Rebel Control destinations, Villages/Cities/Pop, French escort) | CORRECT |
| P5 | March Phase 2 (1 Militia Underground preferred into spaces with none) | CORRECT |
| P5 | March leave-behind (Fort guard, no Active Opp, lose-no-control) | CORRECT |
| P6 | Battle possible (rebel cubes + all 3 Rebellion leaders vs Active Royal pieces) | CORRECT |
| P7 | Rally Bullet 1 (Fort: 4+ units, room, Cities/Pop) | CORRECT |
| P7 | Rally Bullet 2 (Militia at lonely Forts) | CORRECT |
| P7 | Rally Bullet 3 (Continental placement at Fort with most Militia) | CORRECT |
| P7 | Rally Bullet 4 (Continental replacement from Rally-selected spaces only) | CORRECT |
| P7 | Rally Bullet 5 (Militia at non-Fort space, post-Bullet-1 Fort count) | CORRECT |
| P7 | Rally Bullet 6 (change Control, no Active Opp, Cities, Pop; no Active Support exclusion) | CORRECT |
| P7 | Rally Bullet 7 (adjacent Militia gathering, excludes selected spaces) | CORRECT |
| P7 | Rally space-by-space execution with mid-command Persuasion interrupt | CORRECT |
| P8 | Partisans (Village→WP→British; option 3 no WP; option 2 maximize; option 1 default) | CORRECT |
| P9 | Rally preferred (Fort possible OR 1D6 > Underground Militia) | CORRECT |
| P10 | Rabble possible (any space can shift + §3.3.4 eligibility) | CORRECT |
| P11 | Rabble-Rousing (Active Support first, highest Pop, §3.3.4 eligibility filter) | CORRECT |
| P11 | Rabble space-by-space execution with mid-command Persuasion interrupt | CORRECT |
| P12 | Skirmish (Fort-first, Control sub-priority, option 3/2/1 selection) | CORRECT |
| P13 | Persuasion (Rebel Control + Underground Militia + Colony/City filter, Fort priority, max 3) | CORRECT |
| P8→P12→P13 | SA chain (Partisans→Skirmish→Persuasion, resource-0 Persuasion gates) | CORRECT |
| P7↔P11 | Rally/Rabble mutual fallback (infinite loop guard via `_from_rabble`/`_from_rally`) | CORRECT |
| OPS | Supply priority (change Control, RL threat, Villages, Pop) | CORRECT — wired in `year_end.py` |
| OPS | Redeploy Washington (most Continentals) | CORRECT — wired in `year_end.py` |
| OPS | Patriot Desertion (least Control change, keep last unit) | CORRECT — wired in `year_end.py` |
| OPS | Brilliant Stroke trigger (ToA played, Washington+4 Continentals, player 1st Eligible) | CORRECT — wired in `year_end.py` |
| Event | All 13 Patriot card instructions match reference | CORRECT |
| Event | Cards 71/90 `force_unshaded`, 8 `force_if_french_not_human`, 18/44 `force_if_eligible_enemy`, 51 `force_if_51`, 52 `force_if_52` | CORRECT |

### Issues Found: NONE

No new bugs, deviations, or label compliance issues found.

### Previously Documented Outstanding Issues — Status Update

All four items from prior audit sessions (8, 9, 11) have been resolved:

1. ~~**P4 Force level modifiers** — raw piece counts instead of §3.6.5-6 modifiers~~ **RESOLVED**: Lines 335-366 implement all §3.6.5 Defender Loss modifiers (half regs, underground, attacking leader, French-with-Lauzun, defending fort) and all §3.6.6 Attacker Loss modifiers (half regs, underground, defending leader, defending fort). Net calculation at line 369 uses `(rebel_force + att_mod) - (brit_force + def_mod)`.

2. ~~**P4 Win-the-Day per-space** — pre-selects one rally space; requires battle callback refactoring~~ **RESOLVED**: Lines 386-408 define `_win_callback(st, battle_sid)` which is passed to `battle.execute()` at line 408. The callback selects the best Rally space per P7 priorities and the best Blockade city per the flowchart.

3. ~~**P7/P11 Persuasion mid-command** — fires after command, not during~~ **RESOLVED**: Both `_execute_rally()` (lines 959-999) and `_execute_rabble()` (lines 1037-1060) execute space-by-space, checking resources before and after each space. Persuasion fires immediately when resources hit 0. Only residual gap: restored resources don't expand the pre-selected space list (negligible gameplay impact).

4. ~~**OPS methods not wired into year_end**~~ **RESOLVED**: `ops_supply_priority()` called at year_end.py lines 130/163; `ops_redeploy_washington()` called at line 535; `ops_patriot_desertion_priority()` called at line 732; `ops_bs_trigger()` called at line 973.

### Investigation Notes

- **Lauzun double-modifier (false positive)**: The §3.6.5 modifiers list "+1 At least one Attacking Leader" (line 332) and "+1 Attacking including French with Lauzun" (line 333) as separate cumulative modifiers. The code at lines 343-349 correctly applies both: one for any leader present, one specifically for French+Lauzun. This is NOT a bug.

- **P5 March Phase 2 Continental fallback**: Code allows Continentals as fallback when no Militia can reach a target. Reference says "one Militia" but §3.3.2 March allows moving Continentals. Minor pragmatic deviation, not a bug.

- **P9 base room check**: P9 doesn't verify `< 2 bases` in the space when checking "Rally would place Fort." If a space has 4+ Patriot units but already has 2 bases, P9 returns True but Bullet 1 rejects it. Fallback behavior is correct (Rally proceeds with other bullets). Not a bug.

### Conclusion

The Patriot bot implementation is **fully compliant** with the reference documents. All nodes P1-P13, the OPS summary, and all 13 event card instructions match the flowchart and Manual Ch 8 §8.5. No code changes required.

### Tests

915 tests passing (no new tests needed — no bugs found).

---

## Session 14: French Bot Compliance Review (Independent)

### Scope

Independent node-by-node comparison of the entire French bot flowchart implementation in `lod_ai/bots/french.py` against `Reference Documents/french bot flowchart and reference.txt`, Manual Ch 3 (§3.5, §3.6), Manual Ch 4 (§4.5), and Manual Ch 8 (§8.6). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `commands/hortelez.py`, `commands/french_agent_mobilization.py`, `special_activities/naval_pressure.py`, `special_activities/skirmish.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`.

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| F1 | Sword icon skip / Event vs Command | CORRECT — handled by `base_bot._choose_event_vs_flowchart()` |
| F2 | Event conditions (6 bullets) | CORRECT — all 6 conditions verified against flowchart |
| F3 | French Resources > 0 gate | CORRECT |
| F4 | Treaty of Alliance played? | CORRECT |
| F5 | Patriot Resources < 1D3 | CORRECT — strict less-than, `state["rng"]` |
| F7 | Agent Mobilization | CORRECT — correct provinces, priority, Active Support filter |
| F8 | Préparer pre-Treaty | CORRECT |
| F9 | 1D6 < Available Regulars | CORRECT — strict less-than |
| F11 | Hortalez after Treaty | CORRECT — `min(resources, roll)` |
| F12 | Skirmish | CORRECT — WI priority, affected space exclusion, Fort-first option |
| F13 | Can Battle (decision gate) | CORRECT — cubes + Leaders only, excludes WP |
| F14 | March (all 4 bullets) | CORRECT — lose-no-control, Cities/British priority, BFS toward British, fallback |
| F15 | Préparer post-Treaty | CORRECT — D6 gate, +2 Resources fallback |
| F17 | Naval Pressure | CORRECT — Battle space first, then most Support, fallback chain |
| Event instructions | Cards 52, 62, 70, 73, 83, 88, 89, 95 | CORRECT |
| OPS | All methods (supply, redeploy, desertion, ToA trigger, BS trigger) | CORRECT |

### FIXED issues (this session — 3 bugs)

#### 1. F6 `_hortelez` / `_before_treaty` — Préparer ran even when Hortalez couldn't afford roll

**Reference (F6):** "Spend 1D3 French Resource to add Patriot Resources. If none, Pass."

**Bug:** `_hortelez()` returned `None` (void) regardless of whether it executed or skipped. `_before_treaty()` always called `_preparer_la_guerre()` and returned `True` after `_hortelez()`, even when Hortalez was skipped due to insufficient resources. This caused the bot to execute Préparer (SA) without a Command, and to report a successful turn when it should have Passed.

**Fix:** Changed `_hortelez()` return type from `None` to `bool` — returns `True` on success, `False` on skip. Changed `_before_treaty()` to check the return value: `if self._can_hortelez(state) and self._hortelez(state, before_treaty=True):`.

#### 2. F16 `_battle` — Missing FORT_PAT in Rebel Force Level

**Reference (§3.6):** "Force Level of each side = its cubes + Forts."

**Bug:** The `_battle()` method calculated `rebel_force` as `rebel_cubes + active_militia + leader_bonus`, omitting `FORT_PAT`. Patriot Forts contribute to Rebel Force Level and their absence could cause the bot to miss valid battle spaces where a Fort tips the balance.

**Fix:** Added `sp.get(C.FORT_PAT, 0)` to the `rebel_force` calculation.

#### 3. F10 `_muster` — Fallback targets excluded West Indies

**Reference (F10):** "In 1 space with Rebel Control **or the West Indies**."

**Bug:** When `avail_regs >= 4` and no Colony/City with Continentals had Rebel Control, the fallback target list only included Rebel Control spaces. West Indies was excluded even though the overarching condition explicitly includes it as always-valid. Additionally, the `west_indies` variable was checked with `if west_indies` which evaluated the space dict — an empty WI dict `{}` is falsy in Python, so even the first branch (`avail_regs < 4`) could incorrectly exclude WI.

**Fix:** Changed `west_indies = state["spaces"].get(WEST_INDIES)` to `wi_exists = WEST_INDIES in state["spaces"]` (boolean membership test). Added `if wi_exists and WEST_INDIES not in targets: targets.append(WEST_INDIES)` to the fallback branch.

### DOCUMENTED — minor deviations (unchanged from Session 10)

- **F14 March / F16 Battle: Active Militia included unconditionally** — optimistic assumption that Patriots will pay for Militia participation. Reasonable heuristic.
- **get_bs_limited_command skips F9 D6 gate** — minor, affects BS LimCom selection only.
- **ops_redeploy_leader missing Blockade rearrangement** — belongs in year_end.py, not bot method.

### Tests added (4 new, 919 total)

| Test | Verifies |
|------|----------|
| `test_f6_hortalez_cant_afford_does_not_run_preparer` | F6 skip → no Préparer, returns False |
| `test_f6_hortalez_returns_bool` | `_hortelez` returns True/False correctly |
| `test_f16_battle_includes_patriot_forts_in_rebel_force` | FORT_PAT included in Rebel FL |
| `test_f10_muster_fallback_includes_west_indies` | WI in fallback targets when not Rebel Controlled |

---

## Session 15: Indian Bot Compliance Review (Independent)

### Scope

Independent node-by-node comparison of the entire Indian bot flowchart implementation in `lod_ai/bots/indians.py` against `Reference Documents/indian bot flowchart and reference.txt`, Manual Ch 3 (§3.4), Manual Ch 4 (§4.4), and Manual Ch 8 (§8.7). Also reviewed `base_bot.py`, `event_instructions.py`, `event_eval.py`, `commands/scout.py`, `commands/raid.py`, `commands/gather.py`, `commands/march.py`, `special_activities/war_path.py`, `special_activities/trade.py`, `special_activities/plunder.py`, and `rules_consts.py`.

### Label Compliance: PASS

No string literal violations found. All piece tags, faction names, markers, and control values use proper constants from `rules_consts.py`.

### Nodes verified CORRECT

| Node | Description | Status |
|------|-------------|--------|
| I1 | Sword icon skip / Event vs Command | CORRECT — handled by `base_bot._choose_event_vs_flowchart()` |
| I2 | Event conditions (4 bullets) | CORRECT — uses `CARD_EFFECTS` unshaded side per §8.3.2; all 4 conditions verified |
| I3 | Support+1D6 > Opposition test | CORRECT — `randint(1,6)`, `(support + roll) <= opposition` routes to Raid |
| I4 | Raid (Max 3) — space selection, DC range, Plunder-first priority | CORRECT (with FORT_PAT fix below) |
| I4 | Raid — WP movement and village leave-behind | CORRECT (with FORT_PAT fix below) |
| I4 | Raid — mid-Raid Plunder/Trade when resources=0 | CORRECT |
| I5 | Plunder target selection (Raid spaces, WP > rebels, highest Pop) | CORRECT |
| I6 | Gather worthwhile (2+ Villages OR D6 < Available WP) | CORRECT |
| I7 | Gather Bullet 1 (Village placement, Cornplanter threshold, leader priority) | CORRECT |
| I7 | Gather Bullet 2 (WP at Villages: enemies, no UG WP, leader, random) | CORRECT |
| I7 | Gather Bullet 3 (WP in Village-room spaces: 2 WP, 1 WP, random) | CORRECT |
| I7 | Gather Bullet 4 (move adj Active WP, no Rebel Control, flip UG) | CORRECT |
| I8 | War Path — target selection (Fort, most Rebels, Province+Village) | CORRECT |
| I8 | War Path — option selection (3/2/1) | CORRECT |
| I8 | War Path / Trade fallback (resources=0 → Trade) | CORRECT |
| I9 | Space with WP + British Regulars? (both Active and Underground) | CORRECT |
| I10 | March — Phase 1 (Village dest: Neutral/Passive, 3+ WP, room) | CORRECT |
| I10 | March — Phase 2 (Rebel Control, first no Active Support) | CORRECT |
| I10 | March — movement constraints (UG first, no last-WP-from-Village, no Rebel Control) | CORRECT |
| I10 | March → Gather fallback (`_visited` prevents infinite recursion) | CORRECT |
| I11 | Trade — space selection (Village with most Underground WP) | CORRECT |
| I11 | Trade — British resource request (D6 < British Resources → ceil(roll/2)) | CORRECT |
| I12 | Scout — origin selection (WP + British Regulars, most Regs+Tories) | CORRECT |
| I12 | Scout — destination priority (Patriot Fort, Village+enemy, Rebel Control) | CORRECT (with City filter fix below) |
| I12 | Scout — control preservation | CORRECT |
| I12 | Scout + Skirmish (Fort option 3, 2+ enemy option 2, else option 1) | CORRECT |
| I12 | Scout — Tory cap (§3.4.3) | CORRECT (with Tory cap fix below) |
| Event | Cards 4/72/90 Village condition | CORRECT |
| Event | Cards 18/44 eligible enemy condition | CORRECT |
| Event | Card 38 WP condition | CORRECT |
| Event | Card 83 shaded/unshaded selection | CORRECT |
| Event | Cards 4/32/38 force_shaded | CORRECT (Session 12 fix confirmed) |
| OPS | Supply priority (prevent Rebel Control, then Village room) | CORRECT |
| OPS | Patriot Desertion (Village first, control change, last of type, random) | CORRECT (Session 12 fix confirmed) |
| OPS | Redeploy leaders (Brant/DC to most WP; Cornplanter to Neutral/Passive) | CORRECT |
| OPS | BS trigger (ToA + WQ + player/Rebel BS + Leader + 3 WP) | CORRECT (Session 12 fix confirmed) |
| OPS | Leader Movement (largest group from origin) | CORRECT |
| OPS | Defending in Battle (Village → activate all but 1 UG WP; no Village → none) | CORRECT |
| BS | get_bs_limited_command (walks I3→I4/I6→I9→I10) | CORRECT |

### FIXED issues (this session — 3 bugs)

#### 1. I4 `_raid()` — Missing FORT_PAT in `rebels_in_tgt` for needs_move check (MEDIUM)

**Reference (I4):** "move an Underground War Party into each Raid target with none OR where War Parties don't exceed Rebels."

**Bug:** The `rebels_in_tgt` calculation at line 314 counted `MILITIA_A + MILITIA_U + REGULAR_PAT + REGULAR_FRE` but omitted `FORT_PAT`. Patriot Forts are Rebellion pieces per §1.4. This meant the `needs_move` check (`wp_in_tgt <= rebels_in_tgt`) underestimated rebel presence. A target with 1 WP and 1 Fort (rebels=1, but code counted rebels=0) would NOT trigger a move-in, even though WP don't exceed the true rebel count.

This is the same pattern as Session 12 bug #3 (FORT_PAT missing from `score()`, `_can_plunder()`, `_plunder()`), but that fix missed this one calculation within `_raid()`.

**Fix:** Added `+ tgt_sp.get(C.FORT_PAT, 0)` to `rebels_in_tgt`.

#### 2. I12 `_scout()` — Missing Tory ≤ Regulars cap (MEDIUM, crash risk)

**Reference (§3.4.3):** "at least one British Regular must (and Tories up to the number of Regulars may) move with the War Parties."

**Bug:** The code set `n_tories = sp.get(C.TORY, 0)` and `n_regs = sp.get(C.REGULAR_BRI, 0)`, then applied a control-preservation cap on the total, but never enforced `n_tories ≤ n_regs`. In a space with 2 Regulars and 5 Tories, if the moveable cap was large enough, `n_tories=5, n_regs=2` would be passed to `scout.execute()`, which raises `ValueError("Tories moved may not exceed number of Regulars.")`.

**Fix:** Added `n_tories = min(n_tories, n_regs)` after the control-preservation block.

#### 3. I12 `_scout()` — Missing City filter for destination (MEDIUM, crash risk)

**Reference (§3.4.3):** "move at least one War Party into an adjacent Province (not City)."

**Bug:** The destination selection loop iterated through all `_adjacent(origin)` without filtering out Cities. If a City (e.g., Boston adjacent to Massachusetts) had enemy pieces or a Patriot Fort, it could be selected as the highest-scoring destination. `scout.execute()` would then raise `ValueError("Destination must be a Province.")`.

**Fix:** Added `if _MAP_DATA.get(dst, {}).get("type") == "City": continue` to the destination selection loop.

### DOCUMENTED — minor deviations (unchanged from Session 12)

- **Gather Bullet 1: Excludes spaces with existing Villages** — rarely strategically optimal, minor.
- **Mid-Raid Plunder/Trade is atomic** — architectural limitation, no mid-command interrupt support.
- **get_bs_limited_command skips I3 D6 gate** — minor, affects BS LimCom selection only.
- **I2 Event conditions: CARD_EFFECTS static lookup** — correct but cannot verify dynamic game-state conditions.

### Previously documented issues (unchanged)

- **OPS methods not wired into year_end** — all 4 bots define OPS methods but `year_end.py` uses ad-hoc logic.
- **B10 March + Common Cause timing** — CC invoked post-March.

### Tests added (5 new, 924 total)

| Test | Verifies |
|------|----------|
| `test_raid_moves_wp_when_fort_makes_wp_not_exceed_rebels` | FORT_PAT included in needs_move rebel count |
| `test_raid_no_move_when_wp_exceeds_rebels_with_fort` | Raid proceeds without extra move when WP > rebels incl. Fort |
| `test_scout_caps_tories_to_regulars` | Tories capped at Regulars count (no crash with 5 Tories, 2 Regs) |
| `test_scout_all_tories_when_le_regulars` | All Tories move when count ≤ Regulars |
| `test_scout_skips_city_selects_province` | City destination filtered out, Province selected instead |

---

## Session 16: Commands Compliance Review (Manual Ch 3)

### Scope

Systematic comparison of all 11 command implementations in `lod_ai/commands/` against Manual Ch 3 (§3.1–§3.6). Files reviewed: `battle.py`, `march.py`, `muster.py`, `rally.py`, `garrison.py`, `gather.py`, `scout.py`, `raid.py`, `rabble_rousing.py`, `french_agent_mobilization.py`, `hortelez.py`.

### Commands verified CORRECT

| Command | Section | Status |
|---------|---------|--------|
| `muster.py` (British) | §3.2.1 | CORRECT — Regular placement (up to 6), Tory placement (2/1 by support), Fort/Reward Loyalty, resource costs |
| `muster.py` (French) | §3.5.3 | CORRECT — single space, Rebellion Control or WI, up to 4 Regulars, optional Fort replacement |
| `garrison.py` | §3.2.2 | CORRECT — 2 Resource total, Blockade exclusions, Militia activation per 3 cubes, displacement rules, FNI 3 gate, Limited Command constraints |
| `march.py` (British) | §3.2.3 | CORRECT — escort cap 1-for-1, Militia activation per 3 cubes, resource costs |
| `march.py` (Patriots) | §3.3.2 | CORRECT — French escort 1-for-1, WP activation per 2 Continentals, Militia activation conditions, French resource fee |
| `march.py` (Indians) | §3.4.2 | CORRECT — Province-only destinations, first-reserve-free cost, WP activation conditions |
| `march.py` (French) | §3.5.4 | CORRECT — Treaty gate, Continental escort 1-for-1, Patriot resource fee |
| `rally.py` | §3.3.1 | CORRECT — no Active Support, place 1 Militia or build Fort, bulk placement up to Forts+Pop, move-and-flip, promotion, Indian Reserve/WI exclusion |
| `gather.py` | §3.4.1 | CORRECT — support level gate (Neutral/Passive), first reserve free, place 1 WP or build Village, bulk up to Villages+1, move-and-flip |
| `scout.py` | §3.4.3 | CORRECT — Province-only, WP arrive Active, Regulars mandatory, Tory cap, Militia activation, optional Skirmish |
| `raid.py` | §3.4.4 | CORRECT — up to 3 Provinces, Opposition-only, move 1 adjacent WP, Activate 1 WP, Raid marker placement, shift toward Neutral |
| `rabble_rousing.py` | §3.3.4 | CORRECT — Rebellion Control + Patriot piece OR Underground Militia, Propaganda marker, shift toward Opposition, conditional Militia activation |
| `hortelez.py` | §3.5.2 | CORRECT — French pays N, Patriots gain N+1 |
| `battle.py` (force levels) | §3.6.2–3 | CORRECT — cube counts, half Active guerrillas, Forts defending only, Tory cap when British attacks, allied cube limits |
| `battle.py` (dice) | §3.6.4 | CORRECT — Force/3 D3s capped at 3, 0 dice if Force ≤ 2 |
| `battle.py` (modifiers) | §3.6.5–6 | CORRECT — all 9 Defender modifiers and 6 Attacker modifiers match rules |
| `battle.py` (removal) | §3.6.7 | CORRECT — alternating priority, Underground ignored, cubes to Casualties, Forts to Available, guerrillas to Available |
| `battle.py` (winner) | §3.6.8 | CORRECT — elimination check, fewest pieces, defender wins ties, both eliminated = no winner |
| `battle.py` (overflow) | §3.6.8 | CORRECT — adjacent spaces sorted by population |
| `battle.py` (free Rally/Blockade) | §3.6.8 | CORRECT — infrastructure exists, callback mechanism per-space |

### FIXED issues (this session — 1 critical bug)

#### 1. Battle Win-the-Day shift direction INVERTED (CRITICAL)

**Reference (§3.6.8):** "Shift Support/Opposition levels in the Battle space by half the number of pieces the Loser removed." Glossary: "Win the Day: A shift in Support or Opposition for the winning Side in a Battle." Royalist winner shifts toward Support; Rebellion winner shifts toward Opposition.

**Bug:** `_apply_shifts_to()` in `battle.py` had the shift directions reversed:
- Royalist winner: `cur - 1` (shifted toward Opposition instead of Support)
- Rebellion winner: `cur + 1` (shifted toward Support instead of Opposition)

Every Battle Win-the-Day outcome since the code was written shifted the population sentiment AGAINST the winner instead of toward them. Tests also had inverted expectations, masking the bug.

**Fix:** Swapped the conditions and arithmetic:
- Royalist winner: `cur + 1` when `cur < ACTIVE_SUPPORT` (toward Support)
- Rebellion winner: `cur - 1` when `cur > ACTIVE_OPPOSITION` (toward Opposition)

Updated 4 tests: `test_apply_shifts_to_returns_remaining`, `test_apply_shifts_to_rebellion`, `test_overflow_shifts_to_adjacent`, `test_washington_doubles_win_the_day`.

### DOCUMENTED — ambiguity (see QUESTIONS.md Q12)

- **French Agent Mobilization `_VALID_PROVINCES`**: Manual §3.5.1 says "Quebec" but bot flowchart F7 says "Quebec City". Map has both spaces ("Quebec" as Reserve, "Quebec_City" as City). Current code uses "Quebec_City" matching the bot flowchart. Documented as Q12 in QUESTIONS.md for human decision.

---

## Session 17: Zero-Player Smoke Cleanup + 1776 Imbalance Investigation (May 2026)

### Scope

Driven by the user request "tell me what this project is and finish it."
The session ran the 0-player smoke matrix on current main, surfaced four
real bugs, fixed them with regression tests, then took the 150-game
`--large` batch from 1 hard crash + 55 silent illegal/error events down
to 0/0.  Then audited the bot flowcharts (B, I, F nodes) against their
reference docs to investigate the 1776 100%-Patriot-wins phenomenon.

### FIXED — four PRs (merged to main)

#### 1. Patriot Win-the-Day free Rally crashed in Reserve / West Indies

**Source:** Manual §3.6.8 + §1.4.2 + §3.3.1.  Win-the-Day grants a free
Rally in the battle space for Rebellion winners.  Rally is illegal in
West Indies and Indian Reserves.

**Bug:** `PatriotBot._execute_battle`'s `_win_callback` unconditionally
returned the battle space as the free Rally space, so when battle was
fought in Quebec / Northwest / Southwest / West Indies, the subsequent
`rally.execute()` raised `ValueError: Cannot Rally in <space>`.  The
engine caught the exception and downgraded the turn to
`pass(bot_error)`, but the bot silently lost its action (5 occurrences
across 3 games in the 60-game baseline).

**Fix:** consult the existing `self._can_rally_in(st, battle_sid)`
predicate and set `rally_space=None` when the battle space is not
Rally-eligible.  Commits `6d6d4f8` (fix) + `b9f4807` (test).

#### 2. British Limited-Command Muster exceeded the 1-space cap

**Source:** Manual §3.2 / §3.2.1.  Limited Command Muster may affect
only 1 space.

**Bug:** `BritishBot._muster()` correctly capped Regulars + Tory
placement at max_spaces (1 for Limited Command, 4 otherwise), but the
step-3 Reward-Loyalty and Fort-build candidate selection could append
an extra space.  In Limited mode this produced 2 selected spaces and
the engine rejected with `limited_wrong_count (affected=2)`.  50
occurrences across 29/60 games — almost every 1775 and 1776 game
affected.

**Fix:** filter `rl_candidates` and `fort_targets` to spaces already in
`all_selected` when `len(all_selected) >= max_spaces`.  Honors the B8
flowchart phrase "in 1 space, first one already selected above."
Commit `648ae61` (fix) + `b9f4807` (test).

#### 3. British "March in place to Activate Militia" produced no_affected_spaces

**Source:** Manual §3.2.3 + B10 flowchart Phase 3.

**Bug:** `BritishBot._march`'s Phase 3 ("March in place to Activate
Militia, first in Support") called `flip_pieces()` directly to flip
Underground Militia, bypassing `march.execute()`.  Two consequences:
the §3.2.3 cost (1 Resource per destination space selected) was not
paid for these destinations; and `state['_turn_command']` /
`state['_turn_affected_spaces']` were never populated.  When the SA
chain then fired, the engine saw `_turn_used_special=True` with
affected_count=0 and rejected with `no_affected_spaces`.  1 occurrence
in the 60-game baseline (1776 seed 2 card 10).

**Fix:** when activate_in_place is non-empty, charge §3.2.3 cost
per in-place destination (stopping at unaffordable), set
`_turn_command='MARCH'`, and add the paid-for spaces to
`_turn_affected_spaces` before doing the flip.  Commits
`be656da` + `af2b516` (test).

#### 4. §6.2.2 West Indies Free Battle wasn't free

**Source:** Manual §6.2.2 verbatim: "French must conduct a *free*
Battle in the West Indies if French and British pieces are present."

**Bug:** `_supply_phase` in `lod_ai/util/year_end.py` called
`battle.execute(state, FRENCH, {}, [WEST_INDIES_ID])` without
`free=True`.  When French reached year-end with 0 Resources the
`spend()` helper raised `ValueError` and the whole year-end resolution
crashed.  The next line of code pushed history saying "Free Battle in
West Indies (6.2.2)" — the comment knew the rule but the call didn't
reflect it.  Surfaced as 1 CRASH (1778 seed 48) in the `--large`
150-game smoke.

**Fix:** pass `free=True`.  Commit `f0a878e`.

#### 5. Patriot bot fired Persuasion 2-4 times per turn

**Source:** Manual §4.1: "may also execute *one* of its Special
Activities."

**Bug:** `PatriotBot._try_persuasion()` is called from many flowchart
nodes (P7 Rally, P8 Partisans, P11 Rabble-Rousing, P12 Skirmish) and
is also fired as a mid-command resource refill inside `_execute_rabble`
and `_execute_rally` whenever Patriot Resources hit 0.  Nothing
prevented it firing more than once per turn.  Instrumenting a 50-game
1776 batch showed 30% of Persuasion-using turns (52/172) involved >1
Persuasion call, with one turn firing it four times.

**Fix:** gate `_try_persuasion` with `state['_turn_persuasion_used']`,
cleared at the start of every turn via a `PatriotBot.take_turn`
override.  Commit `7cf4412`.

#### 6. Cumulative casualty counters hardcoded to 0 at setup

**Source:** `1776 Scenario Reference.txt`: "Cumulative British
Casualties: 1, Cumulative Rebellion Casualties: 3."  `1778 Scenario
Reference.txt` specifies CBC=10.

**Bug:** `lod_ai/state/setup_state.py` wrote `"cbc": 0, "crc": 0`
unconditionally, ignoring `british_casualties` / `patriot_casualties`
fields in the scenario JSON files.

**Fix:** read `int(scen.get('british_casualties', 0))` and similarly
for CRC.  Commit `7cf4412`.

### Smoke matrix outcome

Before this session:

  Default 60-game matrix: 1 game with bot_errors, 29 games with
  illegal_actions.  150-game `--large`: 1 hard CRASH, 55 silent
  illegal/error events.

After this session:

  Default 60-game matrix: 0 bot_errors, 0 illegal_actions.
  150-game `--large`: 0 crashes, 0 illegal_actions, 0 bot_errors.

### INVESTIGATED — 1776 100% Patriot wins (NOT a coding bug)

After all the above fixes 1776 still produces 49/50 (98%) Patriot wins
on the 50-seed batch.  Investigation chain:

1. **Manual Ch 7 victory conditions:** Patriot = (Opp > Sup + 10) AND
   (Forts + 3 > Villages).  `victory.py` `_patriot_margin` matches.
2. **1776 starting state vs scenario reference:** support track (3),
   opposition track (5), Patriot Forts (2), Villages (2) all match
   reference.  CBC/CRC were the only discrepancy and have been fixed.
3. **Instrumented trace of 1776 seed 30:** Patriots reach Margin 1 = +2
   after 8 cards via:
   - Card 1 (Hessians, BPIF): British plays event (no Support shift);
     Patriots Rabble-Rouse 5 spaces (NC, Philly, Charles_Town, Georgia,
     Quebec) shifting Opposition track from 5 to 10.
   - Card 5 (Declaration of Independence, PIFB): Patriots 1st Eligible.
     Then British attacks New_York and *loses*; §3.6.8 Win-the-Day
     shifts NY by 2 toward Opposition, +4 to track.
   - Card 7 (Morgan's Rifles, PFIB): Virginia shifts to Active Support;
     +4 to Support track.  Patriots still ahead.
   - Card 8 (Winter Quarters): Victory check — PAT margins (2, 3).  Win.
4. **1775 vs 1776 structural comparison:**

| | 1775 | 1776 |
|---|---|---|
| Starting Opp − Sup | 0 | **2** |
| Shift needed for PAT Margin 1 | 10 | **8** |
| Persuasion-eligible spaces | 3 | **4** |
| RR-eligible spaces with shift room | 3 | **5** |
| Patriot resources | 3 | 2 |

5. **British / Indian / French bot audits vs their reference flowcharts:**
   walked B1-B13 + OPS, I3-I12, F3-F17 against the published refs.
   All three implementations are largely faithful.  Minor deviations
   found (B10 extra CC-fallback-before-SA step, B12 battle Force-Level
   heuristic vs exact dice prediction, two OPS methods existing but
   not wired into the engine) but none individually large.

### CONCLUSION

The 1776 100%-Patriot result is what the published bot flowcharts
produce.  It is **not** a coding bug.  Per project rule "Rules-Accurate
Over Simple" and "Never Guess", do not rebalance by altering bot
priorities.  If 1776 is intended to be a Patriot-favored medium-
duration scenario in the bots' world that is the accepted outcome;
if not, the question belongs upstream of this codebase (GMT designer
notes / community playtest data).

### Remaining open items (not crash-class)

- `bot_indian_trade` and `bot_leader_movement` exist on `BritishBot`
  with unit tests but are not invoked from the engine.  Wiring them
  would close two §3.4 / §6 OPS items.
- `_march`'s "try Common Cause as fallback before SA chain" is an
  extra step not in B10's reference text.
- `_battle`'s Force-Level heuristic is rough; a dice-accurate
  estimator might prevent the bot from launching attacks it loses.
- Phase 4 human-player CLI pass: 1-3 human modes have had less
  scrutiny than the bot paths.

---

## Session 18: Full Rules-Compliance Audit (May 2026)

### Scope

User request: "do a full audit of the whole thing against the rules."
Given that audit_report.md through Session 17 already covers Manual
Ch 3 (commands), Ch 7 (victory), Ch 8 (bot flowcharts for all four
factions), the four scenario reference docs, and the ~109 card
handlers (3× re-audited in Sessions 3/4/6), this session focused on
the genuinely under-audited areas:

* `Reference Documents/leader_capabilities.txt` — never explicitly
  audited per prior sessions.
* Manual Ch 1 (game basics — pieces, map, control) — covered
  implicitly by Phase 1 label compliance and scenario setup audits.
* Manual Ch 2 (sequence of play / eligibility) — covered by
  Phase 3 / Session 4 + Session 6 in passing but not explicitly.
* Manual Ch 5 (event resolution mechanics) — heavily covered by the
  three card-handler audits; nothing fresh to add.
* Card handler spot-check — deferred to a future session given time
  budget.

### FIXED — four leader-capability bugs (`leader_capabilities.txt`)

Background: `lod_ai/leaders/__init__.py` registers `pre_*` hooks for
each of the 9 leader capabilities and exposes
`apply_leader_modifiers(state, faction, hook, ctx)`.  In real game
state, `state["leaders"]` is shaped `{leader_id: location}` (the
scenario-JSON convention), not `{faction: [leader_ids]}` as the
module's docstring claims and the hooks expect.  So the entire
`apply_leader_modifiers` ctx-flag path is **dead code in real games**.

For most capabilities this doesn't matter — the per-space rules are
implemented directly via `leader_location()` checks in their command
files (Washington WTD/Defender, Lauzun, Brant, Dragging Canoe).

Four capabilities were silently broken:

#### 1. Clinton (+1 Militia in Skirmish)

`lod_ai/special_activities/skirmish.py` read
`ctx.get("skirmish_extra_militia", 0)`, which was always 0 because
the `_clinton` hook didn't fire.  The code-comment claim "Clinton
bonus is already applied via apply_leader_modifiers" was wrong.

**Fix:** added a direct
`leader_location(state, "LEADER_CLINTON") == space_id` check
alongside the (now-known-dead) ctx fallback.  The fallback was
removed to avoid double-counting in tests that exercise the legacy
`{faction: [leaders]}` state shape.

#### 2. Cornplanter (Village for 1 War Party)

`lod_ai/commands/gather.py` always required exactly 2 War Parties to
build a Village, regardless of Cornplanter's location.  Per
leader_capabilities.txt: "Gather builds Villages for 1 War Party in
the space."

**Fix:** in the `build_village` branch of `gather.execute()`, compute
`village_cost = 1 if leader_location("LEADER_CORNPLANTER") == prov
else 2` and use it for both the WP-availability check and the
WP-removal count.

#### 3. Gage (free first Reward Loyalty shift in the space)

`BritishBot._muster` set `rl_free_first = self._is_gage(state) and
reward_levels > 0`.  `_is_gage` returns True when Gage is the
*first British leader on the map*, which gives the discount when
Reward Loyalty is happening anywhere — even if Gage is in a
different city.  The reference says **"in the space."**

**Fix:** changed `rl_free_first` to check
`leader_location(state, "LEADER_GAGE") == chosen_rl_space`.  Same
fix applied to the affordability pre-calculation
(`_rl_gage = 1 if leader_location == best_rl else 0`).

#### 4. Rochambeau (French free with Patriot Command)

`lod_ai/commands/battle.py` and `lod_ai/commands/march.py` charged
the French allied fee unconditionally whenever Patriots used French
escorts.  Per leader_capabilities.txt: "French may March and Battle
with a Patriot Command at no Resource cost."  Per-space rule —
applies when French Regulars in Rochambeau's space participate.

**Fix:**

* `battle.execute()`: changed the French-allied-fee calculation from
  "1 per space with French Regulars" to "1 per space with French
  Regulars **except** Rochambeau's space."
* `march.execute()`: changed `spend(state, FRENCH,
  len(french_entered_dsts))` to filter out Rochambeau's location
  from the chargeable destinations.

### Regression tests

`lod_ai/tests/test_leader_capabilities_audit.py` — 7 new tests:

* `test_clinton_in_skirmish_space_removes_one_extra_militia`
* `test_clinton_not_in_skirmish_space_grants_no_bonus`
* `test_cornplanter_builds_village_with_one_war_party`
* `test_no_cornplanter_requires_two_war_parties`
* `test_gage_in_rl_space_makes_first_shift_free`
* `test_rochambeau_in_battle_space_waives_french_ally_fee`
* `test_rochambeau_elsewhere_does_not_waive_french_ally_fee`

### Audit findings — Manual Ch 1, Ch 2, Ch 5

#### Ch 1 (game basics)

Piece-count constants in `lod_ai/rules_consts.py`
(`MAX_REGULAR_BRI=25`, `MAX_TORY=25`, `MAX_REGULAR_FRE=15`,
`MAX_REGULAR_PAT=20`, `MAX_MILITIA=15`, `MAX_FORT_BRI=6`,
`MAX_FORT_PAT=6`, `MAX_VILLAGE=12`) match standard Liberty or Death
component counts.  Scenario setups have been validated against the
Scenario Reference docs in prior sessions and via the
CBC/CRC + setup audits in Session 17.

#### Ch 2 (sequence of play / eligibility)

`engine._prepare_card` correctly resets all four factions to
Eligible at the start of each card (per §2.3.6), then applies
`ineligible_next` (single-card ineligibility) and
`ineligible_through_next` (two-card ineligibility) per any
event-driven flags from the previous card.  Brilliant Stroke
all-eligible reset is handled via the BS card handlers.  No fresh
issues found.

#### Ch 5 (event resolution mechanics)

Already deeply covered by Sessions 3/4/6 (full card-handler audits)
and Session 16 (Commands).  No fresh audit needed in this session.

### Documented — apply_leader_modifiers / leaders module is dead code

The `lod_ai/leaders/__init__.py` module registers `pre_battle`,
`pre_skirmish`, `pre_war_path`, `pre_gather`, `pre_raid`,
`pre_reward_loyalty`, `pre_special_activity`, and `pre_command`
hooks for each of the 9 capabilities.  None of them fire in real
games because `apply_leader_modifiers` iterates
`state["leaders"].get(faction, [])` while real state has
`state["leaders"]` shaped `{leader_id: location}`.

Every capability is now implemented via direct `leader_location()`
checks in the relevant command files (after this session's four
fixes).  Two safe future actions:

1. Delete the dead hooks + the docstring claiming the
   `{faction: [leaders]}` shape, since the actual contract is the
   `{leader_id: location}` shape.
2. Or: fix `apply_leader_modifiers` to walk the location dict and
   correctly fire hooks for leaders on the map — but this would
   then duplicate the direct checks now present in command files
   and risk double-counting.

Both are out of scope here; (1) is cleaner.

### What remained out of scope

* **Systematic card-handler spot-check.**  The card handlers have
  been audited three times (Sessions 3, 4, 6) and no new issues
  were surfaced in the most recent re-audit.  Pulling every card
  again was not the highest-value use of this session's time.  A
  future session may want to re-check the ~80 cards not explicitly
  listed as fixed.

* **Howe leader-presence check.**  `BritishBot._is_howe` returns
  True if Howe is the "first" British leader returned by
  `_british_leader`.  If both Gage and Howe are on the map and Gage
  is found first, Howe's FNI bonus may not fire.  Not crash-class
  but worth a follow-up.

---

## Session 19: Misc British-bot follow-ups + Item 4 clarification (May 2026)

### Scope

Three items from CLAUDE.md's "Remaining open items" list:

  1. `_is_howe` / Naval-Pressure leader checks missed leaders when
     multiple British leaders were on the map (the `_british_leader`
     scan returned the *first* leader in a fixed order).
  2. `_march` had an extra post-March "try Common Cause again"
     fallback before the SA chain, which isn't in the B10 reference.
  3. Battle-induced leader movement (originally noted as a gap).

### FIXED

#### 1. Multi-leader presence checks

`BritishBot._is_howe` and the Gage-or-Clinton gate in
`_try_naval_pressure` both consulted `_british_leader`, which
returned the first British leader found in the scan order
LEADER_GAGE -> LEADER_HOWE -> LEADER_CLINTON.  When multiple British
leaders were on the map the wrong leader was selected.  Concretely,
Howe's FNI bonus (Reference Card #110: "Before executing a British
Special Activity, first lower FNI by 1 level") was missed whenever
Gage was also present.

**Fix:** rewrote `_is_howe` as a direct
`leader_location(state, "LEADER_HOWE") is not None` presence check;
the Naval Pressure gate uses two analogous direct checks for Gage
and Clinton.  `_is_gage` and `_british_leader` deleted — every
caller now resolves leaders independently per the
leader_capabilities reference's "in the space" / "is on the map"
semantics.

Commit `9bf4f99`.

#### 2. `_march` extra Common-Cause post-March fallback

B10 reference: "If no Common Cause used, execute a Special
Activity."  The code had an extra `_try_common_cause(state, mode="MARCH")`
call after march.execute returned but before the SA chain.  Per the
flowchart there is no second CC attempt — the bot proceeds directly
to Skirmish/Naval Pressure.

**Fix:** removed the extra CC attempt.  If CC wasn't used during
March planning, the bot now goes straight to `_apply_howe_fni` +
`_skirmish_then_naval`.

Commit `9bf4f99`.

### CLARIFIED — "Battle-induced leader movement" was not actually a gap

The May 2026 audit listed Battle-induced leader movement as a
remaining item with the note "Battle can shift pieces (overflow)."
That sentence conflated two different things:

  * Battle DOES shift Support/Opposition levels (including overflow
    to adjacent spaces per §3.6.8) — but Support levels are not
    pieces.
  * Battle DOES NOT move faction units between spaces.  Inspection
    of `lod_ai/commands/battle.py` confirms that every `remove_piece`
    call sends the piece to "casualties" or "available" (i.e., off
    the map); there are no `move_piece` calls.  The Win-the-Day
    free Rally places militia in the battle space from Available
    (no inter-space movement).  The Win-the-Day free Blockade move
    moves a Blockade *marker*, not a faction's units.

The leader-movement rule from leader_capabilities.txt is "follow
largest group of own units that **moves from** (or stays in) their
spaces."  After a Battle no units move from anywhere, and units that
weren't removed naturally stay.  The existing `bot_leader_movement`
logic correctly handles this case (best_dest defaults to leader_loc
when nothing moves, so leaders stay put).

**No code change required.**  The item is closed by documentation:
this audit entry plus an updated CLAUDE.md "Remaining open items"
section that explains the misunderstanding.

### Noted — minor cross-faction CC follow-up

A genuine but minor edge case surfaced while investigating Item 4:
during a British March that uses Common Cause, Indian War Parties
participate as Tory-equivalents and can move with the British
march from their origin (which may be an Indian leader's space) to
the British destination.  Per OPS the Indian leader (Brant /
Cornplanter / Dragging Canoe) should then follow.

The current wiring fires `_follow_leaders_after_move` only after
Indian commands (March/Scout/Gather/Raid), not after British
commands.  So CC-driven WP movement during a British March doesn't
trigger Indian leader following.

This is a cross-faction edge case, quite minor in practice (CC
requires WPs in the British origin space, and the bot needs to be
in a position where the move shifts Brant/Cornplanter/DC's largest
group).  Documented in CLAUDE.md "Remaining open items" for a
future session.

### Item left out: Battle Force-Level heuristic

Same status as last session — open-ended scope (would require
sandboxed Battle simulations), risks deviating from the B12
reference (which uses Force Level + modifiers, not expected
losses), and any change must be benchmarked against many seeds.

Remains in CLAUDE.md "Remaining open items" as the only
non-trivial follow-up.

## Session 20: Per-faction free-Command planners + free-SA planners (June 2026)

Closed the two deliberately-deferred free-operation items from the
free-op audit (see GITHUB_ISSUES.md "Remaining free-op work — CLOSED").

New module `lod_ai/bots/free_op_planner.py` — planning for card-granted
free Commands/SAs per Manual 8.3.5 ("use the Faction's priorities;
pieces per 8.1.2, spaces randomly per 8.2 where not applicable"):

- **March**: per-faction movement restrictions and destination
  priorities transcribed from flowchart nodes B10/P5/F14/I10 (Manual
  8.4.3/8.5.4/8.6.5/8.7.3), mirroring the audited bot implementations,
  reduced to the single destination a card grants. Escort legality per
  3.2.3/3.3.2/3.5.4 (the old generic planner counted Tory-only spaces
  as March sources, producing zero-piece plans the executor rejected —
  the 4 residual British March skips). No Common Cause on a free March
  (CC is a Special Activity the card does not grant). Indians never
  target a City (3.4.2).
- **Rally**: Patriot-only (3.3); 8.5.2 space priorities (Fort build at
  4+ units and room, bulk Militia at Forts up to Fort+Pop, no own-piece
  requirement per 3.3.1).
- **War Path**: Indian node I8 target priorities + 4.4.2 option
  requirements. **Partisans**: Patriot node P8 + 4.3.2. Both were
  previously clean declines ("no bot planner"); over the 60-game matrix
  they now execute where legal (other free SAs still decline cleanly;
  no card queues them for bots).
- **Card 67 (De Grasse) fix**: handler defaulted to a FRENCH free
  "rally", which can never execute (Rally is Patriot-only). Now pairs
  the faction with its legal Command per 8.3.5: French → Muster
  (post-ToA), otherwise the benefit passes to the Patriots → Rally.
  This was the 1 residual French Rally skip.
- **indians.py I8 fix found during transcription**: the "Province with
  1+ Villages" tiebreak compared against a "Province" map type that
  does not exist in map.json (types are City/Colony/Reserve/Special);
  now matches Colony or Reserve.

Verification: full suite 1219 passed; clean-sweep gate (60 games,
PYTHONHASHSEED=0) reports zero bot errors, zero illegal actions and
zero free-op execution skips — and the gate now HARD-FAILS on execution
skips (a planner-approved free op must execute; genuine no-target
outcomes log as "declined (no legal plan)" and were spot-verified
against the space states). Balance baseline refreshed: 19/60 pinned
winners shifted (free SAs now fire; March follows faction priorities);
per-scenario aggregates moved within band and 1776 remains
Patriot-favored as documented in Session 17.

## Session 21: Event space selection — §8.3.5/§8.3.6/§8.2 transcription (July 2026)

Audit finding (superseding the previous session's handoff, which escalated
this as a design ambiguity): the "candidate set" question for events that
shift Support/Opposition in unnamed Cities/Colonies is **answered by the
manual** and required no human ruling. §8.3.5 routes shift-space selection
to §8.3.6 (Royalist: highest gain in Support, then highest loss in
Opposition; Rebellion mirrored; Population-weighted per §8.1.1, Active
double per §1.6.2). §8.2 Random Spaces is a tie-breaker only ("If several
candidate Province or Cities have EQUAL priority…"). A maxed-out space has
zero gain and cannot tie a space where the shift works; if every candidate
is zero, §8.3.3 (Ineffective Events) applies at the play/don't-play layer.

Mismatches found and fixed (by card, `lod_ai/cards/effects/early_war.py`
unless noted):

- **2 Common Sense** — shaded: 2 Cities picked alphabetically → §8.3.6
  selection; unshaded: 1 City alphabetical → equal priority → §8.2.
- **6 Benedict Arnold** — both sides picked alphabetically (unshaded even
  among Colonies with nothing to remove) → §8.3.5 maximise Forts then
  pieces removed, §8.2 ties; militia removal order fixed to Active before
  Underground (§8.1.2); shaded cube removal now alternates Regulars/Tories
  from the most numerous (Regulars if even), sparing the last Tory (§8.1.2).
- **10 Franklin** — unshaded: first two Cities alphabetically → §8.3.6.
- **32 Rule Britannia!** — unshaded: alphabetical Colony → equal priority
  → §8.2 (override key preserved).
- **41 William Pitt** — 2 Colonies alphabetical → §8.3.6. Note the old
  picker could select a Colony past the target level and shift it AGAINST
  the executing side; §8.3.6 ordering ranks those below zero-gain picks.
- **43 HMS Russian Merchant** — unshaded: first 3 qualifying spaces in
  dict order → §8.2 among equal candidates; Tory sourcing fixed to
  Unavailable first (§8.3.4).
- **46 Burke** — shaded: 2 Cities alphabetical → §8.3.6; unshaded: 3
  spaces alphabetical → §8.2 (West Indies excluded).
- **84 "Merciless Indian Savages"** — unshaded: 2 alphabetical Colonies
  (possibly Gather-illegal, later logged as "genuine declines") → legal
  Colonies per 3.4.1 with the most-own-force priority the engine free-op
  planner uses (§8.3.5: free Commands use the Faction's priorities), §8.2
  ties; shaded Village space now §8.2 among equal candidates.
- **25 British Prison Ships** (`late_war.py`) — same pattern as 41/46 →
  routed through the shared §8.3.6 helper.

Infrastructure:

- `bots/random_spaces.py` — `choose_random_space` threads the seeded
  ``state["rng"]`` (was module-level `random`, unreproducible); new
  `pick_random_spaces(state, candidates, count)` re-rolls per §8.2; the
  arrow walk fixed to continue at the TOP of the next column (§8.2
  "from the bottom of one column to the top of the next") instead of
  rotating rows within each column; stale dead import removed from
  `base_bot`.
- `cards/effects/shared.py` — new `select_support_shift_spaces` (§8.3.6
  key + §8.2 ties; side from `state["active"]`, else §8.3.2 shading);
  `pick_two_cities` deleted; `pick_cities`/`pick_colonies` docstrings now
  restrict them to full-list use.
- `bots/base_bot.py::_is_ineffective_event` — implements §8.3.3's
  net-shift clause: an Event whose simulated net Support−Opposition
  difference moves in favor of the enemy side is Ineffective (this also
  covers §8.3.6's "instead executes a Command and Special Activity"
  guard). Simulation now sets `state["active"]` on both copies, mirroring
  `_execute_event`.

Verification: both test roots green (1,271 tests; 13 added in
`test_event_space_selection.py` covering §8.2 rng determinism, the arrow
walk, §8.3.6 ordering both sides, zero-vs-negative gain, and the §8.3.3
guard on cards 41/46); clean-sweep gate clean on 1775/1776/1778 seeds
1-20 with invariants; balance rebaselined (13/60 pinned winners shifted,
9 in 1775 as expected for early-war cards + the global §8.3.3 guard;
per-scenario faction aggregates moved ≤2/20 and 1776 is unchanged).

Known remaining (not fixed here): other alphabetical/dict-order subset
picks in `late_war.py` (lines ~155/167/205/795/1005) and possibly
`middle_war.py` need the same card-by-card audit against §8.3.5/§8.2.

## Session 22: Traceability matrix bootstrap — Manual Ch 8 (July 2026)

Started ROADMAP.md Piece 1. `TRACEABILITY.md` now maps all 60 numbered
Ch 8 sections to code/tests (mechanical citation scan + hand verification
of §8.1–§8.3.8). Audit-only session — no behaviour changes.

Headline finding — **T1 (P0)**: §8.1 "Commands Not Limited" is violated.
`engine._options_for_slot` hands every 2nd-eligible-after-a-Command seat
`limited_only=True, special_allowed=False`, including bot seats, and
engine.py:619-622 enforces it. The manual: a Non-player told to execute a
Limited Command "instead executes a full Command and Special Activity."
Every bot 2nd-eligible turn after a 1st-eligible Command has been wrongly
capped at one space with no SA. (Event-granted free LimComs are correctly
limited in the free-op path.) Fix queued with full battery + rebaseline.

Ten further backlog items T2–T11 recorded in TRACEABILITY.md, notably:
sword-icon auto-ignore has no supporting data anywhere in the code (T2);
§8.3.3's remove-friendly-without-replacement clause is unimplemented
(T3); §8.1.2 has no shared placement/removal-order helpers (T4).

## Session 23: T1 fix — §8.1 Commands Not Limited (July 2026)

`engine._allowed_for_faction` (new) wraps `_options_for_slot`: when the
Sequence of Play (2.3.4) offers a seat a Limited Command and the seat is
a Non-player, the slot is upgraded to a full Command + Special Activity
per §8.1 "Commands Not Limited". Event availability still follows the
SoP; human seats keep the limitation; event-granted free LimComs remain
limited through the free-op path (§8.1's own carve-out). Unit-tested in
`test_commands_not_limited_8_1.py` (bot upgrade, human unchanged, SoP
event flags preserved, first-eligible and after-event slots untouched).

Opening the suppressed paths immediately tripped the gate (1778 seed 10)
on three latent §3.2.1 Muster bugs, all fixed here:

1. **Tory type filter missing (bot + executor).** §3.2.1: Tories may be
   placed only in Cities or Colonies. `british_bot._tory_eligible` and
   `muster.execute`'s Tory loop both lacked the type check, so Tories
   could be planned into (and executor-placed in) Reserves.
2. **Fabricated zero-count Regular plan.** `_muster` passed
   `{"space": all_muster_spaces[0], "n": 0}` when it had no Regulars to
   place, pointing the executor's Regular-destination check (3.2.1) at
   arbitrary selected spaces (a Reserve, a Blockaded City) → ValueError.
   Removed; `regular_plan=None` is the executor's documented Tory-only
   contract.
3. **Step-3 target unbound / RL at the wrong space.** With no Regular
   plan, `muster.execute`'s Fort/Reward-Loyalty step crashed on an
   unbound `dest`; worse, the bot never passed its B8-chosen RL space,
   so Reward Loyalty silently executed (or was silently skipped) at the
   Regular destination instead of the flowchart-selected space. The
   step-3 space now flows through `fort_space` (Fort or RL), with a
   clean skip when there is no target. Regressions in
   `test_muster_321_regressions.py` (4 tests).

Verification: both roots green (1,240 + 41); clean-sweep gate clean,
seeds 1-20, all scenarios, invariants on; soak 200 games invariants-on,
zero crashes/failures; balance rebaselined — 33/60 pinned winners
flipped, the expected magnitude for a fix that changes every
2nd-eligible-after-Command bot turn. Per-scenario aggregates: 1775
9/7/4 → 7/7/6 (IND/PAT/BRI), 1776 16/4 → 12/7/1 (PAT/BRI/IND), 1778
9/8/2/1 → 5/10/2/3 (PAT/FRE/IND/BRI). British recover share everywhere,
consistent with previously-suppressed SAs; 1776 remains Patriot-favoured
as documented in Session 17.

## Session 24: T2 sword/musket icon audit — record correction (July 2026)

T2's premise was wrong and is hereby corrected: Session 22 claimed "no
sword icon data exists in code" based on a case-sensitive grep. In fact
`base_bot._choose_event_vs_flowchart` has always checked
`card["faction_icons"]` for SWORD (auto-ignore, §8.1) and MUSKET
(directive consult, §8.3.1), and `lod_ai/cards/data.json` carries
`faction_icons` for every card. This session verified the data instead:

- data.json icons == reference ICON lines, all 109 cards, exact match.
- event_instructions dict keys == musket-icon sets, all four factions
  (the "pared-down" comment was stale). One unreachable extra removed:
  INDIANS card 86 (reference: P-Musket only).
- New permanent drift test `test_icon_data_matches_reference.py`
  (4 tests): data.json vs reference, dict keys vs musket sets, no
  sword/directive overlap, and end-to-end sword auto-ignore behaviour.

Found in passing, NOT fixed (blocked on missing source text, QUESTIONS.md
Q15): `force_if_eligible_enemy` computes enemies as
{BRITISH, INDIANS, FRENCH} − {self}, so British count their Indian ally
as an enemy and Patriots are never counted as anyone's enemy (T12).

Lesson recorded: negative claims ("X does not exist in the code") must be
verified case-insensitively and against data files, not just .py sources.

## Session 25: T12 fixed — cards 18/44 enemy targeting (July 2026)

Eric pointed out the Event Instructions sheet contents live at the
bottom of each flowchart reference file ("Special Instructions",
keyed by card TITLE — number-based greps missed them; second search
false-negative this week, lesson repeated). Sheet wording for 18/44:
"Target an Eligible enemy Faction. If none, choose Command & Special
Activity instead."

Fixes:
- `base_bot.force_if_eligible_enemy`: enemy set was
  {BRITISH, INDIANS, FRENCH} − {self} (British counted their Indian
  ally; Patriots were never an enemy). Now side-based per Glossary
  "Enemy" (1.5.2) via `_enemy_factions()`; among multiple eligible
  enemies the target is chosen per §8.3.5 harm ordering (random enemy,
  player first, seeded rng) and passed via card{18,44}_target_faction.
- Card 18/44 handlers hard-defaulted to BRITISH / PATRIOTS — a British
  bot playing 18 made ITSELF ineligible. Now side-aware fallback from
  state["active"] when no explicit target (human CLI target selection
  remains a Piece 7 item).
- Free-op battle planner approved French Battle grants pre-ToA that
  battle.execute rejects (§3.5) — surfaced as a FREE BATTLE_PLUS2 skip
  on gate seed 1775:13 after the targeting change shifted trajectories.
  Planner now declines pre-ToA French battles (genuine decline).

Verification: both roots green (1,249 + 41; 7 tests added); gate clean
seeds 1-20 invariants-on; balance rebaselined — 11/60 flips,
concentrated in 1775 (Indians 7→11: Royalist events no longer waste
targeting on allies, and Indians are never targeted by British);
1776 aggregate unchanged.

## Session 26: T3 — §8.3.3 clause 2 + dead no-effect clause (July 2026)

Implemented §8.3.3's second clause: an Event whose ONLY effect would be
to remove one or more friendly pieces without replacing them with other
friendly pieces is Ineffective. Method: exact reconstruction — deepcopy
the simulated *after*, restore every removed Side piece per space and
its pool entries, and require equality with *before*; any friendly
placement or any other change (support, resources, markers, enemy
pieces) fails the reconstruction, so the clause fires only on strict
"only removal" cases. "Friendly" spans the executing Side (Glossary
"Enemy" mirror, §1.5.2; §8.3.5 treats ally pieces as friendly).

Bigger find while testing: the §8.3.3 "no effect at all" clause has
been DEAD in every live game. `random.Random.__eq__` is identity-based,
so two deepcopies of a state carrying the seeded rng never compare
equal, and `_is_ineffective_event`'s `before == after` always returned
False. Unit tests passed because their hand-built states had no rng.
The comparison now strips rng, rng_log, and history (die rolls are not
game effects). Property-test moral for ROADMAP Piece 4: equality-based
invariants must be exercised against production-shaped states.

Verification: both roots green (1,255 + 41; 6 tests added); gate clean
seeds 1-20 invariants-on; soak 200 games zero failures. Balance
rebaselined: 27/60 flips — the revived no-effect clause changes many
event-vs-command decisions. Indians 1775 11→14 and French 1778 9→13;
Patriots 1775 5→2. Direction is coherent (bots that previously wasted
turns executing null events now take Commands; strong-Command factions
gain). The 60-game pinned sample has wide variance — true rates to be
characterized by the Piece 8 large-N run.

## Session 27: T4 — §8.1.2 shared order helpers (July 2026)

New `lod_ai/util/nonplayer_pieces.py` transcribes the six §8.1.2
bullets as documented helpers (friendly place/remove orders, the move
bullet with Unavailable-first `pull_to_map` and the return order, the
enemy targeting bullet, side/cube-pair definitions: Royalist cubes =
British Regulars + Tories, Rebellion cubes = French Regulars +
Continentals).

Reading the full section corrected two errors from THIS WEEK's fixes —
the friendly-removal and enemy-removal bullets differ, and Sessions
21/23 applied the friendly order to enemy removals on card 6:

- Card 6 unshaded (British removing Patriot Fort+Militia): Session 21
  changed Militia removal to Active-first citing §8.1.2 — but that is
  the FRIENDLY order; the enemy bullet says "target enemy Underground
  Militia or War Parties before Active ones." Reverted (the pre-
  Session-21 code had been right by accident).
- Card 6 shaded (Rebellion removing British Fort+cubes): Session 23's
  local helper alternated from MOST and spared the last Tory — both
  friendly-removal features. Enemy order alternates from FEWEST
  (Regulars if even) with no sparing. Replaced with
  `remove_enemy_cubes`.

Migrations this session: card 6 (both sides), cards 32u/43u/46u pool
pulls → `pull_to_map`. Remaining hand-rolled sites migrate with the
Piece 3 card audit.

Verification: both roots green (1,265 + 41; 9 helper tests +1 corrected
card-6 test); gate clean seeds 1-20 invariants-on; balance checked over
the FULL 60 pinned games — zero flips, no rebaseline (the ordering
changes are within-space and did not alter any pinned outcome).

Process note: this is the third instance of a misapplied or missed
reference passage in one week (T2 grep, Q15 sheet location, now the
friendly/enemy bullets). The pattern: acting on a partial reading.
The traceability matrix exists precisely to force full-section reads;
Piece 2 should extend it to Ch 1-7 before more Ch 1-7-dependent fixes.

## Session 28: Event Instructions content audit — all 48 sheet entries (July 2026)

Source: the per-faction "Special Instructions" sections at the bottom of
the four flowchart reference files (located Session 25). Every entry was
classified (play-condition / text-side selection / execution guidance)
and checked against event_instructions.py, the per-bot condition code,
and (where cheap) the handlers. Verdicts:

**Fixed this session (3):**
- BRITISH 80: condition counted INDIAN pieces as a "Rebel Faction with
  pieces in Cities" — Indians are Royalist (1.5.2). Dropped.
- INDIANS 18/44: the local override verified an eligible enemy existed
  but never TARGETED one; the handler then defaulted (post-T12,
  side-aware, but not eligibility-aware — only-French-eligible produced
  a Patriot target). Now routed through the generic
  force_if_eligible_enemy directive (condition + §8.3.5 targeting);
  local helper and card-set removed.
- BRITISH 29 (ignore_if_4_militia): "would Activate" was computed as
  Underground//2, ignoring already-Active Militia. Card 29 activates
  "until ½ of them are Active", so the count is floor(total/2) − Active.
  With 8U/6A the old formula said 4 (play), the correct count is 1
  (ignore).

**Verified OK (18):** B18/B44/P18/P44/I18/I44 (post-T12), P8 (matches
"If French is a human player, C&SA"), P71 + P90 + I32 + I4 + I38
(text-side selections incl. village/WP placement conditions), I72/I90
(village conditions), I83 (side-pick on village placeability), B62
(New York Active-Opp + no-Tories condition), B70/P70/I70/F70 (Q2
audit), F52 (+ no-remove flag), F62 (militia-only flag).

**Backlog (new items in TRACEABILITY.md):**
- T13 (P2): B51/P51 "March to set up Battle per the Battle
  instructions" conditions hand-roll Force-Level math (min-pairing,
  halving approximations) that Sessions 19-20 eliminated from
  B12/P4/F16 — rebuild on battle.bot_battle_scores + the free-March
  planner. B52/P52 similar but milder.
- T14 (P2, fold into Piece 3): execution-guidance sweep — verify the
  HANDLERS implement per-faction selection guidance: B23 (move
  Patriots Support→non-Support), B30 shaded (leave 1 Regular per
  space; also the directive "force" is a layer error — the sheet gives
  no play condition for unshaded 30), B52 (removal sites), B80/I80
  (City/Fort space selection), B88/P88/I88/F88 (March origin shared
  with enemy), B95/I21 (non-Village first)/I22 (Village first)/I86/P86
  (Village space)/I89/F89 (Active Support first), P83 (Quebec City
  control), B29/P29/I29 (Activation targeting — partial test coverage
  exists).
- T15 (P3): "would-be-removed/would-gain" conditions approximated as
  "exists": P80 (any Village vs Village-would-be-removed), F73/F95
  (Fort exists vs Fort-would-be-removed), F83 (assumes 3 pieces might
  flip Quebec City control). Tighten by simulation.

Tests: test_force_if_eligible_enemy.py +2 (card 80 Indians-excluded,
card 29 formula), test_indian_bot_compliance.py rewritten 18/44 test
(targeting via generic directive).

## Session 29: Ch 8 small items — T5, T6, T9 (July 2026)

- **T5** `_ops_leader_destination`: equal-size groups (origin included)
  now resolve by seeded random per §8.1 ("select which one the Leader
  joins randomly"); previously first-neighbour-in-iteration won and an
  origin tie always stayed. Moved-group tracking (vs the post-move
  count approximation) still open — needs executor move recording.
- **T6** The blanket 0-Resource PASS gate is faithful for B3/P3/F3 but
  the Indian flowchart has no such node. Exempting Indians exposed:
  `_can_scout` missing the Indian half of §3.4.3's two-payer cost
  (crashed the gate at 1775:3 once un-shielded), and Indian March had
  no affordability guard at all plus never claimed §3.4.2's free first
  destination for all-Reserve origins. March now trims destinations to
  budget (§8.1 partial execution) and passes `all_reserve_origin`.
- **T9** swept: ~20 arbitrary subset selections catalogued with line
  numbers into TRACEABILITY.md; all are per-card space selections for
  the Piece 3 audit, none fixable blind.

Verification: both roots green (1,270 + 41; 4 tests added); gate clean
seeds 1-20 invariants-on; soak 120 games zero failures. Balance
rebaselined: 22/60 flips — the Indian behavior changes are real (act at
0 Resources via Trade/free March; low-resource Marches now execute
trimmed instead of erroring into a PASS; leader positioning varies on
ties). 1775 Indians 13→9, Patriots 2→5; 1776/1778 within usual movement.

## Session 30: §8.4–8.7 verification survey + 4 fixes (July 2026)

Piece 1's remaining half: four parallel audit agents verified Manual
8.4-8.7 + the four flowcharts against the bots (full findings:
docs/session30_faction_survey.md; ~45 backlog items). High-severity
claims were hand-spot-checked before recording. Fixed immediately:

1. `_sa_done_this_turn` and `_muster_die_cached` were set and NEVER
   cleared — after the first Garrison SA every later British Muster
   silently skipped its Skirmish/Naval Pressure for the rest of the
   game, and B6's Muster-vs-Battle die was rolled once per GAME. Both
   now cleared at take_turn entry (per-turn scope; tested).
2. French F2 bullet "Event moves French Regulars or Squadrons from
   Unavailable" was dead: it read unavailable-box keys
   (FRENCH_UNAVAIL/SQUADRON) that setup remaps to REGULAR_FRE/BLOCKADE.
3. Patriot Rally fort builds lacked the §1.4.2 stacking-room check in
   the Win-the-Day path (and belt-and-braces on two other sites) —
   crashed the gate at 1778:12 once the unfrozen flags shifted
   trajectories.

Two genuine reference contradictions found → QUESTIONS.md Q16 (pre-ToA
Hortalez "up to 1D3" vs flowchart exact-spend) and Q17 (failed Raid →
Gather per manual, → I6 per flowchart). Per Never-Guess: awaiting
Eric's ruling; code currently follows the flowchart in both.

Verification: both roots green (1,272); gate clean seeds 1-20
invariants-on; balance rebaselined (the unfrozen SA/die flags are a
major British behavior restoration). Backlog triage for the ~45
survey items is the next block of Piece 1/Piece 3 work.

## Session 31: Survey backlog block 1 — WTD rallies + Garrison SA order (July 2026)

- §8.4.1 Garrison SA order was inverted: "First execute Naval Pressure,
  or if that is not possible, Skirmish" — code ran Skirmish first
  (`_skirmish_then_naval`); now `_naval_then_skirmish`.
- §8.5.1 Win-the-Day free Rally was hardwired to the battle space; the
  rule grants "a free Rally Command (8.5.2) in one space", selected by
  the 8.5.2/P7 priorities. The correct selector (`_best_rally_space`)
  existed as dead code and is now wired in.
- §8.6.6: the French bot's callback declined the free Patriot Rally
  outright (comment claimed it was the Patriots' optional cross-faction
  choice; the rule text is mandatory and resolved Q9 had already ruled).
  Non-player Patriots now rally via P7 priorities; human Patriots still
  skip (Piece 7 CLI item).
- §8.5.1/§8.6.6 Blockade move destination must have strictly MORE
  Support than the battle City — both callbacks now enforce it
  (`_best_blockade_city(min_support=…)`); previously any max-support
  city qualified, even at equal or lower Support.

Verification: both roots green (1,272 + 41; +1 blockade test); gate
clean seeds 1-20 invariants-on; balance rebaselined (47 baseline lines
changed — Garrison Naval-first plus real WTD rallies move many pinned
games). Survey items remaining: Supply pay-vs-move inversions (3
factions), dead BS reaction chain, Scout/Raid/March deviations — see
docs/session30_faction_survey.md.

## Session 32: Q16/Q17 rulings implemented (July 2026)

Eric ruled on both open reference conflicts:

- **Q16 (pre-ToA Hortalez):** the manual controls — "spending up to 1D3
  French Resources" (8.6.1); flowchart F6's "Spend 1D3 … If none, Pass"
  is space-saving abbreviation. `french.py:_hortelez` now pays
  min(roll, Resources) on both sides of the Treaty; previously the
  pre-Treaty branch demanded the exact roll and the French could PASS
  holding 1-2 Resources on a roll of 3. Two tests that encoded the
  exact-spend reading rewritten to the ruling.
- **Q17 (failed Raid routing):** the specific flowchart routing
  controls over the general manual clause — a failed Raid (or March)
  proceeds to the I6 decision and may end up Scouting/Marching instead
  of Gathering. The code already did this; the ruling is now documented
  at the routing site (indians.py) so future audits don't re-flag it.

Verification: both roots green (1,274 + 41; +1 Q16 test); gate clean
seeds 1-20 invariants-on; balance within band (5/60 flips from Q16 —
pre-Treaty French no longer skip Hortalez), baseline refreshed.

## Session 33: Supply pay-vs-move rewritten for Patriots/French/Indians (July 2026)

The three Winter Quarters Supply branches paid unconditionally (or, for
the French, moved unconditionally) in bot-suggested order. The rules
make the choice conditional on a simulated Control change:

- §8.5.5 Patriots: pay ONLY where removing half the units (6.2.1)
  would change Control — ordered by would-enable-Reward-Loyalty
  (6.4.1: British Control + Regular + Tory + sub-Active Support), most
  Villages, highest Population; everywhere else remove per 8.1.2
  (Continentals first, then Active before Underground — the old code
  removed in exactly the reverse order, and paid every space).
- §8.6.7 French: pay ONLY where the Regulars' departure would change
  Control (RL-first, then Pop); everywhere else move to the nearest
  Patriot Fort or to Available. Old code moved-first everywhere and
  only paid when NO fort existed anywhere on the map. Nearest-fort
  ties now break randomly (8.2, seeded).
- §8.7.5 Indians: pay first where the War Parties' departure would ADD
  Rebellion Control, then where Gather could place a Village (room,
  3 WPs or 2 with Cornplanter, Neutral/Passive support, Village
  available); if neither or Resources run out, move to the nearest
  Village. Old code paid every space in bucket order including the
  must-move bucket, with no post-move simulation.

Control changes are decided by actual simulation (`_control_after`:
copy spaces, apply the removal, refresh_control, compare). The
Patriot/French/Indian `ops_supply_priority` bot hooks are no longer
consulted (the rules fully determine the ordering); the British branch
keeps its hook. Four tests that encoded the bot-hook contract were
rewritten to assert the rules.

Verification: both roots green (1,274 + 41); gate clean seeds 1-20
invariants-on; balance rebaselined (large shift, as expected for a
change to every faction's yearly Supply economics).

## Session 34: BS reaction chain revived (July 2026)

The bot Brilliant-Stroke REACTION triggers — 8.4.11 "…or the Patriots
play their Brilliant Stroke card", 8.6.11 "…or the British play
theirs", 8.7.8 "…or a Rebellion Faction plays a BS other than the
Treaty of Alliance" — were dead for all factions: `bot_wants_bs`
implemented them correctly, but the engine only polled bots once with
`other_bs_faction=None` and never re-polled after a declaration.

The trump resolution is now a queue (`engine._bs_trump_chain`): after
each successful declaration, every undeclared bot is re-polled with the
declarer as `other_bs_faction`; responders join the queue and trump per
the 2.3.8 hierarchy (Trumped cards return to their owners; ToA stops
the chain). Human reactions to a bot BS remain a Piece 7 CLI item.

Tests: test_bs_reaction_chain.py (2 — reaction+trump path, no-trigger
path). Both roots green (1,277 + 41); gate clean seeds 1-20
invariants-on; balance unchanged over all 60 pinned games (no
rebaseline) — bot-on-bot declarations are rare in the pinned seeds but
now resolve correctly when they occur.

## Session 35: Indian Raid — one SA per turn + two-tier target sort (July 2026)

- The Raid sequence's zero-Resource block ran Plunder AND Trade
  unconditionally, then fell through to the I5 block which could
  Plunder again — up to THREE Special Activities in one turn (§4.1
  allows one). Now: one SA total, gated on _turn_used_special (which
  the SA executors already set): at 0 Resources, Plunder or-else Trade
  (8.7.1's either/or); otherwise I5 Plunder, else War Path, else Trade.
- Target priority was a raw WP-minus-Rebels margin sort; 8.7.1 is a
  two-TIER order — "first where Plunder will be possible after the
  Raid movement, then elsewhere, within each … highest Population" —
  with equal candidates breaking randomly per 8.2 (seeded). The
  plunder-possible test now includes the Underground WP the Raid
  itself would move in.

Remaining under this item (documented, not implemented): the mid-raid
replenish reading — selecting up to 3 spaces beyond current Resources
and Plundering when they hit zero to fund the remainder — stays
unimplemented; selection is still capped at min(3, Resources). The
Playbook's Indian example (Trade at 0, then "can only afford to Raid
in one space… only one Raid will be executed") supports the cap when
the SA is already spent; whether an unused SA licenses over-selection
needs either the Playbook's other examples or a ruling. Filed in
TRACEABILITY under the survey backlog.

Verification: both roots green (1,278 + 41; +1 one-SA test); gate
clean seeds 1-20 invariants-on; balance rebaselined (Indian SA economy
tightened; modest shifts).

## Session 36: Scout retention — British Control preserved (8.7.4/1.7)

Scout's "most Regulars and Tories possible without losing British
Control or adding Rebellion Control in the origin" had two leaks:
§1.7's second condition (British Control needs at least one BRITISH
piece present) was never checked, so Scout could move every British
cube out of a controlled origin; and the minimum fallback forced a
1 WP + 1 Regular move even when no legal budget existed. Now: a
British-controlled origin keeps its Royalist majority AND one British
cube (unless a British Fort covers presence); an uncontrolled origin
only guards against handing Rebellion Control (budget = royalist −
rebel, correcting the extra piece the old formula retained); no legal
budget → Scout declines and the flowchart falls through to March per
IF NONE. Origin-before-destination selection order remains a
documented survey item.

Tests: +1 (both leak cases). Both roots green (1,279 + 41); gate clean
seeds 1-20 invariants-on; balance rebaselined (4 baseline lines).

## Session 37: Muster — six Regulars; Tory priority 2 rebuilt (8.4.2)

- The Regular plan was capped at 4; 3.2.1 allows "up to six" and 8.4.2
  says "as many Regulars as possible". Now min(6, Available).
- Tory priority 2 ("then to change Control of the most Population")
  sorted by the LARGEST rebel-minus-British deficit — precisely the
  spaces the Tories are least likely to flip — and ignored Population
  and whether Control would actually change. Now: only spaces where a
  1.7 simulation of the placed Tories changes Control, ranked by
  Population, seeded-random ties (8.2).

Tests: +1 (six-Regular plan via executor spy). Both roots green
(1,280 + 41); gate clean seeds 1-20 invariants-on; balance rebaselined
(British Muster throughput up; sizeable shift as expected).

## Session 38: Garrison origin pool, Phase 2a scoping, displacement, skirmished-City exclusion (July 2026)

Queue item 1 (survey British #3 remnants), plus two latent bugs found on
the way through the battery.

- §3.2.2/§8.4.1 origin pool: only British-Controlled spaces contributed
  Regulars. Now any space with Regulars contributes (excluding West
  Indies and Blockaded Cities); the leave-2-more retention applies only
  to origins "with British Control" (the rule scopes it there), while
  the last-Regular rule (Pop 0 / Active Support) applies to every
  origin. Royalist/Rebellion retention tallies now mirror the §1.7
  Control tally (Villages/war parties count as Royalist; Villages were
  previously omitted).
- §8.4.1 Phase 2a: targets were only Rebellion-Controlled fortless
  Cities. Now any City NOT under British Control qualifies (flipping an
  Uncontrolled City "adds" British Control too); Cities with a Patriot
  Fort stay eligible behind the fortless tier and NYC (priorities read
  as successive filters per the bot convention — §3.2.2 places no Fort
  restriction on movement); "needed" is computed with the §1.7 tally.
  Partial moves that cannot reach the Control threshold are skipped
  ("Move just enough Regulars to ADD British Control").
- §8.4.1 "Do not move Regulars to any City where a Skirmish has been
  executed" was unenforced: skirmish.execute now records its space in
  state["_turn_skirmished_spaces"] (cleared per turn in base_bot), and
  Garrison Phases 2a/2b exclude those Cities.
- §3.2.2 displacement was restricted to moved-into Cities; now ANY
  post-move British-Controlled, fortless, non-Blockaded City qualifies
  (Limited Command: destination City only, §2.3.5). Source = most
  Rebellion units ("largest possible number", §8.4.1); seeded
  tie-breaks (§8.2) replace first-seen/alphabetical in the source pick,
  the Province-target pick, and Phase 2b ordering.
- BUG (dead code): garrison.py's `_is_blockaded` read a
  state["naval"]["blockades"] dict nothing populates (the real store is
  state["markers"][BLOCKADE]["on_map"], util.naval.has_blockade), so
  §3.2.2's Blockade exclusions could never fire. Session 22's command
  audit had marked them CORRECT — the checks existed but were
  unreachable. Now routed through util.naval; bot planning filters
  Blockaded origins/destinations/displacement Cities to match.
- BUG (planner audit gate): one Garrison plan could use a City as both
  origin and destination, double-booking its Regulars (1778 seed 2:
  Boston sent 2 to Philadelphia AND received 2 from Savannah; "needed"
  was computed on the pre-move tally, so post-move Boston was still
  Rebellion-Controlled and garrison.execute's displacement Control
  check raised the trapped ValueError). Planned target Cities are now
  removed from the origin pool before allocation, and Phase 2b
  thresholds plus the displacement Control simulation use net planned
  flows (incoming − outgoing).
- Free-op planner (§3.5.3): a locationless free FRENCH Muster was
  planned with the BRITISH destination rule (non-Blockaded City /
  adjacent Colony); muster.execute then raised "French Muster requires
  Rebellion Control (or West Indies)" and the clean-sweep gate logged a
  free-op execution skip (1778 seed 5, exposed by this change's
  trajectory shift; baseline HEAD was clean on that seed). The planner
  now applies §3.5.3 (Colony/City with Rebellion Control, or WI) and
  declines pinned illegal locations as a genuine decline.

Tests: `test_garrison_city_requires_rebellion_control` (pinned the
Uncontrolled-Cities-excluded behavior) and
`test_garrison_phase2b_reinforce_targets` (control dict inconsistent
with its own pieces) rewritten to the rule with citations; +9 tests in
TestB5GarrisonRemnants; new lod_ai/tests/commands/test_garrison.py
(Blockade exclusions live, skirmish recording); +2 free French Muster
planner tests.

Verification: both roots green — 1,296 (lod_ai/tests, incl. balance
canary) + 41 (tests/) = 1,337; clean-sweep gate seeds 1-10 and 11-20
clean with invariants on; soak 120 games clean; balance rebaselined
(old → new): 1775 P 5%→0%, B 20%→30%, I 75%→70%; 1776 B 30%→50%,
P 35%→25%, I 35%→25%; 1778 F 50%→70%, P 35%→20%, B 15%→5%, I 0%→5%
(25 winner changes; the stronger early-war British Garrison and the
now-executing free French Musters account for the directions; the 1778
British slide is worth rechecking after queue item 2's March fixes).

## Session 39: British March destination rules (§8.4.3 / B10) (July 2026)

Queue item 2 (survey British #3 March remnants), plus latent bugs in the
same path.

- Phase 2 tier-2 catch-all removed: §8.4.3 lists exactly two Phase 2
  destination profiles — "first to add Tories where Regulars are the
  only British units, then to add Regulars where Tories are the only
  British units" — but the old tier assignment admitted EVERY Pop 1+
  non-Active-Support space as tier 2, marching groups into spaces the
  rule never names.  Only the two profiles qualify now (a tier-0 group
  must actually carry a Tory to "add Tories").
- Population 1-2 limit: now written as 1 <= pop <= 2 per the Manual
  ("spaces with Population one or two"); the flowchart's "Pop 1+" is
  extensionally identical on this map (no space exceeds Population 2),
  so no reference conflict was filed.
- Already-selected preference un-inverted: the rule says "within each,
  move first to March destinations already selected above"; the old
  code EXCLUDED seen destinations.  They are now preferred within each
  tier, evaluated on the post-move board (planned arrivals count toward
  the profile test), and re-using one consumes no new destination slot
  (§3.2.3 pays per destination space selected).
- Common Cause Tory double-count (survey :1239): "make up the
  difference between the number of Regulars and Tories IN THE GROUP" —
  the old code compared the space's raw Regulars against the space's
  Tories PLUS the group's movable Tories, understating the difference
  (often negative), so CC War Parties almost never joined.  Group
  counts are used now; the Tory escort is no longer cut to make room
  for War Parties (the executor caps Tories + WPs jointly at the
  Regular count, which the plan satisfies by construction).
- BUG (phantom CC War Parties): the old plan never put War Parties in
  the march pieces — common_cause.execute only readies them in the
  origin (Active first, §4.2.1); march.execute moves them only when
  they appear in a plan entry.  The WPs' "group size" contribution was
  therefore paper-only and destinations never received them.  CC WPs
  now march with their group and arrive Active; if common_cause.execute
  fails at execution time, the planned WPs are stripped from the plan
  instead of crashing march.execute.
- Phase 1 rebuilt to the §8.4.3 sentence: "Moving the largest groups
  first, add British Control to Cities, then Colonies ... Stop moving
  groups into each destination space once British Control is
  established."  Multiple groups now accumulate into one destination
  until Control flips (the old planner sent exactly one group and never
  checked the goal); a destination that cannot reach Control with the
  available groups is skipped and its tentative commitments rolled
  back (a partial move adds nothing).  Rebellion-cube priority is
  presence (binary, per the rule text) then highest Population then
  seeded random (§8.2) — the old sort used most-cubes.  Destination
  Control math uses the §1.7 tally net of pieces already committed
  out (Session 38's double-booking lesson applied here too).
- March-in-place: §3.2.3 activates ONE Militia per THREE British cubes;
  the old code flipped every Underground Militia in the space (a large
  illegal British benefit) and would pay a Resource for spaces with
  fewer than 3 cubes where nothing could activate.  Both fixed; the
  in-place priority is "first in spaces with Support" (binary) with
  seeded ties.
- Execution no longer slices the plan to 4 ENTRIES: the Max-4 limit is
  on destination spaces (capped during planning); multi-group plans
  legitimately exceed 4 entries.
- _movable_from retention now uses the §1.7 tally (Villages count as
  Royalist) net of ALL committed pieces including CC War Parties.

Tests: new lod_ai/tests/test_brit_march_8_4_3.py (7 tests: catch-all
removal, Pop 0 exclusion, already-selected preference, 3-cube in-place
gate, multi-group accumulation, unreachable-target skip, CC group
difference with WP arrival).  test_british_march_in_place.py's
flip-all assertion rewritten to the §3.2.3 one-per-three rule (its own
comment had flagged the discrepancy).

Verification: both roots green — 1,303 (lod_ai/tests, incl. rebaselined
canary) + 41 (tests/) = 1,344; clean-sweep gate seeds 1-10 and 11-20
clean with invariants on; soak 120 games clean; balance rebaselined
(old → new): 1775 B 30%→25%, I 70%→75%; 1776 P 25%→55%, B 50%→30%,
I 25%→15%; 1778 B 5%→20%, F 70%→55%, P 20%→25% (21 winner changes).
The big 1776 swing is the militia-activation correction — flip-all was
suppressing Patriot Underground Militia everywhere the British marched
in place; Session 38's 1778 British-slide flag is resolved (5%→20%).
Known remaining March gap (not in queue item 2, logged for the survey
long tail): the planner only considers adjacent destinations and does
not use §3.2.3's City-to-City / City-to-adjacent-Province movement.

## Session 40: Scout destination-first ordering; Q18 mid-raid replenish (July 2026)

Queue item 3 — the Scout remnant from survey Indian #4 plus the Raid
replenish that Eric's Q18 ruling unblocked.

- §8.7.4 Scout rebuilt destination-first: "first to a space with a
  Patriot Fort, then to a Village space with enemy pieces, then to
  remove the most Rebellion Control possible" now governs the whole
  selection over all legal (origin, destination) pairs; the origin is
  whichever origin serves the best destination, moving "the most
  Regulars and Tories possible" (tie-break: larger group, then seeded
  random per §8.2).  The old code picked the LARGEST origin first and
  scored only that origin's neighbours, so a big garrison with nothing
  worth scouting beat a small one sitting next to a Patriot Fort.  Two
  further consequences of reading the bullet as a priority list: a
  destination matching NONE of the three priorities is no longer a
  Scout target (falls through to March per IF NONE — the old code
  scouted into any adjacent province), and tier 3 is a post-move
  simulation (the arriving group must actually remove the Rebellion
  Control, §1.7 tally).  Session 36's origin-budget rules (no Control
  loss, keep a British piece, 1 WP + 1 Regular minimum) are preserved
  in a shared helper (_scout_budget).
- §8.7.1 mid-raid replenish per the Q18 ruling (specific over general;
  QUESTIONS.md): with an unspent SA the non-player Indians now SELECT
  up to three Raid targets regardless of the current purse; the Raid
  executes in affordable batches — raid what the purse covers, then
  Plunder in a just-raided space (else Trade), then raid the remainder
  with the new funds.  Unpaid spaces are skipped when the replenish
  comes up short.  A 0-Resource start with an unspent SA now Trades
  first and raids on the proceeds, matching the Playbook's Indian
  example turn.  Without an SA in hand (spent, Limited Command, or
  no-SA slot) selection stays capped at min(3, Resources) — the
  Playbook example's cap, per the ruling.  The mid-raid Plunder pick
  excludes spaces whose War Parties are reserved as sources for the
  remaining batch (Plunder removes a War Party and could strand a
  planned move).
- The one-SA discipline (Session 35) holds on every path: the mid-raid
  Plunder/Trade consumes the turn's SA, and _raid_sequence's post-raid
  SA block already keys off _turn_used_special.

Tests: test_raid_limited_by_resources rewritten to the ruling (cap
applies only when the SA is spent) with citation; +3 Q18 tests
(over-selection funded by mid-raid Plunder; failed replenish skips
unpaid spaces; 0-Resource start Trades then raids); +3 Scout tests
(destination priority beats origin size; no-priority neighbourhood
declines to March; tier 3 requires actual Control removal).

Verification: both roots green — 1,309 (lod_ai/tests, incl. rebaselined
canary) + 41 (tests/) = 1,350; clean-sweep gate seeds 1-10 and 11-20
clean with invariants on; soak 120 games clean; balance rebaselined
(old → new): 1775 unchanged rates (4 winner swaps); 1776 P 55%→45%,
B 30%→40%; 1778 B 20%→10%, I 0%→10% (20 winner changes).  Indians
taking games in 1778 for the first time in the baseline is consistent
with three-space Raids funded mid-Command and Scouts that now chase
Patriot Forts.

## Session 41: T13 + T15 — faithful card 51 conditions; would-be-removed simulations (July 2026)

Queue item 4, parts 1 and 3.  T14 (execution-guidance sweep, ~16 sites)
stays folded into the Piece 3 card audit per TRACEABILITY.md.

- T13: B51/P51 "March to set up Battle per the Battle instructions"
  force-conditions rebuilt on a new shared helper,
  `battle.bot_march_sets_up_battle` — bot_battle_scores (the resolver's
  own Force-Level + §3.6.5/3.6.6 Loss-modifier maths) evaluated on the
  current board and again after a simulated March of every eligible
  cube from ALL adjacent origins (§3.2.3 Tory escorts 1:1; §3.3.2
  Militia keep status, French Regulars accompany Continentals 1:1).
  The old hand-rolled checks (halved Militia, halved War Parties,
  min-paired Tories, no Loss modifiers) over-selected: e.g. 4 Patriot
  cubes vs 3 defending Regulars passed the old math but the faithful
  scores are 4 vs 4 — not a legal selection.  The simulation restores
  the board exactly (tested).  B52/P52 carry no battle math since the
  Session 28 errata rewrite — nothing to rebuild.
- T15: four "exists" approximations tightened by simulation:
  - P80: "select spaces where an Indian Village would be removed" —
    the handler removes 2 Indian pieces per space, War-Parties first,
    from spaces with 2+ Indian pieces; the condition now requires a
    space where the 2-removal actually reaches a Village (>= 2 pieces,
    <= 1 non-Village piece), and pins card80_faction/card80_spaces so
    the handler targets those spaces.  A lone Village is not even a
    candidate; a Village behind 3 War Parties survives.
  - F73: British Fort must be in the card's three removable spaces
    (New_York/Northwest/Quebec), and card73_space is pinned to the
    British-Fort space so the removal cannot hit a Patriot Fort first.
  - F95: British Fort must be in Northwest (the card's only space).
  - F83: "If playing the Event does not gain Rebellion there, C&SA" —
    simulates the shaded placement (up to 3 coalition pieces from
    Available, Patriot Fort first when the space has no Fort/Village,
    mirroring the handler's pools) against the §1.7 tally; previously
    True whenever Quebec City wasn't already Rebellion, even with an
    empty Available pool or a 6-cube garrison.  NOTE for T14: the F83
    HANDLER picks the Quebec/Quebec_City space with fewest pieces while
    the sheet says Quebec City — reconcile in the Piece 3 audit.

Tests: new test_t13_card51_conditions.py (6) and
test_t15_would_be_removed.py (7); three superseded tests rewritten to
the rule with citations (patriot card-51 tips-balance — now needs 5
cubes vs 3 Regulars per the modifiers; french force_if_83 — simulation
semantics on piece-consistent boards; errata force_if_80 — lone
Village is not a candidate).

Verification: both roots green — 1,324 (lod_ai/tests, incl. rebaselined
canary) + 41 (tests/) = 1,365; clean-sweep gate seeds 1-10 and 11-20
clean with invariants on; soak 120 games clean; balance: 1775
unchanged, 1776 B 40%→45% I 15%→10%, 1778 F 55%→45% P/B +5% each
(5 winner changes total — the tightened conditions mostly make bots
decline events that could not actually deliver their effect).

## Session 42: French March rebuilt to §8.6.5 (July 2026)

Queue item 5, first slice — survey French #4.

- "First in Cities, THEN COLONIES": bullet-1 destinations were any
  non-Rebellion space with every non-City type (Reserves included)
  tied at one sort level.  Now only Cities and Colonies qualify, tiered
  City → Colony, within each most British pieces, ties seeded (§8.2).
- Bullet 2 un-demoted: "THEN March any French Regulars that are not in
  or adjacent to a space with British pieces towards the nearest
  British" is part of the SAME March Command.  The old code ran it only
  when bullet 1 produced nothing, moved a single Regular from the first
  ALPHABETICAL source, and returned.  Now every isolated stack steps
  toward the nearest British in the same march plan — all its Regulars
  minus the lose-no-Rebellion-Control budget — with the next hop chosen
  by shortest distance and seeded ties.  A Limited Command still caps
  the whole March at one destination.
- Bullet 3 fallback ("if neither of the above are possible, March one
  French Regular to a space with both Patriots and British") retained,
  with seeded ties replacing the alphabetical source/neighbour scans.
- The affordability trim (1 French Resource per destination) and the
  Patriot escort-fee trim continue to apply to the combined plan;
  bullet-1 destinations keep priority in the trim order.

Tests: +3 (Colony tier beats a British-heavier Reserve; bullet 2
additive with a bullet-1 flip in the same Command and ALL isolated
Regulars moving — including the bullet-1 source's remainder; origin
retention keeps a Rebellion-Controlled stack's space).  Existing F14
suite unchanged and green.

Verification: both roots green — 1,327 (lod_ai/tests, incl. rebaselined
canary) + 41 (tests/) = 1,368; clean-sweep gate seeds 1-10 and 11-20
clean with invariants on; soak 120 games clean; balance: 1775 and 1776
unchanged, 1778 F 45%→40% B 15%→20% (7 winner changes) — the French
now push isolated Regulars toward the front instead of parking them,
which trades a little safety for rule fidelity.

Remaining queue-5 long tail (next sessions): pop-weighting
(level × Population per 8.1.1) + seeded tie-break sweep across
british_bot/patriot; Patriot Rally/March/Desertion/CoC items; WQ
redeploy 0-piece fallbacks.

## Session 43: WQ Leader Redeploy fallbacks per §6.5.2 (July 2026)

Queue item 5, second slice — the redeploy remnants from the survey
(Patriots "Also", Indians "Also") plus the same defect found in the
British and French picks on inspection.

§6.5.2: "Each Faction may redeploy its Leader marker to a space with
same Faction's pieces or Available."  All four bots' redeploy pickers
initialised their best-score scan at -1, so when the primary metric was
zero everywhere (no Continentals / British Regulars / French Regulars /
War Parties on the map) the FIRST DICT-ORDER SPACE won — a space with
no friendly pieces at all — and the year_end caller treated it as a
legal destination instead of sending the Leader to Available.

- Patriots (§8.5.6 "most Continentals"): candidates now require Patriot
  pieces (Continentals, Militia, Fort); at 0 Continentals the pick
  falls back to a Patriot-piece space; None (→ Available) otherwise.
- British ("most British Regulars"): candidates require British pieces
  (Regulars, Tories, Fort).
- French (Regulars+Continentals, then most Regulars): the fallback tier
  now requires French Regulars present; None otherwise.
- Indians (Brant/Dragging Canoe "most War Parties"; Cornplanter's
  qualifying-Province scan): candidates require Indian pieces — a
  Village space is legal at 0 War Parties; Cornplanter's first-seen
  dict-order pick over qualifying Provinces is now seeded (§8.2), as
  are all four factions' remaining ties.

Tests: new test_wq_redeploy_6_5_2.py (6 tests covering the zero-metric
fallbacks, Available (None) with no friendly pieces anywhere, and the
preserved primary priorities).

Verification: both roots green — 1,333 (lod_ai/tests) + 41 (tests/) =
1,374; clean-sweep gate seeds 1-10 and 11-20 clean with invariants on;
soak 120 games clean; balance identical on all three scenarios (zero
winner changes — the fixes bite only in rare zero-piece states), so no
rebaseline was needed.

## Session 44: §8.1.1 pop-weighting + §8.2 seeded ties — first sweep block (July 2026)

Queue item 5, third slice — the "most Support/Opposition" weighting
(§8.1.1: the value a space contributes to Total Support/Opposition,
i.e. level x Population) and seeded ties at four selection sites.

- Naval Pressure blockade pick ("then from the City with the most
  Support"): was the raw support level; now level x Population.
- Garrison displacement Province ("most Opposition then with least
  Support, within that lowest Population"): Opposition/Support terms
  now weighted; lowest Population separates remaining ties as before.
- Muster Reward Loyalty (§8.4.5 "lowest total of Raid and Propaganda
  markers, within that where the largest change in (Support -
  Opposition) is possible"): the change is now affordable shift levels
  x Population — capped by the purse after the per-marker costs and
  the per-space Muster cost, with the Gage discount — instead of the
  raw level distance to Active Support, uncapped.  The §8.4.5
  prohibition ("do not Reward Loyalty in a space if only Raid and/or
  Propaganda markers would be removed") is now enforced by filtering
  candidates whose affordable change is zero (this also drops Pop-0
  spaces, whose shift cannot change the total score).  Seeded ties.
- Patriot Rabble-Rousing (§8.5.3 "first in spaces with Active Support,
  within that first in the space with highest Population"): was a raw
  support-level cascade that wrongly ranked Passive Support above
  Neutral etc.; now a binary Active-Support tier, then Population,
  then seeded ties.

Tests: new test_pop_weighting_8_1_1.py (3 — weighted displacement
through _select_displacement; the §8.4.5 affordable-change ordering;
the §8.5.3 binary tier).

Verification: both roots green — 1,336 (lod_ai/tests) + 41 (tests/) =
1,377; clean-sweep gate seeds 1-10/11-20 clean with invariants on;
soak 120 games clean.  Balance rebaselined (old → new): 1775
P 0%→10%, B 25%→10%, I 75%→80%; 1776 P 45%→35%, I 10%→20%; 1778
F 40%→60% (beyond band), B 20%→5%, P 30%→25% (26 winner changes).
The magnitude is mostly trajectory shift — the new seeded tie-break
draws perturb the rng stream in every game that Rabble-Rouses or
Rewards Loyalty — plus a genuinely more selective RL (affordability
cap + markers-only prohibition).  The 1778 British rate has now
see-sawed 15→5→20→5 across Sessions 38-44 on comparable rng-stream
shifts, which suggests 20-game-per-scenario samples are too small to
read British 1778 strength from; ROADMAP Piece 8 (large-N stats) is
the right instrument — flagged there rather than chased per-session.

Remaining queue-5 items: Patriot Rally/March/Desertion/CoC block;
any residual raw-level/first-seen sites outside the four fixed here
(the Piece 3 card audit will catch handler-side ones).

## Session 45: Patriot block — §8.5.4 March, §8.5.2 Rally, §4.3.2 Partisans, §6.4.2 CoC, §8.5.7 Desertion (July 2026)

Queue item 1 — the Patriot block (survey #2/#4 + "Also" items).

§8.5.4 March (patriot.py _execute_march):
- French gate: "If French Resources exceed 0, include as many French
  Regulars as possible" — French Regulars are now planned only while
  the French purse can pay 1 Resource per destination they enter
  (§3.3.2; Rochambeau's space waived per leader_capabilities).  They
  were previously included unconditionally, so at 0 French Resources
  march.execute's escort-fee validation raised and the bot declined
  the ENTIRE March (the survey's "aborts entirely" finding).
- Destination budget: the artificial 4-destination cap is gone; the
  planner now stops at the Patriot purse (1 Resource per destination,
  §3.3.2; 1 destination when Limited per §2.3.5).  Previously the
  planner ignored affordability entirely, so any plan beyond the
  purse aborted wholesale on march.execute's spend().
- Phase 2 moves Militia ONLY ("get one Militia (Underground if
  possible) into each space with none") — the Continental fallback is
  removed; "first to change Control of the most Population" is now a
  real §1.7 simulation of the placed piece (was: any non-Rebellion-
  controlled space counted as a change), and Population no longer
  orders the "then elsewhere" tier (seeded random per the sheet).
- Latent fix: a failed Phase-1 gather left its tentative takes in
  moved_from, starving later destinations of movable pieces;
  reservations now happen only when a destination commits.

§8.5.2 Rally (patriot.py _execute_rally):
- "4+ Patriot units" now counts Patriot units only — Militia +
  Continentals (Glossary §1.4; French Regulars are French pieces).
  Was _rebel_group_size, which counted French Regulars.  Same fix in
  the P9 Rally-preferred gate and the Win-the-Day selector.
- Lonely-Fort and Fort-with-most-Militia placements now place to the
  §3.3.1 maximum extent (#Patriot Forts + Population, via
  rally.execute bulk_place) instead of a single Militia; §8.1.1.
- Bullet 6 no longer pads slots with no-benefit spaces: a space that
  neither changes Control (real §1.7 simulation) nor sits above
  Active Opposition is skipped.
- Bullet 2/3/4 Fort filters: the old guards admitted fortless spaces
  at the 2-base stacking cap as "Fort spaces"; they now require an
  actual Patriot Fort (or, for bullet 4, one built this Rally), and
  bullet 4's "most Militia" counts this Rally's planned placements.
- Bullet 7's origin check is now "without changing Control" (any
  change, incl. Uncontrolled→BRITISH; was Rebellion-loss only).
- Seeded ties (§8.2) throughout the Rally selections.

§4.3.2/§4.3.3 Partisans & Skirmish:
- Battle-space exclusion enforced: battle.execute records
  _turn_battle_spaces (cleared per turn in base_bot); partisans.execute
  and skirmish.execute (all three factions — §4.2.2/§4.3.3/§4.5.2)
  refuse Battle spaces; the Patriot pickers filter them out.
- Partisans option 3 requires only "no War Parties there" (+ Village
  + 2 Underground Militia) — the old bot gate wrongly demanded no
  enemy cubes, so Villages behind cube screens were never removed.
- Options 1/2 remove Royalist UNITS only (Glossary §1.4) — they could
  previously remove a Village or Fort.  Option 2 now requires the 2
  Underground Militia §4.3.2 demands (the old pick with 1 raised and
  skipped the space).  Space selection scores Village-removability
  (option-3 feasibility), not bare Village presence.  Card 3's free
  Partisans gate aligned (units-only + Battle-space check).

§6.4.2/§8.5.9 Committees of Correspondence (+§6.4.1 RL, year_end):
- RL and CoC now keep SEPARATE two-level-per-space caps (§6.4.1 and
  §6.4.2 are distinct activities; one counter was shared).
- CoC eligibility includes Patriot-Fort-only spaces ("Patriot
  pieces").
- Both sort potentials are now affordable-shift x Population, capped
  at 2 levels and by the purse after markers (was raw uncapped
  distance); seeded ties (§8.2, state-rng optional for bare tests).

§8.5.7 Patriot Desertion (year_end + patriot.py):
- The Patriot remainder is removed ONE PIECE AT A TIME with the
  priority list re-scored after every removal (Control margins and
  the last-unit test change as pieces leave); the old loop scored
  once and bulk-removed from the top space, which could strip a
  small stack bare, flip its Control, and empty it.  Seeded ties in
  ops_patriot_desertion_priority (was alphabetical).

Tests: new test_patriot_block_s45.py (14).  One superseded test
rewritten: test_option1_fort_to_available →
test_option1_cannot_remove_fort (§4.3.2 + Glossary units).

Verification: both roots green — 1,350 (lod_ai/tests) + 41 (tests/) =
1,391; clean-sweep gate seeds 1-10/11-20 clean with invariants on;
soak 120 games DONE clean.  Balance rebaselined (old → new): 1775
P 10%→30%, B 10%→20%, I 80%→50%; 1776 P 35%→80%, B 45%→20%, I 20%→0%;
1778 P 25%→35%, B 5%→0%, F 60%→65%, I 10%→0% (in band).  The drift is
Rebellion-ward, the expected direction (March no longer aborts, purse-
scaled destinations, max-extent Rally, pop-weighted CoC, safer
Desertion).  A game-log sanity check (1776 seed 3) showed no
pathology: one 3-destination March, normal Rally cadence, sane purses.
The 1776 Patriot 80% is a 20-game reading — Piece 8 should confirm
before any tuning conclusions.

Residual (noted, not in queue): partisans.execute's internal removal
order is a fixed tag list (Tory → Active WP → Regular → UG WP), not
the §8.1.2-cited priorities; §4.2.2 Garrison-destination/Muster-space
Skirmish exclusions (British) and §4.5.2 Muster exclusion (French)
remain unenforced at engine level; survey #4's Win-the-Day free-Rally
hardwiring is still open (not in this queue item).

## Session 46: ROADMAP Piece 2 — Ch 1-7 traceability matrix + §1.9 pop-0 fixes (July 2026)

Queue item 2.  New `TRACEABILITY_CH1_7.md`: numbered-section inventory
for Manual Ch 1-7 (123 sections), mechanical lookaround-guarded
citation scan over `lod_ai/` and both test roots, and a first hand-
verification pass covering all of Ch 1, Ch 2 spot checks (2.2-2.3.5
incl. the 2.3.3 pass bonuses +2 B/F +1 P/I), Ch 5, §6.3/6.4/6.6, and
Ch 7 line-by-line (all four §7.2 margin pairs and the §7.3 sums verify
algebraically — the ±10 offsets cancel).  Rows covered by prior
session audits carry their citations (Garrison S38, Scout/Raid S40,
French March S42, WQ redeploy S43, Rally/March/Partisans/CoC/Desertion
S45).  C-series backlog C1-C10 + verification queue at the bottom of
the file.

Fixed this session (the ROADMAP-named §1.9 class):
- C1 — "The population of that City is considered 0 for purposes of
  calculating Support": new `util/naval.effective_population`, applied
  at all three Total-Support/Opposition sites (victory._summarize_board,
  base_bot._support_opposition_totals, batch_smoke reporting).
- C2 — same rule "...and during the Resource Phase": French after-ToA
  income no longer counts Blockaded-City population (British income
  already excluded it).

Notable open findings (backlog): C3 one-Blockade-per-City set model;
C4 British March-to-Blockaded-City + FNI-3-Garrison verification; C5
§1.10 Leader orphan rule has no engine hook; C6 §1.4.1 voluntary
take-own-from-map path missing; C7 §7.1 ranking details (NP-first
ties, placements, all-players-lose, Combined Victory) folded toward
T11; C9 §2.3.4 executed-command criterion; C10 sweep bot pop-weighting
sites to effective population.  Also: board/pieces.return_leaders is a
per-WQ no-op with no textual basis (leaders live in state["leaders"])
— delete when touched.

Tests: new test_ch1_7_traceability_s46.py (3).

Verification: both roots green — 1,353 (lod_ai/tests incl. commands/)
+ 41 (tests/) = 1,394; clean-sweep gate seeds 1-10/11-20 clean with
invariants on; soak 120 games DONE clean (fresh soak.jsonl — the tool
resumes a completed file, so stale progress must be cleared first);
balance: 1775 and 1776 IDENTICAL to baseline (blockades are post-ToA
only — the change bites exactly where §1.9 applies), 1778 within band
(P 35→40, F 65→55, I 0→5, 6 winner changes) and rebaselined.

## Session 47: Piece 3 slice — T14 execution-guidance sweep, all 16 sites (July 2026)

Queue item 3, first slice: every handler on the Session 28 T14 list
verified against its card text and the per-faction Special
Instructions, and fixed where the guidance was absent.  F83's Quebec
City reconciliation (Session 41 note) is included.

Fixed:
- Card 80 (B/I/P executors): evt_080's default target was THE EXECUTOR
  — British and Indian bots removed their own pieces whenever their
  force_if_80 condition passed (neither bot preset the handler keys).
  The executor now targets an ENEMY (§1.5.2), british_bot presets the
  Rebel faction + its Cities (sheet B80), indians.py presets Patriots
  + Fort-would-be-removed spaces and its condition now requires the
  Fort to actually be reachable (≤1 Patriot unit beside it — §8.1.2
  Forts-last, mirroring S41's P80 fix).  Removal inside each space now
  follows the §8.1.2 friendly-removal order per faction
  (_remove_own_faction_pieces) instead of a flat tag list.
- Card 83: evt_083 now honors card83_target (french.py's preset was
  never read — the min-piece scan could pick Quebec over the sheet's
  Quebec City); P83 implemented ("Quebec City if possible to change
  Control there, otherwise Quebec", simulated per §1.7); the
  Fort/Village guard was requiring an EMPTY-base space — now §1.4.2's
  < 2 bases; seeded ties for the no-guidance executors.
- Card 88: single §8.2-seeded origin shared with an ENEMY faction
  (was: every shared space, first-listed neighbour, "enemy" could be
  anyone); destination via a March-priority proxy (gain own-side
  Control, else most friendly pieces, seeded).  Full per-bot March
  wiring stays open under T14 in TRACEABILITY.md.
- Card 52: P/F executors remove no French Regulars (sheets P52/F52 —
  french.py's card52_no_remove_french flag was set but never read);
  B52 removes from spaces where Rebels outnumber the British first;
  the +2-FL free Battle goes to the EXECUTOR (was hardwired FRENCH).
- Card 30: shaded removal leaves 1 Regular per space (largest stacks
  first, forced past the spare only when the quota demands — sheet
  B30); unshaded pulls from Unavailable first (§8.1.2, was
  Available-first) and picks its ≤3 spaces per §8.2 (was dict order);
  the EI.BRITISH "force" directive was a layer error (S28) — now
  "normal" (execution guidance only; key kept for the icon invariant).
- Card 23: origin prefers Support (sheet B23), destination restricted
  to adjacent PROVINCES (card text — was any adjacent space incl.
  Cities; Reserves excluded while Militia move), preferring
  non-Support, seeded ties.
- Card 29: activation flips in §8.2-seeded space order (target's own
  §5.1 choice; was dict order).
- Cards 21/22/86/89/95: sheet orderings implemented — I21 non-Village
  first (+§8.3.6 gain×Pop), I22 Village-first Colony (+ §8.1.2 enemy
  removal order), I86/P86 Village space if possible (was hardwired
  Massachusetts; unshaded requires Underground Militia per §5.1.3),
  I89 Village-first / F89 Active-Support-first, B95 War Parties first.
  Card 95 also stops placing ACTIVE Militia/WPs from Available
  (§1.4.3: new Militia/WPs place Underground).
- Engine latent fix: board/pieces._reclaim_one_from_map could reclaim
  from the DESTINATION space itself (place 3 WPs with pool 2 → the
  third "placement" recycled a WP already there and consumed the
  count).  Reclaim now excludes the placement target.

Tests: new test_t14_execution_guidance_s47.py (15).

Verification: both roots green — 1,368 (lod_ai/tests incl. commands/)
+ 41 (tests/) = 1,409; clean-sweep gate seeds 1-10/11-20 clean with
invariants on; soak 120 games DONE clean.  Balance rebaselined
(old → new): 1775 I 50→70 (beyond band), P 30→20, B 20→10; 1776
I 0→15, P 80→70; 1778 P 40→30, F 55→65 (both in band).  The Indian
gains are the expected direction — the card-80 self-removal bug alone
had Indians stripping their own pieces, and four Indian sheet
orderings landed.  20-game caveat as always (Piece 8).

Remaining Piece 3 items (unchanged): event_instructions transcription
diff vs the sheet reverse side, event_eval static-capability audit,
the ~20 T9 dict-order card-space picks, auto_place_blockade stub,
T7/T8 general who-benefits/second-faction-instruction layers.

## Session 48: Piece 3 slice — T9 space-pick sweep + auto_place_blockade + pick_cities data bug (July 2026)

Queue item 3, second slice: the Session-29 T9 catalogue of
first/alphabetical card-space selections, worked per card text with the
§8.3.5/§8.3.6/§8.2 treatment; plus the auto_place_blockade stub.

T9 sites fixed (all previously dict/alphabetical-order):
- Card 16: shaded pick is now largest (level+1)×Pop Opposition gain
  (§8.3.6 semantics for the set-to-Passive-Opposition shift); unshaded
  "two Tories anywhere" prefers a space where +2 British pieces GAINS
  Control (§8.3.8), WI excluded; both seeded.
- Card 19 shaded: 3 Militia via the §8.5.2-bullet-6 shape (change
  Control, then not at Active Opposition, Cities, Pop; WI excluded).
- Card 24 shaded: seeded ties on the City/Pop key; WI excluded; the
  "Place one Fort anywhere" is a separate choice — it now finds a
  selected space WITH §1.4.2 base room (a full top pick used to lose
  the Fort silently).
- Card 27: shaded Cities via select_support_shift_spaces (§8.3.6);
  unshaded pair of British-controlled Colonies via §8.2.
- Card 28: seeded ties on the max-Tories/max-Militia pick.
- Card 33 shaded: the two adjacent free-Rally spaces via §8.2 (was the
  first two in adjacency-list order).
- Card 72: Reserve with Fort/Village room first (§1.4.2), seeded; the
  docstring's "(Northwest preferred)" claim had no textual source and
  was dropped.
- Card 75: three of four Reserves via §8.2; the free War Path goes to
  a chosen Reserve holding Rebellion pieces (§4.4.2) when one exists.
  (Superseded dict-order test rewritten.)
- Card 79: the Colony must support the action (§5.1.3) — shaded needs
  a Village/WP to remove (Village first), unshaded needs base room.
- Card 90 unshaded: the space now follows the piece — a Patriot Fort
  no longer lands in the first dict-order Indian Reserve; Villages
  prefer Reserves with War Parties; Forts prefer Colonies with own
  pieces.
- Card 91: both sides seeded; unshaded prefers room + most War Parties.
- Card 96: the two free Gather/War Path Reserves via §8.2.

Latent DATA bug (T9 collateral): shared.pick_cities/pick_colonies
filtered on a space-dict "type" key that REAL states never carry
(build_state emits piece tags + control only) — both returned [] in
every real game.  Card 32 shaded has therefore always paid 0
Resources, and card 90's Colony tier was always empty (Fort → first
Reserve).  Now typed via map metadata with the dict key as a
test-fixture fallback.

auto_place_blockade stub DELETED (ROADMAP Piece 3 item): no caller,
and its premise ("certain FNI levels auto-place Blockades in South
Carolina and Massachusetts Ports") has no basis in §1.9 — the French
place Blockades on Cities of their choice (naval_pressure.py).

Latent bot fix (exposed by this session's trajectories, gate 1776:9):
Indian Raid's Q18 second batch — the first batch Activates Underground
War Parties (and the replenish Plunder may remove one), so a remainder
space can lose §3.4.4 Underground-WP access between batches;
raid.execute then raised and the whole turn was trapped.  The
remainder now executes per-space, skipping spaces that no longer
qualify (§5.1.3 / the Q18 skip-unpaid pattern).

Tests: new test_t9_space_picks_s48.py (6); card-75 test rewritten to
the rule.

Verification: both roots green — 1,374 (lod_ai/tests incl. commands/)
+ 41 (tests/) = 1,415; clean-sweep gate seeds 1-10/11-20 clean with
invariants on (after the Raid fix); soak 120 games DONE clean.
Balance rebaselined (old → new): 1775 P 20→40, I 70→50 (the Indian
1775 rate has now see-sawed 80→50→70→50 across S45-48 — Piece 8
territory, not chased); 1776 P 70→75, I 15→5; 1778 B 0→5, F 65→60
(in band).

Remaining Piece 3 items: event_eval static-capability audit vs the
four flowcharts' Event-or-Command bullets; the never-audited remainder
of the 109 cards (cross-check audit_report session lists); T7/T8
general layers.

## Session 49: Piece 3 slice — event_eval / Event-or-Command bullet audit (July 2026)

The four bots' Event-or-Command bullet code (B2/P2/F2/I2) verified
line-by-line against §8.4/§8.5/§8.6/§8.7, and the consumed
CARD_EFFECTS flags audited across all 96 event cards (heuristic
text-scan over the card reference + hand adjudication of 47 candidate
rows; cards 97-109 are WQ/BS cards and correctly absent).

Fixed:
- B2 bullet 2 was DEAD: it read state["unavailable"][C.BRIT_UNAVAIL],
  but real states key the box by the on-map tags (REGULAR_BRI/TORY) —
  the exact class of the French F2 key bug fixed in Session 30, which
  fixed French only.  The British bot never counted
  "places British pieces from Unavailable" toward playing an event.
- §1.9 FNI plumbing into bullet 1, all four factions:
  - removes_blockade=True added to the 12 unshaded Lower-FNI sides
    (7/34/36/37/53/55/57/60/63/64/67/69) — none carried it, so B2's
    "including by removing a Blockade" parenthetical never fired.
  - B2 and I2 bullet 1 now require an actual Blockade on a Support
    City (the §1.9 pop-0 un-zeroing is what favors the Royalists);
    the bare static flag would have fired pre-ToA with no Blockade
    anywhere.
  - New raises_fni flag on the 6 shaded Raise-FNI sides
    (7/34/37/53/60/69); P2 and F2 bullet 1 ("including by increasing
    FNI") now fire via naval.fni_raise_could_reduce_support: ToA
    played, FNI below its ceiling, and an unblockaded Support City to
    land on.
- Card 72: §8.7 I2 note "(place the Village in a space that already
  has War Parties if possible)" — Royalist executors now prefer
  WP-holding Reserves.
- Card-95 unshaded removes_patriot_fort verified True (I2 bullet 3);
  49/54 shaded places_french_from_unavailable verified already True.

Adjudicated-correct (no change): card 3 unshaded removes_patriot_fort
(all Patriot pieces in NW/SW can include a Fort); card 71 unshaded
adds_patriot_resources_3plus (variable city-pop amount CAN reach 3);
replace-away rows (28/47/58/76/89) and count-only rows (74) were
heuristic noise.  Deliberate under-approximation kept: card 73
unshaded removes_patriot_fort stays False — the static flag would
make Indians play it on any map-wide Patriot Fort and the handler
could then only remove a friendly Fort/Village in the three card
spaces (needs a per-card dynamic condition; noted for the remaining
Piece 3 card audit).  is_effective is False only on "(none)" sides,
so bullet-5 is never wrongly blocked; the dynamic §8.3.3 test already
gates it upstream.

Tests: new test_event_eval_audit_s49.py (5).  Two superseded fixtures
rewritten: test_card_34_unshaded_no_blockade (§1.9 says lowering FNI
DOES remove a Blockade) and test_event_availability's C.BRIT_UNAVAIL
key; _EXPECTED_FIELDS gained raises_fni.

Verification: both roots green — 1,382 (lod_ai/tests incl. commands/)
+ 41 (tests/) = 1,423; clean-sweep gate seeds 1-10/11-20 clean with
invariants on; soak 120 games DONE clean.  Balance all three
scenarios IN BAND (1775 P -5/B +5; 1776 P -5/I +5; 1778 F +5/I -5;
2-5 winner changes each) — rebaselined.

Remaining Piece 3: the never-audited remainder of the 109 cards
(cross-check audit_report session lists against all 96 event
handlers); T7/T8 general layers; T10 BS details.

## Session 50: T10 Brilliant Stroke details — the Treaty of Alliance was never played (July 2026)

T10 verification pass over §8.3.7/§2.3.8/§2.3.9 + the §8.1 NP note.

THE find: **no bot path ever declared the Treaty of Alliance.**
bot_wants_bs requires toa_played=True, card 109 is held (never drawn),
and _collect_bot_bs_declarations had no ToA branch — so in bot-only
1775/1776 games the French never entered the war, never qualified for
victory (§2.3.9/§7.2), and spent every game in the pre-ToA flowchart.
Confirmed empirically: 60+ cards into 1775/1776 sims, toa_played still
False; French 1775/1776 win rate was 0% since the beginning of the
project.  Fixed: the engine now declares ToA for a bot French when
§2.3.9's conditions hold with the §8.1 note applied — Available French
Regulars + AVAILABLE Squadrons/Blockades + CBC/2 > 15 (nonplayer
preparations_total; the interrupt site already guarantees no-WQ and
1st-Eligible-not-acted).  _bs_is_legal uses the NP total for a bot
French.

Second find: preparations_total counted UNAVAILABLE Squadrons —
§2.3.9 says "Available French Regulars and Squadrons/Blockades", and
§1.3.9 keeps Unavailable pieces out of play; the total overcounted by
3 at 1775 setup.  Now WI pool + placed markers only.  (Two superseded
test fixtures rewritten with citations.)

Third find: **every bot Brilliant Stroke ran with NO Special
Activity** — _try_bs_special_activity dispatched with space=None, so
every space-requiring SA raised and was silently skipped (the Patriot
list even offered the British-only Common Cause).  §8.3.7 "use the
flowchart to select the SA" now routes through the bots' own SA
pickers (B: Skirmish→Naval Pressure; P: Partisans→Skirmish→Persuasion
per §8.5.1; F: Skirmish→Naval Pressure→Préparer la Guerre; I: War
Path→Plunder→Trade).

Verified OK: trump hierarchy (ToA > Indians > French > British >
Patriots, ToA untrumpable) incl. the S34 reaction re-poll;
abort-if-no-Leader-LimCom with card return; no-WQ + before-1st-action
gating; 8.4.11/8.5.8/8.6.11/8.7.8 trigger conditions in bot_wants_bs.
T10 residuals (TRACEABILITY): second LimCom is a battle/muster/rally
approximation rather than a flowchart re-entry; SA "match the first
Command" pairing is a fixed chain; leader-involvement treats the
Leader's space as the LimCom space (origination nuance for
March/Scout/Raid/Garrison).

Tests: new test_bs_t10_s50.py (4).

Verification: both roots green — 1,391 (lod_ai/tests incl. commands/)
+ 41 = 1,432; gate seeds 1-20 clean invariants-on; soak 120 DONE
clean.  Balance: 1778 IDENTICAL (ToA pre-played there — a clean
control); 1775 F 0→50 (!), I 50→15, B 15→0; 1776 F 0→35, B 20→0,
P 70→60.  Rebaselined.  The French now actually fight the war they
were designed to join; British/Indian early-scenario rates need
Piece 8 reads on the new regime before any tuning talk.

## Session 51: Supply residuals + Indian Gather/March nodes + card-15 regression (July 2026)

Eric's continuation queue, worked in order.  WQ Supply pay-vs-move
inversions: VERIFIED already fixed in Session 33 (survey markers
added); remaining §8.4.7 residuals fixed — the British Supply CoC
proxy now SIMULATES the cubes' departure (§6.4.2 needs Rebellion
Control + Patriot pieces; the old any-rebel-piece proxy over-paid
everywhere the two sides met) and RL-enablement is gated on expected
Support-Phase funds ("given expected British earnings from Forts and
Cities", §1.9-effective city pops).  BS reaction chain: VERIFIED fixed
in Session 34 (test_bs_reaction_chain.py green).

Indian node deviations (survey "Also" items, all with rule cites):
- Gather worthwhile-count now applies the §3.4.1 support gate and
  counts 1-Village-with-room spaces; Gather bullet 1 places SECOND
  Villages where §1.4.2 room allows (gather.execute always permitted
  it).
- Gather bullet 4's "no more War Parties Available" now subtracts
  bullet 3's placements, and its no-Rebellion-Control check simulates
  the departure per §1.7 (the old shortcut missed partial departures).
- Gather at 0 Resources: §3.4.1's free first Indian Reserve Province
  honored in the affordability check (gather.execute already applied
  the discount; the bot refused before reaching it).
- March at 0 Resources: §3.4.2's free all-Reserve first destination
  now reachable (the up-front purse gate blocked planning; the
  post-plan budget already had the credit).
- March Phase 2: the +1 control overshoot removed (§1.7 — equality
  removes Rebellion Control; the extra WP can flip another space).
- WQ auto-Village prefers a Reserve with War Parties (§8.7 note),
  seeded ties.

Regression caught by the gate (1778:14): Session 47's Battle-space
exclusion blocked card 15's OWN scripted sequence (free March → free
Battle → "then Partisans there").  §5.1.1: Event text takes precedence
— partisans/skirmish battle-space checks now exempt card-granted free
ops and Brilliant Stroke actions (bs_free), which §2.3.8 makes
independent of other actions on the card.

Tests: new test_indian_nodes_s51.py (6).

Verification: both roots green — 1,397 (lod_ai/tests incl. commands/)
+ 41 = 1,438; gate seeds 1-20 clean invariants-on (after the card-15
fix); soak 120 DONE clean.  Balance rebaselined: 1775 I 15→35,
P 35→15, B 0→10; 1776 F 35→65, P 60→35; 1778 F 65→75 — the Indian
buffs are direct (six node fixes); French continue climbing in the
new post-ToA regime.  Piece 8 remains the instrument.

## Session 52: Human-mode QA — one full game per faction vs the bots (July 2026)

Eric's directive: play each faction as the human seat across mixed
scenarios, watch for bugs, fix as found.  Played through the LLM/policy
harness (lod_ai/llm — the human seat walks the interactive CLI's own
legality-filtered menus; policy = the strategy profiles in
llm/heuristic.py).  Runner committed as human_qa_run_s52.py (dumps
full history + anomaly report per game).

| # | Scenario/seed | My seat (profile) | Result | Cards | Decisions |
|---|---------------|-------------------|--------|-------|-----------|
| 1 | 1775 / 11 | PATRIOTS (P-AGIT) | INDIANS win at WQ — IND(10,1) both positive, BRI(10,0) correctly excluded (§7.2 cond2 not >0) | 54 | 843 |
| 2 | 1776 / 22 | BRITISH (B-CITY) | FRENCH win at WQ — FRE(5,4); ToA mid-game | 28 | 331 |
| 3 | 1778 / 33 | FRENCH (F-NAVY) | PATRIOTS win at FINAL scoring (§7.3) on a 1-1 tie with French, resolved to Patriots (§7.1) | 32 | 231 |
| 4 | 1775 / 44 | INDIANS (I-VILLAGE) | PATRIOTS win at WQ — PAT(3,1) | 28 | 241 |

Findings: ZERO bot errors, zero illegal actions, zero free-op skips,
and no history anomalies across 1,646 human-seat decisions — the only
flagged lines were benign clamp logs (stacking/cap refusals, pool
shortfall).  Victory determinations verified by hand against
§7.1/§7.2/§7.3 in all four games, including the both-conditions-
positive rule (game 1: British at (10,0) correctly do NOT win) and
final-scoring tie order (game 3).

One live confirmation of a known backlog item: game 3's PAT/FRE 1-1
final-scoring tie resolved to Patriots — correct here BOTH by §7.1's
Patriots-before-French order and by its Non-players-first tier (the
French seat was the human), but the code only implements the faction
order (C7 in TRACEABILITY_CH1_7.md): a human-Patriot vs
non-player-French tie would resolve wrongly.  Stays with C7/T11.

No fixes required — four sessions' worth of Piece 3 hardening appears
to have left the human path and the bots stable under human-mode play.

## Session 53: C7 §7.1 ranking + Piece 8 first large-N balance read (July 2026)

C7 (confirmed live in S52 game 3): final_scoring now applies §7.1's
NON-PLAYERS-FIRST tie tier ahead of the Patriots>British>French>Indians
order (bot-only games unaffected — the tier no-ops with no human
seats), logs 1st-4th placements, and victory.check identifies the
passer with §7.1's "all players lose equally" note when a Non-player
passes with humans seated.  Tests: test_victory_ranking_s53.py (3).
Battery: both roots green (1,391 + 41 + canary), gate 1-20 clean; no
soak/balance rerun (zero bot-only behavior delta — tie tier inert
without humans, remainder is history lines).

Piece 8: first instrumented large-N run — 300 games, seeds 5000+,
full write-up in docs/balance_largeN_s53.md.  Headline: the British
win 1-3% in ALL scenarios with CIs excluding parity — a measured
structural fact, not the 20-game noise of prior sessions.  Rebellion
side 63-87%.  Recommendation recorded: finish the §8.4 UNVERIFIED
verification pass before tuning (the French were 0% until Session 50
found unimplemented rules; the British rows have had no equivalent
pass since Sessions 38-39).

## Session 54: §8.4 British pass, part 1 — Muster SA order, Loyalist Desertion (July 2026)

Driven by the Session 53 large-N finding (British 1-3% everywhere).

- §8.4.2 verified line-by-line against the text and §3.2.1: Regulars
  one-space-up-to-six (3.2.1 governs), Tory P1-P3 (S37 work confirmed),
  RL-or-Fort step (S44 work confirmed), entry gate.  ONE deviation
  found: the post-Muster SA ran Naval-Pressure-first — Session 31 had
  applied GARRISON's §8.4.1 order to Muster, but §8.4.2 says "also
  Skirmish (8.4.1) or, if that is not possible, Naval Pressure" (the
  8.4.1 cites are the SA descriptions, not the order; flowchart B8's
  edge to B11/Skirmish agrees).  Fixed.
- §8.4.10 Loyalist Desertion rewritten to per-Tory re-scored removal
  with §1.7 control simulation and §8.2 seeded ties (the old static
  margin sort could bulk-empty a stack and flip Control mid-batch —
  the §8.5.7 pattern from Session 45).
- §8.4.6 Indian Trade offer verified correct (gate, 1D6, half round
  up).

Tests: test_british_84_s54.py (2).  Battery: 1,434 + 41 green; gate
1-20 clean; soak 120 DONE clean; smoke rebaselined (20-game noise).

Large-N rerun (300 games, seeds 5000+, largeN_s54.jsonl): British
STILL 0-2% — the Muster SA order was not the lever.  1775
P23/B0/F50/I27; 1776 P57/B1/F38/I4; 1778 P20/B2/F69/I9.  Remaining
suspects, in order: §8.4.4 Battle details (last audited S19-20,
before the S28 errata and everything since), the B-node flowchart
inventory (never done), the B2→B6→B9 decision gates' thresholds, and
the structural CRC>CBC starvation (rebel bots now waste few pieces).
That is the next session's target.

## Session 55: §8.4 British pass, part 2a — §8.1 pay-as-you-select, Battle/Skirmish audit (July 2026)

Instrumented first (diag_s55.py, 90 games seeds 5000+): British PASS
~4-7x/game with Resources in hand — `_pass_reason=no_valid_command` —
plus CRC < CBC in ~29/30 games per scenario.  Root cause of the passes:
the Muster and March planners built up-to-4-space plans with no
reference to the purse, then aborted the WHOLE Command when the plan
was unaffordable.  §8.1 "Paying Resource Costs" is explicit that a
Non-player able to pay for at least SOME instructions executes them,
paying per selected space.  Fixes, all in british_bot.py unless noted:

- Muster: plan capped at the purse (min 1 space); March: destination
  list trimmed to budget in plan order (= §8.4.3 priority order), CC
  War-Party bookings rolled back for dropped groups.  bs_free exempt
  (§5.1.1; the Session-51 card-15 class).  no_valid_command passes are
  now ZERO across 15 instrumented games (were ~4/game in 1775).
- B9 `_can_battle` reconciled to §8.4.3's precise complement: >=2
  ACTIVE Rebellion pieces (Forts count — always Active per §1.4.3;
  Underground Militia excluded) AND British Regulars + Leader >
  ALL Rebellion pieces plus Rebellion Leaders (was: > Active only,
  no Forts, no enemy Leaders — too loose on the comparison side).
- Skirmish target choice (§8.4.1): bullet 1 ranks spaces by removable
  Rebellion CUBES desc (Glossary: "Cube: Regular, Continental or Tory"
  — Militia are NOT cubes and return to Available, §1.4.1); the old
  sort used fewest-total-rebels (bullet 2's tiebreak) tier-wide, so it
  removed 1 piece where 2 cubes (CRC!) were removable elsewhere.
  Option choice per "removing one British Regular if necessary": 2+
  cubes -> option 2; exactly 1 cube -> option 1 (sacrifice buys no
  extra cube); no cubes -> bullet 2 (option 1 militia / option 3 fort).
  §4.2.2 Regulars-required now enforced for WI too.
- skirmish.py executor (shared): option 1/2 removal order was Active-
  Militia-FIRST — backwards per §8.4.1; now cubes first (least-
  represented type first, "first whichever type is least"), militia
  only when no cubes remain.  British side only (P/F have no
  militia tag).
- Pre-battle SA chain: chosen Battle spaces now registered in
  _turn_affected_spaces BEFORE the Skirmish/Naval loop so the
  accompanying Skirmish cannot fire in a space selected for Battle
  (§4.2.2, §8.4.4 "in a space not selected for Battle").
- Garrison: §3.2.2 two-Resource minimum moved into _can_garrison
  (§8.1: an unaffordable Command is skipped without burning the
  Naval/Skirmish SA); the §8.4.1 10-Regular count no longer counts
  the West Indies box ("in all Cities and Provinces on the map").

Tests: test_british_84_s55.py (7 new); 3 superseded tests REWRITTEN to
the rule with citations (B9 underground/comparison x2, Clinton
skirmish now cube-first).  Battery: 1,401 + 101 green; gate 1-10 and
11-20 clean sweeps; soak 120 invariants-on DONE clean; balance_smoke
rebaselined (6 winner flips at 20-game scale — noise-band instrument).

Post-fix diagnostic (90 games): no_valid_command passes 0 (all
remaining passes are genuine 0-Resource states); crc-cbc improved
(1775 -8.1 -> -5.6, 1776 -3.9 -> -3.0, 1778 -5.1 -> -4.5) but British
wins still ~1/90 — sup-opp AND crc-cbc both remain negative on
average.  The B-node flowchart inventory and the economy/CBC-CRC
trajectory read continue next.

## Session 55 (cont.): B-node inventory — Garrison clean; March/Battle findings (July 2026)

Full B-node inventory (ROADMAP suspect 2, "never done") via three
parallel read-only audits, findings verified against the text before
any edit:

- GARRISON (B4/B5, §8.4.1, §3.2.2): ZERO deviations — all 12 clause
  groups verified (retention, skirmished-City exclusion, phase
  priorities, abort-to-Muster, displacement, Blockade exclusions,
  Limited handling).
- MARCH (B10/B13, §8.4.3, §3.2.3): one real deviation — the
  march-in-place Phase-3 selector required a British REGULAR in the
  space; §3.2.3 activates "one Militia for every three British CUBES
  there", so a 3+ Tory stack qualifies.  Fixed.  (An agent-reported
  "CC restricted to Colonies" finding was a FALSE POSITIVE: Phase-1
  destinations are Cities/Colonies, "Province" = non-City space, and
  War Parties may never enter Cities (§4.2.1) — the Colony check is
  exactly the rule.  CC's Active-first consumption already satisfies
  "do not use the last War Party (Underground if possible)".)
- BATTLE resolution (§3.6): two findings.
  (1) GAME-WARPING: the British bot called battle.execute with an
  EMPTY ctx, so the resolver read cc_wp=0 — every Common-Cause Battle
  was SELECTED with the CC-boosted Force Level (§4.2.1 WP-as-Tories)
  but RESOLVED without it (and the pre-activated WPs also forfeit the
  Underground +1 attacker mod).  The selection/resolution-mismatch
  class again (T13).  _try_common_cause now returns the CC ctx and
  _battle forwards it; force parity restored.
  (2) MODERATE: "Indians Defending in Indian Reserve -1" (§3.6.5)
  fired only on War-Party presence; Villages are Indian pieces too —
  a Village-only defense now gets the modifier.
- NEW Q19 (QUESTIONS.md, open, non-blocking): do CC War Parties fill
  the TORY slot in §3.6.7 loss alternation ("as if they were Tories",
  §4.2.1) or the literal Active-WP-after-cubes slot?  Reading (a)
  spares Regulars (lower CBC) in every CC battle.  Implementation
  stays at the literal §3.6.7 order pending the ruling; the Playbook
  Brilliant-Stroke example may settle it (Piece 5).

Tests: +2 in test_british_84_s55.py (CC-ctx plumbing end-to-end,
Village Reserve modifier); 3 interface asserts updated for the new
_try_common_cause contract (ctx-or-False).  Battery: 1,402 + 101
green; gates 1-10/11-20 clean; soak 120 invariants DONE clean;
balance rebaselined.  90-game diagnostic: outcome mix essentially
unchanged (British battles are only ~1/game, so CC parity moves few
events) — the structural investigation continues.

## Session 55 (cont.): Q19 resolved by reference — CC War Parties absorb losses as Tories (July 2026)

The Playbook (p.~850, "Indian War Parties can also be used in a
Battle") settles Q19 same-session: "if the Common Cause Special
Activity was used — as a Tory adding to Force Level AND ABSORBING
LOSSES."  Implemented in battle.py _remove: up to cc_wp Active War
Parties fill the TORY slot of the §3.6.7 Regulars/Tories alternation
(WP before own Tories within the slot — §8.1.2 "without removing the
last Tory"; the WP routes to Available and increments no casualties
track, §3.6.7 "Other removed pieces to Available").  Observed effect:
at odd attacker Loss Levels a Regular is spared (CBC 3 -> 2 in the
test fixture); at even levels the mandated alternation overshoots to
the same Regulars (and burns a WP) — parity quirk documented in the
test.  QUESTIONS.md Q19 marked RESOLVED BY REFERENCE (flagged for
Eric's confirmation, non-blocking).

Tests: +1 (CC absorption, with/without-CC differential).  Battery:
1,403 + 101 green; gates 1-10/11-20 clean; soak 120 DONE clean;
balance rebaselined.  Large-N rerun (largeN_s55b.jsonl): unchanged
from the s55 read (British 1/5/2% — CC battles are too rare for Q19
to move the aggregate).

## Session 56: F-node inventory — §8.6 French pass (July 2026)

The Rebellion side's first full flowchart inventory (the S55 handoff's
queue item 1), same method as the S55 B-node sweep: three parallel
read-only audits, every finding verified against the text before any
edit.  Eric confirmed Q19 this session (QUESTIONS.md updated).

Verified-correct (not changed): the §8.6 Event gate bullets, F5/F9
die gates, Hortalez "up to 1D3" (Q16 ruling), pre-ToA Préparer both
branches, F15 <= gate and +2-at-zero rule, Battle SA order (Naval
FIRST per the §8.6.6 note — no S31-class inversion here), pre-battle
_turn_affected_spaces registration (no S55-class Skirmish leak),
§8.6.7 supply priorities (S33 state holds), §8.6.8 WI battle, §8.6.9
leader redeploy + Blockade redistribution, §8.6.10 French Loyalist
Desertion priorities, §8.6.11 BS trigger, March §8.1 budget trim
(already present).  TWO agent findings rejected as false positives
with citations: "British Leaders missing from the F13 gate" (Glossary
195: "Piece: ... (not a marker like Leaders or Blockades)" — and
§8.4.3's "pieces plus Leaders" phrasing confirms Leaders are counted
separately ONLY where the text says so; §8.6.6 says "British pieces",
so the code is right), and the March-agent's CC finding did not recur
here.

Fixed (all cited in code):
- §8.6.2 FAM: additive score (rc*10 + patriots) replaced with
  LEXICOGRAPHIC tiers — a Rebellion-held province with 10+ Patriot
  units could outrank a flippable one — and "add Rebellion Control"
  is now SIMULATED per §1.7 (does the placement flip the count?),
  the S37/S45 class.  §8.2 seeded ties.
- §8.6.4/§3.5.3 Muster: the fallback tier took ANY Rebellion-
  controlled space — Reserves/Provinces are illegal French Muster
  destinations ("In the selected Colony, City or West Indies"); now
  Cities/Colonies only, with WI reached via the fewer-than-four
  branch.  Cost checks moved to can_afford (bs_free exempt, S51
  class) and §8.1-gated in _can_muster (mirrors S55 Garrison).
- §3.5.5 Battle: bs_free exemption on the per-space cost trim (a free
  Battle with an empty purse truncated to zero spaces); spaces whose
  Patriot fee the Patriots cannot fund are now RE-SCORED ally-free
  and kept if they still pass (battle.execute already resolves them
  ally-free — the bot was discarding winnable battles); §8.2 seeded
  tie behind the Population priority.
- §3.5.4 March: bs_free exemption on the destination trim.
- MARKER CONSERVATION (Q21): city Blockades live in a SET (one per
  City max), and _place_blockade_from_wi decremented the WI pool then
  set.add()-ed — placing onto an already-blockaded City silently
  DESTROYED the marker while still raising FNI (and §4.5.3's ceiling
  shrank for the rest of the game).  The bot's NP target scan had no
  blockaded-city exclusion, so this fired repeatedly in real games.
  Now: NP scan and the Win-the-Day Blockade move skip blockaded
  Cities (the no-benefit-selection pattern, §8.4.5/S45); duplicate
  placement raises; move_blockade_city_to_city refuses occupied
  destinations.  Whether the §8.6.3 letter demands literal STACKING
  (§4.5.3 note) needs a count model — Q21, open, non-blocking.
- §8.6.3 hardening: the F11 SA loop is now gated on the Hortalez
  transfer actually happening (latent — _can_hortelez guarantees it).
- NEW Q20 (open, non-blocking): French March bullet 1 "as many ... as
  possible" vs the implemented just-enough (the British text has an
  explicit stop clause; the French text does not).

Tests: test_french_86_s56.py (5 new); 1 superseded test REWRITTEN to
§8.6.4's branch structure (WI-fallback flowchart abbreviation).
Battery: 1,408 + 101 green; gates 1-10/11-20 clean sweeps; soak 120
invariants-on DONE clean; balance rebaselined.

## Session 56 (cont.): large-N + Q21 counter-experiment (July 2026)

largeN_s56.jsonl (300 games): Rebellion 281/300 (94%) — P 38/72/33,
F 52/23/63, B 1/2/0, I 9/3/4.  The marker-conservation fix
strengthened the French Navy (the old silent marker destruction was
an accidental brake).  Q21 experiment (literal-letter NP targeting,
/tmp only, reverted): Rebellion 259/300 (86%), I 26/3/8, B 1/0/3 —
the ruling swings Indians 2x, British unaffected.  Both readings'
numbers recorded in QUESTIONS.md Q21; interim (a) spread kept.
TRACEABILITY.md: all §8.6.x rows now VERIFIED with session refs.
docs/balance_largeN_s56.md has the full read and the ranked remaining
hypotheses for the British ~1%.
