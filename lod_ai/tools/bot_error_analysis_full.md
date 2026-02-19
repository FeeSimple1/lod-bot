# Bot Error Analysis: Full 60-Game Batch

## Executive Summary

60 zero-player games were run (20 per scenario: 1775, 1776, 1778) with seeds
1-20. Every bot pass was categorized by reason, and every unhandled exception
was captured with full traceback.

**5,258 total faction turns** across 60 games.

| Pass Category    | Count | % of Turns | Description |
|-----------------|------:|:----------:|-------------|
| bot_error       | 1,895 |   36.0%    | Unhandled exception in bot code |
| illegal_action  |   767 |   14.6%    | Sandbox action failed legality check |
| resource_gate   |   162 |    3.1%    | Bot had 0 resources, auto-passed |
| no_valid_command |    40 |    0.8%    | Bot tried but found no valid option |
| **Total passes** | **2,864** | **54.5%** | |
| Successful acts  | 2,394 |   45.5%   | Bot executed a command or event |

**54.5% of all bot turns result in a forced pass.** The bots are functional
less than half the time.

---

## Pass Breakdown by Faction

| Faction  | Total Turns | bot_error | illegal_action | resource_gate | no_valid_command | Total Passes | Pass Rate |
|----------|----------:|----------:|---------------:|--------------:|-----------------:|-------------:|----------:|
| BRITISH  |     1,538 |     1,120 |             94 |             1 |               34 |        1,249 |     81.2% |
| INDIANS  |     1,385 |       591 |            197 |            93 |                0 |          881 |     63.6% |
| PATRIOTS |     1,255 |       128 |            352 |            56 |                0 |          536 |     42.7% |
| FRENCH   |     1,080 |        56 |            124 |            12 |                6 |          198 |     18.3% |

The British bot passes on **81.2%** of its turns. Indians pass 63.6%.
Patriots and French are better but still have significant issues (42.7%
and 18.3% respectively). The French bot's 18.3% pass rate is the healthiest,
but still has 124 illegal_action failures.

---

## Error Categories (bot_error only: 1,895 total)

All 1,895 bot_errors are `ValueError` exceptions. They cluster into
**10 root-cause groups** (55 distinct error messages).

### Overview Table

| Group | Root Cause | Count | % of bot_errors | Factions |
|------:|-----------|------:|:---------------:|----------|
| 1 | British Garrison: "not a City" | 848 | 44.7% | BRITISH |
| 2 | Indian Plunder: "no population" | 289 | 15.2% | INDIANS |
| 3 | Indian Gather: "not at eligible support level" | 213 | 11.2% | INDIANS |
| 4 | British March: escort cap exceeded | 207 | 10.9% | BRITISH |
| 5 | Patriot Rally: "Active Support" after Battle | 117 | 6.2% | PATRIOTS |
| 6 | Indian Raid: "no Underground WP to Activate" | 62 | 3.3% | INDIANS |
| 7 | March adjacency errors | 43 | 2.3% | FRENCH, INDIANS |
| 8 | British March: "not enough pieces" | 37 | 2.0% | BRITISH |
| 9 | French March charging PATRIOTS resources | 28 | 1.5% | FRENCH |
| 10 | French Battle before Treaty of Alliance | 27 | 1.4% | BRITISH, INDIANS |
| 11 | Miscellaneous (12 distinct errors) | 24 | 1.3% | Mixed |
| **Total** | | **1,895** | **100%** | |

---

## Detailed Analysis Per Error Group

### Group 1: British Garrison "not a City" (848 errors, 44.7%)

**The single largest error source.** The British bot's `_garrison()` method
sends Regulars to Cities via `garrison.execute()`. The command validates
that the destination is a City, but the validation fails for **every city
on the map**.

| Destination | Count | Scenarios |
|------------|------:|-----------|
| Philadelphia | 330 | 1775, 1776, 1778 |
| Boston | 192 | 1775, 1776, 1778 |
| New_York_City | 121 | 1775, 1778 |
| Norfolk | 106 | 1775, 1776, 1778 |
| Charles_Town | 79 | 1775, 1776 |
| Quebec_City | 13 | 1775, 1776 |
| Savannah | 7 | 1776, 1778 |

