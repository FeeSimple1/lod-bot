# Live LLM human-seat playtests — 2026-10-20

LLM agents navigated the real interactive CLI while the published non-player
bots controlled the other seats. Every substantive answer was selected by an
LLM and recorded with its rationale. These were exploratory sessions, not
completed-game outcome statistics or a claim of commercial readiness.

The original sessions started from main commit
`b9a39fa2b6ad1c237bafc7de1761673b14326e58`. Rules came only from this
repository's Reference Documents. No external model service/key was used;
the players were agents in the working session. They saw public observations,
rendered CLI output, and menus, not the unrevealed deck or future RNG results.

## Method and evidence

| Trial | Human seats | Completed cards | LLM answers | Stop |
|---|---|---:|---:|---|
| 1778, seed 21 | Patriots | 11 | 78 | Explicit player stop |
| 1775, seed 12021 | French | 11 | 29 | Bridge protocol error |
| 1776, seed 21 | British, Indians | 6 | 69 | Requested card limit |
| 1778, seed 12022 | French | 6 | 27 | Requested card limit |

That is **34 completed cards and 203 live LLM answers**, plus separately
recorded focused confirmations. No trial completed an entire game. The French
1775 error is included in activity totals but is not a successful run.

`python -m lod_ai.tools.llm_playtest` runs `interactive_cli._game_loop`, swaps
only its input source, and isolates each trial's saves and reports. Bare
Enter-to-continue pauses are counted separately. A timeout/protocol error never
substitutes a random, first-choice, or bot answer. It checks state validity and
save/load equivalence at card boundaries and at the end.

Recorded trial results and decision logs are in `playtests/2026-10-20/`.
Full transcripts and CLI output are gzip-compressed (`.gz`); decompress with
`gzip -dc <file.gz>` or Python's `gzip` module. Result JSON files are uncompressed.
The decision logs retain the original request, observation, actual menu,
answer, rationale, incremental history and CLI output. Initial logs have a
known instrumentation limitation: normal turns did not initially bind the
provider's faction field, so it could be null or stale. Players followed the
rendered CLI faction headings. The new bridge binds the seat at every turn.

One French 1775 trial ended at a duplicate-response protocol error. Its
11 cards and 29 answers are retained as evidence, not counted as a successful
game. The bridge now records/discards a duplicate prior request ID and waits
for the current answer, with the original timeout still enforced. A separate
French 1778 trial tests the corrected bridge.

## Findings and corrections

| Finding | Evidence | Correction |
|---|---|---|
| Agent Mobilization offered illegal Provinces/Cities | French 1775 requests 5–7: Boston selected, then rejected; state/resources stayed unchanged | Menu now offers only Quebec, New York, New Hampshire and Massachusetts, excluding Active Support (§3.5.1) |
| Rally omitted a legal second Fort and replacement piece choice | Patriot 1778 request 8: Pennsylvania had one Fort and seven Patriot units, but no Fort action; later construction removed Underground Militia without a mix prompt | Permit a second Fort within the two-base cap, and let humans choose the two replaced units (§3.3.1) |
| Indian Event 91 silently selected Florida | Crown requests 7–9: human chose unshaded Event, no Reserve target menu | Human Reserve target on both sides; preserve bot defaults. Pre-edit audit: `card91_human_choice_audit.md` |
| Fixed-location free Commands bypassed human plans | Targeted Card 94 reproduction: zero prompts, automatic Gather and a logged Muster with no placement | Constrained human March/Battle/Rally/Gather/Muster wizards, including +2 Battle; failed execution rolls back and records an error |
| Waxhaws lacked target and movement choices | Targeted source audit and real wizard tests | Target selection on both sides, location-constrained human March/Battle details, printed aftermath after the Commands. Pre-edit audit: `card1_human_choice_audit.md` |
| Gather offered Cities and illegal regrouping, omitted hide-in-place and Cornplanter's one-WP Village | Crown request 50 offered Cities; targeted rule/leader checks confirmed the other missing options | Province-only filter; regroup requires a Village and permits zero movers; Cornplanter cost reflected in choices and planning (§3.4.1; leader reference) |
| Human Leader moved automatically to an unrelated large stack | Crown requests 41–48: Brant's New York War Parties marched to Pennsylvania, but Brant appeared in Florida | Actual March ledger drives human follow/stay choices; an emptied origin offers legal relocation/Available choices before normalization (§1.10). This was the automatic orphan repair, not the bot OPS helper |
| Brilliant Stroke ignored a March origin when checking Leader involvement | Crown requests 51–52 and Patriot requests 60–73: a first March from the Leader's origin did not satisfy involvement | Include movement origins in the check and refresh the displayed Leader location |
| French Muster forced four Regulars | French 1778 requests 7–8: location selection proceeded directly to Fort replacement | Human selects 0–4 Regulars (§3.5.3); existing bot default remains unchanged |
| LLM observation omitted public information and misstated solo victory | French needed `status` for pools/Preparations; serializer inspection confirmed missing empty political spaces/markers | Full public board, population, markers, pools, Preparations and applicable §8.8/Treaty notes, without revealing the deck |
| Human action summaries said “BOT” | Crown/Patriot/French live output | Neutral faction summary heading |

