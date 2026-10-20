"""Drive the real human CLI with decisions supplied by an external LLM.

Run ``python -m lod_ai.tools.llm_playtest --directory /tmp/trial``. Read
``decision.json`` and atomically write ``response.json`` containing its
``request_id``, an ``answer`` string, and a ``rationale``. Each menu answer
must come from the player; this tool never substitutes a bot/random policy.
Send ``{"request_id": N, "stop": true}`` to end a bounded exploratory trial.

The output directory contains the complete CLI output, a request/response
JSONL transcript, isolated saves, and a result with explicit stop/error status.
It is deliberately single-process: run independent trials in separate dirs.
"""
from __future__ import annotations

import argparse
import builtins
import contextlib
import io
import json
import os
from pathlib import Path
import time
import traceback

from lod_ai import cli_utils, interactive_cli as cli, rules_consts as C
from lod_ai.commands import battle
from lod_ai.engine import Engine
from lod_ai.llm.observation import serialize_state
from lod_ai.state.setup_state import build_state
from lod_ai.tools import invariants
from lod_ai.tools.run_diagnostics import collect_runtime_diagnostics, COUNT_KEYS
from lod_ai.util.validate import validate_state


class TrialStop(BaseException):
    """Exit through CLI/engine fallback handlers without taking another action."""


class BridgeFailure(BaseException):
    """A player/protocol failure must never become an automatic game choice."""


def _write_json(path: Path, value) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, default=str) + "\n")
    temp.replace(path)


class OutputCapture(io.StringIO):
    """Keep prompt deltas in memory and flush the full CLI log to disk."""

    def __init__(self, path: Path):
        super().__init__()
        self.log = path.open("w", encoding="utf-8")
        self.offset = 0

    def write(self, text):
        self.log.write(text)
        self.log.flush()
        return super().write(text)

    def delta(self) -> str:
        text = self.getvalue()
        result = text[self.offset:]
        self.offset = len(text)
        return result

    def close(self):
        self.log.close()
        super().close()


