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
    remove_piece, place_with_caps, return_leaders, lift_casualties, flip_pieces
)
import lod_ai.board.pieces as bp
from lod_ai.board import control as board_control
from lod_ai.map import adjacency as map_adj
from lod_ai.util import caps as caps_util
from lod_ai.economy import resources
from lod_ai.economy.resources import add as add_res
from lod_ai.cards.effects.shared import adjust_fni, shift_support
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

def _supply_phase(state, *, bots=None, human_factions=None):
    def _pay(faction, sid, tag):
        if resources.can_afford(state, faction, 1):
            resources.spend(state, faction, 1)
            push_history(state, f"{tag} – paid 1 Resource ({sid})")
            return True
        return False

    def _control_after(sid, removals):
        """Space control after hypothetically removing *removals*
        ({tag: n}) from *sid* — simulate, refresh, read (8.5.5/8.6.7/
        8.7.5 all key the pay decision on an actual control change)."""
        import copy
        st2 = {"spaces": copy.deepcopy(state["spaces"]),
               "control": dict(state.get("control", {}))}
        sp2 = st2["spaces"].get(sid, {})
        for tag, n in removals.items():
            sp2[tag] = max(0, sp2.get(tag, 0) - n)
        board_control.refresh_control(st2)
        return st2.get("control", {}).get(sid)

    def _rl_would_be_possible(sid, post_control):
        """6.4.1: Reward Loyalty needs British Control, a Regular AND a
        Tory in the space, and Support below Active."""
        sp = state["spaces"].get(sid, {})
        return (post_control == "BRITISH"
                and sp.get(REGULAR_BRI, 0) >= 1
                and sp.get(TORY, 0) >= 1
                and state.get("support", {}).get(sid, 0) < ACTIVE_SUPPORT)

    # British — collect unsupplied spaces, then sort by bot priority
    human = human_factions or set()
    brit_unsupplied = []
    for sid, sp in state["spaces"].items():
        if sid == WEST_INDIES_ID:
            continue
        if sp.get(REGULAR_BRI, 0) + sp.get(TORY, 0) == 0:
            continue
        meta = map_adj.space_meta(sid) or {}
        space_type = meta.get("type") or sp.get("type")
        if sp.get(FORT_BRI) or (space_type == "City" and state.get("control", {}).get(sid) == BRITISH):
            continue
        brit_unsupplied.append(sid)

    brit_pay_set = None
    if bots and BRITISH in bots and BRITISH not in human:
        bot = bots[BRITISH]
        priority = bot.bot_supply_priority(state)
        priority_index = {s: i for i, s in enumerate(priority)}
        brit_unsupplied.sort(key=lambda s: priority_index.get(s, 999))
        # Bot reference: "Pay only in spaces where removing British would
        # prevent Reward Loyalty or allow Committees of Correspondance,
        # first with Resources in highest Pop, then with shifts in highest
        # Pop."  Everywhere else the bot removes its cubes (6.2.1) instead
        # of bleeding Support with a shift.
        brit_pay_set = set(priority)

    for sid in brit_unsupplied:
        sp = state["spaces"][sid]
        worth_keeping = brit_pay_set is None or sid in brit_pay_set
        if worth_keeping and _pay(BRITISH, sid, "British Supply"):
            continue
        cur_support = state.get("support", {}).get(sid, 0)
        if worth_keeping and cur_support > ACTIVE_OPPOSITION:
            shift_support(state, sid, -1)
            continue
        if sp.get(REGULAR_BRI, 0):
            remove_piece(state, REGULAR_BRI, sid, sp[REGULAR_BRI], to="available")
        if sp.get(TORY, 0):
            remove_piece(state, TORY, sid, sp[TORY], to="available")
        push_history(state, f"British Supply – cubes removed from {sid}")

    # Patriots — collect unsupplied spaces, then sort by bot priority
    pat_unsupplied = []
    for sid, sp in state["spaces"].items():
        total = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0) + sp.get(REGULAR_PAT, 0)
        if not total:
            continue
        meta = map_adj.space_meta(sid) or {}
        space_type = meta.get("type") or sp.get("type")
        if sp.get(FORT_PAT) or ((space_type in ("Colony", "City")) and state.get("control", {}).get(sid) == "REBELLION"):
            continue
        pat_unsupplied.append(sid)

    # §8.5.5: pay ONLY where removing Patriot pieces (6.2.1: one per two
    # units, rounded down) would change Control — within those, first
    # where the British would otherwise be able to Reward Loyalty, then
    # most Villages, then highest Population. All OTHER unsupplied spaces
    # remove per 8.1.2 (cubes first, then Active before Underground).
    def _pat_removal(sid):
        sp = state["spaces"][sid]
        total = sp.get(MILITIA_A, 0) + sp.get(MILITIA_U, 0) + sp.get(REGULAR_PAT, 0)
        n = total // 2
        plan, left = {}, n
        for pid in (REGULAR_PAT, MILITIA_A, MILITIA_U):   # 8.1.2 friendly order
            take = min(state["spaces"][sid].get(pid, 0), left)
            if take:
                plan[pid] = take
                left -= take
        return plan

    pat_pay, pat_other = [], []
    for sid in pat_unsupplied:
        plan = _pat_removal(sid)
        before = state.get("control", {}).get(sid)
        after = _control_after(sid, plan)
        if plan and after != before:
            sp = state["spaces"][sid]
            key = (0 if _rl_would_be_possible(sid, after) else 1,
                   -sp.get(VILLAGE, 0),
                   -(map_adj.population(sid)))
            pat_pay.append((key, sid))
        else:
            pat_other.append(sid)
    pat_pay.sort()

    def _pat_remove(sid):
        for pid, qty in _pat_removal(sid).items():
            remove_piece(state, pid, sid, qty, to="available")
        push_history(state, f"Patriot Supply – units removed from {sid}")

    for _, sid in pat_pay:
        if not _pay(PATRIOTS, sid, "Patriot Supply"):
            _pat_remove(sid)               # 6.2.1: can't pay → remove
    for sid in pat_other:
        _pat_remove(sid)

    # French — collect unsupplied spaces, then sort by bot priority
    fre_unsupplied = []
    for sid, sp in state["spaces"].items():
        fr = sp.get(REGULAR_FRE, 0)
        if fr == 0 or sid == WEST_INDIES_ID:
            continue

        stype = map_adj.space_type(sid)
        in_supply = (sp.get(FORT_PAT)
                     or (stype in ("Colony", "City")
                         and state.get("control", {}).get(sid) == "REBELLION"))
        if in_supply:
            continue
        fre_unsupplied.append(sid)

    # §8.6.7: pay ONLY where moving the French Regulars out would change
    # Control — within those, first where the British would otherwise be
    # able to Reward Loyalty, then highest Population. All OTHER
    # unsupplied spaces move to the nearest Patriot Fort (or, if none,
    # to Available). 6.2.1: can't pay → move.
    fre_pay, fre_other = [], []
    for sid in fre_unsupplied:
        fr = state["spaces"][sid].get(REGULAR_FRE, 0)
        before = state.get("control", {}).get(sid)
        after = _control_after(sid, {REGULAR_FRE: fr})
        if after != before:
            key = (0 if _rl_would_be_possible(sid, after) else 1,
                   -(map_adj.population(sid)))
            fre_pay.append((key, sid))
        else:
            fre_other.append(sid)
    fre_pay.sort()

    def _fre_move_out(sid):
        fr = state["spaces"][sid].get(REGULAR_FRE, 0)
        forts = [s for s, sp2 in state["spaces"].items()
                 if sp2.get(FORT_PAT) and s != sid]
        if forts:
            dists = {s: len(map_adj.shortest_path(sid, s)) for s in forts}
            best = min(dists.values())
            ties = sorted(s for s, d in dists.items() if d == best)
            rng = state.get("rng")
            dest = (ties[rng.randrange(len(ties))]
                    if rng is not None and len(ties) > 1 else ties[0])
            bp.move_piece(state, REGULAR_FRE, sid, dest, fr)
            push_history(state, f"French Supply – moved {fr} regs {sid}→{dest}")
        else:
            bp.remove_piece(state, REGULAR_FRE, sid, fr)
            push_history(state, f"French Supply – {fr} regs to Available ({sid})")

    for _, sid in fre_pay:
        if not _pay(FRENCH, sid, "French Supply"):
            _fre_move_out(sid)
    for sid in fre_other:
        _fre_move_out(sid)

    # Indians – auto‑Village
    if not any(sp.get(VILLAGE, 0) for sp in state["spaces"].values()):
        reserve = next((s for s in state["spaces"] if map_adj.space_type(s) == "Reserve"), None)
        if reserve:
            place_with_caps(state, VILLAGE, reserve, 1)
            push_history(state, f"Indian Supply – auto‑Village in {reserve}")

    indian_unsupplied = []
    for sid, sp in state["spaces"].items():
        wp_total = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
        if not wp_total:
            continue
        if sp.get(VILLAGE) or map_adj.space_type(sid) == "Reserve":
            continue
        indian_unsupplied.append(sid)

    # §8.7.5: pay FIRST where moving the War Parties out would ADD
    # Rebellion Control, THEN where Gather could place a Village (3.4.1:
    # room, 3+ War Parties — 2 with Cornplanter — Support among
    # Neutral/Passive). If Resources run out or NEITHER condition is
    # met, move the War Parties to the nearest Village space. Ties
    # within each bucket break randomly (8.2, seeded).
    from lod_ai.bots.random_spaces import pick_random_spaces
    from lod_ai.commands.gather import SUPPORT_OK as _GATHER_OK
    from lod_ai.leaders import leader_location as _leader_loc

    def _gather_village_possible(sid):
        sp = state["spaces"][sid]
        wp = sp.get(WARPARTY_A, 0) + sp.get(WARPARTY_U, 0)
        need = 2 if _leader_loc(state, "LEADER_CORNPLANTER") == sid else 3
        bases = (sp.get(VILLAGE, 0) + sp.get(FORT_BRI, 0)
                 + sp.get(FORT_PAT, 0))
        return (state.get("available", {}).get(VILLAGE, 0) > 0
                and wp >= need and bases < 2
                and state.get("support", {}).get(sid, 0) in _GATHER_OK)

    ind_pay_a, ind_pay_b, ind_other = [], [], []
    for sid in indian_unsupplied:
        sp = state["spaces"][sid]
        wp = {WARPARTY_A: sp.get(WARPARTY_A, 0),
              WARPARTY_U: sp.get(WARPARTY_U, 0)}
        before = state.get("control", {}).get(sid)
        after = _control_after(sid, wp)
        if after == "REBELLION" and before != "REBELLION":
            ind_pay_a.append(sid)
        elif _gather_village_possible(sid):
            ind_pay_b.append(sid)
        else:
            ind_other.append(sid)
    ordered_pay = (pick_random_spaces(state, ind_pay_a, len(ind_pay_a))
                   + pick_random_spaces(state, ind_pay_b, len(ind_pay_b)))

    def _ind_move_out(sid):
        sp = state["spaces"][sid]
        dests = [d for d, sp2 in state["spaces"].items()
                 if sp2.get(VILLAGE) and d != sid]
        if not dests:
            return
        dists = {d: len(map_adj.shortest_path(sid, d)) for d in dests}
        best = min(dists.values())
        ties = sorted(d for d, dv in dists.items() if dv == best)
        rng = state.get("rng")
        dest = (ties[rng.randrange(len(ties))]
                if rng is not None and len(ties) > 1 else ties[0])
        for pid in (WARPARTY_U, WARPARTY_A):
            qty = sp.get(pid, 0)
            if qty:
                remove_piece(state, pid, sid, qty, to="available")
                place_with_caps(state, pid, dest, qty)
        push_history(state, f"Indian Supply – War Parties moved {sid} ➜ {dest}")

    for sid in ordered_pay:
        if not _pay(INDIANS, sid, "Indian Supply"):
            _ind_move_out(sid)
    for sid in ind_other:
        _ind_move_out(sid)

    # Refresh & caps
    board_control.refresh_control(state)
    caps_util.enforce_global_caps(state)

    # West Indies battle + garrison payment
    wi = state["spaces"][WEST_INDIES_ID]
    if wi.get(REGULAR_FRE) and wi.get(REGULAR_BRI) and state.get("toa_played", False):
        # Manual §6.2.2: "French must conduct a *free* Battle in the West
        # Indies."  Without free=True, battle.execute() charges 1 Resource
        # and crashes the game whenever French Resources == 0.
        battle_execute(state, FRENCH, {}, [WEST_INDIES_ID], free=True)
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
    """Rule 6.4 - British then Patriots may spend Resources to adjust
    Support or Opposition.

    British (Reward Loyalty) and Patriots (Committees of Correspondence)
    act in that order.  §6.4.1 and §6.4.2 each cap their own shifts at
    two levels per space — the caps are per activity, NOT shared
    (Session 45: a single counter was shared between RL and CoC).
    Spaces are sorted per bot priority rules (8.4.5 / 8.5.9) and
    skipped if only markers would be removed.
    """

    from collections import defaultdict

    rl_shifted = defaultdict(int)    # §6.4.1: max two levels per space
    coc_shifted = defaultdict(int)   # §6.4.2: separate two-level cap
    rng = state.get("rng")
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

    # Build sorted list of eligible spaces per §8.4.5:
    # "first select the space or spaces with the lowest total of Raid
    #  and Propaganda markers, within that where the largest change in
    #  (Support – Opposition) is possible."
    brit_eligible = []
    bri_res = state.get("resources", {}).get(BRITISH, 0)
    for sid, sp in state["spaces"].items():
        if rl_shifted[sid] >= 2:
            continue
        if not (_ctrl(sid, sp) == BRITISH and sp.get(REGULAR_BRI) and sp.get(TORY)):
            continue
        level = state["support"].get(sid, 0)
        if level >= ACTIVE_SUPPORT:
            continue

        n_raid = 1 if sid in raid_on_map else 0
        n_prop = 1 if sid in propaganda_on_map else 0
        marker_count = n_raid + n_prop
        pop = map_adj.population(sid)
        # §8.4.5 "largest change ... possible": §6.4.1 caps shifts at two
        # levels per space, and the purse must pay the markers first
        # (Session 45: was the raw uncapped distance).
        levels = min(ACTIVE_SUPPORT - level, 2,
                     max(0, bri_res - marker_count))
        potential = levels * pop

        # Attach sort keys for this pass (§8.2 seeded tie-break)
        brit_eligible.append((sid, marker_count, potential,
                              rng.random() if rng else 0.0))

    # §8.4.5: fewest markers first, then largest population-weighted change
    brit_eligible.sort(key=lambda x: (x[1], -x[2], x[3]))

    spent = 0
    for sid, _mc, _pot, _tb in brit_eligible:
        sp = state["spaces"][sid]
        if rl_shifted[sid] >= 2:
            continue

        level = state["support"].get(sid, 0)
        if level >= ACTIVE_SUPPORT:
            continue
        steps_remaining = 2 - rl_shifted[sid]
        if steps_remaining <= 0:
            continue

        # §8.4.5: "Do not Reward Loyalty in a space if only Raid and/or
        # Propaganda markers would be removed."
        # Must be able to afford all marker removals PLUS at least 1 shift.
        n_raid = 1 if sid in raid_on_map else 0
        n_prop = 1 if sid in propaganda_on_map else 0
        min_cost = n_raid + n_prop + 1
        if not resources.can_afford(state, BRITISH, min_cost):
            continue

        # Remove Raid or Propaganda marker if present (costs 1 each)
        # Per §6.4.1: marker removal does NOT count against the 2-shift cap
        for marker_tag, on_map in ((RAID, raid_on_map), (PROPAGANDA, propaganda_on_map)):
            if not resources.can_afford(state, BRITISH, 1):
                break
            if sid in on_map:
                resources.spend(state, BRITISH, 1)
                remove_piece(state, marker_tag, sid, 1, to="available")
                push_history(state, f"British removed {marker_tag} in {sid} (6.4.1)")

        # pay 1 Resource per support shift, up to remaining steps
        while steps_remaining > 0 and resources.can_afford(state, BRITISH, 1) and level < ACTIVE_SUPPORT:
            resources.spend(state, BRITISH, 1)
            level += 1
            state["support"][sid] = level
            spent += 1
            rl_shifted[sid] += 1
            steps_remaining -= 1
            push_history(state, f"British shifted {sid} toward Active Support (6.4.1)")

    if spent:
        push_history(state, f"British spent {spent} Resources on Reward Loyalty (6.4.1)")

    # ---------------------------------------------------------------
    # 6.4.2  Committees of Correspondence  (Patriots)
    # ---------------------------------------------------------------

    # Build sorted list of eligible spaces per §8.5.9:
    # "first select the spaces with the lowest number of Raid markers,
    #  within that where the largest change in (Opposition - Support)
    #  is possible."
    pat_eligible = []
    pat_res = state.get("resources", {}).get(PATRIOTS, 0)
    for sid, sp in state["spaces"].items():
        if coc_shifted[sid] >= 2:
            continue
        # §6.4.2: "Rebellion Controlled spaces with Patriot pieces" — a
        # Patriot Fort is a Patriot piece (Session 45: Fort-only spaces
        # were excluded).
        if not (_ctrl(sid, sp) == "REBELLION"
                and (sp.get(MILITIA_A) or sp.get(MILITIA_U)
                     or sp.get(REGULAR_PAT) or sp.get(FORT_PAT))):
            continue
        level = state["support"].get(sid, 0)
        if level <= ACTIVE_OPPOSITION:
            continue

        n_raid = 1 if sid in raid_on_map else 0
        pop = map_adj.population(sid)
        # §8.5.9 "largest change ... possible": §6.4.2 caps shifts at two
        # levels per space, and the purse must pay the Raid marker first
        # (Session 45: was the raw uncapped distance).
        levels = min(level - ACTIVE_OPPOSITION, 2,
                     max(0, pat_res - n_raid))
        potential = levels * pop

        pat_eligible.append((sid, n_raid, potential,
                             rng.random() if rng else 0.0))

    # §8.5.9: fewest Raid markers first, then largest population-weighted change
    pat_eligible.sort(key=lambda x: (x[1], -x[2], x[3]))

    spent = 0
    for sid, _nr, _pot, _tb in pat_eligible:
        sp = state["spaces"][sid]
        if coc_shifted[sid] >= 2:
            continue

        level = state["support"].get(sid, 0)
        if level <= ACTIVE_OPPOSITION:
            continue
        steps_remaining = 2 - coc_shifted[sid]
        if steps_remaining <= 0:
            continue

        # §8.5.9: "Do not execute Committees of Correspondence in a space
        # if only Raid markers would be removed."
        # Must be able to afford marker removal PLUS at least 1 shift.
        n_raid = 1 if sid in raid_on_map else 0
        min_cost = n_raid + 1
        if not resources.can_afford(state, PATRIOTS, min_cost):
            continue

        # remove Raid markers first (cost 1 each)
        # Per §6.4.2: marker removal does NOT count against the 2-shift cap
        if sid in raid_on_map and resources.can_afford(state, PATRIOTS, 1):
            resources.spend(state, PATRIOTS, 1)
            remove_piece(state, RAID, sid, 1, to="available")
            push_history(state, f"Patriots removed Raid in {sid} (6.4.2)")

        # pay 1 Resource per shift toward Opposition
        while steps_remaining > 0 and resources.can_afford(state, PATRIOTS, 1) and level > ACTIVE_OPPOSITION:
            resources.spend(state, PATRIOTS, 1)
            level -= 1
            state["support"][sid] = level
            spent += 1
            coc_shifted[sid] += 1
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

