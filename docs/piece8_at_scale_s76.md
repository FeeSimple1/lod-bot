# Piece 8 — Statistical validation at scale (Session 76)

Instrument: 3,000 zero-player games (1,000 per scenario), seeds 20000+
(disjoint from gate 1-20, soak 1000+, large-N 5000+), PYTHONHASHSEED=0,
HEAD after the S76 C6 fix (bots no longer auto-reclaim own pieces on
pool-dry placements).  Runner: `python -m lod_ai.tools.soak --games
3000 --seed-base 20000 --out piece8_s76.jsonl` (resumable slices).
All 3,000 games ended in a rules victory — zero crashes, zero
invariant failures, zero deck exhaustions.

## Win rates (Wilson 95%, n=1,000/scenario)

| Faction | 1775 | 1776 | 1778 | total (n=3,000) |
|---|---|---|---|---|
| FRENCH | 43.4% (40.4-46.5) | 35.2% (32.3-38.2) | 60.9% (57.8-63.9) | 46.50% (44.7-48.3) |
| PATRIOTS | 14.8% (12.7-17.1) | 33.0% (30.2-36.0) | 23.7% (21.2-26.4) | 23.83% (22.3-25.4) |
| INDIANS | 38.6% (35.6-41.7) | 20.7% (18.3-23.3) | 11.3% (9.5-13.4) | 23.53% (22.0-25.1) |
| BRITISH | 3.2% (2.3-4.5) | 11.1% (9.3-13.2) | 4.1% (3.0-5.5) | 6.13% (5.3-7.0) |

Royalist (B+I): 890/3,000 = 29.67% (28.1-31.3).

## Game length (cards played)

| Scenario | mean | median | p10 | p90 | min | max |
|---|---|---|---|---|---|---|
| 1775 | 56.3 | 62 | 31 | 65 | 6 | 65 |
| 1776 | 36.0 | 40 | 18 | 43 | 6 | 43 |
| 1778 | 27.6 | 29 | 19 | 32 | 6 | 32 |

Medians sit at/near each scenario's deck size — most games run to
final scoring; the p10 values show the early-victory tail (~10% of
games end at a mid-game Victory Check).  min=6 = the earliest
possible WQ check.

## Readings

1. **The at-scale British number is 6.1% (5.3-7.0)** — lower than the
   ~8-10% the 300-game reads suggested, for two reasons: 10× tighter
   CIs, and this baseline is post-C6 (the unconditional auto-reclaim
   the bots were never entitled to mostly refilled CAPPED pools —
   Tories, Militia, War Parties, Forts — and the British Tory economy
   leaned on it).  This is the rules-faithful number.
2. French dominance is now measured at ±1.8pp: 46.5% overall, peaking
   at 60.9% in 1778.  Patriots and Indians are statistically tied
   overall (23.8 vs 23.5) with opposite scenario profiles.
3. **Baseline policy (per ROADMAP Piece 8): future changes whose
   large-N reads land OUTSIDE these intervals must be EXPLAINED, not
   just rebaselined.**  The 60-game canary stays the fast gate; the
   300-game instrument stays the per-session read; this file is the
   at-scale anchor.
4. Deferred sub-item: per-card resource-curve distributions (the
   `run_one_game(detailed=True)` collector exists; wiring it through
   a soak-scale run is queued — the win/length instruments above are
   the decision-relevant pieces for the tune call).