**Call chain:**
```
british_bot.py:566  _garrison  ->  garrison.execute(...)
garrison.py:159     execute    ->  raises ValueError("Destination {X} is not a City")
```

**Root cause:** `garrison.py:159` checks whether the destination space is
classified as a "City" in the state data. The check is failing for all
cities. This is almost certainly a space type lookup bug — either the
garrison command is checking a field that doesn't exist in the state
(e.g., `sp.get("type") == "City"` when the type is stored differently),
or the space IDs used by the bot don't match how Cities are represented
in the state dictionary.

**Representative traceback:**
```
File "bots/british_bot.py", line 566, in _garrison
    garrison.execute(...)
File "commands/garrison.py", line 159, in execute
    raise ValueError(f"Destination {dst_city} is not a City")
```

**Impact:** This is the British bot's primary action path. Since Garrison
is the first thing the British flowchart tries (B1 test), and it fails
every time, the bot cascades to Muster/March fallbacks which also fail
(Group 4). Fixing this single group eliminates 44.7% of all bot_errors.

---

### Group 2: Indian Plunder "no population" (289 errors, 15.2%)

**Message:** `Province has no population to plunder.`

**Call chain:**
```
indians.py:428   _plunder  ->  plunder.execute(state, INDIANS, ctx, target)
plunder.py:70    execute   ->  raises ValueError
```

**Scenarios:** All three (1775, 1776, 1778)

**Root cause:** The Indian bot attempts Plunder as a Special Activity after
Raid. The `_plunder()` method selects a target province but doesn't verify
that the province has "population" (likely meaning it has a Population value
or cubes/pieces that represent population). The `plunder.py` command validates
this and rejects the attempt.

The Indian bot's target selection in `_plunder()` either:
1. Doesn't check population at all before choosing a target, or
2. Checks a different criterion than what `plunder.py` validates.

This is the second-largest error overall and the largest Indian-specific
error. It occurs nearly every time the Indian bot successfully raids (or
attempts to raid) and then tries its SA.

---

### Group 3: Indian Gather "not at eligible support level" (213 errors, 11.2%)

**Message pattern:** `{Province} not at an eligible support level.`

| Province | Count | Scenarios |
|----------|------:|-----------|
| New_York | 101 | 1775, 1776, 1778 |
| Quebec | 53 | 1775, 1776, 1778 |
| Quebec_City | 21 | 1775, 1776, 1778 |
| South_Carolina | 14 | 1778 only |
| Virginia | 11 | 1775 only |
| Georgia | 5 | 1776 only |
| Massachusetts | 4 | 1776 only |
| Northwest | 3 | 1775, 1778 |
| Pennsylvania | 1 | 1776 only |

**Call chain:**
```
indians.py:654   _gather  ->  gather.execute(...)
gather.py:119    execute  ->  raises ValueError
```

**Root cause:** The Indian bot's `_gather()` selects provinces where it wants
to Gather (place War Parties), but `gather.py` validates that each province
is at an eligible support level for Indian Gather. The bot's selection logic
doesn't apply the same support-level filter that the command enforces.

Per the Indian flowchart, Gather should target provinces at Opposition or
Neutral. The bot appears to be targeting spaces regardless of their support
level, hitting spaces at Passive/Active Support where Gather is prohibited.

---

### Group 4: British March Escort Cap Exceeded (207 errors, 10.9%)

**Message:** `Escort cap exceeded for British March.`

**Call chain:**
```
british_bot.py  ->  _march  ->  march.execute(...)
march.py:303    execute     ->  _apply_move
march.py:172    _apply_move ->  raises ValueError
```

**Scenarios:** All three (1775, 1776, 1778)

**Root cause:** The British bot constructs march move plans that include
Tories. Per game rules, Tories must be escorted 1-for-1 by British Regulars
during March. The bot includes more Tories in the move plan than it has
Regulars to escort them.

This is an evolution of Error #3 from the single-game analysis. The previous
`bring_escorts=False` bug was fixed, but now the escort *count* validation
fails. The bot includes Tories without checking whether enough Regulars are
in the plan to escort them. The march command enforces the 1:1 ratio and
rejects the move.

---