def _leader_redeploy(state, *, bots=None, human_factions=None):
    human = human_factions or set()
    order = [INDIANS, FRENCH, BRITISH, PATRIOTS]
    for fac in order:
        leader = state.get("leaders", {}).get(fac)
        if not leader:
            continue

        if bots and fac in bots and fac not in human:
            bot = bots[fac]
            if fac == INDIANS:
                deploy_map = bot.ops_redeploy(state)
                dest = deploy_map.get(leader)
            elif fac == BRITISH:
                dest = bot.bot_redeploy_leader(state)
            elif fac == PATRIOTS:
                dest = bot.ops_redeploy_washington(state)
            elif fac == FRENCH:
                dest = bot.ops_redeploy_leader(state)
            else:
                dest = None

            if dest:
                state.setdefault("leader_locs", {})[leader] = dest
                push_history(state, f"Leader Redeploy – {fac} leader to {dest} (6.5.2, bot)")
            else:
                state.setdefault("leader_locs", {})[leader] = "Available"
                push_history(state, f"Leader Redeploy – {fac} leader to Available (6.5.2)")
        else:
            # Human or no bot — existing generic logic
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
    """§6.5.3 British Release Date.

    Pop the next tranche from ``brit_release_schedule`` and move
    the specified Regulars *and* Tories from Unavailable to Available.
    If fewer pieces are in Unavailable than the schedule calls for,
    move only those that are present (per §6.5.3).
    """
    schedule = state.get("brit_release_schedule", [])
    if not schedule:
        return

    tranche = schedule.pop(0)
    if not tranche:
        return

    unavail = state.setdefault("unavailable", {})
    avail = state.setdefault("available", {})

    total_moved = 0
    for tag, qty in tranche.items():
        have = unavail.get(tag, 0)
        moved = min(qty, have)
        if moved:
            unavail[tag] = have - moved
            if unavail[tag] == 0:
                del unavail[tag]
            avail[tag] = avail.get(tag, 0) + moved
            total_moved += moved
            push_history(state, f"British Release – {moved} {tag} to Available (6.5.3)")

    if total_moved == 0:
        push_history(state, "British Release Date – nothing in Unavailable (6.5.3)")

