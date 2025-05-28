# lod-bot
Automation of bots to run the board game Liberty or Death.

## Running a Turn

The project exposes a lightweight `Engine` that executes queued free
operations and drives bot turns.  A minimal example:

```python
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.cards import CARD_REGISTRY

state = build_state("long")            # load scenario
engine = Engine(state)

current_card = CARD_REGISTRY[1]         # pick a card
engine.play_turn("BRITISH", card=current_card)
```

The engine automatically handles Winter‑Quarters upkeep and refreshes
control and caps after each action.

## Environment Setup

Create a virtual environment and install the project requirements:

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

The repository no longer ships with a `.venv` directory, so you will
need to manage your own environment.

## Running Tests

Execute the tests with `pytest`:

```bash
pytest -q
```

## Generating Data Files

Scripts in `tools/` build JSON data from the reference sources:

- `python tools/build_map.py` reads `data/map_base.csv` and writes
  `lod_ai/map/data/map.json`. Use `--template` to regenerate a blank CSV
  containing all space names.
- `python tools/build_cards.py` parses `data/card reference.txt` and
  creates `lod_ai/cards/data.json`.

Additional utilities such as `clean_scenario.py` and
`validate_scenario.py` help maintain scenario files.
