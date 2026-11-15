from dataclasses import replace
from types import SimpleNamespace

import pytest

from research_pipeline.scan.pipeline import _detection_fingerprint, execute_scan, plan_scan
from test_scan_pipeline import _fake_verify


@pytest.mark.parametrize('enabled,second,count', [
    (True, '    return x[0]\n', 1),
    (True, '    # different comment\n    return x[0]\n', 1),
    (True, '    "different docstring"\n    return x[0]\n', 1),
    (True, '    return x[1]\n', 2),
    (False, '    return x[0]\n', 2),
])
def test_dedupe_verifies_only_identical_ast(tmp_path, enabled, second, count):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'b.py').write_text('def f(x):\n' + second)
    (root / 'a.py').write_text('def f(x):\n    return x[0]\n')
    plan = plan_scan(root, tmp_path / 'out', dedupe=enabled)
    plan.targets.reverse()
    analyzer = SimpleNamespace(analyze=lambda u: [SimpleNamespace(
        verifiable=True, explanation='IndexError', metadata={'expression': 'x[ 0 ]' if u.path.name == 'a.py' else 'x[0]'})])
    calls = []
    report = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify(calls))
    assert len(calls[0]['hypotheses']) == count
    assert report['detection']['hypotheses'] == count
    if enabled:
        groups = report['detection']['duplicates']
        assert len(groups) == 2 - count
        if groups:
            assert groups[0]['representante']['file'].endswith('/a.py')
            assert groups[0]['duplicatas'][0]['file'].endswith('/b.py')
            for filename in ('scan_summary.md', 'relatorio.md'):
                text = (plan.output_dir / filename).read_text()
                assert '2 hipóteses em 2 funções idênticas, verificadas 1 vez' in text
                assert 'b.py' in text and 'CONFIRMED' in text
        plan.targets.reverse()
        second_report = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]))
        assert second_report['detection']['duplicates'] == groups
    else:
        assert 'duplicates' not in report['detection']
        assert 'dedupe' not in plan.to_dict()
        assert _detection_fingerprint(plan, '') != _detection_fingerprint(replace(plan, dedupe=True), '')


def test_offline_measurement_reports_missing_sources(tmp_path):
    import json
    import runpy
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / 'scripts/medir_dedupe.py'
    measure = runpy.run_path(str(script))['measure']
    report = tmp_path / 'scan_report.json'
    report.write_text(json.dumps({'results': [{'hypothesis': {'file': str(tmp_path / 'missing.py'),
        'function': 'f', 'suspect_expression': 'x[0]'}}]}))
    result = measure(report)
    assert result['hypotheses'] == result['representatives'] == result['unresolved_sources'] == 1
    assert result['collapsed'] == 0
