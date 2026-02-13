# QUESTIONS.md — Ambiguities requiring human decision

These items were identified during the compliance audit. The Reference Documents are either ambiguous, contradictory, or silent on these points. Per CLAUDE.md rules: no guessing — wait for human answer.

---

## Q1: Control access pattern — `sp.get("British_Control")` vs `state["control"][sid]`

**Context:** Several card handlers (e.g., Cards 30, 32) and bot modules access control state via `sp.get("British_Control")`, a boolean flag set directly on space dicts by `board/control.py`. The `board/control.py` module *also* maintains `state["control"][sid]` with values like `"BRITISH"` or `"REBELLION"`.

**Question:** Should the codebase standardize on one access pattern? If so, which one? Changing `sp["British_Control"]` would require updating all tests that set up this flag directly.

**Options:**
1. Keep both (current state) — space-level flag for backward compatibility
2. Remove `sp["British_Control"]` and only use `state["control"][sid]`
3. Keep `sp["British_Control"]` as authoritative and derive `state["control"]` from it

---

## Q2: Card 70 (British Gain From French in India) — whose Regulars?

**Context:** Reference says "Remove three Regulars from map or West Indies to Available." It does not specify British or French Regulars.

**Current implementation:** Removes British Regulars first, then French if insufficient.

**Question:** Should this remove British only, French only, a mix, or the executing faction's Regulars? The card order is FIPB, suggesting it's primarily a French/Indian card, but "Regulars" is ambiguous here.

---

## Q3: Queued vs immediate free ops in card events

**Context:** Many card effects queue free operations (March, Battle, Rally, etc.) via `queue_free_op()`. Some reference text uses phrasing like "Patriots free March to and free Battle in one space" which may imply immediate execution rather than queuing for later processing.

**Question:** Should card free ops execute immediately during event resolution, or should they be queued for the game engine to process after the event handler returns? This affects cards 1, 21, 48, 52, 66, 67 and others.

---

## Q4: Brilliant Stroke (Cards 105-109) — interrupt mechanics

**Context:** The Brilliant Stroke cards describe an interrupt/trump chain where one faction can trump another's Brilliant Stroke. The current implementation does not support true interrupts.

**Question:** How should the trump chain work in the bot engine? Specifically:
- When a bot plays a Brilliant Stroke, should all other factions be offered the chance to trump before it resolves?
- What is the exact sequence for multi-bot trump chains?
- Does trumping return the original Brilliant Stroke card to the trumped faction's hand?

---

## Q5: Indian bot I10 March — single vs multiple destinations

**Context:** The Indian bot flowchart describes March with detailed bullets including "March to get 3+ WP in 1 additional Neutral or Passive space with room for a Village." The current implementation only does a single move.

**Question:** Should the Indian bot March attempt up to 3 movements per the flowchart bullets, or is the single-move implementation an acceptable simplification for bot play?

---

## Q6: French bot F5 — Hortalez vs Agent Mobilization ordering

**Context:** The French bot pre-treaty flow (F5-F7) has a conditional branch based on "Patriot Resources < 1D3." The current code checks this to decide between Hortalez and Agent Mobilization, but the ordering of the fallback may not match the flowchart exactly.

**Question:** When the die roll check fails (Patriots have enough Resources), should F7 (Agent Mobilization) be attempted first with Hortalez as fallback, or vice versa? The flowchart arrow direction is ambiguous.
