# lod-bot
Menu-driven helpers and bots for playing Liberty or Death.

## Prerequisites
- Python 3.10 or newer (the code uses `|` type unions).
- Optional: a virtual environment to isolate dependencies.

## Installation
1. Create and activate a virtual environment:
   - Unix/macOS:
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```
   - Windows (Command Prompt):
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate.bat
     ```
2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Running the interactive CLI
Launch the menu-driven interface with:
```bash
python -m lod_ai.interactive_cli
```

You will be prompted for:
- Scenario (1775 Long, 1776 Medium, or 1778 Short).
- Number of human players (0–4).
- Which factions are human-controlled (BRITISH, PATRIOTS, FRENCH, INDIANS).

During play, each revealed card shows its title, order icons/list, and the factions currently eligible. For every faction’s decision slot the CLI will only offer actions that are legal for that position (Pass, Event, or Command, with Special Activities only when permitted). Command menus are tailored to the faction and Treaty status for the French.

### Example session (abridged)
```
Liberty or Death — Interactive CLI
Select a scenario:
  1. 1775 (Long)
  2. 1776 (Medium)
  3. 1778 (Short)
Enter scenario number: 1
Number of human players (0-4): 1
Select human-controlled factions:
  1. BRITISH
  2. PATRIOTS
  3. FRENCH
  4. INDIANS
Choose faction #1: 2

====================================
Card 1: Common Sense
Order: BF
Currently eligible: BRITISH, PATRIOTS, FRENCH, INDIANS
====================================
BRITISH turn. Allowed actions: command, event, pass
P) Pass | E) Event | C) Command
Choose action: P
```

## Running tests
Execute the test suite with:
```bash
pytest
```

The tests live under `lod_ai/tests` and cover card handlers, engine sequencing, and bot scaffolding.
