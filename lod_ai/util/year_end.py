"""
Winter‑Quarters resolution · Liberty or Death  (Rule 6, Aug 2016)
================================================================
Executed **once** per Winter‑Quarters card after the final Faction has acted,
or whenever an Event sets ``state["winter_flag"]``.

Pipeline (Rule 6 sequence):
    6.1  Return Leaders, lift Casualties
    6.2  Supply Phase              – complete
    6.3  Resource Income           – complete
    6.4  Support Phase             – complete
    6.5  Leader Change / Redeploy, British Release, FNI drift – complete
    6.6  Desertion Phase           – complete
    6.7  Reset Phase               – **NEW**
    British Up‑keep follows Reset unless this is the final round

All piece & Resource mutations *must* route through the gate‑keepers:
    • lod_ai.board.pieces.*
    • lod_ai.economy.resources.*

Every step logs a concise message via ``util.history.push_history``.
"""

# ────────────────────────────────────────────────────────────────
#  Imports
# ────────────────────────────────────────────────────────────────
from typing import List, Tuple, Dict

from lod_ai.util.history import push_history
from lod_ai.board.pieces import (
    remove_piece, place_with_caps, return_leaders, lift_casualties
)
import lod_ai.board.pieces as bp
from lod_ai.board import control as board_control
from lod_ai.map import adjacency as map_adj
from lod_ai.util import caps as caps_util
from lod_ai.economy import resources
from lod_ai.economy.resources import add as add_res
from lod_ai.cards.effects.shared import adjust_fni
from lod_ai.commands.battle import execute as battle_execute
from lod_ai.victory import check as victory_check
from lod_ai.rules_consts import (
    MILITIA_A, MILITIA_U, REGULAR_PAT,
    REGULAR_BRI, REGULAR_FRE,
    TORY, VILLAGE, WARPARTY_A, WARPARTY_U,
    BRITISH, PATRIOTS, FRENCH, INDIANS,
    FORT_BRI, FORT_PAT,
    ACTIVE_SUPPORT, ACTIVE_OPPOSITION,
    BLOCKADE, BLOCKADE_KEY, WEST_INDIES_ID,
    LEADER_CHAIN,
    RAID, PROPAGANDA
)
from lod_ai.victory import final_scoring

# ────────────────────────────────────────────────────────────────
#  Helper – count faction pieces in a space (for leader redeploy)
# ────────────────────────────────────────────────────────────────

_FACTION_PIECES: Dict[str, Tuple[str, ...]] = {
    BRITISH: (REGULAR_BRI, TORY),
    PATRIOTS: (REGULAR_PAT, MILITIA_A, MILITIA_U),
    FRENCH: (REGULAR_FRE,),           # ← fixed
    INDIANS: (WARPARTY_A, WARPARTY_U),
}

def _piece_total(sp: Dict, faction: str) -> int:
    return sum(sp.get(pid, 0) for pid in _FACTION_PIECES[faction])


# ────────────────────────────────────────────────────────────────
#  §6.2  Supply Phase
# ────────────────────────────────────────────────────────────────

