"""Session 50 — T10 Brilliant Stroke details (§8.3.7 / §2.3.9 / §8.1)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lod_ai.cards.effects import brilliant_stroke as bs
from lod_ai.state.setup_state import build_state
from lod_ai.engine import Engine
from lod_ai import rules_consts as C


def test_preparations_nonplayer_counts_half_cbc():
    """§8.1 note: NP French count only HALF of CBC toward the Treaty."""
    st = {"available": {C.REGULAR_FRE: 10}, "markers": {}, "cbc": 12,
          "spaces": {}}
    full = bs.preparations_total(st)
    half = bs.preparations_total(st, nonplayer=True)
    assert full == 22
    assert half == 16


def test_bot_french_declares_toa_at_np_threshold():
    """§2.3.9 + §8.1: the bot French declare ToA once Regs + Squadrons +
    CBC/2 exceed 15 (Session 50: no bot path ever declared ToA — it was
    never played in bot-only 1775/1776 games)."""
    engine = Engine(initial_state=build_state("1775", seed=1))
    engine.set_human_factions(set())
    st = engine.state
    st["toa_played"] = False
    st["available"][C.REGULAR_FRE] = 10
    st["markers"] = {}
    st["eligible"] = {C.FRENCH: True}

    st["cbc"] = 12                       # 10 + 0 + 6 = 16 > 15
    assert bs.TOA_KEY in engine._collect_bot_bs_declarations(None)

    st["cbc"] = 10                       # 10 + 0 + 5 = 15, not > 15
    assert bs.TOA_KEY not in engine._collect_bot_bs_declarations(None)


def test_human_french_do_not_auto_declare_toa():
    engine = Engine(initial_state=build_state("1775", seed=1))
    engine.set_human_factions({C.FRENCH})
    st = engine.state
    st["toa_played"] = False
    st["available"][C.REGULAR_FRE] = 20
    st["cbc"] = 20
    assert bs.TOA_KEY not in engine._collect_bot_bs_declarations(None)


def test_bs_special_activity_actually_executes():
    """§8.3.7: the SA routes through the bot's own flowchart picker
    (Session 50: dispatcher calls with space=None raised for every
    space-requiring SA, so bot Brilliant Strokes ran with NO SA)."""
    engine = Engine(initial_state=build_state("1778", seed=2))
    engine.set_human_factions(set())
    st = engine.state
    # Give the British a clean Skirmish target
    st["spaces"]["Virginia"][C.REGULAR_BRI] = 3
    st["spaces"]["Virginia"][C.MILITIA_A] = 2
    before = len(st.get("history", []))
    engine._try_bs_special_activity(C.BRITISH)
    tail = " | ".join(str(h.get("msg", h) if isinstance(h, dict) else h)
                      for h in st["history"][before:])
    assert "SKIRMISH" in tail.upper()