# ────────────────────────────────────────────────────────────────
#  FNI drift & Blockade shuffle (§6.5.4)
# ────────────────────────────────────────────────────────────────

def _fni_drift(state, *, bots=None, human_factions=None):
    if not state.get("treaty_of_alliance", False):
        return  # only after ToA
    human = human_factions or set()

    # Lower FNI one box if > 0
    if state.get("fni_level", 0) > 0:
        adjust_fni(state, -1)
        push_history(state, "FNI drift – box shifts 1 toward War (6.5.4)")

    # Remove one Blockade from a City to the West Indies pool (§6.5.4)
    # §8.6.9: Bot French removes Blockade from City with LEAST Support.
    bloc = state.setdefault("markers", {}).setdefault(BLOCKADE, {"pool": 0, "on_map": set()})
    on_map = bloc.get("on_map", set())
    if on_map:
        if bots and FRENCH in bots and FRENCH not in human:
            # §8.6.9: Remove Blockade from City with least Support
            support_map = state.get("support", {})
            removed_city = min(on_map, key=lambda s: support_map.get(s, 0))
        else:
            removed_city = next(iter(on_map))
        on_map.discard(removed_city)
        bloc["pool"] = bloc.get("pool", 0) + 1
        push_history(state, f"Blockade removed from {removed_city} to West Indies (6.5.4)")

        # §8.6.9: Rearrange remaining Blockades to Cities with most Support
        if bots and FRENCH in bots and FRENCH not in human and on_map:
            _rearrange_blockades(state, on_map)
        elif on_map:
            push_history(state, "French may rearrange remaining Blockade markers (6.5.4)")