def _supply_phase(state):
    def _pay(faction, sid, tag):
        if resources.can_afford(state, faction, 1):
            resources.spend(state, faction, 1)
            push_history(state, f"{tag} – paid 1 Resource ({sid})")
            return True
        return False

    # British
    for sid, sp in state["spaces"].items():
        if sid == WEST_INDIES_ID:
            continue
        if sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0) == 0:
            continue
        meta = map_adj.space_meta(sid) or {}
        space_type = meta.get("type") or sp.get("type")
        if sp.get(FORT_BRI) or (space_type == "City" and state.get("control", {}).get(sid) == BRITISH):
            continue
        if _pay(BRITISH, sid, "British Supply"):
            continue
        if board_control.shift_support(state, sid, -1):
            push_history(state, f"British Supply – Support shifted in {sid}")
            continue
        if sp.get(REGULAR_BRI, 0):
            remove_piece(state, REGULAR_BRI, sid, sp[REGULAR_BRI], to="available")
        if sp.get(TORY, 0):
            remove_piece(state, TORY, sid, sp[TORY], to="available")
        push_history(state, f"British Supply – cubes removed from {sid}")

    # Patriots
    for sid, sp in state["spaces"].items():
        total = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0) + sp.get(REGULAR_PAT, 0)
        if not total:
            continue
        meta = map_adj.space_meta(sid) or {}
        space_type = meta.get("type") or sp.get("type")
        if sp.get(FORT_PAT) or ((space_type in ("Colony", "City")) and state.get("control", {}).get(sid) == "REBELLION"):
            continue
        if _pay(PATRIOTS, sid, "Patriot Supply"):
            continue
        remove_target = total // 2
        for pid in (MILITIA_U, MILITIA_A, REGULAR_PAT):
            if remove_target == 0:
                break
            qty = min(sp.get(pid, 0), remove_target)
            if qty:
                remove_piece(state, pid, sid, qty, to="available")
                remove_target -= qty
        push_history(state, f"Patriot Supply – units removed from {sid}")

    # French
    for sid, sp in state["spaces"].items():
        fr = sp.get(REGULAR_FRE, 0)
        if fr == 0 or sid == WEST_INDIES_ID:
            continue

        in_supply = sp.get(FORT_PAT) or state.get("control", {}).get(sid) == "REBELLION"
        if in_supply:
            continue

        # NEW – try to move to the nearest space with a Patriot Fort
        forts = [
            s for s, sp2 in state["spaces"].items()
            if sp2.get(FORT_PAT)
        ]
        if forts:
            # choose the fort with the shortest path (adj is map.adjacency alias)
            dest = min(
                forts,
                key=lambda x: len(map_adj.shortest_path(state, sid, x))
            )
            if dest != sid:
                bp.move_piece(state, REGULAR_FRE, sid, dest, fr)
                push_history(
                    state,
                    f"French Supply – moved {fr} regs {sid}→{dest}"
                )
                continue        # Supply satisfied by moving

        # if no fort found or move impossible, pay if you can…
        if _pay(FRENCH, sid, "French Supply"):
            continue

        # …otherwise remove them to Available
        bp.remove_piece(state, REGULAR_FRE, sid, fr)
        push_history(
            state,
            f"French Supply – {fr} regs removed ({sid})"
        )

    # Indians – auto‑Village
    if not any(sp.get(VILLAGE, 0) for sp in state["spaces"].values()):
        reserve = next((s for s, sp in state["spaces"].items() if sp.get("Indian_Reserve")), None)
        if reserve:
            place_with_caps(state, VILLAGE, reserve, 1)
            push_history(state, f"Indian Supply – auto‑Village in {reserve}")

    for sid, sp in state["spaces"].items():
        wp_total = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
        if not wp_total:
            continue
        if sp.get(VILLAGE) or sp.get("Indian_Reserve"):
            continue
        if _pay(INDIANS, sid, "Indian Supply"):
            continue
        dests = [d for d, sp2 in state["spaces"].items() if sp2.get(VILLAGE)]
        if not dests:
            continue
        dest = min(dests, key=lambda d: len(map_adj.shortest_path(state, sid, d)))
        for pid in (WARPARTY_U, WARPARTY_A):
            qty = sp.get(pid, 0)
            if qty:
                remove_piece(state, pid, sid, qty, to="available")
                place_with_caps(state, pid, dest, qty)
        push_history(state, f"Indian Supply – War Parties moved {sid} ➜ {dest}")

    # Refresh & caps
    board_control.refresh_control(state)
    caps_util.enforce_global_caps(state)

    # West Indies battle + garrison payment
    wi = state["spaces"][WEST_INDIES_ID]
    if wi.get(REGULAR_FRE) and wi.get(REGULAR_BRI):
        battle_execute(state, FRENCH, {}, [WEST_INDIES_ID])
        push_history(state, "Free Battle in West Indies (6.2.2)")
    def _wi_cleanup(pid, faction):
        cnt = wi.get(pid, 0)
        if not cnt:
            return
        if resources.can_afford(state, faction, 1):
            resources.spend(state, faction, 1)
            push_history(state, f"{faction.title()} pay 1 Resource to keep garrison ({cnt}) in West Indies")
        else:
            remove_piece(state, pid, WEST_INDIES_ID, cnt, to="available")
            push_history(state, f"{faction.title()} return garrison ({cnt}) from West Indies")
    _wi_cleanup(REGULAR_FRE, FRENCH)
    _wi_cleanup(REGULAR_BRI, BRITISH)
    push_history(state, "Supply Phase complete")

