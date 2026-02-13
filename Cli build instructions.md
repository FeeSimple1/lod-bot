 CLI Build Instructions

Read CLAUDE.md first. Then read this entire prompt before writing any code.

## Context

There is already a working CLI in `lod_ai/interactive_cli.py` with numbered menu selection, command wizards for all factions, special activity selection, scenario/human faction setup, and a game loop. There are also utilities in `lod_ai/cli_utils.py` (choose_one, choose_multiple, choose_count). The engine supports `push_history` logging for most actions.

DO NOT rewrite these from scratch. Build on what exists. The goal is to upgrade the CLI into a complete, usable play interface.

## Requirements

### 1. Board State Display (on-demand via 'status' command)

At any input prompt during the game, the player can type `status` (or `s`) to see the full board state. This must show EVERYTHING needed to play with a physical board:

**Score Track / Global State:**
- Resources for all 4 factions
- Support total and Opposition total
- FNI level (state["fni_level"])
- Cumulative British Casualties (state.get("cbc", 0)) and Cumulative Rebellion Casualties (state.get("crc", 0))
- French Preparations total (if Treaty of Alliance not yet played)
- Treaty of Alliance status (played or not)
- Current British Leader, French Leader, Indian Leader (from state["leaders"])
- Eligibility status of all 4 factions
- Brilliant Stroke cards: which factions have played theirs, which still hold theirs

**Available / Unavailable / Casualties boxes:**
- Available pieces by type (state["available"])
- Unavailable pieces by type (state["unavailable"])
- Casualties by type (state["casualties"])

**Markers:**
- Propaganda markers: how many in pool, which spaces have them
- Raid markers: how many in pool, which spaces have them
- Blockades: how many in pool, which cities have them

**Per-space summary (compact table format):**
For each space, one line showing:
- Space name
- Support/Opposition level (e.g. "Active Support", "Passive Opp", "Neutral")
- Control (British/Rebellion/None)
- Population (from map data)
- Pieces present (abbreviated, e.g. "3 BrReg, 2 Tory, 1 BrFort | 1 PatMil(U), 1 PatFort | 2 WP(A), 1 Vil")

Keep it compact â€” this will be 23 lines for all spaces. Group Royalist pieces, Rebellion pieces, and Indian pieces with `|` separators for readability.

**Current/Upcoming cards:**
- Current card number, title, and faction order
- Upcoming card number and title

### 2. Bot Turn Summaries (narrative + structured)

After every bot action, print a summary in two parts:

**Part 1 â€” Plain English narrative:**
```
â”â”â” BRITISH BOT â”â”â”
British chose Command: Garrison with Skirmish.
Moved 3 Regulars from Boston to Connecticut, 2 Regulars from New York City to New Jersey.
Skirmish in Connecticut â€” removed 1 Patriot Militia (Active).
```

**Part 2 â€” Structured details:**
```
  Command: Garrison (3 spaces)
    Move: Boston â†’ Connecticut: 3 British_Regular
    Move: New_York_City â†’ New_Jersey: 2 British_Regular
  Special Activity: Skirmish
    Space: Connecticut
    Removed: 1 Patriot_Militia_A
  Control changes: Connecticut BRITISHâ†’REBELLION
  Resource changes: BRITISH 6â†’4 (-2 supply)
```

To generate these summaries, compare `state["history"]` entries before and after the bot's turn. The history log already captures most actions. You may also need to snapshot resources, control, and piece counts before the bot acts and diff them afterward.

**IMPORTANT:** After printing the summary, PAUSE and wait for the player to press Enter before continuing. Print a message like:
```
[Press Enter to continue, or type 'status' for board state]
```
This gives the player time to update their physical board.

### 3. Card Display

When each new card is drawn, clearly display:
```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  Card 42: British Attack Danbury        â•‘
â•‘  Order: British, Patriots, Indians       â•‘
â•‘  1st Eligible: BRITISH                   â•‘
â•‘  2nd Eligible: PATRIOTS                  â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
  Upcoming: Card 15 â€” Marquis de Lafayette
```

Show which factions are eligible and which have the sword icon (must skip Event).

### 4. Human Turn Interaction

The existing numbered menu system in `interactive_cli.py` is the right approach. Keep it. Make these improvements:

- At EVERY input prompt (not just dedicated pause points), accept `status` or `s` to show board state, `history` or `h` to show recent action log (last 10 entries), and `quit` or `q` to save and exit.
- Before showing the action menu, display a brief context line:
  ```
  PATRIOTS turn (1st Eligible) | Resources: 12 | Card: British Attack Danbury
  ```
- After a human completes their action, show the same structured summary format used for bots (what changed).
- If a human action is illegal, explain WHY it's illegal before showing the menu again.

### 5. Legality Enforcement

The engine already sandboxes actions via `_simulate_action`. Ensure that:
- The CLI never allows an illegal action to be committed to game state.
- If a human selects an action and it's rejected by the engine, print a clear message explaining the rejection and return to the action menu.
- When showing menus, filter out options that are definitely illegal (e.g., don't show "Battle" if the faction has no pieces in spaces with enemies). The existing CLI already does some of this â€” extend it to cover all commands.

### 6. Setup Flow

The existing `_choose_scenario` and `_choose_humans` functions work. Add:
- After selecting human factions, confirm the setup:
  ```
  Scenario: 1775 Long
  British: BOT
  Patriots: HUMAN
  French: BOT
  Indians: HUMAN
  Seed: 42
  
  Start game? (y/n)
  ```
- Allow re-selection if the player says no.

### 7. Event Display

When a bot plays an Event, or when a human is offered the Event option, display the full event text from the card data:
```
Event: British Attack Danbury (Unshaded)
  "British Regulars raid Patriot supplies..."
  [Full event text from card data]
```

For human players choosing between shaded/unshaded, show both texts before asking them to pick.

### 8. Winter Quarters Display

When Winter Quarters triggers, walk through each phase with clear headers:
```
â•â•â• WINTER QUARTERS â•â•â•
Phase 1: Victory Check
  British: margins (3, -2) â€” not met
  Patriots: margins (1, 5) â€” not met
  ...
Phase 2: Supply
  British supply check: [details]
  ...
```

Pause between phases so the player can update their board.

### 9. Game End

When the game ends, display:
- Which faction won (or final scoring if last Winter Quarters)
- Final victory margins for all factions
- Offer to show final board state

## Technical Notes

- The CLI runs entirely in the terminal. No GUI, no web server, no API keys.
- Entry point: `python -m lod_ai` should launch the CLI (update `__main__.py` if needed).
- All state display reads from the existing `state` dict. Do not create parallel tracking â€” use what the engine maintains.
- Use the existing `push_history` system for action logging. If commands or SAs are missing history entries, add them.
- Test by running the CLI manually. This is a UI task â€” automated tests for display formatting are not necessary, but ensure the underlying data access works.

## What NOT to Do

- Do not rewrite the engine, bots, commands, or special activities.
- Do not change game logic. This is a display and interaction layer only.
- Do not add any external dependencies. Standard library and existing requirements only.
- Do not create a GUI or web interface.
- Do not break existing tests. Run pytest before committing.

## Commit Strategy

Commit in logical units:
1. Board state display function
2. Bot turn summary and pause system
3. Card and event display improvements
4. Human turn context and status command integration
5. Setup flow improvements
6. Winter Quarters display
7. Game end display

Push when complete and give me a summary of what was built.
