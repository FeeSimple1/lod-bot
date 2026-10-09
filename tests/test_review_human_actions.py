"""Review regressions: real human action paths and legal choices (§§3–4)."""
from copy import deepcopy
import pytest
from lod_ai import interactive_cli as cli, rules_consts as C
from lod_ai.engine import Engine
from lod_ai.state.setup_state import build_state, init_available
from lod_ai.util.caps import refresh_control
from lod_ai.commands import march
from lod_ai.special_activities import common_cause


def board(placements=None):
    state = build_state('1775', seed=4)
    state['spaces'] = {sid: {} for sid in state['spaces']}
    state['available'] = init_available()
    state['unavailable'] = {}
    state['casualties'] = {}
    state['leaders'] = {}
    state['support'] = {sid: C.NEUTRAL for sid in state['spaces']}
    state['resources'] = {f: 10 for f in (C.BRITISH, C.PATRIOTS, C.FRENCH, C.INDIANS)}
    for sid, pieces in (placements or {}).items():
        state['spaces'][sid].update(pieces)
        for tag, n in pieces.items():
            state['available'][tag] -= n
    refresh_control(state)
    return state


def menus(monkeypatch, singles=(), multiples=(), counts=()):
    single_it, multiple_it, count_it = iter(singles), iter(multiples), iter(counts)
    seen = []
    def one(prompt, options, **kwargs):
        choices = list(options)
        seen.append(prompt)
        answer = next(single_it)
        for label, value in choices:
            if label == answer:
                return value
        raise AssertionError((prompt, answer, [label for label, _ in choices]))
    def many(prompt, options, **kwargs):
        seen.append(prompt)
        answer = next(multiple_it)
        values = [value for _, value in options]
        assert all(v in values for v in answer), (prompt, answer, values)
        assert len(answer) >= kwargs.get('min_sel', 0)
        assert kwargs.get('max_sel') is None or len(answer) <= kwargs['max_sel']
        return answer
    def count(prompt, **kwargs):
        seen.append(prompt)
        answer = next(count_it)
        assert kwargs['min_val'] <= answer <= kwargs['max_val'], (prompt, answer, kwargs)
        return answer
    monkeypatch.setattr(cli, 'choose_one', one)
    monkeypatch.setattr(cli, 'choose_one_or_back', one)
    monkeypatch.setattr(cli, 'choose_multiple', many)
    monkeypatch.setattr(cli, 'choose_count', count)
    monkeypatch.setattr(cli, 'display_turn_context', lambda *a, **k: None)
    monkeypatch.setattr(cli, 'display_bot_summary', lambda *a, **k: None)
    return seen


def human(state, faction):
    engine = Engine(state)
    engine.set_human_factions({faction})
    result, legal, after, ctx = cli._human_decider(
        faction, {'id': 1}, engine._allowed_for_faction(faction, None), engine)
    assert legal
    return result, after, ctx


def test_special_before_command_funds_zero_resource_hortelez(monkeypatch):
    state = board()
    state['resources'][C.FRENCH] = 0
    seen = menus(monkeypatch,
        singles=['Command + Special Activity', 'Before the Command',
                 'Preparer la Guerre', 'RESOURCES', 'Hortelez'], counts=[1])
    result, after, ctx = human(state, C.FRENCH)
    assert after['resources'][C.FRENCH] == 1
    assert after['resources'][C.PATRIOTS] == 12
    assert result['used_special']
    assert seen.index('Select a Special Activity:') < seen.index('Select Command:')
    assert '_command_checkpoint' not in ctx


def test_special_after_command_sees_new_rally_militia(monkeypatch):
    state = board({'Virginia': {C.REGULAR_PAT: 1}})
    menus(monkeypatch,
        singles=['Command + Special Activity', 'After the Command',
                 'Rally', 'Place 1 Militia', 'Persuasion'],
        multiples=[['Virginia'], ['Virginia']])
    result, after, _ = human(state, C.PATRIOTS)
    assert result['used_special']
    assert after['spaces']['Virginia'].get(C.MILITIA_A) == 1
    assert after['resources'][C.PATRIOTS] == 10


def test_during_raid_plunder_pays_for_remaining_provinces(monkeypatch):
    provinces = ['Virginia', 'North_Carolina', 'South_Carolina']
    state = board({sid: {C.WARPARTY_U: 2} for sid in provinces})
    for sid in provinces:
        state['support'][sid] = C.PASSIVE_OPPOSITION
    state['resources'][C.INDIANS] = 1
    # Movement questions arise for all provinces, because neighboring WP exist.
    menus(monkeypatch,
        singles=['Command + Special Activity', 'During the Command', 'Raid', 'Continue Command',
                 'No', 'No', 'No', 'Continue Command',
                 'Execute Special Activity now', 'Plunder', 'Virginia'],
        multiples=[provinces])
    result, after, _ = human(state, C.INDIANS)
    assert result['used_special']
    assert all(after['support'][sid] == C.NEUTRAL for sid in provinces)
    assert after['resources'][C.INDIANS] == 0
    assert after['resources'][C.PATRIOTS] == 8


