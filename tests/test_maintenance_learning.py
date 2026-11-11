from types import SimpleNamespace

from research_pipeline.maintenance.proposals import list_proposals
from research_pipeline.verify import healing, lessons
from research_pipeline.verify.healing import Healer, verify_with_healing
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import VerifyResult
from research_pipeline.verify.outcome import CONFIRMED, UNSUPPORTED


def test_learning_quarantines_repair_instead_of_changing_active_notebook(tmp_path, monkeypatch):
    notebook = tmp_path / 'SKILL.md'
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    source = 'def f(x):\n    return 1 / x\n'
    def fake_verify(h, *, source, **kwargs):
        return VerifyResult(h, CONFIRMED if 'def stub' in source else UNSUPPORTED, reason='ERROR: unsupported')
    monkeypatch.setattr(healing, 'verify_hypothesis', fake_verify)
    llm = SimpleNamespace(complete=lambda *a, **k: SimpleNamespace(harness='{"definitions": "def stub() -> int:\\n    return nondet_int()\\n"}'))
    healer = Healer(llm, None, auto_lessons=True, run_dir=tmp_path / 'run')
    h = BugHypothesis(file='x.py', function='f', suspect_expression='1 / x')
    before = notebook.read_text()
    result = verify_with_healing(h, healer=healer, source=source, llm='fake')
    assert result.verdict == CONFIRMED
    assert notebook.read_text() == before
    proposals = list_proposals(tmp_path / 'run' / 'quarentena')
    assert len(proposals) == 1
    assert proposals[0]['status'] == 'quarentena'
    assert proposals[0]['evidence']['program'] == source
    assert proposals[0]['evidence']['origin']['case'] == h.hypothesis_id


def test_hybrid_checkpoint_marks_new_learning_policy(tmp_path, monkeypatch):
    import json

    from test_main_v2 import _Analyzer, _detection_args, _Synthesizer

    import main

    source = tmp_path / 'sample.py'
    source.write_text('def divide(x: int, y: int) -> int:\n    return x // y\n')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setattr(main, 'build_analyzer', lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, 'LLMClient', _Synthesizer)
    out = tmp_path / 'out'
    assert main.mode_v2(_detection_args(source, out)) == 0
    checkpoint = json.loads((out / 'v2_checkpoint.json').read_text())
    assert checkpoint['fingerprint']['config']['lesson_storage'] == 'quarantine-v1'


