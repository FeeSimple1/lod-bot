# Lessons learned implementing a COIN-series bot engine

*Distilled from the lod-bot project (May 2026) — an interactive CLI implementation of the four non-player bots in GMT Games' Liberty or Death (COIN Series Vol. V).  Audience: future projects implementing other COIN games (Andean Abyss, Cuba Libre, A Distant Plain, Falling Sky, Fire in the Lake, Colonial Twilight, Pendragon, Gandhi, China's War, All Bridges Burning, etc.) or wanting to add bot AI to a tabletop simulation generally.*

The lod-bot project went through 19+ audit sessions (1+ year of intermittent work) and ~200 PRs.  This document is the meta-summary of where the bugs clustered, not a comprehensive bug list.  The full historical bug ledger lives in `audit_report.md` in this repo.

---

## The big lessons (read these even if you skip the rest)

1. **The Manual + the bot reference flowcharts + the scenario reference sheets are the *only* sources of truth.**  Treat every other source — even your own intuition, even community strategy guides, even AI assistance — as a hypothesis to verify against the canonical reference.  When in doubt, re-read the relevant manual chapter.  When still in doubt, write the question down (we use `QUESTIONS.md`) and stop; do not implement a "reasonable interpretation."

2. **Bugs cluster around boundaries.**  The most common bug families in this project were all *boundary* bugs:
   * Where one module assumed a state shape that another module wrote differently
   * Where a forced/scheduled action used a "normal command" pipeline that charged costs the rules said were free
   * Where a per-space rule was implemented as a global check, or vice versa
   * Where the same English-sounding mechanic (e.g., "ineligible next card" vs "ineligible through next card") had subtly different rules

3. **LLM-assisted implementations introduce a predictable failure mode: plausible-looking code that invents constants or misreads precise rules text.**  The lod-bot project's Phase 1 ("Label Compliance") existed entirely because earlier ChatGPT-assisted work had invented piece tags (`"Continental"` instead of `"Patriot_Continental"`, `"Tory"` used both as a piece tag and a marker, `"fort"` lowercase instead of `FORT_BRI`/`FORT_PAT`).  Every such literal had to be tracked down and replaced with imports from a canonical constants module.  Build the constants module *first* and enforce it with grep-style tests from day one.

4. **Bots silently degrade rather than fail loudly.**  Most of this project's bugs didn't crash the game; they made one faction quietly play worse than the rules intended.  Without a multi-game smoke matrix (we use 60 and 150-game zero-player runs) you will never find them.  A test suite of unit tests isn't enough — it covers individual functions but misses integration weirdness.

5. **Documentation drifts fast and silently.**  At the start of the May 2026 session, `CLAUDE.md` claimed "86 tests currently passing"; the real number was 1,123.  `audit_report.md`'s "REMAINING issues" section listed items that had been resolved months earlier.  This drift causes future contributors (and future LLM sessions) to start with the wrong mental model.  Treat documentation refreshes as first-class deliverables, not an afterthought.

6. **Verify regression tests by reverting the fix.**  Multiple times in this project, a regression test was written, passed, and looked good — but didn't actually catch the original bug because the test scenario didn't exercise the right code path.  Standard discipline now: write the fix, write the test, *revert the fix*, confirm the test fails, *re-apply the fix*, confirm it passes.  If steps 3-5 don't work, the test is wrong.

7. **Design integration tests around "what would a player notice."**  The most powerful regression test for a bot is "does it crash, do its turns produce illegal moves, do its decisions end the game in a reasonable distribution?"  That's the smoke matrix.  Unit tests miss the gestalt.

---

## The anti-pattern catalog

Each entry: the pattern, a concrete example from lod-bot, and how to detect/prevent it.

### A. Orphaned code that never gets wired in

**Pattern:** A function is implemented with the right behavior, has its own unit tests, but is never called from production code paths.  Often the result of incremental development where one PR adds the helper and a follow-up PR was supposed to wire it but never landed.

**Examples from lod-bot:**

