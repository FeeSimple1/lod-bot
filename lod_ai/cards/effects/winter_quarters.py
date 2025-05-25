"""Handlers for Winter-Quarters cards (97–104)."""

from lod_ai.cards import register
from lod_ai.cards.effects.shared import add_resource
from lod_ai.board.pieces import remove_piece
from lod_ai.util.history import push_history
from lod_ai.victory import _summarize_board, _patriot_margin, _indian_margin

# ---------------------------------------------------------------------------
# Helper to schedule a Reset-Phase effect
# ---------------------------------------------------------------------------

def _queue_event(state, cid, func):
    state["winter_card_event"] = func
    push_history(state, f"Queued Winter-Quarters {cid}")

# ---------------------------------------------------------------------------
# Individual card effects executed during the Reset Phase
# ---------------------------------------------------------------------------

def _royals_commit(state):
    if state.get("crc", 0) > state.get("cbc", 0):
        add_resource(state, "FRENCH", 5)
        push_history(state, "Royals Commit – French Resources +5")
    else:
        add_resource(state, "BRITISH", 5)
        push_history(state, "Royals Commit – British Resources +5")


def _overconfident(state):
    if state.get("crc", 0) > state.get("cbc", 0):
        add_resource(state, "BRITISH", -3)
        push_history(state, "Overconfident – British Resources -3")
    else:
        add_resource(state, "FRENCH", -3)
        push_history(state, "Overconfident – French Resources -3")


def _casualty_shift(state, label):
    crc = state.get("crc", 0)
    cbc = state.get("cbc", 0)
    diff = abs(crc - cbc) // 2
    if diff == 0:
        return
    if crc > cbc:
        state["crc"] = max(0, crc - diff)
        push_history(state, f"{label} – CRC reduced by {diff}")
    else:
        state["cbc"] = max(0, cbc - diff)
        push_history(state, f"{label} – CBC reduced by {diff}")


def _second_vc_leader(state):
    tallies = _summarize_board(state)
    if _patriot_margin(tallies)[1] > 0:
        return "PATRIOTS"
    if _indian_margin(tallies)[1] > 0:
        return "INDIANS"
    return None


def _lose_resources(state, label):
    fac = _second_vc_leader(state)
    if not fac:
        return
    add_resource(state, fac, -2)
    push_history(state, f"{label} – {fac.title()} lose 2 Resources")


def _lose_fort_or_village(state, label):
    fac = _second_vc_leader(state)
    if not fac:
        return
    target_tag = "Patriot_Fort" if fac == "PATRIOTS" else "Village"
    for sid, sp in state["spaces"].items():
        if sp.get(target_tag):
            remove_piece(state, target_tag, sid, 1, to="available")
            push_history(state, f"{label} – removed 1 {target_tag} from {sid}")
            break

# ---------------------------------------------------------------------------
# Card handlers – each queues its Reset-Phase effect
# ---------------------------------------------------------------------------

@register(97)
def evt_097(state, shaded=False):
    _queue_event(state, 97, _royals_commit)


@register(98)
def evt_098(state, shaded=False):
    _queue_event(state, 98, _overconfident)


@register(99)
def evt_099(state, shaded=False):
    _queue_event(state, 99, lambda s: _casualty_shift(s, "West Indies conflict"))


@register(100)
def evt_100(state, shaded=False):
    _queue_event(state, 100, lambda s: _casualty_shift(s, "India conflict"))


@register(101)
def evt_101(state, shaded=False):
    _queue_event(state, 101, lambda s: _lose_resources(s, "Floods shift the balance"))


@register(102)
def evt_102(state, shaded=False):
    _queue_event(state, 102, lambda s: _lose_fort_or_village(s, "War on the frontier"))


@register(103)
def evt_103(state, shaded=False):
    _queue_event(state, 103, lambda s: _lose_fort_or_village(s, "Severe Winter"))


@register(104)
def evt_104(state, shaded=False):
    _queue_event(state, 104, lambda s: _lose_resources(s, "Hurricane hits the South"))


