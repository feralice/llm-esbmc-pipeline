import json

from research_pipeline.maintenance.refusals import normalize_reason, triage


def report(path, model, results):
    path.write_text(json.dumps({'config': {'model': model}, 'results': results}))
    return path


def item(reason, function='f', program='program.py', verdict='LLM_ONLY'):
    return {'reason': reason, 'verdict': verdict, 'program_path': program,
            'hypothesis': {'function': function, 'file': 'module.py'}}


def test_same_refusal_with_different_paths_and_lines_has_one_signature():
    a = 'ERROR: TypeError at /tmp/programs/232b413943df_a2.py 227: list indices must be integers, not str'
    b = 'ERROR: TypeError at /other/programs/abcdef123456_a3.py 82: list indices must be integers, not str'
    assert normalize_reason(a) == normalize_reason(b)


def test_known_signature_is_not_new(tmp_path):
    reason = 'ERROR: unsupported: async syntax'
    path = report(tmp_path / 'scan.json', 'm1', [item(reason)])
    result = triage([path], {normalize_reason(reason): {'issue': '#42'}})
    assert len(result['known']) == 1
    assert result['new'] == []
    assert result['known'][0]['registry']['issue'] == '#42'


def test_new_signature_keeps_the_program_and_runs_the_search_once(tmp_path):
    reason = 'ERROR: unsupported: async syntax'
    path = report(tmp_path / 'scan.json', 'm1', [item(reason, 'f', 'a.py'), item(reason, 'g', 'b.py')])
    queries = []
    result = triage([path], {}, search=lambda q: queries.append(q) or [{'number': 12}])
    entry, = result['new']
    assert entry['count'] == 2
    assert {x['program'] for x in entry['occurrences']} == {'a.py', 'b.py'}
    assert {x['function'] for x in entry['occurrences']} == {'f', 'g'}
    assert len(queries) == 1
    assert entry['possible_issues'] == [{'number': 12}]


def test_reports_from_different_models_are_not_merged(tmp_path):
    reason = 'ERROR: unsupported: async syntax'
    a = report(tmp_path / 'a.json', 'm1', [item(reason)])
    b = report(tmp_path / 'b.json', 'm2', [item(reason)])
    result = triage([a, b], {})
    assert len(result['new']) == 2
    assert set(result['by_model']) == {'m1', 'm2'}


def test_explicit_unsupported_is_kept_but_other_reasons_are_excluded(tmp_path):
    reason = 'UNSUPPORTED: ERROR: subscripting a value whose type is not known is not supported'
    path = report(tmp_path / 'scan.json', 'm', [item(reason), item('remote connection failed', verdict='PIPELINE_ERROR'), item('unknown')])
    result = triage([path], {})
    assert len(result['new']) == 1
    assert result['new'][0]['signature'] == normalize_reason(reason)


def test_models_missing_from_distinct_reports_are_not_assumed_equal(tmp_path):
    a = report(tmp_path / 'a.json', '', [item('ERROR: unsupported: async')])
    b = report(tmp_path / 'b.json', '', [item('ERROR: unsupported: async')])
    assert len(triage([a, b], {})['by_model']) == 2
