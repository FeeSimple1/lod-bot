# Large-N balance read — Session 53 (ROADMAP Piece 8, first instrumented run)

Method: 300 zero-player games (100 per scenario), seeds 5000+ (disjoint
from the gate's 1-20 and prior soak ranges), PYTHONHASHSEED=0, current
HEAD.  Runner: `python -m lod_ai.tools.soak --games 300 --seed-base
5000 --out largeN_s53.jsonl` (resumable across 45-s shells); Wilson 95%
intervals.  All 300 games ended in a rules victory (no crashes, no
deck exhaustion).

| Faction | 1775 (med 62 cards) | 1776 (med 40) | 1778 (med 30) |
|---|---|---|---|
| PATRIOTS | 31.0% (22.8–40.6) | 50.0% (40.4–59.6) | 18.0% (11.7–26.7) |
| BRITISH | **1.0% (0.2–5.4)** | **1.0% (0.2–5.4)** | **3.0% (1.0–8.5)** |
| FRENCH | 50.0% (40.4–59.6) | 45.0% (35.6–54.8) | 69.0% (59.4–77.2) |
| INDIANS | 18.0% (11.7–26.7) | 4.0% (1.6–9.8) | 10.0% (5.5–17.4) |

Readings:

1. **The British near-zero is now a measured fact, not sample noise** —
   the 95% CI tops out at 5-8% in every scenario.  The 20-game
   see-saws of Sessions 38-48 (5%→20%→5%) were noise around a very low
   true rate.
2. The Rebellion side wins 63-87% everywhere.  Candidate explanations,
   not mutually exclusive: (a) the remaining UNVERIFIED §8.4 British
   rows (TRACEABILITY.md — Muster 8.4.2, Battle 8.4.4 details, and the
   B-node flowchart inventory) hide real deviations, exactly as the
   §8.5-§8.7 rows did before Sessions 45-51; (b) the audit stretch
   disproportionately hardened Rebellion bots (ToA unlock, Patriot
   block, Indian nodes) and the British never got an equivalent pass
   beyond Sessions 38-39; (c) the British second victory condition
   (CRC > CBC) is structurally starved now that rebel bots waste fewer
   pieces.  CBC/CRC trajectories per game are in largeN_s53.jsonl for
   follow-up.
3. Whether these rates match the PHYSICAL game's bot meta is outside
   the repo's ground truth — flagged for Eric.  The audit-first
   recommendation stands regardless: finish the §8.4 verification
   pass before any tuning, since every prior "weak faction" turned
   out to be unimplemented rules (French 0% → Session 50).

Follow-ups queued: §8.4 verification pass (TRACEABILITY queue item 1),
B-node flowchart inventory, CBC/CRC trajectory analysis.
