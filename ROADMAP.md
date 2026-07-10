# ROADMAP — path to commercial-grade rules fidelity

Goal: an engine whose correctness is demonstrated against the Reference
Documents, not just against its own tests. The existing green
infrastructure (test roots, clean-sweep gate, invariant gate, soak,
balance canary) proves crash-freedom and state coherence; the pieces
below close the gap to rules fidelity. Ordered by leverage; each piece
is sized to one or a few working sessions and leaves a committed,
verifiable artifact.

## Piece 1 — Traceability matrix: Manual Ch 8 + bot flowcharts  [IN PROGRESS]

Map every numbered section of Ch 8 and every flowchart node
(B/P/F/I references) to the implementing code and tests.
Artifact: `TRACEABILITY.md`. Empty or weak cells become the audit
backlog for Piece 3. Rationale: audits have historically gone
code→rules (check a handler's citation); nothing goes rules→code, which
is exactly how §8.3.6 went unimplemented while every dashboard was
green. Status values: OK (verified against the text), PARTIAL, GAP,
UNVERIFIED (citation exists; not yet audited), N/A (rule has no
zero-player analogue).

## Piece 2 — Traceability matrix: Manual Ch 1–7

Same treatment for the game rules proper (sequence of play, commands,
SAs, battle, winter quarters, victory, leaders). Larger than Piece 1;
split by chapter. The §1.6.2 Active-counts-double and §1.9 FNI-ceiling
class of rules live here.

## Piece 3 — Complete the card / flowchart-condition audit  [PARTIAL — S73 closed the §8.3.5 residuals]

DONE (Session 73): the exhaustive per-card §8.3.5 who-choice audit
(all 109 cards; cards 29/48/67/74/87 routed onto util/target_order,
three hand-rolled sites verified conforming, ten what-choice-only),
the last 15 pre-Q22 tie sites in the four bot files (card-80 presets,
British garrison 2b/displacement, leader redeploys, Cornplanter,
loyalist desertion), and the §8.3.5 flowchart-question-spaces-first
bullet (state["_event_q_spaces"] threading; test_event_question_spaces).

Remaining backlog from Pieces 1-2 plus the known items:
- `event_instructions.py`: the PATRIOTS / INDIANS / FRENCH dicts are
  self-described "pared-down" versions of the Brown Bess sheet —
  transcribe the full reverse side of the Random Spaces sheet for all
  four factions and diff against the dicts.
- `event_eval.py`: audit every static capability flag against the four
  flowcharts' actual "Event or Command?" bullets (only B2 has had a
  dedicated session).
- Alphabetical / dict-order subset picks: `late_war.py` (~lines
  155/167/205/795/1005), `middle_war.py` (3 suspect sites), same
  §8.3.5/§8.3.6/§8.2 treatment as audit_report.md Session 21.
- `auto_place_blockade` stub: determine from the rules whether any
  trigger should auto-place Blockades, implement or delete.
- Cards never audited card-by-card (cross-check audit_report.md
  session lists against all 109).
Per agents.md: audit report first, then fixes, then validation tests.

## Piece 4 — Rules-derived property tests  [DONE, Session 67]

Extend `tools/invariants.py` (asserted per card in gate + soak) with
properties that encode rules rather than implementation:
- Piece conservation per type: map + available + unavailable +
  casualties + out_of_play is constant.
- Support bounds ±2; Reserves/West Indies always Neutral (§1.6.2).
- FNI ≤ blockade ceiling (§1.9/§4.5.3) — exists; keep.
- No bot-CHOSEN event nets a Support−Opposition shift favoring the
  bot's enemy side (§8.3.3) — post-hoc check on event plays.
- Control recomputation idempotence; Total Support/Opposition track
  equals recomputed pop-weighted sum.  (No stored track exists — totals
  are computed on demand — so only the control half applies.)
- Resources within [0, 50] (§1.7) — verify existing clamp coverage.

Landed (Session 67) as `check_rules_properties` in `tools/invariants.py`,
asserted per card in the gate, soak, and batch_smoke repro path (marker
baselines captured at setup).  First activation caught seven live bug
classes: Rabble-Rousing on Indian Reserves (§3.3.4 type gate missing,
bot + command), Propaganda/Raid marker destruction on re-placement
(place_marker + raid + rabble; Q23 logged for the stacking model),
Garrison displacement destroying a Militia via the Available-pool
variant double debit (move_piece/add_piece class fix), WQ Reward
Loyalty shifting the Quebec Reserve (§1.6.2 guards on RL/CoC) with the
C10 effective-pop fix missing on the RL side, WQ exit paths leaving
control stale, three Q22 rng-sort-key misses in year_end, and the
§8.3.3 net-shift gate using raw instead of §1.9 effective population.

## Piece 5 — Decision coverage instrumentation  [DONE, Session 67]

Count, during soak, which flowchart branches, card sides, and
card×executing-faction combos ever fire. Artifact: coverage matrix
report + targeted scenario tests (or bug fixes) for every never-fired
branch. A branch that never fires in 1,000+ games is either a
transcription error or untested in practice.