def _rearrange_blockades(state, on_map):
    """§8.6.9: Move remaining Blockades to Cities with most Support.

    Collect all remaining Blockades, then redistribute them to Cities
    sorted by descending Support level.  The on_map set stores one entry
    per blockaded city; each entry represents one blockade marker.
    """
    support_map = state.get("support", {})
    remaining = list(on_map)
    on_map.clear()

    if not remaining:
        return

    # Find all Cities (from map data)
    cities = [
        sid for sid in state.get("spaces", {})
        if (map_adj.space_meta(sid) or {}).get("type") == "City"
    ]
    if not cities:
        on_map.update(remaining)
        return

    # Sort cities by most Support (descending), break ties randomly
    cities.sort(key=lambda s: -support_map.get(s, 0))

    # Place each blockade in the highest-Support cities available.
    # Since on_map is a set (one blockade per city), distribute across
    # the top N cities where N = number of remaining blockades.
    n_blockades = len(remaining)
    for i in range(min(n_blockades, len(cities))):
        on_map.add(cities[i])
    push_history(state, f"French rearranged Blockades to {sorted(on_map)} (§8.6.9)")

# ────────────────────────────────────────────────────────────────
#  §6.6  Desertion helpers  (full Rule 6.6 logic)
# ────────────────────────────────────────────────────────────────