class FileDecisionProvider:
    """One outstanding atomic request; every supplied response is recorded."""

    def __init__(self, engine, directory: Path, output: OutputCapture, *,
                 timeout=1800.0, max_decisions=300):
        self.engine = engine
        self.directory = directory
        self.output = output
        self.timeout = timeout
        self.max_decisions = max_decisions
        self.decisions = 0
        self.current_faction = None
        self.history_offset = 0
        self.automatic_pauses = 0

    def begin_turn(self, faction, card=None, allowed=None):
        self.current_faction = faction

    def _record(self, value):
        with (self.directory / "transcript.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(value, default=str) + "\n")

    def prompt(self, label, menu):
        if menu is None and str(label) == "[Press Enter to continue, or type a command] ":
            self.automatic_pauses += 1
            self._record({"type": "automatic_pause", "label": str(label), "answer": ""})
            return ""
        if self.decisions >= self.max_decisions:
            raise TrialStop("decision_limit")
        request_id = self.decisions + 1
        history = self.engine.state.get("history", [])
        request = {
            "request_id": request_id,
            "faction": self.current_faction,
            "label": str(label), "menu": menu,
            "observation": serialize_state(self.engine.state, self.current_faction),
            "cli_output": self.output.delta(),
            "history": history[self.history_offset:],
        }
        self.history_offset = len(history)
        self._record({"type": "request", **request})
        _write_json(self.directory / "decision.json", request)
        deadline = time.monotonic() + self.timeout
        response_path = self.directory / "response.json"
        while True:
            if time.monotonic() >= deadline:
                raise BridgeFailure(f"player_timeout at request {request_id}")
            if not response_path.exists():
                time.sleep(0.1)
                continue
            try:
                response = json.loads(response_path.read_text(encoding="utf-8"))
                response_path.unlink()
                if not isinstance(response, dict):
                    raise ValueError("response must be an object")
                response_id = response.get("request_id")
                if type(response_id) is not int:
                    raise ValueError("request_id must be an integer")
                if "stop" in response and type(response["stop"]) is not bool:
                    raise ValueError("stop must be a boolean")
                if not response.get("stop") and not isinstance(response.get("answer"), str):
                    raise ValueError("answer must be a string")
                if 1 <= response_id < request_id:
                    # A client can read the previous request while its answer
                    # is being consumed. Record/discard that duplicate, keep
                    # waiting for the current ID, and never choose on its behalf.
                    self._record({**response, "type": "duplicate_response",
                                  "waiting_for": request_id})
                    continue
                if response_id != request_id:
                    raise ValueError(f"expected request_id {request_id}")
            except (OSError, ValueError, TypeError) as exc:
                raise BridgeFailure(f"invalid player response: {exc}") from exc
            break
        self._record({"type": "response", **response})
        (self.directory / "decision.json").unlink(missing_ok=True)
        if response.get("stop"):
            raise TrialStop("player_stop")
        self.decisions += 1
        return response["answer"]


@contextlib.contextmanager
def _installed(engine, provider):
    previous_input = builtins.input
    previous_provider = cli_utils.get_input_provider()
    previous_state = cli_utils._game_state
    previous_engine = cli_utils._engine_ref
    previous_undo = cli_utils.get_undo_checkpoint()
    previous_hook = battle._DEFENDER_ACTIVATION_HOOK
    previous_decider = cli._human_decider
    cli_utils.set_game_state(engine.state, engine=engine)
    cli_utils.set_input_provider(provider)
    builtins.input = lambda prompt="", *a, **k: provider.prompt(str(prompt), None)

    def decider(faction, card, allowed, live_engine):
        provider.begin_turn(faction, card, allowed)
        return previous_decider(faction, card, allowed, live_engine)
    cli._human_decider = decider

    def defender(st, sid, side, owner, n_ug, tag):
        if owner not in engine.human_factions:
            return 0
        provider.begin_turn(owner)
        answer = provider.prompt(
            f"{owner}: activate Underground defenders in {sid}",
            {"kind": "count", "min": 0, "max": n_ug},
        )
        try:
            value = int(answer)
        except ValueError as exc:
            raise BridgeFailure("defender activation requires an integer") from exc
        if not 0 <= value <= n_ug:
            raise BridgeFailure("defender activation outside offered range")
        return value

    battle.set_defender_activation_hook(defender)
    try:
        yield
    finally:
        builtins.input = previous_input
        cli_utils.set_input_provider(previous_provider)
        cli_utils.set_game_state(previous_state, engine=previous_engine)
        cli_utils.set_undo_checkpoint(previous_undo)
        battle.set_defender_activation_hook(previous_hook)
        cli._human_decider = previous_decider


def run_trial(directory, *, scenario="1775", seed=1, factions=(C.PATRIOTS,),
              max_cards=8, max_decisions=300, timeout=1800.0):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("Use an empty trial directory to prevent stale responses/logs")
    state = build_state(scenario, seed=seed)
    state.update(_seed=seed, _scenario=scenario, _setup_method="standard",
                 _deck_display_mode="fuzzy", player_factions=[[f] for f in factions],
                 human_factions=set(factions))
    engine = Engine(initial_state=state, use_cli=True)
    engine.set_human_factions(set(factions))
    stats = cli._new_game_stats(engine.human_factions)
    output = OutputCapture(directory / "cli_output.txt")
    provider = FileDecisionProvider(engine, directory, output,
                                    timeout=timeout, max_decisions=max_decisions)
    result = {"scenario": scenario, "seed": seed, "human_factions": sorted(factions),
              "stop_reason": "game_end", "error": None}
    checked_cards = 0

    def verify():
        nonlocal checked_cards
        validate_state(engine.state)
        invariants.check_save_load_roundtrip(
            engine.state, scenario=scenario, seed=seed,
            card_number=stats["cards_played"], human_factions=set(factions),
            dump_dir=str(directory / "crash_dumps"))
        checked_cards += 1

    original_next = engine.next_card
    def bounded_next():
        if stats["cards_played"]:
            verify()
        if stats["cards_played"] >= max_cards:
            raise TrialStop("card_limit")
        return original_next()
    engine.next_card = bounded_next
    previous_cwd = Path.cwd()
    try:
        # CLI autosaves and reports use relative paths; isolate all of them.
        os.chdir(directory)
        with contextlib.redirect_stdout(output), _installed(engine, provider):
            try:
                cli._game_loop(engine, stats)
            except TrialStop as exc:
                result["stop_reason"] = str(exc)
            except BridgeFailure as exc:
                result.update(stop_reason="bridge_error", error=str(exc))
            except SystemExit as exc:
                result["stop_reason"] = "cli_exit"
                result["exit_code"] = exc.code
            except Exception as exc:
                result.update(stop_reason="crash", error=f"{type(exc).__name__}: {exc}",
                              traceback=traceback.format_exc())
            try:
                verify()
                result.update(state_valid=True, save_roundtrip=True)
            except Exception as exc:
                result.update(state_valid=False, save_roundtrip=False,
                              invariant_error=f"{type(exc).__name__}: {exc}")
    finally:
        os.chdir(previous_cwd)
        # Human wizard rejections can occur in a discarded simulation; they
        # need not appear in the committed state's runtime error logs.
        cli_action_failures = [line.strip() for line in output.getvalue().splitlines()
                               if line.strip().startswith("Action failed:")]
        output.close()
    result.update(cards_played=stats["cards_played"], decisions=provider.decisions,
                  automatic_pauses=provider.automatic_pauses,
                  checked_boundaries=checked_cards,
                  victory_result=engine.state.get("victory_result"),
                  diagnostics=collect_runtime_diagnostics(engine.state),
                  cli_action_failures=cli_action_failures,
                  cli_rejections=engine.state.get("_cli_rejection_log", []))
    result["clean"] = (not result["error"] and result.get("state_valid", False)
                       and not any(result["diagnostics"][key] for key in COUNT_KEYS))
    _write_json(directory / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--scenario", choices=("1775", "1776", "1778"), default="1775")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--factions", default=C.PATRIOTS)
    parser.add_argument("--max-cards", type=int, default=8)
    parser.add_argument("--max-decisions", type=int, default=300)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args(argv)
    factions = tuple(f.strip().upper() for f in args.factions.split(",") if f.strip())
    if not factions or set(factions) - {C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS}:
        parser.error("--factions must contain canonical faction names")
    if args.max_cards < 1 or args.max_decisions < 1 or args.timeout <= 0:
        parser.error("limits and timeout must be positive")
    result = run_trial(args.directory, scenario=args.scenario, seed=args.seed,
                       factions=factions, max_cards=args.max_cards,
                       max_decisions=args.max_decisions, timeout=args.timeout)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
