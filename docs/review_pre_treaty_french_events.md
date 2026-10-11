# Pre-Treaty French Event audit — October 2026

This audit was written before changing the affected card handlers, as
required by `agents.md` section 8. Only repository reference documents
were consulted. The reported reproduction is 1775, seed 10441: card 85
places French Regulars in Southwest before the Treaty, and card 66 later
produces a French March plan that the command executor rejects.

## Controlling sources

- Manual §5.1.1 expressly excludes placing French pieces on the map before
  Treaty of Alliance from the usual Event-overrides-rules principle.
- Manual §2.3.9 prohibits French deployment on the map and in the West
  Indies before the Treaty. The pre-Treaty Squadron preparation exception
  remains governed by §4.5.1; this audit concerns French Regulars.
- Manual §5.1.3 requires implementing the portions of an Event that can be
  implemented. An illegal French placement must not cancel legal Patriot
  placements or consume the French pieces from their source pool.
- Manual §5.3 preserves command requirements except where Event text
  overrides them; the command executor's Treaty prerequisite must also
  be reflected by its free-operation planner.

## Findings by card and file

| Card | Source text requirement | Observed implementation mismatch |
| --- | --- | --- |
| 85, `late_war.py` | Shaded places two Militia or Continentals and two French Regulars in Southwest, subject to §5.1.1. | The French placement is unconditional even before the Treaty. Legal Patriot placement must remain. |
| 50, `middle_war.py` | Shaded places two Continentals and two French Regulars from Available or West Indies in a Colony. | Both French source paths can deploy before the Treaty. Legal Continental placement must remain. |
| 57, `late_war.py` | Unshaded moves two French Regulars to West Indies and makes France Ineligible. | Its Available-to-West-Indies path ignores §2.3.9. The eligibility effect must remain. |
| 62, `late_war.py` | Shaded offers three French Regulars in Quebec or three Militia in Northwest. | The default selects the French option even before the Treaty; the legal Militia alternative should remain selectable. |
| 72, `early_war.py` | Places friendly units in an Indian Reserve. | Its fallback list includes Available French Regulars without the Treaty gate. |
| 83, `early_war.py` | Shaded places selected friendly pieces in Quebec or Quebec City. | Generic faction placement can select French Regulars before the Treaty. |
| 95, `late_war.py` | Places friendly units in Northwest. | The French/Patriot coalition placement loop can select French Regulars before the Treaty. |
| 66, `late_war.py` | Shaded grants French or Patriots a free March and Battle in Florida. | The default beneficiary may be French before the Treaty, while the free-March planner returns a plan that `march.execute` rejects. The handler comment incorrectly asserts that Treaty status is irrelevant. |

Cards 48, 55, and 68 also relocate existing French Regulars through the
same movement primitive. They cannot introduce such pieces from a valid
pre-Treaty state, but must not provide a bypass for an already-invalid
state. Card 49's movements between Available and Unavailable are legal
before the Treaty and must remain allowed. Treaty resolution sets the
Treaty flag before placing its own Regulars and therefore remains legal.

## Required implementation scope

1. Add a shared destination restriction in `board/pieces.py` for French
   Regulars, before any source debit, covering placement and relocation to
   map spaces including West Indies. Return zero moved, as with existing
   placement restrictions, so §5.1.3 partial Event execution continues.
2. Keep permitted movements among Available, Unavailable, and Casualties.
3. Remove card 66's unsupported comment and exclude pre-Treaty French from
   its automatic beneficiary choice; retain explicit player choices and
   represent an unavailable granted Command as a legal decline.
4. Prefer card 62's legal Militia branch when no explicit choice is supplied
   before the Treaty.
5. Make the French free-March planner decline before the Treaty, matching
   its executor; never pass an impossible plan through for suppression.
6. Record unexpected free-operation execution exceptions with their
   actual type/message so smoke gates distinguish errors from legal
   no-plan declines.

Regression coverage will verify the audited Event paths before and after
the Treaty, conservation of blocked source pieces, continued legal
Patriot/eligibility effects, the free-operation prerequisite, and the
reported seed. No source-of-truth files or balance baselines will change.

## Card 62 default-choice addendum (before this additional handler edit)

The post-Treaty default also always selects French Regulars, even when
Patriots execute the Event or no French Regulars are Available. Manual
§8.3.5 directs benefit choices to the executing Faction, then its ally;
§8.3.4 requires placing as many permitted pieces as possible. Automatic
selection must therefore prefer the executing Faction among legal,
nonempty placement branches, falling back to its ally when its own
branch cannot place any pieces. This does not replace the French bot's
specific F62 instruction to place Militia only, which is already passed
as an explicit `card62_shaded_choice` override. Explicit player choices
also remain intact.

## Validation

- Focused regression suite (new Treaty/Event regressions, middle/late-war
  handlers, and bot free operations): 86 passed after the card 62 addendum.
- Original reproduction `1775:10441`, with per-card invariants enabled:
  completed 40 cards with no crashes, bot errors, illegal actions,
  free-operation errors, or legacy free-operation skips.
- Initial diagnostic full-suite run: 1810 passed, one balance-canary
  failure. The canary reports changed winners for `1776:2` and `1778:2`;
  its baseline was not changed. This run overlapped other authorized
  fixes and preceded the final card 62 fallback refinement.
- Two existing card 50 fixtures now explicitly set `toa_played=True`
  because they seed French Regulars in West Indies and test their legal
  post-Treaty deployment. No further Treaty fixture failures appeared.
