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

### REMAINING issues (documented, not fixed)

#### Queued vs. immediate execution
- **Cards 12, 13**: Set `winter_flag` for Patriot/Tory Desertion instead of executing immediately. The reference says "Execute...as per Winter Quarters Round." Interpretation: the "as per" phrasing may mean "following the same procedure" while deferring to actual WQ timing. Not changed pending clarification.
- **Card 15 (Morgan's Rifles) shaded**: Uses `queue_free_op` for March/Battle/Partisans. Q3 resolution says engine drains free ops immediately after handler, so this is effectively immediate.
- **Card 94 (Herkimer) unshaded**: Militia removal executes before queued Gather/Muster. Reference order suggests Gather+Muster first, then Militia removal. Since engine drains free ops after handler, the Militia removal in the handler runs before the queued ops. Requires reordering to match reference.

#### Faction choice vs. hardcoded selection
- **Cards 66, 67**: Use `FRENCH if toa_played else PATRIOTS` for faction selection. Reference says "French or Patriots" (player choice). The TOA-gating may be intentional game design (French can only act after ToA) but restricts player choice.
- **Card 29 (Bancroft)**: Activates BOTH Patriots and Indians. Reference: "Patriots **or** Indians must Activate..." — may be a choice of one faction, or may mean both (ambiguous "or" in COIN phrasing). Left as-is pending clarification.
- **Card 48 (God Save the King) shaded**: Moves ALL non-British factions' units. Reference: "A non-British **Faction**" (singular) should move only one faction's units.

#### Minor issues
- **Card 4 (Penobscot) shaded**: Faction-dependent piece choice (Fort vs Village, Militia vs WP) not in reference text — executing player should choose freely.
- **Card 11 (Kosciuszko) shaded**: Uses `"REBELLION"` control check. "Patriot Controlled" might differ from "Rebellion Control" in edge cases involving French pieces.
- **Card 84 (Merciless Indian Savages) unshaded**: `queue_free_op` for Gather has no Colony restriction. Reference says "in two Colonies."
- **Card 87 (Lenape) unshaded**: Fixed removal priority may not match player/bot intent — reference just says "Remove one piece."

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
- **B5 Garrison**: Only targets one city instead of multi-phase operation
- **B10 March**: Only moves Regulars, never Tories; missing phases 2 and 3; Common Cause timing wrong (after March, should be during)
- **B13 Common Cause**: No flowchart-specific logic (don't use last WP in March origin, don't use last Underground WP in Battle)
- **B38 Howe capability**: FNI not lowered before SAs during Howe's leadership period

#### Patriot Bot (patriot.py)
- **P4 Battle**: Force level uses total Militia (Active+Underground) instead of Active only; Washington lookup uses wrong data structure (space_id as key in leaders dict); Win-the-Day free Rally not implemented
- **P5 March**: Missing "lose no Rebel Control" constraint, missing leave-behind logic, missing second phase
- **P7 Rally**: Missing 4 of 6 bullet points (Continental replacement, Fort Available placement, Control-changing Militia, adjacent Militia gathering); always returns True
- **P8 Partisans**: Always uses option=1, never targets Villages (option=3)
- **P12 Skirmish**: Always uses option=1, never removes Forts (option=3)
- **Event Instructions**: Cards 71, 90 say "use unshaded" but bot plays shaded; Cards 18, 44, 51 ignore conditional fallbacks

#### French Bot (french.py)
- **F13 Battle**: Only checks Washington, not all Rebel leaders (Rochambeau, Lauzun)
- **F16 Battle**: Force level missing modifiers; `crown_cubes > 0` check too narrow (should include Fort/WP-only spaces)
- **F14 March**: Missing 4 of 5 constraints/priorities (Lose no Rebel Control, include Continentals, march toward nearest British, fallback to shared space)
- **F12 Skirmish**: Only checks for `REGULAR_BRI`, not other British pieces; no affected-space filter; no Fort-first priority (always uses option=2)
- **F17 Naval Pressure**: Missing target city priority logic (Battle space first, then most Support)
- **Event Instructions**: All French cards use `"force"` — missing conditional fallbacks for cards 52, 62, 70, 73, 83, 95

#### Indian Bot (indians.py)
- **I7 Gather**: Space selection entirely missing — all 4 priority bullets unimplemented
- **I10 March**: Severely simplified — single move, missing priorities and constraints
- **I12 Scout**: No piece count calculation, no Control preservation check; never triggers Skirmish
- **I11 Trade**: Executes in up to 3 spaces; reference says Max 1

### MEDIUM SEVERITY (documented, not fixed)

#### British Bot
- B1 Garrison precondition missing FNI level 3 check
- B5 Garrison "leave 2 more Royalist" omits Forts from count
- B6 Muster precondition consumes die roll on every call
- B8 Tory placement skips Active Opposition and adjacency checks; only places 1 Tory per space
- B12 Battle misses Fort-only spaces; force level ignores modifiers
- B7 Naval Pressure missing Gage/Clinton leader check
- B2 Event conditions overly broad text matching
- B8 Fort target space not passed to muster.execute
- B10 March always passes bring_escorts=False
- B39 Gage leader capability (free RL) not implemented
- OPS reference (Supply/Redeploy/Desertion priorities) not in bot

#### Patriot Bot
- P8 Partisans WP vs British priority flattened into sum
- P2 Event conditions check shaded text only; text matching unreliable
- Rally/Rabble mutual fallback — potential infinite loop masked by always-True return
- Rally Persuasion interrupt happens after Rally, not during
- March destination doesn't verify Rebel Control would actually be gained
- March requires group size >= 3 (not in reference)
- British Tory cap applied when defending (should be uncapped)
- Rabble-Rousing arbitrarily capped at 4 spaces

#### French Bot
- F6 Hortalez "up to" 1D3 language (minor)
- F13 "British pieces" missing Forts and Villages from count
- F16 Battle doesn't enter F12 Skirmish loop afterward
- F10 Muster not filtering by Colony/City type
- Battle counts Underground Militia in force (should be Active only)
- OPS summary items not implemented (Supply, Redeploy, Desertion, ToA trigger, BS trigger)

#### Indian Bot
- I6 checks Available village count instead of whether Gather would place 2+
- I9 checks only Underground WP; reference says any WP
- Missing mid-Raid Plunder/Trade interruption when resources hit 0
- `_can_plunder` checks all map spaces, not just Raid spaces
- Trade multi-space iteration (reference says Max 1)
- Circular fallback between Gather and March — potential infinite loop
- Raid movement doesn't check "WP don't exceed Rebels" condition
- Defending in Battle activation rule not implemented
- Supply, Patriot Desertion, Redeployment priorities not in bot
- Brilliant Stroke trigger conditions not implemented
- Uses `random.random()` instead of `state["rng"]` in multiple places
