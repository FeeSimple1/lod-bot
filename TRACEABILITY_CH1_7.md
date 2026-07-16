# TRACEABILITY_CH1_7 — Manual Ch 1-7 → code → tests

Purpose (ROADMAP.md Piece 2): rules→code coverage for the game rules
proper, same treatment as the Ch 8 matrix in TRACEABILITY.md. The
§1.6.2 Active-counts-double and §1.9 FNI-ceiling class of rules live
here.

Method (Session 46): numbered-section inventory from `Reference
Documents/Manual Ch 1-7.txt`; mechanical citation scan over `lod_ai/`
and both test roots (files containing the section number, lookaround-
guarded); hand verification this pass of Ch 1 (all sections), Ch 2
(2.2-2.3.5 spot checks incl. pass bonuses), Ch 5, Ch 6.3/6.4/6.6/7.x
line-by-line, plus rows carried by prior session audits (cited).
Remaining rows carry pointers only — see the verification queue.

Status legend: **OK** verified against the text (this pass or a cited
session) · **PARTIAL** implemented with identified deviations · **GAP**
rule not implemented / violated · **UNVERIFIED** pointers exist, text
not yet checked line-by-line · **—** no engine-relevant content ·
Cxx = backlog entry at the bottom (C-series = Ch 1-7; T-series lives
in TRACEABILITY.md).


