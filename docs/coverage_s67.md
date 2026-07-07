# Decision coverage — 300 games

## Commands x faction (Ch 3 universe)
  BRITISH  MUSTER                       1135
  BRITISH  GARRISON                      981
  BRITISH  MARCH                         436
  BRITISH  BATTLE                        118
  PATRIOTS RALLY                        1113
  PATRIOTS MARCH                         110
  PATRIOTS BATTLE                        546
  PATRIOTS RABBLE_ROUSING                992
  INDIANS  GATHER                       1480
  INDIANS  MARCH                         655
  INDIANS  SCOUT                         139
  INDIANS  RAID                         1089
  FRENCH   FRENCH_AGENT_MOBILIZATION     645
  FRENCH   HORTELEZ                      451
  FRENCH   MUSTER                       1030
  FRENCH   MARCH                        1188
  FRENCH   BATTLE                        466

## Special Activities x faction (Ch 4 universe)
  BRITISH  COMMON_CAUSE                   36
  BRITISH  SKIRMISH                     1397
  BRITISH  NAVAL_PRESSURE                946
  PATRIOTS PERSUASION                   1796
  PATRIOTS PARTISANS                     834
  PATRIOTS SKIRMISH                       44
  INDIANS  TRADE                        2245
  INDIANS  WAR_PATH                      685
  INDIANS  PLUNDER                       277
  FRENCH   PREPARER                     1181
  FRENCH   SKIRMISH                      919
  FRENCH   NAVAL_PRESSURE               1464

## Event sides never chosen by any bot
  card  48 side(s) never fired: ['shaded'] (God Save the King)

## Event executions by faction (fired combos)
  BRITISH    2110 executions, 86 distinct card-sides
  PATRIOTS   2050 executions, 86 distinct card-sides
  INDIANS    1834 executions, 85 distinct card-sides
  FRENCH     1319 executions, 80 distinct card-sides

## Passes by reason
  BRITISH  resource_gate                     738
  FRENCH   resource_gate                     105
  INDIANS  no_valid_command                   15
  PATRIOTS resource_gate                     632

## Session 67 verdict analysis (every never-fired branch adjudicated)

First 300-game read (pre-fix) flagged: PREPARER 0 uses; cards 2/41/68
never executed; sides 6u/10u/17u/32u/36s/46s/48s/84u never fired.

* FRENCH PREPARER — REAL BUG (fixed): the French bot's inline
  `_preparer_la_guerre` never set `_turn_used_special`, so every
  Préparer (~4/game) was invisible to the engine's §2.3.4/§2.3.5 slot
  matrix (2nd-eligible options computed from a false "no SA used") and
  to this trace.  Post-fix: 1,188 uses/300 games.
* Cards 2, 6u, 10u, 32u, 41, 46s, 84u — REAL BUG (fixed): seven card
  handlers filtered candidates with `info.get("type")` on STATE space
  dicts, which never carry the key (the S48 pick_cities collateral
  class, unswept in early_war.py).  Every candidate list was empty →
  permanently Ineffective.  Post-fix: all seven fire.
* Card 68 — REAL BUG x2 (fixed): (a) `places_patriot_fort` flag was
  False although the only Non-player that can choose the card is the
  PATRIOTS (B/F/I carry Sword icons) and the "friendly Fort" is then
  the Patriot Fort; (b) the P2/F2 bullet evaluators read
  `effects["shaded"]` unconditionally — non-dual cards carry their
  single text under "unshaded", so all six single-sided benefit cards
  (52/68/72/73/92/95) were invisible to Patriot/French Event bullets
  (Sullivan Expedition 73 removes Villages — a printed P2 benefit).
  Post-fix: card 68 executes 48x/300 games.
* Card 17 unshaded — PRECONDITION-RARE, legitimate: needs a Patriot
  Fort in an Indian Reserve, which only cards 68/72 create; it fires
  once card 68 does.  Handler proven by targeted test.
* Card 36 shaded — PRECONDITION-RARE, legitimate: needs British
  Regulars in the West Indies.  Handler proven by targeted test.
* Card 48 shaded — CORRECT never-fire: FRENCH/INDIANS/PATRIOTS all
  carry Sword icons, so no Non-player ever chooses the card; the
  shaded side is reachable only by a human Patriot/French player.
  (The executing-bot side selection makes a bot-chosen 48 always
  unshaded.)  This is the expected steady state of the matrix.
