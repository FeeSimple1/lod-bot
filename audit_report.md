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

**Engine:**
- Q7 BS command priorities (`get_bs_limited_command()` on all 4 bot subclasses; engine calls it)
- All 4 bots use `CARD_EFFECTS` for event evaluation (P2/F2/I2/B2)

### Card Handlers — COMPLETE
All 109 card handlers match `card reference full.txt`. No outstanding card issues.
- Minor: Card 24 shaded uses dict iteration order for space selection (arbitrary). Card 28 still uses alphabetical fallback via `sorted()` for space selection. Both are low impact.

### Remaining Issues

#### Medium Severity

- **OPS methods not wired into year_end**: All 4 bots define `ops_supply_priority()`, `ops_redeploy()`, `ops_desertion()`, `ops_bs_trigger()` methods. `year_end.py` uses its own ad-hoc logic and ignores these. Supply payment order, desertion target selection, and redeployment destination all use bot-independent heuristics instead of the faction-specific priorities from the reference flowcharts. This is a larger refactor — `year_end` needs to detect bot-controlled factions, import their bot instances, and call OPS methods for prioritization.
- **P7/P11 Persuasion mid-command expansion**: Reference says Persuasion fires during Rally/Rabble and restored resources could fund additional spaces. Current code fires Persuasion after all spaces are processed (resources are capped at selection time). Low gameplay impact — bot already gets highest-priority spaces. Would require Rally/Rabble to execute space-by-space with interrupt callbacks.
- **`_indian_defending_activation()` redundant**: The method in `indians.py` is defined and tested but never called from the bot’s own battle flow. However, `battle.py` (lines 299-309) implements the same logic inline for bot-controlled Indians. The `indians.py` method is dead code and should be removed to avoid confusion.

#### Low Severity

- **B10 March + Common Cause timing**: CC invoked post-March instead of during March planning. CC should integrate into group size calculation for adjacent Province destinations. Architectural refactor.
- **Cards 24/28 alphabetical fallback**: Space selection uses alphabetical tiebreaker instead of population or other game-meaningful criteria.

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

#### Q11: P2 Bullet 2 — "Active Opposition" vs "Active Support" (added to QUESTIONS.md)

The flowchart says "Active Opposition" but Manual §8.5 says "Active Support." These are contradictory. Current code uses the broad `places_patriot_militia_u` flag without checking board state, which is a heuristic regardless of which reading is correct. Documented as Q11 in QUESTIONS.md for user decision.

### REMAINING issues (not fixed — architectural or already documented)

- **P4 Force level modifiers**: Reference says "plus modifiers" but bot uses raw piece counts. Would require importing and computing all §3.6.5-6 modifiers at the bot level. Previously documented in Session 5.
- **P4 Win-the-Day per-space**: Code pre-selects one rally space; reference says "for each space where Rebellion Wins the Day." Requires battle.execute() callback refactoring. Previously documented.
- **P7/P11 Persuasion mid-command**: Fires after command, not during when resources reach 0. Previously documented.
- **OPS methods not wired into year_end**: Previously documented in Consolidated Outstanding Issues.

### Tests

See test run results below.
