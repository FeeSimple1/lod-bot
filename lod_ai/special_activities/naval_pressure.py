"""
lod_ai.special_activities.naval_pressure
========================================
Implements the Naval Pressure SA for:

* **BRITISH** (§4.2.3) – may accompany ANY Command.
* **FRENCH**  (§4.5.3) – may accompany any Command EXCEPT French Agent
  Mobilization, and only *after* Treaty of Alliance.

This SA mutates two top-level state fields assumed to exist:

    • state["resources"]      – dict by faction.
    • state["fni_level"]      – int 0-3.  (0 = none, 3 = max)
    • state["markers"]["Blockade"]   – {"pool": int, "on_map": set[str]}

If your schema differs, adapt the helper functions at the top.
"""

from __future__ import annotations
from typing import Dict
from lod_ai.util.history import push_history
from lod_ai.util.caps    import enforce_global_caps, refresh_control
from lod_ai.economy.resources import add as add_res      # NEW
from lod_ai.rules_consts import BLOCKADE, WEST_INDIES_ID, BRITISH, FRENCH
from lod_ai.cards.effects.shared import adjust_fni

SA_NAME = "NAVAL_PRESSURE"      # auto-registered by special_activities/__init__.py

# ---------------------------------------------------------------------------
# Helper adapters – tweak here if your map schema differs
# ---------------------------------------------------------------------------

def _add_resources(state: Dict, faction: str, amt: int) -> None:
    add_res(state, faction, amt)          # caps at 50 automatically

def _roll_d3(state: Dict) -> int:
    val = state["rng"].randint(1, 3)
    state.setdefault("rng_log", []).append(("D3", val))
    return val


def _cities_with_blockade(state: Dict) -> list[str]:
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    return [sid for sid in bloc.get("on_map", set()) if sid != WEST_INDIES_ID]

def _remove_blockade_from_city_to_wi(state: Dict, city_id: str) -> None:
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    on_map = bloc.setdefault("on_map", set())
    if city_id not in on_map:
        raise ValueError(f"{city_id} has no Blockade to remove.")
    on_map.discard(city_id)
    bloc["pool"] = bloc.get("pool", 0) + 1


def _place_blockade_from_wi(state: Dict, city_id: str) -> None:
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    pool = bloc.get("pool", 0)
    if pool <= 0:
        raise ValueError("No Blockade markers in West Indies to place.")
    bloc["pool"] = pool - 1
    bloc.setdefault("on_map", set()).add(city_id)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    *,
    city_choice: str | None = None,           # British (after TOA) choose city; French always choose city
    rearrange_map: dict[str, int] | None = None,  # French optional full rearrange {city: n_blockades}
) -> Dict:
    """
    Parameters
    ----------
    city_choice
        • British (FNI>0) – city from which to pull a Blockade to West Indies.
        • French          – city to receive a new Blockade from W.I. (ignored if
          rearrange_map supplied).
    rearrange_map
        For the French **only when no markers remain in West Indies**:
        a mapping {city_id: n_to_have_after}.  All cities in map must already
        hold a marker so we are merely rearranging.
    """
    state["_turn_used_special"] = True

    if faction == BRITISH:
        _exec_british(state, ctx, city_choice)
    elif faction == FRENCH:
        _exec_french(state, ctx, city_choice, rearrange_map)
    else:
        raise ValueError("Naval Pressure is British or French only.")

    refresh_control(state)
    enforce_global_caps(state)
    return ctx


# ---------------------------------------------------------------------------
# British implementation
# ---------------------------------------------------------------------------

def _exec_british(state: Dict, ctx: Dict, city_choice: str | None) -> None:
    push_history(state, "BRITISH NAVAL_PRESSURE")

    if not state.get("toa_played"):
        gain = _roll_d3(state)
        _add_resources(state, BRITISH, gain)
        state.setdefault("log", []).append(f"BRITISH Naval Pressure +{gain}£ (pre-TOA)")
        return

    # After TOA
    if state.get("fni_level", 0) == 0:
        gain = _roll_d3(state)
        _add_resources(state, BRITISH, gain)
        state.setdefault("log", []).append(f"BRITISH Naval Pressure +{gain}£ (FNI=0)")
        return

    # FNI > 0: lower FNI one, remove a city Blockade to W.I.
    adjust_fni(state, -1)

    if not city_choice:
        cities = _cities_with_blockade(state)
        if not cities:
            raise ValueError("No Blockades on cities to remove.")
        city_choice = cities[0]                      # auto-pick first if caller silent

    _remove_blockade_from_city_to_wi(state, city_choice)
    state.setdefault("log", []).append(
        f"BRITISH Naval Pressure: FNI–1 → {state['fni_level']}, "
        f"Blockade {city_choice} → West Indies"
    )


# ---------------------------------------------------------------------------
# French implementation
# ---------------------------------------------------------------------------

def _exec_french(
    state: Dict, ctx: Dict,
    city_choice: str | None,
    rearrange_map: dict[str, int] | None,
) -> None:
    if not state.get("toa_played"):
        raise ValueError("French Naval Pressure requires Treaty of Alliance.")

    push_history(state, "FRENCH NAVAL_PRESSURE")
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    bloc.setdefault("on_map", set())

    # §4.5.3: "FNI may not be higher than the number of Squadron/Blockade
    # available to place on Cities."  The total in-play markers (pool + on
    # cities) sets the ceiling — markers still in Unavailable don't count.
    wi_blks = bloc.get("pool", 0)
    on_map_count = len(bloc.get("on_map", set()))
    max_fni = wi_blks + on_map_count
    if state.get("fni_level", 0) + 1 > max_fni:
        raise ValueError(f"Cannot raise FNI above {max_fni} (limited by markers in play).")
    adjust_fni(state, +1)

    if wi_blks:   # Option A: move one marker from W.I. to a city
        if not city_choice:
            raise ValueError("French must specify a city to receive the Blockade.")
        _place_blockade_from_wi(state, city_choice)
        state.setdefault("log", []).append(
            f"FRENCH Naval Pressure: FNI→{state['fni_level']}, "
            f"Blockade West Indies → {city_choice}"
        )
    else:         # Option B: rearrange existing city markers
        if not rearrange_map:
            raise ValueError("No markers in W.I.; supply rearrange_map.")
        # Clear all city blockades then re-add per map
        bloc["on_map"].clear()
        for city_id, n in rearrange_map.items():
            if n > 0:
                bloc["on_map"].add(city_id)
        state.setdefault("log", []).append(
            f"FRENCH Naval Pressure: FNI→{state['fni_level']}, blockades rearranged"
        )
