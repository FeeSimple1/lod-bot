"""Policy-seat harness: an authored strategy plays a human seat vs the bots.

Where ``tools/human_qa.py`` fuzzes the interactive loop with random
answers, this harness seats a deterministic, state-aware POLICY at the
same real CLI prompts (``interactive_cli._game_loop`` via the input-
provider protocol) and plays full games.  Uses (Session 74):

  * a baseline instrument for any house-TUNING work stream — pit a
    competent human-style seat against the bots seed-for-seed and
    compare against the all-bot outcome for the same seed (``--control``);
  * a live exercise of the human-mode paths (Piece 7 event-choice
    prompts, wizards, WQ pauses) with *meaningful* answers;
  * a place to iterate on seat strategy (subclass ``Strategist``).

The shipped ``Strategist`` encodes the lessons from the first play
sessions (S74): race your victory track (Muster/Reward-Loyalty for the
British, Rabble-Rousing for the Patriots, Hortelez/Muster for the
French), bank Pass income when poor, and treat Battle as tempo — only
fight when ``commands.battle.bot_battle_scores`` (the exact resolver
math) gives a decisive margin.  Event-vs-command defers to the seat
faction's own flowchart bullet list as an advisor.

    # 1 game, seat = BRITISH, with the all-bot control for comparison:
    python -m lod_ai.tools.policy_seat --scenario 1776 --seeds 42 \\
        --faction BRITISH --control

    # sweep seeds 1-10 as the French in 1778:
    python -m lod_ai.tools.policy_seat --scenario 1778 --seeds 1-10 \\
        --faction FRENCH
"""

from __future__ import annotations

import argparse
import builtins
import contextlib
import io
import os
import random
import sys
from typing import Dict, List, Tuple

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "-m",
                              "lod_ai.tools.policy_seat"] + sys.argv[1:])

import lod_ai.rules_consts as C
from lod_ai import interactive_cli as cli
from lod_ai.cli_utils import set_input_provider, set_game_state
from lod_ai.commands import battle as battle_cmd
from lod_ai.commands.battle import bot_battle_scores
from lod_ai.map import adjacency as map_adj
from lod_ai.tools.human_qa import _new_engine, _card_cap, _CardCap, _REAL_INPUT
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.french import FrenchBot
from lod_ai.bots.indians import IndianBot

ADVISOR = {C.BRITISH: BritishBot, C.PATRIOTS: PatriotBot,
           C.FRENCH: FrenchBot, C.INDIANS: IndianBot}
ROYALIST = (C.BRITISH, C.INDIANS)
SIDE_PREFIX = {True: ("British_", "Indian_"), False: ("Patriot_", "French_")}

#: Attack only when the resolver-math margin is at least this (S74:
#: over-battling starves the support/opposition race).
DECISIVE_MARGIN = 3


def _side_count(sp: Dict, prefixes) -> int:
    return sum(q for t, q in sp.items()
               if isinstance(t, str) and isinstance(q, int) and q > 0
               and t.startswith(prefixes))


