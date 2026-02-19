# Bot Error & Illegal Action Analysis: Round 3 (60-Game Batch)

## Executive Summary

60 zero-player games were run (20 per scenario: 1775, 1776, 1778) with seeds
1-20. Every bot turn was categorized, and every unhandled exception and
illegal_action was captured with full detail.

**5,849 total faction turns** across 60 games.

| Category         | Count | % of Turns | Description |
|-----------------|------:|:----------:|-------------|
| bot_error       |   888 |   15.2%    | Unhandled exception in bot code |
| illegal_action  | 1,400 |   23.9%    | Bot's action rejected by legality check |
| resource_gate   |   231 |    3.9%    | Bot had 0 resources, auto-passed |
| no_valid_command |   138 |    2.4%    | Bot tried but found no valid option |
| **Total passes** | **2,657** | **45.4%** | |
| Successful acts  | 3,192 |   54.6%   | Bot executed a command or event |

**45.4% of all bot turns result in a forced pass.** This is an improvement
from the previous round's 54.5%, primarily due to the Garrison "not a City"
fix (which eliminated 848 errors) and other fixes. However, new error
patterns have emerged as the bots now reach deeper into their flowcharts.

---

## Comparison with Previous Round

| Metric | Round 2 | Round 3 | Change |
|--------|--------:|--------:|--------|
| Total turns | 5,258 | 5,849 | +591 (more turns because fewer early crashes) |
| bot_error | 1,895 | 888 | **-1,007 (-53.1%)** |
| illegal_action | 767 | 1,400 | **+633 (+82.5%)** |
| resource_gate | 162 | 231 | +69 |
| no_valid_command | 40 | 138 | +98 |
| Total pass rate | 54.5% | 45.4% | **-9.1pp improvement** |
| Successful actions | 2,394 | 3,192 | **+798 (+33.3%)** |

The bot_error count dropped by half. However, illegal_actions nearly doubled.
This is the same "fix reveals next bug" pattern: when the bots no longer
crash on Garrison/Plunder/Gather/etc., they now complete those commands but
produce results that fail the legality check — typically because they affect
0 spaces (no-op) or the bot acts as 2nd-eligible and violates Limited Command
constraints.

---

## Per-Faction Summary

| Faction  | Total Turns | Success | Pass Rate | bot_error | illegal_action | resource_gate | no_valid |
|----------|----------:|--------:|----------:|----------:|---------------:|--------------:|---------:|
| BRITISH  |     1,687 |  463 (27.4%) |  72.6% |     820 |           243 |            34 |      127 |
| PATRIOTS |     1,467 |  832 (56.7%) |  43.3% |       8 |           554 |            71 |        2 |
| INDIANS  |     1,432 |  840 (58.7%) |  41.3% |      52 |           425 |           115 |        0 |
| FRENCH   |     1,263 | 1,057 (83.7%) |  16.3% |       8 |           178 |            11 |        9 |

The British bot is still the worst performer (72.6% pass rate), now dominated
by Garrison displacement errors. Patriots and Indians have moderate pass rates
(~42%), dominated by illegal_actions. The French bot remains the healthiest.

---

# SECTION A — Remaining bot_errors (888)

## Overview

All 888 bot_errors are `ValueError` exceptions from **5 root-cause groups**
(53 distinct error messages). The error landscape has radically simplified
compared to Round 2's 11 groups.

### Root Cause Groups

| Group | Root Cause | Count | % of bot_errors | Faction |
|------:|-----------|------:|:---------------:|---------|
| 1 | Garrison displacement: not adjacent | 719 | 81.0% | BRITISH |
| 2 | Garrison displacement: not British-controlled | 98 | 11.0% | BRITISH |
| 3 | Raid: no Underground WP to Activate | 29 | 3.3% | INDIANS |
| 4 | Scout/Battle billing bugs (wrong faction charged) | 22 | 2.5% | INDIANS, FRENCH |
| 5 | Miscellaneous (8 distinct errors) | 20 | 2.3% | Mixed |
| **Total** | | **888** | **100%** | |

