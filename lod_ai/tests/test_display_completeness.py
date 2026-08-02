"""Display completeness + honesty gates (S76, from the fs-bot
human-playtest report: 'nothing asserts display completeness').

1. Every piece tag in the counter mix renders in the board display —
   dynamically enumerated from rules_consts, so a NEW piece type fails
   this test until it is displayed.
2. Both marker types and an on-map leader render.
3. The human turn header carries the victory margins (fs lesson 1.6:
   the victory math on every screen).
4. A bot EVENT summary names the side and quotes the printed text
   (fs lesson 1.4: no black-box bot events).
"""
import io
import contextlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lod_ai.rules_consts as C
from lod_ai.state.setup_state import build_state
from lod_ai.cli_display import (display_board_state, display_turn_context,
                                display_bot_summary, _PIECE_ABBREV,
                                _snapshot_state)

ALL_PIECE_TAGS = (C.REGULAR_BRI, C.TORY, C.FORT_BRI,
                  C.REGULAR_PAT, C.MILITIA_A, C.MILITIA_U, C.FORT_PAT,
                  C.REGULAR_FRE, C.WARPARTY_A, C.WARPARTY_U, C.VILLAGE)


def _capture(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    return buf.getvalue()


def test_every_piece_tag_has_a_label_and_renders():
    assert set(ALL_PIECE_TAGS) <= set(_PIECE_ABBREV), (
        "every counter-mix piece tag needs a display label")
    st = build_state("1775", seed=1)
    sid = "Virginia"
    for tag in ALL_PIECE_TAGS:
        st["spaces"][sid][tag] = st["spaces"][sid].get(tag, 0) + 1
    st["leaders"]["LEADER_WASHINGTON"] = sid
    st["markers"][C.PROPAGANDA]["on_map"][sid] = 2
    st["markers"][C.PROPAGANDA]["pool"] -= 2
    st["markers"][C.RAID]["on_map"][sid] = 1
    st["markers"][C.RAID]["pool"] -= 1
    out = _capture(display_board_state, st)
    for tag in ALL_PIECE_TAGS:
        assert _PIECE_ABBREV[tag] in out, f"{tag} missing from board display"
    assert "Washington" in out, "on-map leader missing from board display"
    assert C.PROPAGANDA in out and C.RAID in out, "markers missing"
    assert "Support Total" in out and "Opposition Total" in out


def test_turn_header_shows_victory_margins():
    st = build_state("1776", seed=1)
    out = _capture(display_turn_context, C.BRITISH, st, slot="1st Eligible",
                   card={"title": "Test Card"})
    assert "Victory margins" in out
    for fac_tag in ("BRI", "PAT", "FRE", "IND"):
        assert fac_tag in out


def test_bot_event_summary_names_side_and_quotes_text():
    st = build_state("1775", seed=1)
    snap = _snapshot_state(st)
    card = {"id": 99, "title": "Test Event", "dual": True,
            "unshaded_event": "Unshaded printed text.",
            "shaded_event": "Shaded printed text."}
    out = _capture(display_bot_summary, C.PATRIOTS, st, snap,
                   {"action": "event", "event_side": "shaded"}, card)
    assert "EVENT (shaded)" in out and "Test Event" in out
    assert "Shaded printed text." in out