# ────────────────────────────────────────────────────────────────
#  §6.3  Resource Income 
# ────────────────────────────────────────────────────────────────

def _resource_income(state):
    """Apply Winter-Quarters Resource income exactly per Rule 6.3.

    - British:  + (# British Forts)  
                 + Σ population of *non-Blockaded* British-Controlled Cities  
                 +5 if British control West Indies
    - Indians:  + ⌊Villages / 2⌋
    - Patriots: + (# Patriot Forts)  
                 + ⌊Rebellion-controlled spaces (ex-W.I.) / 2⌋
    - French:   Before ToA → 2 × Blockade markers in West Indies  
                 After  ToA → FNI box + Σ population of Cities *not* British-Controlled  
                 +5 if Rebellion controls West Indies
    All adds are capped at 50 by economy.resources.add().
    """

    british_income   = 0
    patriot_income   = 0
    french_income    = 0
    indian_income    = 0
    rebellion_spaces = 0                    # exclude West Indies
    control_map = state.get("control", {})
    if not isinstance(control_map, dict):
        control_map = {}

    blockade_state = state.get("markers", {}).get(BLOCKADE, {"pool": 0, "on_map": set()})
    if not isinstance(blockade_state, dict):
        blockade_state = {"pool": 0, "on_map": set()}

    blockaded_cities = blockade_state.get("on_map", set())
    if not isinstance(blockaded_cities, set):
        blockaded_cities = set(blockaded_cities or [])

    # Support both "blockade pool" and "blockade count stored in West Indies space"
    wi_space = state.get("spaces", {}).get(WEST_INDIES_ID, {})
    wi_blockades = 0
    if isinstance(wi_space, dict):
        wi_blockades += int(wi_space.get(BLOCKADE, 0) or 0)
        wi_blockades += int(wi_space.get(BLOCKADE_KEY, 0) or 0)

    wi_pool_blockades = int(blockade_state.get("pool", 0) or 0)
    total_wi_blockades = wi_pool_blockades + wi_blockades

    # ---------------  map sweep  --------------------------------
    for sid, sp in state["spaces"].items():
        meta = map_adj.space_meta(sid) or {}
        space_type = meta.get("type") or sp.get("type")
        pop = meta.get("population", sp.get("pop", 0))
        ctrl = control_map.get(sid)

        # British Forts
        if sp.get(FORT_BRI):
            british_income += 1

        # Patriot Forts
        if sp.get(FORT_PAT):
            patriot_income += 1

        # Villages (Indians)
        indian_income += sp.get(VILLAGE, 0)

        # British-controlled, non-Blockaded *Cities* → pop to British
        if (space_type == "City"
                and ctrl == BRITISH
                and sid not in blockaded_cities):
            british_income += pop

        # Rebellion-controlled spaces (skip West Indies)
        if sid != WEST_INDIES_ID and ctrl == "REBELLION":
            rebellion_spaces += 1

        # City population *not* British-Controlled (for French after ToA)
        if space_type == "City" and ctrl != BRITISH:
            french_income += pop      # kept only post-ToA

    # ---------------  derive totals  ----------------------------
    indian_income //= 2                         # ⌊Villages / 2⌋
    patriot_income += rebellion_spaces // 2     # ⌊spaces / 2⌋

    wi_ctrl = control_map.get(WEST_INDIES_ID)

    if state.get("treaty_of_alliance", False):
        # After ToA: keep city pop and add FNI box level
        french_income += state.get("fni_level", 0)
    else:
        # Before ToA: ignore city pop, earn 2× Blockades in West Indies (pool + per-space)
        french_income = total_wi_blockades * 2

    # West Indies bonuses
    if wi_ctrl == BRITISH:
        british_income += 5
    if wi_ctrl == "REBELLION":
        french_income += 5

    # ---------------  apply & log  ------------------------------
    if british_income:
        add_res(state, BRITISH, british_income)
        push_history(state, f"British earn +{british_income} Resources (6.3)")

    if indian_income:
        add_res(state, INDIANS, indian_income)
        push_history(state, f"Indians earn +{indian_income} Resources (6.3)")

    if patriot_income:
        add_res(state, PATRIOTS, patriot_income)
        push_history(state, f"Patriots earn +{patriot_income} Resources (6.3)")

    if french_income:
        add_res(state, FRENCH, french_income)
        push_history(state, f"French earn +{french_income} Resources (6.3)")

