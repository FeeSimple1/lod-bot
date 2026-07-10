# Large-N balance refresh — Session 72 (post Q22-sweep / T8 / T7)

Method: 300 zero-player games (100 per scenario), seeds 5000+
(disjoint from the gate's 1-20 and soak ranges), PYTHONHASHSEED=0,
HEAD after S68-S72 (Q22 deck-wide card-handler tie sweep, T8 §8.3.1
event-instruction free ops, T7 §8.3.5 target order, Piece 9 hygiene).
Runner: `python -m lod_ai.tools.soak --games 300 --seed-base 5000
--out largeN_s72.jsonl` (resumable ~38s slices); Wilson 95% CIs.
All 300 games ended in a rules victory — no crashes, no invariant
failures, no deck exhaustion.

| Faction | 1775 (%) | 1776 (%) | 1778 (%) | total |
|---|---|---|---|---|
| FRENCH | 41 (31.9-50.8) | 33 (24.6-42.7) | 60 (50.2-69.1) | 134 (44.7%, 39.1-50.3) |
| INDIANS | 47 (37.5-56.7) | 22 (15.0-31.1) | 9 (4.8-16.2) | 78 (26.0%, 21.4-31.2) |
| PATRIOTS | 7 (3.4-13.7) | 28 (20.1-37.5) | 24 (16.7-33.2) | 59 (19.7%, 15.6-24.5) |
| BRITISH | 5 (2.2-11.2) | 17 (10.9-25.5) | 7 (3.4-13.7) | 29 (9.7%, 6.8-13.5) |

Royalist (B+I) total: 107/300 (35.7%).

Readings vs the last read (S63 addendum in
docs/balance_largeN_s60_q22.md — P 54, B 27, F 142, I 77;
Royalist 104/300):

1. **The balance picture is UNCHANGED within noise.**  Every faction's
   S72 total sits inside its S63 CI and vice versa (P 54→59, B 27→29,
   F 142→134, I 77→78).  The S68-S70 fidelity work (28 card-handler
   tie sites onto the ruled table, event-instruction free ops, §8.3.5
   target order) flipped individual game winners but did not move the
   aggregate rates — it was correctness work, not a balance lever.
2. Within-scenario British mix shifted a little (1776 22→17, 1775
   2→5, 1778 3→7) but each cell's CI overlaps its S63 value; the
   headline stays: British ~10% overall, best in the 1776 Howe
   scenario, near-floor in 1775/1778.
3. Standing shape: French strongest everywhere (peak 60% in 1778),
   Indians carried by 1775 (47%), Patriots carried by 1776/1778,
   British weakest everywhere.  The fidelity program has no open
   leads on these numbers (Q1-Q22 resolved; T7/T8 done); whether
   this is the game as designed or a target for house tuning is
   Eric's open judgment call (see HANDOFF_2026-07-10_S72.md) — this
   refresh is the input to that call, not a recommendation.
