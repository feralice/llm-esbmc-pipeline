import pytest

from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay


def program(source, line=2):
    return Program(source, 0, ((line, line),), (), (1, line))


def test_exhaustive_replay_keeps_chosen_values_including_implicit_defaults():
    p = program('def f(s, n):\n    return s[n]\n\nf(nondet_str(), nondet_int())\n')
    r = concrete_replay(p, 'f')
    assert r.status == 'reproduced'
    assert getattr(r, 'inputs', None) == ['', 0]
    assert r.to_dict()['inputs'] == ['', 0]


def test_seeded_replay_keeps_values_rather_than_domain_indices():
    p = program('def f(n):\n    return 1 // (n - 8)\n\nf(nondet_int())\n')
    r = concrete_replay(p, 'f', seeds={'int': [8]})
    assert getattr(r, 'inputs', None) == [8]


def test_fixed_replay_does_not_search_after_the_supplied_input_passes():
    p = program('def f(n):\n    return 1 // n\n\nf(nondet_int())\n')
    r = concrete_replay(p, 'f', inputs=[2], random_runs=300)
    assert (r.status, r.runs) == ('not_reproduced', 1)


def test_fixed_replay_can_reproduce_an_input_outside_the_search_domains():
    p = program('def f(n):\n    return 1 // (n - 37)\n\nf(nondet_int())\n')
    r = concrete_replay(p, 'f', inputs=[37])
    assert (r.status, r.inputs, r.runs) == ('reproduced', [37], 1)


@pytest.mark.parametrize('inputs', [[], [True], ['x'], [0, 1]])
def test_inconsistent_fixed_sequence_is_unavailable(inputs):
    p = program('def f(n):\n    return 1 // n\n\nf(nondet_int())\n')
    assert concrete_replay(p, 'f', inputs=inputs).status == 'unavailable'


def test_empty_fixed_sequence_is_valid_for_a_program_without_nondet():
    p = program('def f():\n    return 1 // 0\n\nf()\n')
    r = concrete_replay(p, 'f', inputs=[])
    assert (r.status, r.inputs, r.runs) == ('reproduced', [], 1)


def test_list_records_argument_length_and_elements_and_replays_exactly():
    p = program('def f(xs):\n    return 1 // (len(xs) - 2)\n\nf(nondet_list(3, elem_type=nondet_str()))\n')
    r = concrete_replay(p, 'f')
    assert r.status == 'reproduced'
    assert getattr(r, 'inputs', None) == ['', 2, '', '']
    assert concrete_replay(p, 'f', inputs=r.inputs).status == 'reproduced'
    assert concrete_replay(p, 'f', inputs=['', 4, '', '', '', '']).status == 'unavailable'


def test_fixed_input_still_obeys_assumptions():
    p = program('def f(n):\n    return 1 // n\n\nn = nondet_int()\n__ESBMC_assume(n != 0)\nf(n)\n')
    assert concrete_replay(p, 'f', inputs=[0]).status == 'not_reproduced'