def _patriot_desertion(state, *, bots=None, human_factions=None):
    """Remove 1‑in‑5 Militia and 1‑in‑5 Continentals (round down).

    • **Indians** choose the *first* Militia **and** the *first* Continental to desert.
    • **Patriots** choose the remainder (engine removes least‑harmful pieces).
    """
    human = human_factions or set()

    # §6.6.1: "Remove 1 in 5 Militia and 1 in 5 Continentals from the map"
    mil_spaces = [(sid, sp.get(MILITIA_U, 0) + sp.get(MILITIA_A, 0))
                  for sid, sp in state["spaces"].items() if (sp.get(MILITIA_U,0)+sp.get(MILITIA_A,0))]
    con_spaces = [(sid, sp.get(REGULAR_PAT, 0))
                  for sid, sp in state["spaces"].items() if sp.get(REGULAR_PAT,0)]

    total_mil = sum(c for _, c in mil_spaces)
    total_con = sum(c for _, c in con_spaces)
    drop_mil  = total_mil // 5
    drop_con  = total_con // 5

    removed = 0

    # Indians choose first Militia & Continental
    if drop_mil and mil_spaces:
        if bots and INDIANS in bots and INDIANS not in human:
            # Build candidate list for Indian bot
            mil_candidates = [(s, MILITIA_U) for s, _ in mil_spaces
                              if state["spaces"][s].get(MILITIA_U, 0)]
            mil_candidates += [(s, MILITIA_A) for s, _ in mil_spaces
                               if state["spaces"][s].get(MILITIA_A, 0)]
            if mil_candidates:
                sorted_mil = bots[INDIANS].ops_patriot_desertion_priority(state, mil_candidates)
                sid, tag = sorted_mil[0]
            else:
                sid = mil_spaces[0][0]
                tag = MILITIA_U if state["spaces"][sid].get(MILITIA_U, 0) else MILITIA_A
        else:
            # Default: pick colony with highest Patriot Support
            sid = max(mil_spaces, key=lambda t: state["support"].get(t[0], 0))[0]
            tag = MILITIA_U if state["spaces"][sid].get(MILITIA_U, 0) else MILITIA_A
        remove_piece(state, tag, sid, 1, to="available")
        push_history(state, f"Patriot Desertion – Indians chose {tag} in {sid}")
        drop_mil -= 1
        removed += 1

    if drop_con and con_spaces:
        if bots and INDIANS in bots and INDIANS not in human:
            con_candidates = [(s, REGULAR_PAT) for s, _ in con_spaces]
            sorted_con = bots[INDIANS].ops_patriot_desertion_priority(state, con_candidates)
            sid, _ = sorted_con[0]
        else:
            sid = max(con_spaces, key=lambda t: state["support"].get(t[0], 0))[0]
        remove_piece(state, REGULAR_PAT, sid, 1, to="available")
        push_history(state, f"Patriot Desertion – Indians chose Continental in {sid}")
        drop_con -= 1
        removed += 1

    # Patriots remove the rest
    if bots and PATRIOTS in bots and PATRIOTS not in human and (drop_mil or drop_con):
        # §8.5.7: "Remove Militia and Continentals so as to change as
        # little Control as possible, within that first without removing
        # the last Patriot unit from any space."  Every removal changes
        # the Control margins and the last-unit test, so re-score the
        # priorities after each single piece (Session 45: the old loop
        # scored once and removed in bulk from the top-ranked space).
        while drop_mil > 0 or drop_con > 0:
            pat_removals = bots[PATRIOTS].ops_patriot_desertion_priority(state)
            pick = None
            for sid, tag in pat_removals:
                sp = state["spaces"].get(sid, {})
                if sp.get(tag, 0) <= 0:
                    continue
                if tag in (MILITIA_U, MILITIA_A) and drop_mil > 0:
                    pick = (sid, tag)
                    break
                if tag == REGULAR_PAT and drop_con > 0:
                    pick = (sid, tag)
                    break
            if pick is None:
                break
            sid, tag = pick
            remove_piece(state, tag, sid, 1, to="available")
            if tag == REGULAR_PAT:
                drop_con -= 1
            else:
                drop_mil -= 1
            removed += 1
    else:
        # Default: iterate spaces arbitrarily
        for sid, sp in state["spaces"].items():
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

