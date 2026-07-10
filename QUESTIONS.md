# QUESTIONS.md — Ambiguities requiring human decision

These items were identified during the compliance audit. The Reference Documents are either ambiguous, contradictory, or silent on these points. Per CLAUDE.md rules: no guessing — wait for human answer.

---

## Q1: Control access pattern — RESOLVED

**Decision:** Standardize on `state["control"][sid]`. All `sp.get("British_Control")`, `sp.get("Patriot_Control")`, and `sp.get("Rebellion_Control")` removed. `board/control.py` no longer sets per-space legacy flags.

---

## Q2: Card 70 (British Gain From French in India) — RESOLVED

**Decision:** Bot-specific removal per each faction's reference document:
- British: Remove French Regulars from WI, then spaces with British pieces.
- French: Remove British Regulars from spaces with Rebels.
- Indian: Remove French Regulars from Village spaces first.
- Patriot: Remove British Regulars from spaces with Patriot pieces.

---

## Q3: Queued vs immediate free ops — RESOLVED

**Decision:** Always immediate execution. Engine's `handle_event()` now drains all queued free ops immediately after the event handler returns, during event resolution.

---

## Q4: Brilliant Stroke (Cards 105-109) — RESOLVED

**Decision:** Full implementation per Manual §2.3.8, §2.3.9, §8.3.7.

Implemented:
- Trump hierarchy: ToA > Indians > French > British > Patriots
- Trumped BS cards return to owners (mark_bs_played → False)
- Bot auto-check before 1st eligible acts (bot_wants_bs conditions)
- Bot BS execution: LimCom + SA + LimCom, leader in space with pieces
- Treaty of Alliance: preparations > 15 (Available French Regs + all Blockades + half CBC)
- All factions become Eligible after BS resolves
- Simultaneous bot BS resolved via trump hierarchy

---

## Q5: Indian bot I10 March — RESOLVED

**Decision:** Implement ALL flowchart movements (not single move). The Indian bot March should attempt up to 3 movements per the flowchart bullets.

**Status:** Implemented. Session 12 verified: `_march()` uses `max_dests = min(3, resources)`, Phase 1 (Village placement) + Phase 2 (Rebel Control removal), all movement constraints correct (Underground-first, no last-WP-from-Village, no Rebel Control addition).

---

## Q6: French bot F5 — RESOLVED

**Decision:** Agent Mobilization first, Hortalez as fallback. The current code already implements this correctly.

---

## Q7: BS bot command priorities in _execute_bot_brilliant_stroke — RESOLVED

**Decision:** Option 3 — Implement a dedicated `get_bs_limited_command(state)` method on each bot subclass. Each method walks its own faction's flowchart looking for the first valid Limited Command that can involve that faction's Leader in the Leader's current space. If no valid LimCom is found, return None (which aborts the BS). Engine's `_execute_bot_brilliant_stroke()` refactored to call this method instead of using hardcoded command priorities.

---

## Q8: Battle Win the Day — adjacent overflow shifts — RESOLVED

**Decision:** Implement overflow shifts to adjacent spaces per §3.6.8. For human play, prompt for adjacent space selection. For bot play, auto-select adjacent spaces prioritizing highest population, then largest possible shift toward the winning side's preferred direction.

**Status:** Implemented in `battle.py` `_shift()` — overflow automatically applied to adjacent spaces sorted by population (descending).

---

## Q9: Battle Win the Day — free Rally and Blockade move for Rebellion winner — RESOLVED

**Decision:** Implement both the free Rally and Blockade move per §3.6.8. The free Rally executes immediately as a full Rally command. For bot Patriots, select the Rally space using the Rally priorities from the Patriot bot flowchart node P7. For bot French, move the Blockade to the City with most Support per the Patriot bot flowchart P4. For human players, prompt for space selection. These execute during Battle resolution, not deferred.