def test_approved_lesson_is_applied_only_after_gate(tmp_path, monkeypatch):
    from research_pipeline.maintenance.learning import promote_lesson, queue_lesson

    repo = tmp_path / 'repo'
    notebook = repo / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    run = tmp_path / 'run'
    assert queue_lesson(error='ERROR: unsupported', fix='+ x = 1\n', program='print(1)', case='a', run_dir=run)
    proposal, = list_proposals(run / 'quarentena')
    def evaluate(candidate):
        assert 'Automatic repair' not in notebook.read_text()
        staged = candidate / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
        assert 'Automatic repair' in staged.read_text()
        return {'verdict': 'ACEITA', 'reasons': []}
    result = promote_lesson(repo, run / 'quarentena', proposal['id'], scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert result['applied'] is True
    assert 'Automatic repair' in notebook.read_text()
    assert list_proposals(run / 'quarentena')[0]['status'] == 'aceita'


def test_rejected_lesson_never_changes_active_notebook(tmp_path, monkeypatch):
    from research_pipeline.maintenance.learning import promote_lesson, queue_lesson

    repo = tmp_path / 'repo'
    notebook = repo / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    initial = '# Notes\n\n## Format of an approved repair\n\n'
    notebook.write_text(initial)
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    run = tmp_path / 'run'
    queue_lesson(error='ERROR: unsupported', fix='+ x = 1\n', program='print(1)', case='a', run_dir=run)
    proposal, = list_proposals(run / 'quarentena')
    result = promote_lesson(repo, run / 'quarentena', proposal['id'], scratch=tmp_path / 'scratch',
                            evaluate=lambda candidate: {'verdict': 'REJEITADA'})
    assert result['applied'] is False
    assert notebook.read_text() == initial
    assert list_proposals(run / 'quarentena')[0]['status'] == 'quarentena'


def test_agent_rounds_queue_program_and_do_not_change_notebook(tmp_path, monkeypatch):
    from research_pipeline.verify.agent_scan import learn_from_rounds

    notebook = tmp_path / 'SKILL.md'
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    case = tmp_path / 'case'
    for number, source, output in [(1, 'x = 1\n', 'ERROR: unsupported\n'),
                                   (2, 'x = 2\n', 'VERIFICATION SUCCESSFUL\n')]:
        folder = case / 'rounds' / f'{number:03d}'
        folder.mkdir(parents=True)
        (folder / 'input.py').write_text(source)
        (folder / 'output.txt').write_text(output)
        (folder / 'exit_code').write_text('1')
    assert learn_from_rounds(case, {'verdict': 'CONFIRMED'}, tmp_path / 'run') == 1
    proposal, = list_proposals(tmp_path / 'run' / 'quarentena')
    assert proposal['evidence']['program'] == 'x = 1\n'
    assert 'Automatic repair' not in notebook.read_text()


def test_learning_skips_non_error_diagnostic_without_failing(tmp_path, monkeypatch):
    notebook = tmp_path / 'SKILL.md'
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    healer = Healer(SimpleNamespace(), None, auto_lessons=True, run_dir=tmp_path / 'run')
    h = BugHypothesis(file='x.py', function='f', suspect_expression='1 / x')
    log = [{'round': 0, 'verdict_before': UNSUPPORTED, 'reason_before': 'ESBMC version 8.6.0',
            'verdict_after': CONFIRMED, 'patch': {'definitions': 'def g() -> int:\n    return nondet_int()\n'}}]
    assert healer.learn(h, log, {'verdict': CONFIRMED, '_learning_program': 'def f(x): return 1 / x'}) == 0
    assert list_proposals(tmp_path / 'run' / 'quarentena') == []


def test_completed_run_schedules_pending_maintenance(tmp_path, monkeypatch):
    import main
    from research_pipeline.maintenance import execution

    seen = []
    monkeypatch.setattr(execution, 'start_automatic_worker', lambda *args: seen.append(args) or {'started': True, 'log': 'test'})
    args = SimpleNamespace(auto_lessons=True, esbmc_command=['esbmc'])
    main._schedule_automatic_maintenance(args, tmp_path)
    assert seen and seen[0][1] == tmp_path
    assert seen[0][2] == ['esbmc']


def test_lesson_without_error_and_fix_cannot_be_promoted(tmp_path):
    import pytest

    from research_pipeline.maintenance.learning import promote_lesson
    from research_pipeline.maintenance.proposals import add_proposal

    repo = tmp_path / 'repo'
    notebook = repo / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    queue = tmp_path / 'queue'
    proposal_id = add_proposal('licao', 'incompleta', {'program': 'print(1)', 'origin': {'run': 'r', 'case': 'c'}},
                               queue, author='teste')
    with pytest.raises(ValueError, match='erro e alteração'):
        promote_lesson(repo, queue, proposal_id, scratch=tmp_path / 'scratch', evaluate=lambda root: {'verdict': 'ACEITA'})


def test_queue_write_failure_preserves_verification_and_records_error(tmp_path, monkeypatch):
    from research_pipeline.maintenance import learning

    notebook = tmp_path / 'SKILL.md'
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    def fail_queue(**kwargs):
        raise OSError('sem espaço')
    monkeypatch.setattr(learning, 'queue_lesson', fail_queue)
    def fake_verify(h, *, source, **kwargs):
        return VerifyResult(h, CONFIRMED if 'def stub' in source else UNSUPPORTED, reason='ERROR: unsupported')
    monkeypatch.setattr(healing, 'verify_hypothesis', fake_verify)
    llm = SimpleNamespace(complete=lambda *a, **k: SimpleNamespace(harness='{"definitions": "def stub() -> int:\\n    return nondet_int()\\n"}'))
    healer = Healer(llm, None, auto_lessons=True, run_dir=tmp_path / 'run')
    h = BugHypothesis(file='x.py', function='f', suspect_expression='1 / x')
    result = verify_with_healing(h, healer=healer, source='def f(x): return 1 / x', llm='fake')
    assert result.verdict == CONFIRMED
    assert 'sem espaço' in result.healing[-1]['learning_error']


def test_agent_queue_failure_preserves_result_and_records_error(tmp_path, monkeypatch):
    from research_pipeline.verify import agent_scan

    h = BugHypothesis(file='x.py', function='f', suspect_expression='1 / x')
    monkeypatch.setattr(agent_scan, 'run_agent_arm', lambda *a, **k: {'verdict': 'CONFIRMED', 'hypothesis': h.to_dict()})
    def fail_queue(*args, **kwargs):
        raise OSError('sem espaço')
    monkeypatch.setattr(agent_scan, 'learn_from_rounds', fail_queue)
    verify = agent_scan.agent_verifier(lambda *a: '', esbmc_command=['esbmc'], bound=5, timeout_seconds=1,
                                       agent_timeout=1, auto_lessons=True)
    results = verify([h], llm=None, output_dir=tmp_path, completed={}, on_result=lambda *a: None)
    assert results[0]['verdict'] == 'CONFIRMED'
    assert 'sem espaço' in results[0]['learning_error']