- `BritishBot.bot_indian_trade(state)` and `BritishBot.bot_leader_movement(state, leader, ...)` existed, were unit-tested, but no code in the engine called them.  Indians never asked British for Trade Resources, British leaders never followed their armies.  Found in May 2026, wired in commit `9155880`.
- `IndianBot.ops_leader_movement(state, leader)` existed, was unit-tested, and was never called.  Indian leaders (Brant / Cornplanter / Dragging Canoe) never followed their War Parties through any in-turn movement.  Wired in `e6036ef`.
- The entire `apply_leader_modifiers` hook system in `lod_ai/leaders/__init__.py` was dead code because it iterated `state["leaders"].get(faction, [])` while real game state stored leaders as `{leader_id: location}`.  The nine `@_register`'d hook functions for the 9 leader capabilities never fired in real games.  Deleted in `db4c17e`.

**Detection:**
- `grep -r function_name lod_ai/ | grep -v test_` — if every match is inside a test file, it's orphaned.
- A code-coverage report on a smoke run will show 0% coverage on orphaned helpers.

**Prevention:**
- Every public API needs an end-to-end integration test that proves it fires during a real game (not just a unit test that calls it directly).
- When you add a helper, in the same PR add the call site.  If you can't, file a follow-up ticket immediately and link it from the helper's docstring.

---

### B. Data-shape mismatch between modules

**Pattern:** Module A writes `state["X"]` as one shape, module B reads it as another.  Both modules compile, both have unit tests that mock their own preferred shape.  In production neither shape is wrong — the data flow simply never connects.

**Example from lod-bot:**

`lod_ai/leaders/__init__.py` documented `state["leaders"]` as `{faction: [leader_id, ...]}` and `apply_leader_modifiers` iterated that shape.  But the scenario JSON files and `setup_state.py` wrote `state["leaders"]` as `{leader_id: location_string}` (the natural per-leader-position representation).  Both shapes were used in tests; production used the location shape; the hook iteration silently found empty lists.

**Detection:**
- Schema validation in a single state-shape module that both writers and readers reference.
- An integration test that builds production state via `build_state()` and runs the consumer against it — not a mock state in the consumer's preferred shape.

**Prevention:**
- One canonical state schema document, kept in source control alongside the schema-using code.
- Type aliases or TypedDicts that document the shape with literal keys.
- A `validate_state(state)` helper called at engine init that raises on shape violations.

---

### C. "Forced / scheduled / free" actions reusing the standard pipeline

**Pattern:** The standard command pipeline charges resources, validates legality, requires player choice.  Year-end forced actions or event-triggered free actions should bypass some of that — but the engine call site forgets the `free=True` (or equivalent) flag and the forced action behaves like a normal command.

**Examples from lod-bot:**

- **WI Free Battle (§6.2.2):** Year-end Winter Quarters Supply phase forced a French vs British battle in the West Indies.  The Manual says "**free** Battle" — no Resource cost.  The code in `_supply_phase` called `battle.execute(state, FRENCH, {}, [WEST_INDIES_ID])` without `free=True`, so it charged the French 1 Resource.  When French had 0 Resources at year-end (a realistic state in 1778), `spend()` raised `ValueError` and the whole year-end resolution crashed.  Fixed in `f0a878e`.
- **Forced March-in-place activation:** British bot's B10 "March in place to Activate Militia" called `flip_pieces()` directly instead of `march.execute()`, skipping the §3.2.3 Resource cost AND skipping `_turn_command` / `_turn_affected_spaces` tagging.  When the SA chain then fired, the engine saw `_turn_used_special=True` with `affected_count=0` and rejected the whole turn as `no_affected_spaces`.  Fixed in `be656da` (cost-paying + command-tagging routed properly).

**Detection:**
- Audit every callsite of `*.execute()` for forced or year-end usage.  Each one should be either calling with `free=True` (or whatever the cost-bypass flag is) or have a comment explaining why the cost is intentional.
- Look for direct piece-manipulation calls (`flip_pieces`, `move_piece`, `add_piece`) inside bot code — those bypass all the cost/tagging infrastructure and should usually be replaced with the standard pipeline.

**Prevention:**
- Two distinct entrypoints rather than a `free=True` flag.  `battle.execute_paid()` and `battle.execute_free()` are harder to confuse than one function with a kwarg.
- All `_turn_command` / `_turn_affected_spaces` / cost-payment infrastructure lives in the standard pipeline only.  Bots that bypass it should be flagged for review.

---

### D. Per-space rule implemented as a global check (and vice versa)

**Pattern:** A leader capability or special-activity bonus says "in the space" — but the code checks a more global condition like "is this leader on the map" or "is this the faction's current leader."  The bonus then fires in the wrong context or fails to fire when it should.

**Examples from lod-bot:**

