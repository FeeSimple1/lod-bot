# Bot Error Analysis — Round 4

## Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **bot_errors** | 39 | 0 | **-100%** |
| **illegal_actions** | 219 | 0 | **-100%** |
| Total faction turns | ~4,545 | ~4,660 | +2.5% |
| Successful actions | ~3,477 | ~3,849 | +10.7% |
| Pass rate (overall) | ~23.5% | ~17.4% | -6.1 pp |

## Per-Faction Results (After)

| Faction | Turns | Successes | Pass Rate | Errors | Illegal |
|---------|-------|-----------|-----------|--------|---------|
| BRITISH | 1,248 | 841 | 32.6% | 0 | 0 |
| PATRIOTS | 1,148 | 995 | 13.3% | 0 | 0 |
| INDIANS | 1,162 | 967 | 16.8% | 0 | 0 |
| FRENCH | 1,102 | 1,046 | 5.1% | 0 | 0 |

## Errors Fixed

### bot_errors (39 → 0)

#### 1. British March: empty move_plan pieces (18 errors)
- **Root cause**: `british_bot._march()` Phase 1 included Common-Cause War Party counts in the total piece check (`actual_total = sum(pieces.values()) + cc_wp_count`), but the `pieces` dict itself could be empty. CC War Parties are moved by `common_cause.execute()`, not `march.execute()`, so an entry with empty pieces was passed to march which raised ValueError.
- **Fix** (`british_bot.py`): Changed the check to `if sum(pieces.values()) <= 0: continue` — skip entries where the bot has no directly-movable pieces, regardless of CC WP count.

#### 2. Patriot Rally: fort-build pre-check (16 errors)
- **Root cause**: `patriot._execute_rally()` checked fort-build eligibility (4+ Patriot units, 2+ removable) at planning time, but state could change between planning and execution within the same turn. Additionally, `_execute_battle._win_callback` for Win-the-Day free Rally also requested fort builds without checking removable unit count.
- **Fix** (`patriot.py`): Added runtime `removable >= 2` guard in both `_execute_rally` (before each `rally.execute()` call) and `_win_callback` (before requesting fort build). Falls back to `place_one` if fort build is no longer feasible.

#### 3. Battle: allied fee overflow (2 errors)
- **Root cause**: When Patriots battle in spaces with French Regulars, the allied fee (`spend(state, FRENCH, fee)`) was called without checking French affordability.
- **Fix** (`battle.py:100-105`): Cap fee at `min(fee, state["resources"].get(FRENCH, 0))` and skip if 0.

#### 4. Muster: Reward Loyalty resource shortfall (1 → 5 → 0 errors)
- **Root cause**: Bot's RL cost estimation was imprecise (marker counts, shift levels, Gage discount). The cost check in `_reward_loyalty()` ran after muster payment, so resources were already depleted.
- **Fix** (`muster.py:271-280`): Added pre-check in `muster.execute()` computing exact RL cost (`markers + shift_levels - discount`) and verifying `resources >= cost` before calling `_reward_loyalty()`. Silently skips RL if unaffordable.

#### 5. Indian Gather: move_plan destination pruning (2 errors)
- **Root cause**: When `_gather()` trimmed `selected` for affordability, the `move_plan_list` still contained entries with destinations that were no longer in `selected`.
- **Fix** (`indians.py:717-719`): Added `move_plan_list = [(s, d, n) for s, d, n in move_plan_list if d in selected_set]` after selected-list trimming.

#### 6. French March: affordability (7 errors, new in round 2)
- **Root cause**: French bot's `_march()` Step 2 built a move_plan with more destinations than the French could afford (march costs 1 resource per destination).
- **Fix** (`french.py`): Added affordability cap trimming destinations to `french_res` count. Also added resource gate before Steps 3-4. Also added affordability guard for French Muster (2 resources) and French Battle (1 per space).

#### 7. Indian WP_U movement in march (3 errors)
- **Root cause**: Indian bot's `_march()` planning snapshot tracked virtual WP arrivals at destinations (`wp_snap[target][0] += 1`). When those destinations later served as sources, the plan requested more WP_U than actually existed in the real state.
- **Fix** (`indians.py`): Added plan validation before `march.execute()` — for each (src, pieces) entry, cap each piece tag count to what actually exists in the source space, tracking cumulative draws.

