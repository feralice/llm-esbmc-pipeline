from pathlib import Path
from types import SimpleNamespace

import pytest

from research_pipeline.maintenance.execution import run_replay, run_suite


@pytest.fixture(autouse=True)
def simulated_windows_disks(monkeypatch):
    """Testes de processo usam discos simulados, sem depender de montagens WSL."""
    import shutil

    original = Path.is_dir
    monkeypatch.setattr(Path, 'is_dir', lambda path: True if str(path) in {'/mnt/c', '/mnt/e'} else original(path))
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=10 * 1024 ** 3))


def test_suite_uses_timeout_and_records_failures_without_live_llm(tmp_path, monkeypatch):
    calls = []
    waits = []
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        xml = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--junitxml='))
        Path(xml).write_text('<testsuites><testsuite><testcase classname="t" name="ok"/>'
                             '<testcase classname="t" name="bad"><failure/></testcase></testsuite></testsuites>')
        return SimpleNamespace(wait=lambda timeout: waits.append(timeout) or 1)
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', fake_run)
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-pass')
    result = run_suite(tmp_path, tmp_path / 'out')
    assert result['complete'] and result['failures'] == ['t::bad'] and result['passed'] == 1
    command, kwargs = calls[0]
    assert waits == [600]
    assert kwargs['env'].get('OPENAI_API_KEY') is None
    assert 'not live_llm' in command


def test_replay_never_enables_live_model_or_healing(tmp_path, monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(wait=lambda **kw: 0)
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', fake_run)
    result = run_replay(tmp_path, tmp_path / 'reference.json', tmp_path / 'out', ['esbmc'])
    command, _ = calls[0]
    assert command[command.index('--heal') + 1] == 'none'
    assert '--live-spec' not in command
    assert result['complete'] is False


def test_probe_failure_is_not_a_successful_result(tmp_path, monkeypatch):
    from research_pipeline.maintenance.execution import run_probes

    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen',
                        lambda *args, **kwargs: SimpleNamespace(returncode=1, communicate=lambda timeout: ('', 'failed')))
    result = run_probes(tmp_path, tmp_path / 'out', ['esbmc'])
    assert result['reason'] != 'sondas'
    assert result['results'] == {}


