import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

import main
from research_pipeline.scan.pipeline import _detection_fingerprint, execute_scan, plan_scan
from test_scan_pipeline import _fake_verify


class Analyzer:
    model = 'fake'

    def __init__(self, still_missing=False):
        self.units = []
        self.still_missing = still_missing

    def analyze(self, unit):
        self.units.append(unit)
        note = 'helper, which is not shown' if len(self.units) == 1 or self.still_missing else 'IndexError'
        return [SimpleNamespace(verifiable=True, explanation=note, metadata={'expression': 'helper(x)'})]


def make_plan(tmp_path, *, helper=True, **kwargs):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'm.py').write_text('def f(x):\n    return helper(x)\n' +
                               ('\ndef helper(x):\n    return x[0]\n' if helper else ''))
    return plan_scan(repo, tmp_path / 'out', only=('f',), prefilter=True, **kwargs)


@pytest.mark.parametrize('enabled,helper,missing,calls', [
    (False, True, False, 1), (True, True, False, 2),
    (True, False, False, 1), (True, True, True, 2),
])
def test_context_retry(tmp_path, enabled, helper, missing, calls):
    plan = make_plan(tmp_path, helper=helper, context_retry=enabled)
    analyzer = Analyzer(missing)
    report = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]))
    assert len(analyzer.units) == calls
    row = report['detection']['functions_detail'][0]
    if calls == 2:
        assert 'def helper(x)' in analyzer.units[1].caller_context
        assert 'm.py:4' in analyzer.units[1].caller_context
        assert row['held'][0]['retried'] is True
        assert bool(row['candidates']) is not missing
        assert len(row['held']) == (2 if missing else 1)
    else:
        assert len(row['held']) == 1 and 'retried' not in row['held'][0]
    execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]), resume=True)
    assert len(analyzer.units) == calls
    saved = json.loads((plan.output_dir / 'scan_checkpoint.json').read_text())
    state = saved['detection'][plan.targets[0].key]
    assert {k: state[k] for k in ('error', 'candidates', 'held')} == {
        k: row[k] for k in ('error', 'candidates', 'held')}
    assert not state.get('context_retry_pending')


@pytest.mark.parametrize("prefilter", [False, True])
def test_disabled_fingerprint_is_legacy(tmp_path, prefilter):
    from research_pipeline.scan.pipeline import _hash, _prompts_hash
    plan = make_plan(tmp_path, context_retry=False)
    plan.prefilter = prefilter
    legacy = _hash({'root': str(plan.root), 'variants': plan.variants, 'model': 'fake', 'focus': plan.focus,
                    'prompts': _prompts_hash(plan), 'targets': [t.key for t in plan.targets],
                    **({'prefilter': True} if prefilter else {})})
    assert _detection_fingerprint(plan, 'fake') == legacy
    assert 'context_retry' not in plan.to_dict()
    assert 'dedupe' not in plan.to_dict()
    assert _detection_fingerprint(replace(plan, context_retry=True), 'fake') != legacy


def test_cli_retry_requires_prefilter(tmp_path, monkeypatch, capsys):
    import sys
    monkeypatch.setattr(sys, 'argv', ['main.py', '--mode', 'scan', '--input', str(tmp_path),
                                     '--scan-context-retry'])
    assert main.main() == 1
    assert '--scan-prefilter' in capsys.readouterr().err


def test_retry_history_is_visible_in_reports(tmp_path):
    plan = make_plan(tmp_path, context_retry=True)
    execute_scan(plan, analyzer=Analyzer(), spec_llm=None, verify=_fake_verify([]))
    for filename in ('scan_summary.md', 'relatorio.md'):
        text = (plan.output_dir / filename).read_text()
        assert 'refeita com definições' in text
        assert 'helper(x)' in text


@pytest.mark.parametrize('limited', [False, True])
def test_retry_failure_saves_first_response_and_resume_only_retries_enriched_call(tmp_path, limited):
    from research_pipeline.llm.rate_limit import UsageLimitReached

    plan = make_plan(tmp_path, context_retry=True)
    analyzer = Analyzer()
    original = analyzer.analyze

    def interrupted(unit):
        if len(analyzer.units) == 1:
            analyzer.units.append(unit)
            if limited:
                raise UsageLimitReached('quota')
            raise RuntimeError('temporary failure')
        return original(unit)

    analyzer.analyze = interrupted
    if limited:
        with pytest.raises(UsageLimitReached):
            execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]))
    else:
        report = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]))
        assert report['detection']['failed'] == 1
    saved = json.loads((plan.output_dir / 'scan_checkpoint.json').read_text())
    state = saved['detection'][plan.targets[0].key]
    assert state['held'][0]['expression'] == 'helper(x)'
    analyzer.analyze = original
    resumed = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=_fake_verify([]), resume=True)
    assert len(analyzer.units) == 3
    assert 'def helper(x)' in analyzer.units[-1].caller_context
    assert resumed['detection']['failed'] == 0
    assert resumed['detection']['hypotheses'] == 1


def test_retry_fingerprint_changes_when_helper_changes(tmp_path):
    plan = make_plan(tmp_path, context_retry=True)
    before = _detection_fingerprint(plan, 'fake')
    source = plan.root / 'm.py'
    source.write_text(source.read_text().replace('return x[0]', 'return x[999]'))
    after = plan_scan(plan.root, plan.output_dir, only=('f',), prefilter=True, context_retry=True)
    assert _detection_fingerprint(after, 'fake') != before


def test_definition_priority_and_limit(tmp_path):
    from research_pipeline.scan.context_retry import MAX_RETRY_DEFINITION_CHARS, retry_context

    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'm.py').write_text('class C:\n    def f(self, x):\n        return self.helper(x)\n'
                                '    def helper(self, x):\n        return x[0]\n'
                                '\ndef helper(x):\n    return x[1]\n')
    for name in ('a', 'b', 'c'):
        (root / f'{name}.py').write_text('def helper(x):\n    return x[2]\n')
    plan = plan_scan(root, tmp_path / 'out', only=('C.f',), prefilter=True, context_retry=True)
    context = retry_context(plan.graph, plan.targets[0], [{
        'expression': 'self.helper(x)', 'reason': 'requested (missing context)'}])
    assert context.count('Definition from') == 3
    assert context.index('m.py:4') < context.index('m.py:7') < context.index('a.py:1')
    assert 'b.py:' not in context and 'c.py:' not in context
    assert len(context) < 3 * (MAX_RETRY_DEFINITION_CHARS + 100)