- **Gage capability:** Reference Card says *"First Loyalty shift: Reward Loyalty is free in the space."*  The code used `_is_gage(state)` which is true whenever Gage is on the map anywhere.  So Gage's "free first shift" discount was applied to any Reward Loyalty the British bot did, even when Gage was in a completely different city.  Fixed in `83aff7a` to check `leader_location("LEADER_GAGE") == chosen_rl_space`.
- **Clinton capability:** Says *"Skirmish removes 1 additional Militia in the space."*  Code read a ctx flag set by the dead `apply_leader_modifiers` hook — always 0.  So Clinton's Skirmish bonus never fired.  Fixed in `83aff7a` with a direct per-space `leader_location("LEADER_CLINTON") == space_id` check.
- **Rochambeau capability:** Says *"French may March and Battle with a Patriot Command at no Resource cost."*  Per-space rule (Rochambeau must be in the space).  Not implemented at all — French ally fees were charged unconditionally during Patriot Battle and March.  Fixed in `83aff7a` to filter Rochambeau's space out of the chargeable destinations.
- **_is_howe / _british_leader scope:** `_is_howe` delegated to `_british_leader` which returned the *first* British leader on the map in a fixed scan order (Gage → Howe → Clinton).  When both Gage and Howe were on the map, Gage was found first and Howe's FNI bonus didn't fire.  Fixed in `9bf4f99` to use direct presence check `leader_location("LEADER_HOWE") is not None`.

**Detection:**
- For every leader / event / capability with "in the space" in its text, grep the codebase for the leader/event/capability constant and verify the surrounding check is per-space.
- For every "is X the faction's leader" check, ask: should this be "is X anywhere on the map" or "is X in this specific space"?

**Prevention:**
- Encode the scope in the helper's name.  `leader_in_space(state, leader_id, space_id)` and `leader_anywhere(state, leader_id)` are harder to confuse than `_is_gage(state)`.
- For every capability, write the per-rule test: "fires when leader in space, doesn't fire when leader elsewhere."

---

### E. Bot flowchart violations

**Pattern:** The bot's reference flowchart prescribes a specific sequence of decisions.  The implementation makes "improvements" or shortcuts that look reasonable but diverge from the reference.  The bot then plays sub-optimally or makes illegal moves.

**Examples from lod-bot:**

- **Patriot multi-Persuasion:** Manual §4.1 says "one Special Activity per Command."  Patriot bot called `_try_persuasion` from many flowchart nodes (P7 Rally, P8 Partisans, P11 Rabble-Rousing, P12 Skirmish) and as a mid-command resource refill in `_execute_rabble` and `_execute_rally`.  Nothing prevented Persuasion firing more than once per turn.  Instrumenting 50 1776 games showed 30% of Persuasion-using turns involved >1 call, with one turn firing it four times.  Fixed in `7cf4412` with a turn-scoped `state["_turn_persuasion_used"]` flag.
- **British MUSTER Limited-Command space cap:** `BritishBot._muster()` correctly capped Regulars + Tory placement to `max_spaces` (1 for Limited Command, 4 otherwise), but the step-3 Reward Loyalty and Fort-build selection could append an extra space.  In Limited mode this produced 2 selected spaces and the engine rejected with `limited_wrong_count (affected=2)`.  50 occurrences across 29/60 games — almost every 1775 and 1776 game affected.  Fixed in `648ae61` by filtering candidate spaces to already-selected when at the cap.
- **British _march extra CC fallback:** B10 reference says "If no Common Cause used, execute a Special Activity."  The code had an extra `_try_common_cause(state, mode="MARCH")` attempt before falling to the SA chain.  Not in the reference; removed in `9bf4f99`.
- **Indian bot double SA:** Earlier in the project (commit `696955d`), the Indian bot was executing both War Path AND Trade in one turn — two SAs in violation of §4.1.

**Detection:**
- For each bot flowchart node, write a "this is what the node should do" test that exercises the prescribed behavior with a controlled state.
- Run a multi-game smoke matrix and capture per-turn diagnostics (what command attempted, what SA fired, did the engine reject the turn).  Pattern-spot the rejections.

**Prevention:**
- Treat the bot reference flowcharts as line-for-line specifications.  Comments in the bot code should cite the flowchart node ID and quote the reference text.
- Specific guard: per-turn flags for "X has been used this turn" for each special activity.  Reset at turn start in `take_turn()`.

---

### F. Cross-faction interaction gaps

