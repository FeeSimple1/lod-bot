"""Tests for the LLM harness: an LLM (here, offline policies) playing Liberty or
Death as a human faction against the bots."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.cli_utils as U
import lod_ai.commands.battle as battle_cmd
from lod_ai import rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.llm import run_game, serialize_state
from lod_ai.llm.policy import (
    RandomPolicy, ScriptedPolicy, FirstChoicePolicy, _valid_choices,
)
from lod_ai.llm.provider import LLMInputProvider


# --------------------------------------------------------------------------- #
# Policy / menu helpers
# --------------------------------------------------------------------------- #
def test_valid_choices_select_and_count():
    sel = {"kind": "select", "options": ["a", "b", "c"], "allow_back": True}
    assert _valid_choices(sel) == ["1", "2", "3", "0"]
    cnt = {"kind": "count", "min": 0, "max": 3}
    assert _valid_choices(cnt) == ["0", "1", "2", "3"]
    assert _valid_choices(None) == []


def test_random_policy_returns_legal_choice():
    pol = RandomPolicy(seed=1)
    menu = {"kind": "select", "options": ["x", "y"], "allow_back": False}
    for _ in range(20):
        assert pol.choose("obs", "Select:", menu, "PATRIOTS") in {"1", "2"}


def test_scripted_then_fallback():
    pol = ScriptedPolicy(["2"], fallback="1")
    menu = {"kind": "select", "options": ["x", "y", "z"], "allow_back": False}
    assert pol.choose("o", "p", menu, "PATRIOTS") == "2"      # scripted
    assert pol.choose("o", "p", menu, "PATRIOTS") == "1"      # fallback -> 1st legal


def test_first_choice_policy():
    menu = {"kind": "count", "min": 2, "max": 5}
    assert FirstChoicePolicy().choose("o", "p", menu, None) == "2"


# --------------------------------------------------------------------------- #
# Observation serializer
# --------------------------------------------------------------------------- #
def test_serialize_state_contains_key_sections():
    st = build_state("1775", seed=1)
    text = serialize_state(st, C.PATRIOTS)
    assert "CURRENT CARD" in text
    assert "Victory margins" in text
    assert "YOU ARE PLAYING: PATRIOTS" in text
    assert "Boston" in text  # a real space appears in the board dump


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
def test_provider_routes_to_policy_and_retry_guard():
    st = build_state("1778", seed=1)

    class _Engine:
        def __init__(self, s):
            self.state = s

    eng = _Engine(st)
    # A deliberately broken policy that always returns an illegal answer.
    class _Bad:
        def choose(self, obs, label, menu, faction):
            return "999"
    prov = LLMInputProvider(_Bad(), eng, [C.PATRIOTS], max_retries=5)
    prov.begin_turn(C.PATRIOTS, {}, {})
    menu = {"kind": "select", "options": ["a", "b"], "allow_back": False}
    # Repeating the same prompt eventually trips the safety valve and returns a
    # guaranteed-legal first option instead of looping forever.
    out = None
    for _ in range(6):
        out = prov.prompt("Select:", menu)
    assert out == "1"


# --------------------------------------------------------------------------- #
# End-to-end games
# --------------------------------------------------------------------------- #
def test_full_short_game_with_random_policy_completes():
    r = run_game("1778", seed=3, llm_factions=["PATRIOTS"],
                 policy=RandomPolicy(11), quiet=True)
    assert r["cards_played"] > 0
    assert r["winner"] is not None
    # Globals restored so we don't leak into other tests.
    assert isinstance(U.get_input_provider(), U.StdinInputProvider)
    assert battle_cmd._DEFENDER_ACTIVATION_HOOK is None


def test_capped_game_makes_decisions_and_seats_llm():
    r = run_game("1778", seed=1, llm_factions=["PATRIOTS", "FRENCH"],
                 policy=RandomPolicy(5), max_cards=5, quiet=True)
    assert r["cards_played"] == 5
    assert r["human_factions"] == ["FRENCH", "PATRIOTS"]
    assert r["decisions"] >= 1


def test_random_policy_is_seed_deterministic():
    a = run_game("1778", seed=2, llm_factions=["PATRIOTS"],
                 policy=RandomPolicy(99), max_cards=10, quiet=True)
    b = run_game("1778", seed=2, llm_factions=["PATRIOTS"],
                 policy=RandomPolicy(99), max_cards=10, quiet=True)
    assert a["winner"] == b["winner"]
    assert a["cards_played"] == b["cards_played"]
    assert a["decisions"] == b["decisions"]


# --------------------------------------------------------------------------- #
# Winner detection
# --------------------------------------------------------------------------- #
def test_detect_winner_resolves_wq_victory_to_faction():
    """A mid-game Winter-Quarters victory (6.1) logs no faction name; the
    harness must recompute the winner from victory margins, not return the
    raw history message."""
    from lod_ai.llm.harness import _detect_winner

    st = build_state("1778", seed=1)
    st.setdefault("history", []).append(
        {"msg": "Victory achieved at Winter-Quarters (6.1)"})
    w = _detect_winner(st)
    assert w in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS, "UNKNOWN")
    assert "Victory achieved" not in (w or "")


def test_detect_winner_parses_explicit_winner_message():
    from lod_ai.llm.harness import _detect_winner

    st = {"history": [{"msg": "Winner: PATRIOTS (Rule 7.3)"}]}
    assert _detect_winner(st) == "PATRIOTS"


# --------------------------------------------------------------------------- #
# Heuristic policies
# --------------------------------------------------------------------------- #
def test_choose_count_impossible_range_does_not_prompt():
    """max < min (e.g. 'place >=1' with 0 available) must not loop forever."""
    class _Boom:
        def prompt(self, label, menu):
            raise AssertionError("prompt should not be called for empty range")
    U.set_input_provider(_Boom())
    try:
        assert U.choose_count("Place how many?", min_val=1, max_val=0) == 0
    finally:
        U.set_input_provider(None)


def test_heuristic_profiles_play_games():
    from lod_ai.llm.heuristic import HeuristicPolicy, PROFILES

    for name in ("P-AGIT", "B-CITY", "F-PREP", "I-VILLAGE"):
        prof = PROFILES[name]
        r = run_game("1778", seed=1, llm_factions=[prof["faction"]],
                     policy=HeuristicPolicy(prof), max_cards=3)
        assert r["cards_played"] >= 1
        assert r["decisions"] >= 0


def test_heuristic_parse_board_roundtrip():
    from lod_ai.llm.heuristic import parse_board

    st = build_state("1775", seed=1)
    text = serialize_state(st, C.PATRIOTS)
    board = parse_board(text)
    assert board, "parser should find occupied spaces"
    sample = next(iter(board.values()))
    assert {"support", "control", "pieces", "rebel", "crown"} <= set(sample)


# --------------------------------------------------------------------------- #
# Fixes from the four-human-seat external playtest report
# --------------------------------------------------------------------------- #
def test_human_french_can_declare_treaty_of_alliance():
    """An all-human game must be able to bring ToA into play: the engine now
    prompts human seats for Brilliant Stroke declarations (via the input
    provider) before the 1st Eligible acts."""
    from lod_ai.engine import Engine
    from lod_ai.cards.effects import brilliant_stroke as bs

    st = build_state("1775", seed=1)
    # Make ToA legal: Preparations > 15 (Available French Regulars + naval
    # + CBC) and eligibility.
    st["available"][C.REGULAR_FRE] = 14
    st["cbc"] = 5
    eng = Engine(initial_state=st)
    eng.set_human_factions({C.FRENCH})
    assert bs.preparations_total(eng.state) > 15

    class _DeclareFirst:
        def prompt(self, label, menu):
            return "1"          # first option = Declare Treaty of Alliance
    U.set_input_provider(_DeclareFirst())
    try:
        fired = eng._resolve_brilliant_stroke_interrupt(
            {"id": 999, "title": "dummy", "winter_quarters": False})
    finally:
        U.set_input_provider(None)
    assert fired, "ToA declaration should fire the BS interrupt"
    assert eng.state.get("toa_played"), "Treaty of Alliance must be in play"


def test_battle_candidates_are_side_aware():
    """An allied Indian Village must not make a space a British Battle
    target (previously caused committed 0-0 battles)."""
    from lod_ai.interactive_cli import _battle_candidates

    st = build_state("1775", seed=1)
    for sp in st["spaces"].values():        # clear the board
        for k in list(sp):
            if isinstance(sp[k], int):
                sp[k] = 0
    st["spaces"]["Quebec"][C.REGULAR_BRI] = 2
    st["spaces"]["Quebec"][C.VILLAGE] = 1   # allied Crown piece only
    assert "Quebec" not in _battle_candidates(st, C.BRITISH)
    st["spaces"]["Quebec"][C.MILITIA_U] = 1  # now a real Rebel target
    assert "Quebec" in _battle_candidates(st, C.BRITISH)
    # And the mirror: Patriots don't see French Regulars as targets.
    st["spaces"]["Boston"][C.MILITIA_U] = 1
    st["spaces"]["Boston"][C.REGULAR_FRE] = 2
    assert "Boston" not in _battle_candidates(st, C.PATRIOTS)


def test_tory_only_muster_is_legal():
    """§3.2.1 'place up to six Regulars' includes zero: British Muster with
    regular_plan=None (no Regulars Available) must execute the Tory step."""
    from lod_ai.commands import muster

    st = build_state("1775", seed=1)
    st["resources"][C.BRITISH] = 5
    sid = "New_York_City"
    st["spaces"].setdefault(sid, {})[C.REGULAR_BRI] = \
        st["spaces"][sid].get(C.REGULAR_BRI, 0) + 1
    before = st["spaces"][sid].get(C.TORY, 0)
    muster.execute(st, C.BRITISH, {}, [sid], regular_plan=None,
                   tory_plan={sid: 1})
    assert st["spaces"][sid].get(C.TORY, 0) == before + 1


def test_preparer_regulars_rejected_when_pool_empty():
    from lod_ai.special_activities import preparer
    import pytest as _pytest

    st = build_state("1775", seed=1)
    st["unavailable"][C.REGULAR_FRE] = 0
    with _pytest.raises(ValueError):
        preparer.execute(st, C.FRENCH, {}, choice="REGULARS")


def test_per_faction_policies_are_routed():
    """run_game(policies={...}) must dispatch each faction's prompts to its
    own policy object."""
    seen = {}

    class _Tagged(RandomPolicy):
        def __init__(self, tag):
            super().__init__(seed=1)
            self.tag = tag
        def choose(self, obs, label, menu, faction):
            seen.setdefault(self.tag, set()).add(faction)
            return super().choose(obs, label, menu, faction)

    run_game("1778", seed=1,
             llm_factions=["BRITISH", "PATRIOTS"],
             policies={"BRITISH": _Tagged("B"), "PATRIOTS": _Tagged("P")},
             max_cards=6)
    assert seen.get("B", set()) <= {C.BRITISH}
    assert seen.get("P", set()) <= {C.PATRIOTS}
    assert seen.get("B") and seen.get("P")
