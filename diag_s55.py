"""Session 55 diagnostic: per-game finals for the British 0-2% investigation.

Runs zero-player games (same schedule as soak: scenario rotates, seed-base)
and logs per game: winner, final support/opposition, cbc/crc, per-faction
command counts parsed from history, and British battle/skirmish tallies.
Resumable jsonl like soak. NOT part of the battery.
"""
import argparse, json, os, sys, time, re

if os.environ.get("PYTHONHASHSEED") != "0" and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, "diag_s55.py"] + sys.argv[1:])

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai.tools.batch_smoke import _check_game_over

SCEN = ("1775", "1776", "1778")

CMD_PAT = re.compile(r"^(BRITISH|PATRIOT|PATRIOTS|FRENCH|INDIAN|INDIANS) (BATTLE|MARCH|MUSTER|GARRISON|RALLY|GATHER|PASS|SKIRMISH)")

def one(scenario, seed):
    state = build_state(scenario, seed=seed)
    eng = Engine(initial_state=state, use_cli=False)
    eng.set_human_factions([])
    cards = 0
    winner = None
    while cards < 200:
        card = eng.draw_card()
        if card is None:
            break
        eng.play_card(card, human_decider=None)
        cards += 1
        winner = _check_game_over(eng.state)
        if winner:
            break
    st = eng.state
    hist = st.get("history", [])
    counts = {}
    brit_battle_spaces = 0
    for h in hist:
        line = h.get("msg", "") if isinstance(h, dict) else str(h)
        m = CMD_PAT.match(line)
        if m:
            key = m.group(1)[:3] + "_" + m.group(2)
            counts[key] = counts.get(key, 0) + 1
            if m.group(1) == "BRITISH" and m.group(2) == "BATTLE":
                brit_battle_spaces += line.count(",") + 1
        if line.startswith("BRITISH PASS (no Resources)"):
            counts["BRI_PASS_NORES"] = counts.get("BRI_PASS_NORES", 0) + 1
    sup = 0; opp = 0
    from lod_ai.victory import _summarize_board
    t = _summarize_board(st)
    return {
        "scenario": scenario, "seed": seed, "cards": cards,
        "winner": winner,
        "support": t["support"], "opposition": t["opposition"],
        "cbc": t["cbc"], "crc": t["crc"],
        "toa": t["treaty_of_alliance"],
        "counts": counts, "brit_battle_spaces": brit_battle_spaces,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=90)
    ap.add_argument("--seed-base", type=int, default=5000)
    ap.add_argument("--out", default="diag_s55.jsonl")
    ap.add_argument("--max-seconds", type=float, default=38)
    a = ap.parse_args()
    done = 0
    if os.path.exists(a.out):
        done = sum(1 for l in open(a.out) if l.strip())
    plan = [(SCEN[i % 3], a.seed_base + i // 3) for i in range(a.games)]
    t0 = time.time(); ran = 0
    with open(a.out, "a") as f:
        for i in range(done, len(plan)):
            if a.max_seconds and time.time() - t0 > a.max_seconds:
                break
            try:
                rec = one(*plan[i])
            except Exception as e:
                rec = {"scenario": plan[i][0], "seed": plan[i][1], "error": str(e)[:200]}
            f.write(json.dumps(rec) + "\n"); f.flush(); ran += 1
    total = sum(1 for l in open(a.out) if l.strip())
    print(f"ran {ran}, total {total}/{len(plan)}" + (" DONE" if total >= len(plan) else ""))

if __name__ == "__main__":
    main()
