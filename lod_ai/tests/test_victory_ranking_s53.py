"""Session 53 — C7: §7.1 ranking details."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.victory import final_scoring, check
from lod_ai.rules_consts import PATRIOTS, BRITISH, FRENCH, INDIANS


def _st(**extra):
    st = {"spaces": {}, "support": {}, "cbc": 0, "crc": 0,
          "toa_played": True, "treaty_of_alliance": True, "history": []}
    st.update(extra)
    return st


def _hist(st):
    return [str(h.get("msg", h) if isinstance(h, dict) else h)
            for h in st["history"]]


def test_np_beats_human_on_final_scoring_tie():
    """§7.1: "resolved in order of NON-PLAYERS, the Patriots, British,
    French and Indian" — a non-player French ties a HUMAN Patriot and
    the non-player wins (the faction order alone said Patriots)."""
    # Zero board gives PAT a base total of 3 (Forts+3-Villages); with
    # CRC=3 the British total also reaches 3 — a genuine tie.  The
    # human Patriots must LOSE the tie to the non-player British
    # (the bare faction order said Patriots).
    st = _st(human_factions={PATRIOTS}, crc=3)
    final_scoring(st)
    h = " | ".join(_hist(st))
    assert "Winner: BRITISH" in h
    assert "Placements (7.1): BRITISH > PATRIOTS" in h


def test_all_bot_tie_keeps_faction_order():
    st = _st(human_factions=set())
    final_scoring(st)
    h = " | ".join(_hist(st))
    assert "Winner: PATRIOTS" in h        # §7.1 faction order unchanged


def test_np_pass_logs_all_players_lose():
    """§7.1: any Non-player passing a victory check → all players lose."""
    st = _st(human_factions={BRITISH})
    # Patriots (non-player) pass: Opposition 11 over Support, forts+3>villages
    st["spaces"] = {"Virginia": {"Patriot_Fort": 1}}
    st["support"] = {"Virginia": -2, "Pennsylvania": -2, "Massachusetts": -2,
                     "New_York": -2, "North_Carolina": -2, "South_Carolina": -2}
    for s in list(st["support"]):
        st["spaces"].setdefault(s, {})
    assert check(st) is True
    h = " | ".join(_hist(st))
    assert "Victory Check passed by PATRIOTS" in h
    assert "all players lose equally" in h
