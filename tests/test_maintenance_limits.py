
import pytest

from research_pipeline.maintenance.limits import (
    compare_baseline,
    diff_outcomes,
    run_limits,
)
from research_pipeline.models import ESBMCDirectResult


def result(path, status, output='', returncode=0):
    return ESBMCDirectResult(str(path), status, [], returncode, '', stdout=output)


def test_crash_is_classified_apart_from_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.limits.esbmc_identity', lambda command: {'version': 'ESBMC version 8.6.0'})
    outputs = {
        '01_crash.py': ('tool_error', 'ESBMC caught SIGSEGV', 1),
        '02_refused.py': ('tool_error', 'ERROR: feature not supported', 1),
        '03_success.py': ('no_violation_found', 'VERIFICATION SUCCESSFUL', 0),
        '04_timeout.py': ('timeout', '', None),
        '12_incremental.py': ('violation_found', 'VERIFICATION FAILED', 1),
    }
    calls = {}
    for name in outputs:
        (tmp_path / name).touch()

    def runner(path, **kwargs):
        calls[path.name] = kwargs
        return result(path, *outputs[path.name])

    found = run_limits(['esbmc'], tmp_path, runner=runner)
    assert [found[name]['outcome'] for name in outputs] == ['crash', 'refused', 'successful', 'timeout', 'failed']
    assert calls['01_crash.py']['bound_flags'] == ['--unwind', '5']
    assert calls['01_crash.py']['extra_flags'] == ['--no-pointer-check', '--no-align-check']
    assert calls['12_incremental.py']['bound_flags'] == ['--incremental-bmc', '--max-k-step', '5']
    assert calls['12_incremental.py']['multi_property'] is True


def test_diff_reports_a_refusal_that_became_successful_as_changed_not_fixed(tmp_path):
    old = {'a.py': {'outcome': 'refused', 'detail': 'unsupported'}, 'b.py': {'outcome': 'failed', 'detail': 'old'}}
    new = {'a.py': {'outcome': 'successful', 'detail': ''}, 'b.py': {'outcome': 'failed', 'detail': 'different'}}
    diff = diff_outcomes(old, new)
    assert diff == {'changed': ['a.py'], 'unchanged': ['b.py'], 'added': [], 'removed': []}
    report = compare_baseline(tmp_path / 'baseline.json', new, identity={'version': 'v'})
    assert report['comparison'] is None
    (tmp_path / 'baseline.json').write_text(__import__('json').dumps({'identity': {}, 'outcomes': old}))
    report = compare_baseline(tmp_path / 'baseline.json', new, identity={'version': 'v'})
    assert 'mudou, conferir' in report['message']
    assert 'corrigido' not in report['message']


def test_missing_baseline_writes_it_and_compares_nothing(tmp_path):
    path = tmp_path / 'baseline.json'
    outcomes = {'a.py': {'outcome': 'refused', 'detail': 'unsupported'}}
    report = compare_baseline(path, outcomes, identity={'version': 'v'})
    assert path.is_file()
    assert report['comparison'] is None
    assert 'sem comparação' in report['message']


def test_missing_esbmc_stops_before_runner(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.limits.esbmc_identity', lambda command: {'version': 'unavailable: FileNotFoundError'})
    (tmp_path / '01_case.py').touch()
    with pytest.raises(RuntimeError, match='ESBMC'):
        run_limits(['missing'], tmp_path, runner=lambda *a, **k: pytest.fail('não deve executar'))


def test_filename_containing_crash_marker_does_not_override_success(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.limits.esbmc_identity', lambda command: {'version': 'ESBMC version 8.6.0'})
    (tmp_path / '75_irep2.py').touch()

    def runner(path, **kwargs):
        return result(path, 'no_violation_found', f'Parsing {path}\nVERIFICATION SUCCESSFUL', 0)

    assert run_limits(['esbmc'], tmp_path, runner=runner)['75_irep2.py']['outcome'] == 'successful'


def test_failed_records_the_violated_property(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.limits.esbmc_identity', lambda command: {'version': 'ESBMC version 8.6.0'})
    (tmp_path / '01_case.py').touch()

    def runner(path, **kwargs):
        return result(path, 'violation_found', 'Violated property:\n  assertion x != 0\nVERIFICATION FAILED', 1)

    assert run_limits(['esbmc'], tmp_path, runner=runner)['01_case.py']['detail'] == 'assertion x != 0'


def test_unchanged_baseline_does_not_claim_results_changed(tmp_path):
    path = tmp_path / 'baseline.json'
    outcomes = {'a.py': {'outcome': 'successful', 'detail': ''}}
    compare_baseline(path, outcomes, identity={'version': 'v'})
    report = compare_baseline(path, outcomes, identity={'version': 'v'})
    assert 'mudou' not in report['message']
    assert 'sem mudança' in report['message']


def test_limits_stop_if_windows_disk_is_nearly_full(tmp_path, monkeypatch):
    import shutil
    from types import SimpleNamespace

    monkeypatch.setattr('research_pipeline.maintenance.limits.esbmc_identity', lambda command: {'version': 'ESBMC version 8.6.0'})
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=1))
    (tmp_path / '01_case.py').touch()
    with pytest.raises(RuntimeError, match='espaço'):
        run_limits(['esbmc'], tmp_path, runner=lambda *a, **k: pytest.fail('não executar'))