# ────────────────────────────────────────────────────────────────
#  Support Phase (§6.4) – NEW
# ────────────────────────────────────────────────────────────────

from collections import defaultdict

def _support_phase(state):
    """
    Rule 6.4 – British then Patriots may spend Resources to adjust
    Support or Opposition.

    • British (Reward Loyalty) and Patriots (Committees of Correspondence)
      act in that order.
    • A space may shift at most TWO levels during this phase.
    • The routine below follows a deterministic “spend until blocked” policy.
    """

    from collections import defaultdict

    shifted = defaultdict(int)      # how many times each space has shifted
    control_map = state.get("control", {})
    if not isinstance(control_map, dict):
        control_map = {}

    def _ctrl(sid, sp):
        return control_map.get(sid)

    markers = state.setdefault("markers", {})
    raid_on_map = markers.setdefault(RAID, {"pool": 0, "on_map": set()}).setdefault("on_map", set())
    propaganda_on_map = markers.setdefault(PROPAGANDA, {"pool": 0, "on_map": set()}).setdefault("on_map", set())

    # ---------------------------------------------------------------
    # 6.4.1  Reward Loyalty  (British)
    # ---------------------------------------------------------------
    spent = 0
    for sid, sp in state["spaces"].items():
        # skip if this space already shifted twice
        if shifted[sid] >= 2:
            continue

        # must be British-controlled City/Colony and contain both Regulars & Tories
        if not (_ctrl(sid, sp) == BRITISH and sp.get(REGULAR_BRI) and sp.get(TORY)):
            continue

        level = state["support"].get(sid, 0)
        if level >= ACTIVE_SUPPORT:          # already max Active Support
            continue
        steps_remaining = 2 - shifted[sid]
        if steps_remaining <= 0:
            continue

        # first, remove Raid or Propaganda marker if present (costs 1 each)
        for marker_tag, on_map in ((RAID, raid_on_map), (PROPAGANDA, propaganda_on_map)):
            if steps_remaining <= 0 or not resources.can_afford(state, BRITISH, 1):
                break
            if sid in on_map:
                resources.spend(state, BRITISH, 1)
                remove_piece(state, marker_tag, sid, 1, to="available")
                push_history(state, f"British removed {marker_tag} in {sid} (6.4.1)")
                shifted[sid] += 1
                steps_remaining -= 1

        # pay 1 Resource per support shift, up to remaining steps
        while steps_remaining > 0 and resources.can_afford(state, BRITISH, 1) and level < ACTIVE_SUPPORT:
            resources.spend(state, BRITISH, 1)
            level += 1
            state["support"][sid] = level
            spent += 1
            shifted[sid] += 1
            steps_remaining -= 1
            push_history(state, f"British shifted {sid} toward Active Support (6.4.1)")

    if spent:
        push_history(state, f"British spent {spent} Resources on Reward Loyalty (6.4.1)")

    # ---------------------------------------------------------------
    # 6.4.2  Committees of Correspondence  (Patriots)
    # ---------------------------------------------------------------
    spent = 0
    for sid, sp in state["spaces"].items():
        if shifted[sid] >= 2:      # already shifted twice
            continue

        # must be Rebellion-controlled and contain Patriot pieces
        if not (_ctrl(sid, sp) == "REBELLION" and (sp.get(MILITIA_A) or sp.get(MILITIA_U) or sp.get(REGULAR_PAT))):
            continue

        level = state["support"].get(sid, 0)
        if level <= ACTIVE_OPPOSITION:            # already max Active Opposition
            continue
        steps_remaining = 2 - shifted[sid]
        if steps_remaining <= 0:
            continue

        # Skip if only marker removal would occur
        if level <= ACTIVE_OPPOSITION:
            continue

        # remove Raid markers first (cost 1 each)
        if sid in raid_on_map and steps_remaining > 0 and resources.can_afford(state, PATRIOTS, 1):
            resources.spend(state, PATRIOTS, 1)
            remove_piece(state, RAID, sid, 1, to="available")
            push_history(state, f"Patriots removed Raid in {sid} (6.4.2)")
            shifted[sid] += 1
            steps_remaining -= 1

        # pay 1 Resource per shift toward Opposition
        while steps_remaining > 0 and resources.can_afford(state, PATRIOTS, 1) and level > ACTIVE_OPPOSITION:
            resources.spend(state, PATRIOTS, 1)
            level -= 1
            state["support"][sid] = level
            spent += 1
            shifted[sid] += 1
            steps_remaining -= 1
            push_history(state, f"Patriots shifted {sid} toward Active Opposition (6.4.2)")

    if spent:
        push_history(state, f"Patriots spent {spent} Resources on Committees (6.4.2)")