### Group 5: Patriot Rally at Active Support (117 errors, 6.2%)

**Message pattern:** `{Space} has Active Support; cannot Rally there.`

| Space | Count | Scenarios |
|-------|------:|-----------|
| New_York_City | 64 | 1775, 1776, 1778 |
| Quebec_City | 39 | 1775, 1776, 1778 |
| Philadelphia | 8 | 1778 only |
| Boston | 4 | 1775 only |
| New_York | 2 | 1778 only |

**Call chain:**
```
patriot.py  ->  _execute_battle  ->  battle.execute(...)
battle.py:137   execute          ->  rally.execute(...)  [post-battle Rally]
rally.py:209    execute          ->  raises ValueError
```

**Root cause:** The Patriot bot executes Battle, and after Battle,
`battle.py` automatically triggers a Rally in the battle space. However,
`rally.py` rejects Rally in spaces already at Active Support (the maximum
support level). The Patriot bot wins battles in cities that already have
Active Support, and the post-battle Rally call fails.

The issue is in the battle-to-rally chain: `battle.py:137` calls Rally
unconditionally after battle, without checking whether Rally is valid
in that space. If the space is already at Active Support, Rally has no
effect and shouldn't be attempted (or should be a no-op).

---

### Group 6: Indian Raid "no Underground WP to Activate" (62 errors, 3.3%)

**Message pattern:** `{Province}: no Underground WP to Activate.`

| Province | Count | Scenarios |
|----------|------:|-----------|
| Massachusetts | 13 | 1775, 1776, 1778 |
| South_Carolina | 13 | 1778 only |
| Connecticut_Rhode_Island | 10 | 1776, 1778 |
| Virginia | 9 | 1775 only |
| North_Carolina | 9 | 1776, 1778 |
| New_York | 6 | 1775 only |
| New_Jersey | 2 | 1778 only |

**Call chain:**
```
indians.py:384  _raid  ->  raid.execute(...)
raid.py:154     execute ->  raises ValueError
```

**Root cause:** The Indian bot constructs Raid plans that include provinces
where it has War Parties, but those War Parties are Active (not Underground).
Raid requires activating Underground War Parties. The bot doesn't filter
its Raid targets by Underground WP availability.

---

### Group 7: March Adjacency Errors (43 errors, 2.3%)

**Message pattern:** `{Src} is not adjacent to {Dst}.`

| Route | Count | Factions | Scenarios |
|-------|------:|----------|-----------|
| New_Jersey -> New_York | 20 | FRENCH=18, INDIANS=2 | 1778 only |
| Massachusetts -> New_Hampshire | 17 | FRENCH=10, PATRIOTS=7 | 1775, 1776, 1778 |
| Quebec -> New_York | 6 | INDIANS=6 | 1775, 1776 |

**Call chain:**
```
{bot}.py  ->  march.execute(...)
march.py:303  execute    ->  _apply_move
march.py:140  _apply_move ->  raises ValueError
```

**Root cause:** The bots construct march plans with source-destination
pairs that are not adjacent on the map. This indicates either:
1. The adjacency data in `map/data/map.json` is missing these connections, or
2. The bots are using a different adjacency source than what `march.py`
   validates against.

New_Jersey and New_York *should* be adjacent (they share a border). Same
for Massachusetts and New_Hampshire. This looks like a map data bug
rather than a bot logic bug.

---

### Group 8: British March "Not Enough Pieces" (37 errors, 2.0%)

**Message pattern:** `Not enough {piece_type} in {Space}.`

| Space | Count | Scenarios |
|-------|------:|-----------|
| North_Carolina | 16 | 1775, 1776, 1778 |
| New_York | 11 | 1775, 1778 |
| Connecticut_Rhode_Island | 3 | 1776 |
| New_Jersey | 2 | 1778 |
| Maryland-Delaware | 2 | 1778 |
| Boston | 1 | 1775 |
| Philadelphia | 1 | 1778 |
| South_Carolina | 1 | 1778 |

**Call chain:**
```
british_bot.py  ->  _march  ->  march.execute(...)
march.py:164    _apply_move ->  _take  ->  raises ValueError
```

