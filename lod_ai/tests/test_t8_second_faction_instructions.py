"""T8 (§8.3.1): the 2nd Faction's Event Instructions govern how it
executes actions granted by another Faction's Event.  The one card with
an unpinned granted March + a "March to set up Battle" instruction is
card 51 (force_if_51, British unshaded / Patriot shaded); its free March
must target a winnable Battle space, not a generic destination.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from lod_ai import rules_consts as C
from lod_ai.commands.battle import bot_march_battle_target
from lod_ai.engine import Engine, _event_instruction


def _state(spaces, support=None):
    return {
        "spaces": spaces,
        "resources": {C.BRITISH: 5, C.PATRIOTS: 5, C.FRENCH: 5, C.INDIANS: 5},
        "available": {}, "unavailable": {}, "casualties": {},
        "support": support or {}, "control": {}, "markers": {},
        "leaders": {}, "rng": random.Random(3), "history": [],
        "fni_level": 0,
    }


def test_event_instruction_lookup():
    # Both card-51 grantees carry force_if_51; a faction w/o an entry -> None.
    assert _event_instruction(C.BRITISH, 51) == "force_if_51"
    assert _event_instruction(C.PATRIOTS, 51) == "force_if_51"
    assert _event_instruction(C.PATRIOTS, 21) is None      # Patriots have no 21
    assert _event_instruction(C.BRITISH, None) is None


def test_battle_target_is_the_setup_space():
    # 5 Regulars in Boston, lone Militia in adjacent Massachusetts:
    # marching in sets up a winning Royalist Battle THERE.
    st = _state({
        "Massachusetts": {C.MILITIA_A: 1},
        "Boston": {C.REGULAR_BRI: 5},
    })
    assert bot_march_battle_target(st, C.BRITISH) == "Massachusetts"


def test_no_battle_target_when_no_enemy():
    st = _state({
        "Massachusetts": {},
        "Boston": {C.REGULAR_BRI: 5},
    })
    assert bot_march_battle_target(st, C.BRITISH) is None


def test_card51_free_march_planned_to_battle_space():
    """_plan_bot_free_op with card_id=51 sends the unpinned March to the
    battle-setup space; without the instruction it uses generic priorities."""
    st = _state({
        "Massachusetts": {C.MILITIA_A: 1},
        "Boston": {C.REGULAR_BRI: 5},
    })
    eng = Engine(initial_state=st)
    plan = eng._plan_bot_free_op(eng.state, C.BRITISH, "march", None, card_id=51)
    assert plan is not None
    assert plan["destinations"] == ["Massachusetts"]
    # Regulars actually route from Boston toward the battle space.
    assert "Boston" in plan["sources"]
