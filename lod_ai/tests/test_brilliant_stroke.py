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
