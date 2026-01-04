# lod-bot
Interactive, menu-driven helpers and bots for **Liberty or Death**.

## Installation
1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Run the interactive CLI
Start a game with:
```bash
python -m lod_ai
```

Setup wizard:
1) Pick scenario (1775 Long, 1776 Medium, 1778 Short).
2) Choose deck method (Standard or Period Events) and RNG seed.
3) Select number of human players (0–4) and which factions they control.

During play the CLI always shows the current and upcoming card. Each faction’s turn presents only the actions that are legal for that slot (Pass, Event, Command/Special). Commands, spaces, and piece counts are chosen from numbered menus—no free typing. Illegal choices are rejected before they commit.

## Running tests
```bash
pytest
```

## CLI flow example
```
Liberty or Death — Interactive CLI
Select a scenario:
  1. 1775 Long
  2. 1776 Medium
  3. 1778 Short
Select: 1
Deck method:
  1. Standard
  2. Period Events
Select: 1
Select RNG seed:
  1. 1
  2. 2
  3. 3
  4. 4
  5. 5
  6. Random (based on time)
Select: 1
Number of human players:
  1. 0
  2. 1
  3. 2
  4. 3
  5. 4
Select: 2
Select human-controlled factions:
  1. BRITISH
  2. PATRIOTS
  3. FRENCH
  4. INDIANS
Select: 1
Select: 2

================ CURRENT CARD ================
16: Treaty of Alliance | Order: PFBI
---------------- UPCOMING ----------------
17: Winter Quarters | Order: PFBI
=============================================
BRITISH turn. Choose action:
  1. Pass
  2. Event
  3. Command
Select: 3
```
