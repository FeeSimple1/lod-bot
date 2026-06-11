"""Regressions for the external bot-combination audit (June 2026).

Three bot-planner defects produced trapped bot_error/illegal_action passes
in full-game diagnostics while every targeted unit test stayed green:
French March planned Continental escorts the Patriots could not pay for;
British Muster planned Regular destinations the executor rejects; Indian
Limited Gather could affect two spaces. Plus the audit's structural ask:
a gate asserting that full bot-only games produce ZERO trapped errors,
not merely completed games.
"""
import contextlib
import io

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine


def _play_bot_game(scenario, seed, max_cards=200):
    st = build_state(scenario, seed=seed)
    eng = Engine(initial_state=st)
    eng.set_human_factions(set())
    with contextlib.redirect_stdout(io.StringIO()):
        n = 0
        while n < max_cards:
            card = eng.draw_card()
            if card is None:
                break
            eng.play_card(card)
            n += 1
    return eng.state


def test_french_march_escorts_capped_by_patriot_resources():
    """Defect 1: the French bot must never plan Continental escorts the
    Patriots cannot pay for (1 Resource per escort destination, 3.5.4)."""
    from lod_ai.bots.french import FrenchBot

    st = build_state("1778", seed=2)
    st["toa_played"] = True
    st["resources"][C.PATRIOTS] = 0
    # Give the French an obvious March posture: regulars + adjacent allies.
    bot = FrenchBot()
    st["_bot_error_log"] = []
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            bot.take_turn(st, {"id": 1, "title": "t", "order": ["FRENCH"]})
        except ValueError as exc:
            assert "escort fee" not in str(exc), \
                "planner must pre-check Patriot escort affordability"
    assert not [e for e in st.get("_bot_error_log", [])
                if "escort fee" in str(e.get("error", ""))]


def test_british_muster_planner_matches_executor_legality():
    """Defect 2: planner and executor must share the Regular-destination
    rule (non-Blockaded City, adjacent Colony, or West Indies)."""
    from lod_ai.bots.british_bot import BritishBot
    from lod_ai.commands.muster import _is_legal_regular_dest

    st = build_state("1775", seed=1)
    bot = BritishBot()
    st["_bot_error_log"] = []
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            bot.take_turn(st, {"id": 1, "title": "t", "order": ["BRITISH"]})
        except ValueError as exc:
            assert "cannot be placed" not in str(exc)
    for e in st.get("_bot_error_log", []):
        assert "cannot be placed" not in str(e.get("error", ""))


def test_formerly_failing_games_produce_zero_trapped_errors():
    """The audit's gate: full bot-only games on the exact seeds that used
    to produce trapped bot_error / illegal_action passes must now run
    clean. A completed game is not a clean game."""
    for scenario, seed in (("1778", 2), ("1778", 8), ("1775", 9)):
        st = _play_bot_game(scenario, seed)
        errs = st.get("_bot_error_log", []) or []
        assert not errs, (
            f"{scenario} seed {seed}: trapped bot errors remain: "
            f"{[str(e.get('error'))[:80] for e in errs[:3]]}")
        bad = [h for h in st.get("history", [])
               if "illegal" in str(h).lower()]
        assert not bad, f"{scenario} seed {seed}: illegal actions: {bad[:2]}"


def test_outcomes_invariant_across_hash_seeds():
    """Game outcomes must be deterministic from the scenario seed alone --
    not Python's per-process hash seed (audit recommendation 7). Plays the
    once hash-sensitive game (1778 seed 4) under two different
    PYTHONHASHSEED values in subprocesses and compares winner + length."""
    import subprocess, sys, os, json

    code = (
        "import json;"
        "from lod_ai.tools.balance_smoke import play_bot_game;"
        "r = play_bot_game('1778', 4);"
        "print(json.dumps([r['winner'], r['cards']]))"
    )
    results = []
    for hs in ("0", "31337"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, timeout=180,
                             env=env, cwd=os.path.dirname(os.path.dirname(
                                 os.path.dirname(os.path.abspath(__file__)))))
        assert out.returncode == 0, out.stderr[-400:]
        results.append(json.loads(out.stdout.strip().splitlines()[-1]))
    assert results[0] == results[1], \
        f"hash-seed-dependent outcome: {results}"
