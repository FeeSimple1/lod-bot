"""Human-mode QA runner: play one game with a human-seat policy, dump
history + anomaly report."""
import json, sys, contextlib, io
from lod_ai.llm import run_game
from lod_ai.llm.heuristic import HeuristicPolicy, PROFILES

scenario, seed, faction, profile, out = (
    sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5])

res = run_game(scenario, seed=seed, llm_factions=[faction],
               policy=HeuristicPolicy(PROFILES[profile]), quiet=True)
st = res["state"]
hist = [str(h.get("msg", h) if isinstance(h, dict) else h)
        for h in st.get("history", [])]

report = {
    "scenario": scenario, "seed": seed, "faction": faction,
    "profile": profile,
    "winner": res.get("winner"), "cards": res.get("cards_played"),
    "decisions": res.get("decisions"),
    "bot_errors": st.get("_bot_error_log", []),
    "illegal": [h for h in hist if "illegal" in h.lower()],
    "free_op_skips": [h for h in hist if "skipped (no valid target)" in h
                      or "declined (no legal plan)" in h],
    "toa": st.get("toa_played"),
    "resources": st.get("resources"),
    "cbc": st.get("cbc"), "crc": st.get("crc"),
}
with open(out, "w") as f:
    json.dump({"report": report, "history": hist}, f, indent=1)
r = dict(report); r.pop("bot_errors")
print(json.dumps(r, indent=1))
print("bot_errors:", len(report["bot_errors"]))
for e in report["bot_errors"][:2]:
    print(" ", e.get("faction"), e.get("exception_type"), e.get("exception_message"))
