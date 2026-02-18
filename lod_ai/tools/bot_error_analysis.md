# Bot Error Analysis: 1775 Scenario, Seed=1

## Executive Summary

A single zero-player game (1775, seed=1) was run with enhanced exception
logging in `engine.py play_turn()`. Every exception that caused a bot to
pass was captured with full traceback.

**59 total bot errors** were recorded:
- **BRITISH: 31 errors** (out of 39 eligible turns = 79% error rate)
- **INDIANS: 27 errors** (out of 37 eligible turns = 73% error rate)
- **PATRIOTS: 1 error** (out of 26 eligible turns = 4% error rate)
- **FRENCH: 0 errors** (out of 24 eligible turns = 0% error rate)

These errors directly translate to forced passes via `bot_error`, which is
the primary cause of Patriot dominance in zero-player games.

---

## Error Classification

All 59 errors are `ValueError` exceptions. They fall into **5 distinct
categories** ranked by frequency:

| # | Error Message | Count | Faction(s) | % of Total |
|---|-------------|-------|-----------|-----------|
| 1 | Quebec not within Raid move range of New_York | 25 | INDIANS=25 | 42% |
| 2 | Reward Loyalty requires >=1 British Regular and >=1 Tory in space | 13 | BRITISH=13 | 22% |
| 3 | Escorts required to move Tories or War Parties | 10 | BRITISH=10 | 17% |
| 4 | British must Control the space to Reward Loyalty | 6 | BRITISH=6 | 10% |
| 5 | not enough values to unpack (expected 2, got 0) | 2 | BRITISH=1, INDIANS=1 | 3% |
| 6 | {FACTION} cannot afford {N} Resources | 3 | BRITISH=1, INDIANS=1, PATRIOTS=1 | 5% |

---

## Detailed Analysis Per Error

### Error #1: Indian Raid Invalid Move Plan (25 occurrences, 42% of all errors)

**Message:** `Quebec not within Raid move range of New_York.`

**Call chain:**
```
indians.py:131  _follow_flowchart  ->  _raid_sequence
indians.py:159  _raid_sequence     ->  _raid
indians.py:336  _raid              ->  raid.execute(...)
raid.py:129     execute            ->  raises ValueError
```

**Cards affected:** 7, 12, 20, 26, 34, 37, 39, 40, 43, 46, 47, 51, 53, 57,
60, 66, 67, 69, 74, 75, 77, 79, 85, 92, 93

**Root cause:** The Indian bot's `_raid()` method builds move plans where
War Parties are pulled from a source space to a target. It uses
`_reserve_source(target)` which:

1. First checks adjacent spaces for Underground War Parties (correct).
2. Falls back to Dragging Canoe's location if within 2 moves (problematic).

The fallback to Dragging Canoe does not properly track exhaustion of
Dragging Canoe's War Party pool across multiple moves in the same plan.
The bot decrements `available_wp[dc_loc]` but continues to return
`dc_loc` as a valid source even after the leader's WP are exhausted.
Meanwhile, `raid.py` validates `dc_pool > dc_used` (strict inequality)
and rejects moves that exceed the pool.

Additionally, the error message itself (`Quebec not within Raid move
range of New_York`) shows the bot is constructing move plans where
the source (New_York) is not adjacent to the destination (Quebec),
relying on Dragging Canoe's extended range. But when the extended-range
validation fails in `raid.py`, the move is rejected.

**Impact assessment:** This is the single largest source of Indian bot
failures. It causes the Indian bot to pass on nearly every turn when the
I3 support test fails (which routes to the Raid branch). Since
I3 fails often (Opposition tends to exceed Support+D6), the Raid path
is the most common flowchart branch, and it fails almost every time.

**Representative traceback:**
```
File "bots/indians.py", line 131, in _follow_flowchart
    if self._raid_sequence(state):    # I4 -> I5
File "bots/indians.py", line 159, in _raid_sequence
    if not self._raid(state):
File "bots/indians.py", line 336, in _raid
    raid.execute(state, C.INDIANS, {}, selected, move_plan=move_plan)
File "commands/raid.py", line 129, in execute
    raise ValueError(f"{src} not within Raid move range of {dst}.")
```

---

### Error #2: Muster Reward Loyalty -- Missing Pieces (13 occurrences, 22%)

**Message:** `Reward Loyalty requires >=1 British Regular and >=1 Tory in space.`

**Call chain:**
```
british_bot.py:304  _follow_flowchart  ->  _muster
british_bot.py:935  _muster            ->  muster.execute(...)
muster.py:261       execute            ->  _reward_loyalty
muster.py:125       _reward_loyalty    ->  raises ValueError
```

**Cards affected:** 8, 17, 20, 37, 40, 48, 53, 67, 75, 82, 85, 92, 93