**Root cause:** The British bot's `_march()` constructs move plans
referencing more British_Regular in a space than actually exist there.
The bot takes a snapshot of available pieces at plan-construction time
but doesn't account for pieces already committed to earlier moves in
the same plan. When `march.py` tries to pick up pieces, the space has
fewer than expected.

---

### Group 9: French March Charging PATRIOTS Resources (28 errors, 1.5%)

**Message pattern:** `PATRIOTS cannot afford {N} Resources`

| Amount | Count |
|--------|------:|
| 1 Resource | 12 |
| 2 Resources | 10 |
| 3 Resources | 4 |
| 4 Resources | 2 |

**Call chain (all from French bot):**
```
french.py  ->  march.execute(state, FRENCH, ...)
march.py:286   execute  ->  spend(state, PATRIOTS, fee)
resources.py:18  spend  ->  raises ValueError
```

**Scenarios:** 1778 only (all 28 occurrences)

**Root cause:** The French March code at `march.py:286` charges
**PATRIOTS** for the march fee instead of **FRENCH**. This is a billing
bug — the march command is spending from the wrong faction's resource pool.
When Patriots happen to have 0 resources, the charge fails.

This only appears in 1778 because that's the scenario where France is
most active (post-Treaty of Alliance), and Patriots tend to be resource-
depleted in the short game.

---

### Group 10: French Battle Before Treaty of Alliance (27 errors, 1.4%)

**Message:** `French cannot Battle before Treaty of Alliance`

**Call chain:**
```
base_bot.py:242  _is_ineffective_event  ->  handler(after, shaded=shaded)
middle_war.py:794  evt_055_french_navy  ->  battle.execute(state, FRENCH, ...)
battle.py:87     execute               ->  raises ValueError
```

**Factions affected:** BRITISH=16, INDIANS=11

**Scenarios:** 1775 and 1776 only

**Root cause:** The `_is_ineffective_event()` method in `base_bot.py`
speculatively runs card handlers to see if they'd change the game state.
When Card 55 (French Navy) is evaluated, its handler tries to execute
a French Battle. But before the Treaty of Alliance is played, French
cannot Battle. The speculative execution crashes.

This affects British and Indian bots (not French or Patriot) because
those are the factions that would consider playing Card 55's shaded
side. The crash happens during event evaluation, not during actual
event execution.

---

### Group 11: Miscellaneous Errors (24 errors, 1.3%)

| Error | Count | Faction | Scenarios |
|-------|------:|---------|-----------|
| War Path: no Rebellion units | 6 | INDIANS | 1776, 1778 |
| Muster: fort stacking limit | 5 | BRITISH | 1776 |
| Rally: need 2 units for Fort | 4 | PATRIOTS | 1778 |
| Muster: BRITISH can't afford 4 Resources | 3 | BRITISH | 1776 |
| Garrison: BRITISH can't afford 2 Resources | 2 | BRITISH | 1775, 1776 |
| Muster: not enough for Reward Loyalty | 1 | BRITISH | 1776 |
| Gather: WP available count mismatch | 1 | INDIANS | 1776 |
| Battle: BRITISH can't afford 3 Resources | 1 | BRITISH | 1776 |
| Gather: move destination not in selected | 1 | INDIANS | 1778 |

These are low-frequency errors with diverse causes. Most are pre-condition
check failures where the bot doesn't validate affordability, stacking
limits, or piece availability before executing.

---

## Comparison: bot_error vs illegal_action

| Category | Count | What It Means |
|----------|------:|---------------|
| bot_error | 1,895 | Bot code raised an unhandled exception during `_simulate_action()` |
| illegal_action | 767 | Bot returned an action, sandbox completed, but `_is_action_legal()` rejected it |

**illegal_action breakdown by faction:**

| Faction | illegal_action | Likely Cause |
|---------|---------------:|-------------|
| PATRIOTS | 352 | Bot returns actions that affect 0 spaces (empty commands) |
| INDIANS | 197 | Bot returns actions that affect 0 spaces |
| FRENCH | 124 | Bot returns actions that affect 0 spaces or limited-only violations |
| BRITISH | 94 | Bot returns actions that affect 0 spaces |