**Fixing Groups 1-2 alone would eliminate 817 of 888 bot_errors (92.0%).**

---

### Group 1: Garrison Displacement Adjacency (719 errors, 81.0%)

**The single largest error source by far.** The British bot's `_garrison()`
method executes successfully (Garrison no longer crashes on "not a City"),
but when the Garrison command tries to *displace Rebellion pieces* from the
city to an adjacent Province, it selects a non-adjacent Province.

**Every city on the map** experiences this error with **every non-adjacent
Province** as a displacement target. This is not selective — the displacement
target selection logic appears to pick provinces without checking adjacency.

**Top displacement routes (by frequency):**

| City → Target | Count | Scenario |
|---------------|------:|----------|
| Boston → New_Jersey | 115 | 1778 |
| Philadelphia → Massachusetts | 106 | 1775, 1776, 1778 |
| Philadelphia → New_Hampshire | 65 | 1775, 1776 |
| Norfolk → New_Jersey | 64 | 1778 |
| Philadelphia → Georgia | 51 | 1775, 1776 |
| New_York_City → New_Hampshire | 50 | 1775, 1776 |
| Charles_Town → New_Hampshire | 35 | 1775, 1776 |
| Charles_Town → Massachusetts | 33 | 1775, 1776 |
| Boston → New_Hampshire | 31 | 1775, 1776, 1778 |
| Norfolk → Massachusetts | 20 | 1775, 1776, 1778 |
| New_York_City → Massachusetts | 20 | 1775, 1776 |
| Philadelphia → North_Carolina | 16 | 1776 |
| Norfolk → Georgia | 14 | 1775, 1776 |
| Norfolk → New_Hampshire | 12 | 1775, 1776 |

**Call chain:**
```
british_bot.py:297  _follow_flowchart  →  _can_garrison + _garrison
british_bot.py:568  _garrison          →  garrison.execute(...)
garrison.py:197     execute            →  _displace_rebellion(city, target, state)
garrison.py:85      _displace_rebellion →  raises ValueError("{city} is not adjacent to {target}")
```

**Root cause:** The `_displace_rebellion()` function in `garrison.py` picks
a displacement target for Rebellion pieces. It selects a Province but does
not verify that the Province is adjacent to the city. Per the rules, displaced
pieces move to an adjacent Province. The target selection algorithm appears
to use a different criterion (e.g., "Province with most Rebellion support")
without filtering by adjacency first.

**This is a regression from the Round 2 Garrison fix.** The "not a City"
error was eliminated, but the displacement logic that was previously masked
is now exposed as broken.

---

### Group 2: Garrison Displacement Not British-Controlled (98 errors, 11.0%)

**Message:** `Displace city must be under British Control`

**Call chain:**
```
british_bot.py:568  _garrison  →  garrison.execute(...)
garrison.py:196     execute    →  raises ValueError("Displace city must be under British Control")
```

**Root cause:** The British bot attempts Garrison at cities that are not
under British Control. The `_can_garrison()` pre-check in the bot either
doesn't check control or checks it differently than `garrison.py` validates.
Per the rules, Garrison can only be performed in cities the British control.

---

### Group 3: Indian Raid "No Underground WP" (29 errors, 3.3%)

**Message pattern:** `{Province}: no Underground WP to Activate.`

| Province | Count |
|----------|------:|
| Connecticut_Rhode_Island | 14 |
| Massachusetts | 11 |
| New_Jersey | 2 |
| New_Hampshire | 2 |

**Call chain:**
```
indians.py:159  _raid_sequence  →  _raid(state)
indians.py:392  _raid           →  raid.execute(...)
raid.py:154     execute         →  raises ValueError
```

**Root cause:** Same as Round 2 — the Indian bot's Raid target selection
doesn't filter by Underground WP availability. The count dropped from 62
to 29, suggesting partial fixes were applied but the filter is still
incomplete. The remaining cases are concentrated in New England provinces
where Indians have Active (not Underground) War Parties.

---