**Status:** Infrastructure implemented in `battle.py` — caller provides `win_rally_space`/`win_rally_kwargs` for free Rally and `win_blockade_dest` for Blockade move as parameters to `execute()`. **Note:** Patriot bot P4 `_execute_battle()` does not yet pass these parameters — bot integration tracked as outstanding in `audit_report.md`.

---

## Q10: French Naval Pressure (§4.5.3) — FNI cap interpretation — RESOLVED

**Decision:** FNI cap = pool + on_map markers (interpretation 2). This is the only reading consistent with Option B existing in the rules — interpretation (1) would make Option B unreachable.

**Status:** Implemented in `naval_pressure.py` `_exec_french()` — `max_fni = wi_blks + on_map_count`.

---

## Q11: Patriot P2 Bullet 2 — "Active Opposition" vs "Active Support" — RESOLVED

**Decision:** Use "Active Support" (Manual §8.5 is correct).

**Evidence:** Analysis of all 18 shaded cards that place Underground Militia shows the largest cluster (cards 28, 47, 58, 78, 89) targets Active Support spaces (Tory-occupied, British-controlled territory). "Active Opposition with no militia" is a near-impossible board state. "Active Support or Village" forms a coherent strategic grouping: enemy-aligned territory lacking Patriot military presence.

**Implementation:** `_faction_event_conditions()` now checks the board for Active Support or Village spaces with no existing militia, instead of the previous over-broad flag check.

---

## Q12: French Agent Mobilization (§3.5.1) — "Quebec" vs "Quebec City" — RESOLVED

**Decision:** Use `"Quebec"` (Reserve) per Manual §3.5.1 command definition. The bot flowchart's "Quebec City" is treated as an informal reference to the same location; the command definition in the manual is authoritative for what spaces the command can target.

**Implementation:** Changed `_VALID_PROVINCES` in both `french_agent_mobilization.py` and `bots/french.py` from `"Quebec_City"` to `"Quebec"`. Updated 3 tests.

---

## Q13: British bot Supply — fate of non-qualifying spaces (6.2.1) — RESOLVED

**Context:** The bot reference says: *"British Supply / West Indies: Pay only in
spaces where removing British would prevent Reward Loyalty or allow Committees of
Correspondance, first with Resources in highest Pop, then with shifts in highest Pop."*

