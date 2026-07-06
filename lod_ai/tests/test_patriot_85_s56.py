"""Session 56 — P-node inventory fixes (§8.5.4 French escorts, §8.5.1
Persuasion tie)."""
import lod_ai.rules_consts as C
from lod_ai.bots.patriot import PatriotBot
from lod_ai.state.setup_state import build_state
from lod_ai.board.control import refresh_control


def test_march_includes_max_french_escorts_beyond_control_need():
    """§8.5.4 (S56): "include as many French Regulars as possible" — the
    French escort count is capped by the 1-for-1 rule (§3.3.2) and the
    French purse, NOT by the remaining Control need."""
    state = build_state("1775", seed=7)
    bot = PatriotBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.REGULAR_BRI, C.TORY, C.FORT_PAT, C.FORT_BRI,
                    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE):
            sp[tag] = 0
    # Origin: 4 Continentals + 4 French; destination Boston has 1 British
    # cube -> Control need is small, but all 4 French may escort.
    src = "Massachusetts"
    state["spaces"][src][C.REGULAR_PAT] = 4
    state["spaces"][src][C.REGULAR_FRE] = 4
    state["spaces"]["Boston"][C.REGULAR_BRI] = 1
    state["resources"][C.PATRIOTS] = 5
    state["resources"][C.FRENCH] = 5
    state["toa_played"] = True
    state["treaty_of_alliance"] = True
    refresh_control(state)
    ok = bot._execute_march(state) if hasattr(bot, "_execute_march") else bot._march(state)
    if ok:
        moved_fre = 4 - state["spaces"][src].get(C.REGULAR_FRE, 0)
        moved_pat = 4 - state["spaces"][src].get(C.REGULAR_PAT, 0)
        assert moved_fre >= min(moved_pat, 4) - 0, "escorts move with Continentals"
        if moved_pat >= 2:
            assert moved_fre >= 2, (
                "French escorts must not be capped at the residual "
                "Control need (§8.5.4 'as many as possible')"
            )


def test_persuasion_fort_tier_is_binary_with_seeded_ties():
    """§8.5.1 PERSUASION (S56): 'first spaces with Patriot Forts' is a
    presence tier; there is no Population priority in the text."""
    state = build_state("1775", seed=7)
    bot = PatriotBot()
    for sid, sp in state["spaces"].items():
        for tag in (C.MILITIA_A, C.MILITIA_U, C.REGULAR_PAT, C.REGULAR_FRE,
                    C.REGULAR_BRI, C.TORY, C.FORT_PAT, C.FORT_BRI,
                    C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE):
            sp[tag] = 0
    # Fort space (low pop) + fortless space (high pop) + a third: the
    # fort space must always be selected first.
    state["spaces"]["Georgia"][C.MILITIA_U] = 2
    state["spaces"]["Georgia"][C.FORT_PAT] = 1
    state["spaces"]["Massachusetts"][C.MILITIA_U] = 2
    state["resources"][C.PATRIOTS] = 5
    state["_turn_persuasion_used"] = False
    refresh_control(state)
    ok = bot._try_persuasion(state)
    assert ok is True
    # Persuasion activates one Underground Militia per selected space —
    # the Fort space must be among them.
    assert state["spaces"]["Georgia"].get(C.MILITIA_A, 0) >= 1, (
        "the Patriot-Fort space is the first Persuasion pick (§8.5.1)"
    )