## Ch 1 — Concepts & Components

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 1.1 | Course of Play | OK | — | — | Intro; normative content lives in 2.x/6.x rows. |
| 1.2 | Components | UNVERIFIED (C8) | rules_consts.py, util/caps.py | — | No §1.2 in the extracted Ch 1 text; caps.py cites §1.2 for CAP_TABLE global piece totals — verify counts vs the Available Forces Table (p.35) → C8. |
| 1.3 | The Map | OK | bots/british_bot.py | — | map/adjacency.py + map_base data; long-exercised. |
| 1.3.1 | Map Spaces | OK | special_activities/trade.py | — | Types Province(Colony/Reserve)/City modeled in map data. |
| 1.3.2 | Provinces (Pop 0-2) | OK | — | — | population() used throughout; §8.1.1 weighting sessions 44-45. |
| 1.3.3 | Cities (Pop 1-2) | OK | — | — | Naming note (Quebec City vs Quebec) is the T14 F83 reconciliation. |
| 1.3.4 | Indian Reserves | OK | — | — | type=Reserve; 0 pop; Militia/support guards cite it (rally, shift_support). |
| 1.3.5 | Colonies (11 spaces) | OK | — | — | Map data. |
| 1.3.6 | Adjacency | OK | — | — | map/adjacency.py adjacent_spaces(); symmetric per map_base. |
| 1.3.7 | West Indies | UNVERIFIED | — | — | Holding box 'not in play until after ToA' — WI battle/march/FNI paths gate on toa_played, but no single not-in-play guard; verify per-path (queue). |
| 1.3.8 | (no such § in source text) | — | — | — | Section absent from Reference Documents text. |
| 1.3.9 | Unavailable boxes | UNVERIFIED | — | — | French Unavailable + British Release Date (6.5.3) paths exist; verify vs scenario set-up. |
| 1.4 | Pieces | OK | bots/patriot.py, cards/effects/middle_war.py, commands/battle.py, special_activities/partisans.py, tools/gather_decline_audit.py | t/test_battle_modifiers.py, t/test_pat_bot.py, t/test_patriot_block_s45.py, t/test_special_activities.py, t/test_battle_selection.py | Tag model in rules_consts. |
| 1.4.1 | Availability and Removal | OK (C6 closed S76, C8 verified S66) | cards/effects/early_war.py | — | Pool model + add_piece clamps OK; casualties routing OK (1.6.4). MISSING: voluntary take-own-pieces-from-map when type not Available (exception: not B/F Regulars) — no path anywhere → C6; 'replace with unavailable piece = simply remove' is per-site (5.1.1) → Piece 3. |
| 1.4.2 | Stacking | PARTIAL | bots/patriot.py, util/caps.py | t/test_pat_bot.py, t/test_smoke_zero_player_fixes.py | enforce_global_caps trims: ≤2 Fort/Village per space, WI occupancy whitelist, Indian-no-City. Enforcement is post-hoc TRIM, not placement-time refusal — planners must pre-check (Session 30 _fort_room lesson); refusal exists in rally/muster paths. |
| 1.4.3 | Underground/Active | OK | cards/effects/early_war.py | — | New Militia/WP placed Underground (rally _place_militia→MILITIA_U, muster, gather); moves preserve state (march 3.3.2 note); flip helpers for Activate. |
| 1.5 | Players & Factions | OK | — | — | Faction constants; human/bot seating via engine.set_human_factions. |
| 1.5.1 | Sides | OK | — | — | REB/ROY prefixes throughout (control.py, bots). |
| 1.5.2 | Friends and Enemies | OK | bots/base_bot.py, bots/british_bot.py, cards/effects/late_war.py, util/nonplayer_pieces.py | t/test_force_if_eligible_enemy.py, t/test_ineffective_friendly_removal.py | Battle/Skirmish/War Path/Partisans target enemy-side tags only (verified for Partisans/Skirmish in Session 45; battle sides fixed by construction). |
| 1.5.3 | Negotiation | — | — | — | Human-table rule; no engine content. Resource-transfer-only-by-rule holds (no transfer API). |
| 1.6 | Support/Opposition intro | OK | — | — | ±2..-2 encoding in rules_consts. |
| 1.6.1 | 5 levels; 0-pop always Neutral | OK | cards/effects/shared.py | — | shift_support refuses Reserve/Special (WI); no other 0-pop spaces exist in map data. |
| 1.6.2 | Active counts double | PARTIAL (C1) | bots/base_bot.py, cards/effects/shared.py, cli_display.py, tools/batch_smoke.py, victory.py | t/test_victory_casualties.py | ±2 encoding doubles Active in every total (victory, base_bot, batch_smoke) — OK. But §1.9 blockade-pop-0 missing from all three Total-Support sites → C1 (FIXED this session for the three total sites). |
| 1.6.3 | Total Support/Opposition | PARTIAL (C1) | bots/base_bot.py, cli_display.py, victory.py | t/test_bs_limited_command.py, t/test_pop_weighted_totals.py, t/test_victory_casualties.py | victory._summarize_board = sum(level×pop); same C1 blockade caveat (fixed this session). |
| 1.6.4 | Casualties, CBC/CRC | OK | board/pieces.py, commands/battle.py, state/setup_state.py | t/test_victory_casualties.py | increment_casualties per tag class; battle Forts return to Available but still count (battle.py:715 §3.6.7/§1.6.4); casualties→Available at Reset (6.7); counters never decrement. |
| 1.6.5 | Fort/Village tracks | OK | board/control.py, bots/free_op_planner.py | t/test_map_utils.py | Track is physical bookkeeping; counts derived by summing map (victory, income). |
| 1.7 | Control | OK | bots/british_bot.py, bots/indians.py, bots/patriot.py, commands/garrison.py | t/test_brit_bot_review.py, t/test_ch8_small_items.py, t/test_french_bot.py | board/control.py verified vs text this pass: REB if rebels>royalist; BRITISH if royalist>rebels AND ≥1 British piece; Indians-only never British control; Villages count as Indian pieces; leaders are markers (not counted) per Glossary. |
| 1.8 | Resources 0-50 | OK | — | — | economy/resources: spend floors at 0 & raises if short; add caps at 50. |
| 1.9 | FNI & Blockades | PARTIAL (C1-C4) | cards/effects/brilliant_stroke.py, cards/effects/shared.py, rules_consts.py, util/naval.py | t/test_fni_ceiling.py | Verified: FNI 0 pre-ToA + raise-ceiling ≤ Available Blockades (util/naval.adjust_fni); Garrison blockade checks (S38). Gaps: blockade-pop-0 for Support/Resource calcs → C1/C2 (fixed this session); one-blockade-per-City set model can't hold a 2nd marker → C3; March-to-blockaded-City restriction + FNI-3-no-Garrison unverified → C4. |
| 1.10 | Leaders | PARTIAL (C5, T10) | — | — | Follow-unit moves (indians helper, T5 ties); WQ redeploy 6.5.2 (S43, all four bots). MISSING: orphan rule — Leader in a space with no friendly pieces must move to a friendly space or Available immediately; no engine hook → C5. BS Leader-in-LimCom-space precondition → T10. NOTE: board/pieces.return_leaders cites 'Rule 6.1' but leaders live in state['leaders'], not spaces — dead code, never called. |

