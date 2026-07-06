# Large-N balance read — Session 55 (post §8.4 part-2 audit)

Method identical to S53/S54: 300 zero-player games (100/scenario),
seeds 5000+, PYTHONHASHSEED=0, `soak --games 300 --seed-base 5000
--out largeN_s55.jsonl`, Wilson 95% CIs.  All 300 clean.

| Faction | 1775 | 1776 | 1778 |
|---|---|---|---|
| PATRIOTS | 24.0% (16.7–33.2) | 53.0% (43.3–62.5) | 29.0% (21.0–38.5) |
| BRITISH | 1.0% (0.2–5.4) | **5.0% (2.2–11.2)** | 2.0% (0.6–7.0) |
| FRENCH | 49.0% (39.4–58.7) | 30.0% (21.9–39.6) | 59.0% (49.2–68.1) |
| INDIANS | 26.0% (18.4–35.4) | 12.0% (7.0–19.8) | 10.0% (5.5–17.4) |

vs S54 (P23/B0/F50/I27; P57/B1/F38/I4; P20/B2/F69/I9): British 3/300
→ 8/300; 1776 moved 1%→5%.  The S55 clusters (§8.1 pay-as-you-select,
Skirmish cube-priority + executor order, CC force parity, B9 gate)
also shifted the Rebellion mix substantially (1778 French 69→59,
Patriots 20→29; 1775 Indians 18→26), consistent with the Skirmish
executor change touching every British Skirmish.

Diagnostic facts (diag_s55.py, 90 games):
- no_valid_command passes: 0 (were ~4-7/game) — all remaining British
  passes are genuine 0-Resource states (~1.5-4/game; median purse 2).
- Casualty sources, 10×1775: CBC = 12.9 Regulars + 6 Tories + 1 Fort
  per game; CRC = 8.7 French Regulars + 4.2 Continentals.  Patriot
  battles run 5-7/game vs British ~1 (the B4/B6 gates route the
  British to Garrison/Muster — per flowchart).
- Both British margins remain negative on average: sup−opp ≈ −3.6 to
  −7.5, crc−cbc ≈ −3.0 to −5.6.  Final-scoring margin is their sum,
  and the French margin is its mirror — hence French dominance.

Open levers, in order of expected value:
1. Q19 ruling (CC War Parties in the Tory loss slot) — lowers CBC in
   every CC battle if ruled (a).
2. Piece 5 Playbook goldens — worked examples would validate Battle/
   CC/Skirmish behavior against ground truth instead of inference.
3. F-node and remaining P-node inventories — the Rebellion side has
   never had the equivalent of today's B-node pass; French dominance
   may be THEIR unimplemented restraints, not missing British power.
4. Eric's judgment call (handoff "Awaiting Eric"): whether ~0-5%
   non-player British is true to the physical game's bot meta.

The §8.4 audit queue is now exhausted: every B-node and §8.4.x row is
text-verified (TRACEABILITY.md updated; Garrison had zero deviations).
