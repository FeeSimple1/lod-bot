# Liberty or Death — Strategy Guide

*A faction-by-faction, scenario-by-scenario strategic guide for GMT Games' Liberty or Death: The American Insurrection (COIN Series Vol. V, designed by Harold Buchanan, 2016).*

*Synthesized from the official Manual (`Reference Documents/`), a multi-source deep-research dossier compiled May 2026, and the lod-bot project's audit work across the rules.*

---

## What this file is and is NOT

**This is a supplementary strategy reference for LLM sessions and human
contributors who want to think about gameplay decisions** — for example,
to spot when the bot would make a tactically poor choice that follows
the flowchart, or to write strategic notes alongside a card-handler
patch, or to consult when implementing an LLM-driven decider that needs
to reason about positioning.

**It is NOT:**

* part of the runtime engine.  No code reads it.
* authoritative for rules questions.  When this guide and the Manual
  disagree, the Manual wins.  (Direct designer quotes here are tagged
  [D]; Manual-verified facts are tagged [M].)
* a substitute for the bot flowchart references in
  `Reference Documents/`.  The bot implementations must follow those
  flowcharts, not this strategy guide.  Per the project rule
  "Rules-Accurate Over Simple" / "Never Guess", do not adjust bot
  priorities based on what this document suggests.

The right way to use this file is to read it once for context, then
consult it when you need to understand *why* a faction would prefer
one play over another — for example, to author better commit messages,
investigate bot-flowchart anomalies, or write a human-side CLI prompt.

---

## How to use this guide

This guide assumes you know the basic rules — pieces, support track, command/SA structure, the sequence of play.  If you don't, read the Manual first (especially Ch 2 sequence and Ch 7 victory), then come back.

The guide is organized so you can read top-to-bottom for a comprehensive treatment, or jump to your faction and scenario for targeted advice.  Each section ends with a short "what to actually do" summary.

A note on confidence: claims marked with **[D]** are direct designer statements (Harold Buchanan); **[M]** are Manual-verified rules; **[C]** are community consensus from multiple sources; everything else is synthesis.  If you disagree with a synthesis claim, trust the rules + your own play.

---

# Part I — Game fundamentals

## 1. Victory conditions and what they mean

**[M] During Winter Quarters Victory Checks** (mid-game, the strict "more than 10" threshold applies):

| Faction | Margin 1 | Margin 2 |
|---|---|---|
| British | Support > Opposition by **more than 10** | CRC > CBC |
| Patriots | Opposition > Support by **more than 10** | Patriot Forts + 3 > Villages |
| French | Opposition > Support by **more than 10** + ToA played | CBC > CRC |
| Indians | Support > Opposition by **more than 10** | Villages − 3 > Patriot Forts |

To win at a Victory Check, **both your margins must be positive** (strictly above 0).

**[M] At Game End** (final Winter Quarters, the "more than 10" requirement drops; net score wins):

| Faction | Game-end formula |
|---|---|
| British | (Sup − Opp) + (CRC − CBC) |
| Patriots | (Opp − Sup) + (Forts + 3 − Villages) |
| French | (Opp − Sup) + (CBC − CRC) — ToA required |
| Indians | (Sup − Opp) + (Villages − 3 − Patriot Forts) |

Highest net score wins.  Even negative scores can win if less negative than rivals.

### What this actually means strategically

**The +3 and −3 are huge.**  Patriots start with 3 free points on Margin 2 just by existing.  Indians start with −3 — they need to build at least 4 more Villages than Patriot Forts to enter Margin-2 contention.  This single asymmetry shapes the entire game: Patriots can afford to be lazy about Forts early, Indians cannot afford to be lazy about Villages.

**Margin 1 is a single shared axis** (the Support–Opposition gap).  British and Indians want it positive; Patriots and French want it negative.  Same axis, opposite signs.  In any given turn, one side's gain is the other side's loss.

**Margin 2 is the faction-vs-faction axis.**  Patriots and Indians compete on Forts/Villages.  British and French compete on CRC/CBC casualties.  Your "ally" is also your competitor — keep that uppermost in mind.

**At Game End the math is unforgiving.**  A 1-point negative result on the Forts/Villages axis can be the difference between 2nd and 4th place.  Build a buffer in your Margin 2 well before the final Winter Quarters.

## 2. The two-vs-two dynamic

LoD is structurally a **2-vs-2** game (Royalist = British + Indians; Rebellion = Patriots + French) where the **side** competition is Margin 1, but the **within-side** competition is Margin 2.  This produces what Buchanan calls "veiled cooperation":

> **[D]** *"Keep the allies from getting too friendly!"*
> — Harold Buchanan, designer, commenting on Meeple Lady's playthrough (2017)

> **[C]** *"In the end you win alone so you must always keep that blade sharp and ready to stick in your ally's backs when appropriate."*
> — Players' Aid Indian COIN Workshop (2023)

The practical rule: **help your partner just enough on Margin 1 that your side wins it, but make sure you personally are ahead of them on Margin 2.**

A Patriot player who lets the French rack up CBC without scoring any themselves will lose Margin 2 at game end.  An Indian player who lets the British dominate Support track without building Villages will win Margin 1 but lose Margin 2.

### Partnership levers

**Patriot ↔ French (cooperation-heavy in the early game):**
- French funds Patriots via **Hortalez et Cie** (French pays N Resources, Patriot gains N+1).  This is the *only* meaningful Patriot funding source in the first campaign year.
- French places Patriot units pre-Treaty via **French Agent Mobilization** (2 Militia or 1 Continental in Quebec, NY, NH, or Mass.).
- Post-Treaty: **Rochambeau** makes joint Patriot Marches and Battles free of French Resource cost when French Regulars are in his space.  This is a big multiplier.

**British ↔ Indians (cooperation-light, lots of friction):**
- British uses Indian War Parties as Tory-equivalents in March/Battle via **Common Cause** (§4.2.1).  Helps British force levels but burns Indian WP inventory needed for Village-building.
- Indians can **Trade** with British for Resources.  British player chooses how much to transfer; 0 is legal.  Per the British bot OPS reference, British offers (D6+1)/2 Resources if Indian Res < British Res and D6 < British Res.
- **Brilliant Stroke trump chain** lets allied factions interfere with each other (more below).