def test_automatic_baseline_rejects_if_reference_is_not_reproduced(tmp_path):
    import json

    from research_pipeline.maintenance.execution import prepare_baseline

    ref = tmp_path / 'reference.json'
    ref.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    result = prepare_baseline(tmp_path, ref, tmp_path / 'out', ['esbmc'],
                              suite_runner=lambda *a: {'complete': True, 'passed': 5, 'failures': []},
                              probe_runner=lambda *a: {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita'}}},
                              replay_runner=lambda *a: {'complete': True, 'confirmed': 13})
    assert result['ready'] is False
    assert 'não reproduziu' in result['reason']


def test_automatic_baseline_fails_closed_on_incomplete_suite(tmp_path):
    import json

    from research_pipeline.maintenance.execution import prepare_baseline

    ref = tmp_path / 'reference.json'
    ref.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    result = prepare_baseline(tmp_path, ref, tmp_path / 'out', ['esbmc'],
                              suite_runner=lambda *a: {'complete': False},
                              probe_runner=lambda *a: (_ for _ in ()).throw(AssertionError('não executar sondas')),
                              replay_runner=lambda *a: (_ for _ in ()).throw(AssertionError('não executar replay')))
    assert result['ready'] is False


def test_cycle_applies_queued_lesson_after_real_gate_decision(tmp_path, monkeypatch):
    import json

    from research_pipeline.maintenance.execution import process_lesson
    from research_pipeline.maintenance.learning import queue_lesson
    from research_pipeline.maintenance.proposals import list_proposals
    from research_pipeline.verify import lessons

    root = tmp_path / 'repo'
    notebook = root / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    notebook.write_text('# Notes\n\n## Format of an approved repair\n\n')
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    reference = tmp_path / 'ref.json'
    reference.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    run = tmp_path / 'run'
    queue_lesson(error='ERROR: unsupported', fix='+ x = 1\n', program='print(1)', case='case', run_dir=run)
    proposal, = list_proposals(run / 'quarentena')
    suite = lambda *a: {'complete': True, 'passed': 2, 'failures': []}
    probes = lambda *a: {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita'}}}
    replay = lambda *a: {'complete': True, 'confirmed': 14}
    result = process_lesson(root, run / 'quarentena', proposal['id'], reference, tmp_path / 'work', ['esbmc'],
                            suite_runner=suite, probe_runner=probes, replay_runner=replay)
    assert result['applied'] is True
    assert 'Automatic repair' in notebook.read_text()
    assert list_proposals(run / 'quarentena')[0]['status'] == 'aceita'


def test_cycle_does_not_apply_when_reference_baseline_is_incomplete(tmp_path):
    import json

    from research_pipeline.maintenance.execution import process_lesson

    ref = tmp_path / 'reference.json'
    ref.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    from research_pipeline.maintenance.proposals import add_proposal

    queue = tmp_path / 'queue'
    proposal_id = add_proposal('licao', 'teste', {'program': 'print(1)', 'origin': {'run': 'r', 'case': 'c'},
                          'error': 'ERROR: test', 'fix': '+ x = 1'}, queue, author='teste')
    result = process_lesson(tmp_path, queue, proposal_id, ref, tmp_path / 'work', ['esbmc'],
                            suite_runner=lambda *a: {'complete': False})
    assert result['applied'] is False
    assert 'incompleta' in result['reason']


def test_cycle_keeps_lesson_queued_when_candidate_breaks_a_probe(tmp_path, monkeypatch):
    import json

    from research_pipeline.maintenance.execution import process_lesson
    from research_pipeline.maintenance.learning import queue_lesson
    from research_pipeline.maintenance.proposals import list_proposals
    from research_pipeline.verify import lessons

    root = tmp_path / 'repo'
    notebook = root / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    initial = '# Notes\n\n## Format of an approved repair\n\n'
    notebook.write_text(initial)
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    reference = tmp_path / 'ref.json'
    reference.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    run = tmp_path / 'run'
    queue_lesson(error='ERROR: unsupported', fix='+ x = 1\n', program='print(1)', case='case', run_dir=run)
    proposal, = list_proposals(run / 'quarentena')
    suite = lambda *a: {'complete': True, 'passed': 2, 'failures': []}
    def probes(path, *args):
        outcome = 'aceita' if path == root else 'recusa'
        return {'reason': 'sondas', 'results': {'p': {'outcome': outcome}}}
    replay = lambda *a: {'complete': True, 'confirmed': 14}
    result = process_lesson(root, run / 'quarentena', proposal['id'], reference, tmp_path / 'work', ['esbmc'],
                            suite_runner=suite, probe_runner=probes, replay_runner=replay)
    assert result['applied'] is False
    assert result['gate']['verdict'] == 'REJEITADA'
    assert notebook.read_text() == initial
    assert list_proposals(run / 'quarentena')[0]['status'] == 'quarentena'


def test_cycle_applies_code_patch_only_after_gate_accepts(tmp_path):
    import json

    from research_pipeline.maintenance.execution import process_code
    from research_pipeline.maintenance.proposals import add_proposal, list_proposals

    root = tmp_path / 'repo'
    target = root / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    patch = 'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    queue = tmp_path / 'queue'
    proposal_id = add_proposal('codigo', 'ajuste', {'program': 'assert 1', 'origin': {'run': 'r', 'case': 'c'},
                                                   'patch': patch}, queue, author='self-learning')
    reference = tmp_path / 'ref.json'
    reference.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    suite = lambda *a: {'complete': True, 'passed': 2, 'failures': []}
    probes = lambda *a: {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita'}}}
    replay = lambda *a: {'complete': True, 'confirmed': 14}
    result = process_code(root, queue, proposal_id, reference, tmp_path / 'work', ['esbmc'],
                          suite_runner=suite, probe_runner=probes, replay_runner=replay)
    assert result['applied'] is True
    assert target.read_text() == 'value = 2\n'
    assert list_proposals(queue)[0]['status'] == 'aceita'
    assert list_proposals(queue)[0]['approval_method'] == 'portao_automatico'


def test_suite_does_not_use_external_disk_for_pytest_capture(tmp_path, monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append(kwargs)
        xml = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--junitxml='))
        Path(xml).write_text('<testsuites><testsuite><testcase classname="t" name="ok"/></testsuite></testsuites>')
        return SimpleNamespace(wait=lambda timeout: 0)
    monkeypatch.setenv('TMPDIR', '/mnt/e')
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', fake_run)
    assert run_suite(tmp_path, tmp_path / 'out')['complete'] is True
    assert calls[0]['env'].get('TMPDIR') != '/mnt/e'


def test_worker_starts_only_when_queue_has_pending_lesson(tmp_path, monkeypatch):
    from research_pipeline.maintenance.execution import (
        _launch_automatic_worker as start_automatic_worker,
    )
    from research_pipeline.maintenance.proposals import add_proposal

    calls = []
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen',
                        lambda *a, **k: calls.append((a, k)) or SimpleNamespace(pid=123))
    root = tmp_path / 'repo'
    root.mkdir()
    run = tmp_path / 'run'
    output = tmp_path / 'output'
    assert start_automatic_worker(root, run, ['esbmc'], output)['started'] is False
    add_proposal('licao', 'teste', {'program': 'print(1)', 'origin': {'run': 'r', 'case': 'c'}},
                 run / 'quarentena', author='teste')
    result = start_automatic_worker(root, run, ['esbmc', '--z3'], output)
    assert result['started'] is True
    command = calls[0][0][0]
    assert '--esbmc-arg=--z3' in command
    assert command[command.index('auto') + 1] == str(run / 'quarentena')


def test_worker_scheduling_never_accesses_the_external_disk(tmp_path, monkeypatch):
    from research_pipeline.maintenance.execution import start_automatic_worker

    def forbidden(*args, **kwargs):
        pytest.fail('O processo principal não pode consultar nem abrir o disco externo')

    monkeypatch.setattr('research_pipeline.maintenance.proposals.list_proposals', forbidden)
    monkeypatch.setattr(Path, 'mkdir', forbidden)
    calls = []
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen',
                        lambda *a, **k: calls.append((a, k)) or SimpleNamespace(pid=123))
    result = start_automatic_worker(tmp_path, Path('/mnt/e/rodada'), ['esbmc'], Path('/mnt/e/saida'))
    assert result['scheduled'] is True and result['pid'] == 123
    assert calls[0][1]['start_new_session'] is True
    assert calls[0][1]['env']['PYTHONPATH'] == str(tmp_path / 'src')


def test_real_launcher_exits_without_running_maintenance_for_an_empty_queue(tmp_path, monkeypatch):
    import subprocess

    from research_pipeline.maintenance.execution import start_automatic_worker

    spawned = []
    original = subprocess.Popen

    def capture(*args, **kwargs):
        process = original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(subprocess, 'Popen', capture)
    result = start_automatic_worker(Path(__file__).resolve().parents[1], tmp_path / 'run', ['esbmc'],
                                    tmp_path / 'output')
    assert result['scheduled'] is True
    try:
        assert spawned[0].wait(timeout=5) == 0
    finally:
        if spawned[0].poll() is None:
            spawned[0].kill()
            spawned[0].wait(timeout=5)
    assert not (tmp_path / 'output').exists()


def test_replay_refuses_to_start_if_windows_disk_is_nearly_full(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(total=10, used=9, free=1))
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen',
                        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('não executar')))
    result = run_replay(tmp_path, tmp_path / 'reference.json', tmp_path / 'out', ['esbmc'])
    assert result['complete'] is False
    assert 'espaço' in result['reason']