**Root cause:** The British bot's `_muster()` method selects a Reward
Loyalty target at `british_bot.py:881-890` by filtering spaces with:
- Support below Active Support
- British Control
- >=1 British Regular
- >=1 Tory

This filtering is done against the PRE-muster state. However, the muster
execution in `muster.py` processes Regular placement, then Tory placement,
then Reward Loyalty **sequentially**. Between target selection and RL
execution, pieces may have been removed (e.g., by other muster actions
altering the board) or the state check was done on a stale snapshot.

More critically, the bot passes `reward_levels` to `muster.execute()`
targeting spaces where the current piece state at execution time no
longer satisfies the constraint. The bot picks the RL target early in
`_muster()` but the actual execution happens later, and the space may
have lost its Regular or Tory by that point.

**Impact assessment:** This is the second most common British bot error.
13 of the British bot's 31 errors (42%) are this specific validation
failure. Every time the Muster path is reached in the flowchart and
the bot wants to Reward Loyalty, there's a high chance it picks an
invalid target.

**Representative traceback:**
```
File "bots/british_bot.py", line 304, in _follow_flowchart
    if self._muster(state, tried_march=tried_march):
File "bots/british_bot.py", line 935, in _muster
    did_something = muster.execute(...)
File "commands/muster.py", line 261, in execute
    _reward_loyalty(state, state["spaces"][target], target, reward_levels, ...)
File "commands/muster.py", line 125, in _reward_loyalty
    raise ValueError("Reward Loyalty requires >=1 British Regular and >=1 Tory in space.")
```

---

### Error #3: March Without Escorts (10 occurrences, 17%)

**Message:** `Escorts required to move Tories or War Parties.`

**Call chain:**
```
british_bot.py:304   _follow_flowchart  ->  _muster
british_bot.py:950   _muster            ->  _march (fallback)
british_bot.py:1201  _march             ->  march.execute(...)
march.py:303         execute            ->  _apply_move
march.py:169         _apply_move        ->  raises ValueError
```

**Cards affected:** 26, 34, 45, 52, 57, 65, 72, 77, 79, 96

**Root cause:** The British bot's `_march()` method constructs move plans
that include Tories in the pieces dict (`british_bot.py:1105-1114`):

```python
if movable.get(C.TORY, 0) > 0:
    pieces[C.TORY] = movable[C.TORY]
```

But the march execution call at `british_bot.py:1201` **hardcodes
`bring_escorts=False`**:

```python
march.execute(
    state, C.BRITISH, march_ctx,
    all_srcs, all_dsts,
    plan=move_plan[:4],
    bring_escorts=False,   # <-- ALWAYS FALSE
    limited=False,
)
```

Per the game rules (Manual Ch 3): "Tories may only accompany British
Regulars 1 for 1." The `march.py` validation at line 169 enforces this:
if Tories are in the move plan but `bring_escorts=False`, the move is
rejected.

**Impact assessment:** This error occurs every time the bot's March
fallback path (from Muster) tries to move Tories. Since the bot
aggressively includes all movable pieces including Tories, and never
sets `bring_escorts=True`, any march involving Tories fails.

**Representative traceback:**
```
File "bots/british_bot.py", line 1201, in _march
    march.execute(...)
File "commands/march.py", line 303, in execute
    info = _apply_move(entry["src"], entry["dst"], entry["pieces"])
File "commands/march.py", line 169, in _apply_move
    raise ValueError("Escorts required to move Tories or War Parties.")
```

---

### Error #4: Muster Reward Loyalty -- No Control (6 occurrences, 10%)

**Message:** `British must Control the space to Reward Loyalty.`

**Call chain:**
```
british_bot.py:304  _follow_flowchart  ->  _muster
british_bot.py:935  _muster            ->  muster.execute(...)
muster.py:261       execute            ->  _reward_loyalty
muster.py:127       _reward_loyalty    ->  raises ValueError
```

**Cards affected:** 5, 12, 51, 60, 69, 74

**Root cause:** Same pattern as Error #2 but a different validation:
the bot selects a space for Reward Loyalty that had British Control
at selection time, but by the time `_reward_loyalty` executes, the
space is no longer British-Controlled. This happens because:

1. The Muster action itself can place or remove pieces that change
   control (via `refresh_control()`).
2. The bot selects the RL target based on state at the start of
   `_muster()`, not after placements are complete.

**Impact assessment:** Combined with Error #2, Reward Loyalty failures
account for 19 of the British bot's 31 errors (61%). The Muster
command is the British bot's primary action, and RL is a key part
of the British victory strategy (building Support). Its consistent
failure means the British bot almost never successfully builds Support.

---

### Error #5: Card 10 Handler Crash (2 occurrences, 3%)

**Message:** `not enough values to unpack (expected 2, got 0)`

