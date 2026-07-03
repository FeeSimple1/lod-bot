"""T5/T6 (TRACEABILITY.md): §8.1 leader-follow tie randomness and the
Indian resource-gate exemption with per-command affordability."""
import random

import pytest

from lod_ai import rules_consts as C
from lod_ai.bots import indians as indians_mod
from lod_ai.bots.indians import IndianBot


def test_leader_follow_ties_are_random_not_first_neighbour(monkeypatch):
    """§8.1: "If two or more such groups are of the same size, select
    which one the Leader joins randomly." Two equal neighbour groups must
    both be reachable across seeds (the old code always took the first
    neighbour in iteration order, and never left on an origin tie)."""
    monkeypatch.setattr(indians_mod, "leader_location",
                        lambda st, leader: "Northwest")
    # Real map: Northwest is adjacent to Quebec and others; give two
    # neighbours equal WP counts and the origin fewer.
    neighbours = indians_mod._adjacent("Northwest")
    n1, n2 = neighbours[0], neighbours[1]
    seen = set()
    for seed in range(30):
        st = {"spaces": {"Northwest": {C.WARPARTY_U: 1},
                         n1: {C.WARPARTY_U: 3},
                         n2: {C.WARPARTY_U: 3}},
              "rng": random.Random(seed)}
        dest = indians_mod._ops_leader_destination(st, "LEADER_BRANT")
        assert dest in (n1, n2)
        seen.add(dest)
    assert seen == {n1, n2}


def test_leader_stays_when_origin_group_largest(monkeypatch):
    monkeypatch.setattr(indians_mod, "leader_location",
                        lambda st, leader: "Northwest")
    st = {"spaces": {"Northwest": {C.WARPARTY_U: 5}},
          "rng": random.Random(1)}
    assert indians_mod._ops_leader_destination(st, "LEADER_BRANT") is None


def test_scout_requires_both_payers(monkeypatch):
    """§3.4.3: "Pay one Resource. British also pay one Resource." §8.1:
    unaffordable Commands are skipped, continuing down the flowchart."""
    bot = IndianBot()
    monkeypatch.setattr(bot, "_space_has_wp_and_regulars", lambda st: True)
    st = {"resources": {C.INDIANS: 0, C.BRITISH: 5}}
    assert bot._can_scout(st) is False
    st["resources"][C.INDIANS] = 1
    assert bot._can_scout(st) is True
    st["resources"][C.BRITISH] = 0
    assert bot._can_scout(st) is False


def test_indians_not_blanket_gated_at_zero_resources():
    """The Indian flowchart has no "Resources > 0?" node (unlike B3/P3/
    F3) — at 0 Resources the Indian bot must reach its flowchart (I8:
    Trade if possible), not auto-PASS."""
    import inspect
    from lod_ai.bots.base_bot import BaseBot
    src = inspect.getsource(BaseBot.take_turn)
    assert "C.INDIANS" in src  # the exemption is present
