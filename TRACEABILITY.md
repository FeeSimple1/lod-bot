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
| 8.1.2 | Pieces and Resources | PARTIAL (helpers done, Session 27; migration in Piece 3) | bots/free_op_planner.py, cards/effects/early_war.py, engine.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py | No shared placement/removal-order helper exists; each site hand-rolls. Removal alternation + spare-last-Tory implemented locally for card 6 only (Session 21). Placement order (Forts/Villages → Militia/WP → alternating cubes from fewest), removal order generally, move-Unavailable-first, remove-to-replace-even-without-replacements, March-Underground-first: all unaudited per site. Cited only in free_op_planner comments. |
| 8.1.3 | Selecting Spaces | OK | — | — | Priority-loop semantics implemented across bot command methods and free_op_planner; ties → §8.2 seeded (Session 21). No section-number citation in code (cite it when next touched). |
| 8.2 | Random Spaces | OK | bots/free_op_planner.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py, engine.py | tests/test_event_space_selection.py | `bots/random_spaces.py` — seeded from state['rng'], column-major arrow walk (fixed Session 21), top-space-first in two-space boxes, re-roll per extra space (`pick_random_spaces`). Equal-chance Play Note used by `free_op_planner._rand_choice` as sanctioned stand-in. Tested: test_event_space_selection.py. |
| 8.3 | Non-Player Events | OK | bots/base_bot.py, bots/british_bot.py, bots/free_op_planner.py, bots/french.py, bots/indians.py, bots/patriot.py, bots/random_spaces.py, cards/effects/brilliant_stroke.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py, tests/test_event_space_selection.py | Intro only; no normative content beyond 8.3.x below. |
| 8.3.1 | Event Instructions | PARTIAL (P1) | engine.py | lod_ai/tests/test_t8_second_faction_instructions.py | `bots/event_instructions.py` implements musket directives, BUT non-British dicts are self-described 'pared-down' — but keys verified complete vs musket icons (Session 24); CONTENT audit unblocked: sheet text = the per-faction Special Instructions sections in the flowchart reference files (Piece 3). **T8 CLOSED (Session 69):** `engine._drain_free_ops` now threads the resolving card id to `_plan_bot_free_op`, which consults the GRANTED faction's Event Instruction via `_event_instruction()`.  Deck-wide the only unpinned granted op with an execution-shaping instruction is card 51 (force_if_51, British unshaded / Patriot shaded): its free March now targets a winnable Battle space (`battle.bot_march_battle_target`) per §8.3.5 'to set up Battle', instead of a generic destination.  All other grants pin their location (no 2nd-faction execution change) and card 52's battle_plus2 already routes through the Battle planner.  Sword auto-ignore implemented + data-verified (T2 closed, Session 24). |
| 8.3.2 | Dual-Use Events | OK | cards/effects/shared.py | — | `base_bot._execute_event` / `_is_ineffective_event`: shaded iff dual and faction in {PATRIOTS, FRENCH}; force_shaded/unshaded directives override. `select_support_shift_spaces` mirrors it for side inference. |
| 8.3.3 | Ineffective Events | OK (T3 fixed, Session 26) | bots/base_bot.py, cards/effects/shared.py | tests/test_event_space_selection.py | No-effect simulation + net-shift-favors-enemy clause implemented (Session 21, `base_bot._is_ineffective_event`; tested). MISSING third clause: 'only effect would be to remove one or more friendly pieces without replacing them' → T3. |
| 8.3.4 | Event Placement | PARTIAL | cards/effects/early_war.py | — | Unavailable-first fixed at cards 32u/43u/46u (Session 21); every other place/relocate site unaudited → fold into Piece 3 card audit. |
| 8.3.5 | Events: Who/What/Where | PARTIAL (T7, P2) | bots/free_op_planner.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py | tests/test_bot_free_ops.py, tests/test_early_war_cards.py, tests/test_event_space_selection.py | Shift routing → 8.3.6 OK (Session 21). Free-Command choices → faction priorities OK (free_op_planner + engine._plan_bot_free_op; card 84 Session 21). Maximise-Forts-then-pieces used for card 6. Q22 space-tie sweep CLOSED deck-wide (Session 68): every card-effect handler now resolves space ties via `random_spaces.pick_by_priority`/`pick_random_spaces` (the Random Spaces table), no rng embedded in any sort key.  STILL open → T7 (deferred to per-card Piece 3 audit): the general who-gets-benefits ordering (executing → friendly → random enemy non-player first; harm → random enemy player first) and flowchart-question-spaces-first. |
| 8.3.6 | Events that Shift Support/Opposition | OK | bots/base_bot.py, bots/random_spaces.py, cards/effects/early_war.py, cards/effects/late_war.py, cards/effects/shared.py | tests/test_early_war_cards.py, tests/test_event_space_selection.py | `shared.select_support_shift_spaces` (Session 21): royalist/rebel two-level key, pop-weighted, zero-gain over negative-gain; §8.2 ties; instead-execute-C&SA guard via 8.3.3 net-shift test. Tested both sides + guard (test_event_space_selection.py). |
| 8.3.7 | Brilliant Stroke | UNVERIFIED (T10) | bots/british_bot.py, bots/french.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | — | BS infrastructure exists (base_bot get_bs_limited_command + per-bot overrides, engine interrupt). Unaudited: abort-if-no-Leader-LimCom, SA-independence clause, simultaneous-BS trump order, and the §8.1 ToA numeric condition (Squadrons WI + Avail FR Regs + CBC/2 > 15). |
| 8.3.8 | Other Event Choices | PARTIAL (T9, P2) | cards/effects/late_war.py | — | Cited at 2 late_war sites only. Default for uncovered event choices across 109 cards is frequently first/alphabetical — same class as the Session 21 finds. Audit in Piece 3. |
| 8.4 | Non-Player British Actions | UNVERIFIED | bots/british_bot.py, bots/free_op_planner.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.4.1 | Garrison | VERIFIED (S55) | british_bot._garrison + helpers, commands/garrison.py | lod_ai/tests/test_brit_bot*.py, test_british_84_s55.py | Full clause inventory S55: zero deviations; S55 added §8.1 2-Resource gate + WI excluded from 10-Regular count. |
| 8.4.2 | British Muster | VERIFIED (S54, S55) | british_bot._muster | test_british_84_s54.py, test_british_84_s55.py | Line-by-line S54 (SA order fixed); S55 §8.1 pay-as-you-select budget cap. |
| 8.4.3 | British March | VERIFIED (S55) | british_bot._march, commands/march.py | test_brit_march_8_4_3.py, test_british_84_s55.py | B-node inventory S55: march-in-place Tory-stack fix; §8.1 budget trim; CC-to-Colony check confirmed correct (WP may not enter Cities). |
| 8.4.4 | British Battle | VERIFIED (S55) | british_bot._battle/_can_battle/_cc_battle_wp, commands/battle.py | test_british_84_s55.py | S55: B9 gate per §8.4.3 full comparison; CC ctx now reaches battle.execute (T13 class); pre-battle Skirmish exclusion. OPEN: Q19 (CC WP loss slot). |
| 8.4.5 | Reward Loyalty | VERIFIED (S44/S45, re-read S55) | util/year_end._support_phase, british_bot._muster RL step | tests/test_year_end.py | Marker-first, pop-weighted affordable shift, no-marker-only rule all present. |
| 8.4.6 | Indian Trade SA | VERIFIED (S54) | bot_indian_trade | test_british_84_s54.py | Gate, 1D6, half-round-up verified S54. |
| 8.4.7 | British Supply | VERIFIED (S51) | util/year_end.py supply phase | — | S51: CoC-prevention simulated, earnings-gated RL. |
| 8.4.8 | West Indies Battle | UNVERIFIED | cand: engine §6.2.2 WI battle call (CLAUDE.md note) — verify British-control condition | — | No §-citation in code. cand: engine §6.2.2 WI battle call (CLAUDE.md note) — verify British-control condition. |
| 8.4.9 | British Leader Redeployment | UNVERIFIED | cand: leader redeploy logic — locate (winter_quarters.py?) | — | No §-citation in code. cand: leader redeploy logic — locate (winter_quarters.py?). |
| 8.4.10 | Loyalist Desertion | VERIFIED (S54) | util/year_end.py desertion | test_british_84_s54.py | Per-Tory re-scored removal with control simulation (S54). |
| 8.4.11 | British Brilliant Stroke | UNVERIFIED | cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.5 | Non-Player Patriot Actions | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_pat_bot.py, tests/test_year_end.py, tests/test_battle_selection.py | Citation-scan row; verification pass queued (see below). |
| 8.5.1 | Patriot Battle | VERIFIED (S56) | bots/patriot.py | test_pat_bot.py, test_battle_selection.py, test_patriot_85_s56.py | P-node inventory S56: gate/selection/fees/SA cascade clean; PERSUASION fort tier fixed (binary + §8.2 ties). |
| 8.5.2 | Rally | UNVERIFIED | bots/free_op_planner.py, bots/patriot.py, engine.py | tests/test_bot_free_ops.py, tests/test_pat_bot.py | Citation-scan row; verification pass queued (see below). |
| 8.5.3 | Rabble-Rousing | UNVERIFIED | bots/patriot.py | tests/test_pat_bot.py | Citation-scan row; verification pass queued (see below). |
| 8.5.4 | Patriot March | VERIFIED (S45, S56) | bots/patriot.py | test_patriot_85_s56.py | S56 FIX: French escorts no longer capped at residual Control need ('as many as possible'); 1-for-1 legality cap (§3.3.2) confirmed. |
| 8.5.5 | Patriot Supply | UNVERIFIED | cand: supply phase — locate | — | No §-citation in code. cand: supply phase — locate. |
| 8.5.6 | Patriot Leader Redeployment | UNVERIFIED | cand: leader redeploy — locate | — | No §-citation in code. cand: leader redeploy — locate. |
| 8.5.7 | Patriot Desertion | UNVERIFIED | cand: desertion — locate | — | No §-citation in code. cand: desertion — locate. |
| 8.5.8 | Patriot Brilliant Stroke | UNVERIFIED | bots/patriot.py, cards/effects/brilliant_stroke.py, util/year_end.py | — | Citation-scan row; verification pass queued (see below). |
| 8.5.9 | Committees of Correspondence | UNVERIFIED | util/year_end.py | tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.6 | Non-Player French Actions | UNVERIFIED | bots/free_op_planner.py, bots/french.py, cards/effects/brilliant_stroke.py, engine.py, util/year_end.py | tests/test_bot_free_ops.py, tests/test_french_bot.py, tests/test_year_end.py | Citation-scan row; verification pass queued (see below). |
| 8.6.1 | Roderigue Hortalez et Cie | VERIFIED (S56) | french.py _hortelez/_preparer_la_guerre | test_french_bot.py | F-node inventory S56: gate, up-to-1D3 (Q16 ruling), pre-ToA Préparer both branches clean. |
| 8.6.2 | French Agent Mobilization | VERIFIED (S56) | french.py _agent_mobilization | test_french_86_s56.py | S56 FIX: lexicographic control-tier with simulated flip (was additive score); Quebec Militia legality cleared (§3.5.1 explicit). |
| 8.6.3 | Roderigue Hortalez et Cie | VERIFIED (S56) | french.py _hortelez/_skirmish_loop/_try_naval_pressure | test_french_86_s56.py | SA chain order + transfer gate verified (gate hardened S56); NP no-benefit interim per Q21. |
| 8.6.4 | French Muster | VERIFIED (S56) | french.py _muster/_can_muster | test_french_86_s56.py, test_french_bot.py | S56 FIX: fallback restricted to City/Colony with RC (§3.5.3 legality); can_afford gates (bs_free). |
| 8.6.5 | French March | VERIFIED (S56) | french.py _march | test_french_bot.py | S42 tiers hold; §8.1 trim present; S56 bs_free exemption. OPEN Q20: as-many-as-possible vs just-enough. |
| 8.6.6 | French Battle | VERIFIED (S56) | french.py _battle/_can_battle | test_french_86_s56.py | Naval-first SA order confirmed; S56: ally-free rescore when Patriot fee unfundable, bs_free trim, seeded pop ties; Leaders-not-pieces gate confirmed vs Glossary. |
| 8.6.7 | French Supply | VERIFIED (S33, re-read S56) | util/year_end.py | tests/test_year_end.py | Control-change payment + RL-prevention tier + highest-Pop verified current. |
| 8.6.8 | West Indies Battle | VERIFIED (S56) | util/year_end.py | tests/test_year_end.py | Pay-1-to-stay else Available verified. |
| 8.6.9 | French Redeployment | VERIFIED (S56) | util/year_end.py, french.py ops_redeploy_leader | tests/test_year_end.py | Leader priorities + Blockade redistribution implemented (least-Support removal, most-Support moves). |
| 8.6.10 | Loyalist Desertion | VERIFIED (S56) | french.py ops_loyalist_desertion_priority | — | French one-Tory most-Control priorities verified distinct from British §8.4.10. |
| 8.6.11 | French Brilliant Stroke | VERIFIED (S56) | french.py ops_bs_trigger | — | ToA + 4+ Regulars w/ Leader + eligibility condition verified. |
| 8.7 | Non-Player Indian Actions | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, bots/patriot.py, cards/effects/brilliant_stroke.py, commands/battle.py, engine.py, util/year_end.py | tests/test_errata_fixes.py, tests/test_indian_bot_fixes.py | Citation-scan row; verification pass queued (see below). |
| 8.7.1 | Raid | VERIFIED (S48/S51, sweep S57) | indians.py _raid/_raid_sequence, commands/raid.py | — | I3 die gate in dispatcher; Q18 mid-raid replenish conformant; last-WP-Village retention; priorities clean. |
| 8.7.2 | Gather | VERIFIED (S51, gate re-read S57) | indians.py gather | — | S51 body work holds; Q17 routing per ruling. |
| 8.7.3 | March | VERIFIED (S51, gate re-read S57) | indians.py march | — | S51 nodes hold (free first-Reserve, 0-Resource all-Reserve, bullet-4 counts). |
| 8.7.4 | Scout | VERIFIED (S57) | indians.py _scout_sequence, commands/scout.py | — | Gate, British-pays (§8.1 allied bullet), priorities clean. |
| 8.7.5 | Indian Supply | VERIFIED (S57) | util/year_end.py | — | Control-add tier, Gather-Village tier, move-to-nearest-Village verified. |
| 8.7.6 | Patriot Desertion | VERIFIED (S57) | indians.py + year_end.py | — | Indian-seat priorities (Village, control, last-of-type, random) verified distinct from §8.5.7/§8.4.10. |
| 8.7.7 | Indian Leader Redeployment | VERIFIED (S57) | indians.py | — | Brant/DC most-WP; Cornplanter Neutral/Passive 2+WP w/ Village room, fallback most-WP. |
| 8.7.8 | Indian Brilliant Stroke | VERIFIED (S57) | indians.py | — | ToA + 3+WP Leader + player-1st-or-Rebel-BS verified. |
| 8.7.9 | Defending in Battle | VERIFIED (S57) | commands/battle.py defender hook | — | All-but-1 UG WP when Village present; 0 otherwise; hook seat routing verified. |
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
- **T2 — CLOSED (Session 24), record corrected.** The Session 22 claim
  "no icon data exists in code" was a FALSE POSITIVE (case-sensitive
  grep): `base_bot._choose_event_vs_flowchart` implements the sword
  auto-ignore and `lod_ai/cards/data.json` carries `faction_icons` that
  match the reference ICON lines exactly on all 109 cards (verified).
  The musket-directive dicts also key exactly the musket-icon cards per
  faction — the "pared-down" comment was stale (one unreachable INDIANS
  entry for card 86, P-Musket only, removed). Permanent drift test:
  `test_icon_data_matches_reference.py`. Directive CONTENT remains
  unauditable in-repo → see QUESTIONS.md Q15 (sheet text needed).