Save, status, defensive activation, human command/SA ordering, Event choices,
and undo during Winter Quarters were exercised successfully. Save/undo
observations concern the existing committed-boundary semantics, not arbitrary
prompt-level continuation.

## Controlled failure testing

Separately from live play, an injected bot Brilliant Stroke planner exception
proved that partial Resource/board/RNG/context changes survived a swallowed
exception. The fix restores those values and records a structured bot error.
Injected failed human free operations similarly verify rollback and no
automatic replacement plan. These are fault-injection tests, not naturally
observed crashes. The initial French bot “BS aborted” message alone does not
prove an exception: an ordinary no-plan result remains legitimate.

Zero runtime diagnostic counters did **not** establish correct human play:
missing choices and rejected sandbox actions can leave those counters at zero.
The bridge now also retains rendered `Action failed:` messages separately.
The old “human completeness” test was an inventory of existing hooks; it could
not detect missing hooks. Its description now states that limitation.

## Remaining follow-up

- Audit every printed human choice against actual menus, rather than relying
  on hook inventory. These sessions do not establish completeness.
- Collect target choices from human beneficiaries when a bot executes a
  named-faction Event; the executor-only collection path remains a gap.
- Add dedicated free-operation choices for Partisans/War Path, and audit
  voluntary map-piece removal choices when an Available pool is empty.
- Audit multi-space Rally pool projections: newly recruited or returned
  pieces are not fully projected into later planning menus. The new typed
  movement ledger fixes reuse of departing units, not that broader issue.
- Review French March destination filtering and Special Activity option
  descriptions flagged by the French player. These were observations for
  follow-up, not confirmed board-state errors in this batch.
- Leader choices after operations/removals beyond human March still need a
  systematic audit. The separate non-player OPS post-stack approximation was
  not rewritten here.
- Broader save durability/version validation and transaction coverage remain
  separate commercial-quality work.
- Run more seeds, complete full human-seat games, and use other model families
  and actual human testers. This small same-model sample cannot estimate win
  rates or certify all rules and usability paths.

Existing API-backed LLM policies can fall back to a first legal answer on
provider errors; those policies were **not** used for the live trials above.
Only the explicit file bridge supports the all-recorded-LLM-decisions claim
for this batch.

## Verification

- Full suite: **2,008 tests passed**.
- Bot invariant gate: **60/60 games clean** (seeds 1–20 across all three
  scenarios), including per-card schema and save/load checks.
- Existing gradual type gate: no issues in 23 util/board source files.
- Focused live confirmation: six LLM decisions reproduced Brant's emptied
  origin with Florida at four War Parties and Pennsylvania at two. The new
  menu selected Pennsylvania, and normalization preserved it; state/save
  checks passed. This was a constructed fixture, not a full game.
- Focused live Rally confirmation: four LLM decisions selected a second Fort
  in Pennsylvania and spent two Continentals, preserving both Underground
  Militia. The resulting three Continentals/two Militia/two Forts position
  passed state/save checks. This was a constructed fixture, not a full game.
- Final multi-space Rally regressions also verify that the Fort picker cannot
  reuse Militia already assigned to regroup elsewhere, and that regrouped
  arrivals cannot move twice.
