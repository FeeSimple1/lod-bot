"""
winter_quarters.py  –  handlers for cards 97-104

Each Winter-Quarters card is single-sided.  We push its rule text into
state["winter_q_effects"] so the Reset-Phase routine can execute them in
year order.  That lets you finish the real end-of-year logic later
without breaking tests today.
"""
from lod_ai.cards import register, CARD_REGISTRY
from lod_ai.util.history import push_history

# --------------------------------------------------------------------------- #
# little helper so engine can find queued effects later
# --------------------------------------------------------------------------- #
def _queue(state, card_id: int, text: str) -> None:
    state.setdefault("winter_q_effects", []).append((card_id, text))
    push_history(state, f"Queued Winter-Quarters {card_id}")

# --------------------------------------------------------------------------- #
# lookup table taken verbatim from the reference
# --------------------------------------------------------------------------- #
_WQ_RULE = {
    97: "Royals commit: If CRC > CBC, French Resources +5; "
        "else British Resources +5 (Reset Phase).",

    98: "Overconfident at home: If CRC > CBC, British Resources –3; "
        "else French Resources –3 (Reset Phase).",

    99: "West Indies conflict goes the other way: Reduce the larger of "
        "CRC or CBC by half the difference (rounding down) (Reset Phase).",

    100: "India conflict goes the other way: Reduce the larger of CRC or "
         "CBC by half the difference (rounding down) (Reset Phase).",

    101: "Floods shift the balance: If Patriots or Indians lead their 2nd "
         "VC (§7.2), that Faction loses 2 Resources (Reset Phase).",

    102: "War on the frontier: If Patriots or Indians lead their 2nd VC "
         "(§7.2), that Faction removes 1 Fort or Village (Reset Phase).",

    103: "Severe winter: If Patriots or Indians lead their 2nd VC (§7.2), "
         "that Faction removes 1 Fort or Village (Reset Phase).",

    104: "Hurricane hits the South: If Patriots or Indians lead their 2nd VC "
         "(§7.2), that Faction loses 2 Resources (Reset Phase).",
}

# --------------------------------------------------------------------------- #
# auto-register every WQ card
# --------------------------------------------------------------------------- #
for _cid, meta in CARD_REGISTRY.items():
    if not getattr(meta, "winter_quarters", False):
        continue

    _text = _WQ_RULE[_cid]          # raise KeyError if JSON & table mismatch

    @register(_cid)                 # closure; binds _cid/_text per loop
    def _make_wq(state, shaded=False, _c=_cid, _t=_text):
        _queue(state, _c, _t)