- **T12 — FIXED (Session 25).** The Event Instructions sheet contents
  were in Reference Documents all along — the "Special Instructions"
  sections at the bottom of each `* bot flowchart and reference.txt`
  (Session 22/24 claims of a missing source corrected; the sections are
  keyed by card TITLE, which is why number-based greps missed them).
  Sheet wording for 18/44: "Target an Eligible enemy Faction. If none,
  choose Command & Special Activity instead." Fixed per the Glossary
  ("Enemy: assets of the other Side", 1.5.2): Royalist bots target
  {PATRIOTS, FRENCH}, Rebellion bots {BRITISH, INDIANS}; target chosen
  per §8.3.5 harm ordering (random enemy, player first) and passed to
  the card 18/44 handlers, which previously defaulted to BRITISH /
  PATRIOTS and could make the EXECUTOR ineligible. Handlers now
  side-aware when no explicit target. Also fixed while re-running the
  battery: the free-op battle planner approved French Battles pre-ToA
  that `battle.execute` rejects (§3.5) — now a genuine decline.
  Tests: `test_force_if_eligible_enemy.py` (6),
  `test_bot_free_ops.py::test_french_free_battle_pre_toa…`.
- **T3 — FIXED (Session 26).** §8.3.3 clause 2 implemented:
  `_only_removes_friendly_pieces` (exact state reconstruction — put the
  removed Side pieces back, restore their pool entries, compare;
  "friendly" spans the Side per Glossary/§8.3.5). Found and fixed a
  bigger latent bug in the process: `random.Random` compares by
  IDENTITY, so `before == after` was always False in any state carrying
  the seeded rng — the §8.3.3 "no effect at all" clause had been dead in
  every live game (unit tests passed because their states lacked rng).
  The comparison now drops rng/rng_log/history. Reviving the clause
  changed many event decisions (27/60 baseline flips; Indians 1775
  11→14, French 1778 9→13 — bots stop burning turns on null events).
  Tests: `test_ineffective_friendly_removal.py` (6).
