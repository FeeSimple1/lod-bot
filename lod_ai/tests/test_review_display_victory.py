"""Rules/CLI regressions from the October 2026 project review."""
from copy import deepcopy
import json
from importlib.resources import files

import pytest

from lod_ai import rules_consts as C
from lod_ai import victory
from lod_ai.cli_display import (display_board_state, display_card,
    display_bot_summary, display_brilliant_strokes, display_turn_context, _snapshot_state)
from lod_ai import cli_utils
from lod_ai.state.setup_state import build_state


def test_every_card_printed_effect_is_visible(capsys):
    cards = json.loads((files('lod_ai.cards') / 'data.json').read_text())
    for card in cards:
        display_card(card)
        output = capsys.readouterr().out
        for key in ('unshaded_event', 'shaded_event', 'effect'):
            if card.get(key):
                assert card[key] in output, (card['id'], key)


def test_turn_context_repeats_complete_current_and_upcoming_card(capsys):
    state = build_state('1776')
    state['upcoming_card'] = {'id': 97, 'title': 'Winter Quarters',
                              'winter_quarters': True, 'effect': 'A reset effect.'}
    display_turn_context(C.PATRIOTS, state, card={'title': 'Current',
                          'unshaded_event': 'Current full effect.'})
    out = capsys.readouterr().out
    assert 'A reset effect.' in out
    assert 'Current full effect.' in out


def test_brilliant_strokes_print_french_and_treaty_effects(capsys):
    state = build_state('1775')
    display_brilliant_strokes(state, C.FRENCH)
    output = capsys.readouterr().out
    assert 'Execute two free Limited Commands' in output
    assert 'French may choose to enter the war' in output


def test_board_and_victory_share_weighted_blockade_calculation(capsys):
    state = build_state('1776')
    state['support'] = {'Boston': 2, 'Virginia': -2, 'New_York_City': -2}
    state['markers'][C.BLOCKADE]['on_map'] = {'Boston', 'New_York_City'}
    totals = victory._summarize_board(state)
    # §1.9 suppresses Support, not Opposition, in a Blockaded City.
    from lod_ai.map.adjacency import population
    expected_opp = 2 * (population('Virginia') + population('New_York_City'))
    assert totals['support'] == 0
    assert totals['opposition'] == expected_opp
    display_board_state(state)
    board = capsys.readouterr().out
    cli_utils.set_game_state(state)
    cli_utils._handle_meta_command('victory')
    output = capsys.readouterr().out
    for rendered in (board, output):
        assert f'Support Total: 0  |  Opposition Total: {expected_opp}' in rendered


def test_french_preparations_use_live_pieces_cbc_and_available_naval(capsys):
    state = build_state('1776')
    before = deepcopy(state)
    display_board_state(state)
    out = capsys.readouterr().out
    assert 'French Preparations: 9' in out
    assert 'French Non-player Preparations (half CBC): 8' in out
    assert state['markers'] == before['markers']
    assert 'french_preparations' not in state


def test_empty_display_does_not_add_marker_structures(capsys):
    state = {'spaces': {'Boston': {}}, 'support': {'Boston': 1}}
    before = deepcopy(state)
    display_board_state(state)
    assert state == before


def test_summary_exposes_piece_pool_marker_leader_eligibility_changes(capsys):
    state = build_state('1775')
    snap = _snapshot_state(state)
    state['spaces']['Virginia'][C.MILITIA_U] = 4
    state['available'][C.MILITIA_U] = 3
    state['leaders']['LEADER_WASHINGTON'] = 'Virginia'
    state['markers'][C.RAID]['on_map']['Virginia'] = 2
    state['eligible'][C.PATRIOTS] = False
    state['toa_played'] = True
    display_bot_summary(C.PATRIOTS, state, snap)
    output = capsys.readouterr().out
    for text in ('Pieces at Virginia', 'Mil(U)', 'Available', 'Leaders',
                 'LEADER_WASHINGTON', 'Markers', 'Virginia', 'Eligibility',
                 'Treaty of Alliance played'):
        assert text in output
    assert snap['markers'][C.RAID]['on_map'].get('Virginia') is None


