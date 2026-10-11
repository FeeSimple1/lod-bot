# Event gain-priority audit: cards 1, 16, and 21

Audit recorded on 2026-10-09 before implementation changes. Scope is the
automatic target selection in `evt_001_waxhaws`, `evt_016_mercy_warren`, and
`evt_021_sumter` in `lod_ai/cards/effects/late_war.py`. Source-of-truth
documents remain unchanged. This audit follows the separately documented
shared-selector Blockade defect; these handlers currently bypass that
selector with their own gain calculations.

## Authoritative requirements

- `Reference Documents/card reference full.txt`, card 1, lines 7–11:
  unshaded removes two Continentals in one space with British, shifts that
  space one level toward Active Support, and places two Propaganda. The
  shaded side has a free March and Battle followed by other effects; that
  free-Command target-selection procedure is outside this narrow correction.
- The same file, card 16, lines 195–205: shaded shifts one City **to**
  Passive Opposition, rather than a fixed number of levels toward it.
- The same file, card 21, lines 258–268: unshaded shifts South Carolina or
  Georgia two levels toward Active Support.
- `Reference Documents/Manual Ch 1.txt`, §§1.6.2–1.6.3: Support and
  Opposition totals weight their levels by Population. Section 1.9,
  lines 275–277, treats a Blockaded City's Population as zero when
  calculating **Support**; it does not suppress Opposition.
- `Reference Documents/Manual Ch 8.txt`, §8.3.5, lines 214–226: prefer
  spaces matching the deciding Event question, then apply §8.3.6 shift
  priorities. **Within** these priorities, maximize the specified piece
  placements/removals. Resolve remaining ties through §8.2.
- The same manual, §8.3.6, lines 227–239: Royalists prioritize highest
  Support gain, then highest Opposition loss; Rebellion factions prioritize
  highest Opposition gain, then highest Support loss. These are ordered
  priorities, not their sum or a total number of shifted levels.
- `Reference Documents/indian bot flowchart and reference.txt`, card 21
  Special Instructions, lines 156–159: Indians select non-Village spaces
  first. This instruction precedes the default gain priorities.
- All four `* bot flowchart and reference.txt` Special Instructions
  sections were inspected: none specifies a card 1 exception that would
  place Continental removals ahead of the default shift priorities.
- `QUESTIONS.md` Q14 confirms §8.3.6 gain selection; Q21 retains the
  Blockade set model without changing Support scoring; Q22 requires the
  printed Random Spaces procedure for equal-priority choices.

## Confirmed defects and reproductions

The examples below used canonical map identifiers and constants. Diagnostic
handlers ran on in-memory states only; no source was changed to reproduce
the findings.

### Card 1: unshaded Waxhaws Massacre

The old expression at `late_war.py:142` references `ACTIVE_SUPPORT` without
importing it. Any eligible unshaded invocation raises `NameError` before
performing its effects. Injecting the canonical constant into the diagnostic
process allowed the underlying ranking to be inspected separately.

With equal removable Continentals, Neutral Boston Blockaded and Neutral
Norfolk unblocked, both received gain 1 from printed Population. Seed 0
selected Boston, whose actual Support gain is zero; Norfolk gains one.
The corrected key must apply Blockade suppression to Support only.

The existing key also maximizes removals before shifts and treats every
upward level as the same kind of gain. Section 8.3.5 places piece
maximization within the shift priorities. Therefore the automatic unshaded
key must use Support gain, Opposition loss, then removable Continentals,
with deciding-question spaces first and §8.2 for remaining ties.

### Card 16: shaded Mercy Warren's “The Motley Assembly”

The old `(level + 1) * Population` score conflates Opposition gain with
Support loss and counts Blockaded Support. Reproduced examples:

| Candidates before the Event | Old selection | Required selection and reason |
| --- | --- | --- |
| Blockaded Boston at Active Support; unblocked Norfolk at Passive Support | Boston | Norfolk: both gain 1 Opposition, but only Norfolk loses counted Support (1). |
| Boston at Active Support; New_York_City Neutral, neither Blockaded | Boston | New_York_City: it gains 2 Opposition, versus Boston's 1; Support loss is secondary. |

Selection must evaluate the full move to Passive Opposition, including
movement from Active Opposition toward Passive Opposition when applicable.
An explicit valid `card16_city` remains the supplied choice.

### Card 21: unshaded The Gamecock Thomas Sumter

Both eligible spaces are Colonies, so Blockades cannot cause this defect.
The old `levels shifted * Population` key instead violates the ordered
Support/Opposition priorities. With South_Carolina at Active Opposition and
Georgia Neutral, it selects South_Carolina: four Opposition are lost but
zero Support gained. Georgia gains two Support and therefore has priority.
The Indian non-Village instruction must remain ahead of default gains.
An explicit valid `card21_target` remains the supplied choice.

## Correction and validation scope

