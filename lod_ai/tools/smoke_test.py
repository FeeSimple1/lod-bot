"""Quick smoke test for loading state and executing a minimal command."""

from lod_ai import rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.util.normalize_state import normalize_state
from lod_ai.util.validate import validate_state


def run() -> None:
    state = build_state("long")

    # Ensure Indians can afford a simple Gather
    state["resources"][C.INDIANS] = max(state["resources"].get(C.INDIANS, 0), 1)

    engine = Engine(state, use_cli=True)
    engine.dispatcher.execute(
        "gather",
        faction=C.INDIANS,
        selected=["Northwest"],
        place_one={"Northwest"},
        limited=True,
    )

    normalize_state(state)
    validate_state(state)
    print("Smoke test completed successfully.")


if __name__ == "__main__":
    run()