def test_command_only_cannot_move_common_cause_war_parties():
    state = board({'Massachusetts': {C.REGULAR_BRI: 1, C.WARPARTY_U: 1}})
    with pytest.raises(ValueError, match='Common Cause authorization'):
        march.execute(state, C.BRITISH, {}, [], ['Connecticut_Rhode_Island'],
            bring_escorts=True, move_plan=[{'src': 'Massachusetts',
                'dst': 'Connecticut_Rhode_Island',
                'pieces': {C.REGULAR_BRI: 1, C.WARPARTY_U: 1}}])


def test_common_cause_authorization_used_by_human_march(monkeypatch):
    state = board({'Massachusetts': {C.REGULAR_BRI: 1, C.WARPARTY_U: 1}})
    menus(monkeypatch,
        singles=['Command + Special Activity', 'Before the Command',
                 'Common Cause', 'March', 'Yes'],
        multiples=[['Massachusetts'], ['Connecticut_Rhode_Island'], ['Massachusetts']],
        counts=[1, 1, 1])
    result, after, _ = human(state, C.BRITISH)
    assert result['used_special']
    assert after['spaces']['Connecticut_Rhode_Island'][C.WARPARTY_A] == 1


@pytest.mark.parametrize('faction,pieces,activity,target', [
    (C.PATRIOTS, {C.MILITIA_U: 2, C.VILLAGE: 1}, 'Partisans', C.VILLAGE),
    (C.INDIANS, {C.WARPARTY_U: 2, C.FORT_PAT: 1}, 'War Path', C.FORT_PAT),
    (C.PATRIOTS, {C.REGULAR_PAT: 1, C.FORT_BRI: 1}, 'Skirmish', C.FORT_BRI),
    (C.BRITISH, {C.REGULAR_BRI: 1, C.FORT_PAT: 1}, 'Skirmish', C.FORT_PAT),
])
def test_option_three_only_targets_are_offered(monkeypatch, faction, pieces, activity, target):
    state = board({'Virginia': pieces})
    menus(monkeypatch, singles=[activity, 'Virginia', 'Option 3'])
    ctx = {}
    runner = cli._special_wizard(state, faction, ctx)
    runner(state, ctx)
    assert not state['spaces']['Virginia'].get(target)


def test_rally_bulk_recruitment_and_continental_promotion(monkeypatch):
    state = board({'Virginia': {C.FORT_PAT: 1, C.MILITIA_A: 2}})
    menus(monkeypatch, singles=['Place Militia up to Forts + Population', 'Virginia'],
          multiples=[['Virginia']], counts=[3, 2])
    engine = Engine(state)
    cli._rally_wizard(engine, C.PATRIOTS, False)(state, {})
    assert state['spaces']['Virginia'][C.MILITIA_U] == 3
    assert state['spaces']['Virginia'][C.REGULAR_PAT] == 2
    assert state['resources'][C.PATRIOTS] == 9


def test_rally_regroup_hides_without_moving(monkeypatch):
    state = board({'Virginia': {C.FORT_PAT: 1, C.MILITIA_A: 2}})
    menus(monkeypatch, singles=['Move Militia here and turn all Underground', 'No promotion'],
          multiples=[['Virginia']])
    engine = Engine(state)
    cli._rally_wizard(engine, C.PATRIOTS, False)(state, {})
    assert state['spaces']['Virginia'][C.MILITIA_U] == 2
    assert not state['spaces']['Virginia'].get(C.MILITIA_A)


def test_rabble_rousing_in_british_controlled_space(monkeypatch):
    state = board({'Virginia': {C.REGULAR_BRI: 2, C.MILITIA_U: 1}})
    menus(monkeypatch, multiples=[['Virginia']])
    cli._rabble_wizard(Engine(state), C.PATRIOTS, False)(state, {})
    assert state['support']['Virginia'] == C.PASSIVE_OPPOSITION
    assert state['spaces']['Virginia'][C.MILITIA_A] == 1


def test_british_march_city_network_is_available(monkeypatch):
    state = board({'Boston': {C.REGULAR_BRI: 1}})
    menus(monkeypatch, singles=['No'], multiples=[['Savannah'], ['Boston']], counts=[1])
    cli._march_wizard(Engine(state), C.BRITISH, False)(state, {})
    assert state['spaces']['Savannah'][C.REGULAR_BRI] == 1


def test_british_muster_can_recruit_in_empty_city(monkeypatch):
    state = board()
    menus(monkeypatch, singles=['Savannah', 'None'], multiples=[['Savannah']], counts=[2, 0])
    cli._muster_wizard(Engine(state), C.BRITISH, False)(state, {})
    assert state['spaces']['Savannah'][C.REGULAR_BRI] == 2