Use the shared Blockade-aware Support/Opposition gain calculation for the
three automatic selectors. Compose it with their printed, applicable
priorities before invoking the existing Random Spaces tie resolver. Import
canonical Support/Opposition constants where needed. Preserve the effects,
explicit choices, event-question precedence, and Indian card 21 instruction.

Focused regression tests will exercise card 1's missing constant and
Blockade/ordered priorities, card 16's two reproduced mis-rankings and full
move to Passive Opposition, card 21's ordered priorities and Indian
non-Village instruction, explicit choices, and applicable question-space
precedence. Existing Event target-selection and late-war card tests will
also run. No balance tuning or source-of-truth edits are included.

## Implementation and validation

The three automatic selectors now use
`shared.support_shift_gain_key` with their applicable additional priorities
and `pick_by_priority`. Card 1 imports canonical `ACTIVE_SUPPORT` before
its unshaded selection; card 16 uses canonical `PASSIVE_OPPOSITION` for
both evaluation and application. Card 21 retains its Indian non-Village
priority. Explicit choices and the separate shaded free-Command branches
remain intact.

Validation on 2026-10-09: **88 tests passed**, comprising the 16 cases in
`lod_ai/tests/test_review_event_gain_priorities.py` plus
`test_review_event_blockade_targets.py`, `test_event_space_selection.py`,
`test_event_question_spaces.py`, `test_t9_space_picks_s48.py`, and
`test_late_war_cards.py`. The card 1 tests invoke the handler directly
without injecting any constants. No gameplay seed or balancing parameter
was changed for these corrections.

## Authorized follow-up: card 1 candidate eligibility

Recorded before this follow-up implementation on 2026-10-09. The root
review explicitly extended the scope to card 1's candidate filter.

`Reference Documents/card reference full.txt`, card 1, lines 7–11, requires
British presence only on the unshaded side. It says British, not British
Regulars; `Manual Ch 1.txt` §1.4 identifies Regulars, Tories, and Forts as
British pieces. The shaded text allows its free Patriot March and Battle
in one space without requiring any British piece there.

The current shared candidate filter requires `REGULAR_BRI` on both sides.
Consequently it skips unshaded effects in Tory-only or Fort-only British
spaces, and excludes shaded destinations with Indian enemies but no
British. These are concrete card-text mismatches, independent of gain
ranking.

The narrow correction is to admit all three British piece tags for
unshaded eligibility and remove the British-presence requirement for
shaded eligibility. Preserve the existing shaded free-Command target
priority and subsequent effects. Add regressions for Tory-only and
Fort-only unshaded spaces and a shaded March/Battle target defended by
Indians, with no British pieces anywhere in the fixture.

Follow-up validation: the three added eligibility cases pass, including
both unshaded British piece types and the actual shaded free-Command target
helper. Re-running the same six test files produced **91 passed**; the
focused new file now contains 19 cases.

## Authorized follow-up: card 1 shaded effect sequence

Recorded before implementation on 2026-10-09. The source review confirmed
an additional literal-order mismatch. Card 1's shaded text specifies the
free Patriot March and Battle first, then two Propaganda in that space,
then a one-level shift toward Neutral. `Manual Ch 5.txt` §5.1 requires
literal execution of the Event; §5.3 makes its free Commands immediate
interruptions. Section 5.1.3 requires the remaining possible effects even
when a granted Command cannot be performed.

The handler currently queues March and Battle but immediately places
Propaganda and shifts Support. The Engine only executes the queued
Commands after the handler returns. This reverses the printed sequence,
lets the Commands see markers that should not exist yet, and calculates
the Neutral shift before Battle's Win the Day can change Support.

The correction will queue serializable aftermath data after granting
March and Battle. Engine free-operation resolution must complete both
Commands (or their legal declines), then place the two Propaganda and
shift the **resulting** Support level one step toward Neutral. Event
choice audit completion must follow the aftermath. No function or
callback may be stored in the game state. Card 1's candidate-selection
priorities remain unchanged by this sequencing correction.

Regression coverage will observe that the marker and shift are absent
during both free Commands, that a Battle-time Support change is used by
the later Neutral shift, and that the possible aftermath still executes
when both Commands are declined. Existing direct-handler tests must
resolve the legitimate aftermath before asserting final marker/Support
effects.

Sequencing validation: the handler now schedules only serialized
`place_marker` and `shift_support_toward` records after its two granted
Commands. Engine resolution consumes these records before closing the
Event audit. Regression tests verify actual free March and Battle with
no Propaganda present during either command, and an actual Win the Day
that changes Pennsylvania from Passive Support to Passive Opposition
before the Event shifts it to Neutral. Additional tests isolate reading
the post-Battle level and executing the possible aftermath when both
Commands legally decline. The focused card-priority file now has 22
cases. The combined card/Event/selection/scoring/audit suite passed
**486 tests**, and `git diff --check` was clean. No callbacks are stored
in game state.
