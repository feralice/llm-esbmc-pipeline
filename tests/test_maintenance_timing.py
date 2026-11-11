import json

from research_pipeline.maintenance.timing import collect_timings, summarize


def test_rows_without_a_bound_are_counted_as_missing_not_zero(tmp_path):
    report = tmp_path / 'report.json'
    report.write_text(json.dumps({'config': {'model': 'example'}, 'results': [
        {'hypothesis': {'function': 'f'}, 'seconds': 18, 'verdict': 'ESBMC_TIMEOUT',
         'attempts': [{'attempt': 0, 'esbmc_status': 'timeout'},
                      {'attempt': 1, 'unwind': 5, 'esbmc_status': 'no_violation_found'}]}
    ]}))
    rows = collect_timings([report])
    assert rows[0]['bound'] is None
    assert rows[0]['seconds'] is None
    assert rows[0]['hypothesis_seconds'] == 18
    assert rows[1]['bound'] == 5
    summary = summarize(rows)
    assert summary['missing_bound'] == 1
    assert summary['missing_seconds'] == 2
    assert summary['by_bound'][5]['timeouts'] == 0
    assert summary['by_bound'][5]['measured_statuses'] == 1


def test_timeout_rate_uses_attempt_status_and_excludes_unknown_status():
    rows = [{'bound': 5, 'seconds': None, 'attempt_status': 'timeout'},
            {'bound': 5, 'seconds': 4, 'attempt_status': 'violation_found'},
            {'bound': 5, 'seconds': None, 'attempt_status': None}]
    result = summarize(rows)['by_bound'][5]
    assert result['timeouts'] == 1
    assert result['measured_statuses'] == 2
    assert result['timeout_rate'] == 0.5
    assert result['missing_status'] == 1


def test_no_attempt_is_recorded_without_inventing_a_bound(tmp_path):
    path = tmp_path / 'report.json'
    path.write_text(json.dumps({'config': {}, 'results': [{'hypothesis': {'function': 'g'},
                    'seconds': 5, 'verdict': 'LLM_ONLY', 'attempts': []}]}))
    rows = collect_timings([path])
    assert len(rows) == 1
    assert rows[0]['bound'] is None
    assert rows[0]['attempt_status'] is None
    assert rows[0]['model'] is None