def _tory_desertion(state, *, bots=None, human_factions=None):
    """Remove 1‑in‑5 Tories (round down).

    • **French** choose the *first* Tory to desert.
    • **British** choose the remainder (engine removes arbitrarily).
    """
    human = human_factions or set()

    tory_spaces = [(sid, sp.get(TORY, 0)) for sid, sp in state["spaces"].items() if sp.get(TORY,0)]
    total = sum(c for _, c in tory_spaces)
    drop = total // 5
    if drop == 0:
        return

    removed = 0

    # French choose first Tory
    if bots and FRENCH in bots and FRENCH not in human:
        french_picks = bots[FRENCH].ops_loyalist_desertion_priority(state)
        if french_picks:
            sid_choice, _ = french_picks[0]
        else:
            sid_choice = tory_spaces[0][0]
    else:
        # Default: colony with highest Patriot Support
        sid_choice = max(tory_spaces, key=lambda t: state.get("support", {}).get(t[0], 0))[0]

    remove_piece(state, TORY, sid_choice, 1, to="available")
    push_history(state, f"Tory Desertion – French chose Tory in {sid_choice}")
    drop -= 1; removed += 1

    # British remove the rest
    if bots and BRITISH in bots and BRITISH not in human and drop > 0:
        removals = bots[BRITISH].bot_loyalist_desertion(state, drop)
        for sid, n in removals:
            remove_piece(state, TORY, sid, n, to="available")
            removed += n
        drop = 0
    else:
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
    for sid, sp in state["spaces"].items():
        if sp.get(MILITIA_A):
            flip_pieces(state, MILITIA_A, MILITIA_U, sid, sp[MILITIA_A])
        if sp.get(WARPARTY_A):
            flip_pieces(state, WARPARTY_A, WARPARTY_U, sid, sp[WARPARTY_A])

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

