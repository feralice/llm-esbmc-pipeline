import json
from pathlib import Path

from scripts import maintenance

FINGERPRINT = {'git_commit': 'abc', 'dirty': True, 'notebook_version': 'v',
               'rules': {'active_rules': [], 'reason': 'teste'},
               'esbmc_identity': {'version': 'ESBMC version test'}}


def test_every_report_starts_with_the_fingerprint_and_says_when_the_tree_is_dirty(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    report = tmp_path / 'scan.json'
    report.write_text(json.dumps({'config': {'model': 'm'}, 'results': []}))
    output = tmp_path / 'output'
    for args, name in [(['refusals', str(report)], 'refusals'), (['timing', str(report)], 'timing'),
                       (['proposals', 'list'], 'proposals')]:
        assert maintenance.main(['--output-dir', str(output), *args]) == 0
        content = (output / f'{name}.json').read_text()
        assert next(iter(json.loads(content))) == 'fingerprint'
        markdown = (output / f'{name}.md').read_text()
        assert markdown.startswith('# Impressão digital')
        assert 'alterações não commitadas' in markdown


def test_missing_esbmc_stops_with_a_clear_message_and_exit_code_1(tmp_path, monkeypatch, capsys):
    def unavailable(*args, **kwargs):
        raise RuntimeError('ESBMC ausente ou versão indisponível')
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', unavailable)
    assert maintenance.main(['--output-dir', str(tmp_path), 'limits']) == 1
    assert 'ESBMC' in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_gate_reports_missing_evidence_without_claiming_success(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    report = tmp_path / 'reference.json'
    report.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    assert maintenance.main(['--output-dir', str(tmp_path), 'gate', str(report)]) == 0
    result = json.loads((tmp_path / 'gate.json').read_text())['resultado']
    assert result['verdict'] == 'REJEITADA'
    assert result['metrics']['bugs_confirmados']['depois'] is None


def test_existing_reports_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    (tmp_path / 'proposals.json').write_text('original')
    (tmp_path / 'proposals.md').write_text('original')
    assert maintenance.main(['--output-dir', str(tmp_path), 'proposals', 'list']) == 0
    assert (tmp_path / 'proposals.json').read_text() == 'original'
    assert (tmp_path / 'proposals_2.json').is_file()


def test_duplicate_add_reports_the_existing_status(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    evidence = tmp_path / 'evidence.json'
    evidence.write_text(json.dumps({'program': 'assert False', 'origin': {'run': 'r', 'case': 'c'}}))
    quarantine = tmp_path / 'quarentena'
    args = ['--output-dir', str(tmp_path), 'proposals', '--root', str(quarantine), 'add',
            '--kind', 'issue', '--title', 'Exemplo', '--author', 'F', '--evidence', str(evidence)]
    assert maintenance.main(args) == 0
    proposal_id = json.loads((tmp_path / 'proposals.json').read_text())['resultado']['id']
    maintenance.set_status(quarantine, proposal_id, 'rejeitada')
    assert maintenance.main(args) == 0
    assert json.loads((tmp_path / 'proposals_2.json').read_text())['resultado']['status'] == 'rejeitada'


def test_limits_report_has_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    monkeypatch.setattr(maintenance, 'run_limits', lambda *a, **k: {})
    monkeypatch.setattr(maintenance, 'compare_baseline', lambda *a, **k: {'comparison': None})
    assert maintenance.main(['--output-dir', str(tmp_path), 'limits']) == 0
    report = json.loads((tmp_path / 'limits.json').read_text())
    assert next(iter(report)) == 'fingerprint'
    assert report['fingerprint']['dirty'] is True


def test_auto_processes_pending_lesson_without_asking(tmp_path, monkeypatch):
    from research_pipeline.maintenance.proposals import add_proposal

    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    calls = []
    monkeypatch.setattr(maintenance, 'process_lesson', lambda *a, **k: calls.append(a) or {'applied': False, 'reason': 'teste'})
    queue = tmp_path / 'queue'
    proposal = add_proposal('licao', 'teste', {'program': 'print(1)', 'origin': {'run': 'r', 'case': 'c'}},
                            queue, author='teste')
    assert maintenance.main(['--output-dir', str(tmp_path / 'out'), 'auto', str(queue)]) == 0
    assert len(calls) == 1 and calls[0][2] == proposal
    result = json.loads((tmp_path / 'out/auto.json').read_text())['resultado']
    assert result['propostas'][0]['resultado']['applied'] is False


def test_limits_use_output_disk_for_esbmc_logs(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    seen = []
    monkeypatch.setattr(maintenance, 'run_limits', lambda *a, **k: seen.append(Path(tempfile.gettempdir())) or {})
    monkeypatch.setattr(maintenance, 'compare_baseline', lambda *a, **k: {'comparison': None})
    output = tmp_path / 'output'
    assert maintenance.main(['--output-dir', str(output), 'limits']) == 0
    assert seen == [output]


def test_auto_stops_batch_when_baseline_is_not_valid(tmp_path, monkeypatch):
    from research_pipeline.maintenance.proposals import add_proposal

    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    calls = []
    monkeypatch.setattr(maintenance, 'process_lesson', lambda *a, **k: calls.append(a) or
                        {'applied': False, 'ready': False, 'reason': 'replay incompleto'})
    queue = tmp_path / 'queue'
    for case in ['a', 'b']:
        add_proposal('licao', case, {'program': f'print({case!r})', 'origin': {'run': 'r', 'case': case}},
                     queue, author='teste')
    assert maintenance.main(['--output-dir', str(tmp_path / 'out'), 'auto', str(queue)]) == 0
    assert len(calls) == 1


def test_auto_does_not_process_queue_already_locked(tmp_path, monkeypatch):
    import fcntl

    from research_pipeline.maintenance.proposals import add_proposal

    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    calls = []
    monkeypatch.setattr(maintenance, 'process_lesson', lambda *a, **k: calls.append(a))
    queue = tmp_path / 'queue'
    add_proposal('licao', 'teste', {'program': 'print(1)', 'origin': {'run': 'r', 'case': 'c'}},
                 queue, author='teste')
    with (queue / '.maintenance.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert maintenance.main(['--output-dir', str(tmp_path / 'out'), 'auto', str(queue)]) == 0
    assert not calls
    result = json.loads((tmp_path / 'out/auto.json').read_text())['resultado']
    assert 'já está em avaliação' in result['propostas'][0]['resultado']['reason']


def test_baseline_command_reports_failed_reproduction(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, 'pipeline_fingerprint', lambda *a, **k: FINGERPRINT)
    monkeypatch.setattr(maintenance, 'prepare_baseline', lambda *a, **k: {'ready': False, 'reason': 'replay incompleto'})
    assert maintenance.main(['--output-dir', str(tmp_path), 'baseline']) == 0
    result = json.loads((tmp_path / 'baseline.json').read_text())['resultado']
    assert result == {'ready': False, 'reason': 'replay incompleto'}
