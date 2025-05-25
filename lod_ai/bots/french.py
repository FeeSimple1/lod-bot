import random

def choose_command(state):
    """
    Minimal French flow‑chart stub.
      • If Resources ≤ 6  → TRADE (income)
      • else              → 50 % MARCH / 50 % BATTLE

    Returns a tuple: (command, target_space_or_None)
    """
    res = state["resources"]["FRENCH"]

    if res <= 6:
        return ("TRADE", None)

    # Resources > 6 : spend them
    return ("MARCH", None) if random.random() < 0.5 else ("BATTLE", None)
