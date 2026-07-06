# Large-N baseline RESET — Session 60, post-Q22 (Random Spaces table)

Q22 (Eric's ruling): the Random Spaces table now governs ALL
non-player tie resolution engine-wide (35 former seeded-uniform sites
across the four bots; shared pick_by_priority/choose_random_space in
lod_ai/bots/random_spaces.py, incl. the two-candidate D6 convention).
ALL PRIOR LARGE-N NUMBERS (S53-S59) ARE NON-COMPARABLE from this
commit forward.  New baseline (largeN_s60_q22.jsonl, 300 games,
seeds 5000+, PYTHONHASHSEED=0):

| Faction | 1775 | 1776 | 1778 | total |
|---|---|---|---|---|
| PATRIOTS | 12 | 47 | 29 | 88 (29%) |
| BRITISH | 1 | 6 | 2 | 9 (3%) |
| FRENCH | 44 | 31 | 61 | 136 (45%) |
| INDIANS | 43 | 16 | 8 | 67 (22%) |

KEY READING: under uniform ties (largeN_s59b, same code otherwise)
the British were 20/300 (6-7%); under the table they fall to 9/300.
The table's column-scan distribution is NOT uniform — it redirects
the British Muster/Garrison tie picks (pop-2 destinations cluster in
the table's early columns) enough to cost ~11 wins/300.  This is the
distributional effect Q22 anticipated, now measured: the RULED
procedure is the fidelity ground truth, and the S59 6-7% read was
partly an artifact of uniform ties.  Indians hold at 43% in 1775
under both regimes (the S59/S60 Royalist fixes, not the tie model).
Next instruments: Example 4 golden (Brilliant Stroke), the Indian
1775 concentration, and exact-pick tightening of the Example 2/3
goldens now that table parity holds.