## Ch 2 — Sequence of Play

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 2.1 | Set-Up | UNVERIFIED | — | — | state/setup_state.build_state vs the three scenario reference files — bulk-verify in a dedicated pass (scenario refs are in Reference Documents). |
| 2.2 | Start / card flow | OK | — | — | engine.draw_card: one-ahead reveal, WQ swap-and-play (2.3.7); exercised every sim. |
| 2.3 | Event card: ≤2 factions act | OK | — | — | engine sequencing; test_eligibility.py. |
| 2.3.1 | Eligibility | OK | — | — | eligible/ineligible sets + eligible_next/ineligible_next; free ops don't touch eligibility (5.3/3.1.2 free-op path). |
| 2.3.2 | Faction Order | OK | — | — | Card faction_order drives 1st/2nd Eligible (engine). |
| 2.3.3 | Passing | OK | — | — | _award_pass: +2 BRI/FRE, +1 PAT/IND (verified this pass); passer stays Eligible; next-leftmost promotion in engine loop. |
| 2.3.4 | Options for Eligible | PARTIAL (C9) | engine.py | t/test_commands_not_limited_8_1.py, t/test_execute_ctx_boolean.py | 1st/2nd option matrix in engine._options_for_slot (T1 FIXED S23: LimCom slots full for bots per §8.1). 'Command qualifies as executed if ≥1 space selected' + RHeC ≥1-Resource exception — not explicitly modeled → C9. |
| 2.3.5 | Limited Command | OK | bots/british_bot.py, bots/patriot.py, commands/rally.py | t/test_brit_bot_review.py, t/test_commands_not_limited_8_1.py | 1 space / 1 destination / no SA enforced in commands (march/rally limited=) + engine slot flags (S23); §8.1 full-command carve-out for bots. |
| 2.3.6 | Adjust Eligibility | UNVERIFIED | — | t/test_execute_ctx_boolean.py, t/test_indian_bot_fixes.py | eligible_next/ineligible_next mechanics + BS all-Eligible reset exist; event stay-Eligible/render-Ineligible overrides per-card (Piece 3); verify pass. |
| 2.3.7 | Next Card / WQ swap | OK | — | — | engine.draw_card; WQ handled immediately (6.0). |
| 2.3.8 | Brilliant Stroke | UNVERIFIED (T10) | engine.py | — | BS infra + trump order + preconditions → T10 items. |
| 2.3.9 | BS - Treaty of Alliance | UNVERIFIED (T10) | cards/effects/brilliant_stroke.py, engine.py, state/setup_state.py | t/test_setup_casualties_from_scenario.py | ToA gating widely enforced (toa_played); numeric auto-play condition → T10. |
| 2.4 | Winter Quarters card | OK | — | — | year_end.run_winter_quarters phases 6.1-6.7. |
| 2.4.1 | Final Winter Quarters | UNVERIFIED | — | — | Final round omits 6.5-6.7 and ends at 6.4.3 (final_scoring exists); verify the omission wiring. |

