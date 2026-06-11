"""Heuristic policies for the LLM harness.

Each profile encodes a strategy hypothesis (drawn from strategy.md and
published play advice) as menu-answering rules, so large self-play batches
can compare strategies without any model calls.

Usage:
    from lod_ai.llm.heuristic import HeuristicPolicy, PROFILES
    policy = HeuristicPolicy(PROFILES["P-AGIT"])
    run_game("1778", llm_factions=["PATRIOTS"], policy=policy)
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .policy import Policy, _valid_choices
from lod_ai.map import adjacency as MAP

# --------------------------------------------------------------------------- #
# Observation parsing
# --------------------------------------------------------------------------- #
_SUPPORT_NUM = {
    "Active Support": 2, "Passive Support": 1, "Neutral": 0,
    "Passive Opposition": -1, "Active Opposition": -2,
}
_BOARD_RE = re.compile(
    r"^\s{2}(\S+)\s{2,}(Active Support|Passive Support|Neutral|"
    r"Passive Opposition|Active Opposition|\S+)\s{2,}"
    r"(British Control|Rebellion Control|no Control)\s{2,}(.*)$"
)
_PIECE_RE = re.compile(r"(\d+)\s+([A-Za-z()]+)")

_REBEL = ("Continental", "Militia", "PatFort", "FrenchReg")
_CROWN = ("BritReg", "Tory", "BritFort", "WarParty", "Village")


def parse_board(observation: str) -> Dict[str, dict]:
    """Extract per-space support/control/pieces from the rendered observation."""
    spaces: Dict[str, dict] = {}
    for line in observation.splitlines():
        m = _BOARD_RE.match(line)
        if not m:
            continue
        sid, sup_txt, ctrl, rest = m.groups()
        pieces: Dict[str, int] = {}
        for n, label in _PIECE_RE.findall(rest.split("|")[0]):
            pieces[label] = pieces.get(label, 0) + int(n)
        spaces[sid] = {
            "support": _SUPPORT_NUM.get(sup_txt, 0),
            "control": ctrl,
            "pieces": pieces,
            "rebel": sum(v for k, v in pieces.items()
                         if any(t in k for t in _REBEL)),
            "crown": sum(v for k, v in pieces.items()
                         if any(t in k for t in _CROWN)),
        }
    return spaces


def _pop(sid: str) -> int:
    try:
        return MAP.population(sid)
    except Exception:
        return 0


def _is_city(sid: str) -> bool:
    try:
        return MAP.is_city(sid)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Space scorers.  Each returns a number; <= 0 means "don't pick this space".
# Signature: (sid, info_or_None, side) where side is "REBEL" or "CROWN".
# --------------------------------------------------------------------------- #
def _info(board, sid):
    return board.get(sid, {"support": 0, "control": "no Control",
                           "pieces": {}, "rebel": 0, "crown": 0})


def score_rabble_rouse(sid, info, _):
    if info["support"] <= -2:          # already Active Opposition
        return 0
    return _pop(sid) * 10 + info["support"] + 3


def score_reward_loyalty(sid, info, _):
    if info["support"] >= 2:           # already Active Support
        return 0
    return _pop(sid) * 10 + (5 if _is_city(sid) else 0) - info["support"]


def score_muster(sid, info, _):
    return _pop(sid) * 5 + (10 if _is_city(sid) else 0) + info["crown"]


def score_rally(sid, info, _):
    bonus = 10 if "PatFort" in info["pieces"] else 0
    return _pop(sid) * 5 + bonus + info["rebel"]


def score_battle_rebel(sid, info, _):
    # Only attack with a clear force edge and no enemy fort.
    if "BritFort" in info["pieces"]:
        return 0
    edge = info["rebel"] - 2 * info["crown"]
    return edge * 10 if edge > 0 else 0


def score_battle_crown(sid, info, _):
    if "PatFort" in info["pieces"]:
        return 0
    edge = info["crown"] - 2 * info["rebel"]
    return edge * 10 if edge > 0 else 0


def score_gather(sid, info, _):
    wp = sum(v for k, v in info["pieces"].items() if "WarParty" in k)
    reserve = 10 if _pop(sid) == 0 and not _is_city(sid) else 0
    return wp * 10 + reserve + 1


def score_raid(sid, info, _):
    # Raid shifts toward Neutral: target Opposition provinces.
    if info["support"] >= 0:
        return 0
    return -info["support"] * 10 + _pop(sid)


def score_persuasion(sid, info, _):
    return _pop(sid) * 10 + 1


def score_march_dest(sid, info, side):
    own = info["rebel"] if side == "REBEL" else info["crown"]
    enemy = info["crown"] if side == "REBEL" else info["rebel"]
    return _pop(sid) * 2 + own - enemy + 1


SCORERS = {
    "Rabble-Rousing": score_rabble_rouse,
    "Rally": score_rally,
    "Muster": score_muster,
    "Battle": None,                    # filled per side below
    "Gather": score_gather,
    "Raid": score_raid,
    "Persuasion": score_persuasion,
    "March destinations": score_march_dest,
    "Common Cause": score_march_dest,
}

# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
_ACTION_ORDER = ["Command + Special Activity", "Command Only",
                 "Command (Limited)", "Limited Command", "Event", "Pass"]

PROFILES: Dict[str, dict] = {
    # ---- Patriots ----
    "P-AGIT": {                        # agitation engine: RR + Persuasion, forts
        "faction": "PATRIOTS", "side": "REBEL",
        "commands": ["Rabble-Rousing", "Rally", "March", "Battle"],
        "sas": ["Persuasion", "Partisans", "No Special Activity"],
        "event_side": "Shaded",
        "build_fort": "Yes", "max_picks": 3,
    },
    "P-MIL": {                         # army-first: rally Continentals, battle
        "faction": "PATRIOTS", "side": "REBEL",
        "commands": ["Rally", "Battle", "March", "Rabble-Rousing"],
        "sas": ["Partisans", "Persuasion", "No Special Activity"],
        "event_side": "Shaded",
        "build_fort": "Yes", "max_picks": 3,
    },
    # ---- British ----
    "B-CITY": {                        # hold cities, Muster+RL, garrison
        "faction": "BRITISH", "side": "CROWN",
        "commands": ["Muster", "Garrison", "Battle", "March"],
        "sas": ["Common Cause", "Skirmish", "No Special Activity"],
        "event_side": "Unshaded",
        "fort_or_rl": ["Reward Loyalty", "Build Fort", "None"],
        "max_picks": 3,
    },
    "B-AGGRO": {                       # hunt rebel stacks
        "faction": "BRITISH", "side": "CROWN",
        "commands": ["Battle", "March", "Muster", "Garrison"],
        "sas": ["Skirmish", "Common Cause", "No Special Activity"],
        "event_side": "Unshaded",
        "fort_or_rl": ["Build Fort", "Reward Loyalty", "None"],
        "max_picks": 3,
    },
    # ---- French ----
    "F-PREP": {                        # hoard pre-ToA, expedition post-ToA
        "faction": "FRENCH", "side": "REBEL",
        "commands": ["Hortelez", "Muster", "March", "Battle"],
        "commands_post_toa": ["Battle", "March", "Muster", "Hortelez"],
        "sas": ["Preparer la Guerre", "Common Cause", "No Special Activity"],
        "sas_post_toa": ["Naval Pressure", "Skirmish", "No Special Activity"],
        "event_side": "Shaded",
        "preparer": "REGULARS", "max_picks": 2,
    },
    "F-NAVY": {                        # naval/economic pressure throughout
        "faction": "FRENCH", "side": "REBEL",
        "commands": ["Hortelez", "Muster", "Battle", "March"],
        "commands_post_toa": ["Muster", "Battle", "March", "Hortelez"],
        "sas": ["Preparer la Guerre", "Naval Pressure", "No Special Activity"],
        "sas_post_toa": ["Naval Pressure", "Common Cause", "No Special Activity"],
        "event_side": "Shaded",
        "preparer": "RESOURCES", "max_picks": 2,
    },
    # ---- Indians ----
    "I-VILLAGE": {                     # gather/build villages, trade, defend
        "faction": "INDIANS", "side": "CROWN",
        "commands": ["Gather", "Raid", "Scout", "March", "Battle"],
        "sas": ["Trade", "War Path", "No Special Activity"],
        "event_side": "Unshaded",
        "gather_action": ["Build Village", "Bulk place War Parties",
                          "Place 1 War Party", "Move War Parties in"],
        "max_picks": 3,
    },
    "I-RAID": {                        # raid opposition, war path forts
        "faction": "INDIANS", "side": "CROWN",
        "commands": ["Raid", "Gather", "Scout", "Battle", "March"],
        "sas": ["War Path", "Plunder", "Trade", "No Special Activity"],
        "event_side": "Unshaded",
        "gather_action": ["Bulk place War Parties", "Place 1 War Party",
                          "Build Village", "Move War Parties in"],
        "max_picks": 3,
    },
}

# Count-prompt rules: first regex match wins.
_COUNT_RULES: List[Tuple[str, str]] = [
    (r"Resources to pay", "min"),
    (r"Number of Garrison moves", "one"),
    (r"[Ll]oss(es)?|[Rr]emove", "min"),
    (r"Activate how many", "max"),
    (r"Militia_U from", "keep1"),      # leave a seed militia behind
    (r"to place|to move|Move how many|How many", "max"),
]

_YESNO_RULES: List[Tuple[str, str]] = [
    (r"Build a Fort", "Yes"),
    (r"Skirmish after Scout", "Yes"),
    (r"Bring escorts", "No"),
]


class HeuristicPolicy(Policy):
    """Answer harness menus according to a strategy profile."""

    def __init__(self, profile: dict, seed: int = 0):
        self.p = dict(profile)
        self.side = self.p.get("side", "REBEL")
        self._picks: Dict[str, int] = {}
        self._attempt = 0          # nth try at the current turn (wizard restarts)

    def begin_turn(self, faction, card, allowed) -> None:
        """Called by the harness provider at the start of each real turn."""
        self._attempt = 0

    # -- helpers ---------------------------------------------------------- #
    def _pick_by_pref(self, options: List[str], prefs: List[str]) -> Optional[int]:
        best, best_rank = None, len(prefs)
        for i, opt in enumerate(options):
            for rank, pref in enumerate(prefs):
                if pref.lower() in opt.lower() and rank < best_rank:
                    best, best_rank = i, rank
        return best

    def _scorer_for(self, prompt: str):
        if "Battle" in prompt:
            return (score_battle_rebel if self.side == "REBEL"
                    else score_battle_crown)
        for key, fn in SCORERS.items():
            if fn and key in prompt:
                return fn
        return score_march_dest                      # generic fallback

    def _count_answer(self, prompt: str, menu: dict) -> str:
        lo, hi = menu.get("min", 0), menu.get("max", 0)
        for pat, mode in _COUNT_RULES:
            if re.search(pat, prompt):
                if mode == "min":
                    return str(lo)
                if mode == "max":
                    return str(hi)
                if mode == "one":
                    return str(min(max(1, lo), hi))
                if mode == "keep1":
                    return str(max(lo, hi - 1))
        if menu.get("default") is not None:
            return str(menu["default"])
        return str(lo)

    # -- main entry -------------------------------------------------------- #
    def choose(self, observation, label, menu, faction):
        if not menu:
            return ""
        prompt = (menu.get("prompt") or label or "").strip()

        if menu.get("kind") == "count":
            return self._count_answer(prompt, menu)

        options = menu.get("options", [])
        valid = _valid_choices(menu)

        # Brilliant Stroke declaration: declare the Treaty of Alliance
        # whenever it is offered (it is the French win condition's gate and
        # cannot be trumped); decline ordinary Brilliant Strokes -- the
        # profiles have no BS plan logic, and failed plans roll back anyway.
        if "declare a Brilliant Stroke" in prompt:
            for i, opt in enumerate(options, 1):
                if "Treaty of Alliance" in opt:
                    return str(i)
            for i, opt in enumerate(options, 1):
                if "No declaration" in opt:
                    return str(i)
            return valid[0]

        # Top-level turn menu: reset per-turn pick counters.  Seeing it again
        # within the same turn means our last plan was rejected -- degrade
        # gracefully instead of replaying the identical failing answers.
        if "turn. Choose action" in prompt:
            self._picks.clear()
            self._attempt += 1
            order = _ACTION_ORDER
            if self._attempt >= 6:
                order = ["Pass"]
            elif self._attempt >= 4:
                order = ["Command Only", "Command (Limited)", "Event", "Pass"]
            i = self._pick_by_pref(options, order)
            return str(i + 1) if i is not None else valid[0]

        post_toa = "Treaty of Alliance=played" in observation

        if prompt.startswith("Select Command"):
            prefs = list((self.p.get("commands_post_toa") if post_toa else None)
                         or self.p["commands"])
            # On retries, rotate the preference list to try a different command.
            shift = max(0, self._attempt - 1) % max(1, len(prefs))
            prefs = prefs[shift:] + prefs[:shift]
            i = self._pick_by_pref(options, prefs)
            return str(i + 1) if i is not None else valid[0]

        if prompt.startswith("Select a Special Activity"):
            prefs = (self.p.get("sas_post_toa") if post_toa else None) \
                or self.p["sas"]
            i = self._pick_by_pref(options, prefs)
            return str(i + 1) if i is not None else valid[0]

        if prompt.startswith("Select event side"):
            i = self._pick_by_pref(options, [self.p.get("event_side", "Shaded")])
            return str(i + 1) if i is not None else valid[0]

        if prompt.startswith("Fort or Reward Loyalty"):
            i = self._pick_by_pref(options, self.p.get(
                "fort_or_rl", ["Reward Loyalty", "Build Fort", "None"]))
            return str(i + 1) if i is not None else valid[0]

        if prompt.startswith("Choose Gather action"):
            i = self._pick_by_pref(options, self.p.get(
                "gather_action", ["Place 1 War Party"]))
            return str(i + 1) if i is not None else valid[0]

        if prompt.startswith("Choose Preparer option"):
            i = self._pick_by_pref(options, [self.p.get("preparer", "REGULARS")])
            return str(i + 1) if i is not None else valid[0]

        if set(options) <= {"Yes", "No"}:
            # After a failed turn, answer No to optional add-ons (they are the
            # usual culprits, e.g. an unaffordable Fort).
            if self._attempt <= 1:
                for pat, ans in _YESNO_RULES:
                    if re.search(pat, prompt):
                        i = self._pick_by_pref(options, [ans])
                        if i is not None:
                            return str(i + 1)
            i = self._pick_by_pref(options, ["No"])
            return str(i + 1) if i is not None else valid[0]

        # Space-selection menus: score options against the parsed board.
        board = parse_board(observation)
        space_opts = [o for o in options if o in board or _pop(o) or
                      MAP.space_type(o) is not None]
        if space_opts:
            base = re.sub(r"\(.*?\)", "", prompt).strip()
            multi = "select 0 when done" in prompt and menu.get("allow_back")
            picked = self._picks.get(base, 0)
            cap = self.p.get("max_picks", 3)
            if multi and picked >= cap:
                return "0"
            scorer = self._scorer_for(prompt)
            scored = sorted(
                ((scorer(o, _info(board, o), self.side), idx)
                 for idx, o in enumerate(options)),
                reverse=True,
            )
            best_score, best_idx = scored[0]
            if multi and best_score <= 0:
                return "0"
            self._picks[base] = picked + 1
            return str(best_idx + 1)

        # Unknown select menu: first option.
        return valid[0] if valid else ""