### Group 4: Billing Bugs — Wrong Faction Charged (22 errors, 2.5%)

Two related billing bugs:

**4a. Scout charges BRITISH instead of INDIANS (14 errors)**

| Error | Count | Faction | Scenario |
|-------|------:|---------|----------|
| BRITISH cannot afford 1 Resources | 14 | INDIANS | 1775, 1776, 1778 |

**Call chain:**
```
indians.py:1044  _scout  →  scout.execute(...)
scout.py:127     execute →  spend(state, BRITISH, 1)
resources.py:18  spend   →  raises ValueError
```

The Scout command at `scout.py:127` charges **BRITISH** for the scouting
fee when it should charge **INDIANS** (the faction executing Scout).

**4b. French Battle charges PATRIOTS instead of FRENCH (8 errors)**

**Call chain:**
```
french.py:697    _battle →  battle.execute(state, FRENCH, ...)
battle.py:106    execute →  spend(state, PATRIOTS, fee)
resources.py:18  spend   →  raises ValueError
```

Same billing bug pattern as Round 2 — `battle.py:106` charges **PATRIOTS**
when French executes Battle. Only appears in 1778 when French is most active.

---

### Group 5: Miscellaneous (20 errors, 2.3%)

| Error | Count | Faction | Scenario |
|-------|------:|---------|----------|
| Rally: need 2 units for Fort | 8 | PATRIOTS | 1778 |
| Gather: move destination not in selected | 4 | INDIANS | 1775, 1776, 1778 |
| March: not enough WP_U | 4 | INDIANS | 1775 |
| Muster: Reward Loyalty resources | 2 | BRITISH | 1775, 1776 |
| Gather: WP available count mismatch | 1 | INDIANS | 1778 |
| March: empty move plan | 1 | BRITISH | 1776 |

These are low-frequency errors with diverse causes. Most are pre-condition
check failures where the bot doesn't validate resource/piece availability
before executing.

---

# SECTION B — Illegal Actions (1,400)

## Overview

Illegal actions occur when the bot's sandbox execution completes without
exception, but `_is_action_legal()` rejects the result. This is distinct
from bot_error (which means the code crashed). **An illegal_action means
the bot ran successfully but produced an action the engine considers invalid.**

### Rejection Reason Breakdown

| Rejection Reason | Count | % of illegal | Description |
|-----------------|------:|:------------:|-------------|
| action_type_not_allowed | 526 | 37.6% | Bot returned "event" when events weren't allowed |
| limited_used_special | 266 | 19.0% | Bot used Special Activity in a Limited Command slot |
| limited_wrong_count (affected=4) | 195 | 13.9% | Bot affected 4 spaces in a Limited (1-space) slot |
| limited_wrong_count (affected=2) | 180 | 12.9% | Bot affected 2 spaces in a Limited (1-space) slot |
| limited_wrong_count (affected=3) | 147 | 10.5% | Bot affected 3 spaces in a Limited (1-space) slot |
| limited_wrong_count (affected=5+) | 86 | 6.1% | Bot affected 5-8 spaces in a Limited (1-space) slot |

**There are ZERO `no_affected_spaces` rejections.** This is a major change
from Round 2, where the dominant illegal_action was `affected < 1` (command
affected 0 spaces). The previous fixes eliminated the no-op commands; now
the failures are all about **slot constraint violations**.

### The Three Failure Modes

**Mode 1: Bot plays Event as 2nd-eligible (526, 37.6%)**

All 526 `action_type_not_allowed` rejections are the bot returning
`action = "event"` when `event_allowed = False`. This happens when:
- First faction plays an Event → second faction can only play Command (not Event)
- First faction plays Command+SA → second faction can play Command or Event

In 442 cases: `event_allowed=False, special_allowed=True` (first faction played Event)
In 84 cases: `event_allowed=False, limited_only=True` (first faction played Cmd+SA, but bot tried Event instead of Limited Command)

