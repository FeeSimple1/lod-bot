from lod_ai.cards import CARD_REGISTRY, EVENT_HANDLERS

def test_loader_sizes():
    assert len(CARD_REGISTRY) == 109
    assert len(EVENT_HANDLERS) == 109        # after stubbing all

def test_common_sense_shaded(tmp_state):
    from bots.common import play_event      # once you add it
    before = tmp_state.snapshot()
    play_event(tmp_state, 2, "Patriots")    # shaded branch
    assert tmp_state != before