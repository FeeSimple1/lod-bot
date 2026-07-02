# TRACEABILITY — Manual Ch 8 → code → tests

Purpose (ROADMAP.md Piece 1): rules→code coverage, so unimplemented rules
are visible. Historically audits went code→rules, which is how §8.3.6 (and
now §8.1 Commands-Not-Limited, T1) stayed silently wrong under green
dashboards.

Method: numbered-section inventory from `Reference Documents/Manual Ch
8.txt`; mechanical citation scan over `lod_ai/` (code) and both test
roots; hand verification of §8.1–§8.3.8 against the text (this pass,
Session 22). §8.4–§8.7 rows carry citation pointers and candidates only —
their verification passes are queued below.

Status legend: **OK** verified against the text · **PARTIAL** implemented
with identified deviations · **GAP** rule not implemented / violated ·
**UNVERIFIED** pointers exist, text not yet checked line-by-line · Txx =
backlog entry at the bottom.

Citation columns are from the mechanical scan (files containing the
section number); "cand:" entries are hand-supplied starting points where
no citation exists.

| § | Rule | Status | Code | Tests | Notes |
|---|------|--------|------|-------|-------|
| 8.1 | Non-Player Sequence of Play | PARTIAL (T1 **FIXED**) | bots/free_op_planner.py, bots/french.py, bots/indians.py, bots/patriot.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/shared.py, engine.py, tools/batch_smoke.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py, tests/test_pat_bot.py | T1 FIXED (Session 23): 'Commands Not Limited' — `engine._options_for_slot` (engine.py:554) applies `limited_only`/`special_allowed=False` to ALL seats; `base_bot.take_turn` propagates to `state['_limited']`/`_no_special` and engine.py:619-622 rejects >1 space / SA use. Per §8.1 a Non-player in a LimCom slot executes a FULL Command and SA. (Event-granted free LimComs ARE correctly capped at 1 space in the free-op path.) Other bullets: no-voluntary-removal OK by absence (no 1.4.1 voluntary-removal path exists for bots); sword-icon auto-ignore → T2; resource-cost fallthrough → T6; ToA BS numeric condition → T10; leader-follows-largest-group implemented (`indians.follow_indian_leaders_after_move`) but ties resolve to first neighbour in iteration order, not randomly, and 'moves from origin' is approximated post-hoc → T5. |
| 8.1.1 | Events, Commands, SAs — guidelines | PARTIAL | cards/effects/early_war.py, cards/effects/shared.py | — | 'Max extent' is convention across bots/planners (not centrally tested); 'most Support/Opposition = level x Pop' now explicit in `select_support_shift_spaces` (§1.6.2 double-Active falls out of the ±2 encoding). No general test asserts max-extent behaviour → Piece 4 property candidate. |
| 8.1.2 | Pieces and Resources | PARTIAL (T4, P1) | bots/free_op_planner.py, cards/effects/early_war.py, engine.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py | No shared placement/removal-order helper exists; each site hand-rolls. Removal alternation + spare-last-Tory implemented locally for card 6 only (Session 21). Placement order (Forts/Villages → Militia/WP → alternating cubes from fewest), removal order generally, move-Unavailable-first, remove-to-replace-even-without-replacements, March-Underground-first: all unaudited per site. Cited only in free_op_planner comments. |
| 8.1.3 | Selecting Spaces | OK | — | — | Priority-loop semantics implemented across bot command methods and free_op_planner; ties → §8.2 seeded (Session 21). No section-number citation in code (cite it when next touched). |
| 8.2 | Random Spaces | OK | bots/free_op_planner.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py, engine.py | tests/test_event_space_selection.py | `bots/random_spaces.py` — seeded from state['rng'], column-major arrow walk (fixed Session 21), top-space-first in two-space boxes, re-roll per extra space (`pick_random_spaces`). Equal-chance Play Note used by `free_op_planner._rand_choice` as sanctioned stand-in. Tested: test_event_space_selection.py. |
| 8.3 | Non-Player Events | OK | bots/base_bot.py, bots/british_bot.py, bots/free_op_planner.py, bots/french.py, bots/indians.py, bots/patriot.py, bots/random_spaces.py, cards/effects/brilliant_stroke.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py, tests/test_event_space_selection.py | Intro only; no normative content beyond 8.3.x below. |
| 8.3.1 | Event Instructions | PARTIAL (T2+T8, P1) | engine.py | — | `bots/event_instructions.py` implements musket directives, BUT non-British dicts are self-described 'pared-down' (Piece 3: transcribe full Brown Bess sheet). Second-faction instructions applying to granted free actions: NOT consulted by `engine._drain_free_ops` → T8. Sword auto-ignore: no icon data anywhere in code → T2. |
| 8.3.2 | Dual-Use Events | OK | cards/effects/shared.py | — | `base_bot._execute_event` / `_is_ineffective_event`: shaded iff dual and faction in {PATRIOTS, FRENCH}; force_shaded/unshaded directives override. `select_support_shift_spaces` mirrors it for side inference. |
| 8.3.3 | Ineffective Events | PARTIAL (T3, P1) | bots/base_bot.py, cards/effects/shared.py | tests/test_event_space_selection.py | No-effect simulation + net-shift-favors-enemy clause implemented (Session 21, `base_bot._is_ineffective_event`; tested). MISSING third clause: 'only effect would be to remove one or more friendly pieces without replacing them' → T3. |
| 8.3.4 | Event Placement | PARTIAL | cards/effects/early_war.py | — | Unavailable-first fixed at cards 32u/43u/46u (Session 21); every other place/relocate site unaudited → fold into Piece 3 card audit. |
| 8.3.5 | Events: Who/What/Where | PARTIAL (T7, P2) | bots/free_op_planner.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py, tests/test_event_space_selection.py | Shift routing → 8.3.6 OK (Session 21). Free-Command choices → faction priorities OK (free_op_planner + engine._plan_bot_free_op; card 84 Session 21). Maximise-Forts-then-pieces used for card 6. NOT generally implemented: who-gets-benefits ordering (executing → friendly → random enemy non-player first; harm → random enemy player first) and flowchart-question-spaces-first → T7, per-card audit in Piece 3. |
| 8.3.6 | Events that Shift Support/Opposition | OK | bots/base_bot.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py | tests/test_early_war_cards.py, tests/test_event_space_selection.py | `shared.select_support_shift_spaces` (Session 21): royalist/rebel two-level key, pop-weighted, zero-gain over negative-gain; §8.2 ties; instead-execute-C&SA guard via 8.3.3 net-shift test. Tested both sides + guard (test_event_space_selection.py). |
| 8.3.7 | Brilliant Stroke | UNVERIFIED (T10) | bots/british_bot.py, bots/french.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | — | BS infrastructure exists (base_bot get_bs_limited_command + per-bot overrides, engine interrupt). Unaudited: abort-if-no-Leader-LimCom, SA-independence clause, simultaneous-BS trump order, and the §8.1 ToA numeric condition (Squadrons WI + Avail FR Regs + CBC/2 > 15). |
| 8.3.8 | Other Event Choices | PARTIAL (T9, P2) | cards/effects/late_war.py | — | Cited at 2 late_war sites only. Default for uncovered event choices across 109 cards is frequently first/alphabetical — same class as the Session 21 finds. Audit in Piece 3. |
| 8.4 | Non-Player British Actions | UNVERIFIED | bots/british_bot.py, bots/free_op_planner.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.4.1 | Garrison | UNVERIFIED | engine.py | — | Citation-scan row; verification pass queued (see below). |
| 8.4.2 | British Muster | UNVERIFIED | cand: british_bot._muster (flowchart B: cites node labels, not §) | — | No §-citation in code. cand: british_bot._muster (flowchart B: cites node labels, not §). |
| 8.4.3 | British March | UNVERIFIED | bots/free_op_planner.py, engine.py | — | Citation-scan row; verification pass queued (see below). |
| 8.4.4 | British Battle | UNVERIFIED | cand: british_bot._battle + commands/battle bot_battle_scores (B12; audited Sessions 19-20) | — | No §-citation in code. cand: british_bot._battle + commands/battle bot_battle_scores (B12; audited Sessions 19-20). |
| 8.4.5 | Reward Loyalty | UNVERIFIED | util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.4.6 | Indian Trade SA | UNVERIFIED | cand: bot_indian_trade wired per CLAUDE.md (commit 9155880) | — | No §-citation in code. cand: bot_indian_trade wired per CLAUDE.md (commit 9155880). |
| 8.4.7 | British Supply | UNVERIFIED | cand: winter-quarters/supply phase — locate; engine._supply_phase | — | No §-citation in code. cand: winter-quarters/supply phase — locate; engine._supply_phase. |
| 8.4.8 | West Indies Battle | UNVERIFIED | cand: engine §6.2.2 WI battle call (CLAUDE.md note) — verify British-control condition | — | No §-citation in code. cand: engine §6.2.2 WI battle call (CLAUDE.md note) — verify British-control condition. |
| 8.4.9 | British Leader Redeployment | UNVERIFIED | cand: leader redeploy logic — locate (winter_quarters.py?) | — | No §-citation in code. cand: leader redeploy logic — locate (winter_quarters.py?). |
| 8.4.10 | Loyalist Desertion | UNVERIFIED | cand: desertion phase — locate | — | No §-citation in code. cand: desertion phase — locate. |
| 8.4.11 | British Brilliant Stroke | UNVERIFIED | cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.5 | Non-Player Patriot Actions | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_pat_bot.py, tests/test_year_end.py, tests/test_battle_selection.py | Citation-scan row; verification pass queued (see below). |
| 8.5.1 | Patriot Battle | UNVERIFIED | bots/patriot.py | tests/test_pat_bot.py, tests/test_battle_selection.py | Citation-scan row; verification pass queued (see below). |
| 8.5.2 | Rally | UNVERIFIED | bots/free_op_planner.py, bots/patriot.py, engine.py | tests/test_bot_free_ops.py, tests/test_pat_bot.py | Citation-scan row; verification pass queued (see below). |
| 8.5.3 | Rabble-Rousing | UNVERIFIED | bots/patriot.py | tests/test_pat_bot.py | Citation-scan row; verification pass queued (see below). |
| 8.5.4 | Patriot March | UNVERIFIED | bots/free_op_planner.py, bots/patriot.py, engine.py | — | Citation-scan row; verification pass queued (see below). |
| 8.5.5 | Patriot Supply | UNVERIFIED | cand: supply phase — locate | — | No §-citation in code. cand: supply phase — locate. |
| 8.5.6 | Patriot Leader Redeployment | UNVERIFIED | cand: leader redeploy — locate | — | No §-citation in code. cand: leader redeploy — locate. |
| 8.5.7 | Patriot Desertion | UNVERIFIED | cand: desertion — locate | — | No §-citation in code. cand: desertion — locate. |
| 8.5.8 | Patriot Brilliant Stroke | UNVERIFIED | bots/patriot.py, cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.5.9 | Committees of Correspondence | UNVERIFIED | util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.6 | Non-Player French Actions | UNVERIFIED | bots/free_op_planner.py, bots/french.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_french_bot.py, tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.6.1 | Roderigue Hortalez et Cie | UNVERIFIED | cand: french.py RH et Cie pre-ToA (cites F-nodes) | — | No §-citation in code. cand: french.py RH et Cie pre-ToA (cites F-nodes). |
| 8.6.2 | French Agent Mobilization | UNVERIFIED | cand: french.py agent mobilization (QUESTIONS.md Q12) | — | No §-citation in code. cand: french.py agent mobilization (QUESTIONS.md Q12). |
| 8.6.3 | Roderigue Hortalez et Cie | UNVERIFIED | cand: french.py RH et Cie post-ToA | — | No §-citation in code. cand: french.py RH et Cie post-ToA. |
| 8.6.4 | French Muster | UNVERIFIED | cand: french.py muster | — | No §-citation in code. cand: french.py muster. |
| 8.6.5 | French March | UNVERIFIED | bots/free_op_planner.py, engine.py | tests/test_bot_free_ops.py | Citation-scan row; verification pass queued (see below). |
| 8.6.6 | French Battle | UNVERIFIED | bots/french.py | tests/test_french_bot.py | Citation-scan row; verification pass queued (see below). |
| 8.6.7 | French Supply | UNVERIFIED | cand: supply — locate | — | No §-citation in code. cand: supply — locate. |
| 8.6.8 | West Indies Battle | UNVERIFIED | cand: engine WI battle (free=True fix in CLAUDE.md) | — | No §-citation in code. cand: engine WI battle (free=True fix in CLAUDE.md). |
| 8.6.9 | French Redeployment | UNVERIFIED | util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.6.10 | Loyalist Desertion | UNVERIFIED | cand: desertion — locate | — | No §-citation in code. cand: desertion — locate. |
| 8.6.11 | French Brilliant Stroke | UNVERIFIED | bots/french.py, cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.7 | Non-Player Indian Actions | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, commands/battle.py, engine.py, util/year_end.py | tests/test_errata_fixes.py, tests/test_indian_bot_fixes.py | Citation-scan row; verification pass queued (see below). |
| 8.7.1 | Raid | UNVERIFIED | cand: indians.py raid (I-nodes) | — | No §-citation in code. cand: indians.py raid (I-nodes). |
| 8.7.2 | Gather | UNVERIFIED | cand: indians.py gather + engine free-gather planner | tests/test_indian_bot_fixes.py | No §-citation in code. cand: indians.py gather + engine free-gather planner. |
| 8.7.3 | March | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, engine.py | tests/test_errata_fixes.py, tests/test_indian_bot_fixes.py | Citation-scan row; verification pass queued (see below). |
| 8.7.4 | Scout | UNVERIFIED | cand: indians.py scout | — | No §-citation in code. cand: indians.py scout. |
| 8.7.5 | Indian Supply | UNVERIFIED | cand: supply — locate | — | No §-citation in code. cand: supply — locate. |
| 8.7.6 | Patriot Desertion | UNVERIFIED | cand: desertion — locate | — | No §-citation in code. cand: desertion — locate. |
| 8.7.7 | Indian Leader Redeployment | UNVERIFIED | cand: leader redeploy — locate | — | No §-citation in code. cand: leader redeploy — locate. |
| 8.7.8 | Indian Brilliant Stroke | UNVERIFIED | cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.7.9 | Defending in Battle | UNVERIFIED | commands/battle.py | tests/test_indian_bot_fixes.py | Citation-scan row; verification pass queued (see below). |
| 8.8 | One-Player Victory | UNVERIFIED (T11) | — | — | No citations. Applies to human+bot seatings (human_qa covers 5 seatings but not victory-margin rules). Verify: lone player never wins mid-game Victory Phase; NP victory tie order French > Indian > Patriot; difficulty option unimplemented? |