**Call chain:**
```
base_bot.py:19      take_turn                ->  _choose_event_vs_flowchart
base_bot.py:170     _choose_event_vs_flowchart -> _is_ineffective_event
base_bot.py:242     _is_ineffective_event    ->  handler(after, shaded=shaded)
early_war.py:174    evt_010_franklin_to_france -> c1, c2 = pick_two_cities(state)
```

**Cards affected:** Card 10 only (but hits both British and Indian bots)

**Root cause:** The `_is_ineffective_event()` method in `base_bot.py`
runs card handlers speculatively on a deep copy to check if the event
would change anything. When card 10's handler (`evt_010_franklin_to_france`)
runs, it calls `pick_two_cities(state)` which looks for spaces with
`type == "City"`.

The `pick_two_cities()` function (in `cards/effects/shared.py`) checks
`info.get("type") == "City"` on each space. If spaces in the copied
state don't have a `"type"` field (because `normalize_state` or
`setup_state` stores type information differently, or the deepcopy
doesn't include map metadata), the function returns an empty list,
causing the unpacking to fail.

**Impact assessment:** Low frequency (only card 10), but it affects
all non-French bots when card 10 comes up. The error occurs during
the event-vs-flowchart decision, meaning the bot can't even evaluate
whether to play the event.

---

### Error #6: Resource Affordability (3 occurrences, 5%)

**Messages:**
- `BRITISH cannot afford 4 Resources` (1x, card 62)
- `INDIANS cannot afford 2 Resources` (1x, card 52)
- `PATRIOTS cannot afford 1 Resources` (1x, card 45)

**Call chains:**
- British: `_march -> march.execute -> _pay_cost -> resources.spend`
- Indians: `_gather -> gather.execute -> _pay_cost -> resources.spend`
- Patriots: `_execute_battle -> battle.execute -> rally.execute -> resources.spend`

**Root cause:** Each bot has a resource check early in `take_turn()`
(`base_bot.py:27`):

```python
if state["resources"][self.faction] <= 0:
    state['_pass_reason'] = 'resource_gate'
    return {"action": "pass", ...}
```

This only gates on `resources <= 0`. The bots then proceed to execute
commands that cost more than their remaining resources. The command
modules validate affordability and throw. The bots should either:
1. Check that they can afford the specific command before executing, or
2. The base resource gate should account for command costs.

**Impact assessment:** Low frequency (3 total), because the resource
gate catches the most common case (zero resources). But when a bot
has 1-3 resources and tries a command costing more, it fails.

---

## Summary: Interrelationships

The errors are NOT independent. They form two clusters:

### Cluster 1: British Muster/March Chain (29 of 31 British errors)
The British flowchart routes through `_muster()` as the primary action.
When Muster fails (Errors #2 and #4), the bot falls through to `_march()`
as a fallback. March then fails with Error #3 (escorts). This creates a
**cascading failure**: Muster fails -> March fallback fails -> entire turn
is a pass.

The flow is:
```
_follow_flowchart() -> _muster()
  -> Reward Loyalty validation fails (Error #2 or #4)
  -> Falls through to _march() at british_bot.py:950
    -> March includes Tories without escorts (Error #3)
    -> Entire turn becomes bot_error pass
```

### Cluster 2: Indian Raid Dominance (25 of 27 Indian errors)
The Indian flowchart's I3 test (Support+D6 > Opposition?) fails most
turns because Opposition exceeds Support throughout the game. When I3
fails, the bot always enters the Raid branch. Raid then fails every
time due to the Quebec/New_York move plan bug (Error #1). The bot
never reaches the Gather, March, or Scout branches as fallbacks.

---

## Recommended Fix Priority

1. **Error #1 (Indian Raid, 25x):** Fix `_reserve_source()` in
   `indians.py` to properly track Dragging Canoe WP exhaustion and
   validate move ranges before adding to the plan. This single fix
   would eliminate 42% of all errors.

2. **Error #3 (British March escorts, 10x):** Change
   `bring_escorts=False` to `bring_escorts=True` in `british_bot.py:1201`
   when the move plan includes Tories, OR filter Tories out of move
   plans when escorts aren't available. This would eliminate 17% of
   all errors.

3. **Errors #2 + #4 (British Muster RL, 19x combined):** Validate the
   Reward Loyalty target at execution time (not just selection time) by
   re-checking pieces and control in `_muster()` before calling
   `muster.execute()`. This would eliminate 32% of all errors.

4. **Error #5 (Card 10 handler, 2x):** Add a guard in
   `evt_010_franklin_to_france` to handle `pick_two_cities()` returning
   fewer than 2 results.

5. **Error #6 (Resource affordability, 3x):** Add per-command cost
   checks in the bots before executing, or catch resource errors
   gracefully and fall through to the next flowchart branch.

**Combined impact:** Fixing errors #1-#3 would eliminate 56 of 59
errors (95%), restoring both the British and Indian bots to functional
operation and likely rebalancing the zero-player game outcomes.
