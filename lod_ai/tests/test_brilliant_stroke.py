from lod_ai.engine import Engine
from lod_ai import rules_consts as C
from lod_ai.cards.effects import brilliant_stroke as bs


def _dummy_card():
    return {"id": 9001, "title": "Test Event", "order": [C.BRITISH, C.PATRIOTS], "winter_quarters": False}


def _stub_command(engine, space="Boston"):
    def _cmd(*, faction, space_id=None, free=False, **kwargs):
        engine.state.setdefault("_turn_affected_spaces", set()).add(space_id or space)
        return {}
    return _cmd


def _stub_special(engine):
    def _sa(*, faction, space_id=None, free=False, **kwargs):
        engine.state["_turn_used_special"] = True
        return {}
    return _sa


def test_brilliant_stroke_cancels_event_and_records_played_cards():
    engine = Engine()
    engine.dispatcher._cmd["march"] = _stub_command(engine)
    engine.dispatcher._cmd["battle"] = _stub_command(engine)
    engine.dispatcher._sa["common_cause"] = _stub_special(engine)

    engine.state["bs_declarations"] = [C.PATRIOTS]
    engine.state["bs_plan"] = {
        C.PATRIOTS: [
            {"type": "command", "label": "march"},
            {"type": "special", "label": "common_cause"},
            {"type": "command", "label": "battle"},
        ]
    }

    actions = engine.play_card(_dummy_card())

    assert actions == []
    assert engine.state["played_cards"][-2:] == [9001, bs.FACTION_BY_BS_CARD[C.PATRIOTS]]
    assert engine.state["bs_played"][C.PATRIOTS] is True


def test_brilliant_stroke_trump_chain_and_eligibility_reset():
    engine = Engine()
    engine.dispatcher._cmd["march"] = _stub_command(engine)
    engine.dispatcher._cmd["battle"] = _stub_command(engine)
    engine.dispatcher._sa["common_cause"] = _stub_special(engine)

    engine.state["leaders"]["LEADER_ROCHAMBEAU"] = "Massachusetts"
    engine.state["spaces"]["Massachusetts"][C.REGULAR_FRE] = 1

    engine.state["bs_declarations"] = [C.PATRIOTS, C.BRITISH, C.FRENCH, C.INDIANS]
    engine.state["bs_plan"] = {
        C.INDIANS: [
            {"type": "command", "label": "march"},
            {"type": "special", "label": "common_cause"},
            {"type": "command", "label": "battle"},
        ]
    }

    engine.play_card(_dummy_card())

    assert engine.state["bs_played"].get(C.INDIANS) is True
    assert engine.state["bs_played"].get(C.PATRIOTS) is False
    assert engine.state["bs_played"].get(C.BRITISH) is False
    assert engine.state["bs_played"].get(C.FRENCH) is False
    assert all(engine.state["eligible"].values())


def test_treaty_of_alliance_trumps_and_cannot_be_trumped():
    engine = Engine()
    engine.dispatcher._cmd["march"] = _stub_command(engine)
    engine.dispatcher._cmd["battle"] = _stub_command(engine)
    engine.dispatcher._sa["common_cause"] = _stub_special(engine)

    engine.state["leaders"]["LEADER_ROCHAMBEAU"] = "Massachusetts"
    engine.state["spaces"]["Massachusetts"][C.REGULAR_FRE] = 1
    engine.state["available"][C.REGULAR_FRE] = 13
    engine.state["unavailable"][C.BLOCKADE] = 3
    engine.state["cbc"] = 0

    engine.state["bs_declarations"] = [C.PATRIOTS, bs.TOA_KEY, C.INDIANS]
    engine.state["bs_plan"] = {
        C.FRENCH: [
            {"type": "command", "label": "march"},
            {"type": "special", "label": "common_cause"},
            {"type": "command", "label": "battle"},
        ]
    }

    engine.play_card(_dummy_card())

    assert engine.state["played_cards"][-1] == bs.TOA_CARD_ID
    assert engine.state["bs_played"].get(bs.TOA_KEY) is True
    assert engine.state.get("toa_played") is True


def test_british_reward_loyalty_cost_not_waived_in_brilliant_stroke():
    engine = Engine()
    engine.dispatcher._cmd["march"] = _stub_command(engine)
    engine.dispatcher._sa["common_cause"] = _stub_special(engine)

    engine.state["resources"][C.BRITISH] = 1
    engine.state["spaces"]["Boston"][C.REGULAR_BRI] = 1
    engine.state["spaces"]["Boston"][C.TORY] = 1
    engine.state["control"]["Boston"] = C.BRITISH
    engine.state["support"]["Boston"] = 0

    engine.state["bs_declarations"] = [C.BRITISH]
    engine.state["bs_plan"] = {
        C.BRITISH: [
            {
                "type": "command",
                "label": "muster",
                "kwargs": {
                    "selected": ["Boston"],
                    "regular_plan": {"space": "Boston", "n": 1},
                    "tory_plan": {},
                    "reward_levels": 1,
                },
            },
            {"type": "special", "label": "common_cause"},
            {"type": "command", "label": "march"},
        ]
    }

    engine.play_card(_dummy_card())

    assert engine.state["resources"][C.BRITISH] == 0


# ---------------------------------------------------------------
# New tests: bot BS conditions, preparations_total, bot execution
# ---------------------------------------------------------------

