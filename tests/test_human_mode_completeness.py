"""ROADMAP Piece 7 — human-mode completeness gate.

A card presents a player choice iff its event handler reads a
`state.get("card<N>_<key>")` override — the hook a human (via the CLI)
or a bot is meant to set.  This test freezes the audited registry of
such cards (docs/human_mode_audit.md, Session 72) so that:

  * a NEW card that adds a player choice fails the test until it is
    triaged into the registry (and, ultimately, wired into the CLI
    event-choice step);
  * removing a choice hook is likewise surfaced.

The CLI collection layer (lod_ai/event_choices.py) is being wired in
batches; tests/test_event_choices.py asserts each wired card's keys
match this registry.  Wiring status:

  * WIRED (batch 1, the 26 space-selection cards): 5, 7, 9, 11, 15, 16,
    17, 19, 21, 23, 25, 27, 29, 31, 35, 47, 50, 59, 73, 76, 77, 79, 81,
    83, 84, 93.  (Note: card 29's value is a FACTION, not a space —
    audit-table correction recorded in docs/human_mode_audit.md.)
  * WIRED (batch 2, sub-option cards): 14, 26, 38, 52, 55, 62.
  * WIRED (batch 3, faction-target / piece-mix cards): 4, 18, 44, 48,
    66, 67, 74, 80, 85, 87, 88.

ALL 43 cards are wired (Session 73); tests/test_event_choices.py
asserts EVENT_CHOICES covers this registry exactly.  Residual out of
scope: event-GRANTED free ops for a human faction are still bot-planned
(see docs/human_mode_audit.md).

This gate stops the audit from silently drifting while the remaining
batches are built out.
"""
import re
import pathlib

_EFFECTS = pathlib.Path(__file__).resolve().parents[1] / "lod_ai/cards/effects"

# Frozen registry: card number -> the override keys its handler reads.
# Regenerate deliberately (never blindly) when a card's choices change,
# and update docs/human_mode_audit.md in the same commit.
CHOICE_REGISTRY = {
    4: ('base', 'units'),
    5: ('dest', 'src'),
    7: ('dest',),
    9: ('spaces',),
    11: ('spaces',),
    14: ('dest', 'followup', 'op', 'src'),
    15: ('colony',),
    16: ('city', 'target'),
    17: ('space',),
    18: ('target_faction',),
    19: ('targets',),
    21: ('target',),
    23: ('dst', 'src', 'target'),
    25: ('cities',),
    26: ('choice', 'src'),
    27: ('cities', 'colonies'),
    29: ('target',),
    31: ('target',),
    35: ('shaded_target', 'target'),
    38: ('shaded_choice', 'unshaded_mix', 'unshaded_space'),
    44: ('target_faction',),
    47: ('colony',),
    48: ('faction',),
    50: ('colony',),
    52: ('no_remove_french',),
    55: ('do_battle',),
    59: ('space',),
    62: ('shaded_choice', 'target', 'unshaded_choice'),
    66: ('mix', 'shaded_faction', 'target'),
    67: ('faction',),
    73: ('space',),
    74: ('recipient', 'spaces'),
    76: ('space',),
    77: ('space',),
    79: ('colony',),
    80: ('faction', 'spaces'),
    81: ('target',),
    83: ('target',),
    84: ('colonies',),
    85: ('mix', 'shaded_choice'),
    87: ('piece',),
    88: ('destinations', 'target_faction'),
    93: ('targets',),
}


def _discover():
    found = {}
    for f in _EFFECTS.glob("*.py"):
        for m in re.finditer(r'state\.get\("card(\d+)_([a-z_]+)"', f.read_text()):
            found.setdefault(int(m.group(1)), set()).add(m.group(2))
    return {c: tuple(sorted(v)) for c, v in found.items()}


def test_choice_bearing_cards_match_registry():
    discovered = _discover()
    expected = {c: tuple(sorted(k)) for c, k in CHOICE_REGISTRY.items()}
    new_cards = sorted(set(discovered) - set(expected))
    gone_cards = sorted(set(expected) - set(discovered))
    changed = {c: (expected[c], discovered[c])
               for c in set(expected) & set(discovered)
               if expected[c] != discovered[c]}
    assert not new_cards, (
        f"New choice-bearing card(s) {new_cards}: a human seat cannot make "
        f"these choices until the CLI event step is wired.  Triage into "
        f"docs/human_mode_audit.md + this registry.")
    assert not gone_cards, f"Choice hook(s) removed for card(s) {gone_cards}."
    assert not changed, f"Choice keys changed: {changed}"


def test_registry_size_is_the_audited_count():
    # Guards the headline number in the audit doc.
    assert len(CHOICE_REGISTRY) == 43
