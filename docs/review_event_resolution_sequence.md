# Event follow-ups after immediate free Commands

Source review before implementation: `Reference Documents/Manual Ch 5.txt`
§5.1 requires literal event text and §5.3 makes free Commands immediate.
`Reference Documents/card reference full.txt` card 1 shaded gives free
March and Battle, followed by placement of two Propaganda and a shift one
level toward Neutral. The current handler queues March/Battle but performs
the marker placement and Neutral shift before the engine drains the queue.
That reverses the printed sequence and can change the resulting Support.

Correction: serialize explicit follow-up records for marker placement and
Support shift. Engine drains granted operations, including legal declines
or recorded execution failures, then applies the follow-ups in order and
finally completes the event audit. There are no callable objects in state.
Save/load can retain both queues. Undo propagates before follow-ups and
restores the transaction snapshot through the engine's existing mechanism.

This changes the partial card 1 efficacy preview as a direct consequence
of correct sequencing: the handler now schedules the final Neutral shift
rather than executing it. The handler-only preview does not evaluate the
complete contingent result. That remaining policy issue is Q24, not solved
by assuming an expected Battle result.

## Deterministic queued outcomes

The follow-up replay found card 1 cases where the queued Battle legally
declines and the final Neutral shift therefore has a deterministic adverse
result (1775 seed 10383 and 1778 seed 10403). The presence of a free-operation
queue is insufficient evidence of efficacy. Section 5.3 includes the full
immediate operation sequence; §8.3.3 tests the completed Event.

The bot now drains another copied state through the same engine planners
and executors. It uses that completed state only when no Battle dice were
rolled, no human free-operation choice is needed, and all queued effects
finished. Otherwise it discards the completed copy entirely and preserves
the existing handler-only contingent policy documented in Q24. The real
state and RNG are unchanged by either preview. Deterministic free-operation
failures become structured preview errors. Empty queue containers do not
count as effects.

The deterministic preview is checked again after Event questions consume
their D6 or set question-space priorities. This makes its selected target
match execution at the current RNG position, including Events whose
Battle grants decline. Regression tests cover the real card 1 no-forces
case for both Rebellion factions, changed targets after a deciding D6,
the no-effect clause, state/RNG isolation, human-choice deferral, and
discarding either favorable or unfavorable speculative combat results.

Focused validation: **379 tests passed** across Event efficacy, friendly
removal, question-space, free-operation, second-faction instruction, and
audit regressions. Both original no-Battle reproductions now finish with
per-card invariants enabled and no recorded errors: 1775/10383 completes
after 61 cards; 1778/10403 completes after 28 cards. These are targeted
replays; the final aggregate validation is recorded separately.