**The bot doesn't check its slot position.** When acting as 2nd-eligible,
the bot's `take_turn()` → `_choose_event_vs_flowchart()` decides to play
the Event without considering that events are forbidden in the 2nd slot
(when the 1st faction already played an event).

| Faction | Count | Description |
|---------|------:|-------------|
| PATRIOTS | 195 | Most frequent — Patriots frequently act 2nd |
| INDIANS | 122 | |
| BRITISH | 109 | |
| FRENCH | 100 | |

**Mode 2: Bot uses Special Activity in Limited Command slot (266, 19.0%)**

When the bot acts as 2nd-eligible and the 1st faction played Command+SA,
the 2nd faction can only play a **Limited Command** (1 space, no SA).
But the bots execute their SA as part of their normal flowchart, not
knowing they're constrained to Limited.

| Faction/Command | Count | Description |
|-----------------|------:|-------------|
| INDIANS/SCOUT | 49 | Scout includes War Path SA |
| INDIANS/RAID | 49 | Raid includes Plunder/Trade SA |
| FRENCH/MUSTER | 34 | Muster includes Préparer SA |
| PATRIOTS/BATTLE | 31 | Battle includes Partisans SA |
| PATRIOTS/RABBLE_ROUSING | 23 | Rabble Rousing includes SA |
| INDIANS/GATHER | 21 | Gather includes SA |
| FRENCH/BATTLE | 14 | |
| INDIANS/MARCH | 13 | |
| FRENCH/MARCH | 13 | |
| Others | 19 | |

**Mode 3: Bot affects too many spaces in Limited Command slot (608, 43.4%)**

When the 2nd faction can only play a Limited Command (affecting exactly
1 space), the bots execute full (unlimited) commands affecting 2-8 spaces.

**Breakdown by affected count:**

| Spaces Affected | Count | % |
|----------------|------:|---:|
| 2 | 180 | 29.6% |
| 3 | 147 | 24.2% |
| 4 | 195 | 32.1% |
| 5 | 29 | 4.8% |
| 6 | 23 | 3.8% |
| 7 | 19 | 3.1% |
| 8 | 15 | 2.5% |

**By faction and command:**

| Faction/Command | Count | Typical Spaces |
|-----------------|------:|:-------------:|
| PATRIOTS/RALLY | 186 | 2-4 |
| INDIANS/RAID | 67 | 2-3 |
| INDIANS/GATHER | 58 | 2-4 |
| PATRIOTS/RABBLE_ROUSING | 99 | 2-7 |
| BRITISH/MARCH | 73 | 4-8 |
| BRITISH/GARRISON | 34 | 2-4 |
| FRENCH/MARCH | 10 | 2-4 |
| FRENCH/BATTLE | 6 | 2 |
| Others | 75 | Various |

---

## Detailed Faction Analysis

### BRITISH (243 illegal_actions)

| Command | Rejection Reason | Count |
|---------|-----------------|------:|
| NONE (event) | action_type_not_allowed | 106 |
| MARCH | limited_wrong_count (4-8 spaces) | 73 |
| GARRISON | limited_wrong_count (2-4 spaces) | 34 |
| GARRISON | limited_used_special | 6 |
| BATTLE | limited_used_special | 3 |
| BATTLE | limited_wrong_count | 2 |
| Others | Various | 19 |

**Analysis:** The British bot has two main illegal_action paths:
1. **Event as 2nd-eligible (106):** Bot plays Event when it should play Command
2. **Full March/Garrison as Limited (107):** Bot marches through 4-8 spaces
   or garrisons multiple cities when limited to 1 space

The British bot's March and Garrison are designed for full (unlimited)
execution. When constrained to Limited, they don't scale down.

### PATRIOTS (554 illegal_actions — largest faction)

| Command | Rejection Reason | Count |
|---------|-----------------|------:|
| NONE (event) | action_type_not_allowed | 194 |
| RALLY | limited_wrong_count (2-4) | 186 |
| RABBLE_ROUSING | limited_wrong_count (2-7) | 63 |
| BATTLE | limited_used_special | 31 |
| RABBLE_ROUSING | limited_used_special | 23 |
| RALLY | limited_used_special | 5 |
| Others | Various | 52 |

