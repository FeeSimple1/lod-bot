# Liberty or Death Vassal module cross-check

Review date: October 19, 2026. Engine baseline: `a51d8da038388de58dfde7906dc88fcbf55e8a6c`
(merged Q24 ruling). The user requested this supplementary comparison.

## Material and method

Reviewed the [Vassal module library entry](https://vassalengine.org/library/projects/Liberty_or_Death_The_American_Insurrection)
and its latest listed release, **LOD v2.vmod**, published October 21, 2020,
requiring Vassal 3.4.1 or later. Download:
<https://obj.vassalengine.org/images/d/d5/LOD_v2.vmod>.

The downloaded archive matches the published SHA-256:
`5ac9664c99ef04b7cf65a549699ab71075943a581da1d09bb4770b7d22fef7bf`.

This was a static inspection of the actual module, not merely its release
notes. Inspected `buildFile`, prototypes, property formulas, deck recipes,
player-aid images, and all three embedded scenario saves. Each savedGame
was decoded from its `!VCSK` hexadecimal/XOR representation; stack parent
coordinates and module map polygons located its pieces. No Vassal client
was launched, and no third-party executable code was run.

The module is a secondary cross-check. Corrections below are independently
required by the repository's read-only Reference Documents and the supplied
rules files. No source-of-truth file, card handler, or published bot priority
was changed to imitate the module.

## Three confirmed engine corrections

### 1. Casualty Forts must return immediately to Available

Manual §1.6.4 explicitly distinguishes the cumulative loss from the
physical destination: British and Patriot Fort casualties count toward
CBC/CRC but immediately return to Available and may be built immediately.
The exception applies to Commands, Special Activities, and Events.

Before this review, Battle implemented that exception, but the shared
`board.pieces.remove_piece(..., to="casualties")` parked Forts in the
Casualties box until Reset. Skirmish option 3, War Path option 3, and card 6
exposed that difference. Both Fort prototypes in Vassal explicitly combine
the cumulative-counter increment with a return to Available, corroborating
the rule.

The shared remover now preserves the requested casualty intent for CBC/CRC
while routing the Fort to Available. Actual removals count once, whether
the caller selects a location or removes across the map. Battle's existing
Available-plus-explicit-counter path remains unchanged. Existing card and
SA tests that asserted the incorrect parked-Fort result were corrected.

### 2. Winter Quarters income must count Fort pieces

Manual §1.4.2 permits two Forts/Villages in one space. Sections 6.3.1 and
6.3.3 award Resources for the number of British/Patriot Forts on the map,
not the number of spaces containing one.

`year_end._resource_income` previously added one for any occupied Fort
space. A legal two-Fort stack earned one Resource instead of two. It now
adds the actual Fort count, preserving City income, the Patriot controlled-
space bonus, Blockade effects, and the Resource cap of 50. This was a
rules-confirmed follow-up found while checking the module's piece and
Fort bookkeeping, not a claim that Vassal computes Winter Quarters income.

### 3. Blockades do not erase Opposition when ranking Support-phase actions

Manual §§1.6.2–1.6.3 and 1.9 preserve printed Population for Opposition in
a Blockaded City. Only Support is suppressed. Vassal's city prototype
likewise suppresses its Support contribution while retaining Opposition
adjustments.

The engine's total Support/Opposition arithmetic already respected this,
but Winter Quarters Reward Loyalty and Committees of Correspondence
priorities did not. Their potential-change calculation used zero Population
for both sides of every shift in a Blockaded City. That contradicted the
net political-change priorities in §§8.4.5 and 8.5.9.

The ranking now measures each endpoint's Support-minus-Opposition value,
including shifts across Neutral. With two Resources and equal marker
counts, removing two levels of Opposition from Blockaded New York City
gains four political points and outranks a one-point Support gain in
Georgia. Creating Opposition in that City likewise has its proper value.
Shifts entirely within its suppressed Support still gain zero. Existing
marker-first priorities, affordability, and two-shift limits are preserved.

## Independent checks that agreed

- All **96 Event IDs** and all three **32-card period groupings** agree with
  `cards/data.json`.
- Standard deck construction uses 6/4/3 Campaigns for 1775/1776/1778.
  Period construction uses `(2, 2, 2)`, `(1, 2, 1)`, and `(0, 1, 2)`
  Campaigns from the three period decks. Each Campaign has six initial
  Events followed by four Events shuffled with its Winter Quarters card.
- The module's immediate swap of a newly revealed Upcoming Winter Quarters
  card with the Current Event agrees with `Engine.draw_card`.
- Its Control formula requires Royalist superiority and a British piece
  for British Control. Indian superiority alone does not grant British
  Control; ties are Uncontrolled. This agrees with the engine.
- The scenario audit accounted for all **142 force/Squadron pieces per
  scenario**, all on-map placements, all **54 political markers**, all
  **12 faction Resource values**, on-map leaders, Squadron locations, and
  initial FNI 0. Starting Support/Opposition totals agree:

| Scenario | Total Support | Total Opposition |
| --- | ---: | ---: |
| 1775 | 4 | 4 |
| 1776 | 3 | 5 |
| 1778 | 17 | 16 |

All 1775 and 1778 Available/Unavailable force counts also agree. The 1776
exceptions are recorded below rather than imported into the engine.

## Errors and limits in the module itself

Two discrepancies in the **1776 module save** are directly contradicted
by `1776 Scenario Reference.txt`. Our engine already has the correct values:

| Item | Vassal 2.0 save | Reference and engine |
| --- | ---: | ---: |
| French Regulars Available / Unavailable | 9 / 6 | 6 / 9 |
| Cumulative British / Rebellion Casualties | 0 / 0 | 1 / 3 |

For the casualty discrepancy, both saved global properties (`CBC_Num`,
`CRC_Num`) and the current marker coordinates indicate zero. Old-position
metadata remembers 1 and 3, but that is not the saved current position.
The 1778 save correctly has CBC 10 and CRC 12.

An additional **unconfirmed client-behavior concern** appears in the
Patriot Militia prototype: its old Ctrl-C handler can still increment
`CRC_Num`, although the Send-to-Casualties menu/trait was removed. That
could count Militia toward CRC without moving it. This was observed only
in configuration, not reproduced in a running Vassal client. Our engine's
CRC classification correctly excludes Militia and was left unchanged.

The module contains images, configuration, metadata, and setup saves;
there are no custom Java classes or scripted Command/Event/bot engine.
Its automation handles bookkeeping and card sequencing. The library
instructions explicitly omit solitaire charts; its included charts are
faction player aids, Battle, Sequence of Play, and Leader Capabilities.
It therefore cannot independently validate bot flowcharts or settle Q24.
The user's binding pre-roll Q24 ruling remains in force.

## Validation

New regressions cover immediate Fort reuse and cumulative counters,
Battle's existing non-duplicated counter path, Skirmish and War Path,
stacked-Fort income, and Blockaded political changes across Neutral.
`python -m pytest -q` passed all **1,943 tests**, including **26 new
regressions**. Gradual mypy passed for all 23 checked util/board files.
`clean_sweep_gate --seeds 1-20` passed **60 bot-only games** with zero
runtime diagnostic errors or invariant violations.

The intended rules corrections changed five winners in the fixed
60-game baseline: 1775 seeds 3, 10, 11, and 15; 1776 seed 20. The
baseline was refreshed from a complete fresh replay of seeds 1–20 in
all three scenarios. No priorities were tuned to obtain those outcomes.
