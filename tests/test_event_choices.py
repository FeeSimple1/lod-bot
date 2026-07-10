"""ROADMAP Piece 7 — CLI event-choice collection tests (batch 1).

Covers lod_ai/event_choices.py, the layer that prompts a human playing an
Event for the card's player choices and applies them as card<N>_*
overrides (docs/human_mode_audit.md).

The full interactive loop (with these prompts answered at random) is
fuzzed by lod_ai.tools.human_qa; these tests pin the pieces that need to
stay true structurally:

  * every wired card/key matches the frozen audit registry;
  * every candidate builder returns only in-play, handler-legal picks;
  * collection returns values of the shape each handler expects;
  * a handler really honors a collected override (spot checks).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import lod_ai.rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state
from lod_ai.cards import CARD_HANDLERS
from lod_ai.event_choices import EVENT_CHOICES, collect_event_choices
from lod_ai import cli_utils
from tests.test_human_mode_completeness import CHOICE_REGISTRY


class _FirstOption:
    """Input provider that answers '1' to every menu (first option)."""

    def prompt(self, label, menu):
        if (menu or {}).get("kind") == "count":
            return str(menu.get("min", 0))
        if not (menu or {}).get("options"):
            return "0"          # empty multi menu -> Done
        return "1"


def _rich_state():
    """A 1775 state mutated so most candidate lists are non-empty."""
    state = build_state("1775", seed=3)
    sp = state["spaces"]

    def bump(sid, tag, n):
        if sid in sp:
            sp[sid][tag] = sp[sid].get(tag, 0) + n

    bump("North_Carolina", C.MILITIA_U, 3)        # 23 shaded / 76
    bump("North_Carolina", C.REGULAR_PAT, 1)      # 23 unshaded src
    bump("Quebec", C.VILLAGE, 1)                  # 73
    bump("Quebec", C.FORT_PAT, 1)                 # 17 (Quebec is a Reserve? no)
    bump("Northwest", C.FORT_PAT, 1)              # 17 needs a Reserve fort
    bump("New_York", C.REGULAR_BRI, 2)            # 9 unshaded / 77
    bump("New_York", C.MILITIA_A, 1)              # 9 unshaded enemy
    bump("New_York", C.WARPARTY_U, 1)             # 77 Indian piece
    bump("Virginia", C.REGULAR_PAT, 2)            # 9 shaded / 59
    bump("Virginia", C.REGULAR_BRI, 1)            # 9 shaded enemy
    bump("Virginia", C.REGULAR_FRE, 2)            # 59
    bump("Georgia", C.VILLAGE, 1)                 # 79 shaded
    bump("Georgia", C.WARPARTY_U, 2)              # 79 shaded / 84 adjacency
    return state


def _engine(all_human=True):
    eng = Engine(initial_state=_rich_state(), use_cli=False)
    eng.set_human_factions(
        [C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS] if all_human else [])
    return eng


def _fake_card(cid):
    return {"id": cid, "title": f"test card {cid}", "dual": True}


def test_wired_cards_and_keys_match_frozen_registry():
    for cid, steps in EVENT_CHOICES.items():
        assert cid in CHOICE_REGISTRY, f"card {cid} wired but not in registry"
        reg_keys = set(CHOICE_REGISTRY[cid])
        for step in steps:
            assert step.key in reg_keys, (
                f"card {cid}: wired key {step.key!r} not in the audit "
                f"registry {sorted(reg_keys)}")


def test_all_43_registry_cards_are_wired():
    assert sorted(EVENT_CHOICES) == sorted(CHOICE_REGISTRY)


# Non-space option values the handlers accept (enums, flags, factions,
# piece tags for mixes and card 87).
_ENUM_VALUES = {
    "SCOUT", "MARCH", "WAR_PATH", "BRITISH_BATTLE",       # 14
    "FORT", "TORIES",                                      # 26 / 62
    "MILITIA", "WARPARTY", "CONTINENTAL",                  # 4 / 38 / 62 / 85
    "FORT_PAT", "FORT_BRI", "VILLAGE",                     # 4
    "FRENCH_QUEBEC", "MILITIA_NORTHWEST",                  # 62
    True, False,                                           # 52 / 55
    C.PATRIOTS, C.INDIANS, C.BRITISH, C.FRENCH,            # faction picks
    C.REGULAR_BRI, C.REGULAR_FRE, C.REGULAR_PAT, C.TORY,   # mixes / 87
    C.MILITIA_U, C.MILITIA_A, C.WARPARTY_U, C.WARPARTY_A,
    C.FORT_BRI, C.FORT_PAT, C.VILLAGE,
}


def test_candidate_builders_return_in_play_legal_picks():
    state = _rich_state()
    for cid, steps in EVENT_CHOICES.items():
        for want_shaded in (False, True):
            picks = {}
            for step in steps:
                if step.side is not None and step.side != want_shaded:
                    continue
                opts = step.options(state, C.PATRIOTS, picks)
                for label, value in opts:
                    assert isinstance(label, str) and label
                    if step.kind == "map":
                        assert label in state["spaces"]
                        assert all(d in state["spaces"] for d in value)
                    else:
                        assert value in state["spaces"] or value in _ENUM_VALUES, (
                            f"card {cid}/{step.key}: {value!r} neither in "
                            f"play nor a known enum")
                if opts:
                    picks[step.key] = opts[0][1]


def test_collection_shapes_match_handler_expectations():
    eng = _engine(all_human=True)
    provider = cli_utils.get_input_provider()
    cli_utils.set_input_provider(_FirstOption())
    try:
        for cid, steps in EVENT_CHOICES.items():
            for shaded in (False, True):
                if not any(s.side in (None, shaded) for s in steps):
                    continue
                overrides = collect_event_choices(
                    eng, C.PATRIOTS, _fake_card(cid), shaded)
                for key, value in overrides.items():
                    assert key.startswith(f"card{cid}_")
                    suffix = key.split("_", 1)[1]
                    step = next(s for s in steps
                                if s.key == suffix and s.side in (None, shaded))
                    if step.kind in ("multi", "repeat"):
                        assert isinstance(value, list) and value
                        if step.kind == "repeat":
                            assert len(value) == step.count
                        if step.max_sel:
                            assert len(value) <= step.max_sel
                    elif step.kind == "mix":
                        assert isinstance(value, dict)
                        assert sum(value.values()) == step.count
                    elif step.kind == "map":
                        assert isinstance(value, dict) and value
                        for origin, dest in value.items():
                            assert origin in eng.state["spaces"]
                            assert dest in eng.state["spaces"]
                    else:
                        assert isinstance(value, (str, bool)) and value != ""
    finally:
        cli_utils.set_input_provider(provider)


def test_overrides_do_not_outlive_collection_scope():
    """The CLI runner pops overrides after handle_event; the collection
    itself must never touch engine state."""
    eng = _engine(all_human=True)
    before = dict(eng.state)
    provider = cli_utils.get_input_provider()
    cli_utils.set_input_provider(_FirstOption())
    try:
        collect_event_choices(eng, C.PATRIOTS, _fake_card(9), False)
    finally:
        cli_utils.set_input_provider(provider)
    assert not [k for k in eng.state if k.startswith("card9_")]
    assert set(before) == set(eng.state)


def test_handler_honors_collected_space_override_card59():
    state = _rich_state()
    # Two qualifying spaces; the default scan would prefer a space with
    # BOTH Continentals and French Regulars -- Virginia.  Give a second
    # qualifying space and choose it explicitly instead.
    sp = state["spaces"]
    sp["Pennsylvania"][C.REGULAR_PAT] = sp["Pennsylvania"].get(C.REGULAR_PAT, 0) + 2
    sp["Pennsylvania"][C.REGULAR_FRE] = sp["Pennsylvania"].get(C.REGULAR_FRE, 0) + 2
    before = (sp["Pennsylvania"][C.REGULAR_PAT], sp["Pennsylvania"][C.REGULAR_FRE])
    state["card59_space"] = "Pennsylvania"
    CARD_HANDLERS[59](state, shaded=False)
    after = (sp["Pennsylvania"].get(C.REGULAR_PAT, 0),
             sp["Pennsylvania"].get(C.REGULAR_FRE, 0))
    assert after == (before[0] - 2, before[1] - 2), (
        "card59_space override must direct the removal")


def test_handler_honors_collected_colony_override_card79():
    state = _rich_state()
    state["card79_colony"] = "Georgia"
    v0 = state["spaces"]["Georgia"].get(C.VILLAGE, 0)
    CARD_HANDLERS[79](state, shaded=True)
    assert state["spaces"]["Georgia"].get(C.VILLAGE, 0) == v0 - 1, (
        "card79_colony override must direct the removal")


def test_handler_honors_sub_option_override_card26():
    state = _rich_state()
    avail = state.get("available", {}).get(C.TORY, 0)
    t0 = state["spaces"]["North_Carolina"].get(C.TORY, 0)
    state["card26_choice"] = "TORIES"
    CARD_HANDLERS[26](state, shaded=False)
    t1 = state["spaces"]["North_Carolina"].get(C.TORY, 0)
    assert t1 - t0 == min(2, avail), (
        "card26_choice=TORIES must place Tories, not the default Fort")


def test_handler_honors_faction_override_card18():
    state = _rich_state()
    state["active"] = C.PATRIOTS
    state["card18_target_faction"] = C.FRENCH   # even an ally is legal
    CARD_HANDLERS[18](state, shaded=False)
    assert C.FRENCH in state.get("ineligible_through_next", set()), (
        "card18_target_faction must direct the ineligibility")


def test_bot_decider_steps_are_skipped_for_bot_factions():
    """Card 84's Gather colonies belong to the INDIANS; with Indians a
    bot, a human executor must NOT be prompted (handler default runs)."""
    eng = Engine(initial_state=_rich_state(), use_cli=False)
    eng.set_human_factions([C.BRITISH])

    class _Boom:
        def prompt(self, label, menu):  # pragma: no cover
            raise AssertionError("prompted for a bot faction's choice")

    provider = cli_utils.get_input_provider()
    cli_utils.set_input_provider(_Boom())
    try:
        overrides = collect_event_choices(
            eng, C.BRITISH, _fake_card(84), False)
    finally:
        cli_utils.set_input_provider(provider)
    assert overrides == {}