### When to defect

- **Late-game (after WQ-3 or so),** the Margin 2 race is the decision.  If your partner is far ahead of you on Margin 2, prioritize personal Margin 2 even at side-cost.  If your side is uncatchable on Margin 1, focus purely on Margin 2.
- **If your partner's win is more likely than yours,** sabotage the side win to deny them and try to take 3rd place via the game-end tiebreakers (which favor the "winning Side's better-margin faction takes 1st, other takes 2nd").

## 3. Sequence of play and eligibility — the strategic dimension

**[M] Two factions act per card** (1st Eligible, then 2nd Eligible).  Acting renders you Ineligible for the next card.  Some events render OTHER factions Ineligible for the next card too.

**[M] What 2nd Eligible can do depends on 1st Eligible's action:**
- 1st Pass → 2nd has full options (Event, Command + SA)
- 1st Event → 2nd: Command + SA
- 1st Command + SA → 2nd: Limited Command only (1 space, no SA)
- 1st Command only → 2nd: Event OR Command + SA

This produces sharp tactical tradeoffs.  A Command + SA by 1st Eligible constrains the 2nd Eligible to a Limited Command, which is much less powerful.  If you're 1st Eligible and the upcoming card is bad for the 2nd Eligible's faction, going Command + SA punishes them.

### Pass is sometimes the right play

- If today's card is sub-optimal for you and tomorrow's card is good, **Pass today, act tomorrow.**  You stay Eligible.
- If you'd be 2nd Eligible and the card is rough, sometimes Pass on a marginal turn to preserve your slot for a better card.

### Reading the upcoming card

**[M]** The next card is always revealed.  Knowing what's coming is half the game.  Examples:
- If the next card has your Sword icon, you'd want to play the Event.  Don't waste your turn this card; Pass if possible.
- If the next card has a partner-helpful event but your partner is currently Ineligible, you may need to either act now (taking the Ineligible slot yourself) or hope the deck doesn't pass them by.

### Ineligibility weaponization

Some events render an opposing faction Ineligible for the next card (e.g., cards 18 "If it hadn't been so stormy", 44 "Earl of Mansfield Recalled From Paris").  If the target faction is well-positioned to act on the next card, the event is essentially a one-card silencing.  Worth saving these events for moments when the target faction has urgent business.

## 4. Brilliant Stroke and Treaty of Alliance

**[M] §2.3.8**: Each faction starts with 1 Brilliant Stroke card (the French start with 2, one of which is Treaty of Alliance).  A BS can be played to **interrupt** the sequence of play and cancel a currently played Event card — provided:

- The playing faction is Eligible
- The 1st Eligible faction has not yet acted
- No Winter Quarters card is showing

**The trump hierarchy (top can trump anything below):**

1. **Treaty of Alliance** — trumps any other BS, cannot itself be trumped
2. **Indian BS** — trumps all except ToA
3. **French BS** (non-ToA) — trumps Patriots and British
4. **British BS** — trumps Patriots
5. **Patriot BS** — cannot trump

A trumped BS is **returned to its owner** for later use.

**[M]** After any BS resolves (including a trumped one being replaced), **all four factions become Eligible**.

### Leader requirement

**[D]** *"If a Faction plays a Brilliant Stroke card, the Leader must be in a space involved in at least one of the Limited Commands (including an origination space for a March, Scout, Raid or Garrison Limited Command). If not, the Brilliant Stroke cannot be played."*
— Buchanan, *Brilliant Strokes in Liberty or Death*

This is the single most-missed restriction.  Plan your leader's location ahead of when you want to play the BS.

### Treaty of Alliance specifics

**[M] §2.3.9**: ToA can be played when:
- French Preparations > 15 (Available French Regulars + Squadrons/Blockades + CBC)
- French Faction is Eligible
- 1st Eligible has not acted
- No WQ card showing

> **[D]** *"In the early War Scenarios, the French rarely play the Treaty of Alliance card before the end of the 1776 Campaign."*

> **[D]** *"The French option of when and how to enter the War is perhaps the most powerful event in the game.  The power of this choice defines the fun in playing the French."*
> — Buchanan, *On Victory Conditions and Playing the French*

### When to play your Brilliant Stroke

- **Set up the leader first.**  March your leader into the right space *before* the card you want to interrupt arrives.
- **Watch for trump-vulnerable moments.**  Patriots can never trump; play Patriot BS against an event where no higher-priority faction would want to interfere.  British BS is vulnerable to French and Indian trump — pick a moment when neither French nor Indians have setup to play their BS.
- **The "obvious" play is often anticipated.**  Strong COIN players will guess your BS timing.  If you can wait one card past when it seems obvious, you may catch them off-guard.

---

# Part II — Per-faction strategy

## 5. British

### Position summary

The British are mechanically the simplest faction (one resource source, one main Support-shifting tool) but strategically the hardest to *win* with.

> **[D]** *"It can be miserable being the British – it is a long hard war and it is rare if not impossible that the British win during an early victory check."*
> — Harold Buchanan

The British arc is **a long grind toward final-round score**, not a knockout punch.  Expect to be playing for game-end position throughout, not for a mid-game Victory Check win.

### Margin 1 plan (Sup > Opp + 10)

Your only direct Support-shifting tool is **Reward Loyalty during Muster** (§3.2.1):
- Space must be British-Controlled, have ≥1 Regular and ≥1 Tory
- 1 Resource per Raid/Propaganda marker removed (must clear markers first)
- Then 1 Resource per shift toward Active Support
- Max 2 shifts per space per phase
- **Gage capability:** *first* RL shift in Gage's space is free

**[C] The canonical British recipe:**
1. **Land troops** via Muster — place Regulars in coastal Cities (Boston, NYC, Philadelphia, Norfolk, Charles Town, Savannah).  These start British-controlled by default in most scenarios.
2. **Raise Tories** via Muster (up to 2 per space, 1 if Passive Opposition).
3. **Reward Loyalty** to flip Neutral/Passive spaces toward Active Support.

A single Limited-Command Muster can produce dramatic swings — Adam Weeks's solo play documented 6 Regulars + 2 Tories + Reward Loyalty in Norfolk for 2 Resources total, shifting it to Passive Support.

