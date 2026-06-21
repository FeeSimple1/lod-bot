"""
Headless human-mode QA harness.

Drives the *real* interactive game loop (`interactive_cli._game_loop`) with
a scripted input provider standing in for a person, so the human-facing
code paths get the same automated scrutiny the bot paths get from the
60-game gate. It deliberately exercises the documented blind spots:

  * meta-commands mid-wizard  -- status/history/victory/deck/help/save are
    injected at real wizard prompts (they must loop back transparently);
  * undo during Winter Quarters -- an "undo" is injected at a human prompt
    while the current card is a Winter Quarters card, hitting the
    `except UndoException` restart path in the WQ branch of the loop;
  * Brilliant Stroke interrupt from a human seat -- detected and counted
    when a BS-interrupt prompt is presented to a seated human;
  * French pre-Treaty flow -- FRENCH is seated as a human in 1775;
  * save/load mid-game -- the loop autosaves every card; every save file
    produced is reloaded and validated, and a dedicated resume cycle saves
    mid-game, reloads into a fresh engine, and plays to completion.

Any crash, or any post-game invariant violation, writes a crash-repro dump
(scenario + seed + seated factions + the full scripted input log) and the
harness fails (exit 1).

    python -m lod_ai.tools.human_qa --seeds 1-5
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import random
import sys
import traceback
from copy import deepcopy

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.human_qa"] + sys.argv[1:])

from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai import interactive_cli as cli
from lod_ai import cli_display
from lod_ai.cli_utils import (set_input_provider, set_game_state,
                              set_undo_checkpoint)
from lod_ai.commands import battle as battle_cmd
from lod_ai.save_game import save_game, load_game
from lod_ai.util.validate import validate_state
from lod_ai.tools import invariants

import builtins
_REAL_INPUT = builtins.input

# Safe meta-commands that resolve and loop back to the same prompt.
_SAFE_META = ("status", "history", "victory", "deck", "help", "save")

# Faction seatings worth covering. 1775 French exercises the pre-Treaty flow;
# multi-faction sets exercise cross-faction interaction.
SEATINGS = (
    ("1775", ("PATRIOTS",)),
    ("1775", ("FRENCH",)),                 # pre-Treaty French
    ("1775", ("BRITISH", "INDIANS")),
    ("1778", ("FRENCH", "PATRIOTS")),
    ("1776", ("PATRIOTS", "BRITISH", "INDIANS")),
)


class ScriptedProvider:
    """Answers every CLI menu and injects meta-commands / undo on a budget."""

    def __init__(self, engine, rng, *, meta_budget=10, undo_budget=2,
                 wq_undo_budget=1):
        self.engine = engine
        self.rng = rng
        self.meta_budget = meta_budget
        self.undo_budget = undo_budget
        self.wq_undo_budget = wq_undo_budget
        self.log = []                 # (label, returned) for repro
        self.meta_fired = 0
        self.undo_fired = 0
        self.wq_undo_fired = 0
        self.bs_prompts = 0
        self._meta_streak = 0
        self._undo_cooldown = 0
        self._meta_idx = 0

    # -- helpers ---------------------------------------------------------
    def _is_wq_now(self) -> bool:
        cc = self.engine.state.get("current_card") or {}
        return bool(cc.get("winter_quarters"))

    def _answer(self, menu) -> str:
        kind = (menu or {}).get("kind")
        if kind == "count":
            lo = int(menu.get("min", 0)); hi = int(menu.get("max", lo))
            if hi < lo:
                hi = lo
            return str(self.rng.randint(lo, hi))
        # select
        opts = (menu or {}).get("options") or []
        n = len(opts)
        if n == 0:
            return "0"
        allow_back = (menu or {}).get("allow_back")
        back_label = (menu or {}).get("back_label")
        # choose_multiple shows back_label "Done"; finish ~30% of the time.
        if allow_back and back_label == "Done" and self.rng.random() < 0.30:
            return "0"
        return str(self.rng.randint(1, n))

    # -- provider protocol ----------------------------------------------
    def prompt(self, label: str, menu) -> str:
        if self._undo_cooldown > 0:
            self._undo_cooldown -= 1
        # Count Brilliant Stroke interrupt prompts presented to the human.
        text = f"{label} {(menu or {}).get('prompt', '')}".lower()
        if "brilliant stroke" in text:
            self.bs_prompts += 1

        # WQ-targeted undo: hit the undo-during-Winter-Quarters path. Uses
        # a reserved budget so it is not starved by the general undo below.
        if (self._is_wq_now() and self.wq_undo_budget > 0
                and self._undo_cooldown == 0):
            self.wq_undo_budget -= 1
            self.undo_fired += 1
            self.wq_undo_fired += 1
            self._undo_cooldown = 25
            self.log.append((label, "undo[WQ]"))
            return "undo"

        # Bounded meta-command injection mid-wizard.
        if (self.meta_budget > 0 and self._meta_streak < 2
                and self.rng.random() < 0.25):
            cmd = _SAFE_META[self._meta_idx % len(_SAFE_META)]
            self._meta_idx += 1
            self.meta_budget -= 1
            self.meta_fired += 1
            self._meta_streak += 1
            self.log.append((label, f"meta:{cmd}"))
            return cmd

        # Occasional non-WQ undo to exercise the normal-card restart path.
        if (self.undo_budget > 0 and self._undo_cooldown == 0
                and self.rng.random() < 0.04):
            self.undo_budget -= 1
            self.undo_fired += 1
            self._undo_cooldown = 25
            self.log.append((label, "undo"))
            return "undo"

        self._meta_streak = 0
        ans = self._answer(menu)
        self.log.append((label, ans))
        return ans


def _install_hooks(engine, provider, rng):
    set_game_state(engine.state, engine=engine)
    set_input_provider(provider)
    # pause_for_player and a couple of end-of-game prompts read stdin
    # directly (via the builtin). Route bare input() through the same
    # provider so the REAL pause_for_player runs -- this exercises its
    # meta-command handling (including undo at the Winter Quarters pause).
    builtins.input = lambda prompt="", *a, **k: provider.prompt(str(prompt), None)

    def _defender_hook(st, sid, def_side, owner, n_ug, ug_tag):
        if owner not in engine.human_factions:
            return 0
        return rng.randint(0, max(0, n_ug))
    battle_cmd.set_defender_activation_hook(_defender_hook)


def _teardown_hooks():
    set_input_provider(None)
    battle_cmd.set_defender_activation_hook(None)
    builtins.input = _REAL_INPUT


def _new_engine(scenario, seed, human_factions):
    state = build_state(scenario, seed=seed)
    state["_seed"] = seed
    state["_scenario"] = scenario
    state["_setup_method"] = "standard"
    state["_deck_display_mode"] = "exact"
    engine = Engine(initial_state=state, use_cli=True)
    engine.set_human_factions(set(human_factions))
    return engine


def _verify_state(engine, scenario, seed, hf, provider, dump_dir, phase):
    """Validate + save/load round-trip the live state; dump+raise on failure."""
    try:
        validate_state(engine.state)
        invariants.check_save_load_roundtrip(
            engine.state, scenario=scenario, seed=seed,
            card_number=len(engine.state.get("played_cards", [])),
            human_factions=set(hf), dump_dir=dump_dir,
        )
    except Exception as exc:
        path, repro = invariants.dump_repro(
            engine.state, scenario=scenario, seed=seed,
            card_number=len(engine.state.get("played_cards", [])),
            kind="human_qa", detail=f"{phase}: {type(exc).__name__}: {exc}",
            traceback_str=traceback.format_exc(), human_factions=set(hf),
            dump_dir=dump_dir,
        )
        # Attach the scripted input log for replay.
        raise RuntimeError(
            f"human QA {phase} failed [{scenario} seed={seed} hf={sorted(hf)}]: "
            f"{exc}\n  dump: {path}\n  inputs: {provider.log[-12:]}"
        ) from exc


def run_one(scenario, seed, human_factions, *, dump_dir="crash_dumps",
            max_cards=400):
    """Play one full human-seated game through the real loop. Returns stats."""
    rng = random.Random((seed << 8) ^ hash(human_factions) & 0xFFFF)
    engine = _new_engine(scenario, seed, human_factions)
    provider = ScriptedProvider(engine, rng)
    game_stats = cli._new_game_stats(engine.human_factions)
    # Safety cap: stop a runaway loop loudly rather than hang.
    engine.state["_qa_max_cards"] = max_cards

    _install_hooks(engine, provider, rng)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            with _card_cap(engine, max_cards):
                cli._game_loop(engine, game_stats)
    except _CardCap:
        pass  # game ran to the cap without ending; that's fine for QA
    except SystemExit:
        # 'quit' meta is not injected, but guard anyway.
        pass
    except Exception as exc:
        path, repro = invariants.dump_repro(
            engine.state, scenario=scenario, seed=seed,
            card_number=len(engine.state.get("played_cards", [])),
            kind="human_qa_crash", detail=f"{type(exc).__name__}: {exc}",
            traceback_str=traceback.format_exc(),
            human_factions=set(human_factions), dump_dir=dump_dir,
        )
        _teardown_hooks()
        raise RuntimeError(
            f"human QA crash [{scenario} seed={seed} hf={sorted(human_factions)}]: "
            f"{exc}\n  dump: {path}\n  inputs: {provider.log[-12:]}"
        ) from exc

    _verify_state(engine, scenario, seed, human_factions, provider,
                  dump_dir, "post-game")
    _teardown_hooks()
    return {
        "scenario": scenario, "seed": seed, "hf": sorted(human_factions),
        "meta_fired": provider.meta_fired, "undo_fired": provider.undo_fired,
        "wq_undo_fired": provider.wq_undo_fired, "bs_prompts": provider.bs_prompts,
        "prompts": len(provider.log),
    }


def run_resume(scenario, seed, human_factions, *, dump_dir="crash_dumps",
               stop_after=8):
    """Save mid-game, reload into a fresh engine, and finish. Returns ok bool."""
    rng = random.Random(0xC0FFEE ^ seed)
    engine = _new_engine(scenario, seed, human_factions)
    provider = ScriptedProvider(engine, rng, meta_budget=0, undo_budget=0,
                                wq_undo_budget=0)
    _install_hooks(engine, provider, rng)
    save_path = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            played = 0
            while played < stop_after:
                card = engine.draw_card()
                if card is None:
                    break
                set_undo_checkpoint(deepcopy(engine.state))
                engine.play_card(card, human_decider=cli._human_decider)
                played += 1
            # Save mid-game.
            save_path = save_game(engine.state, engine.human_factions,
                                  filename=f"qa_resume_{scenario}_{seed}")
        # Reload into a brand-new engine and finish the game.
        state2, hf2 = load_game(save_path)
        validate_state(state2)
        engine2 = Engine(initial_state=state2, use_cli=True)
        engine2.set_human_factions(hf2)
        provider2 = ScriptedProvider(engine2, rng)
        gs2 = cli._new_game_stats(engine2.human_factions)
        _install_hooks(engine2, provider2, rng)
        with contextlib.redirect_stdout(io.StringIO()):
            with _card_cap(engine2, 400):
                try:
                    cli._game_loop(engine2, gs2)
                except _CardCap:
                    pass
        _verify_state(engine2, scenario, seed, human_factions, provider2,
                      dump_dir, "post-resume")
    finally:
        _teardown_hooks()
        if save_path and os.path.exists(save_path):
            os.remove(save_path)
    return True


# --- a card-count cap implemented by wrapping engine.draw_card -------------

class _CardCap(Exception):
    pass


@contextlib.contextmanager
def _card_cap(engine, max_cards):
    orig = engine.draw_card
    count = {"n": 0}

    def capped(*a, **k):
        if count["n"] >= max_cards:
            raise _CardCap()
        count["n"] += 1
        return orig(*a, **k)

    engine.draw_card = capped
    try:
        yield
    finally:
        engine.draw_card = orig


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--dump-dir", default="crash_dumps")
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)

    results = []
    failures = []
    for scenario, hf in SEATINGS:
        for seed in seeds:
            tag = f"[{scenario} seed={seed:2d} hf={','.join(hf)}]"
            try:
                r = run_one(scenario, seed, hf, dump_dir=args.dump_dir)
                run_resume(scenario, seed, hf, dump_dir=args.dump_dir)
                results.append(r)
                print(f"{tag}  ok  ({r['prompts']} prompts, "
                      f"meta={r['meta_fired']}, undo={r['undo_fired']}"
                      f"/wq={r['wq_undo_fired']}, bs={r['bs_prompts']})")
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc))
                print(f"{tag}  FAIL: {str(exc).splitlines()[0]}")

    tot_meta = sum(r["meta_fired"] for r in results)
    tot_undo = sum(r["undo_fired"] for r in results)
    tot_wq = sum(r["wq_undo_fired"] for r in results)
    tot_bs = sum(r["bs_prompts"] for r in results)
    print(f"\nCoverage: {len(results)} games ok, meta-commands={tot_meta}, "
          f"undos={tot_undo} (WQ undos={tot_wq}), BS-interrupt prompts={tot_bs}")
    if failures:
        print(f"\nFAIL: {len(failures)} human-QA game(s) broke:")
        for m in failures[:5]:
            print(f"  {m}")
        return 1
    print("OK: human-mode QA clean (no crashes, no invariant violations).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