## Flowchart nodes (B/P/F/I)

Not yet inventoried — next sub-step of Piece 1: extract every node from
the four `* bot flowchart and reference.txt` files and add rows mapping
node → bot method → tests. The bots cite node labels (B12, P4, F15, I8…)
rather than section numbers, which is why several 8.4–8.7 rows above show
no citation despite likely implementations.

## Backlog from this pass

- **T1 — FIXED (Session 23)** §8.1 Commands Not Limited:
  `engine._allowed_for_faction` now upgrades bot seats in LimCom slots to
  a full Command + SA (Event availability still per SoP); human seats
  keep SoP limits; event-granted free LimComs stay limited via the
  free-op path. Tested in `test_commands_not_limited_8_1.py`. The fix
  exposed and forced fixes for three latent §3.2.1 Muster bugs (see
  audit_report.md Session 23): Tory placement lacked the City/Colony
  type filter in BOTH the British bot and the executor (Tories could
  land in Reserves); the bot fabricated a zero-count Regular plan that
  pointed the executor's Regular-destination check at arbitrary spaces;
  and the executor's step-3 target fell back to an unbound Regular
  destination — with the B8-chosen Reward-Loyalty space never passed at
  all, RL silently executed (or was skipped) at the wrong space.
  Balance rebaselined: 33/60 pinned winners flipped — expected for a
  sequence-of-play-wide fix; 1776 remains Patriot-favoured (12/20).