**Analysis:** The Patriot bot is the most-affected by illegal_actions.

1. **Event as 2nd-eligible (194):** Same issue as all factions — bot plays
   Event when events are forbidden in the current slot.

2. **Rally affecting too many spaces (186):** The Patriot bot's `_rally()`
   selects multiple provinces for Rally (place Militia, shift support).
   When constrained to Limited (1 space), it still selects 2-4 provinces.
   This is the single largest command-specific illegal_action category.

3. **Rabble Rousing affecting too many spaces (63) or with SA (23):**
   The Patriot bot's Rabble Rousing selects multiple provinces and sometimes
   includes the SA, both of which violate Limited constraints.

4. **Battle with SA (31):** The Patriot bot executes Battle and then triggers
   Partisans (SA), violating the "no SA in Limited" constraint.

**The core issue:** The Patriot bot has no concept of "Limited Command".
Its flowchart always executes full Commands with SAs. When the engine
constrains it to Limited, every multi-space or SA-inclusive action fails.

### INDIANS (425 illegal_actions)

| Command | Rejection Reason | Count |
|---------|-----------------|------:|
| NONE (event) | action_type_not_allowed | 122 |
| SCOUT | limited_used_special | 49 |
| RAID | limited_used_special | 49 |
| GATHER | limited_wrong_count (2-4) | 58 |
| RAID | limited_wrong_count (2-3) | 67 |
| GATHER | limited_used_special | 21 |
| MARCH | limited_used_special | 13 |
| Others | Various | 46 |

**Analysis:**

1. **Event as 2nd-eligible (122):** Same cross-faction issue.

2. **Scout with War Path SA (49):** Every time the Indian bot Scouts, it
   also triggers War Path as its SA. In Limited slots, the SA is forbidden.

3. **Raid with SA (49):** Same pattern — Raid always pairs with Plunder/Trade.

4. **Gather/Raid affecting too many spaces (125):** Full commands targeting
   2-4 provinces instead of the required 1.

**The core issue:** The Indian bot's flowchart sequences are tightly coupled:
Raid→Plunder, Scout→War Path, Gather→Trade. These pairs are inseparable in
the current bot code, but the Limited slot forbids the SA half.

### FRENCH (178 illegal_actions)

| Command | Rejection Reason | Count |
|---------|-----------------|------:|
| NONE (event) | action_type_not_allowed | 100 |
| MUSTER | limited_used_special | 34 |
| BATTLE | limited_used_special | 14 |
| MARCH | limited_used_special | 13 |
| MARCH | limited_wrong_count (2-4) | 11 |
| BATTLE | limited_wrong_count (2) | 6 |

**Analysis:** The French bot is the least-affected but follows the same
patterns. Its 100 event-as-2nd-eligible rejections are proportionally the
highest (56% of its illegal_actions). The SA violations occur when Muster
triggers Préparer, or Battle/March include an SA.

---

## Cross-Cutting Root Causes

### Root Cause A: Bots ignore slot constraints (874 of 1,400 = 62.4%)

The 874 non-event illegal_actions (limited_used_special + limited_wrong_count)
all share the same root cause: **the bot flowcharts have no concept of
"Limited Command" constraints.** When a bot acts as 2nd-eligible:

- `allowed["limited_only"] = True` means the bot must affect exactly 1 space
  and must not use a Special Activity
- But `bot.take_turn()` runs the same full flowchart regardless of slot position
- The flowchart always tries to maximize effect (multiple spaces, SA included)

**Fix approach:** Each bot's `take_turn()` or `_follow_flowchart()` needs
to receive the `allowed` constraints and adjust behavior:
- If `limited_only`: select only 1 space for the command
- If `not special_allowed`: skip the SA step
- This requires plumbing the `allowed` dict through to the bot

### Root Cause B: Bots play Event as 2nd-eligible (526 of 1,400 = 37.6%)