class Strategist:
    """A competent, deterministic seat policy answering real CLI menus."""

    def __init__(self, engine, faction: str, rng: random.Random):
        self.engine = engine
        self.faction = faction
        self.rng = rng
        self.royal = faction in ROYALIST
        self.advisor = ADVISOR[faction]()
        self.log: List[str] = []
        self._card_attempts: Dict = {}   # per-card action/command attempts
        self._multi_prompt = None        # Done-loop tracking
        self._multi_picks = 0
        self._last_sig = None            # identical-menu loop breaker
        self._sig_reps = 0

    # ---- helpers ------------------------------------------------------
    @property
    def state(self):
        return self.engine.state

    def _card_key(self):
        return len(self.state.get("played_cards", []))

    def _winnable_battles(self) -> List[Tuple[int, str]]:
        out = []
        for sid in cli._battle_candidates(self.state, self.faction):
            try:
                att, dfd = bot_battle_scores(
                    self.state, sid,
                    attacker_side=("ROYALIST" if self.royal else "REBELLION"),
                    attacker_faction=self.faction)
            except Exception:  # noqa: BLE001 — planner probe only
                continue
            if att > dfd:
                out.append((att - dfd, sid))
        return sorted(out, reverse=True)

    def _resources(self) -> int:
        return self.state.get("resources", {}).get(self.faction, 0)

    def _label_space(self, label):
        sid = str(label).split(" (")[0].strip()
        return sid if sid in self.state.get("spaces", {}) else None

    def _score_space(self, sid: str, mode: str):
        sp = self.state["spaces"].get(sid, {})
        mine = _side_count(sp, SIDE_PREFIX[self.royal])
        theirs = _side_count(sp, SIDE_PREFIX[not self.royal])
        pop = map_adj.population(sid) or 0
        if mode == "battle":
            margin = next((m for m, s in self._winnable_battles()
                           if s == sid), -99)
            return (margin, pop)
        if mode == "dest":       # march/scout destination: hit weak stacks
            if theirs and mine >= 0:
                return (10 - theirs if theirs else 0, pop, -theirs)
            return (0, pop, mine)
        if mode == "source":     # move FROM: biggest of my stacks
            return (mine, -theirs)
        if mode == "remove":     # hurt them most
            return (theirs, pop)
        # placement/default: population first, contested spaces next
        return (pop, theirs, mine)

    # ---- menu answers ---------------------------------------------------
    def _pick_best(self, options, mode: str) -> str:
        scored = []
        for idx, label in enumerate(options, 1):
            sid = self._label_space(label)
            if sid:
                scored.append((self._score_space(sid, mode), idx))
        if not scored:
            return "1"
        scored.sort(reverse=True)
        return str(scored[0][1])

    def _action_menu(self, options) -> str:
        key = self._card_key()
        n = self._card_attempts.get(key, 0)
        self._card_attempts[key] = n + 1
        if n >= 5 and "Pass" in options:
            return str(options.index("Pass") + 1)   # anti-loop bailout

        card = self.state.get("current_card") or {}
        want: List[str] = []
        try:
            # The faction's own Event-or-Command bullet list as advisor.
            if n == 0 and self.advisor._faction_event_conditions(self.state,
                                                                 card):
                want.append("Event")
        except Exception:  # noqa: BLE001 — advisory only
            pass
        # Economy: with an empty purse and no cheap win, Pass banks
        # income and feeds the WQ Reward-Loyalty purse.
        if (not want and self._resources() <= 2
                and not self._winnable_battles() and "Pass" in options):
            want.append("Pass")
        want += ["Command + Special Activity", "Command",
                 "Command (Limited)", "Command Only", "Event", "Pass"]
        seen = [w for i, w in enumerate(want) if w in options
                and w not in want[:i]]
        pick = seen[min(n, len(seen) - 1)] if seen else options[0]
        return str(options.index(pick) + 1)

    def _command_menu(self, options) -> str:
        res = self._resources()
        prefs: List[str] = []
        wb = self._winnable_battles()
        # Battle is tempo, not points (S74): only decisive wins.
        if wb and wb[0][0] >= DECISIVE_MARGIN:
            prefs.append("Battle")
        if self.faction == C.FRENCH:
            if res >= 4:
                prefs += ["Muster", "March", "Hortelez",
                          "French Agent Mobilization"]
            else:
                prefs += ["Hortelez", "French Agent Mobilization", "March",
                          "Muster"]
        elif self.faction == C.BRITISH:
            # The British race is SUPPORT: Muster (cubes + Reward
            # Loyalty) is the engine.
            prefs += (["Muster", "Garrison", "March"] if res >= 4
                      else ["Garrison", "March", "Muster"])
        elif self.faction == C.PATRIOTS:
            # The rebel race is OPPOSITION: Rabble-Rousing scores it.
            prefs += (["Rabble-Rousing", "Rally", "March"] if res >= 2
                      else ["March", "Rally", "Rabble-Rousing"])
        else:
            prefs += ["Gather", "Raid", "Scout", "March"]
        key = ("cmd", self._card_key())
        n = self._card_attempts.get(key, 0)
        self._card_attempts[key] = n + 1
        ordered = [p for p in prefs if p in options]
        ordered += [o for o in options if o not in ordered]
        pick = ordered[min(n, len(ordered) - 1)]
        return str(options.index(pick) + 1)

    def _multi(self, prompt, options, allow_back) -> str:
        """Done-style multi menus: pick up to a cap of good options."""
        if prompt != self._multi_prompt:
            self._multi_prompt, self._multi_picks = prompt, 0
        low = prompt.lower()
        if "battle" in low:
            good = {s for _m, s in self._winnable_battles()}
            for idx, label in enumerate(options, 1):
                sid = self._label_space(label)
                if sid and sid in good:
                    self._multi_picks += 1
                    return str(idx)
            if self._multi_picks == 0:
                # min_sel=1 menus refuse Done with nothing picked; take
                # the least-bad option rather than loop.
                self._multi_picks += 1
                return self._pick_best(options, "battle")
            return "0"
        cap = 1 if ("destination" in low or "march" in low) else 2
        if self._multi_picks >= cap:
            return "0"
        self._multi_picks += 1
        mode = ("dest" if "destination" in low
                else "source" if ("origin" in low or "source" in low)
                else "remove" if "remove" in low
                else "place")
        return self._pick_best(options, mode)

    def _select(self, prompt, options, allow_back, back_label) -> str:
        low = (prompt or "").lower()
        if "choose action" in low:
            return self._action_menu(options)
        if "select event side" in low:
            side = "Unshaded" if self.royal else "Shaded"
            return str(options.index(side) + 1) if side in options else "1"
        if "select command" in low:
            return self._command_menu(options)
        if allow_back and back_label == "Done":
            return self._multi(prompt, options, allow_back)
        if "brilliant stroke" in low:
            for i, o in enumerate(options, 1):
                if str(o).lower().startswith(("no", "decline", "skip",
                                              "pass")):
                    return str(i)
            return "1"
        if sorted(options) == ["No", "Yes"]:
            return str(options.index("Yes") + 1)
        mode = ("battle" if "battle" in low
                else "dest" if ("destination" in low or "march to" in low)
                else "source" if ("source" in low or "from which" in low)
                else "remove" if "remove" in low
                else "place")
        return self._pick_best(options, mode)

    # ---- provider protocol ------------------------------------------------
    def prompt(self, label, menu):
        menu = menu or {}
        kind = menu.get("kind")
        sig = (menu.get("prompt"), tuple(menu.get("options") or ()), kind)
        if sig == self._last_sig:
            self._sig_reps += 1
        else:
            self._last_sig, self._sig_reps = sig, 0
        if kind == "select" and self._sig_reps >= 3:
            # Identical menu 4x running: my usual answer is being
            # rejected — cycle raw options to break out.
            opts = menu.get("options") or ["1"]
            ans = str((self._sig_reps - 3) % len(opts) + 1)
            self.log.append(f"LOOPBREAK {sig[0]!r} -> {ans}")
            return ans
        if kind == "count":
            lo, hi = int(menu.get("min", 0)), int(menu.get("max", 0))
            p = (menu.get("prompt") or "").lower()
            if ("activate how many underground" in p
                    and menu.get("default") is not None):
                ans = str(menu["default"])       # keep the ambush bonus
            else:
                ans = str(max(lo, hi))           # commit force / max effect
        elif kind == "select":
            ans = self._select(menu.get("prompt") or label,
                               menu.get("options") or [],
                               menu.get("allow_back"),
                               menu.get("back_label"))
        else:
            ans = ""                             # pause / bare input
        self.log.append(f"{(menu.get('prompt') or label)[:70]!r} -> {ans}")
        return ans


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def play(scenario: str, seed: int, faction: str, *, max_cards: int = 200,
         strategist_cls=Strategist):
    """Play one full game with *faction* as the policy seat.

    Returns (engine, provider, stats, stdout_text, err).  ``stats``
    carries the CLI's winner detection; ``err`` is None on a clean
    finish, "card-cap" if the cap stopped a runaway game, else the
    exception string.
    """
    rng = random.Random(seed * 977)
    engine = _new_engine(scenario, seed, {faction})
    provider = strategist_cls(engine, faction, rng)
    stats = cli._new_game_stats(engine.human_factions)
    set_game_state(engine.state, engine=engine)
    set_input_provider(provider)
    builtins.input = lambda prompt="", *a, **k: provider.prompt(str(prompt),
                                                                None)
    battle_cmd.set_defender_activation_hook(
        lambda st, sid, side, owner, n_ug, tag:
            n_ug if owner in engine.human_factions else 0)
    buf = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            with _card_cap(engine, max_cards):
                cli._game_loop(engine, stats)
    except _CardCap:
        err = "card-cap"
    except SystemExit:
        pass
    except Exception as exc:  # noqa: BLE001 — reported to the caller
        err = f"{type(exc).__name__}: {exc}"
    finally:
        set_input_provider(None)
        battle_cmd.set_defender_activation_hook(None)
        builtins.input = _REAL_INPUT
    cli._detect_winner(stats, engine.state)
    return engine, provider, stats, buf.getvalue(), err


