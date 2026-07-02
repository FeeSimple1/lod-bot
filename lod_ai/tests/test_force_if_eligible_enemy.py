"""Cards 18/44 sheet instruction: "Target an Eligible enemy Faction. If
none, choose Command & Special Activity instead." (Special Instructions
sections of the four flowchart references.) Enemy = other Side per the
Glossary (1.5.2). Regression for TRACEABILITY.md T12: the old code used
{BRITISH, INDIANS, FRENCH} − {self} — British counted their Indian ally
as an enemy and nobody counted Patriots — and never passed a target, so
card 18 defaulted to making BRITISH ineligible even when the British
themselves played it."""
import random

from lod_ai import rules_consts as C
from lod_ai.bots.base_bot import BaseBot


def _bot(faction):
    b = BaseBot()
    b.faction = faction
    return b


def _state(eligible, humans=()):
    return {
        "eligible": eligible,
        "human_factions": set(humans),
        "spaces": {},
        "support": {},
        "resources": {C.BRITISH: 9, C.PATRIOTS: 9, C.FRENCH: 9, C.INDIANS: 9},
        "rng": random.Random(7),
    }


def _card18(icons=("BRITISH", "PATRIOTS", "INDIANS")):
    return {"id": 18, "dual": True,
            "faction_icons": {f: "MUSKET" for f in icons}}


def test_british_targets_rebellion_not_indian_ally():
    st = _state({C.PATRIOTS: True, C.INDIANS: True,
                 C.FRENCH: False, C.BRITISH: True})
    assert _bot(C.BRITISH)._choose_event_vs_flowchart(st, _card18()) is True
    assert st["card18_target_faction"] == C.PATRIOTS
    assert C.PATRIOTS in st["ineligible_through_next"]


def test_british_with_only_ally_eligible_declines():
    st = _state({C.INDIANS: True, C.PATRIOTS: False,
                 C.FRENCH: False, C.BRITISH: True})
    assert _bot(C.BRITISH)._choose_event_vs_flowchart(st, _card18()) is False
    assert "ineligible_through_next" not in st


def test_patriot_targets_royalist_not_french_ally():
    st = _state({C.FRENCH: True, C.BRITISH: False,
                 C.INDIANS: True, C.PATRIOTS: True})
    bot = _bot(C.PATRIOTS)
    assert bot._choose_event_vs_flowchart(st, _card18()) is True
    assert st["card18_target_faction"] == C.INDIANS


def test_patriot_with_only_french_ally_eligible_declines():
    st = _state({C.FRENCH: True, C.BRITISH: False,
                 C.INDIANS: False, C.PATRIOTS: True})
    assert _bot(C.PATRIOTS)._choose_event_vs_flowchart(st, _card18()) is False


def test_harmful_choice_prefers_player_faction():
    """§8.3.5: harmful Event choices select a random enemy, PLAYER first."""
    st = _state({C.PATRIOTS: True, C.FRENCH: True,
                 C.BRITISH: True, C.INDIANS: False},
                humans={C.FRENCH})
    assert _bot(C.BRITISH)._choose_event_vs_flowchart(st, _card18()) is True
    assert st["card18_target_faction"] == C.FRENCH


def test_card44_handler_never_self_targets_without_override():
    from lod_ai.cards.effects.middle_war import evt_044_mansfield_recalled
    st = {"active": C.PATRIOTS, "history": []}
    evt_044_mansfield_recalled(st, shaded=False)
    assert C.PATRIOTS not in st["ineligible_through_next"]
    assert C.BRITISH in st["ineligible_through_next"]


def test_british_card80_condition_excludes_indian_pieces():
    """Sheet (British, card 80): "Choose a REBEL Faction with pieces in
    Cities" — Rebellion is Patriots + French (1.5.2). Indian War Parties
    in a City must not satisfy the condition (they did before Session 28)."""
    from lod_ai.bots.british_bot import BritishBot
    bot = BritishBot()
    st = _state({})
    st["spaces"] = {"Boston": {C.WARPARTY_U: 2}}
    assert bot._force_condition_met("force_if_80", st, {"id": 80}) is False
    st["spaces"]["Boston"][C.MILITIA_U] = 1
    assert bot._force_condition_met("force_if_80", st, {"id": 80}) is True


def test_card29_would_activate_accounts_for_already_active():
    """Card 29: activation runs "until ½ of them are Active" — the count
    that WOULD Activate is floor(total/2) − already-Active. With 8
    Underground and 6 already Active, only 1 would flip (< 4 → ignore);
    the old hidden//2 formula said 4 and wrongly played the event."""
    st = _state({})
    st["spaces"] = {"Massachusetts": {C.MILITIA_U: 8, C.MILITIA_A: 6}}
    bot = _bot(C.BRITISH)
    assert bot._condition_satisfied("ignore_if_4_militia", st, {"id": 29}) is True
    st["spaces"]["Massachusetts"][C.MILITIA_A] = 0
    # 8 Underground, 0 Active → 4 would flip → do NOT ignore.
    assert bot._condition_satisfied("ignore_if_4_militia", st, {"id": 29}) is False