**Pattern:** Faction A's command does something to or with Faction B's pieces or state, but the engine only invokes Faction A's leader-handling / OPS / cleanup hooks.  Faction B's hooks never see the cross-faction effect.

**Examples from lod-bot:**

- **CC-during-British-March doesn't trigger Indian leader following.**  During a British March using Common Cause, Indian War Parties participate as Tory-equivalents and can move from an Indian leader's space to the British destination.  Per OPS the Indian leader should follow per "Royalist Leaders follow largest group of own units that moves from (or stays in) their spaces."  The British March wires `_follow_leaders_after_march` for British leaders only; Indian leaders are unchecked.  Documented but not fixed (cross-faction edge case, minor).
- **Indian Trade flow.**  `IndianBot._trade` was computing the British offer inline using a 1D6 roll, but was missing the "Indian Resources < British Resources" gate from the OPS reference.  The British bot's `bot_indian_trade` had the correct gate but was never called.  Fixed in `9155880` to delegate from Indian to British.

**Detection:**
- Map out which actions can affect which factions' pieces / state.  Battle, Common Cause, French Allied participation, Indian Trade, all cross faction lines.
- For each cross-faction interaction, list every per-faction hook (leader movement, OPS, BS trigger) and check whether each fires when triggered from the OTHER faction's command.

**Prevention:**
- Cross-faction effects should fire ALL affected factions' hooks, not just the acting faction's.
- A `state_changed_for_faction(faction)` event-bus pattern instead of per-command hook wiring.

---

### G. Card-handler bugs (the long tail)

**Pattern:** Card handlers in a COIN game often have 50-150 unique cards, each with shaded and unshaded effects.  The card reference text is precise but each handler is small and unsupervised.  Bugs accumulate.

**Examples from lod-bot (representative subset):**

- **Card 1 Waxhaws:** Shaded "shift toward Neutral" was actually shifting toward Opposition.
- **Card 39 King Mob:** Shift toward Neutral but used wrong helper, often set to 0 instead of moving toward 0.
- **Card 48 God Save King:** Shaded moves pieces to adjacent space; code was removing them to Available instead.
- **Card 64 Fielding:** Shaded was applying British -3 & FNI +1; reference says Patriots +5.  Critical sign error.
- **Card 71 Treaty of Amity:** Shaded was British +4; reference says French +5.  Same sign-error pattern.
- **Inverted shaded/unshaded** in several cards (card 18, others).
- **Hardcoded space selections** instead of player/bot choice (cards 2, 6, 24, 28, 80).
- **Wrong eligibility durations:** `ineligible_next` (1 card) vs `ineligible_through_next` (2 cards) confused in several handlers.
- **Queued vs immediate free ops:** Several cards queued free operations that should execute immediately per the card text.  Engine fix: drain free-ops immediately after event handler returns.

**Detection:**
- A "card audit" script that reads every card's reference text from `card reference full.txt` and a structured representation of the handler's effect, then flags discrepancies.
- Many small unit tests, one per card, asserting the handler matches the reference text.

**Prevention:**
- Card handlers should reference the canonical card-reference-text file directly in their docstrings.
- A test scaffolding pattern: `test_card_<N>_unshaded` and `test_card_<N>_shaded` for every card.
- An audit tool that compares the live handler code to the reference text.  In lod-bot this is `tools/card_audit_fix.py`.

---

### H. Scenario JSON ignored / hardcoded defaults

**Pattern:** Setup data lives in scenario JSON files, but the loader hardcodes default values instead of reading from the JSON.  Most scenarios have those values at 0, so the bug is invisible — until a scenario has a non-zero starting value.

**Example from lod-bot:**

`setup_state.py` had `"cbc": 0, "crc": 0` unconditionally, ignoring `british_casualties` / `patriot_casualties` in the scenario JSON.  For 1776 these should have been 1 / 3 per the Scenario Reference; for 1778 they should have been 10.  The bug discarded 10 Cumulative British Casualties at 1778 setup — a major French Margin-2 advantage erased.  Fixed in `7cf4412`.

**Detection:**
- Diff every key in the scenario JSON files against what `build_state` actually reads.  Anything in JSON but unread is suspicious.
- For each scenario, read the Scenario Reference text file and write a one-shot test asserting `build_state(scenario)` matches every track value, casualty counter, etc.

**Prevention:**
- A scenario loader that *iterates* the JSON keys and rejects any unrecognized key (forces explicit handling).
- For each non-zero starting value in any scenario, a regression test.

