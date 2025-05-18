"""
brilliant_strokes.py  –  cards 105-109
--------------------------------------
• 105  Patriots  – Brilliant Stroke!
• 106  British   – Brilliant Stroke!
• 107  French    – Brilliant Stroke!
• 108  Indians   – Brilliant Stroke!
• 109  Treaty of Alliance (special)

Each Brilliant-Stroke lets its faction execute **two free Limited Commands
+ one Special Activity** and immediately resets all Eligibility.  Instead of
trying to drive the engine right here, we just **queue** the request in
state["bs_queue"] so the turn loop can resolve it cleanly.

Treaty of Alliance (#109) queues a different key and sets
state["toa_played"] = True.  Flesh out the real engine logic later.
"""

from lod_ai.cards import register
from lod_ai.util.history import push_history

# ------------------------------------------------ helper ------------------ #
def _queue_bs(state, faction: str | None):
    """
    Append a tuple to state['bs_queue']:
      ('BS', faction)   or   ('TOA', None)
    """
    key = "bs_queue"
    state.setdefault(key, []).append(("BS", faction))
    push_history(state, f"Brilliant Stroke queued for {faction or 'Treaty'}")

# ------------------------------------------------ 105-108 ------------------ #
_BS_FACTION = {
    105: "PATRIOTS",
    106: "BRITISH",
    107: "FRENCH",
    108: "INDIANS",
}

for _cid, _fac in _BS_FACTION.items():
    @register(_cid)                       # closure captures _cid/_fac
    def _make_bs(state, shaded=False, _f=_fac):
        """
        Queue a normal Brilliant-Stroke for *_f*.
        Engine will pop state['bs_queue'] and execute it.
        """
        _queue_bs(state, _f)
        # All factions become Eligible immediately
        state["ineligible_next"] = set()

# ------------------------------------------------ 109  Treaty ------------- #
@register(109)
def evt_109_treaty_of_alliance(state, shaded=False):
    """
    Treaty of Alliance – special Brilliant Stroke (card #109)
    Queues a 'TOA' entry and marks treaty as played.
    """
    state["toa_played"] = True
    state.setdefault("bs_queue", []).append(("TOA", None))
    push_history(state, "Treaty of Alliance queued")
    state["ineligible_next"] = set()