## Ch 3 — Commands & Battle

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 3.1 | Commands in General | PARTIAL | bots/indians.py, util/caps.py | t/test_indian_bot_fixes.py | Pay-per-space in each command; 0-Resource bots → Pass (8.1 fallthrough T6); 'may select same space only once per Command' unverified per command. |
| 3.1.1 | Pawns | — | — | — | Physical aid; no engine content. |
| 3.1.2 | Free Commands | OK | — | — | free=True paths skip cost + eligibility (engine free-op path; §8.3.5/T8 caveats live in the Ch 8 matrix). |
| 3.2.1 | British Muster | UNVERIFIED | bots/british_bot.py, commands/muster.py | t/commands/test_muster.py, t/commands/test_muster_321_regressions.py, t/test_ch8_small_items.py, t/test_llm_harness.py, t/test_smoke_zero_player_fixes.py | commands/muster.py + t/commands/test_muster*.py; B-node planner audited S39-44 slices; §3.2.1 text pass queued. |
| 3.2.2 | Garrison | OK | bots/british_bot.py, commands/garrison.py, interactive_cli.py | t/commands/test_garrison.py, t/test_brit_bot_review.py | Rebuilt Session 38 vs §3.2.2 (origins any non-Blockaded space, net-flow planning, skirmished-City exclusion §8.4.1). |
| 3.2.3 | British March | PARTIAL (C4) | bots/british_bot.py, bots/free_op_planner.py, commands/battle.py, commands/march.py, engine.py | t/commands/test_march.py, t/test_bot_free_ops.py, t/test_brit_march_8_4_3.py, t/test_british_march_in_place.py | commands/march.py: city-network legality checks blockades; Session 39 two-profile planner. Blockaded-City march prohibition bullet (§1.9) → C4. |
| 3.2.4 | British Battle | OK | — | — | battle.py sides/scores audited Sessions 19-20, 28 errata; WI loss-level bullet in 3.6.5/3.6.6 rows. |
| 3.3.1 | Rally | OK | bots/free_op_planner.py, bots/patriot.py, commands/rally.py, engine.py | t/commands/test_rally.py, t/test_bot_free_ops.py, t/test_patriot_block_s45.py, t/test_smoke_zero_player_fixes.py | commands/rally.py verified against §3.3.1 in Session 45 (place-one / fort-replace / bulk ≤ Forts+Pop / move-and-flip / Continental promotion; cost & Active-Support guards). |
| 3.3.2 | Patriot March | OK | bots/free_op_planner.py, bots/patriot.py, commands/battle.py, commands/march.py, engine.py | t/commands/test_march.py, t/test_patriot_block_s45.py | commands/march.py escorts 1-for-1, per-destination ally fees (Rochambeau waiver), militia activation on Brit-controlled-City entry >3 — verified in Session 45 planner work. |
| 3.3.3 | Patriot Battle | OK | bots/french.py, commands/battle.py | t/commands/test_battle.py | Costs + French involvement fees in battle.py (S19-20); Patriot-bot selection §8.5.1. |
| 3.3.4 | Rabble-Rousing | OK | bots/patriot.py, commands/rabble_rousing.py, rules_consts.py | t/test_pat_bot.py | commands/rabble_rousing per §3.3.4 (RC+piece/UG-militia select, Propaganda cap 12, activate-unless-RC+piece); §8.5.3 tier fixed S44. |
| 3.4.1 | Gather | UNVERIFIED | cards/effects/early_war.py, commands/gather.py, util/year_end.py | t/commands/test_gather.py, t/test_early_war_cards.py, t/test_static_property_fixes.py | commands/gather.py + Indian bot S30-40 fixes; §3.4.1 text pass queued (Village replace/move rules). |
| 3.4.2 | Indian March | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, commands/march.py, engine.py | t/commands/test_march.py, t/test_bot_free_ops.py, t/test_indian_bot_fixes.py, t/test_static_property_fixes.py | As 3.4.1; War-Parties-never-into-Cities enforced (CC fix S39 + caps). |
| 3.4.3 | Scout | OK | bots/indians.py, commands/scout.py, interactive_cli.py | t/commands/test_scout.py, t/test_ch8_small_items.py, t/test_indian_bot_fixes.py | Rebuilt Session 40 destination-first per flowchart + §3.4.3. |
| 3.4.4 | Raid | OK | commands/raid.py, interactive_cli.py, rules_consts.py | — | Q18 ruling implemented Session 40 (3-target select, mid-command Plunder/Trade, unpaid-space skip). |
| 3.5.1 | French Agent Mobilization | UNVERIFIED | bots/french.py, commands/french_agent_mobilization.py | t/test_bot_compliance.py | french.py + commands; Q12 resolved; text pass queued. |
| 3.5.2 | Roderigue Hortalez et Cie | UNVERIFIED | cards/effects/late_war.py, commands/hortelez.py | t/test_bot_free_ops.py, t/test_french_bot.py | Q16 (pre-ToA 1D3) resolved; 2.3.4 executed-exception → C9. |
| 3.5.3 | French Muster | OK | bots/french.py, commands/muster.py, engine.py, interactive_cli.py | t/commands/test_muster.py, t/test_bot_free_ops.py | Free-Muster planner fixed to §3.5.3 Session 38 (Colony/City/WI only); muster.execute type-validation gap noted in survey → French residual queue. |
| 3.5.4 | French March | OK | bots/free_op_planner.py, bots/french.py, commands/march.py, engine.py | t/commands/test_march.py, t/test_bot_planner_audit.py | §8.6.5 rebuild Session 42; ToA gate + Continental-escort fees in march.py (S45 read). |
| 3.5.5 | French Battle | OK | bots/french.py, commands/battle.py | t/commands/test_battle.py, t/test_battle_selection.py | battle.py ally fees; §8.6.6 priorities in french.py (WtD free-Rally return-None finding stays open in survey French #2). |
| 3.6.1 | Factional Cooperation | UNVERIFIED | commands/battle.py | t/commands/test_battle.py | Ally inclusion + fee model in battle.py; verify vs text (queue). |
| 3.6.2 | Definitions | OK | bots/british_bot.py, bots/french.py, bots/patriot.py, commands/battle.py | t/test_battle_mechanics.py, t/test_french_bot.py, t/test_pat_bot.py | Attacker/defender/side tallies (S19-20). |
| 3.6.3 | Force Levels | OK | bots/british_bot.py, commands/battle.py, interactive_cli.py, llm/harness.py | t/commands/test_battle.py, t/test_battle_mechanics.py, t/test_pat_bot.py, t/test_battle_selection.py | bot_battle_scores + FL maths audited S19-20/28; UG-militia exclusion, fort caps tested (test_pat_bot P4 suite). |
| 3.6.4 | Enemy Loss Level | UNVERIFIED | commands/battle.py | — | battle.py loss ladder; audited S19-20; keep pointer. |
| 3.6.5 | Defender Loss modifiers | UNVERIFIED | bots/british_bot.py, bots/patriot.py, commands/battle.py | t/test_battle_modifiers.py, t/test_pat_bot.py | Incl. WI Squadron +1 British Loss Level bullet (§1.9) — verify. |
| 3.6.6 | Attacker Loss modifiers | UNVERIFIED | bots/british_bot.py, bots/french.py, bots/patriot.py, commands/battle.py | t/test_battle_modifiers.py, t/test_pat_bot.py | As 3.6.5. |
| 3.6.7 | Removal | OK | commands/battle.py, util/piece_kinds.py | t/commands/test_battle.py, t/test_battle_mechanics.py | Removal order + Forts-return-to-Available-but-count (battle.py:715, §1.6.4) verified this pass. |
| 3.6.8 | Win the Day | OK | commands/battle.py, util/naval.py | t/commands/test_battle.py, t/test_piece_kinds.py | Q9 infra in battle.py (win_rally_space/win_blockade_dest); Patriot-bot wiring gap tracked in survey #4 / audit_report. |

## Ch 4 — Special Activities

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 4.1 | SAs in General | PARTIAL | bots/indians.py, bots/patriot.py | t/test_ch8_small_items.py, t/test_persuasion_once_per_turn.py | One SA per Command turn (_turn_used_special, _turn_persuasion_used); accompany-Command pairing restrictions are per-SA — CC March/Battle-only, French Skirmish/NP not-with-FAM: enforcement unverified (queue). |
| 4.2.1 | Common Cause | UNVERIFIED | bots/british_bot.py, commands/march.py, special_activities/common_cause.py | t/test_brit_march_8_4_3.py, t/test_special_activities.py, t/test_static_property_fixes.py, t/test_battle_selection.py, t/test_common_cause_b13.py | S39 CC fixes (group counts, WP march); §4.2.1 text pass queued (WP-as-Tories scope, activation). |
| 4.2.2 | British Skirmish | PARTIAL | bots/base_bot.py, commands/battle.py, special_activities/skirmish.py | t/test_patriot_block_s45.py, t/test_special_activities.py | Battle-space exclusion engine-enforced Session 45; Garrison-destination and Muster-space exclusions still unenforced (S45 residual). |
| 4.2.3 | Naval Pressure (British) | OK | special_activities/naval_pressure.py | t/test_special_activities.py | Pre/post-ToA branches + FNI lower + blockade-to-WI; most-Support pick pop-weighted S44. |
| 4.3.1 | Persuasion | OK | special_activities/persuasion.py | t/test_pat_bot.py, t/test_persuasion_once_per_turn.py, t/test_special_activities.py | persuasion.execute: ≤3 RC Colonies/Cities with UG Militia, activate 1, +1 Resource, Propaganda ≤12; bot priorities (Forts first) in _try_persuasion. |
| 4.3.2 | Partisans | OK | bots/base_bot.py, bots/free_op_planner.py, bots/patriot.py, cards/effects/middle_war.py, commands/battle.py, engine.py, special_activities/partisans.py | t/test_bot_free_ops.py, t/test_patriot_block_s45.py, t/test_special_activities.py | Session 45: Battle-space exclusion enforced; options 1/2 units-only (Glossary §1.4); option-3 gate = no War Parties + 2 UG Militia + Village. Residual: internal removal order is a fixed tag list vs §8.1.2-cited priorities (S45 audit note). |
| 4.3.3 | Patriot Skirmish | OK | bots/base_bot.py, bots/patriot.py, commands/battle.py, special_activities/skirmish.py | t/test_patriot_block_s45.py, t/test_special_activities.py | Session 45 Battle-space exclusion; options/eligibility verified (no-WI for Patriots). |
| 4.4.1 | Trade | UNVERIFIED | special_activities/trade.py | t/test_special_activities.py | S40 mid-Raid Plunder-else-Trade; §4.4.1 amount-choice text pass queued. |
| 4.4.2 | War Path | UNVERIFIED | bots/free_op_planner.py, bots/indians.py, engine.py, special_activities/war_path.py | t/test_bot_free_ops.py, t/test_special_activities.py | special_activities/war_path.py; text pass queued. |
| 4.4.3 | Plunder | UNVERIFIED | special_activities/plunder.py | t/test_special_activities.py | S40 usage; text pass queued. |
| 4.5.1 | Préparer la Guerre | UNVERIFIED | special_activities/preparer.py | t/test_special_activities.py | F2/F-node paths + S38 handoff notes; text pass queued. |
| 4.5.2 | French Skirmish | PARTIAL | bots/base_bot.py, commands/battle.py, special_activities/skirmish.py | t/test_patriot_block_s45.py, t/test_special_activities.py | Battle-space exclusion enforced S45; Muster-space exclusion + not-with-FAM pairing unenforced (residual). |
| 4.5.3 | Naval Pressure (French) | OK | cards/effects/shared.py, special_activities/naval_pressure.py, util/naval.py | t/test_special_activities.py, t/test_fni_ceiling.py | adjust_fni ceiling (§1.9); Squadron-from-WI placement / rearrange branches in naval helpers. |

## Ch 5 — Events

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 5.1 | Executing Events | PARTIAL | — | — | Handler-per-card model; literalness is the Piece 3 audit. |
| 5.1.1 | Event vs rules precedence | PARTIAL | — | — | Global guards hold regardless of card text: stacking trim, Available-only placement (add_piece), Resource 0-50 clamps, French-pre-ToA. Remove-rather-than-replace per-site → Piece 3. |
| 5.1.2 | Event vs Event precedence | — | — | — | No persistent-contradiction model needed yet; capabilities layer handles lasting effects — revisit in Piece 3 if a pair conflicts. |
| 5.1.3 | Implement what can be | PARTIAL | — | — | Handler convention; enforced per-card in Piece 3 audit. |
| 5.1.4 | Brilliant Stroke cards | UNVERIFIED (T10) | — | — | See 2.3.8/T10. |
| 5.2 | Dual Use | OK | — | — | §8.3.2 row OK (base_bot shaded/unshaded selection; force directives). |
| 5.3 | Free Commands | OK | — | — | free=True: no cost, no eligibility change (engine free-op path); second-faction instructions gap = T8. |

## Ch 6 — Winter Quarters

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 6.1 | Victory Check Phase | OK | board/pieces.py, llm/harness.py, tools/batch_smoke.py, util/year_end.py, victory.py | t/test_llm_harness.py | victory.check per §7.2 (verified this pass); called at WQ start; NP-pass consequences → C7. |
| 6.2 | Supply Phase | PARTIAL | board/pieces.py, rules_consts.py, util/year_end.py | — | Framework runs; §8.5.5 Patriot pay-every-space + §8.6.7 French move-vs-pay INVERTED remain open survey items (queue #4 residuals). |
| 6.2.1 | Extended Supply Lines | UNVERIFIED | util/year_end.py | t/test_year_end.py, t/test_year_end_ops.py | year_end supply sweep; in-supply definition (Fort/adjacent chains) — text pass queued with the supply survey items. |
| 6.2.2 | West Indies Battle | OK | util/year_end.py | t/test_year_end_wi_free_battle.py | Free French WI battle when both fleets present (free=True fix; test_year_end_wi_free_battle.py). |
| 6.3 | Resources Phase | PARTIAL (C2) | util/year_end.py | — | Verified this pass vs 6.3.1-6.3.4: British Forts+non-Blockaded-City pop+WI ✓; Indians ⌊Villages/2⌋ ✓; Patriots Forts+⌊RC spaces ex-WI/2⌋ ✓; French pre-ToA 2×WI-Blockades / post-ToA FNI+non-British-City pop+5 ✓ EXCEPT French city pop ignores §1.9 blockade-pop-0 → C2 (fixed this session). |
| 6.3.1 | British Earnings | OK | — | — | See 6.3. |
| 6.3.2 | Indian Earnings | OK | — | — | See 6.3. |
| 6.3.3 | Patriot Earnings | OK | — | — | See 6.3. |
| 6.3.4 | French Earnings | PARTIAL (C2) | — | — | Blockaded-City pop → C2 (fixed this session). |
| 6.4.1 | Reward Loyalty | OK | util/year_end.py | t/test_year_end.py | 6.4.1 mechanics + §8.4.5 sort (capped, S45); separate 2-level cap (S45); marker-then-shift order. |
| 6.4.2 | Committees of Correspondence | OK | util/year_end.py | t/test_patriot_block_s45.py, t/test_year_end.py | Session 45: Fort-only eligibility, own 2-level cap, capped pop-weighted potential, markers-only prohibition. |
| 6.4.3 | Game End | OK | engine.py, util/year_end.py | t/test_victory_casualties.py | final_scoring per §7.3 (verified this pass). |
| 6.5.1 | Leader Change | OK | rules_consts.py, util/year_end.py | — | LEADER_CHAIN + first-faction-on-upcoming-card + French-pre-ToA lock (read this pass). |
| 6.5.2 | Leader Redeployment | OK | bots/british_bot.py, bots/french.py, bots/indians.py, bots/patriot.py, util/year_end.py | t/test_wq_redeploy_6_5_2.py | Session 43 all-four-bots own-pieces scoping; order I,F,B,P handled in year_end. |
| 6.5.3 | British Release Date | UNVERIFIED | state/setup_state.py, util/year_end.py | t/test_year_end.py | Release-date paths exist (setup + WQ); verify vs scenario refs. |
| 6.5.4 | FNI drift (post-ToA) | UNVERIFIED | util/year_end.py | — | year_end lowers FNI 1 + Blockade→WI; 'French may rearrange remaining Blockades' — presence unverified; note the history string says 'toward War' (label check). |
| 6.6.1 | Patriot Desertion | OK | cards/effects/early_war.py, cards/effects/middle_war.py, util/year_end.py | t/test_early_war_cards.py, t/test_middle_war_cards.py, t/test_static_property_fixes.py | 1-in-5 each type (floor) ✓; Indians choose first (bot hook; support-max default for humanless) ✓; Patriot remainder re-scored per piece (S45). |
| 6.6.2 | Tory Desertion | PARTIAL | util/year_end.py | t/test_static_property_fixes.py | 1-in-5 ✓, French-first hook ✓; British remainder + French static sort survey residuals open (Loyalist Desertion static sort). |
| 6.7 | Reset Phase | OK | util/year_end.py | — | Markers cleared, all Eligible, casualties→Available, flip UG, reveal, WQ-card event hook (year_end; exercised every sim). |

## Ch 7 — Victory

| § | Rule | Status | Code (citation scan) | Tests | Notes |
|---|------|--------|----------------------|-------|-------|
| 7.1 | Ranking Wins & Ties | PARTIAL (C7) | tools/batch_smoke.py, victory.py | — | Tie order P>B>F>I implemented in final_scoring; MISSING: Non-players-first tie tier, 1st-4th placement ranking, all-players-lose-if-NP-passes-check, French-last-without-ToA (margin ranking aside) → C7/T11. |
| 7.2 | Victory Check | OK | state/setup_state.py, victory.py | t/test_victory_casualties.py | All four margin pairs verified vs text this pass (incl. ToA gate for French); Combined Victory (both-factions player) unmodeled → C7 note. |
| 7.3 | Final Scoring | OK | cli_display.py, engine.py, interactive_cli.py, llm/harness.py, util/year_end.py, victory.py | t/test_llm_harness.py, t/test_victory_casualties.py | Margin sums verified algebraically vs text this pass (the ±10 offsets cancel); French -inf without ToA. |


## Backlog (C-series)

- **C1** §1.9/§1.6.3 (FIXED Session 46): "The population of that City is
  considered 0 for purposes of calculating Support" — Total
  Support/Opposition ignored Blockades at all three total sites
  (victory._summarize_board, base_bot._support_opposition_totals,
  batch_smoke). Fixed via util/naval.effective_population.
- **C2** §1.9/§6.3.4 (FIXED Session 46): French after-ToA WQ income
  counted Blockaded-City population ("...and during the Resource Phase").
- **C3** §1.9 (RESOLVED — Eric ruled Q21, S60): the one-per-City SET model
  stands (the additional Blockade "has no additional impact", so the
  count is never board-relevant); non-player placement never targets an
  already-blockaded City, and the loud duplicate guards (S56) prevent the
  pre-S56 silent marker loss.  No count-model refactor.
- **C4** §1.9 (VERIFIED S66): FNI-3-blocks-Garrison present
  (british_bot._can_garrison, fni_level>=3 -> False).  March: the
  city-network route excludes Blockaded Cities (has_blockade in
  march._qual_city), and the bots ONLY generate adjacent marches (all
  destinations from map_adj.adjacent_spaces), which the rule's "unless
  destination adjacent to starting space" exception permits — so the
  prohibition is satisfied for every reachable bot path.  Muster
  legality (non-Blockaded City / adjacent Colony w/ a non-Blockaded
  City neighbour) verified in muster._is_legal_regular_dest.
- **C5** §1.10 (FIXED S66): the orphan rule is enforced in
  normalize_state._enforce_leader_orphan (runs after every mutation).
  An orphaned Leader relocates to the space with the MOST of its
  Faction's pieces (deterministic sorted-id tie, no rng — normalize
  stays pure), else Available.  Free on the hot path (profiled: 0.009s
  / 2000 calls).  test_leader_orphan_c5.py (4).
- **C6** §1.4.1 CLOSED (Session 76): the "no path anywhere" read was
  WRONG — place_piece._ensure_available auto-reclaimed own pieces from
  the map on EVERY pool-dry placement, bots included, violating Manual
  §8 "No voluntary removal" (Non-players NEVER use the 1.4.1 option).
  Now gated: the force owner must be a human seat AND the active
  executing faction (the rule's own scope); bots place what the pool
  holds (§5.1.3).  B/F-Regulars exception holds (not reclaim-eligible).
  Human interim: the pull auto-fires (maximises the placement);
  RESIDUAL: CLI prompt for the may-decline and which-piece choice.
  Tests: test_c6_voluntary_removal.py (4).
- **C7** §7.1/§7.2: Final ranking details — Non-players-first tie tier,
  1st-4th placement, all-players-lose-if-a-NP-passes-victory-check,
  French-last-without-ToA, Combined Victory for a both-factions player.
  Fold into T11 (§8.8 one-player victory) work.
- **C8** §1.2/§1.4.1 (VERIFIED S66): piece conservation checked
  programmatically — every scenario (1775/76/78) sums EXACTLY to the
  MAX_* constants across spaces+available+unavailable (BRI 25, Tory 25,
  FRE 15, PAT 20, Militia 15, WP 15, Forts 6/6, Villages 12).  CAP_TABLE
  holds only the Fort/Village "highest-numbered box" caps; cube totals
  are enforced by the Available pool model (conservation confirms it).
- **C9** §2.3.4 (VERIFIED S66): engine._command_effect_count returns the
  affected-space count and models the Roderigue-Hortalez ≥1-Resource
  exception explicitly (HORTELEZ + pay>=1 -> counts as 1); the LimCom
  legality check gates on affected==1, and executed/eligibility follow
  the count.
- **C10** §8.1.1×§1.9 (FIXED S66): the WQ Reward-Loyalty and Committees
  potential sites (year_end._support_phase) now use EFFECTIVE population
  (Blockaded City -> 0), so a blockaded City's RL/CoC "change in
  Support" ranks as 0.  The remaining raw-Population bot sites are
  within-tier RANKING keys where blockade-zeroing does not change
  legality or, in practice, ordering — left as-is (documented).
- **Dead-effect note**: board/pieces.return_leaders (called each WQ in
  year_end before redeploy, citing "Rule 6.1") scans spaces for leader
  TAGS, but real leaders live in state["leaders"] — a no-op in real
  games.  No manual text returns Leaders to Available at WQ (6.5.2
  moves them between friendly spaces), so the right fix when touched
  is deletion, not repair.

## Verification pass queue

1. Ch 3 command texts vs commands/*.py line-by-line (3.2.1 Muster,
   3.4.1/3.4.2 Gather/Indian March, 3.5.1/3.5.2, 3.6.1/3.6.4-3.6.6
   battle modifiers incl. the WI Squadron +1 bullet).
2. Ch 4 pairing restrictions (CC March/Battle-only; French not-with-FAM;
   British Garrison-dest/Muster-space Skirmish exclusions — S45
   residual) and 4.4.x Indian SA texts.
3. Ch 2: 2.3.6 adjust-eligibility overrides, 2.4.1 final-round phase
   omission wiring, C9.
4. Ch 6: 6.2.1 extended supply lines (with the open §8.5.5/§8.6.7
   survey items), 6.5.3 release dates vs scenarios, 6.5.4 rearrange.
5. 2.1 scenario set-up vs the three scenario reference files + C8.
