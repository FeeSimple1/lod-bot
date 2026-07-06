# Large-N balance read — Session 56 (post §8.6 F-node inventory)

Method as S53-S55: 300 games (100/scenario), seeds 5000+,
PYTHONHASHSEED=0, Wilson 95% CIs.  File: largeN_s56.jsonl.

| Faction | 1775 | 1776 | 1778 |
|---|---|---|---|
| PATRIOTS | 38.0% (29.1–47.8) | 72.0% (62.5–79.9) | 33.0% (24.6–42.7) |
| BRITISH | 1.0% (0.2–5.4) | 2.0% (0.6–7.0) | 0.0% (0.0–3.7) |
| FRENCH | 52.0% (42.3–61.5) | 23.0% (15.8–32.2) | 63.0% (53.2–71.8) |
| INDIANS | 9.0% (4.8–16.2) | 3.0% (1.0–8.5) | 4.0% (1.6–9.8) |

vs S55b (B 1/5/2, I 27/12/10): the S56 F-node fixes made the
REBELLION side stronger — 281/300 (94%).  Driver: the Blockade
marker-conservation fix.  Before S56 the French Navy was throttled by
a real BUG (placing onto an already-blockaded City silently destroyed
the marker while raising FNI); with markers conserved and the
no-benefit spread interim, more Cities are blockaded, and §1.9 zeroes
a blockaded City's Support population — both Royalist victory
conditions degrade.

Q21 counter-experiment (see QUESTIONS.md): under the literal-letter
reading (NP targets the most-Support City even when blockaded; the
placement fails as-modeled and the SA falls through to Skirmish) the
Rebellion takes 259/300 (86%), Indians recover 16→37, British stay
~1%.  So the Q21 ruling is worth ~8 points of Rebellion share and a
2x Indian swing — but is NOT the British lever.

Standing: every §8.4.x AND §8.6.x row is now text-verified.  British
~1% survives a fully-audited British bot AND a fully-audited (and
strengthened) French bot.  Remaining hypotheses, in order:
1. §8.5 Patriot and §8.7 Indian residual rows (the S45/S51 blocks
   covered the majors; the P/I flowchart inventories at the S55/S56
   standard have NOT been done).
2. Piece 5 Playbook goldens — the worked examples are the only
   remaining ground truth that could reveal systematic mis-reads.
3. Eric's judgment call: the physical game's non-player British may
   simply be this weak in bot-vs-bot play (the game was designed for
   HUMAN British vs bots; the 8.4 flowchart is a defensive caretaker
   by design — Garrison/Muster-heavy, Battle-rare).