- **T4 — helpers DONE (Session 27); per-site migration continues in
  Piece 3.** `lod_ai/util/nonplayer_pieces.py` transcribes all six
  §8.1.2 bullets: friendly placement order, friendly removal (cubes
  most-first alternation sparing the last Tory/Continental → Active
  before Underground → Forts/Villages), the move bullet
  (`pull_to_map` Unavailable-first + the Blockades/Forts/
  Continentals-Tories/Regulars return order), and the ENEMY bullet
  (Forts/Villages → Underground before Active → cubes fewest-first, no
  last-cube protection). The friendly/enemy distinction corrected two
  of this week's own fixes: Session 21 put card 6's enemy-Militia
  removal Active-first (friendly order) — reverted to
  Underground-first; Session 23's cube helper used most-first +
  last-Tory sparing on an enemy removal — now fewest-first without
  sparing. Cards 6/32u/43u/46u migrated; unit tests in
  `test_nonplayer_pieces_812.py` (9). Balance: zero pinned flips
  (checked over all 60, no rebaseline).
- **T5 — tie randomness FIXED (Session 29); moved-group tracking
  remains.** Ties among equal-size groups (including the origin group)
  now resolve by seeded random per §8.1. The "group that MOVED from
  origin" is still approximated by post-move WP counts — full fidelity
  needs move recording in the March/Scout/Gather/Raid executors
  (documented in `_ops_leader_destination`).
