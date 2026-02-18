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

## Q12: French Agent Mobilization (§3.5.1) — "Quebec" vs "Quebec City"

**What I was trying to verify:** Whether `french_agent_mobilization.py` uses the correct space ID for the "Quebec" option.

**What the references say:**

- **Manual §3.5.1:** "Select one of the following: Quebec, New York, New Hampshire, or Massachusetts." Procedure text says "In the selected Province, place two Available Militia or one Continental."
- **French bot flowchart (F7):** "Place 2 Militia, or—if not possible—1 Continental, in Quebec City, New York, New Hampshire, or Massachusetts."

**What's ambiguous:** Manual §3.5.1 says "Quebec" and calls it a "Province" in the procedure. The map has two spaces: "Quebec" (type Reserve) and "Quebec_City" (type City). The bot flowchart explicitly says "Quebec City" while the manual command definition says "Quebec". These are different spaces on the map.

**Current code:** Both `french_agent_mobilization.py` and `bots/french.py` use `"Quebec_City"`, matching the bot flowchart but not the manual command definition.

**Options:**
1. Use `"Quebec"` (Reserve) — matches Manual §3.5.1 command definition text
2. Use `"Quebec_City"` (City) — matches the bot flowchart reference text
3. Allow both — the command accepts either interpretation

**Impact:** If the answer is "Quebec" (Reserve), the bot flowchart reference and bot code also need updating. If the answer is "Quebec_City" (City), the manual text is treated as using an informal name for the city.