# ────────────────────────────────────────────────────────────────
#  Leader Change  (§6.5.1)
# ────────────────────────────────────────────────────────────────

def _leader_change(state):
    """Apply automatic Leader Change for the **first faction** on the next
    Event card (state["upcoming_card"]).

    Expected card stub::
        state["upcoming_card"] = {"first_faction": BRITISH}
    """
    card = state.get("upcoming_card", {})
    fac = card.get("first_faction")
    if not fac or fac == PATRIOTS:
        return  # no change required or Patriots never change
    if fac == FRENCH and not state.get("treaty_of_alliance", False):
        return  # French changes locked until ToA

    current = state.get("leaders", {}).get(fac)
    nxt = LEADER_CHAIN.get(current)
    if not nxt:
        return  # no further change in chain

    state["leaders"][fac] = nxt
    push_history(state, f"Leader Change – {fac} {current} → {nxt} (6.5.1)")

# ────────────────────────────────────────────────────────────────
#  Leader Redeploy  (§6.5.2)
# ────────────────────────────────────────────────────────────────

def _leader_redeploy(state):
    order = [INDIANS, FRENCH, BRITISH, PATRIOTS]
    for fac in order:
        leader = state.get("leaders", {}).get(fac)
        if not leader:
            continue
        # Determine destination: space with most pieces of that faction
        dest = None
        best = 0
        for sid, sp in state["spaces"].items():
            cnt = _piece_total(sp, fac)
            if cnt > best:
                best, dest = cnt, sid
        if dest:
            state.setdefault("leader_locs", {})[leader] = dest
            push_history(state, f"Leader Redeploy – {fac} leader to {dest} (6.5.2)")
        else:
            state.setdefault("leader_locs", {})[leader] = "Available"
            push_history(state, f"Leader Redeploy – {fac} leader to Available (6.5.2)")

# ────────────────────────────────────────────────────────────────
#  British Release Date  (§6.5.3)
# ────────────────────────────────────────────────────────────────

def _british_release(state):
    qty = state.pop("brit_release", 0)
    if not qty:
        return

    # Move up to qty British Regulars from Unavailable → Available
    moved = bp.lift_unavailable(state, REGULAR_BRI, qty)

    if moved:
        push_history(
            state,
            f"British Release Date – {moved} Regulars to Available (6.5.3)"
        )

# ────────────────────────────────────────────────────────────────
#  FNI drift & Blockade shuffle (§6.5.4)
# ────────────────────────────────────────────────────────────────

def _fni_drift(state):
    if not state.get("treaty_of_alliance", False):
        return  # only after ToA
    # Lower FNI one box if > 0
    if state.get("fni_level", 0) > 0:
        adjust_fni(state, -1)
        push_history(state, "FNI drift – box shifts 1 toward War (6.5.4)")
    # Remove one Blockade from a City to the West Indies pool (§6.5.4)
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    on_map = bloc.get("on_map", set())
    if on_map:
        removed_city = next(iter(on_map))
        on_map.discard(removed_city)
        bloc["pool"] = bloc.get("pool", 0) + 1
        push_history(state, f"Blockade removed from {removed_city} to West Indies (6.5.4)")

        # Per Manual Ch 6.5.4: "French may rearrange the remaining Blockade markers"
        # For bot play, the French bot decides; for now, log the opportunity.
        push_history(state, "French may rearrange remaining Blockade markers (6.5.4)")