### Margin 2 plan (CRC > CBC)

**Symmetric arithmetic** — the formula is "Rebellion Casualties minus British Casualties."  Preventing your own losses matters as much as inflicting theirs.

**Levers that help CRC:**
- **Battle** — but only when you'll win.  See common mistakes.
- **Skirmish** SA — targeted, lower-risk Patriot removal in a non-Battle space.  Free Tory cube too sometimes.
- **Common Cause** during Battle, when Indian WPs let your force level dominate.
- Events that inflict Rebellion casualties (card 30 Hessians places more Regulars, card 79 Culper Ring lets you Activate 3 Patriot Militia anywhere — eliminating their RR/Persuasion utility).

**Levers that prevent CBC:**
- Avoid attacking when the Rebellion will win — Win-the-Day shift hurts you on Margin 1 too.
- Garrison up before Winter Quarters; isolated forces pay Supply costs and risk removal.
- Use Naval Pressure (Blockade) when French is active to make their Battles costlier for them.

### Command priorities by phase

**Opening (cards 1-10):** Muster → Reward Loyalty in 1-2 high-pop coastal cities.  Establish at least one Tory-holding Colony as a forward base.  Don't waste Resources on speculative Battles.

**Mid-game (cards 10-40):** Continue Muster + RL across the South (where Patriot presence is weaker).  Use Garrison to consolidate forces in Controlled Cities.  Pick spots for high-EV Battles where Patriot pieces are exposed (no Fort, force ratio favors you).

**Late game (last campaign before final WQ):** Position for final-round score.  Make sure your forces are in Controlled Cities or with Forts for Winter Quarters Supply.  Eliminate Patriot pieces where you can to widen CRC − CBC.

### Special activities

- **Common Cause (§4.2.1):** Use Indian WPs as Tory-equivalents in a March or Battle space.  Powerful but burns the Indian player's WP inventory.  **Watch the Indian player's reaction** — repeated CC without compensating Trade transfers will sour the partnership.
- **Skirmish (§4.2.2):** "In any one space or West Indies with both British Regulars and Rebellion pieces and no Battle, Garrison destination or Muster space."  Three options (remove 1 cube; remove 2 cubes + sacrifice 1 Regular; remove a Fort + sacrifice 1 Regular).  **Clinton** in the space adds 1 extra Militia removal.
- **Naval Pressure (§4.5.2):** If FNI > 0 and Gage or Clinton is on-map: remove 1 Blockade.  If FNI = 0: +1D3 British Resources.  Critical Resource pump in the mid-game.

### Brilliant Stroke timing

British BS is vulnerable to French and Indian trump.  Best windows:
- After ToA fires but before Indians have their BS leader well-positioned
- During a campaign year where French is busy with their own buildup
- Pick a turn where the *target event* is bad enough that you'd want to cancel it AND your leader is in a space where you can launch a meaningful Limited Command

### Scenario-specific British notes

- **1775 Long:** Plenty of time to build.  Use Hessians (card 30) when it lands (Musket icon — Event is preferred); accept Regulars from Unavailable.  Don't rush South — establish the North first, then push.
- **1776 Medium:** First Winter Quarters brings 6 Regulars + 6 Tories (release date).  Position carefully so the new units land in useful Cities.  Patriots will be running their RR engine hard; consider Reward Loyalty in early-Passive-Opposition spaces to slow them down.
- **1778 Short:** Less time, all four factions on-map, French will play ToA almost immediately.  Be aggressive — every card matters.  Naval Pressure to clear French Blockades is critical for keeping your sea movement.

### Common British mistakes

1. **Attacking when Rebellion will win.**  §3.6.8 Win-the-Day shifts toward the winner.  A failed British attack hurts you twice (lost cubes → CBC up; Opposition shift → Margin 1 hurt).  The lod-bot Force-Level heuristic gets this wrong about 1-2% of the time across 150 games — humans should be more careful.
2. **Spreading too thin.**  Forces not in Controlled Cities/Forts during Winter Quarters Supply pay Resources or are removed.  Concentrate where you'll defend, don't try to occupy everything.
3. **Wasting Brilliant Stroke.**  Once-per-game, leader-tied, easily trumped.  Don't burn it on a marginal interrupt.
4. **Letting the Indians collapse.**  British needs Indians for Common Cause, Trade resource transfers, and to absorb some Rebellion attention.  Throw them enough Trade Resources to keep them functional.
5. **Ignoring CBC.**  Each cube you lose in a Battle is a permanent CBC point that helps French.  "Save your Regulars" should be a constant thought.

---

## 6. Patriots

### Position summary

Cash-starved, propaganda-focused, **don't fight unless you have to**.

> **[D]** *"This game does not reward a Washington that wants to Battle continually."*
> — Buchanan

> **[C]** *"Players have had their most success when the Patriots avoid battle, focus on getting the French in the fight and use propaganda."*
> — BGG personal review (thread 1559042)

Your engine is **Rabble-Rousing + Persuasion** — a self-amplifying combo that shifts spaces toward Active Opposition while refilling your Resource pool.

### Margin 1 plan (Opp > Sup + 10)

**Rabble-Rousing (§3.3.4):** 1 Resource per selected space; shifts the space toward Active Opposition by 1 level; places a Propaganda marker.  Requires:
- Rebellion Control + ≥1 Patriot piece in the space, OR
- ≥1 Underground Militia (any control)

**Persuasion (§4.3.1):** Up to 3 Colonies/Cities with Rebellion Control + Underground Militia.  Each:
- Activates 1 Underground Militia → Active
- **Adds 1 Patriot Resource**
- Places a Propaganda marker

Per §4.1 you can only do **one** Special Activity per Command.  Persuasion (1 SA) can hit up to 3 spaces.

**The engine:** RR several spaces → Resources hit 0 → Persuasion 3 spaces → +3 Resources → continue RR.  A single turn can flip 4-6 spaces toward Opposition.  This is *the* canonical Patriot Support-shifting engine and is the reason Patriots dominate 1776 — the starting position has 4-5 immediately Persuasion-eligible spaces.

### Margin 2 plan (Forts + 3 > Villages)

**You start +3 ahead** just by existing.  Maintain or extend the lead, don't let it slip.

