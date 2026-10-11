# Q24 pre-roll Event-evaluation audit

Recorded on 2026-10-11 before the Q24 implementation changes. Scope is the
shared Non-player Event-effectiveness preview and its diagnostic evidence,
not any card's printed effects or target-selection priorities. The user
resolved the open policy question: “The bot should judge only based on what
it knows before rolling.” Source-of-truth documents remain unchanged.

## Authoritative requirements and supplied ruling

- `Reference Documents/Manual Ch 8.txt`, §8.3.3 (lines 181–188): after
  applicable Event Instructions, an Event is Ineffective if it has no
  effect, only removes friendly pieces without friendly replacement, or
  shifts the Support/Opposition difference in favor of the enemy side.
- The same manual, §8.3.5 (lines 202–207): free Commands use the recipient
  faction's priorities; multiple free Commands use the first Command's
  priorities. These are selection rules, not permission to see future
  Battle results.
- Sections 8.4, 8.5, 8.6, and 8.7 explicitly exclude free Battles from
  their favorable Support/Opposition Event-selection trigger. British and
  French casualty triggers may include a legal free Battle, subject to
  their specified Battle priorities; the grant is meaningful without
  knowing its eventual casualties.
- `Reference Documents/Manual Ch 5.txt`, §5.3 (lines 56–62): granted free
  Commands resolve immediately and retain other requirements unless the
  Event trumps them. Preview policy must not alter the live Event's order.
- `Reference Documents/card reference full.txt`: card 1 shaded (lines
  10–11) orders Patriot March and Battle before Propaganda and a Neutral
  shift; card 5 shaded (lines 62–63) grants Patriot March and Battle;
  card 48 unshaded (lines 611–612) grants British March to one space and
  permits Battle there.
- The user's Q24 ruling limits the advance effectiveness judgment to
  information available before Battle rolls. Prospective Battle losses,
  Win-the-Day shifts, and other outcome-dependent changes are not evidence
  for that judgment. Once selected, the Event remains selected even if the
  later Battle outcome is adverse; there is no Event-to-Command pivot.

## Confirmed mismatches before editing

`BaseBot._is_ineffective_event` runs the card handler on a copy of the live
seeded RNG. A handler such as card 5's can execute Battle immediately in
that copy, allowing a future combat roll and resulting board changes to
determine the advance Event judgment. Copying RNG prevents live-state
mutation but does not make the unknown roll information available to the
bot.

The queued path is different: `_complete_noncombat_preview` resolves a
second copy but discards its whole result if Battle dice were rolled.
Consequently, when card 1's Battle is possible, its deterministic printed
Propaganda and Neutral follow-ups are omitted from the final effectiveness
evidence. This makes direct and queued Battles follow different advance
policies. A declined Battle already exposes those follow-ups and correctly
allows an otherwise harmful Neutral shift to veto the Event.

Simply completing all queues with ordinary combat would extend the first
defect to queued Battles. Simply stopping at Battle would retain the
second defect. Neither implements the supplied ruling.

## Correction scope

Use a preview-only shared Battle boundary. Plan legal granted Commands by
the existing rules and apply their deterministic, pre-roll changes; do not
resolve combat dice or predict Battle-generated changes in the preview.
This boundary excludes all prospective Battle effects, even when the
Force Levels require zero D3 rolls. After checking legality, the preview
records the Battle offer before ally payments, activation, resolution,
or callbacks; it does not forecast these effects.
Record a legal offered Battle as a possible meaningful Event benefit, so a
Battle-only grant is not mistaken for no effect merely because its losses
have not been rolled. A genuinely impossible or declined Battle provides
no such benefit.

Continue deterministic printed follow-ups on the resulting known-board
preview. In particular, judge card 1's one-level Neutral shift without a
speculative Win-the-Day shift changing its starting political level. A
possible favorable Battle cannot rescue an otherwise enemy-favoring known
shift. Conversely, an adverse actual Battle must not retroactively turn an
accepted pre-roll decision into an illegal choice.

Track actual Battle Commands independently of the D3-roll counter in audit
evidence. A zero-die Battle is still actual Battle resolution and must not
be mistaken for a completed non-Battle Event whose result can be used to
reject the earlier choice retrospectively. This outcome distinction never
overrides the advance veto for an enemy-favoring known preview.

The preview cannot invent a human player's granted-Command choices.
Random Spaces tie-breaking and prescribed flowchart D6 questions remain
normal selection procedures; they are not future Battle outcomes. Recheck
effectiveness when those procedures change the actual Event target, still
without combat lookahead.

Keep preview controls off live state and outside semantic effect/removal
comparisons. Preserve all live card effects, combat resolution, linked
destinations, free costs, Eligibility, and printed order. A shared helper is
required because handlers can invoke Battle directly or queue it; no
card-specific rewrite or balance tuning is part of this correction.

## Required regression evidence

Test both direct and queued granted Battles, including card 1 follow-ups,
card 5's Battle-only grant, and card 48's linked destination. Advance
choices and recorded preview deltas must not depend on future Battle dice,
and the preview must not roll those dice at all. Exercise legal Battle,
genuine decline, deterministic enemy-favoring follow-ups, question-space
target changes, human-choice boundaries, and zero-die Battle resolution.
After acceptance, test that
the real Event resolves its Battle and remaining effects in printed order
even when the rolled result is adverse. Run the full test suite and
zero-player invariant gates before publication.

## Verification after implementation

- Full suite: `python -m pytest -q` — 1,917 tests passed, including 19 new
  Q24 regressions. The tests cover real cards 1, 5, and 48, copied-state
  isolation, no future Battle rolls, known harmful follow-ups, impossible
  grants, legal Fort-only Battle spaces, binding adverse outcomes, and
  actual zero-die Battles.
- `python -m mypy lod_ai/util lod_ai/board` — no issues in 23 source files.
- `python -m lod_ai.tools.clean_sweep_gate --seeds 1-20` — 60 clean games.
- The balance matrix for seeds 1–20 produced the existing 60-game baseline
  exactly; no baseline change or priority tuning was necessary.
- `PYTHONHASHSEED=0 python -m lod_ai.tools.soak --games 150 --seed-base
  10000 --invariants --out <scratch-output>` — 150 clean games (50 each
  scenario, seeds 10000–10049), 6,165 cards, zero runtime diagnostic errors
  or invariant violations. Six adverse actual Battle outcome observations
  were retained separately from errors. These are a focused follow-up,
  not a replacement for the earlier 1,500-game experiment.

No card handlers or source-of-truth files were modified. Shared execution
continues the literal live Event sequence; preview controls exist only on
copies. Actual Battle resolution is counted separately from D3 rolls,
and audit completion includes any queued immediate operations.