def test_cards_and_board_meta_commands(capsys):
    state = build_state('1776')
    state['current_card'] = {'id': 97, 'title': 'WQ', 'effect': 'Reset effect'}
    cli_utils.set_game_state(state)
    assert cli_utils._handle_meta_command('cards')
    assert 'Reset effect' in capsys.readouterr().out
    assert cli_utils._handle_meta_command('board')
    assert 'BOARD STATE' in capsys.readouterr().out


def _solo(faction=C.PATRIOTS, forts=0, villages=0):
    return {'spaces': {'Virginia': {C.FORT_PAT: forts, C.VILLAGE: villages}},
            'support': {}, 'cbc': 0, 'crc': 0, 'toa_played': True,
            'human_factions': {faction}, 'history': []}


def test_solo_human_cannot_win_during_victory_check():
    state = build_state('1775')
    state['human_factions'] = {C.BRITISH}
    state['support'] = {s: 2 for s in state['spaces']}
    state['crc'] = 1
    state['cbc'] = 0
    assert victory._british_margin(victory._summarize_board(state))[0] > 0
    assert victory.check(state) is False


@pytest.mark.parametrize('forts,villages,expected', [(0, 2, 'stalemate'),
    (2, 0, 'stalemate'), (3, 0, 'victory')])
def test_solo_final_scoring_stalemate_and_six_point_win(forts, villages, expected):
    state = _solo(forts=forts, villages=villages)
    victory.final_scoring(state)
    assert state['victory_result']['outcome'] == expected
    assert state['victory_result']['winner'] == (C.PATRIOTS if expected == 'victory' else None)


def test_solo_tie_loses_to_nonplayer():
    state = _solo()
    state['crc'] = 3
    victory.final_scoring(state)
    assert state['victory_result']['winner'] == C.BRITISH
    assert state['victory_result']['human_won'] is False


def test_shared_player_scores_lower_faction_margin():
    state = _solo(forts=8)
    state['human_factions'] = {C.PATRIOTS, C.FRENCH}
    state['player_factions'] = [[C.PATRIOTS, C.FRENCH]]
    state['cbc'] = 2
    victory.final_scoring(state)
    assert state['victory_result']['gap'] == 4  # min(11,2) - max(-2,-11)
    assert state['victory_result']['outcome'] == 'stalemate'


def test_separate_humans_are_not_silently_treated_as_solo():
    state = _solo(forts=8)
    state['human_factions'] = {C.PATRIOTS, C.FRENCH}
    victory.final_scoring(state)
    assert state['victory_result']['winner'] == C.PATRIOTS
    assert 'gap' not in state['victory_result']


def test_french_without_treaty_cannot_win_solo():
    state = _solo(C.FRENCH)
    state['toa_played'] = False
    state['cbc'] = 30
    victory.final_scoring(state)
    assert state['victory_result']['winner'] != C.FRENCH
    assert state['victory_result']['human_won'] is False


def test_combined_victory_check_requires_both_factions():
    state = build_state('1775')
    state['human_factions'] = {C.BRITISH, C.INDIANS, C.PATRIOTS}
    state['player_factions'] = [[C.BRITISH, C.INDIANS], [C.PATRIOTS]]
    state['support'] = {s: 2 for s in state['spaces']}
    state['crc'] = 1
    for sp in state['spaces'].values():
        sp[C.VILLAGE] = 0
    assert victory.check(state) is False
    state['spaces']['Northwest'][C.VILLAGE] = 10
    assert victory.check(state) is True
    assert state['victory_result']['winner'] == 'BRITISH + INDIANS'


def test_solo_difficulty_begins_with_second_winter_quarters():
    state = _solo(C.BRITISH)
    state['solo_difficulty'] = True
    state['winter_quarters_count'] = 1
    assert victory.check(state) is False
    state['winter_quarters_count'] = 2
    assert victory.check(state) is True
    assert state['victory_result']['winner'] == C.PATRIOTS


def test_setup_records_combined_side_as_one_player(monkeypatch):
    from lod_ai.interactive_cli import _choose_players
    answers = iter(['1', '5'])
    monkeypatch.setattr('builtins.input', lambda prompt='': next(answers))
    assert _choose_players() == [[C.BRITISH, C.INDIANS]]


def test_structured_stalemate_reaches_game_report():
    from lod_ai.interactive_cli import _detect_winner
    state = _solo(forts=2)
    victory.final_scoring(state)
    stats = {}
    _detect_winner(stats, state)
    assert stats['winner'] == 'Stalemate'
    assert stats['victory_type'] == 'final_scoring'
