"""Decision-coverage instrumentation (ROADMAP Piece 5, Session 67).

Counts, across many bot-only games, which card sides x executing
factions, commands x factions, and Special Activities x factions ever
fire, from the engine's per-card ``_card_turn_log`` (plus the
``_turn_event_side`` / ``_turn_special_type`` trace keys added for this
purpose).  A combination that never fires in a large soak is either a
transcription error, a dead branch, or untested in practice — each one
is an audit lead, exactly like the §8.3.6/§8.3.7 classes found by hand.

Usage (aggregation is in-process; batch_smoke/soak call ``consume``):

    python -m lod_ai.tools.soak --games 300 --coverage coverage_s67.json
    python -m lod_ai.tools.coverage --report coverage_s67.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict

FACTIONS = ("BRITISH", "PATRIOTS", "INDIANS", "FRENCH")

# Universe tables straight from the rulebook section headers.
COMMANDS = {                                   # Manual Ch 3
    "BRITISH":  ("MUSTER", "GARRISON", "MARCH", "BATTLE"),          # 3.2
    "PATRIOTS": ("RALLY", "MARCH", "BATTLE", "RABBLE_ROUSING"),     # 3.3
    "INDIANS":  ("GATHER", "MARCH", "SCOUT", "RAID"),               # 3.4
    "FRENCH":   ("FRENCH_AGENT_MOBILIZATION", "HORTELEZ",           # 3.5.1-2
                 "MUSTER", "MARCH", "BATTLE"),                      # 3.5.3-5
}
SPECIAL_ACTIVITIES = {                         # Manual Ch 4
    "BRITISH":  ("COMMON_CAUSE", "SKIRMISH", "NAVAL_PRESSURE"),     # 4.2
    "PATRIOTS": ("PERSUASION", "PARTISANS", "SKIRMISH"),            # 4.3
    "INDIANS":  ("TRADE", "WAR_PATH", "PLUNDER"),                   # 4.4
    "FRENCH":   ("PREPARER", "SKIRMISH", "NAVAL_PRESSURE"),         # 4.5
}


class Collector:
    def __init__(self) -> None:
        self.events: Counter = Counter()    # (card_id, side, faction)
        self.commands: Counter = Counter()  # (faction, command)
        self.sas: Counter = Counter()       # (faction, sa)
        self.passes: Counter = Counter()    # (faction, reason)
        self.games = 0

    # -- ingestion ---------------------------------------------------------
    def consume_turn_log(self, state: Dict[str, Any]) -> None:
        for entry in state.get("_card_turn_log", []) or []:
            faction = entry.get("faction")
            action = entry.get("action")
            if faction not in FACTIONS:
                continue
            if action == "event":
                cid = entry.get("event_card_id")
                side = entry.get("event_side") or "unshaded"
                if cid is not None:
                    self.events[(int(cid), side, faction)] += 1
            elif action == "command":
                cmd = entry.get("command_type")
                if cmd:
                    self.commands[(faction, cmd)] += 1
                if entry.get("used_special"):
                    sa = entry.get("special_type") or "UNKNOWN"
                    self.sas[(faction, sa)] += 1
            elif action == "pass":
                self.passes[(faction, entry.get("pass_reason") or "other")] += 1

    def finish_game(self) -> None:
        self.games += 1

    # -- persistence -------------------------------------------------------
    def to_json(self) -> Dict[str, Any]:
        return {
            "games": self.games,
            "events": [[list(k), v] for k, v in sorted(self.events.items())],
            "commands": [[list(k), v] for k, v in sorted(self.commands.items())],
            "sas": [[list(k), v] for k, v in sorted(self.sas.items())],
            "passes": [[list(k), v] for k, v in sorted(self.passes.items())],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=1))

    @classmethod
    def load(cls, path: str | Path) -> "Collector":
        data = json.loads(Path(path).read_text())
        c = cls()
        c.games = data.get("games", 0)
        c.events = Counter({tuple(k): v for k, v in
                            ((tuple(k), v) for k, v in data.get("events", []))})
        c.commands = Counter({tuple(k): v for k, v in
                              ((tuple(k), v) for k, v in data.get("commands", []))})
        c.sas = Counter({tuple(k): v for k, v in
                         ((tuple(k), v) for k, v in data.get("sas", []))})
        c.passes = Counter({tuple(k): v for k, v in
                            ((tuple(k), v) for k, v in data.get("passes", []))})
        return c

    def merge(self, other: "Collector") -> None:
        self.games += other.games
        self.events += other.events
        self.commands += other.commands
        self.sas += other.sas
        self.passes += other.passes


# Process-global collector used by batch_smoke / soak when enabled.
GLOBAL: Collector | None = None


def enable() -> Collector:
    global GLOBAL
    if GLOBAL is None:
        GLOBAL = Collector()
    return GLOBAL


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _card_universe():
    """(card_id, dual, winter_quarters, brilliant_stroke, title) for the deck."""
    import lod_ai.rules_consts as C
    data = json.loads((Path(__file__).resolve().parents[1] / "cards" /
                       "data.json").read_text())
    cards = data["cards"] if isinstance(data, dict) and "cards" in data else data
    out = []
    for c in cards:
        cid = int(c["id"])
        out.append((cid, bool(c.get("dual")),
                    cid in C.WINTER_QUARTERS_CARDS,
                    cid in C.BRILLIANT_STROKE_CARDS,
                    c.get("title", "")))
    return out


def report(coll: Collector) -> str:
    lines = [f"# Decision coverage — {coll.games} games", ""]

    lines.append("## Commands x faction (Ch 3 universe)")
    for fac in FACTIONS:
        for cmd in COMMANDS[fac]:
            n = coll.commands.get((fac, cmd), 0)
            flag = "" if n else "   <-- NEVER FIRED"
            lines.append(f"  {fac:8s} {cmd:26s} {n:6d}{flag}")
    extra = [(k, v) for k, v in coll.commands.items()
             if k[1] not in COMMANDS.get(k[0], ())]
    for (fac, cmd), v in sorted(extra):
        lines.append(f"  {fac:8s} {cmd:26s} {v:6d}   <-- OUTSIDE Ch 3 universe")
    lines.append("")

    lines.append("## Special Activities x faction (Ch 4 universe)")
    for fac in FACTIONS:
        for sa in SPECIAL_ACTIVITIES[fac]:
            n = coll.sas.get((fac, sa), 0)
            flag = "" if n else "   <-- NEVER FIRED"
            lines.append(f"  {fac:8s} {sa:26s} {n:6d}{flag}")
    extra = [(k, v) for k, v in coll.sas.items()
             if k[1] not in SPECIAL_ACTIVITIES.get(k[0], ())]
    for (fac, sa), v in sorted(extra):
        lines.append(f"  {fac:8s} {sa:26s} {v:6d}   <-- OUTSIDE Ch 4 universe")
    lines.append("")

    lines.append("## Event sides never chosen by any bot")
    fired_sides = {(cid, side) for (cid, side, _f) in coll.events}
    for cid, dual, wq, bs, title in _card_universe():
        if wq or bs:
            continue  # WQ/BS cards are not chosen events
        sides = ("unshaded", "shaded") if dual else ("unshaded",)
        missing = [s for s in sides if (cid, s) not in fired_sides]
        if len(missing) == len(sides):
            lines.append(f"  card {cid:3d} NEVER EXECUTED ({title})")
        elif missing:
            lines.append(f"  card {cid:3d} side(s) never fired: {missing} ({title})")
    lines.append("")

    lines.append("## Event executions by faction (fired combos)")
    per_fac = Counter()
    for (cid, side, fac), v in coll.events.items():
        per_fac[fac] += v
    for fac in FACTIONS:
        distinct = len({(c, s) for (c, s, f) in coll.events if f == fac})
        lines.append(f"  {fac:8s} {per_fac.get(fac, 0):6d} executions, "
                     f"{distinct} distinct card-sides")
    lines.append("")

    lines.append("## Passes by reason")
    for (fac, reason), v in sorted(coll.passes.items()):
        lines.append(f"  {fac:8s} {reason:30s} {v:6d}")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="coverage json to report on")
    args = ap.parse_args(argv)
    print(report(Collector.load(args.report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