# ────────────────────────────────────────────────────────────────
#  §6.6  Desertion helpers  (full Rule 6.6 logic)
# ────────────────────────────────────────────────────────────────

def _patriot_desertion(state):
    """Remove 1‑in‑5 Militia and 1‑in‑5 Continentals (round down).

    • **Indians** choose the *first* Militia **and** the *first* Continental to desert.
    • **Patriots** choose the remainder (engine removes least‑harmful pieces).
    """
    # candidate lists restricted to Colonies
    mil_spaces = [(sid, sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0))
                  for sid, sp in state["spaces"].items() if sp.get("type") == "Colony" and (sp.get(MILITIA_U,0)+sp.get(MILITIA_A,0))]
    con_spaces = [(sid, sp.get(REGULAR_PAT, 0))
                  for sid, sp in state["spaces"].items() if sp.get("type") == "Colony" and sp.get(REGULAR_PAT,0)]

    total_mil = sum(c for _, c in mil_spaces)
    total_con = sum(c for _, c in con_spaces)
    drop_mil  = total_mil // 5
    drop_con  = total_con // 5

    removed = 0

    # Indians choose first Militia & Continental – pick colony with **highest** Patriot Support
    if drop_mil and mil_spaces:
        sid = max(mil_spaces, key=lambda t: state["support"].get(t[0], 0))[0]
        if state["spaces"][sid].get(MILITIA_U, 0):
            remove_piece(state, MILITIA_U, sid, 1, to="available")
        else:
            remove_piece(state, MILITIA_A, sid, 1, to="available")
        push_history(state, f"Patriot Desertion – Indians chose Militia in {sid}")
        drop_mil -= 1
        removed += 1

    if drop_con and con_spaces:
        sid = max(con_spaces, key=lambda t: state["support"].get(t[0], 0))[0]
        remove_piece(state, REGULAR_PAT, sid, 1, to="available")
        push_history(state, f"Patriot Desertion – Indians chose Continental in {sid}")
        drop_con -= 1
        removed += 1

    # Patriots remove the rest: Underground Militia → Active Militia → Continentals
    for sid, sp in state["spaces"].items():
        if sp.get("type") != "Colony":
            continue
        if drop_mil:
            q = min(sp.get(MILITIA_U, 0), drop_mil)
            if q:
                remove_piece(state, MILITIA_U, sid, q, to="available")
                drop_mil -= q; removed += q
            q = min(sp.get(MILITIA_A, 0), drop_mil)
            if q:
                remove_piece(state, MILITIA_A, sid, q, to="available")
                drop_mil -= q; removed += q
        if drop_con:
            q = min(sp.get(REGULAR_PAT, 0), drop_con)
            if q:
                remove_piece(state, REGULAR_PAT, sid, q, to="available")
                drop_con -= q; removed += q
        if drop_mil == 0 and drop_con == 0:
            break

    if removed:
        push_history(state, f"Patriot Desertion – {removed} pieces removed (6.6.1)")

def _tory_desertion(state):
    """Remove 1‑in‑5 Tories (round down).

    • **French** choose the *first* Tory to desert.
    • **British** choose the remainder (engine removes arbitrarily).
    """
    tory_spaces = [(sid, sp.get(TORY, 0)) for sid, sp in state["spaces"].items() if sp.get(TORY,0)]
    total = sum(c for _, c in tory_spaces)
    drop = total // 5
    if drop == 0:
        return

    removed = 0
    # French choose first Tory – colony with highest Patriot Support
    sid_choice = max(tory_spaces, key=lambda t: state["support"].get(t[0], 0))[0]
    remove_piece(state, TORY, sid_choice, 1, to="available")
    push_history(state, f"Tory Desertion – French chose Tory in {sid_choice}")
    drop -= 1; removed += 1

    # British remove the rest – iterate
    for sid, sp in state["spaces"].items():
        if drop == 0:
            break
        q = min(sp.get(TORY, 0), drop)
        if q:
            remove_piece(state, TORY, sid, q, to="available")
            drop -= q; removed += q

    if removed:
        push_history(state, f"Tory Desertion – {removed} cubes removed (6.6.2)")