---

### I. AI-assisted implementation patterns

**Pattern:** LLM-assisted code looks plausible but invents constants, conflates similar mechanics, misreads precise English in rules text, or applies the right behavior to the wrong situation.  This is harder to detect than ordinary bugs because the code *reads correctly* — every line makes sense in isolation.

**Examples from lod-bot:**

- **Phase 1 label compliance bugs (all from earlier ChatGPT-assisted work):** Invented piece tags `"Continental"`, `"Militia"`, `"Tory"` (as a piece), `"fort"` used in code where the canonical constants are `Patriot_Continental`, `Patriot_Militia_A`, `British_Tory`, `British_Fort` / `Patriot_Fort`.  Every such literal had to be hunted down (Phase 1 took 14 commits).
- **Card behavior misreads:** "place" vs "move", "to Casualties" vs "to Available", "may" vs "must" — multiple card handlers had the wrong destination or modality.
- **The "implementation looks fine, doesn't fire" pattern:** Multiple capabilities had hook-style implementations that looked correct but ran against a state shape they didn't actually match (see §B).

**Detection:**
- Compile-time grep for any string literal that *looks like* a game term but isn't imported from a constants module.
- A "label compliance" test that grep-checks every `.py` file for non-canonical literals.
- For every commit that adds card behavior, require a corresponding test that quotes the reference text and asserts the handler matches.

**Prevention:**
- Constants module enforced from day one.  Never let a card handler land with a hardcoded string for a piece/marker/faction.
- LLM-generated code should be reviewed by a human or by a second LLM specifically prompted to find inventions and misreadings against the canonical reference.
- The "verify regression test by reverting the fix" discipline from the meta-lessons above catches a lot of LLM-generated "looks right but doesn't actually work" code.

---

### J. CLI / UX drift from documented design

**Pattern:** The README or design doc specifies a CLI flow.  Refactoring or quick fixes silently drift away from it.

**Examples from lod-bot:**

- `_choose_seed` originally presented a menu of 1-5 + Random (per README); at some point it was replaced with auto-generation that never prompted.  Reproducible games (for testing, sharing, debugging) became impossible.  Fixed in `f66d490`.
- Setup choice order in `main()` was Scenario+Deck → Humans → Seed, but the README documents Scenario → Deck+Seed → Humans.  Cosmetic but a UX consistency issue.

**Detection:**
- Scripted-input integration tests that exercise the documented flow and assert the prompts appear in the right order.

**Prevention:**
- Snapshot tests for CLI prompt sequences.
- A test that scripts stdin through the documented happy path and verifies the prompts match the README.

---

### K. Documentation drift

**Pattern:** As code evolves, documentation lags.  Test counts in CLAUDE.md, "Remaining Issues" lists in audit_report.md, README examples that no longer match actual behavior.  This costs every subsequent contributor (and LLM session) time as they start from the wrong mental model.

**Examples from lod-bot:**

- `CLAUDE.md` claimed "86 tests currently passing" when the real number was 1,123.  ChatGPT-era known issues were described as the *current* state of the code when Phases 1-3 had been complete for months.
- `audit_report.md` had a "REMAINING issues" section that listed bugs already fixed in subsequent sessions.
- `GITHUB_ISSUES.md` had no status markers, making it look like all Phase 1/2/3 work was still open.

**Detection:**
- Periodic doc-vs-reality audits.  We did this in commit `002c351` and immediately found the test count was wrong.

**Prevention:**
- Treat documentation refreshes as first-class deliverables, not afterthought.
- A CI check that compares the test count claimed in CLAUDE.md against actual `pytest --collect-only` output.
- Per-session doc updates as part of the standard PR template.

---

## Architecture recommendations

These follow from the anti-pattern catalog above.

### A. Constants module, enforced from day one

Build `rules_consts.py` (or equivalent) with every piece tag, faction name, marker, leader, and space ID.  Make it the single source of truth.  Add a label-compliance test that grep-scans the codebase for string literals matching game-term patterns and rejects unfamiliar ones.

### B. State schema documented and validated

Pick one canonical shape for every state key.  Document it.  Write a `validate_state(state)` that runs at engine init and rejects unexpected shapes.  Refactor any consumer that assumes a different shape.

### C. Clear separation between "normal commands" and "forced / free actions"