#### 8. Indian Gather: WP availability after village builds (2 errors, residual)
- **Root cause**: Bullet 4's move_plan recorded source WP counts at planning time, but `gather.execute()` processes `build_village` first (removing 2 WP from spaces), reducing the actual count below what was planned.
- **Fix** (`indians.py`): Added pre-validation capping move counts against actual state minus build_village removals. Also hardened `gather.py:199-202` to cap moves to available count instead of raising ValueError.

### illegal_actions (219 → 0)

#### 1. Accumulated _turn_affected_spaces across fallback commands (189 errors)
- **Root cause**: When a bot's flowchart tried Command A (which partially modified `_turn_affected_spaces`) and then fell through to Command B, the accumulated affected spaces caused the engine's legality check to see too many affected spaces (> 1 for limited commands).
- **Fix**:
  - Added `BaseBot._reset_command_trace()` static method (`base_bot.py`) that clears `_turn_used_special`, `_turn_affected_spaces`, `_turn_command`, and `_turn_command_meta`.
  - All four bot files (`british_bot.py`, `patriot.py`, `indians.py`, `french.py`) call `_reset_command_trace()` before each fallback command attempt.
  - `british_bot._muster()` and `._march()` also reset trace before internal fallback calls between those commands.

#### 2. Indian Scout SA suppression (23 errors)
- **Root cause**: Scout's optional Skirmish called `skirmish.execute()` which set `_turn_used_special = True`. But per §3.4.3, Skirmish within Scout is part of the command, NOT a separate Special Activity.
- **Fix** (`scout.py:156-160`): Save `_turn_used_special` before skirmish call and restore it after.

#### 3. Patriot Rally/Battle limited_wrong_count (28 errors, new in round 3)
- **Root cause**: Battle's Win-the-Day callback called `rally.execute()` with a DIFFERENT space than the battle space. `rally.execute()` added this space to `_turn_affected_spaces` and overwrote `_turn_command` to "RALLY". For limited commands (1 space only), this resulted in 2 affected spaces.
- **Fix**:
  - `battle.py`: Save/restore `_turn_affected_spaces` and `_turn_command` around Win-the-Day rally calls — WTD rally is part of battle, not a separate command.
  - `patriot.py`: Changed `_win_callback` to use `battle_sid` as the rally space per §3.6.8.

#### 4. Engine: _limited/_no_special persistence across turns (contributed to above)
- **Root cause**: `engine._reset_trace_on()` didn't clear `_limited` and `_no_special` flags, so they could persist from a previous turn's sandbox.
- **Fix** (`engine.py`): Added `target_state.pop("_limited", None)` and `target_state.pop("_no_special", None)` to `_reset_trace_on()`.

## Files Modified

| File | Changes |
|------|---------|
| `lod_ai/engine.py` | Clear _limited/_no_special in _reset_trace_on |
| `lod_ai/bots/base_bot.py` | Add _reset_command_trace() static method |
| `lod_ai/bots/british_bot.py` | Trace resets in fallback chains; Phase 1 empty pieces fix; RL cost estimation |
| `lod_ai/bots/patriot.py` | Trace resets; fort build guards; WTD rally uses battle_sid |
| `lod_ai/bots/indians.py` | Trace resets; march plan validation; gather move_plan pruning + WP cap |
| `lod_ai/bots/french.py` | March/muster/battle affordability guards |
| `lod_ai/commands/battle.py` | Allied fee cap; WTD rally trace save/restore |
| `lod_ai/commands/muster.py` | RL affordability pre-check |
| `lod_ai/commands/scout.py` | SA flag save/restore around Skirmish |
| `lod_ai/commands/gather.py` | WP move count cap (defensive) |

## Test Coverage

- 949 existing tests continue to pass
- New tests added in `test_bot_error_fixes.py` covering key fixes

## Methodology

- 60 zero-player games: 3 scenarios (1775, 1776, 1778) × 20 seeds each
- Deterministic RNG per seed for reproducibility
- Full traceback capture for bot_errors, detailed logging for illegal_actions
- Multiple iteration cycles: initial run → analysis → fixes → re-run → verify
