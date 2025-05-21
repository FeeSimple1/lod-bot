# bots/patriot.py
"""
Minimal—but smarter—Patriot solo bot.

Decision order each time the Patriots take a Command:

  1.  If Resources ≤ 2 .................................  RALLY
  2.  Else if a worthwhile Battle exists ............... 40 % BATTLE
  3.  Otherwise ........................................ 50 % MUSTER / 50 % MARCH

• "Worthwhile Battle" = any space that contains Patriot cubes
  (Continentals or Militia) and British cubes (Regulars or Tories).
• BATTLE always targets exactly one such space; the main engine
  resolves casualties.
• MUSTER places a Continental if ≤ 3 already; otherwise RALLY flips
  spaces at Opposition.
"""

import random
from typing import Dict, Tuple, Optional

# ---------------------------------------------------------------------
# Entry point for ai_helper
# ---------------------------------------------------------------------
def choose_command(state: Dict) -> Tuple[str, Optional[str]]:
    res = state["resources"]["PATRIOTS"]

    # ---------- 1. RALLY when broke -----------------------------------
    if res <= 2:
        return ("RALLY", _pick_opposition_space(state))

    # ---------- 2. 40 % chance to Battle if target exists -------------
    battle_target = _pick_battle_target(state)
    if battle_target and random.random() < 0.40:
        return ("BATTLE", battle_target)

    # ---------- 3. otherwise Muster or March --------------------------
    if random.random() < 0.50:
        return ("MUSTER", _pick_muster_space(state))
    else:
        return ("MARCH", None)

# ---------------------------------------------------------------------
# Helper selectors
# ---------------------------------------------------------------------
def _pick_battle_target(state: Dict) -> Optional[str]:
    """Any space with both Patriot and British cubes; prefer Cities."""
    patri_tags = ("Patriot_Continentals", "Patriot_Militia")
    brit_tags  = ("British_Regulars", "British_Tory")

    def has_cubes(space: Dict, tags) -> bool:
        return any(space.get(t, 0) for t in tags)

    cities, others = [], []
    for name, sp in state["spaces"].items():
        if has_cubes(sp, patri_tags) and has_cubes(sp, brit_tags):
            (cities if "City" in name else others).append(name)

    pool = cities or others
    return random.choice(pool) if pool else None


def _pick_muster_space(state: Dict) -> Optional[str]:
    """Place a Continental where ≤ 3 already, else None."""
    spaces = [n for n, sp in state["spaces"].items()
              if sp.get("Patriot_Continentals", 0) < 4]
    return random.choice(spaces) if spaces else None


def _pick_opposition_space(state: Dict) -> Optional[str]:
    """Flip Opposition → Neutral via RALLY."""
    oppo = [n for n, sp in state["spaces"].items() if sp.get("Opposition", 0)]
    return random.choice(oppo) if oppo else None

def apply_committees_of_correspondence(state: Dict, target: str) -> None:
    """
    This function represents the Committees of Correspondence effect
    after a successful Patriot Rally action, as per the rulebook.
    It shifts political alignment and places Propaganda markers where applicable.
    """
    sp = state["spaces"][target]
    
    # Check if the space has Opposition (to shift toward Active Support)
    if sp.get("Opposition", 0) > 0:
        # Shift Opposition down and Support up
        sp["Opposition"] -= 1
        sp["Support"] = sp.get("Support", 0) + 1
        print(f"Patriot Committees of Correspondence shifts {target} toward Active Support.")
    
    # Place a Propaganda marker in the space
    _place_marker("Propaganda", target, 1, state)
    
    # Optionally: Increase Patriot Resources by 1 (if beneficial or required by the rules)
    add_resources("PATRIOTS", 1, state)  # You can adjust this based on the rules’ stipulation