- **T2 (P1)** §8.1/§8.3.1 sword-icon auto-ignore: no icon data exists in
  code (`grep -ri sword lod_ai` → nothing). Check every sword-underlined
  faction symbol in `card reference full.txt` against the per-faction
  event-condition tables; encode icon data and auto-ignore if not covered.
- **T3 (P1)** §8.3.3 missing clause: "only effect would be to remove one
  or more friendly pieces without replacing them" — extend
  `_is_ineffective_event` (piece-delta bookkeeping per faction).
- **T4 (P1)** §8.1.2 shared placement/removal helpers: build
  `nonplayer_place_order` / `nonplayer_remove_order` utilities
  implementing the full priority text; migrate card handlers and bot
  code site-by-site (Piece 3 companion; card 6 already compliant locally).
- **T5 (P2)** §8.1 leader-follow: neighbour ties resolve
  first-in-iteration (should be random); 'largest group that moves from
  origin' approximated by post-move board state
  (`indians._ops_leader_destination`).
- **T6 (P2)** §8.1 resource-cost fallthrough: bots PASS at 0 Resources at
  the top of take_turn; rule wants flowchart fallthrough to a Command it
  can afford (and partial execution when it can afford some instructions).
  Audit each flowchart's cost handling.
- **T7 (P2)** §8.3.5 benefit/harm target ordering (executing → friendly →
  random enemy non-player first; harm → random enemy player first): no
  general implementation; per-card audit (Piece 3).
- **T8 (P2)** §8.3.1 second-faction event instructions must govern how a
  faction executes actions granted by another faction's event;
  `engine._drain_free_ops` never consults `event_instructions`.
- **T9 (P2)** §8.3.8 random default for uncovered event choices: audit all
  handlers for first/alphabetical defaults (same class as Session 21
  finds; 2 sites cite 8.3.8 today).
- **T10 (P3)** §8.3.7 details: abort-if-no-Leader-LimCom, SA-independence,
  simultaneous-BS trump order, §8.1 ToA numeric condition — locate and
  verify each.
- **T11 (P3)** §8.8 one-player victory rules for human+bot seatings:
  verify or implement (lone player never wins mid-game; NP tie order
  French > Indian > Patriot; difficulty option).

## Verification pass queue

1. §8.4 + 8.4.1–8.4.11 vs `british_bot.py` (+ supply/desertion/redeploy
   phase code, wherever located — note several rows above lack even a
   candidate file).
2. §8.5 vs `patriot.py`, §8.6 vs `french.py`, §8.7 vs `indians.py`.
3. Flowchart-node inventory (above).
4. Ch 1–7 matrices (ROADMAP Piece 2).