- **T6 — FIXED (Session 29).** The blanket 0-Resource PASS is
  flowchart-faithful for British/Patriots/French (explicit B3/P3/F3
  "Resources > 0?" nodes) but the INDIAN flowchart has no such node —
  it handles 0 Resources inline (I8 Trade; Raid's mid-command
  Plunder/Trade). Indians are now exempt from the blanket gate, which
  exposed and forced two §8.1 affordability fixes: `_can_scout` never
  checked the INDIAN half of Scout's cost (§3.4.3: both factions pay
  1), and the Indian March had NO affordability guard (march.execute
  raised) nor did it ever claim §3.4.2's free first destination for
  all-Reserve origins — the bot now trims destinations to budget and
  passes the `all_reserve_origin` flag. Remaining under T6: the Raid
  node's mid-command "Plunder then Trade before completing" (I-flowchart)
  is unverified.
- **T7 (P2)** §8.3.5 benefit/harm target ordering (executing → friendly →
  random enemy non-player first; harm → random enemy player first): no
  general implementation; per-card audit (Piece 3).  PARTIAL PROGRESS
  (Session 68): the §8.2 *space-tie* half is now closed deck-wide — every
  card handler resolves ties via the Random Spaces table (Q22), no rng in
  any sort key.  The benefit/harm *who* ordering remains the Piece 3 item.
