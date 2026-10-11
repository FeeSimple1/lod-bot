# Bot outcome diagnostic investigation — October 2026

**2026-10-11 policy update:** The user has resolved Q24 with judgment based
only on knowledge before rolls and a binding Event choice. The new preview excludes
prospective Battle effects, including zero-die Battles; see `QUESTIONS.md`
Q24 and `audit_q24_pre_roll_event_evaluation.md`. The results and policy
limitations recorded below remain historical evidence of the specified
earlier engine, not validation of this subsequent Q24 change.

This follows the 1,500-game standard-setup experiment on the source tree
`788ad3fbb0652ea687adbf65d53c3900079dc9a4` (PR #198). The experiment used
seeds 10000–10499 for each of 1775, 1776, and 1778, with four bots and
`PYTHONHASHSEED=0`. Seven games had reported flags. The original results
remain observations of that older engine; they must not be presented as
outcomes of the corrected engine.

## Original flags

| Scenario / seed | Finding | Correction |
| --- | --- | --- |
| 1775 / 10301, 10322 | Card 39 target ranking charged a Support loss in Blockaded Boston. This created a false tie with unblocked Cities, allowing a genuinely harmful target choice. | Score Support using Blockade-adjusted Population and Opposition using printed Population. |
| 1775 / 10130; 1776 / 10240 | Card 5's actual Battle dice differed from its speculative effectiveness preview. An unlucky realized result was treated as proof of an illegal choice. | Keep decision evidence separate from random combat outcomes; retain checks for deterministic harmful choices. |
| 1775 / 10155; 1776 / 10212 | Card 1's audit recorded a handler-only result while granted free operations were still pending. | Finish the audit at the Event resolution boundary. See the contingent-event limitation below. |
| 1775 / 10441 | Card 85 introduced French Regulars before Treaty of Alliance. Card 66 later planned a forbidden French March, whose executor rejection was reported as an ordinary skip. | Enforce the map-entry restriction centrally, choose legal Event alternatives, align the free-March planner with its executor, and retain execution errors as structured diagnostics. |

## Related corrections

The focused follow-up reviewed the helpers used by the flagged Events. It
found related target-gain, question-space, and removal-priority defects.
The pre-edit audits describe the authoritative requirements and individual
card changes:

- [Blockade target ranking and shared selection](audit_card39_blockade_event_targets.md).
- [Cards 1, 16, and 21](audit_event_gain_priorities_cards1_16_21.md).
- [Card 1 sequencing and deterministic queued Event efficacy](review_event_resolution_sequence.md).
- [Card 14 follow-up legality](audit_card14_followup_legality.md).
- [Card 48 linked March and Battle](audit_card48_linked_march_battle.md).
- [Card 55 optional French Battle before Treaty](audit_card55_pre_treaty_battle.md).
- [French Event placement before Treaty](review_pre_treaty_french_events.md).
- [Card 87 removal priorities](audit_card87_removal_priority.md).

Measurement corrections use structured engine state for winners and Treaty
timing, distinguish Battle Commands from resolved spaces, preserve counts
on failed runs, and enforce `--large --invariants`. Batch, clean-sweep, and
soak gates now inspect recorded bot exceptions, rejected actions, and failed
free operations even when a game eventually declares a winner. Resuming a
soak does not erase a previously recorded failure. Blockades no longer
erase Opposition from reported totals.

The stronger checks then exposed additional paths in cards 1, 14, 48, and
55. Card 1's final Neutral shift could be harmful even when no Battle was
possible; card 14 attempted an unavailable War Path option; card 48 planned
its March and Battle independently despite the required shared destination;
and card 55 attempted its optional French Battle before the Treaty. These
are included in the follow-up repairs and final regression matrix.

## Interpretation limits

Passing the checks establishes completion and compliance with the encoded
invariants; it does not prove every card or bot decision is correct. The
contingent-event effectiveness policy and its source ambiguity are recorded
in `QUESTIONS.md` Q24. A random Battle outcome alone cannot establish that
a prior Event choice violated a deterministic selection rule.
The per-game batch and soak records preserve these observations and their
counts separately from errors rather than dropping them from the results.

## Validation

The final matrix repeated all 1,500 original scenario/seed pairs against
frozen source tree `ed8bd322143952680a3e546cefd03bc7e812ffe4`, with
`PYTHONHASHSEED=0` and invariants after each card. All 1,500 games completed
cleanly, resolving 62,239 cards. Bot errors, rejected actions, failed free
operations, legacy error skips, and Event-preview errors were all zero.
There were no detected invariant violations or unfinished games. Runtime
files match the final change set; later changes only record these results
and refresh the balance fixture.

| Scenario | Games | British | Patriots | French | Indians | Mean cards |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1775 | 500 | 25 (5.0%) | 53 (10.6%) | 197 (39.4%) | 225 (45.0%) | 56.930 |
| 1776 | 500 | 88 (17.6%) | 154 (30.8%) | 169 (33.8%) | 89 (17.8%) | 38.608 |
| 1778 | 500 | 47 (9.4%) | 145 (29.0%) | 263 (52.6%) | 45 (9.0%) | 28.940 |

Final scoring ended 1,173 games; victory-condition checks ended 327.
There were 527 same-seed winner changes from the original engine (198, 179,
and 150 by scenario). This comparison combines the repairs and subsequent
changes in decisions and RNG consumption; it does not isolate the effect of
any one correction or establish human-play balance. No priorities were
tuned to produce desired win rates.

The diagnostics retain **62 adverse Battle-dependent Event observations in
61 games**, separately from errors: card 1 (7), card 5 (1), card 21 (1),
card 48 (52), and card 66 (1). By scenario there were 18, 21, and 23
observations. These observations are still subject to the Q24 limitation
above; a clean matrix does not resolve that rule interpretation.

Additional verification:

- Full regression suite: **1,899 passed**. The separate core-fix commit also
  passed its complete suite of 1,865 tests before the measurement changes.
- Clean-sweep gate: 60 games, seeds 1–20 across all three scenarios, clean.
- Bounded invariant soak: 60 games, clean.
- Human QA: five seating arrangements completed with save/resume checks;
  50 meta-commands, 15 undos (including five Winter Quarters undos), and
  233 Brilliant Stroke interruption prompts exercised.
- Gradual mypy: all 23 configured source files passed.
- Independent focused review caught and verified the repair of the paid
  human in-place March cost; its paid/free and checkpoint variants pass.

The 60-game balance baseline was refreshed only for these intentional
rules corrections; 24 of its winner entries changed. Rules and scenario
reference inputs were not edited. The downloadable evidence archive
contains all 1,500 per-game records, aggregate statistics, raw shard hashes,
and reproduction scripts.
