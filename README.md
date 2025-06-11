# lod-bot
Automation of bots to run the board game Liberty or Death.

## Running a Turn

The project exposes a lightweight `Engine` that executes queued free
operations and drives bot turns.  A minimal example:

```python
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.cards import CARD_REGISTRY

state = build_state("long", setup_method="standard")  # load scenario
engine = Engine(state)                 # bot-driven
# engine = Engine(state, use_cli=True)  # manual selection

current_card = CARD_REGISTRY[1]         # pick a card
engine.play_turn("BRITISH", card=current_card)
```

Pass `setup_method="historical"` to `build_state` to stack the deck by Period
Events instead of shuffling all event cards.

The engine automatically handles Winter‑Quarters upkeep and refreshes
control and available-piece counts after every action, so the state
stays consistent.

### Running the Engine

Execute the above snippet in a Python interpreter or include it in a
script. Set `use_cli=True` when creating the `Engine` to manually select
commands instead of relying on the built‑in bot logic.

### Tests

Install the test requirements and run the suite:

```bash
pip install -r requirements-dev.txt
pytest -q
```

This runs the small suite under `lod_ai/tests` to verify that the bots
and core engine logic load correctly.
