# Card 39 audit: Blockade-aware Event target selection

Audit completed 2026-10-09 before implementation changes. Scope: card 39,
`lod_ai/cards/effects/late_war.py::evt_039_king_mob`, and its shared
`select_support_shift_spaces` helper. Source-of-truth files remain unchanged.

## Authoritative requirements

- `Reference Documents/card reference full.txt`, card 39, unshaded:
  shift three Cities one level toward Neutral; there is no shaded effect.
- `Reference Documents/Manual Ch 1.txt`, §§1.6.2–1.6.3: Support and
  Opposition totals are Population-weighted; Active counts double Passive.
- The same manual, §1.9: a Blockaded City's Population is zero for
  calculating **Support**. Opposition retains the printed Population.
- `Reference Documents/Manual Ch 8.txt`, §§8.3.5–8.3.6: Royalists select
  Event shift spaces for the highest Support gain, then Opposition loss;
  Rebellion factions use Opposition gain, then Support loss. §8.2 resolves
  equal-priority ties. §§8.3.3/8.3.6 reject an Event whose net shift favors
  the enemy side.
- `QUESTIONS.md` Q14 confirms these gain priorities; Q21 retains the
  existing Blockade City set model; Q22 requires the printed Random Spaces
  tie procedure. None changes the §1.9 distinction between Support and
  Opposition.

## Confirmed mismatch

The shared helper weights both Support and Opposition changes by printed
Population. It therefore treats reducing Support in a Blockaded City as a
Support loss, although the City's contribution to Total Support remains
zero. Card 39 incorrectly ties this harmless shift with a real Support
loss in an unblocked City. A later tie roll can select the harmful space,
even after the Event effectiveness preview selected the harmless space.

The handler's one-level shift and three-City limit match the card text.
The defect is in target valuation, not in the card's effects or the
printed tie procedure. The same helper's other callers inherit the
incorrect Support valuation whenever an eligible City is Blockaded.

## Reproduced evidence before changes

Both games were replayed with `PYTHONHASHSEED=0`, scenario `1775`, standard
setup, all four bots. A read-only runtime wrapper around card 39 recorded
the preview and actual handler calls; no source was modified.

| Seed / draw | Blockade | Preview targets | Actual targets | Actual Support / Opposition | Actual difference |
| --- | --- | --- | --- | --- | --- |
| 10301 / 31 | Boston | Norfolk, Boston, Quebec_City | Norfolk, Charles_Town, Quebec_City | 23 / 8 → 21 / 7 | 15 → 14 |
| 10322 / 55 | Boston | Quebec_City, Boston, Philadelphia | Quebec_City, Philadelphia, Savannah | 32 / 12 → 30 / 11 | 20 → 19 |

In each preview, the difference was unchanged. Correct priorities must
retain Boston among the three targets: its Support marker can shift
without reducing Total Support. The remaining equal-priority choice may
still vary according to §8.2, but that variation must not change the
measured Support loss in these positions.

## Required correction and validation

Use Blockade-adjusted Population for the shared helper's Support delta,
and printed Population for its Opposition delta. Preserve the existing
side priorities, shift clamp, candidate set, and random tie procedure.
Add focused tests for Royalist and Rebellion priorities, Opposition in a
Blockaded City, and actual card 39 execution with Blockaded Boston and
alternative unblocked Support Cities. Replay both reported seeds and run
the existing Event selection tests. Do not alter balance baselines or
source-of-truth documents as part of this correction.

## Adjacent shared-selector finding (audited before its correction)

The selector computes its best gain tier before calling
`pick_random_spaces`. That picker honors `_event_q_spaces`, but it only
sees the already-filtered equal-gain candidates. Consequently, an Event
flowchart-question match with a lower gain can lose to a nonmatching
space. Manual §8.3.5 explicitly puts question-matching spaces before the
other Event target priorities. For example, when Boston is the matching
space and Boston/New_York_City are both Neutral, a one-level Support
shift must select Boston first, even though New_York_City's Population
would yield a larger gain.

Route the selector through the existing `pick_by_priority`, which applies
question matches before substantive keys and preserves the §8.2 tie
procedure. Expose the corrected gain tuple so adjacent card handlers can
combine the same Support/Opposition priorities with their documented
placement/removal priorities without reimplementing the scoring.

## Implemented correction and validation

`shared.support_shift_gain_key` now computes the ordered gain tuple with
Blockade suppression for Support only. The shared selector uses that key
through `pick_by_priority`, preserving question-space precedence and
printed random ties. No card 39 effect changes were required.

`lod_ai/tests/test_review_event_blockade_targets.py` adds 31 regressions:
the four factions' relevant gain priorities, Blockaded Opposition,
question-space precedence, and card 39 across 20 tie-roll seeds. Together
with the existing Event selection/question, bot scoring, early/late card,
and Event evaluation suites, 424 tests passed.

Both original games were also replayed through completion immediately
after the shared Blockade correction, with every card checked by
`invariants.check_all` and no bot errors:

- 1775/10301, draw 31: actual targets included Boston; Support/Opposition
  changed 23/8 → 22/7, leaving the difference at 15.
- 1775/10322, draw 55: actual targets included Boston; Support/Opposition
  changed 32/12 → 31/11, leaving the difference at 20.

Those replays isolate this correction; subsequent separately audited
card fixes can alter earlier play and final outcomes. The initial shared
correction changed 10301's winner, so previous outcome measurements must
remain associated with their original source tree.