When the first faction plays an Event, the second faction can only play
a Command (possibly with SA). But `_choose_event_vs_flowchart()` in
`base_bot.py` doesn't check whether events are allowed in the current slot.
It evaluates the event purely on game-state criteria.

**Fix approach:** Pass `event_allowed` to `take_turn()` and short-circuit
`_choose_event_vs_flowchart()` when events are forbidden.

---

## Scenario Distribution

| Error Category | 1775 | 1776 | 1778 |
|---------------|:----:|:----:|:----:|
| Garrison displacement adjacency | Yes | Yes | Yes |
| Garrison not British-controlled | Yes | Yes | Yes |
| Raid no Underground WP | Yes | Yes | Yes |
| Scout billing bug | Yes | Yes | Yes |
| French Battle billing bug | No | No | **1778** |
| Event as 2nd-eligible | Yes | Yes | Yes |
| Limited command violations | Yes | Yes | Yes |

---

## Recommended Fix Priority (by Impact)

### bot_errors (888 total)

| Priority | Group | Count | % of bot_errors | Fix |
|---------:|------:|------:|:---------------:|-----|
| 1 | Garrison displacement adjacency | 719 | 81.0% | Filter displacement targets by adjacency in garrison.py |
| 2 | Garrison not British-controlled | 98 | 11.0% | Check British Control in bot's _can_garrison() |
| 3 | Raid no Underground WP | 29 | 3.3% | Filter Raid targets by Underground WP in indians.py |
| 4 | Scout billing bug | 14 | 1.6% | Fix scout.py:127 to charge correct faction |
| 5 | French Battle billing | 8 | 0.9% | Fix battle.py:106 to charge correct faction |

**Fixing Groups 1-2 eliminates 92.0% of all bot_errors.**

### illegal_actions (1,400 total)

| Priority | Root Cause | Count | % of illegal | Fix |
|---------:|-----------|------:|:------------:|-----|
| 1 | Event as 2nd-eligible | 526 | 37.6% | Pass event_allowed flag to bot.take_turn() |
| 2 | SA in Limited slot | 266 | 19.0% | Pass special_allowed flag; skip SA when False |
| 3 | Full command in Limited slot | 608 | 43.4% | Pass limited_only flag; select only 1 space |

**All three illegal_action root causes require the same architectural fix:
plumb the `allowed` constraint dict from engine.play_turn() through to the
bot's take_turn() and _follow_flowchart() methods.** This is a single
systemic change that would address all 1,400 illegal_actions.

---

## Changes From Round 2

| Round 2 Finding | Round 3 Reality |
|----------------|-----------------|
| #1: Garrison "not a City" (848x) | **FIXED** — no longer appears |
| #2: Plunder "no population" (289x) | **FIXED** — no longer appears |
| #3: Gather "support level" (213x) | **FIXED** — no longer appears |
| #4: March escort cap (207x) | **FIXED** — no longer appears |
| #5: Rally Active Support (117x) | **FIXED** — no longer appears |
| #6: Raid no Underground WP (62x) | Reduced to 29x (partially fixed) |
| #7: March adjacency (43x) | **FIXED** — no longer appears |
| #8: March "not enough pieces" (37x) | **FIXED** — no longer appears |
| #9: French March billing (28x) | Reduced to 8x (partially fixed, now in battle.py too) |
| #10: French Battle pre-ToA (27x) | **FIXED** — no longer appears |
| NEW: Garrison displacement adjacency | **719 errors** — masked by "not a City" crash |
| NEW: Garrison not British-controlled | **98 errors** — same masking |
| NEW: Scout billing bug | **14 errors** — newly exposed |
| NEW: All illegal_action categories | **+633 increase** — bots now reach legality check |

The Round 2 fixes resolved 7 of 11 error groups completely and partially
fixed 2 more. But the fixes unmasked two new Garrison sub-problems (adjacency
and control check) that were hidden behind the original "not a City" crash.
The bots are now reaching the legality check far more often, revealing that
the core architectural problem — bots ignoring slot constraints — produces
the majority of failures.
