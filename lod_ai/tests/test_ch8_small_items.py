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


def test_per_turn_flags_cleared_at_turn_start(monkeypatch):
    """Session 30: _sa_done_this_turn and _muster_die_cached froze for the
    whole game once set (Muster's SA permanently skipped; B6's die rolled
    once per game). take_turn must clear both at entry."""
    from lod_ai.bots.base_bot import BaseBot

    bot = BaseBot()
    bot.faction = "BRITISH"
    monkeypatch.setattr(bot, "_choose_event_vs_flowchart",
                        lambda st, card: False)
    monkeypatch.setattr(bot, "_follow_flowchart", lambda st: None)
    st = {"resources": {"BRITISH": 5},
          "_sa_done_this_turn": True, "_muster_die_cached": 3,
          "history": []}
    bot.take_turn(st, {"id": 1})
    assert "_sa_done_this_turn" not in st
    assert "_muster_die_cached" not in st


def test_blockade_move_requires_strictly_more_support():
    """§8.5.1/§8.6.6: Win-the-Day Blockade moves 'to another City with
    MORE Support' — a tie or worse means no move."""
    from lod_ai.bots.patriot import PatriotBot
    bot = PatriotBot()
    st = {"spaces": {}, "support": {"Boston": 1, "New_York_City": 1,
                                    "Philadelphia": 0}}
    # Origin support 1; all other cities <= 1 → no destination.
    assert bot._best_blockade_city(st, exclude="Boston",
                                   min_support=1) is None
    st["support"]["Philadelphia"] = 2
    assert bot._best_blockade_city(st, exclude="Boston",
                                   min_support=1) == "Philadelphia"


def test_pre_treaty_hortalez_spends_up_to_the_roll(monkeypatch):
    """Q16 ruling: §8.6.1 'spending up to 1D3 French Resources' controls
    over flowchart F6's exact-spend wording. With 1 Resource and a roll
    of 3, the French spend 1 and execute — they do not Pass."""
    import random
    from lod_ai.bots.french import FrenchBot

    bot = FrenchBot()

    class Roll3:
        def randint(self, a, b):
            return 3
    st = {"resources": {"BRITISH": 5, "PATRIOTS": 5, "FRENCH": 1,
                        "INDIANS": 5},
          "spaces": {}, "rng": Roll3(), "history": []}
    assert bot._hortelez(st, before_treaty=True) is True
    assert st["resources"]["FRENCH"] == 0          # spent the 1 it had
    assert st["resources"]["PATRIOTS"] > 5         # Patriots gained


def test_raid_uses_at_most_one_special_activity(monkeypatch):
    """§4.1 one SA per turn. 8.7.1's zero-Resource clause is 'Plunder
    (or if that is not possible, Trade)' — either/or. The old sequence
    ran Plunder AND Trade at 0 Resources, then the I5 block again."""
    bot = IndianBot()
    calls = []

    def fake_plunder(st):
        st["_turn_used_special"] = True
        calls.append("plunder")
        return True

    monkeypatch.setattr(bot, "_can_raid", lambda st: True)
    monkeypatch.setattr(bot, "_raid", lambda st: True)
    monkeypatch.setattr(bot, "_can_plunder", lambda st: True)
    monkeypatch.setattr(bot, "_plunder", fake_plunder)
    monkeypatch.setattr(bot, "_trade",
                        lambda st: calls.append("trade") or True)
    monkeypatch.setattr(bot, "_war_path_or_trade",
                        lambda st: calls.append("war_path"))

    st = {"resources": {C.INDIANS: 0}}
    assert bot._raid_sequence(st) is True
    assert calls == ["plunder"]          # exactly ONE SA

    # SA already used this turn → no further SA at all.
    calls.clear()
    st2 = {"resources": {C.INDIANS: 0}, "_turn_used_special": True}
    assert bot._raid_sequence(st2) is True
    assert calls == []
