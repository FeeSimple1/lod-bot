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
engine = Engine(state)                 # bot-driven
# engine = Engine(state, use_cli=True)  # manual selection

current_card = CARD_REGISTRY[1]         # pick a card
engine.play_turn("BRITISH", card=current_card)
```

The engine automatically handles Winter‑Quarters upkeep and refreshes