# ────────────────────────────────────────────────────────────────
#  6.7  Reset Phase  – **NEW**
# ────────────────────────────────────────────────────────────────

def _reset_phase(state):
    """Rule 6.7 – prepare map & deck for the next card."""

    # Remove all Raid & Propaganda markers (support both marker-map and per-space storage)
    markers = state.setdefault("markers", {})
    for tag in (RAID, PROPAGANDA):
        entry = markers.setdefault(tag, {"pool": 0, "on_map": set()})
        on_map = entry.get("on_map", set())
        if not isinstance(on_map, set):
            on_map = set(on_map or [])

        removed = 0

        # If markers are stored directly in spaces (e.g., sp["Raid"]=1), remove them and count them.
        for sid, sp in state.get("spaces", {}).items():
            if not isinstance(sp, dict):
                continue
            if tag in sp:
                cnt = int(sp.get(tag, 0) or 0)
                sp.pop(tag, None)          # TESTS EXPECT KEY TO BE GONE
                if cnt > 0:
                    removed += cnt
                on_map.discard(sid)        # avoid double-count if also tracked in markers.on_map

        # If markers are tracked via markers[tag]["on_map"], remove 1 per remaining sid.
        removed += len(on_map)

        entry["pool"] = int(entry.get("pool", 0) or 0) + removed
        entry["on_map"] = set()

    # Mark all factions Eligible (§6.7 step 2)
    state["eligible"] = {BRITISH: True, PATRIOTS: True, FRENCH: True, INDIANS: True}

    # Move cubes from the Casualties box to Available (§6.7 step 3)
    lift_casualties(state)

    # Flip Militia & War Parties to Underground (§6.7 step 4)
    for sp in state["spaces"].values():
        if sp.get(MILITIA_A):
            sp[MILITIA_U] = sp.get(MILITIA_U, 0) + sp[MILITIA_A]
            sp[MILITIA_A] = 0
        if sp.get(WARPARTY_A):
            sp[WARPARTY_U] = sp.get(WARPARTY_U, 0) + sp[WARPARTY_A]
            sp[WARPARTY_A] = 0

    # Reveal next Ops card (§6.7 step 5)
    deck = state.get("deck", [])
    if deck and state.get("upcoming_card") is None:
        state["upcoming_card"] = deck.pop(0)
        _uc = state["upcoming_card"]
        _title = _uc.get("title") or _uc.get("name") or f"Card {_uc.get('id')}"
        push_history(state, f"Reset – revealed card {_title}")

    # Resolve WQ card event (§6.7 step 6)
    wq_event = state.pop("winter_card_event", None)
    if callable(wq_event):
        wq_event(state)
        push_history(state, "Reset – Winter‑Quarters event executed")

    push_history(state, "Reset Phase complete (6.7)")




# ────────────────────────────────────────────────────────────────
#  Public entry‑point
# ────────────────────────────────────────────────────────────────

def resolve(state):
    """Run the full Winter‑Quarters routine on *state* in rule‑order."""

    # 6.1  Victory Check Phase
    if victory_check(state):
        push_history(state, "Victory achieved at Winter-Quarters (6.1)")
        return  # game ends immediately

    # Return all Leaders to Available before redeploy (Rule 6.1)
    return_leaders(state)

    # 6.2
    _supply_phase(state)

    # 6.3
    _resource_income(state)

    # 6.4
    _support_phase(state)


    # ── Final steps ───────────────────────────────────────────
    if state.get("final_winter_round", False):
        # 6.4.3 was the last phase; go straight to end-of-game scoring (Rule 7.3)
        push_history(state, "Final Winter-Quarters card – Support Phase complete")
        final_scoring(state)
        return

    # 6.5  Redeployment Phase
    _leader_change(state)
    _leader_redeploy(state)
    _british_release(state)
    _fni_drift(state)

    # 6.6  Desertion Phase — unconditional per §6.6
    _patriot_desertion(state)
    _tory_desertion(state)

    # 6.7  Reset Phase
    _reset_phase(state)
    push_history(state, "Winter-Quarters routine complete")
