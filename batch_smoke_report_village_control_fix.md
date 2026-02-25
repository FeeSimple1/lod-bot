# Batch Smoke Test Report: Village Control Fix

**Date:** 2026-02-25
**Fix:** Villages now counted toward Indian/Royalist control in `lod_ai/board/control.py`
**Batch:** 150 games (50 seeds x 3 scenarios), `--large` mode, zero crashes/timeouts

---

## 1. Overall Win Rates

| Faction  | Previous | New | Delta |
|----------|----------|-----|-------|
| PATRIOTS | 107 (71.3%) | 99 (66.0%) | -8 |
| BRITISH  | 4 (2.7%)    | 0 (0.0%)   | -4 |
| INDIANS  | 4 (2.7%)    | 6 (4.0%)   | +2 |
| FRENCH   | 35 (23.3%)  | 45 (30.0%) | +10 |

**Key change:** Patriots dropped from 71.3% to 66.0%. French surged from 23.3% to 30.0%. Indians gained slightly. British dropped to 0.

---

## 2. Per-Scenario Win Rates

### Scenario 1775 (50 games)

| Faction  | Previous | New | Delta |
|----------|----------|-----|-------|
| PATRIOTS | 50 (100%) | 45 (90%) | -5 |
| INDIANS  | 0 (0%)    | 5 (10%)  | +5 |

Indians went from 0 to 5 wins (all via final scoring). Patriots no longer sweep 1775.

### Scenario 1776 (50 games)

| Faction  | Previous | New | Delta |
|----------|----------|-----|-------|
| PATRIOTS | 49 (98%) | 50 (100%) | +1 |
| BRITISH  | 1 (2%)   | 0 (0%)    | -1 |

Patriot dominance in 1776 remains near-total — still 100%.

### Scenario 1778 (50 games)

| Faction  | Previous | New | Delta |
|----------|----------|-----|-------|
| PATRIOTS | 8 (16%)  | 4 (8%)    | -4 |
| BRITISH  | 3 (6%)   | 0 (0%)    | -3 |
| INDIANS  | 4 (8%)   | 1 (2%)    | -3 |
| FRENCH   | 35 (70%) | 45 (90%)  | +10 |

French dominance increased sharply in 1778. British and Indian wins both dropped.

---

## 3. Error Rate

| Metric | Count |
|--------|-------|
| Crashes | 0/150 |
| Timeouts (200-card limit) | 0/150 |
| Interactive prompts | 0/150 |
| Deck exhausted | 0/150 |

**Zero errors.** The control fix did not introduce any new crashes or hangs.

---

## 4. Indian-Specific Metrics

### Average Indian Victory Margins (final state)

| Scenario | Margin 1 | Margin 2 | Both Positive |
|----------|----------|----------|---------------|
| 1775     | -17.4    | -4.1     | 0/50 (0.0%)   |
| 1776     | -20.8    | -4.3     | 0/50 (0.0%)   |
| 1778     | -12.2    | -2.1     | 0/50 (0.0%)   |

Indians never achieved both margins positive at any WQ check across all 150 games. Their 6 wins all came via final scoring tiebreakers, not victory conditions.

### Average Indian Pieces at Game End

| Scenario | Avg Villages | Avg Indian Pieces |
|----------|-------------|-------------------|
| 1775     | 2.0         | 10.9              |
| 1776     | 2.4         | 11.9              |
| 1778     | 5.9         | 17.2              |

### Indian Win Details

All 6 Indian wins were via **final scoring** with negative margins:

- **1775 seed 1:** margins [-5, -2]
- **1775 seed 21:** margins [-5, -3]
- **1775 seed 22:** margins [-7, -2]
- **1775 seed 31:** margins [-5, -3]
- **1775 seed 38:** margins [-1, -4]
- **1778 seed 43:** margins [-3, 0]

---

## 5. Control & Board State

### Average Controlled Spaces (at final WQ)

| Scenario | British Ctrl | Rebellion Ctrl |
|----------|-------------|----------------|
| 1775     | 12.6        | 3.8            |
| 1776     | 12.2        | 4.6            |
| 1778     | 11.2        | 7.3            |

### Average Support/Opposition (at final WQ)

| Scenario | Total Support | Total Opposition |
|----------|--------------|-----------------|
| 1775     | 9.0          | 16.4            |
| 1776     | 5.9          | 16.6            |
| 1778     | 12.8         | 15.0            |

### Average Casualties

| Metric | Value |
|--------|-------|
| CBC (avg at game end) | 14.0 |
| CRC (avg at game end) | 9.1 |
| Royalist battle losses/game | 8.1 |
| Rebellion battle losses/game | 4.7 |
| Total battles/game | 4.7 |

---

## 6. Analysis

### Expected Effects of the Village Control Fix

| Prediction | Result |
|------------|--------|
| Indian win rate increased | **Partially confirmed.** Indians gained +2 wins overall (4 -> 6), and gained +5 wins in 1775. However, lost 3 wins in 1778. |
| Patriot/French win rate decreased (inflated Rebellion Control) | **Opposite for French.** Patriots dropped as expected (-8), but French actually gained +10. The fix appears to have shifted the balance toward French, not away from Rebellion. |
| British win rate stayed similar | **Dropped to 0.** British went from 4 wins to 0. This was unexpected since British control uses British pieces. |
| No new errors | **Confirmed.** Zero crashes, zero timeouts. |

### Interpretation

1. **The Village control fix primarily benefited French, not Indians.** By correctly counting Villages toward Royalist control, the fix increased Royalist control counts. Since British victory requires high British-controlled spaces AND high support, while French victory requires French Regular pieces AND high opposition, the increased Royalist control may have prevented Patriots from achieving their victory conditions as easily, allowing more games to reach final scoring where French dominates in 1778.

2. **Indian win rate remains very low.** Despite the fix, Indians still cannot achieve both victory margins positive. Their 6 wins are all tiebreaker scenarios. Indian villages average only 2.0-5.9 at game end, and their overall piece counts are low. The fundamental Indian balance issue goes deeper than just control counting.

3. **1775 scenario became slightly more competitive.** Patriots dropped from 100% to 90%, with Indians taking 10% via final scoring. This is a meaningful improvement.

4. **1776 scenario is completely Patriot-dominated.** 100% Patriot wins, unchanged by the fix.

5. **1778 became more French-dominated.** French went from 70% to 90%, crowding out British and Indian wins entirely.

6. **British never win in any scenario now.** This is a regression from the previous 4 wins (1 in 1776, 3 in 1778). The fix may have inadvertently changed decision paths in ways that hurt British performance.

---

## 7. Recommendations

1. Investigate why British win rate dropped to 0 — the Village control fix should not have affected British control calculations directly.
2. Indian balance needs deeper attention beyond the control fix — their margins are deeply negative across all scenarios.
3. The 1776 Patriot sweep (100%) suggests systemic balance issues in that scenario's setup or bot logic.
4. Consider whether the final scoring tiebreaker is implemented correctly, since Indians are "winning" with negative margins.
