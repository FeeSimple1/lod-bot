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

## Piece 3 — Complete the card / flowchart-condition audit

Work the backlog from Pieces 1–2 plus the known items:
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

## Piece 5 — Decision coverage instrumentation

Count, during soak, which flowchart branches, card sides, and
card×executing-faction combos ever fire. Artifact: coverage matrix
report + targeted scenario tests (or bug fixes) for every never-fired
branch. A branch that never fires in 1,000+ games is either a
transcription error or untested in practice.

## Piece 6 — Playbook goldens  [UNBLOCKED]

The Playbook's Non-Player Examples of Play are official oracle data:
encode each documented setup and assert the bot makes the documented
choice. Source now in Reference Documents (`LOD_Playbook_Aug2016.pdf`
+ `Playbook Aug2016.txt`): five step-by-step Non-player walk-throughs
(pp. 19-27), all set at the start of the 1776 Medium scenario with
Patriots+French as the player. Also contains errata (blue text in the
PDF), the Event Text and Background section (useful cross-check for
the Piece 3 card audit), and Non-Player Designer's Notes. The Event
Instructions sheet wording is NOT in it — T12 stays blocked on Q15.

## Piece 7 — Human-mode completeness

- Enumerate every card-text player choice; diff against the override
  keys (63 today) and CLI prompts; any card whose choice silently
  falls through to bot selection for a human seat is a bug.
- CLI fuzzing: random inputs through the real `_game_loop`, undo at
  every prompt, save/load at every pause point, asserting round-trip
  state equality (extends `tools/human_qa.py`).

## Piece 8 — Statistical validation at scale

One large run (~1,000 games/scenario): win-rate confidence intervals,
game-length and resource-curve distributions, documented in-repo.
Future changes landing outside the intervals must be explained, not
just rebaselined. (The 60-game pinned baseline stays as the fast
canary.)

## Piece 9 — Hygiene / CI hardening

- CI (`ci.yml`) runs the clean-sweep gate and a bounded soak slice,
  not just pytest.
- Lint rule banning module-level `random` use in gameplay code
  (`base_bot.py` still carries a stale `import random`; discipline is
  currently by convention).
- mypy on `lod_ai/` (gradual, starting with util/ and board/).
- Repo cleanup per agents.md (stray artifacts, __pycache__).
