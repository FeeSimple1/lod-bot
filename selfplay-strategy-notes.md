# Liberty or Death — Self-Play Strategy Notes

*Generated June 2026 from heuristic self-play experiments using the repo's LLM harness
(`lod_ai/llm/heuristic.py` + `lod_ai/tools/heuristic_selfplay.py`). These notes describe
what wins against this engine's rule-based bots — they are evidence about the
implementation as much as about the board game, and should be read alongside
`strategy.md`, which supplied most of the strategy hypotheses tested here.*

## Method

Eight heuristic profiles — two competing strategy hypotheses per faction — were encoded
as menu-answering policies and seated as the "human" player via the harness, with the
rule-based bots playing the other three factions. Each profile was compared against a
uniform-random-legal-move baseline (`RANDOM`) and a first-legal-option baseline
(`FIRST`) on the same seeds. Volume: 320 games on 1778 (20 seeds × 16 configurations),
120 games on 1775, 100 games on 1776, plus 60 bot-only reference games. No game crashed
or stalled. With n = 10–20 per cell, win-rate differences under ~20 points are noise;
the findings below rest on the large gaps.

The profiles, in brief: Patriots **P-AGIT** (Rabble-Rousing + Persuasion engine, forts,
battle only with a clear edge) vs **P-MIL** (Rally Continentals and seek battle).
British **B-CITY** (Muster + Reward Loyalty in high-population cities, Garrison) vs
**B-AGGRO** (battle-first). French **F-PREP** (hoard and Préparer pre-Treaty, switch to
expeditionary battle after) vs **F-NAVY** (economic/naval pressure throughout). Indians
**I-VILLAGE** (Gather toward villages, Trade) vs **I-RAID** (Raid opposition, War Path).

## Results

Win rate = games won by the seated profile's own faction.

| Seat | Profile | 1775 Long | 1776 Medium | 1778 Short |
|---|---|---|---|---|
| Patriots | P-AGIT | **40%** | 80% | 30% |
| Patriots | P-MIL | 0% | 70% | **40%** |
| Patriots | RANDOM | 0% | 80% | 20% |
| British | B-CITY | 0% | 0% | 0% |
| British | B-AGGRO | 0% | 0% | 0% |
| British | RANDOM | 0% | 0% | 0% |
| French | F-PREP | 0% | 0% | 30% |
| French | F-NAVY | — | — | 5% |
| French | RANDOM | 0% | 0% | 35% |
| Indians | I-VILLAGE | 10% | 0% | 0% |
| Indians | I-RAID | 10% | — | 5% |
| Indians | RANDOM | 0% | 0% | 0% |

Bot-only reference (60 games): 1775 → Patriots 16, British 3, Indians 1; 1776 →
Patriots 19, British 1; 1778 → French 12, Patriots 7, British 1.

## Findings

**1. The Patriot question is "when do you militarize," and the scenario answers it.**
The cleanest result in the data. In 1775 Long, the agitation engine wins 40% while the
military profile and the random baseline win zero — and the failure mode is specific:
military Patriots hand the game to the *British* in 8 of 10 games, because early
battles feed casualties to the Crown while Opposition never gets built. In 1778 Short
the ranking flips (military 40% > agitation 30% > random 20%): Opposition is already
high at setup, the margin to defend is Forts vs Villages, and Continentals matter more
than another support shift. This directly confirms `strategy.md`'s phase guidance, and
sharpens it: the long-game penalty for premature battling is not just inefficiency, it
is actively winning the game for your enemy.

**2. Never voluntarily battle early as the Patriots in the long scenarios.** Worth
stating separately because the cost is so asymmetric. P-AGIT (which only attacks with a
2:1 force edge and no enemy fort) never lost to the British in 1775; P-MIL (same code,
battle-seeking command order) lost to them 80% of the time. Underground Militia that
stay underground are worth more than any early exchange.

**3. The British seat is the hardest chair in the engine, and aggression makes it
worse.** Every British configuration — both heuristics and both baselines, all three
scenarios — went 0 for 90. The British *bot* does win games (≈15% over the reference
batches), so the seat is not hopeless; its flowchart cadence simply beats my
keyword-level heuristics. What the data does show: B-AGGRO games are the shortest in
the whole experiment (avg 21–28 cards, all Patriot wins), i.e. battle-led British play
accelerates your own defeat. B-CITY at least survives to card 51 on average in 1775.
The British margin (Support − Opposition > 10 *and* CRC > CBC) appears to demand
coordinated event use and precise battle timing that neither randomness nor simple
command preferences reach. For a human or LLM player: expect the British to be the seat
where move quality matters most.

**4. French Naval Pressure is a trap as a default activity.** F-NAVY, which leads with
Naval Pressure and economic play after the Treaty, won 1 game in 20 on 1778 — against
30% for battle-forward F-PREP and 35% for random. Naval Pressure spends the special
activity without moving either French victory margin (Opposition or CBC); a French seat
that doesn't fight doesn't score. Use Naval Pressure to enable a specific battle or
blockade plan, not as a routine.

**5. The French win window is 1778.** No French configuration won a single 1775 or 1776
game, while 1778 gives the French seat its best odds in the experiment (30–35%), and
the French bot likewise dominates bot-only 1778 (12 of 20). The pre-Treaty game is
preparation in the literal sense: nothing you do before ToA shows up in your score
until the short-scenario phase of the war.

**6. The Indian seat mostly decides who else wins.** Indian win rates are near zero
everywhere (best: I-VILLAGE/I-RAID at 10% in 1775) — Support − Opposition > 10 plus a
village margin is rarely reachable. But the third-party effect is dramatic: with a
random Indian seat, games end in 21–25 cards as near-universal Patriot wins; village-
focused play stretches games past card 48 and keeps British hopes alive. Playing the
Indians is largely kingmaking: build and defend villages, deny Patriot tempo, and take
the rare win when the British keep Support high for you.

**7. Engine balance tilts Patriot.** Random Patriots win 80% of 1776 games; the Patriot
bot wins 16/20 bot-only 1775 games and 19/20 1776 games. Some of this echoes the
known pass-rate diagnostics in `lod_ai/tools/bot_error_analysis*.md` (bots occasionally
pass on errors), but the size of the skew suggests 1776 setup or Patriot bot strength
is worth an engine-side look before reading too much strategy out of that scenario.

## Caveats and next steps

These results measure play against this engine's bots with deliberately simple
policies; they say nothing about play against humans, and little about lines the
profiles can't express (event timing, Brilliant Stroke usage, leader positioning —
all events were deprioritized below commands in every profile). Natural next
experiments: a Patriot hybrid that agitates until ToA then militarizes (the data
suggests it would dominate both pure profiles across scenarios); British profiles that
prioritize faction events and battle only at computed force advantage; and replacing
profile keyword scoring with the engine-state space scorers for sharper targeting.

## Sources for the strategy priors

Profiles encode hypotheses from the repo's `strategy.md` plus published play advice:
[The Players' Aid COIN Workshop — Indian faction](https://theplayersaid.com/2023/01/17/coin-workshop-liberty-or-death-the-american-insurrection-from-gmt-games-indians-faction/),
[The Players' Aid review](https://theplayersaid.com/2017/03/01/turning-the-wargaming-world-upside-down-a-review-of-liberty-or-death-the-american-insurrection-by-gmt-games/),
and [Board Game Meeple Lady's overview](https://www.boardgamemeeplelady.com/2017/07/04/liberty-or-death-the-american-insurrection/).