- **T8 (P3) FIXED (Session 69).** §8.3.1 second-faction event
  instructions now govern how a faction executes actions granted by
  another faction's event.  `engine._drain_free_ops` threads the
  resolving card id into `_plan_bot_free_op`, which looks up the GRANTED
  faction's Brown-Bess instruction via `_event_instruction()`.  The one
  deck-wide unpinned grant with an execution-shaping directive is card 51
  (force_if_51): its free March is now sent "to set up Battle" via
  `battle.bot_march_battle_target` (the winnable Battle space with the
  most defenders, Q22 ties).  Every other grant pins its location, and
  card 52's battle_plus2 already routes through the Battle planner.
  Fixing this also exposed and closed a pre-existing partisans
  planner/executor divergence (the free-op planner counted a British Fort
  as a removable Royalist and picked option 1 in a Fort-only space, which
  partisans.execute rejects — gate 1775:12).  Tests:
  test_t8_second_faction_instructions.py.
- **T9 — FIXED (Session 48).**  All catalogued sites reworked per card
  text (16, 19, 24, 27, 28, 33, 72, 75, 79, 90, 91, 96 + card 80's in
  Session 47); collateral: pick_cities/pick_colonies read a "type" key
  real states never carry — returned [] in every real game (card 32
  shaded always paid 0).  Original catalogue below for reference.
  Grep sweep found ~20 first/alphabetical subset selections across the
  card handlers, essentially all card-specific SPACE selections
  (§8.3.5/§8.3.6/§8.2 territory, needing per-card text reads) rather
  than pure §8.3.8 misc choices: early_war.py lines ~275/403/464/726/
  789/1069, late_war.py ~156/168/204/209/340/351/803/1013, middle_war.py
  ~582/596/1094. Each goes through the agents.md card workflow with the
  Piece 3 audit.
