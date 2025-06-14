import pytest

from lod_ai.economy import resources
from lod_ai import rules_consts as C


def make_state(amount):
    return {"resources": {C.BRITISH: amount}}


def test_add_respects_cap():
    state = make_state(resources.MAX_RESOURCES - 1)
    resources.add(state, C.BRITISH, 5)
    assert state["resources"][C.BRITISH] == resources.MAX_RESOURCES


def test_spend_reduces_resources():
    state = make_state(10)
    resources.spend(state, C.BRITISH, 4)
    assert state["resources"][C.BRITISH] == 6


def test_spend_raises_when_insufficient():
    state = make_state(3)
    with pytest.raises(ValueError):
        resources.spend(state, C.BRITISH, 5)


def test_can_afford():
    state = make_state(5)
    assert resources.can_afford(state, C.BRITISH, 5)
    assert not resources.can_afford(state, C.BRITISH, 6)