Either two distinct entrypoints (`battle.execute_paid` vs `battle.execute_free`) or a `free=True` flag plus a discipline that every callsite explicitly specifies one or the other.  No defaults that silently apply costs to forced actions.

### D. All state mutation through engine helpers

Bot code should never call `flip_pieces`, `move_piece`, `add_piece` directly.  Always go through the command pipeline (`march.execute`, `garrison.execute`, etc.) which handles cost payment, command tagging, validation.  When the bot needs a "March in place" or similar shortcut, the engine should expose that as a proper entrypoint, not let the bot bypass.

### E. Cross-faction effects fire all affected hooks

Whenever a command affects pieces of multiple factions, ALL affected factions' post-command hooks (leader movement, OPS triggers) should fire — not just the acting faction's.

### F. Per-leader / per-space scope made explicit in helper names

`leader_in_space(state, leader_id, space_id)` and `leader_anywhere(state, leader_id)` rather than `_is_X(state)`.  The scope is in the name.

### G. Per-turn flags reset by `take_turn()`

For any "X happens at most once per turn" rule, use a state flag (`_turn_X_used`) cleared at the start of every turn.  Don't rely on local variables in the bot's flowchart code — they can leak across nested function calls.

---

## Testing recommendations

### A. Multi-game zero-player smoke matrix

Run N games (we use 60 and 150) where every faction is bot-controlled, capture per-turn diagnostics, and gate CI on:
- 0 crashes
- 0 hangs / timeouts
- 0 illegal-action rejections
- 0 unhandled bot exceptions

This catches integration bugs that no unit test will find.  In lod-bot this is `lod_ai/tools/batch_smoke.py` + `error_diagnostic_runner_round3.py`.

### B. Verify-the-test discipline

For every new regression test:
1. Apply the fix.  Run the test — should pass.
2. Revert the fix (`git stash` the fix-file).  Run the test — should fail.
3. Restore the fix.  Run the test — should pass again.

If step 2 doesn't fail, the test isn't exercising the bug.  We caught at least 3 test-doesn't-actually-test-the-fix situations in this project.

### C. Per-card unit tests

For every card handler, write a test that:
- Sets up the state described in the card's preconditions
- Calls the handler with shaded and unshaded paths
- Asserts the post-state matches what the card reference text prescribes

This catches card-handler bugs (§G in the anti-pattern catalog).

### D. Per-capability integration tests