**Forts come from Rally** — replace Continentals in a space with a Patriot Fort.  Costs precious Continental units.  Tension: Continentals are also your line battle force.

**Indians attack your Forts via War Path option 3** (when no Rebellion pieces share the space).  Don't let Patriot Forts sit isolated with no nearby Continentals/Militia, especially in Provinces adjacent to Indian Reserves.

**Strategic balance:** Build enough Forts to maintain the Margin 2 lead, but don't over-build at the cost of Continentals.  Aim for ~5-6 Forts by mid-game.

### Frontier discipline — non-obvious but critical

> **[C]** *"The Colonists win the war by killing Native Americans, not by running the British out of the country—that's how the French win. If the British have been expelled but the Colonists have not burned sufficient Native American villages to the ground, the Colonists will lose."*
> — Players' Aid Review

Patriot endgame Margin 2 is half about Forts you have, half about Villages they don't.  **Reduce Indian Villages** when you can:
- Attack Indian-occupied Provinces with a Battle, removing Villages as cube-equivalents
- Use card-driven Village removal effects when they appear

### Command priorities by phase

**Opening (cards 1-10):**
- Run the RR + Persuasion engine in Rebellion-controlled spaces with Underground Militia
- Use **French Hortalez funding** when offered — Patriot Resources are precious
- Build *one* Fort somewhere safe (Margin 2 cushion); usually Massachusetts or Philadelphia
- Don't Battle unless you're winning by a wide force-level margin