def test_preparations_total_uses_full_cbc():
    """preparations_total should use full CBC per §2.3.9."""
    from lod_ai.util.naval import _blockade_markers
    state = {
        "available": {C.REGULAR_FRE: 4},
        "unavailable": {C.BLOCKADE: 2},
        "markers": {C.BLOCKADE: {"pool": 1, "on_map": set()}},
        "cbc": 10,
    }
    # Available French Regulars = 4
    # Total blockades = pool(1) + on_map(0) + unavail(2) = 3
    # CBC = 10
    # Total = 4 + 3 + 10 = 17
    assert bs.preparations_total(state) == 17


def test_bot_wants_bs_requires_toa_played():
    """Bot BS triggers require Treaty of Alliance to have been played."""
    state = {
        "toa_played": False,
        "eligible": {C.BRITISH: True},
        "bs_played": {},
        "spaces": {"Boston": {C.REGULAR_BRI: 5}},
        "leaders": {"LEADER_CLINTON": "Boston"},
        "leader_locs": {"LEADER_CLINTON": "Boston"},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
    }
    # Even with all other conditions met, should return False
    assert bs.bot_wants_bs(state, C.BRITISH, first_eligible=C.PATRIOTS, human_factions={C.PATRIOTS}) is False


def test_bot_wants_bs_british_trigger():
    """British bot: Rebellion player 1st Eligible OR Patriots play BS."""
    state = {
        "toa_played": True,
        "eligible": {C.BRITISH: True},
        "bs_played": {},
        "spaces": {"Boston": {C.REGULAR_BRI: 5}},
        "leaders": {"LEADER_CLINTON": "Boston"},
        "leader_locs": {"LEADER_CLINTON": "Boston"},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
    }
    # Rebellion player (Patriots) is 1st eligible
    assert bs.bot_wants_bs(state, C.BRITISH, first_eligible=C.PATRIOTS, human_factions={C.PATRIOTS}) is True
    # Non-Rebellion player 1st eligible — no trigger
    assert bs.bot_wants_bs(state, C.BRITISH, first_eligible=C.INDIANS, human_factions={C.INDIANS}) is False
    # Patriots play their BS — trigger
    assert bs.bot_wants_bs(state, C.BRITISH, first_eligible=C.INDIANS, human_factions=set(),
                           other_bs_faction=C.PATRIOTS) is True


def test_bot_wants_bs_indians_trigger():
    """Indians bot: any player 1st Eligible OR Rebellion plays BS (not ToA)."""
    state = {
        "toa_played": True,
        "eligible": {C.INDIANS: True},
        "bs_played": {},
        "spaces": {"Northwest": {C.WARPARTY_A: 2, C.WARPARTY_U: 1}},
        "leaders": {"LEADER_BRANT": "Northwest"},
        "leader_locs": {"LEADER_BRANT": "Northwest"},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
    }
    # Any player is 1st eligible
    assert bs.bot_wants_bs(state, C.INDIANS, first_eligible=C.BRITISH, human_factions={C.BRITISH}) is True
    # No player 1st eligible, but French plays BS
    assert bs.bot_wants_bs(state, C.INDIANS, first_eligible=C.BRITISH, human_factions=set(),
                           other_bs_faction=C.FRENCH) is True


def test_bot_wants_bs_insufficient_pieces():
    """Bot BS requires leader in space with enough faction pieces."""
    state = {
        "toa_played": True,
        "eligible": {C.BRITISH: True},
        "bs_played": {},
        "spaces": {"Boston": {C.REGULAR_BRI: 2}},  # Only 2, need 4
        "leaders": {"LEADER_CLINTON": "Boston"},
        "leader_locs": {"LEADER_CLINTON": "Boston"},
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
    }
    assert bs.bot_wants_bs(state, C.BRITISH, first_eligible=C.PATRIOTS, human_factions={C.PATRIOTS}) is False


def test_bot_bs_auto_check_in_engine():
    """Engine auto-checks bot BS conditions when bots meet trigger criteria."""
    engine = Engine()
    engine.dispatcher._cmd["battle"] = _stub_command(engine)
    engine.dispatcher._cmd["march"] = _stub_command(engine)
    engine.dispatcher._cmd["muster"] = _stub_command(engine)
    engine.dispatcher._sa["skirmish"] = _stub_special(engine)
    engine.dispatcher._sa["common_cause"] = _stub_special(engine)

    # Set up British bot to trigger BS
    engine.state["toa_played"] = True
    engine.state["spaces"]["Boston"][C.REGULAR_BRI] = 5
    engine.state["spaces"]["Boston"][C.MILITIA_A] = 1  # enemy for battle
    engine.state["leaders"]["LEADER_CLINTON"] = "Boston"
    engine.state["leader_locs"] = {"LEADER_CLINTON": "Boston"}

    # 1st eligible is a human-controlled Patriot
    engine.human_factions = {C.PATRIOTS}

    card = {"id": 9001, "title": "Test", "order": [C.PATRIOTS, C.BRITISH], "winter_quarters": False}
    actions = engine.play_card(card)

    # British bot should have auto-triggered BS
    assert engine.state["bs_played"].get(C.BRITISH) is True
    assert all(engine.state["eligible"].values())


def test_wq_card_blocks_brilliant_stroke():
    """Brilliant Stroke cannot be played when Winter Quarters is showing."""
    engine = Engine()
    engine.state["bs_declarations"] = [C.PATRIOTS]
    engine.state["bs_plan"] = {
        C.PATRIOTS: [
            {"type": "command", "label": "march"},
            {"type": "special", "label": "common_cause"},
            {"type": "command", "label": "battle"},
        ]
    }
    card = {"id": 9001, "title": "WQ", "order": [C.BRITISH, C.PATRIOTS], "winter_quarters": True}
    # WQ card — BS should not fire (play_card returns [] due to WQ handling)
    result = engine._resolve_brilliant_stroke_interrupt(card)
    assert result is False
