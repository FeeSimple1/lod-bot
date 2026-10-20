"""Human-seat models need the whole public position, including empty spaces."""
from copy import deepcopy

from lod_ai import rules_consts as C
from lod_ai.cards.effects.brilliant_stroke import preparations_total
from lod_ai.llm.heuristic import parse_board
from lod_ai.llm.observation import serialize_state
from lod_ai.map.adjacency import population, space_type
from lod_ai.state.setup_state import build_state
from lod_ai.tools.invariants import _canonical


def _line(text, sid):
    return next(line for line in text.splitlines() if line.startswith(f"  {sid} "))


def test_empty_opposition_space_population_and_markers_are_visible():
    state = build_state("1775", seed=1)
    sid = next(sid for sid, space in state["spaces"].items()
               if population(sid) > 0 and not any(space.get(tag, 0) for tag in (
                   C.REGULAR_BRI, C.TORY, C.FORT_BRI, C.REGULAR_PAT, C.MILITIA_U,
                   C.MILITIA_A, C.FORT_PAT, C.REGULAR_FRE, C.WARPARTY_U,
                   C.WARPARTY_A, C.VILLAGE))
               and sid not in state.get("leaders", {}).values())
    state["support"][sid] = C.ACTIVE_OPPOSITION
    state["markers"][C.PROPAGANDA]["on_map"][sid] = 2
    state["markers"][C.RAID]["on_map"][sid] = 1
    observation = serialize_state(state, C.PATRIOTS)
    line = _line(observation, sid)
    assert "Active Opposition" in line
    assert f"Population={population(sid)}" in line
    assert "Propaganda=2" in line and "Raid=1" in line
    parsed = parse_board(observation)
    assert set(parsed) == set(state["spaces"])
    assert parsed[sid]["support"] == C.ACTIVE_OPPOSITION
    assert parsed[sid]["pieces"] == {}  # Metadata is not misread as pieces.


def test_blockades_and_all_piece_pools_are_public():
    state = build_state("1776", seed=1)
    sid = next(sid for sid in state["spaces"] if space_type(sid) == "City")
    state["markers"][C.BLOCKADE]["on_map"].add(sid)
    state["markers"][C.BLOCKADE]["pool"] = 1
    state["available"][C.REGULAR_FRE] = 4
    state["unavailable"][C.REGULAR_FRE] = 11
    state["casualties"][C.REGULAR_BRI] = 2
    text = serialize_state(state, C.FRENCH)
    assert "BLOCKADE" in _line(text, sid) and "Blockade=1" in _line(text, sid)
    assert "4 FrenchReg" in next(line for line in text.splitlines()
                                  if line.startswith("Available pieces:"))
    assert "11 FrenchReg" in next(line for line in text.splitlines()
                                   if line.startswith("Unavailable pieces:"))
    assert "2 BritReg" in next(line for line in text.splitlines()
                               if line.startswith("Casualties pieces:"))
    assert "Markers available: Propaganda=12, Raid=12" in text
    assert "Squadrons/Blockades: West Indies=1, on Cities=1" in text


def test_preparations_use_available_naval_counters_and_correct_cbc_weight():
    state = build_state("1775", seed=1)
    sid = next(sid for sid in state["spaces"] if space_type(sid) == "City")
    state["available"][C.REGULAR_FRE] = 4
    state["markers"][C.BLOCKADE].update(pool=2, on_map={sid})
    state["unavailable"][C.BLOCKADE] = 99  # Must not contribute to Preparations.
    state["cbc"] = 5
    text = serialize_state(state, C.FRENCH)
    assert preparations_total(state) == 12
    assert preparations_total(state, nonplayer=True) == 9
    assert "French Preparations: player/full CBC=12, Non-player/half CBC=9" in text
    assert "Treaty of Alliance threshold > 15" in text


def test_solitaire_objective_does_not_promise_a_human_victory_phase_win():
    state = build_state("1775", seed=1)
    state["human_factions"] = {C.FRENCH}
    state["player_factions"] = [[C.FRENCH]]
    text = serialize_state(state, C.FRENCH)
    assert "both must be > 0 to win at a check" not in text
    assert "lone human player never wins a Victory Phase" in text
    assert "lead 1-5 is a stalemate; lead 6+ is player victory" in text
    assert "French victory also requires Treaty of Alliance" in text
    assert "FRENCH=ineligible before Treaty of Alliance" in text
    state["toa_played"] = True
    assert "FRENCH=ineligible before Treaty of Alliance" not in serialize_state(state)


def test_player_ownership_and_optional_solo_difficulty_are_respected():
    state = build_state("1778", seed=1)
    state["human_factions"] = {C.PATRIOTS, C.FRENCH}
    state["player_factions"] = [[C.PATRIOTS, C.FRENCH]]
    state["solo_difficulty"] = True
    text = serialize_state(state)
    assert "One-player rules (8.8)" in text
    assert "Greater challenge enabled: from the second Winter Quarters" in text
    state["player_factions"] = [[C.PATRIOTS], [C.FRENCH]]
    assert "One-player rules (8.8)" not in serialize_state(state)


def test_observation_preserves_occupied_piece_parsing_and_hides_future_deck():
    state = build_state("1775", seed=1)
    state["deck"] = [{"id": 999, "title": "UNREVEALED CARD SECRET"}]
    state["rng_log"] = ["HIDDEN FUTURE RANDOMNESS"]
    before = _canonical(deepcopy(state))
    rng_before = state["rng"].getstate()
    text = serialize_state(state, C.PATRIOTS)
    parsed = parse_board(text)
    for sid, space in state["spaces"].items():
        assert parsed[sid]["pieces"].get("BritReg", 0) == space.get(C.REGULAR_BRI, 0)
        assert parsed[sid]["pieces"].get("Militia(U)", 0) == space.get(C.MILITIA_U, 0)
    assert "UNREVEALED CARD SECRET" not in text
    assert "HIDDEN FUTURE RANDOMNESS" not in text
    assert _canonical(state) == before
    assert state["rng"].getstate() == rng_before


def test_rendering_preparations_does_not_initialize_sparse_state_markers():
    state = build_state("1775", seed=1)
    state.pop("markers")
    before = _canonical(state)
    serialize_state(state)
    assert _canonical(state) == before
