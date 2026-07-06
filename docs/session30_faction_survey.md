# Session 30 — §8.4–8.7 verification survey (agent-assisted, July 2026)

Four parallel audit agents compared each faction's Manual Ch 8 section
and flowchart against the bots. Method: full-section reads, clause-by-
clause, read-only. High-severity claims spot-checked by hand before
recording; three were fixed immediately (see audit_report Session 30).
Everything else is BACKLOG — statuses below feed TRACEABILITY.md.

## British (§8.4) — worst findings
1. FIXED: `_sa_done_this_turn` never cleared → after the first Garrison
   SA, every later Muster skipped its Skirmish/Naval Pressure for the
   rest of the game (british_bot.py:521/1091).
2. FIXED: `_muster_die_cached` never cleared → B6's "a D6 roll" rolled
   once per GAME (british_bot.py:1621-1625).
3. Garrison SA order inverted: 8.4.1 "First execute Naval Pressure, or
   if that is not possible, Skirmish"; code does Skirmish first (:520).
4. 8.4.8 WI Battle: pays to hold WI with no British-Control check
   (year_end.py:256-267).
5. 8.4.11 "or the Patriots play their Brilliant Stroke": dead — engine
   always passes other_bs_faction=None (engine.py:917-923). [Shared
   with 8.5.8/8.6.11/8.7.8 — the whole bot-BS reaction chain.]
Also: FIXED (Session 38): Garrison origin pool restricted to controlled
spaces; skirmished-city exclusion unenforced; displacement under-scoped
(also dead §3.2.2 Blockade checks and an origin/destination
double-booking found on the way — see audit_report Session 38). Still open: Muster places ≤4
Regulars (rule: up to 6, "as many as possible"); Tory P2 sorts backwards
(largest deficit first, ignores Population/actual flip); FIXED (Session 39): March pop 1-2 limit, already-selected-destination preference, tier-2 catch-all, CC Tory double-count (+ phantom CC WPs, flip-all in-place activation — audit_report Session 39); _can_battle counts only ACTIVE rebels (rule:
ALL Rebellion pieces + Leaders); RL "largest change" ignores level×pop;
Supply lacks earnings projection; CoC-prevention proxy wrong; Loyalist
Desertion static sort can flip Control; pervasive raw-level-vs-pop and
alphabetical/first-seen tie-breaks (8.1.1/8.2).

## Patriots (§8.5) — worst findings
1. 8.5.5 Supply pays for EVERY unsupplied space (rule: only where
   removal would change Control) and unpaid removal order reverses
   8.1.2 (year_end.py:136-156).
2. FIXED Session 45: 8.5.4 March aborts entirely when French Regulars
   included at 0 French Resources (march.py raises; no gate at
   patriot.py:602); artificial 4-destination cap (now purse-budgeted);
   Continental-instead-of-Militia fallback.
3. 8.5.1 P6 gate omits Forts/Villages from "Active Royalist pieces"
   (Glossary: cubes/Forts/Villages are always Active) — over-Battles;
   Fort-only spaces excluded from selection.
4. Win-the-Day free Rally hardwired to the battle space; correct
   `_best_rally_space` selector is dead code (patriot.py:388-391/438)
   [still open].  FIXED Session 45: Partisans option-3 wrongly
   requires no enemy cubes; Battle-space exclusion (4.3.2/4.3.3)
   unenforced for Partisans/Skirmish (now engine-enforced for all
   three Skirmish factions; options 1/2 also restricted to UNITS per
   Glossary 1.4).
5. Systemic deterministic tie-breaks (Rally/March/Supply/Desertion/
   Redeploy) vs 8.2 seeded-random.
Also: FIXED Session 45 — Rally counts French Regulars in "4+ Patriot
units"; Rally bullet 6 fills slots with no-benefit spaces; lonely-fort
placements use 1 Militia vs max-extent; Desertion bulk removal not
re-scored; CoC potential uncapped by 2-level max, Fort-only spaces
excluded, shift allowance shared with RL.  FIXED Session 43: 8.5.6
redeploy can pick a Patriot-less space at 0 Continentals.  Still
open: BS first-eligible None-passthrough.

## French (§8.6) — worst findings
1. 8.6.7 Supply move-vs-pay INVERTED: never pays to hold Control-
   changing spaces while any Patriot Fort exists (year_end.py:157-206).
2. 8.6.6 Win-the-Day free Patriot Rally deliberately returns None,
   contradicting 8.6.6 and resolved QUESTIONS.md Q9
   (french.py:772-787).
3. FIXED: F2 bullet "moves French Regulars or Squadrons from
   Unavailable" read keys that never exist (FRENCH_UNAVAIL/SQUADRON vs
   the remapped REGULAR_FRE/BLOCKADE) — dead since setup remaps keys.
4. 8.6.5 March: missing "then Colonies" tier; "March any French
   Regulars … towards nearest British" demoted to fallback and moves
   only 1 Regular; alphabetical ties. [FIXED Session 42]
5. 8.6.4 Muster fallback can pick a Province (3.5.3: Colony/City/WI
   only; muster.execute doesn't validate type either) + Q16 (Hortalez
   pre-ToA "up to 1D3" conflict — see QUESTIONS.md).
Also: 8.6.2 binary control proxy + fixed-order ties; 8.6.10 misses
British→Uncontrolled flips; blockade model caps 1/City; WTD blockade
"more Support" unchecked; BS reaction chain dead (see British #5).

## Indians (§8.7) — worst findings
1. 8.7.1 Raid 0-Resource path runs Plunder + Trade + possibly Plunder
   again (up to 3 SAs; rule allows one) [FIXED Session 35], and the
   mid-raid replenish-then-continue is not implemented (pre-capped to
   starting Resources) (indians.py:236-250, 410) [FIXED Session 40 per
   Q18 ruling].
2. 8.7.5 Supply pays for spaces that must MOVE instead ("If … neither
   of the above conditions are met, move the War Parties");
   add-Rebellion-Control test never simulates the post-move board
   (year_end.py:229-231; indians.py:1326-1348).
3. Failed-Raid routing: manual says (twice) failed Raid → Gather;
   flowchart YAML routes to I6 (may Scout/March). Reference conflict →
   QUESTIONS.md Q17.
4. 8.7.4 Scout can lose British Control (moves every British piece
   out) [FIXED Session 36]; origin picked before destination priorities
   [FIXED Session 40 — destination-first over all pairs].
5. 8.7 intro: FNI-reducing events never satisfy bullet 1; Raid target
   sort ignores the plunder-possible/pop two-tier order and 8.2 ties.
Also: Village-with-WP placement preference unimplemented; Gather
worthwhile-count ignores support gate; 1-Village spaces with room
excluded from bullet 1; bullet-4 availability miscount; free-Reserve
gather refused at 0 Resources; March Phase-2 overshoots control need
by 1; redeploy ties dict-order and 0-WP fallback illegal per 6.5.2.

## Cross-cutting
- The bot Brilliant-Stroke REACTION chain (respond to another bot's or
  player's BS) is dead for all four factions: engine hardcodes
  other_bs_faction=None and never re-polls during trump resolution.
- "Most Support/Opposition" repeatedly computed as raw level instead
  of level × Population (8.1.1).
- Tie-breaks are pervasively alphabetical/first-seen instead of 8.2
  seeded-random.
- Winter Quarters phase code (year_end.py) carries several per-faction
  Supply/Desertion/Redeploy deviations — none of it was
  section-cited until now.
