from __future__ import annotations
"""lod_ai.commands.garrison
================================================
British **Garrison** Command implementation (§3.2.2).
Only available to the BRITISH faction and only when French
Naval Intervention (FNI) is *below* level 3.

Public entry point
------------------
``execute(state, faction, ctx, move_map, *, limited=False,
         displace_city: str | None = None,
         displace_target: str | None = None)``

Parameters
~~~~~~~~~~
* ``move_map`` – dict mapping ``src_space`` → ``dst_city`` → ``n_cubes``.
  It may include any number of source spaces (none of them Blockaded)
  and any number of destination *Cities* (none Blockaded).  All cubes
  moved must be ``REGULAR_BRI``.  If ``limited`` is *True* the dict must
  contain **exactly one* destination City; any number of sources may feed
  into it.
* ``displace_city`` & ``displace_target`` – if supplied, perform the
  optional displacement step.  The origin City must meet all rule
  criteria (British Control, no Patriot Fort, not Blockaded).  The target
  must be adjacent.  In a Limited Command it must be the same as the
  single destination City.

The function deducts **2 Resources total**, pushes history once, mutates
state, refreshes control, enforces global caps, logs a one‑line summary
and returns ``ctx`` unchanged.

Determinism note: no randomness occurs here.  All state changes happen
between a single ``push_history`` and the final refresh so that undo is
clean.
"""

from typing import Dict, Mapping

from lod_ai.rules_consts import (
    REGULAR_BRI, REGULAR_PAT, REGULAR_FRE,
    TORY,
    MILITIA_A, MILITIA_U,
)
from lod_ai.util.history   import push_history
from lod_ai.util.caps      import refresh_control, enforce_global_caps
from lod_ai.util.adjacency import is_adjacent
from lod_ai.leaders        import apply_leader_modifiers
from lod_ai.board.pieces      import remove_piece, add_piece
from lod_ai.economy.resources import spend, can_afford

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nav(state: Dict) -> Dict:
    """Return the nested naval dict created by the Naval‑System helpers."""
    return state.get("naval", {})


def _is_blockaded(city: str, state: Dict) -> bool:
    """True if the City currently hosts ≥1 Blockade marker."""
    return city in _nav(state).get("blockades", {})


def _count_brit_cubes(sp: Dict) -> int:
    """Return number of British *cubes* (Regulars + Tories) in space."""
    return sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0)


def _activate_militia(state: Dict, city: str) -> None:
    """Flip Underground Militia Active: 1 per 3 British cubes in *city*."""
    sp = state["spaces"][city]
    brit_cubes = _count_brit_cubes(sp)
    flips = min(brit_cubes // 3, sp.get(MILITIA_U, 0))
    if flips:
        remove_piece(state, MILITIA_U, city, flips)
        add_piece(state, MILITIA_A, city, flips)

def _displace_rebellion(origin: str, target: str, state: Dict):
    """Move all Rebellion pieces from *origin* to *target*."""
    if not is_adjacent(origin, target):
        raise ValueError(f"{origin} is not adjacent to {target} for displacement")

    sp_orig = state["spaces"][origin]
    sp_tgt  = state["spaces"][target]

    tags = (REGULAR_PAT, REGULAR_FRE, MILITIA_U, MILITIA_A)
    for tag in tags:
        n = sp_orig.get(tag, 0)
        if n:
            remove_piece(state, tag, origin, n)
            add_piece(state, tag, target, n)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(
    state: Dict,
    faction: str,
    ctx: Dict,
    move_map: Mapping[str, Mapping[str, int]],
    *,
    limited: bool = False,
    displace_city: str | None = None,
    displace_target: str | None = None,
) -> Dict:
    """Perform the British GARRISON Command.

    ``move_map`` example::
        {
            "New_York_City": {"Boston": 2},     # move 2 regs NYC → Boston
            "Savannah":      {"Boston": 1},     # move 1 reg  Savannah → Boston
            "Quebec_City":  {"Philadelphia": 3}
        }

    *Keys* are origin spaces; *values* are mapping of destination Cities to
    number of Regulars.  Provide 0 or omit an entry to move none.
    """

    if faction.upper() != "BRITISH":
        raise ValueError("Only BRITISH may execute GARRISON")

    # FNI gate -------------------------------------------------------
    if _nav(state).get("fni", 0) == 3:
        raise ValueError("GARRISON unavailable at FNI level 3")

    # Cost -----------------------------------------------------------
    spend(state, "BRITISH", 2)

    # Leader hooks (none today, keep pattern) -----------------------
    ctx = apply_leader_modifiers(state, faction, "pre_garrison", ctx)

    state["_turn_command"] = COMMAND_NAME
    dest_set = {dst for inner in move_map.values() for dst in inner}
    # Limited‑command validations -----------------------------------
    if limited:
        if len(dest_set) != 1:
            raise ValueError("Limited GARRISON must end in a single City")
        if displace_city and displace_city != next(iter(dest_set)):
            raise ValueError("Limited GARRISON displacement must originate in the destination City")

    state.setdefault("_turn_affected_spaces", set()).update(dest_set)
    # Main movement --------------------------------------------------
    push_history(state, "BRITISH GARRISON")

    for src, dsts in move_map.items():
        sp_src = state["spaces"][src]
        if _is_blockaded(src, state):
            raise ValueError(f"Source {src} is Blockaded; cannot Garrison from it")
        moved_from_src = 0
        for dst_city, n in dsts.items():
            if n <= 0:
                continue
            sp_dst = state["spaces"][dst_city]
            if not sp_dst.get("is_city"):
                raise ValueError(f"Destination {dst_city} is not a City")
            if _is_blockaded(dst_city, state):
                raise ValueError(f"Destination {dst_city} is Blockaded; cannot Garrison into it")
            avail = sp_src.get(REGULAR_BRI, 0)
            if n > avail:
                raise ValueError(f"Trying to move {n} regs from {src} but only {avail} present")
            if limited and dst_city != next(iter({d for inner in move_map.values() for d in inner})):
                raise ValueError("All moves in Limited GARRISON must share the same destination City")

            # actual move
            remove_piece(state, REGULAR_BRI, src, n)
            add_piece(state, REGULAR_BRI, dst_city, n)
            moved_from_src += n
        if moved_from_src == 0:
            continue

    # Militia activation --------------------------------------------
    if limited:
        city_list = list({d for inner in move_map.values() for d in inner})
    else:
        city_list = [name for name, sp in state["spaces"].items() if sp.get("is_city") and not _is_blockaded(name, state)]

    for city in city_list:
        _activate_militia(state, city)

    # Optional displacement -----------------------------------------
    if displace_city and displace_target:
        if _is_blockaded(displace_city, state):
            raise ValueError("Cannot displace from a Blockaded City")
        sp_city = state["spaces"][displace_city]
        if sp_city.get("Patriot_Fort", 0):
            raise ValueError("Cannot displace from a City with a Patriot Fort")
        # British Control check (1.7)
        if state.get("control", {}).get(displace_city) != "BRITISH":
            raise ValueError("Displace city must be under British Control")
        _displace_rebellion(displace_city, displace_target, state)

    # Final bookkeeping ---------------------------------------------
    refresh_control(state)
    enforce_global_caps(state)

    dest_summary = {dst for inner in move_map.values() for dst in inner}
    state.setdefault("log", []).append(
        f"BRITISH GARRISON → {sorted(dest_summary)} (limited={limited}, displace={bool(displace_city)})"
    )
    return ctx