def test_replay_stops_its_process_group_if_windows_disk_fills(tmp_path, monkeypatch):
    import shutil
    import subprocess

    calls = []
    free = iter([10 * 1024 ** 3, 1])
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=next(free)))
    class Process:
        pid = 123
        def wait(self, timeout=None):
            if not calls:
                raise subprocess.TimeoutExpired('test', timeout)
            return -15
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', lambda *a, **k: Process())
    monkeypatch.setattr('research_pipeline.maintenance.execution.os.killpg', lambda pid, sig: calls.append((pid, sig)))
    result = run_replay(tmp_path, tmp_path / 'reference.json', tmp_path / 'out', ['esbmc'])
    assert result['complete'] is False
    assert 'espaço' in result['reason']
    assert calls and calls[0][0] == 123


def test_suite_timeout_stops_its_process_group(tmp_path, monkeypatch):
    import subprocess

    calls = []
    class Process:
        pid = 321
        def wait(self, timeout=None):
            if not calls:
                raise subprocess.TimeoutExpired('pytest', timeout)
            return -15
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', lambda *a, **k: Process())
    monkeypatch.setattr('research_pipeline.maintenance.execution.os.killpg', lambda pid, sig: calls.append((pid, sig)))
    result = run_suite(tmp_path, tmp_path / 'out')
    assert result['complete'] is False
    assert calls and calls[0][0] == 321