For every leader capability, special activity bonus, or event-triggered effect with "in the space" / "for the faction" / "during X command" semantics:
- Test the positive case (bonus fires when conditions met)
- Test the negative case (bonus doesn't fire when conditions absent)
- Test the boundary case (bonus is per-space, not global; or per-leader, not first-found)

### E. State schema contract tests

Build a sample state via `build_state` for each scenario.  For each module that reads from state, assert its shape expectations are met.

### F. Scripted-input CLI tests

For every menu flow in the CLI, write a test that scripts stdin through the documented flow and asserts the prompts appear in the documented order with the documented content.  Catches CLI drift.

---

## Process recommendations

### A. Maintain a session-by-session audit log

We use `audit_report.md`.  Each work session appends a section describing what was audited, what was found, what was fixed, what's left.  This means a future contributor (or LLM session) can read the audit log and not re-discover known issues from scratch.

### B. Refresh CLAUDE.md (or equivalent onboarding doc) every session

Test counts, LOC, completed phases, open items list — all drift.  At the end of every work session, refresh them.

### C. Strategic guide as orthogonal supplementary reference

A `strategy.md` (or equivalent) that captures gameplay strategy, separate from the rules-implementation work, helps contributors understand WHY a faction prefers certain plays.  Clearly framed as NOT authoritative for code (the Manual + flowchart references are), but useful for spotting "the bot is making a tactically weird choice that follows the flowchart but ignores obvious play."  Lod-bot's `strategy.md` was added late in the project; would have been useful earlier.

### D. "No guessing" rule

When the Manual is ambiguous or contradictory, write the question down in `QUESTIONS.md` and stop work on that specific issue.  Do not implement a "reasonable interpretation."  The lod-bot project has 12 QUESTIONS entries, all of which now have human-decided answers; without that discipline we'd have a codebase full of guessed-at behavior that's inconsistent with the Manual.

### E. Run zero-player smoke after every change

Even doc-only commits.  Even pure refactors.  The smoke matrix is fast (45-60 seconds for 60 games) and catches integration regressions immediately.

### F. Cross-reference fixes by commit hash in audit log

When you fix a bug, the audit_report.md entry should cite the commit hash.  Makes the "what changed and when" history trivially navigable.

---

## Bug appendix: representative pattern → example matrix

| Pattern (§) | Example                                                  | Severity              | Lod-bot commit |
|-------------|----------------------------------------------------------|-----------------------|---------------|
| A Orphaned  | `bot_indian_trade` never called                          | Medium (silent)       | `9155880`     |
| A Orphaned  | `apply_leader_modifiers` system dead code                | High (capabilities)   | `db4c17e`     |
| B Shape     | `state["leaders"]` faction-vs-leader mismatch            | High (capabilities)   | `db4c17e`     |
| C Free      | WI Free Battle wasn't free                               | Crash class           | `f0a878e`     |
| C Free      | British March-in-place no_affected_spaces                | Medium (silent)       | `be656da`     |
| D Per-space | Gage global instead of per-space                         | Medium (Reward Loyalty)| `83aff7a`    |
| D Per-space | Clinton ctx flag never fired                             | Medium (Skirmish)     | `83aff7a`     |
| D Per-space | Rochambeau French-free missing                           | Medium (French)       | `83aff7a`     |
| D Per-space | `_is_howe` first-leader scope                            | Medium (FNI bonus)    | `9bf4f99`     |
| E Flowchart | Patriot multi-Persuasion (>1 SA per turn)                | Medium (Patriot OP)   | `7cf4412`     |
| E Flowchart | British MUSTER 1-space cap exceeded via RL/Fort          | High (50/60 games)    | `648ae61`     |
| E Flowchart | Indian double SA (War Path + Trade)                      | Medium                | `696955d`     |
| E Flowchart | `_march` extra CC fallback                               | Low                   | `9bf4f99`     |
| F Cross-fac | CC-during-British-March Indian leader following          | Low                   | (open)        |
| G Card      | Card 1 Waxhaws shift direction inverted                  | Medium                | (Phase 2)     |
| G Card      | Card 64 Fielding sign error                              | High (faction swap)   | (Phase 2)     |
| G Card      | Battle Win-the-Day shift direction inverted in `_apply_shifts_to` | **Critical** (every battle wrong) | (Session 2) |
| H Setup     | CBC/CRC hardcoded to 0                                   | Medium (Margin 2)     | `7cf4412`     |
| H Setup     | WQ insertion off-by-one                                  | Medium (deck shuffle) | (Phase 3)     |
| I AI        | Phase 1 label compliance (invented piece tags)           | Pervasive             | (Phase 1)     |
| J CLI       | `_choose_seed` lost menu                                 | UX                    | `f66d490`     |
| K Docs      | CLAUDE.md test count drift (86 → 1123 unupdated)         | High (onboarding)     | `002c351`     |

---

## What I would do differently

If I were starting this project from scratch today:

1. **Build the constants module + label-compliance test in the first commit.**  Don't let any "smart" first-pass code introduce invented piece tags.

2. **Build the smoke matrix in the second commit.**  Even before any cards work, have a `python -m tools.batch_smoke` that runs N zero-player games and reports crashes.  Make CI gate on it.

3. **Build state-shape validation in the third commit.**  `validate_state(state)` called at engine init.  Reject any unexpected key shape.

4. **Build the audit log discipline from day one.**  Even the first commit's PR description should land in `audit_report.md` as Session 1.

5. **Refuse "looks plausible" code reviews.**  When LLM-generated code touches a card handler or capability, require it to quote the reference text and require a regression test that's verified by reverting the fix.

6. **Treat the bot flowcharts as line-for-line specifications.**  Every bot code comment should cite the flowchart node ID and quote the reference text.  Don't paraphrase.

7. **Plan for the integration-bug class of failures.**  Set aside time specifically for state-shape mismatches, orphaned helpers, and forced-action vs. normal-command boundary issues.  These are the bugs you cannot find with unit tests alone.

8. **Don't trust early test pass rates.**  In this project, 1,123 tests passing didn't mean the bots played correctly — it just meant unit-tested functions worked individually.  The integration smoke matrix is what caught the most important bugs.

---

*This document is a snapshot of one project's experience.  The patterns described here are not exhaustive — they're the ones that surfaced repeatedly across the lod-bot project's audit history.  Other COIN-series implementations will likely surface their own patterns; please add to or branch this document with your own findings.*