def bot_control(scenario: str, seed: int):
    """Same scenario/seed with no human seat — the all-bot baseline."""
    from lod_ai.tools.batch_smoke import run_one_game
    r = run_one_game(scenario, seed)
    return r["winner"], r["cards_played"]


def _winner_faction(stats) -> str:
    msg = str(stats.get("winner") or "")
    for fac in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS):
        if fac in msg:
            return fac
    return "?"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="1776",
                    choices=("1775", "1776", "1778"))
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--faction", default="BRITISH",
                    choices=(C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS))
    ap.add_argument("--control", action="store_true",
                    help="also run the all-bot game per seed and compare")
    ap.add_argument("--log-dir", default=None,
                    help="write per-game stdout + decision logs here")
    ap.add_argument("--max-cards", type=int, default=200)
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)

    wins = flips = errs = 0
    for seed in seeds:
        engine, provider, stats, out, err = play(
            args.scenario, seed, args.faction, max_cards=args.max_cards)
        me = _winner_faction(stats)
        if args.log_dir:
            os.makedirs(args.log_dir, exist_ok=True)
            base = f"{args.scenario}_{seed}_{args.faction}"
            open(os.path.join(args.log_dir, f"game_{base}.log"),
                 "w").write(out)
            open(os.path.join(args.log_dir, f"decisions_{base}.log"),
                 "w").write("\n".join(provider.log))
        line = (f"[{args.scenario} seed={seed:3d}] seat={args.faction} "
                f"winner={me:8s} cards={len(engine.state.get('played_cards', []))}")
        if err:
            errs += 1
            line += f"  ERR={err}"
        if args.control:
            ctl, _cards = bot_control(args.scenario, seed)
            line += f"  | all-bot winner={ctl}"
            if me == args.faction and ctl != args.faction:
                flips += 1
                line += "  << FLIPPED"
        if me == args.faction:
            wins += 1
        print(line)

    n = len(list(seeds))
    print(f"\npolicy seat won {wins}/{n}"
          + (f" ({flips} flipped vs all-bot)" if args.control else "")
          + (f"; {errs} error(s)" if errs else ""))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