def test_probes_refuse_when_windows_disk_is_nearly_full(tmp_path, monkeypatch):
    import shutil

    from research_pipeline.maintenance.execution import run_probes

    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=1))
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen',
                        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('não executar')))
    result = run_probes(tmp_path, tmp_path / 'out', ['esbmc'])
    assert result['results'] == {}
    assert 'espaço' in result['reason']


def test_automatic_baseline_rejects_if_reference_changes_during_run(tmp_path):
    import json

    from research_pipeline.maintenance.execution import prepare_baseline

    ref = tmp_path / 'reference.json'
    ref.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    def replay(*args):
        ref.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 99}}}}))
        return {'complete': True, 'confirmed': 14}
    result = prepare_baseline(tmp_path, ref, tmp_path / 'out', ['esbmc'],
                              suite_runner=lambda *a: {'complete': True, 'passed': 1, 'failures': []},
                              probe_runner=lambda *a: {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita'}}},
                              replay_runner=replay)
    assert result['ready'] is False
    assert 'referência mudou' in result['reason']


def test_cycle_does_not_apply_if_reference_changes_during_candidate_checks(tmp_path, monkeypatch):
    import json

    from research_pipeline.maintenance.execution import process_lesson
    from research_pipeline.maintenance.learning import queue_lesson
    from research_pipeline.maintenance.proposals import list_proposals
    from research_pipeline.verify import lessons

    root = tmp_path / 'repo'
    notebook = root / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    notebook.parent.mkdir(parents=True)
    initial = '# Notes\n\n## Format of an approved repair\n\n'
    notebook.write_text(initial)
    monkeypatch.setattr(lessons, 'NOTEBOOK', notebook)
    reference = tmp_path / 'ref.json'
    reference.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}}))
    run = tmp_path / 'run'
    queue_lesson(error='ERROR: unsupported', fix='+ x = 1\n', program='print(1)', case='case', run_dir=run)
    proposal, = list_proposals(run / 'quarentena')
    suite = lambda *a: {'complete': True, 'passed': 2, 'failures': []}
    probes = lambda *a: {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita'}}}
    def replay(path, *args):
        if path != root:
            reference.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': 14}}}, 'changed': True}))
        return {'complete': True, 'confirmed': 14}
    result = process_lesson(root, run / 'quarentena', proposal['id'], reference, tmp_path / 'work', ['esbmc'],
                            suite_runner=suite, probe_runner=probes, replay_runner=replay)
    assert result['applied'] is False
    assert notebook.read_text() == initial


def test_probes_stop_process_group_if_windows_disk_fills(tmp_path, monkeypatch):
    import shutil
    import subprocess

    from research_pipeline.maintenance.execution import run_probes

    calls = []
    free = iter([10 * 1024 ** 3, 1])
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=next(free)))
    class Process:
        pid = 444
        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired('probes', timeout)
        def wait(self, timeout=None):
            return -15
    monkeypatch.setattr('research_pipeline.maintenance.execution.subprocess.Popen', lambda *a, **k: Process())
    monkeypatch.setattr('research_pipeline.maintenance.execution.os.killpg', lambda pid, sig: calls.append((pid, sig)))
    result = run_probes(tmp_path, tmp_path / 'out', ['esbmc'])
    assert result['results'] == {}
    assert 'espaço' in result['reason']
    assert calls and calls[0][0] == 444


def test_killed_process_does_not_block_forever_when_system_stalls(monkeypatch):
    import subprocess

    from research_pipeline.maintenance.execution import _stop_group

    class Process:
        pid = 444
        def wait(self, timeout=None):
            assert timeout is not None
            raise subprocess.TimeoutExpired('blocked', timeout)
    monkeypatch.setattr('research_pipeline.maintenance.execution.os.killpg', lambda *args: None)
    assert _stop_group(Process()) is False
