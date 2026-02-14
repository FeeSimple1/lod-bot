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

**Status:** Not yet implemented — documented for future work.

---

## Q6: French bot F5 — RESOLVED

**Decision:** Agent Mobilization first, Hortalez as fallback. The current code already implements this correctly.

---

## Q7: BS bot command priorities in _execute_bot_brilliant_stroke — OPEN

**Context:** `engine.py` `_execute_bot_brilliant_stroke()` hardcodes command priorities (e.g., British: battle→muster→march, Patriots: battle→rally→march) instead of consulting each faction's flowchart.

**What the reference says:** §8.3.7 states "follow the executing Faction's flowchart to select the first Limited Command that both matches the flowchart priorities and can involve that Faction's Leader."

**What's ambiguous:** Whether the hardcoded order is an acceptable approximation or must be replaced with actual flowchart consultation. The flowcharts have conditional branches that the hardcoded order doesn't capture.

**Options:**
1. Replace hardcoded priorities with calls to each faction's bot `_follow_flowchart()` method
2. Keep hardcoded order but verify it matches each flowchart's priority ordering
3. Implement a dedicated `get_bs_limited_command()` method on each bot subclass

---

## Q8: Battle Win the Day — adjacent overflow shifts

**Context:** `battle.py` `_shift()` currently applies all support shifts to the Battle space only.

**What the reference says:** §3.6.8 states "If all shifts are not possible in the Battle space, British (if Royalist winner) or Patriots (if Rebellion winner) may use remaining shifts in adjacent spaces."

**What's ambiguous:** The player selects which adjacent spaces receive the overflow shifts. For bot play, there's no guidance on priority for selecting adjacent spaces. Additionally, this interacts with the support track boundaries per space.

**Options:**
1. Implement overflow with caller-provided adjacent-space list
2. Auto-select adjacent spaces based on highest impact for bot play
3. Skip overflow for now (current behavior) and add later when bot flowcharts are verified

---

## Q9: Battle Win the Day — free Rally and Blockade move for Rebellion winner

**Context:** §3.6.8 states that if Rebellion wins, "Patriots may free Rally in any one eligible space" and "the French may move any Blockades from the Battle City to another City."

**What's ambiguous:** These are complex post-battle actions requiring player decisions. For bot play, the flowcharts may have specific guidance on when/where to Rally and move Blockades. The free Rally is a full Rally command execution in a different space.

**Options:**
1. Implement with caller-provided parameters for Rally space and Blockade destinations
2. Defer to bot flowchart integration (Phase 3 work)
3. Implement Rally-only (simpler) and defer Blockade move
