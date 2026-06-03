# LLM Harness — play *Liberty or Death* as a human seat

This package lets a language model (or any decision **policy**) sit in a human
chair and play *Liberty or Death* against the rule-based bots. The other
factions are still driven by their flowchart bots; the LLM plays one or more
factions through the **exact same** decision flow a human uses at the CLI.

## How it works

The interactive CLI already implements complete human play: every choice —
which action, which command, which spaces, how many pieces, escorts, Special
Activities, Underground activation — is a small, numbered, **already
legality-filtered** menu funnelled through one input function.

The harness changes only the *input source*:

1. `cli_utils.set_input_provider(provider)` swaps stdin for a pluggable provider.
2. `LLMInputProvider` renders the board for the acting faction (`serialize_state`)
   and hands the menu to a `Policy`, which returns the option number.
3. The harness reuses the CLI's own `_human_decider` and command wizards
   verbatim, so the LLM walks the same legality-checked decision tree — illegal
   moves are impossible because only legal options are ever offered.
4. A separate hook lets the LLM also choose §3.6.3 Underground activation when
   **defending** during a bot's Battle.

Because the engine enforces legality and sequence-of-play, the LLM cannot make
an illegal move; at worst a poor policy makes a weak (but legal) choice.

## Usage

Offline smoke test — random *legal* moves, no API key:

```bash
python -m lod_ai.llm --scenario 1778 --factions PATRIOTS --policy random
```

Let an LLM play (needs `ANTHROPIC_API_KEY`):

```bash
python -m lod_ai.llm --scenario 1775 --factions PATRIOTS \
    --policy anthropic --model claude-sonnet-4-5 --verbose
```

From Python:

```python
from lod_ai.llm import run_game
from lod_ai.llm.policy import AnthropicPolicy, RandomPolicy

result = run_game(
    "1775", seed=1,
    llm_factions=["PATRIOTS", "FRENCH"],   # LLM plays the whole Rebellion side
    policy=AnthropicPolicy(model="claude-sonnet-4-5"),
)
print(result["winner"], result["cards_played"], result["decisions"])
```

## Policies

| Policy | Needs API? | Use |
|--------|-----------|-----|
| `RandomPolicy(seed)` | no | smoke-test the harness; deterministic by seed |
| `FirstChoicePolicy()` | no | trivial "always advance" baseline |
| `ScriptedPolicy([...])` | no | deterministic, hand-scripted runs (tests) |
| `AnthropicPolicy(model=...)` | yes | real LLM play |

Write your own by subclassing `Policy` and implementing

```python
def choose(self, observation: str, label: str, menu: dict | None,
           faction: str | None) -> str: ...
```

returning the raw string a human would type (an option number, or a count).
`menu` is `{"kind": "select"|"count", "prompt": str, "options": [...], ...}`.

## What the model sees

Each decision, the policy receives a compact board observation (current/upcoming
card, eligibility, resources, FNI, CBC/CRC, every faction's victory margins, and
all non-empty spaces with control/support/pieces/leaders) plus the menu of legal
options. It replies with a single number.

## Notes

- The harness restores stdin and clears the defender hook on exit, so it never
  leaks global state.
- `run_game(..., quiet=True)` suppresses the CLI's board printing; `verbose=True`
  streams each decision.
- This drives the same engine the bots use, so every rules fix applies equally to
  LLM play.