def resolve(state, *, bots=None, human_factions=None):
    """Run the full Winter‑Quarters routine on *state* in rule‑order.

    Parameters
    ----------
    bots : dict | None
        Mapping of faction string → bot instance (e.g. {"BRITISH": BritishBot()}).
        When provided, bot-controlled factions use their OPS methods for
        Supply priority, Leader Redeploy, and Desertion choices.
    human_factions : set | None
        Set of faction strings controlled by humans.  These factions use the
        existing ad-hoc logic even when *bots* is provided.
    """

    # 6.1  Victory Check Phase
    if victory_check(state):
        push_history(state, "Victory achieved at Winter-Quarters (6.1)")
        return  # game ends immediately

    # Return all Leaders to Available before redeploy (Rule 6.1)
    return_leaders(state)

    # 6.2
    _supply_phase(state, bots=bots, human_factions=human_factions)

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
    _leader_redeploy(state, bots=bots, human_factions=human_factions)
    _british_release(state)
    _fni_drift(state, bots=bots, human_factions=human_factions)

    # 6.6  Desertion Phase — unconditional per §6.6
    _patriot_desertion(state, bots=bots, human_factions=human_factions)
    _tory_desertion(state, bots=bots, human_factions=human_factions)

    # 6.7  Reset Phase
    _reset_phase(state)
    push_history(state, "Winter-Quarters routine complete")


# ────────────────────────────────────────────────────────────────
#  Brilliant Stroke trigger check (§8.3.7)
# ────────────────────────────────────────────────────────────────

def check_bs_triggers(state, *, bots=None, human_factions=None):
    """Check whether any bot-controlled faction should trigger its
    Brilliant Stroke card per §8.4.11 / §8.5.8 / §8.6.11 / §8.7.8.

    Returns a dict mapping faction → True for each bot faction whose
    ``ops_bs_trigger(state)`` returns True.  Human factions are excluded.

    Callers (e.g. engine.py) should invoke this when a Brilliant Stroke
    card is drawn to determine which bots want to play it.
    """
    human = human_factions or set()
    triggers = {}
    if not bots:
        return triggers
    for faction, bot in bots.items():
        if faction in human:
            continue
        if hasattr(bot, "ops_bs_trigger") and bot.ops_bs_trigger(state):
            triggers[faction] = True
    return triggers