Previously the engine ignored the "pay only" clause for the bot: it paid in every
unsupplied space while Resources lasted, then **shifted toward Opposition** wherever
it went broke. Measured effect in 1776 bot-only games: about −5 Support per game from
Supply alone (as large as the Patriots' entire Committees program), which was a major
contributor to Patriots winning ~95% of bot-only 1776 games.

**Implemented reading (literal):** spaces failing the qualifying test (would not
prevent RL: needs Control + ≥1 Regular + ≥1 Tory + below Active Support; would not
allow Committees: no Rebel pieces present) are now **removed to Available** per
6.2.1, never paid and never shifted. Qualifying spaces pay first (highest Pop), then
shift when broke.

**Effect on bot-only balance (20 seeds/scenario):**
- 1775: Patriots 16/British 3/Indians 1  →  Indians 9/British 7/Patriots 4
- 1776: Patriots 19/British 1            →  Patriots 18/British 1/Indians 1
- 1778: French 12/Patriots 7/British 1   →  Patriots 9/French 7/British 2/Indians 2

**The ambiguity:** the literal reading also removes large Tory-less Regular armies
(3–7 cubes) standing in Colonies with no Rebels present, even when the British could
afford the 1 Resource. An alternative reading is that the sentence only orders
*spending priority*, with removal merely the implied fallback once Resources run out
— under that reading a rich British bot would still pay for field armies in
non-qualifying spaces. The reference text does not say which is intended, and the
balance consequences are large (see Indians 9/20 in 1775 above, driven by Support
staying high).

**Decision (owner, 2026-06-09):** keep the literal reading. Non-qualifying spaces
are removed to Available — never paid, never shifted.

---

## Q14: Event space selection for unnamed Cities/Colonies — RESOLVED (not ambiguous)

A prior handoff escalated "should candidates for e.g. 'shift 2 Cities' be
all Cities or only Cities where the shift can take effect?" as a design
call. On inspection the manual answers it: §8.3.5 routes Support/Opposition
shift selection to **§8.3.6** (gain-maximisation, Population-weighted per
§8.1.1/§1.6.2); §8.2 Random Spaces is a tie-breaker among candidates of
EQUAL priority only; §8.3.3 makes a no-effect (or enemy-favoring) Event
Ineffective. A maxed-out City has zero gain and can never tie a City where
the shift works, so the escalated dilemma cannot arise. Implemented in
Session 21 (see audit_report.md) with no human ruling needed.

---

## Q15: Missing source texts — Event Instructions sheet + Playbook examples — OPEN (needs materials, not a ruling)

Two official texts are absent from Reference Documents and block audits:

1. **Event Instructions sheet** — RESOLVED (Eric): the sheet contents
   have been in Reference Documents all along, as the per-faction
   "Special Instructions" sections at the BOTTOM of each
   `* bot flowchart and reference.txt` (keyed by card title, not
   number — the reason earlier searches missed them). T12 fixed against
   that text in Session 25; the full directive-content audit is now
   unblocked (ROADMAP Piece 3).
2. **Playbook "Non-Player Examples of Play"** — RESOLVED: Eric supplied
   `LOD_Playbook_Aug2016.pdf`; added to Reference Documents as PDF +
   extracted text (`Playbook Aug2016.txt`). Unblocks ROADMAP Piece 6.
   Note: the Playbook does NOT contain the Event Instructions sheet
   wording, so item 1 (and T12) remains open.

Both items resolved — no outstanding source-material requests.

---

## Q16: Pre-ToA Hortalez — manual "up to 1D3" vs flowchart F6 exact spend — RESOLVED

Manual 8.6.1: Roderigue Hortalez et Cie spends "**up to** 1D3 French
Resources". Flowchart F6: "Spend 1D3 … If none, Pass." The code follows
the flowchart (french.py:411-424): it requires paying the exact roll and
can PASS with Resources 1-2 when the roll is 3. Post-ToA code already
uses min(resources, roll). Which reading governs pre-ToA?

## Q17: Failed Raid routing — manual "instead execute Gather" vs flowchart I4→I6 — RESOLVED

Manual 8.7.1: "If no Raid is possible, instead execute Gather" and
8.7.2 repeats it ("or if the Indians selected a Raid or March Command
but were unable to execute it, Gather"). The flowchart YAML routes a
failed Raid to the I6 decision (which can end in Scout or March), and
the code follows the flowchart (indians.py:202-220). Manual is explicit
twice; flowchart disagrees. Which governs?

---

### Rulings for Q16 / Q17 (Eric, July 2026)

- **Q16:** the manual controls — pre-Treaty Hortalez spends **up to**
  1D3 (min of the roll and French Resources); the flowchart's "Spend
  1D3 … If none, Pass" is space-saving abbreviation. Implemented in
  `french.py:_hortelez` (both branches now identical "up to" logic).
- **Q17:** the specific flowchart routing controls over the general
  manual clause — a failed Raid (or March) proceeds to the I6
  decision ("Gather would place 2+ Villages, or 1D6 < Available War
  Parties?") and may end up Scouting/Marching instead of Gathering.
  The code already did this; ruling documented at the routing site in
  `indians.py`.

---

## Q18: Mid-raid Plunder to fund additional Raid spaces — RESOLVED

8.7.1: "If Resources fall to zero during the Raid Command, Plunder (or
if that is not possible, Trade) before completing the Raid Command."
Does an unspent SA license the non-player Indians to SELECT more Raid
spaces than current Resources afford (e.g., 1 Resource, three legal
targets: raid one, hit zero, Plunder, raid the other two)? The
Playbook's Indian example caps selection at affordability, but there
the SA (Trade) was already spent that turn. Current implementation
caps selection at min(3, Resources) and does not extend. Session 35
fixed the one-SA discipline either way.

**Eric's ruling (July 3, 2026): specific over general — the §8.7.1
bullet governs.** With an unspent SA, non-player Indians may select
Raid targets beyond current affordability (up to three per §3.4.4/
§8.7.1 priorities), and when Resources hit zero mid-Command they
Plunder (else Trade) before completing the remaining selected spaces.
The §3.1 affordability rule yields to the bot-specific instruction.
As with Q16/Q17, this ruling is case-by-case for THIS conflict — do
not generalize a precedence rule from it. To be implemented with
queue item 3 (Raid mid-raid replenish); selection should still not
exceed what the replenish can plausibly fund (a failed Plunder AND
failed Trade leaves the shortfall unraidable — skip unpaid spaces).

---

## Q19 (Session 55, RESOLVED — Eric CONFIRMED July 6 2026): Do Common-Cause
War Parties fill the Tory slot in Battle loss removal?  YES — the
Playbook (p.~850, "Indian War Parties can also be used in a Battle")
is explicit: "if the Common Cause Special Activity was used — as a
Tory adding to Force Level AND ABSORBING LOSSES."  Implemented: up to
cc_wp Active WPs fill the Tory slot of the §3.6.7 alternation, WP
before own Tories within the slot (§8.1.2 "without removing the last
Tory"; WP routes to Available, no casualties track — §3.6.7 "Other
removed pieces to Available").  Eric confirmed the Playbook reading on July 6, 2026:
"CC War Parties absorb losses as a Tory per the Playbook. Keep the
current implementation."

§4.2.1: "the British may utilize one or more War Parties as if they
were Tories ... It may accompany March or Battle."  §3.6.7 removal
priorities: "Royalists alternate removing one each British Regulars
then Tories. Once exhausted, remove Active War Parties."

Conflict: when CC War Parties are utilized "as if they were Tories"
in a Battle, do they (a) alternate with Regulars in the Tory slot of
§3.6.7 (sparing Regulars — lower CBC), or (b) get removed in the
literal §3.6.7 Active-War-Party phase after cubes are exhausted
(more Regulars die first)?  Either way they are physically War
Parties, so presumably they return to Available and count toward no
casualties track — but reading (a) changes WHICH British pieces die
and therefore CBC, in the British bot's favor, in every CC Battle.

Current implementation: (b), the literal §3.6.7 order (resolver's
_remove never sees cc_wp).  Session 55 fixed the FORCE-LEVEL side
(the resolver now receives the CC ctx and counts the WP as Tories in
Force Level per §4.2.1) but left removal at (b) pending this ruling.
The Playbook's Non-player British Brilliant Stroke example (§8.3.7
note) may contain a worked CC Battle — worth checking when Piece 5
transcribes it.

---

## Q20 (Session 56, RESOLVED — Eric ruled July 6 2026): French March
bullet 1 — "as many as possible" vs just-enough

§8.6.5: "March with as many French Regulars and Continentals as
possible to add Rebellion Control, first in Cities, then Colonies..."
The British March (§8.4.3) has an explicit stop clause ("Stop moving
groups into each destination space once British Control is
established"); the French text does not.  Two readings: (a) move the
MAXIMUM movable French/Continentals into each control-adding
destination (subject to lose-no-Rebellion-Control), or (b) move just
enough to flip Control (current implementation, mirroring the British
pattern).  (a) would concentrate French stacks — materially stronger
French defense and follow-up Battles.

**Eric's ruling (July 6, 2026): interpretation (b)** — "Treat §8.6.5
parallel to the British §8.4.3: move just enough to establish
Rebellion Control at each destination."  Matches the implementation;
no code change required.

## Q21 (Session 56, RESOLVED — Eric ruled July 6 2026): Blockade
stacking vs the one-per-City set model

§4.5.3 note: "There is no limit to the number of Blockades that may
be placed on one City."  The engine models city Blockades as a SET of
city names — stacking is unrepresentable, and (until S56) placing
onto an already-blockaded City silently DESTROYED the marker (pool
decremented, set.add no-op) while still raising FNI, shrinking the
§4.5.3 FNI ceiling for the rest of the game.  S56 interim: duplicate
placements now fail loudly; the non-player Naval Pressure target scan
and the Win-the-Day Blockade move skip already-blockaded Cities (the
no-benefit-selection pattern: §8.4.5 markers-only rule, S45 bullet-6
filter).  OPEN: does the §8.6.3 NP letter ("then the City with most
Support") demand literal stacking (a wasted marker parked on the top
city — weaker French than the current spread)?  Deciding that needs
the marker model changed from set to counts, touching income (§1.9),
victory, invariants, save format, and both bots' naval logic.

MEASURED (S56, 300 games seeds 5000+ each): reading (a) spread
(committed interim) — Rebellion 281/300 (94%): P143/F138/I16/B3.
Reading (b) literal-letter target with as-modeled failure (NP falls
through to Skirmish when the top city is blockaded) — Rebellion
259/300 (86%): P133/F126/I37/B4.  The ruling swings the INDIANS by
2x and the Patriot/French mix; the British stay ~1% under both, so
Q21 is not the British lever.

**Eric's ruling (July 6, 2026): interpretation (a)** — read "add one
Blockade ... to the City with most Support" with an implicit
not-already-blockaded qualifier (the Spread reading).  Matches the
implementation; the set model stands (no count-model refactor);
the loud duplicate guards stay as invariant protection.

---

## Q22 (Session 60, RESOLVED — Eric ruled July 6 2026): Non-player tie
resolution — seeded uniform vs the printed Random Spaces table

The engine resolved non-player ties with seeded-uniform
state["rng"].random() sort keys; the physical procedure (Ch 8
guidelines + Random Spaces sheet; demonstrated in Playbook Examples
2-3) rolls D3+D6 for a start cell, scans DOWN the column (wrapping
column-major, "when two spaces are listed in the same box, the upper
one is selected first"), and uses a plain D6 split (1-3/4-6) when
only two candidates remain.  The scan is NOT uniform over candidates,
so the two models differ distributionally at instrument scale.

**Eric's ruling (July 6, 2026): option (b) — implement the Random
Spaces table ENGINE-WIDE.**  Full physical parity including the
two-candidate D6 convention; reset the balance baselines and accept
the migration cost; tighten the Playbook goldens to exact-pick
asserts once parity holds.  Implementation notes: the §8.2 table
walker already existed (lod_ai/bots/random_spaces.py — start cell,
column-major wrap, upper-first) with three call sites (year_end,
Indian raid, card-effect shared); the migration replaces the bots'
remaining rng.random() sort-key ties with grouped table selection
(shared pick_by_priority helper), ordering the 2-candidate D6 split
by table position.  S53-S60 large-N numbers are NOT comparable
across this change — fresh baselines required.

**Addendum (July 7, 2026, Session 70 — source-coverage confirmed,
RESOLVED): the tie topic is fully covered by the Manual + Playbook.**
On review of whether the Reference Documents actually SPECIFY tie
resolution (vs. leaving it to engine convention):
  • Multi-candidate SPACE ties — Manual §8.1.3 → §8.2: the Random
    Spaces table (1D3 column + 1D6 row, top-of-box first, scan down the
    column following the arrows, reroll only if needed).  Complete.
  • Exactly-two-candidate ties — NOT in the rules text, but the Playbook
    states the procedure explicitly (twice, near-verbatim): "Since there
    are only two spaces to choose between, the player rolls a D6 instead
    of using the Random Spaces table: 1-3 = X, 4-6 = Y" (e.g. 1-3=
    Philadelphia/4-6=New York City; 1-3=Boston/4-6=Norfolk).  So counting
    the Playbook this is a STATED rule, not a gap — the engine's
    two-candidate D6 split is on-source.
  • Non-space / "who" choices — §8.3.8 ("choose randomly among the
    possibilities") and §8.3.5 (benefit/harm ordering, T7).
  • Victory-margin ties — §7.1 (deterministic NP > P > B > F > I; French
    last without ToA).  Tracked separately (C7).
The ONLY detail neither source pins down is which of the two candidates
is labelled 1-3 vs 4-6 (the Playbook just assigns 1-3 to the
first-listed candidate in each example).  This is outcome-neutral — a
50/50 split either way, so a single pick has identical odds regardless
of label order; it matters only for reproducing a SPECIFIC narrated die
roll, which the Playbook goldens already pin (all five replay green,
Example 3 at exact picks).  Eric's ruling (July 7, 2026): the Manual +
Playbook are sufficient basis — consider tie resolution fully RESOLVED,
no engine change or open lead remains.

---

## Q23 (Session 67, RESOLVED — Eric ruled July 10 2026): Propaganda/Raid
marker stacking — set model vs printed multi-placement

**Eric's ruling (July 10, 2026): markers STACK — option (b), per-space
counts.**  Implemented Session 74: `markers[tag]["on_map"]` is a
`{space_id: count}` dict for Propaganda and Raid (Blockade keeps the
Q21 set model), capped only by the global pool of 12.  Cards 1/2/47
place both markers; §3.4.4 re-Raids and §3.3.4/§4.3.1 re-placements
add a marker; §6.4.1/§6.4.2 Reward Loyalty / Committees of
Correspondence pay 1 Resource PER MARKER before any shift (the
"once no Raid or Propaganda is in a space" reading), including the
§8.4.5/§8.5.9 only-markers skip and the Muster-RL cost; the WQ Reset
returns full stacks to the pool.  Save format: counts round-trip as
JSON dicts; legacy set/list saves load as count-1.  Census invariant
sums stacked counts.  Gates: lod_ai/tests/test_q23_marker_stacking.py.

--- original question (for the record) ---

The Piece 4 marker-conservation invariant exposed the model question
Q21 settled for Blockades, now for Propaganda/Raid.  The engine models
both as {pool, on_map:set} — at most one marker per space, stacking
unrepresentable.  The reference disagrees in three places:

* Card 1 Waxhaws (unshaded): "Place two Propaganda there."
* Card 2 Common Sense: "Place two Propaganda markers there." /
  shaded "Place two Propaganda markers in each."
* Card 47 Tories Tested (shaded): "Place two Propaganda there."
* §6.4.1/§6.4.2 pricing reads as per-marker, not per-space: "Every one
  Resource spent removes one Raid or Propaganda marker—once no Raid or
  Propaganda is in a space—shifts it…" (multiple removals per space
  only make sense if a space can hold several markers).

§3.3.4 Rabble-Rousing itself places only "a Propaganda marker" (cap
NOTE is the global 12); no per-space limit is stated anywhere.

INTERIM (committed, Session 67): marker-conserving set semantics — a
placement onto an already-marked space is skipped (marker NOT
destroyed; the pre-S67 code destroyed the marker while debiting the
pool, cards 1/2/47 destroyed one per play, and re-Raiding a marked
Province destroyed a Raid marker per §3.4.4 execution).  place_marker
now places at most one per space and returns the true count.

DECISION NEEDED: (a) keep the set model with skip semantics (Q21
precedent: set model stands, loud/skip guards), accepting that cards
1/2/47 place one marker instead of two and RL/CoC removal costs cap at
1 Propaganda + 1 Raid per space; or (b) migrate Propaganda/Raid to
per-space counts (schema + save format + validate + RL/CoC pricing +
card handlers + census invariant).  (b) is a working session of
its own.  Balance stakes unmeasured; the RL pricing difference plays
into the British WQ economy.
