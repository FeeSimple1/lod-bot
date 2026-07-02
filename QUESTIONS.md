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

1. **Event Instructions sheet** (reverse of the Random Spaces sheet,
   §8.3.1). The `event_instructions.py` directive KEYS are verified
   complete against the card ICON lines, but the directive CONTENT
   (conditions like "target eligible enemy", "ignore if 4+ Militia")
   cannot be checked against anything in-repo. It is also needed to
   resolve T12 (the `force_if_eligible_enemy` enemy-set looks wrong:
   British treat Indians as an enemy and nobody treats Patriots as one).
2. **Playbook "Non-Player Examples of Play"** — needed for ROADMAP
   Piece 6 (golden oracle tests).

Action (Eric): add both texts to Reference Documents.