def test_limited_garrison_can_use_multiple_origins_and_displace(monkeypatch):
    state = board({'Boston': {C.REGULAR_BRI: 2}, 'New_York_City': {C.REGULAR_BRI: 2},
                   'Savannah': {C.MILITIA_U: 1}})
    menus(monkeypatch, singles=['Savannah', 'Georgia'],
          multiples=[['Savannah'], ['Boston', 'New_York_City']], counts=[2, 2])
    cli._garrison_wizard(Engine(state), C.BRITISH, True)(state, {})
    assert state['spaces']['Savannah'][C.REGULAR_BRI] == 4
    assert state['spaces']['Georgia'][C.MILITIA_A] == 1
    assert state['resources'][C.BRITISH] == 8


def test_no_special_activity_does_not_claim_one(monkeypatch):
    state = board({'Virginia': {C.REGULAR_PAT: 1}})
    menus(monkeypatch,
        singles=['Command + Special Activity', 'After the Command',
                 'Rally', 'Place 1 Militia', 'No Special Activity'],
        multiples=[['Virginia']])
    result, after, _ = human(state, C.PATRIOTS)
    assert result['used_special'] is False
    assert after['resources'][C.PATRIOTS] == 9


def test_during_sa_before_details_funds_zero_resource_hortelez(monkeypatch):
    state = board()
    state['resources'][C.FRENCH] = 0
    menus(monkeypatch,
        singles=['Command + Special Activity', 'During the Command', 'Hortelez',
                 'Execute Special Activity now', 'Preparer la Guerre', 'RESOURCES'],
        counts=[1])
    result, after, _ = human(state, C.FRENCH)
    assert result['used_special']
    assert after['resources'][C.FRENCH] == 1
    assert after['resources'][C.PATRIOTS] == 12


def test_mid_march_persuasion_can_flip_unit_that_has_not_moved_yet(monkeypatch):
    state = board({'Massachusetts': {C.REGULAR_PAT: 1}, 'Virginia': {C.MILITIA_U: 1}})
    menus(monkeypatch,
        singles=['Command + Special Activity', 'During the Command', 'March',
                 'Continue Command', 'No', 'Continue Command',
                 'Execute Special Activity now', 'Persuasion'],
        multiples=[['Boston', 'Norfolk'], ['Massachusetts'], ['Virginia'], ['Virginia']],
        counts=[1, 1])
    result, after, _ = human(state, C.PATRIOTS)
    assert result['used_special']
    assert after['spaces']['Norfolk'].get(C.MILITIA_A) == 1
    assert not after['spaces']['Virginia'].get(C.MILITIA_U)


def test_sa_removal_does_not_authorize_substitution_for_missing_planned_unit():
    state = board({'Virginia': {C.MILITIA_A: 1}})
    # A removed Underground piece is not an activated piece. Without an
    # actual SA flip credit the existing Active piece cannot replace it.
    with pytest.raises(ValueError, match='Not enough'):
        march.execute(state, C.PATRIOTS, {}, [], ['Norfolk'],
            move_plan=[{'src': 'Virginia', 'dst': 'Norfolk', 'pieces': {C.MILITIA_U: 1}}])


def test_march_cannot_move_an_arriving_cube_twice():
    state = board({'Boston': {C.REGULAR_BRI: 1}})
    with pytest.raises(ValueError, match='cannot March more than once'):
        march.execute(state, C.BRITISH, {}, [], ['Massachusetts', 'Connecticut_Rhode_Island'],
            move_plan=[{'src': 'Boston', 'dst': 'Massachusetts', 'pieces': {C.REGULAR_BRI: 1}},
                       {'src': 'Massachusetts', 'dst': 'Connecticut_Rhode_Island',
                        'pieces': {C.REGULAR_BRI: 1}}])


def test_sa_activation_does_not_erase_march_move_once_provenance():
    from lod_ai.special_activities import persuasion
    state = board({'Virginia': {C.MILITIA_U: 1}})
    def interrupt(s, ctx, label, sid):
        if label == 'After moving to March destination' and sid == 'North_Carolina':
            persuasion.execute(s, C.PATRIOTS, ctx, spaces=[sid])
    with pytest.raises(ValueError, match='unmoved units'):
        march.execute(state, C.PATRIOTS, {'_command_checkpoint': interrupt}, [],
            ['North_Carolina', 'South_Carolina'],
            move_plan=[{'src': 'Virginia', 'dst': 'North_Carolina', 'pieces': {C.MILITIA_U: 1}},
                       {'src': 'North_Carolina', 'dst': 'South_Carolina',
                        'pieces': {C.MILITIA_A: 1}}])
