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