- **T10 (P3)** FIXED (Session 50) — bot ToA declaration existed nowhere
  (French never entered the war in bot 1775/1776 games; French win rate
  was structurally 0%); §8.1 half-CBC NP preparations + §2.3.9
  Available-only Squadron counting implemented; bot BS SAs actually
  execute now (space=None dispatch had silently skipped every one).
  Verified: trump order + S34 re-poll, abort-if-no-Leader-LimCom,
  no-WQ/before-1st-action gates.  Residual: second LimCom is a
  battle/muster/rally approximation (not flowchart re-entry); SA
  pairing is a fixed chain; Leader-origination nuance for
  March/Scout/Raid/Garrison LimComs.
- **T11 (P3)** §8.8 one-player victory rules for human+bot seatings:
  verify or implement (lone player never wins mid-game; NP tie order
  French > Indian > Patriot; difficulty option).

- **T13 (P2)** FIXED (Session 41): B51/P51 force-conditions rebuilt on
  `battle.bot_march_sets_up_battle` (bot_battle_scores over a simulated
  all-origins March).  B52/P52 carry no battle math after the Session 28
  errata rewrite.
- **T14 (P2)** FIXED (Session 47) — all 16 Session-28 sites verified/
  implemented (B23, B30+EI layer, B29/P29/I29, B52/P52, B80/I80 incl.
  the executor-self-target bug, P83/F83 Quebec City reconciliation,
  I86/P86, B88/P88/I88/F88, I89/F89, B95, I21, I22, +F73 side-aware
  order).  Residual: card 88's destination uses a March-priority
  proxy (gain Control, else most friendly pieces, seeded) rather than
  each bot's full March planner — revisit if Piece 4 property tests
  flag it.
- **T15 (P3)** FIXED (Session 41): P80 (Village-would-be-removed via the
  handler's 2-removal order), F73/F95 (British Fort within the card's
  removable spaces), F83 (simulated 3-piece placement vs the §1.7
  tally) — all tightened by simulation.

## Verification pass queue

1. §8.4 + 8.4.1–8.4.11 vs `british_bot.py` (+ supply/desertion/redeploy
   phase code, wherever located — note several rows above lack even a
   candidate file).
2. §8.5 vs `patriot.py`, §8.6 vs `french.py`, §8.7 vs `indians.py`.
3. Flowchart-node inventory (above).
4. Ch 1–7 matrices (ROADMAP Piece 2) — DONE Session 46: see
   `TRACEABILITY_CH1_7.md` (C-series backlog lives there; C1/C2 fixed
   same session).