The `illegal_action` path (engine.py:842-845) fires when the bot's sandbox
execution completes without exception but the result fails the legality check
in `_is_action_legal()`. The most common legality failure is `affected < 1`
(line 415-416): the bot "executed" a command that didn't actually affect any
spaces, so the engine rejects it as a no-op.

This is distinct from bot_error: **illegal_action means the bot code ran
successfully but produced an ineffective result.** bot_error means the bot
code crashed.

---

## Scenario Distribution

| Error Group | 1775 | 1776 | 1778 |
|------------|:----:|:----:|:----:|
| Garrison "not a City" | Yes | Yes | Yes |
| Plunder "no population" | Yes | Yes | Yes |
| Gather "support level" | Yes | Yes | Yes |
| March escort cap | Yes | Yes | Yes |
| Rally Active Support | Yes | Yes | Yes |
| Raid "no Underground WP" | Yes | Yes | Yes |
| March adjacency | Yes | Yes | Yes |
| March "not enough pieces" | Yes | Yes | Yes |
| French March billing | No | No | **1778 only** |
| French Battle pre-ToA | Yes | Yes | No |

Most errors appear across all three scenarios. Two are scenario-specific:
- French March billing bug appears only in 1778 (French most active)
- French Battle pre-ToA appears only in 1775/1776 (before ToA is guaranteed)

---

## Recommended Fix Priority (by Impact)

| Priority | Group | Count | % of bot_errors | Fix Complexity |
|---------:|------:|------:|:---------------:|---------------|
| 1 | Garrison "not a City" | 848 | 44.7% | Fix City type check in garrison.py |
| 2 | Plunder "no population" | 289 | 15.2% | Add population check in indians.py _plunder() |
| 3 | Gather "support level" | 213 | 11.2% | Add support level filter in indians.py _gather() |
| 4 | March escort cap | 207 | 10.9% | Enforce 1:1 Tory:Regular ratio in british_bot.py _march() |
| 5 | Rally Active Support | 117 | 6.2% | Skip Rally in battle.py when space at Active Support |
| 6 | Raid "no Underground WP" | 62 | 3.3% | Filter by Underground WP in indians.py _raid() |
| 7 | March adjacency | 43 | 2.3% | Fix map adjacency data or bot routing logic |
| 8 | March "not enough pieces" | 37 | 2.0% | Track piece commitments in british_bot.py _march() |
| 9 | French March billing | 28 | 1.5% | Fix faction in march.py:286 spend() call |
| 10 | French Battle pre-ToA | 27 | 1.4% | Guard Card 55 handler against pre-ToA execution |

**Fixing Groups 1-4 would eliminate 1,557 of 1,895 bot_errors (82.1%).**
**Fixing Groups 1-6 would eliminate 1,736 of 1,895 bot_errors (91.6%).**

---

## Changes From Single-Game Analysis

The single-game analysis (1775/seed=1) found 59 errors in 5 categories.
The full 60-game batch reveals a dramatically different error profile:

| Single-Game Finding | Full-Batch Reality |
|--------------------|-------------------|
| #1: Indian Raid Quebec/New_York range (25x) | Not in top 20 — was likely fixed |
| #2: Muster Reward Loyalty pieces (13x) | Not in top 20 — was likely fixed |
| #3: March without escorts (10x) | Evolved into Group 4: escort *cap* exceeded (207x) |
| #4: Muster Reward Loyalty no control (6x) | Not in top 20 — was likely fixed |
| #5: Card 10 handler crash (2x) | Not in top 55 — was likely fixed |
| NEW: Garrison "not a City" | **848 errors** — completely absent from single-game |
| NEW: Plunder "no population" | **289 errors** — completely absent from single-game |
| NEW: Gather "support level" | **213 errors** — completely absent from single-game |

The fixes applied after the single-game diagnostic resolved 4 of the
original 5 error categories, but **uncovered new errors that were masked
by the earlier crashes.** When the Indian Raid bug was fixed, the Indian
bot now reaches Plunder and Gather — which have their own bugs. When the
British Muster Reward Loyalty bugs were fixed, the British bot now reaches
Garrison — which has a City type check bug.

This is the classic "fix reveals the next bug" pattern described in
CLAUDE.md's Known Issues.