Landed (Session 67): `tools/coverage.py` collector fed from the
engine's `_card_turn_log` (+ new `_turn_event_side` /
`_turn_special_type` trace keys and per-SA name stamps); soak
`--coverage out.json` aggregates; report in `docs/coverage_s67.md`.
The 300-game matrix found: the French bot's inline Préparer never set
`_turn_used_special` (invisible to the §2.3.4/§2.3.5 slot matrix,
~4 uses/game); seven card handlers dead behind state-space
`get("type")` filters (cards 2/41 never executed, five more sides
never fired — the unswept S48 class); card 68's missing
`places_patriot_fort` flag; and the P2/F2 bullet evaluators reading
`effects["shaded"]` unconditionally, hiding all six single-sided
benefit cards (52/68/72/73/92/95) from Patriot/French bots.  Steady
state: every Ch 3 command and Ch 4 SA fires for every faction; the
only never-fired side is card 48 shaded, which is Sword-blocked for
every non-player and reachable only by a human (documented).
Flowchart NODE-level counters were scoped out: every §8.4–§8.7 row is
already text-verified (S55–S57) and golden-replayed; the remaining
value sits in card/SA/side coverage, which is what landed.

## Piece 6 — Playbook goldens  [DONE, Session 57-63]

All five Non-player walk-throughs are transcribed and replay green
in lod_ai/tests/test_playbook_goldens.py (Example 3 at exact piece
picks).  They are the project's deepest instrument — they found the
two biggest project-lifetime bugs after every flowchart row was
already "verified".  Original scope notes below.

The Playbook's Non-Player Examples of Play are official oracle data:
encode each documented setup and assert the bot makes the documented
choice. Source now in Reference Documents (`LOD_Playbook_Aug2016.pdf`
+ `Playbook Aug2016.txt`): five step-by-step Non-player walk-throughs
(pp. 19-27), all set at the start of the 1776 Medium scenario with
Patriots+French as the player. Also contains errata (blue text in the
PDF), the Event Text and Background section (useful cross-check for
the Piece 3 card audit), and Non-Player Designer's Notes. The Event
Instructions sheet wording is NOT in it — T12 stays blocked on Q15.

## Piece 7 — Human-mode completeness  [DONE, Session 73]

- Part 1 (card-choice audit, S72) + CLI wiring (S73) DONE:
  `lod_ai/event_choices.py` collects every choice-bearing card's player
  choices from a human Event player (space pickers, sub-options,
  faction targets, piece mixes, card 88's per-origin destination map)
  and applies them as the `card<N>_*` overrides the handlers already
  honor.  All 43 registry cards wired in three batches; candidate menus
  mirror each handler's own legality filters; choices the card text
  assigns to a named faction prompt only when that faction is a human
  seat (bot deciders keep their §8.3.x-faithful handler defaults).
  Gates: `tests/test_human_mode_completeness.py` (frozen registry) +
  `tests/test_event_choices.py` (registry-exact wiring, shapes,
  override-honor spot checks).
- Residual follow-up (out of the audited scope): free operations
  GRANTED to a human faction by an event (e.g. card 15's Patriot
  March/Battle/Partisans) are still bot-planned in `_drain_free_ops`
  rather than wizarded for the human seat.
- Part 2 (CLI fuzzing) already covered by `tools/human_qa.py`: it drives
  the real `_game_loop` with a scripted provider, injects undo at WQ and
  general prompts, and save/loads every card through
  `invariants.check_save_load_roundtrip`, which asserts exact
  canonical-state + RNG equality.  Green across all scenarios/seatings.

## Piece 8 — Statistical validation at scale

One large run (~1,000 games/scenario): win-rate confidence intervals,
game-length and resource-curve distributions, documented in-repo.
Future changes landing outside the intervals must be explained, not
just rebaselined. (The 60-game pinned baseline stays as the fast
canary.)

## Piece 9 — Hygiene / CI hardening  [DONE, Session 71]

- CI (`ci.yml`) now runs, as separate jobs: pytest, the clean-sweep gate
  (seeds 1-20 x3), the balance guardrail (seeds 1-20), a bounded soak
  slice (60 games, --invariants), and gradual mypy (util + board).
- Lint rule banning the process-global `random` module in gameplay code
  (draws must use the seeded `state["rng"]`, Q22): pytest test
  `tests/test_no_global_random.py`, with a self-test guarding the regex.
  Gameplay code was already clean; `base_bot.py`'s truly-stale
  `import random` (its last use went away with the T7 refactor) removed.
- Gradual mypy: `mypy.ini` (lenient, ignore_missing_imports) + a CI
  `typecheck` job enforcing `lod_ai/util` and `lod_ai/board` clean (two
  missing local annotations fixed).  Widen the CI scope as more of
  `lod_ai/` is annotated.
- Repo cleanup: removed 8 stale, unreferenced bot-error diagnostic dumps
  (`bot_error_log*.json`, `bot_error_analysis*.md`) and gitignored the
  pattern; __pycache__/*.pyc/*.jsonl already ignored.