**Mid-game (cards 10-40):**
- Continue RR but watch for Active-Opposition saturation (RR can't shift further once Active Opp)
- Train Continentals via Rally
- Pick a couple of well-defended Provinces to Battle into (look for British Regulars without Tory support)
- Watch the Indians on the frontier — if their Villages are growing, plan a punitive Battle into an Indian Province

**Late game (last campaign before final WQ):**
- Position Continentals for late Battles (with French help if possible)
- Make sure Margin 2 is comfortable — at least Forts ≥ Villages so Margin 2 > 2
- Use Brilliant Stroke if you've held it; Patriot BS can't trump anyone so timing matters

### Special activities

- **Persuasion (§4.3.1):** as above.  Once per Command (§4.1).  Pick the 3 best Rebellion-Controlled Colonies/Cities with Underground Militia.
- **Partisans (§4.3.2):** Activate 1 Underground Militia + remove 1 Royalist unit in one space.  Useful when you'd otherwise lose a Fort or want to strip a British presence without a Battle.
- **Skirmish (§4.3.3):** Same as British version but for Patriots.  *"Skirmish with the British in small numbers to make their stay expensive."*

### Brilliant Stroke timing

Patriot BS (Washington) **cannot trump anyone**.  So:
- Play it when no one will trump (e.g., during a card where French ToA isn't yet possible AND Indians/British don't have setup)
- Wait until Washington is in a space where you can launch a meaningful Limited Command — usually a Province with Continentals and Patriot Fort
- The BS often most useful for setting up a decisive Battle the British isn't expecting

### Scenario-specific Patriot notes

- **1775 Long:** Slow build.  Patriot starts with limited pieces.  Use RR + Persuasion in Massachusetts and Philadelphia to start tilting the Opposition track.  French is purely a funder for the first 2+ years — extract Hortalez funding aggressively.  Build the southern army (Charles Town, NC, Virginia) by mid-game.
- **1776 Medium:** **Easy mode** for Patriots.  Starting position is +2 on the Opposition track and has 4-5 Persuasion-eligible spaces.  A well-played Patriot can win at the FIRST Winter Quarters via RR engine alone (this is what the lod-bot smoke matrix shows at 98-100%).  Don't get cute — execute the engine consistently.
- **1778 Short:** Aggressive game.  French is on-map already and will play ToA immediately.  Coordinate Battles with French (Rochambeau makes joint Battles free).  Less time to build, more pressure to act.

### Common Patriot mistakes

1. **Fighting too much.**  Per Buchanan, Continentals are expensive and Battle is the wrong path for Patriot wins.  Use RR/Persuasion/Partisans first.
2. **Ignoring the frontier.**  Indians are non-obvious enemies — every Indian Village they build hurts your Margin 2 even though they're "on the other side."
3. **Letting French run away with CBC.**  If French is killing all the British, French wins Margin 2.  Make sure you're scoring CBC too (kill some Brits yourself).
4. **Mistiming Persuasion.**  Persuasion is once per Command per §4.1.  Don't waste it on 1 space when you could hit 3.  But also: it's *only* useful when you have Underground Militia in eligible Rebellion-Controlled spaces.  If you don't, it can't fire.
5. **Building too many Forts too early.**  Each Fort costs you Continentals that you might need later for Battle.  Build to maintain Margin 2, not to maximize it.

---

## 7. French

### Position summary

**Pre-ToA you are a diplomat.  Post-ToA you are an expeditionary force.**  The transition between these two roles is the most important strategic decision in the game.

> **[D]** *"The French option of when and how to enter the War is perhaps the most powerful event in the game.  The power of this choice defines the fun in playing the French."*

### Pre-ToA (mostly 1775/1776)

You cannot Battle.  You cannot place pieces on the map (except via Agent Mobilization).  Your job is:
- **Roderigue Hortalez et Cie (§3.5.2):** Pay French Resources to give Patriots (paid amount + 1) Resources.  This is the Patriots' main funding source.
- **French Agent Mobilization (§3.5.1):** Place 2 Militia or 1 Continental in Quebec, NY, NH, or Mass.  Helps Patriot board presence.
- **Préparer la Guerre (§4.5.1):** Move 1 Blockade from Unavailable to West Indies; or up to 3 French Regulars from Unavailable to Available.  This is how French Preparations climb.

**French Preparations** = Available French Regulars + Squadrons/Blockades + CBC.  ToA requires Preparations > 15.

**Timing math:** You start with ~6 French Regulars Available + some Squadrons.  You'll need to use Préparer la Guerre several times AND let CBC accumulate (i.e., let the Patriots kill British) to reach Preparations 16+.

> **[D]** *"The French Faction can accelerate entry if the Patriot player kills the British."*

**Strategic implication:** Pre-ToA, encourage Patriots to fight (via funding) only when British casualties are likely.  Hortalez timing matters — funding for a doomed Patriot Battle is wasted CBC.

### Post-ToA transformation

> **[D]** *"Once the French enter the War by playing the Treaty of Alliance card, the map changes dramatically: The West Indies come into play and get a significant amount of British and French interest, and the French Blockade completely changes British flexibility and freedom to choose Special Activities."*

You gain:
- **March, Battle access** with French Regulars
- **Naval Pressure (Blockade):** Place a Blockade in a British-controlled City to prevent British sea movement; significant Battle modifier
- **Muster** in West Indies or Rebellion-controlled spaces (1 space at a time)
- **Rochambeau leader bonus:** French March/Battle with Patriot Command at no Resource cost (when French Regulars in Rochambeau's space)
- **Lauzun leader bonus:** +1 Defender Loss when French is attacking

### Margin 1 plan (Opp > Sup + 10)

You have **no direct Support-shifting command**.  Your contributions are indirect:
- Win-the-Day shifts from Battles you participate in (Rebellion winner shifts toward Opposition)
- Setup for Patriot RR engine (funding via Hortalez)
- Blockade in Battle cities (Battle modifier helps you win → Win-the-Day shift)

The French Margin 1 essentially **rides the Patriot Margin 1**.  Your job is to keep the Patriot engine fed and to win Battles for the Win-the-Day shifts.

### Margin 2 plan (CBC > CRC)

> **[D]** *"This leads to the Secondary Victory condition between the French and British: pieces eliminated. Make the other Faction pay a high price for involvement and pull pressure off other critical theaters."*

**Direct British casualty count.**  Levers:
- Battle British-occupied spaces with strong French force (Rochambeau helps you afford it)
- Naval Pressure Blockade as Battle modifier
- Watch for Lauzun's +1 Defender Loss for clutch Battle outcomes

**Critical tension with Patriots:** Both factions want British dead, but they're competing on CBC.  If Patriots kill all the British and you don't, **you lose Margin 2 to them**.  After ToA, prioritize French-participated Battles even when Patriots could do it solo.

### Command priorities by phase

**Pre-ToA opening (cards 1-15 in long scenario, less in 1776):**
- Préparer la Guerre every turn you can (build toward Preparations 16)
- Hortelez when Patriot Resources are low (< some threshold; the French bot uses 1D3)
- Agent Mobilization to seed Patriot units in NY/Mass corridor
- Save your BS leaders (Rochambeau, Lauzun) for post-ToA

**Pre-ToA mid-game:** Watch for the ToA trigger window.  Want to play ToA when:
- Preparations > 15 (mandatory)
- Patriot is about to take a major action that benefits from French support
- No higher-priority faction (Indians) has BS setup that could trump

**Post-ToA:** Active expeditionary play.  Coordinate with Patriots for joint Battles.  Use Naval Pressure aggressively to clear British movement.  Build Blockades around key British Cities.

**Late game:** Final Battles for CBC.  Make sure your CBC lead over CRC is solid.

### Special activities

- **Préparer la Guerre (pre-ToA only, §4.5.1):** Blockade or Regulars from Unavailable.  Always available pre-ToA, never useful post-ToA.
- **Naval Pressure (§4.5.2):** Post-ToA Blockade placement/removal.  Blockades affect Battle.
- **Battle modifier from Lauzun** (passive, not an SA)

### Brilliant Stroke timing

You have **two** BS cards: Treaty of Alliance and one regular BS (typically Rochambeau-led).

- **ToA timing:** As above.  Buchanan says rarely before end of 1776 Campaign.  But the longer you wait, the more time Patriots have to lose Margin 1.  Generally: play ToA when Preparations hits 16-18 and the Patriots are well-positioned for an offensive push.
- **Second BS:** Available after ToA fires.  Use it for a decisive joint Battle or to interrupt a critical British event.  French BS can trump Patriots and British (not Indians or ToA).

### Scenario-specific French notes

- **1775 Long:** Long pre-ToA period.  Patient buildup via Préparer + Hortelez.  Don't rush ToA.
- **1776 Medium:** Pre-ToA is tighter — usually only 1-2 years before ToA fires.  Buildup faster.
- **1778 Short:** ToA almost immediately.  French Regulars are pre-positioned but the Treaty isn't played.  Play ToA early (often turn 1-3) and then run expeditionary play.

### Common French mistakes

1. **Playing ToA too early.**  If Preparations is at 16 but you only have 4 French Regulars Available, post-ToA you'll have nothing to fight with.  Wait until you have at least 8-10 Regulars + a couple of Blockades ready.
2. **Playing ToA too late.**  If you let Patriots lose Margin 1 before you can help, the side war is lost and French has no path.
3. **Funding doomed Patriot operations.**  Hortelez Resources to a Patriot turn that won't kill any British is wasted (it doesn't advance Preparations).
4. **Letting Patriots take all the British casualties post-ToA.**  Both sides want CBC; if Patriots get them all, French loses Margin 2.
5. **Forgetting Rochambeau / Lauzun positioning.**  These leaders' bonuses are per-space.  Move them ahead of the action.

---

## 8. Indians

### Position summary

> **[C]** *"The Indian Faction is one of the most overlooked Factions in the game, but their menu of actions can carry them to victory. Most of the time the Patriots and French, as well as their own ally the British, just ignore and overlook the Indians allowing them to always be in the game at the end reckoning."*
> — Players' Aid Indian COIN Workshop

You are weak in the short term and **sticky** in the long term.  Patient Village-building plus opportunistic Patriot harassment can win at game end while everyone else has been fighting over the central theater.

### Margin 1 plan (Sup > Opp + 10)

You have **one direct Support-shifting tool: Raid (§3.4.4)**.  Up to 3 Provinces; shifts Opposition toward Neutral by 1 level; places a Raid marker (blocks RR/Persuasion bonuses in that space).

A single Raid command into 3 Opposition Provinces can swing the track by 3-6 points.  Combined with the marker that hampers Patriot RR, this is your main contribution to the Royalist side.

Beyond Raid, you're relying on the British to do the heavy Margin 1 lifting via Reward Loyalty.

### Margin 2 plan (Villages − 3 > Patriot Forts)

**You start −3 behind.**  You need 4+ more Villages than Patriot Forts at game end to score positive Margin 2.  At minimum, build 6+ Villages.

**Gather (§3.4.1):** Build Villages where 3+ War Parties present (2+ if Cornplanter in space).  Replace 2 WPs with 1 Village.  Costs 1 Resource per Province (first selected Indian Reserve is free).

**Cap:** 2 Villages per Province × 4 Indian Reserves (Quebec, Florida, Northwest, Southwest) = 8 "safe" Village slots.  You can also build Villages in Colonies adjacent to Reserves but they're more vulnerable.

**War Path option 3 (§4.4.2):** When no Rebellion pieces in a space, removes 1 Patriot Fort.  Your only Fort-removal tool — use it when opportunities arise.

### Visual margin-2 check

> **[C]** *"There is no great need to calculate the '+3' mathematically since the Indian Villages and Patriot Forts tracks on the map do it for you visually. The Forts track is offset by 3 holding 'boxes' (circles/stars) compared to the Villages track, so if the 'lowest' empty Village circle on the Village track is 'below' the lowest empty Fort star on the Forts track the Indians are ahead in their victory condition."*

So you don't need to do mental arithmetic — just compare the track positions visually each Winter Quarters.

### Command priorities by phase

**Opening (cards 1-10):**
- **Gather** to build War Party numbers in Indian Reserves (free in first selected Reserve)
- Once a Reserve has 3+ WPs, start building Villages (one per Gather Command)
- **Trade** with British for Resources when your pool is low

**Mid-game (cards 10-40):**
- **Raid** Opposition Provinces to shift toward Neutral (helps British Margin 1)
- **War Path option 3** when Patriot Forts are isolated
- **Plunder** Patriot Resources from Provinces with more WPs than Rebel pieces
- Keep building toward 6-8 Villages

**Late game:** Defensive Village protection.  Avoid getting drawn into British Battles (CBC is not your concern).  Make sure each Indian Reserve has WPs to defend Villages.

### Special activities

- **War Path (§4.4.2):** Three options.  Option 3 (remove Fort) is the only Indian way to dent Patriot Margin 2.
- **Trade (§4.4.1):** In a Province with WP + Village.  British may transfer Resources (0+); if 0 transferred, Indians get 1 flat.  Activates 1 WP.  **Critical resource refill.**
- **Plunder (§4.4.3):** Steal Patriot Resources from a Province with more WPs than Rebel pieces.

### Brilliant Stroke timing

Indian BS can trump anything except ToA.  This is very powerful — Indians are the highest-priority trumper outside the Treaty of Alliance.

Best windows:
- After ToA is played (no longer trump risk from ToA)
- When the just-played Event is bad for the Royalist side AND your BS leader is in the right space
- Specifically watch for *Patriot* BS plays — your Indians BS trumps theirs

### Coordination with British

> **[C]** *"The Indians are so weak and quite wretched when left on their own but when properly and skillfully used to support and guide the mighty columns of Regulars to battles, can truly be game changing. The Indians can do little to directly raise support or remove Patriot forts. They depend on the British to do the bulk of the fighting."*

**You need British cooperation:**
- Trade Resources (your main funding source)
- Common Cause activations that help Britain win battles → keeps Britain alive
- British Margin 1 wins (Reward Loyalty) → your Margin 1 wins too

**But British also competes with you (sort of):**
- British Margin 2 is CRC > CBC — not directly competing with your Forts/Villages
- However, British attention is finite — if British is busy with French/Patriots, they may not have resources to throw you in Trade

### Scenario-specific Indian notes

- **1775 Long:** Indians start with some WPs and 0-1 Villages.  Plenty of time to build.  Patient Gather → Village pipeline.
- **1776 Medium:** Same as 1775 but compressed.  Patriot RR engine will hammer the Margin 1 track hard — your Raid is critical to counter-balance.
- **1778 Short:** Active game from turn 1.  All four factions on map.  Use Raid aggressively early, then settle into Village-building rhythm.

### Common Indian mistakes

1. **Trying to win Margin 1 solo.**  Without British, you can't.  Raid contributes but isn't enough.  Rely on British Reward Loyalty as the main Margin 1 lever.
2. **Spreading too thin.**  Concentrate WPs in 2-3 Reserves rather than 1 in each of 8 spaces.  Concentrated WPs let you Gather, Raid, and defend.
3. **Letting British exhaust your WPs via Common Cause without compensation.**  Negotiate Trade Resources for CC use.  Don't let yourself become a free-WP factory.
4. **Forgetting War Path option 3.**  Patriot Fort removal is rare and precious.  Watch for isolated Forts and strike.
5. **Building Villages in Colonies adjacent to Patriot pieces.**  Easier targets for Patriot Battles.  Stick to Reserves where possible.

---

# Part III — Scenario-specific notes

## 9. 1775 "A People Numerous and Armed" (Long)

**Years:** 1775-1780.  **Pace:** Slow build, rewards patience.

**Starting position highlights:**
- French *completely* off-map; no French units in play at all
- Patriots start with limited pieces; relies on French Hortalez funding
- British has many Regulars on-map but spread across coastal cities
- 0-1 starting Forts and Villages

**Strategic shape:**
- French has 2+ years before ToA becomes realistic.  Long diplomatic phase.
- Patriots build slowly via RR + Persuasion; Continentals come online mid-game
- British establishes Northern + Southern theaters
- Indians have plenty of time to build Villages

**Faction priorities:**
- **British:** Long grind toward game-end score.  Buildup North first, then South.  Don't rush.
- **Patriots:** RR/Persuasion engine + frontier discipline.  Build Forts to maintain Margin 2 buffer.
- **French:** Préparer + Hortelez.  Don't play ToA before late 1776 unless French Preparations are unusually high.
- **Indians:** Village-building campaign.  Aim for 6+ Villages by mid-game.

**Recommended for:** Players who want the full COIN experience with all four factions involved across many cards.  The lod-bot smoke matrix shows Patriots ~76%, British ~14%, Indians ~10%, French ~0% — but this reflects bot play limits.  Human play should be more balanced; French in particular can do better with patient ToA timing.

## 10. 1776 "British Return to New York" (Medium)

**Years:** 1776-1779.  **Pace:** Medium.  **Tutorial recommended by playbook.**

**Starting position highlights:**
- French still off-map (same as 1775)
- British receives 6 Regulars + 6 Tories at first Winter Quarters (release date)
- Patriot starts with 1 Fort (Massachusetts), Continentals + Militia spread
- Massachusetts starts at Active Opposition (the big one — pop 2 × 2 = 4 Opposition)
- 4-5 Persuasion-eligible spaces (Rebellion Control + Underground Militia)
- Starting Opposition track is ~2 ahead of Support

**Strategic shape:**
- **Patriots dominate** in bot play (98-100% bot wins).  Human play is more balanced but Patriots still favored.
- 1776 starting position is **structurally pro-Patriot** — only 8 points from Margin 1 victory, 4-5 RR-ready Underground Militia, +3 Margin 2 head start.
- French ToA usually fires by end of 1776 or early 1777
- British must work hard to slow Patriot RR engine

**Faction priorities:**
- **British:** Reward Loyalty in early-Opposition spaces (Boston, Massachusetts) to fight the RR tide.  Use Common Cause aggressively.  Don't waste Resources on weak Battles.
- **Patriots:** Run the RR + Persuasion engine.  Focus on the 4-5 starting Persuasion-eligible spaces.  Build Continentals + maintain Forts.
- **French:** Same pre-ToA play as 1775 but compressed.  Push ToA in late 1776 if possible.
- **Indians:** Raid hard to counter Patriot Opposition surge.  Build Villages quickly in Northwest/Southwest.

**Recommended for:** Beginners (per the playbook).  Also for players who want a faster game than 1775 Long.

**Note on the 1776 imbalance:** This is structural per the published bot flowcharts, not a bot bug.  Human play will narrow the gap (humans can recognize and counter the Patriot RR engine in ways the bots can't).  See `audit_report.md` Session 17 for the detailed investigation.

## 11. 1778 "The Southern Campaign" (Short)

**Years:** 1778-1780 (or 1778-1779 in the "Sprint" sub-variant).  **Pace:** High pressure.

**Starting position highlights:**
- All four factions on-map at full capability
- French pre-positioned but **ToA not yet played** (must be played early in scenario)
- CBC=10 baseline (significant French head start on Margin 2)
- All Brilliant Strokes pre-positioned (where playable per leader location)

**Strategic shape:**
- ToA fires in turn 1-3 typically.  French immediately becomes expeditionary.
- Short scenario means less time to recover from mistakes
- French + Patriots have a big Margin 1 advantage from initial Opposition track + RR engine
- British has Naval Pressure to disrupt French sea movement

**Faction priorities:**
- **British:** Aggressive play — every card matters.  Use Reward Loyalty to slow Opposition.  Battle when ratios favor you.  Brilliant Stroke early.
- **Patriots:** Coordinate with French.  Rochambeau makes joint Battles free — exploit this.  RR engine still works.
- **French:** Play ToA turn 1-3.  Then run aggressive Battle play.  Naval Pressure to lock down British movement.  Use Rochambeau + Lauzun bonuses.
- **Indians:** Raid + Village-building.  Less time = less Village inventory but also less Patriot pressure (they're focused on French).

**Recommended for:** Experienced players who want a tight, decisive game.  French and Patriots favored per typical play (~50% combined French + Patriot).

---

# Part IV — High-impact cards

## 12. Brilliant Stroke cards (105-109)

| Card | Faction | Notes |
|---|---|---|
| 105 | British | Led by current British leader.  Vulnerable to French/Indian trump. |
| 106 | Patriots | Led by Washington.  Cannot trump anyone.  Plan around no-trump windows. |
| 107 | French (regular) | Available after ToA played.  Trumps Patriots and British. |
| 108 | Indians | Trumps everyone except ToA.  Most powerful non-ToA BS. |
| 109 | French (Treaty of Alliance) | Trumps everything, untrumpable.  Single biggest decision in the game. |

## 13. Other high-impact cards

**Card 13 "Common Sense" (dual):**
- British: Place 2 Regulars + 2 Tories in any City + 2 Propaganda + 4 Resources
- Patriots: Shift 2 Cities one level toward Active Opposition + 2 Propaganda in each
- Note: Propaganda markers must be cleared before either side can use Reward Loyalty / Rabble-Rousing in those spaces

**Card 24 "Declaration of Independence" (dual):**
- Iconic Patriot card.  Patriots want to be Eligible when it surfaces.
- Patriot side: Place up to 3 Militia anywhere + 1 Propaganda each + 1 Fort anywhere (shaded)
- British side: Patriots stay fractured — remove 2 Continentals + 2 Militia + 1 Fort (unshaded — this is the bot trap I documented in Session 17)

**Card 30 "Hessians" (British Musket):**
- British prefers Event (bot does too)
- Effect: In up to 3 British-controlled spaces with British Regulars, place up to 2 Regulars from Available or Unavailable + British Resources +2
- Watch the eligibility window — if British is Ineligible when this lands, opportunity lost

**Card 39 "King Mob":**
- Shift toward Neutral effect
- Strategic weight unclear from web research — not highly discussed in community

**Card 53 "The World Turned Upside Down":**
- British/Indian: Place 1 Fort or Village
- Patriot/French: Remove 2 British Regulars to Casualties (swings CBC vs CRC)
- *"if you use the event at the right time, possibly prior to a Winter Quarters Round and a Victory Check, you could find yourself gaining the number of Victory Points needed to tip you over the top and win the game"*

**Card 79 "Culper Ring":**
- British/Indian: Activate 3 Patriot Militia anywhere (eliminates their RR/Persuasion utility)
- Patriot/French: Remove 3 British Cubes (Regulars or Tories) to Casualties
- *"This is a key action because it can cause the shifting of the delicate balance for the British between Combined Rebellion Casualties (CRC) versus Combined British Casualties (CBC)."*

**Indian-flagged cards** (Indians act first):
- Card 75 "Congress' Speech to the Six Nations"
- Card 83 "Guy Carleton and Indians Negotiate"
- Card 84 "Merciless Indian Savages"
- Card 96 "Iroquois Confederacy" (Mohawk/Brant connection)

## 14. Winter Quarters cards (97-104)

**Seeded in the deck** — *"randomly placed among the last four cards of each deck pile."*  You roughly know when they're coming.

**Each WQ triggers:**
- **Victory Check Phase:** All factions check Margins.  Both must be positive (strict >0) for a win.
- **Resource Phase:** British +Resources for British-controlled City pop; French +Resources for non-British City pop; etc.
- **Support Phase:** various scenario-specific reorganizations

**Strategic implications:**
- Don't have forces in remote spaces during WQ Supply — they'll cost Resources or be removed
- Position leaders for WQ if changes apply
- Time your offensive pushes for the cards just before WQ (high-impact, then WQ check)

---

# Part V — Partnership cooperation tensions

## 15. British ↔ Indians

**What helps both:** British Reward Loyalty (good for both Margin 1).  Indian Raid (helps British Margin 1 via Opposition reduction).

**Friction points:**
- **Common Cause:** British uses Indian WPs as Tory-equivalents.  Helpful for British Battles but burns Indian Village-building inventory.
- **Trade:** British decides how much (if any) Resources to give Indians.  British can give 0 — but Indians remember.
- **Margin 2 isolation:** British (CRC vs CBC) and Indians (Villages vs Forts) don't compete directly on Margin 2.  So at game-end, both can win independently if the Royalist side won Margin 1.

**How to manage as British:** Throw Indians enough Trade Resources to keep their WP pool healthy.  Use Common Cause sparingly — every CC depletes Indian inventory.  Indians ignored for too long will defect (in spirit if not mechanics).

**How to manage as Indians:** Make CC use a quid-pro-quo — *"If you Common Cause me, you owe me a Trade Resource next turn."*  Don't accept too many CC raids without compensation.  Use your BS to support British when it benefits Margin 1 AND your own positioning.

## 16. Patriots ↔ French

**What helps both:** French Hortalez funding to Patriots.  French Naval Pressure post-ToA.  Joint Battles with Rochambeau bonuses.  Both want Opposition track high.

**Friction points:**
- **CBC competition:** Both want British dead, but CBC is split.  If French takes all the British casualties, Patriots win nothing on Margin 2.
- **Resource flow:** Hortelez moves French Resources to Patriots.  When French needs Resources for ToA Preparations, this gets tight.
- **Battle initiative:** Battles benefit the initiator more (especially with Rochambeau).  Who initiates determines who scores the CBC.

**How to manage as Patriots:** Don't over-extract from French.  Make sure you initiate enough Battles personally to score CBC.  Coordinate with French on which Province to push next.

**How to manage as French:** Negotiate Patriot-led vs French-led Battles ahead of time.  When you want post-ToA CBC, attack British-occupied spaces yourself.  Don't let Patriots cherry-pick all the British targets.

---

# Part VI — Common mistakes catalog

## All factions

1. **Overextending into Winter Quarters.**  Forces not in Controlled Cities/Forts pay Resources or are removed.  Plan Winter positions ahead of time.
2. **Wasting Brilliant Stroke.**  Once per game (twice for French), leader-tied, trump-vulnerable.  Don't burn it on a marginal interrupt.
3. **Ignoring the upcoming card.**  Next card is revealed.  Sequence your Eligibility around it.
4. **Failing to count Margin 2 throughout.**  Don't wait until the final WQ to realize you're 2 points short.

## British-specific

5. **Attacking when Rebellion will win.**  Win-the-Day hurts you on both axes.
6. **Spreading too thin geographically.**  Concentrate.
7. **Letting Indians collapse.**  You need them for CC and to absorb Patriot attention.
8. **Hoarding Resources for a "decisive moment" that never comes.**

## Patriot-specific

9. **Fighting when you should be propagandizing.**
10. **Ignoring the frontier (Indians).**  Their Villages cost you Margin 2.
11. **Building Forts that don't serve a purpose.**  Each Fort = Continentals you can't use in Battle.
12. **Letting French take all the British casualties.**

## French-specific

13. **Playing ToA too early or too late.**  Both lose the game.
14. **Funding Patriot operations that don't kill British.**  Wasted CBC.
15. **Forgetting Rochambeau / Lauzun positioning.**  Per-space bonuses are huge.
16. **Skipping Préparer la Guerre when you could play it.**  Slows ToA timing.

## Indian-specific

17. **Trying to win Margin 1 without British help.**  Can't.
18. **Letting British exhaust your WPs without Trade compensation.**
19. **Forgetting War Path option 3 against isolated Patriot Forts.**
20. **Building Villages in vulnerable Colonies.**  Stick to Reserves.

---

# Part VII — Recommended further reading

**Primary sources (must-read):**

- The Manual (in your game box or in `Reference Documents/` of the lod-bot repo): Ch 1 (basics), Ch 2 (sequence), Ch 3 (commands), Ch 4 (SAs), Ch 6 (year-end), Ch 7 (victory), Ch 8 (bots).
- The Playbook: scenario setups + worked examples.
- Reference Card #110 (leader capabilities).

**Designer essays (InsideGMT — Harold Buchanan):**

- *On Victory Conditions and Playing the French in Liberty or Death* — definitive French strategy from the designer
- *The Campaign of 1777 – Liberty or Death* — mid-game British/Patriot dynamics
- *Brilliant Strokes in Liberty or Death* — leader-tied BS mechanics
- *Liberty or Death: Addressing Open Questions* — FAQ-style rules clarifications

**Community strategy:**

- Players' Aid: Kleinhenz's *COIN Workshop: LoD Indian Faction* (Jan 2023) is the deepest single-faction guide available
- Players' Aid: Kleinhenz's review (March 2017) for overall framing
- BGG strategy forum threads (require a browser to read):
  - 1723774 "Strategies for beginner players"
  - 1527844 "British Muster and Reward Loyalty"
  - 1541503 "Victory Condition Thoughts"
  - 1525893 "Thoughts on playing Winter Quarters immediately"
  - 1695790 "Bot Brilliant Stroke rules" (for solo players)
- Adam Weeks's Medium solo play (Sept 2016) — concrete turn-by-turn 1775 walkthrough

**For specific cards:**

- The Players' Aid has individual card-deep-dive posts (Cards 13, 53, 79, etc.) that walk through optimal usage

---

*End of strategy guide.  Good luck.  Remember: in the end, you win alone.*
