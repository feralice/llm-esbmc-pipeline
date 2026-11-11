"""Executa verificações locais do portão sem chamadas de LLM."""

from __future__ import annotations

import os
import resource
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .gate import read_junit, recorded_replay


def _environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'GEMINI_API_KEY', 'CODEX_API_KEY'):
        env.pop(key, None)
    env['PYTHONPATH'] = str(root / 'src')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def _no_core() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _stop_group(process) -> bool:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
        return True
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
            return True
        except subprocess.TimeoutExpired:
            return False


def run_suite(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report = output / 'pytest.xml'
    command = [str(root / '.venv/bin/python'), '-m', 'pytest', 'tests', '-q', '-m', 'not live_llm',
               f'--junitxml={report.resolve()}']
    env = _environment(root)
    env['TMPDIR'] = '/tmp'
    shell_command = ['/bin/bash', '-c', 'ulimit -c 0; exec "$@"', 'maintenance-pytest', *command]
    with (output / 'pytest.log').open('x', encoding='utf-8') as log:
        process = subprocess.Popen(shell_command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            stopped = _stop_group(process)
            reason = 'suíte excedeu 10 minutos'
            if not stopped:
                reason += '; processo não encerrou após pedido de interrupção'
            return {'complete': False, 'failures': None, 'passed': None, 'reason': reason}
    return read_junit(report, returncode=code)


def run_replay(root: Path, reference: Path, output: Path, esbmc_command: list[str],
               *, timeout_seconds: int = 28800) -> dict:
    windows_disk = Path('/mnt/c')
    if windows_disk.is_dir() and shutil.disk_usage(windows_disk).free < 3 * 1024 ** 3:
        return {'complete': False, 'confirmed': None, 'reason': 'espaço insuficiente no disco C'}
    output.mkdir(parents=True, exist_ok=True)
    command = [str(root / '.venv/bin/python'), str(root / 'scripts/v2_replay_specs.py'), str(reference.resolve()),
               '--esbmc', shlex.join(esbmc_command), '--timeout', '180', '--sources',
               'dataset/disciplina_pgene601/arquivo_com_bug', '--strict-sources', '--heal', 'none',
               '--out', str(output.resolve())]
    env = _environment(root)
    if Path('/mnt/e').is_dir():
        env['TMPDIR'] = '/mnt/e'
    shell_command = ['/bin/bash', '-c', 'ulimit -c 0; exec "$@"', 'maintenance-replay', *command]
    with (output / 'replay.log').open('x', encoding='utf-8') as log:
        process = subprocess.Popen(shell_command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                code = process.wait(timeout=max(0.1, min(30, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                low_disk = windows_disk.is_dir() and shutil.disk_usage(windows_disk).free < 3 * 1024 ** 3
                if low_disk or time.monotonic() >= deadline:
                    stopped = _stop_group(process)
                    reason = 'espaço insuficiente no disco C' if low_disk else 'replay excedeu o tempo limite'
                    if not stopped:
                        reason += '; processo não encerrou após pedido de interrupção'
                    return {'complete': False, 'confirmed': None, 'reason': reason}
    if code:
        return {'complete': False, 'confirmed': None, 'reason': f'replay saiu com código {code}'}
    return recorded_replay(reference, output, root / 'dataset/disciplina_pgene601/ground_truths.json')


def run_probes(root: Path, output: Path, esbmc_command: list[str]) -> dict:
    import json

    windows_disk = Path('/mnt/c')
    if windows_disk.is_dir() and shutil.disk_usage(windows_disk).free < 3 * 1024 ** 3:
        return {'reason': 'espaço insuficiente no disco C', 'results': {}}
    output.mkdir(parents=True, exist_ok=True)
    program = ('import json,sys; from pathlib import Path; '
               'from research_pipeline.verify.capabilities import resolve_rules; '
               'print(json.dumps(resolve_rules(json.loads(sys.argv[1]), cache_dir=Path(sys.argv[2]))))')
    env = _environment(root)
    if Path('/mnt/e').is_dir():
        env['TMPDIR'] = '/mnt/e'
    command = [str(root / '.venv/bin/python'), '-c', program, json.dumps(esbmc_command),
               str(output.resolve())]
    shell_command = ['/bin/bash', '-c', 'ulimit -c 0; exec "$@"', 'maintenance-probes', *command]
    try:
        process = subprocess.Popen(shell_command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        deadline = time.monotonic() + 3600
        while True:
            try:
                stdout, _ = process.communicate(timeout=max(0.1, min(30, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                low_disk = windows_disk.is_dir() and shutil.disk_usage(windows_disk).free < 3 * 1024 ** 3
                if low_disk or time.monotonic() >= deadline:
                    stopped = _stop_group(process)
                    reason = 'espaço insuficiente no disco C' if low_disk else 'sondas excederam o tempo limite'
                    if not stopped:
                        reason += '; processo não encerrou após pedido de interrupção'
                    return {'reason': reason, 'results': {}}
        if process.returncode:
            return {'reason': 'falha ao executar sondas', 'results': {}}
        data = json.loads(stdout)
        return data if isinstance(data, dict) else {'reason': 'resposta inválida das sondas', 'results': {}}
    except (OSError, ValueError):
        return {'reason': 'sondas indisponíveis', 'results': {}}


def prepare_baseline(root: Path, reference: Path, output: Path, esbmc_command: list[str], *,
                     suite_runner=run_suite, probe_runner=run_probes, replay_runner=run_replay) -> dict:
    """Mede o estado anterior e recusa iniciar mudanças se a referência não for reproduzida."""
    import hashlib
    import json

    from .automatic import _snapshot

    reference_bytes = reference.read_bytes()
    reference_hash = hashlib.sha256(reference_bytes).hexdigest()
    report = json.loads(reference_bytes)
    expected = report['evaluation']['confirmed_by_location']['location']['tp']
    before = _snapshot(root)
    suite = suite_runner(root, output / 'suite',)
    if not suite.get('complete') or suite.get('failures') is None or suite.get('passed') is None:
        return {'ready': False, 'reason': 'suíte anterior incompleta'}
    probes = probe_runner(root, output / 'sondas', esbmc_command)
    results = probes.get('results', {})
    if (probes.get('reason') != 'sondas' or not results
            or any(item.get('outcome') not in {'aceita', 'recusa'} for item in results.values())):
        return {'ready': False, 'reason': 'sondas anteriores incompletas'}
    replay = replay_runner(root, reference, output / 'replay', esbmc_command)
    if not replay.get('complete') or replay.get('confirmed') != expected:
        return {'ready': False, 'reason': 'replay não reproduziu a referência', 'replay': replay, 'expected': expected}
    if hashlib.sha256(reference.read_bytes()).hexdigest() != reference_hash:
        return {'ready': False, 'reason': 'a referência mudou durante a medição'}
    if _snapshot(root) != before:
        return {'ready': False, 'reason': 'o código ou os dados mudaram durante a medição'}
    return {'ready': True, 'suite': suite, 'probes': probes, 'replay': replay, 'snapshot': before,
            'reference_hash': reference_hash}


def process_lesson(root: Path, proposals_root: Path, proposal_id: str, reference: Path, output: Path,
                   esbmc_command: list[str], *, suite_runner=run_suite, probe_runner=run_probes,
                   replay_runner=run_replay) -> dict:
    """Mede base e candidato; aplica a lição apenas depois de todas as comparações."""
    from .automatic import _snapshot
    from .gate import run_gate
    from .learning import promote_lesson
    from .proposals import list_proposals

    entries = [p for p in list_proposals(proposals_root) if p['id'] == proposal_id]
    if len(entries) != 1 or entries[0]['kind'] != 'licao' or entries[0]['status'] != 'quarentena':
        raise ValueError('Proposta de lição em quarentena não encontrada')
    evidence = entries[0]['evidence']
    if not isinstance(evidence.get('error'), str) or not evidence['error'].startswith('ERROR:') or not isinstance(evidence.get('fix'), str) or not evidence['fix'].strip():
        raise ValueError('Lição exige erro e alteração para promoção')
    baseline = prepare_baseline(root, reference, output / 'antes', esbmc_command,
                                suite_runner=suite_runner, probe_runner=probe_runner, replay_runner=replay_runner)
    if not baseline.get('ready'):
        return {'applied': False, **baseline}
    if _snapshot(root) != baseline['snapshot']:
        return {'applied': False, 'reason': 'o código mudou depois de medir a base'}

    def evaluate(candidate: Path) -> dict:
        before = _snapshot(candidate)
        suite = suite_runner(candidate, output / 'depois' / 'suite')
        probes = probe_runner(candidate, output / 'depois' / 'sondas', esbmc_command)
        replay = replay_runner(candidate, reference, output / 'depois' / 'replay', esbmc_command)
        result = run_gate(reference, esbmc_command=esbmc_command, runner=lambda: probes,
                          replay=lambda path: replay, suite=lambda: suite, baseline_probes=baseline['probes'],
                          baseline_failures=baseline['suite']['failures'], baseline_passed=baseline['suite']['passed'])
        import hashlib

        if hashlib.sha256(reference.read_bytes()).hexdigest() != baseline['reference_hash']:
            result['verdict'] = 'REJEITADA'
            result['reasons'].append('a referência mudou durante a avaliação')
        if _snapshot(candidate) != before:
            result['verdict'] = 'REJEITADA'
            result['reasons'].append('o candidato mudou durante os testes')
        return result

    return promote_lesson(root, proposals_root, proposal_id, scratch=output / 'candidatos', evaluate=evaluate)


def process_code(root: Path, proposals_root: Path, proposal_id: str, reference: Path, output: Path,
                 esbmc_command: list[str], *, suite_runner=run_suite, probe_runner=run_probes,
                 replay_runner=run_replay) -> dict:
    """Aplica um patch de código só após medir a base e testar a cópia alterada."""
    from .automatic import _snapshot, apply_proposal
    from .gate import run_gate
    from .proposals import accept_by_gate, list_proposals

    entries = [p for p in list_proposals(proposals_root) if p['id'] == proposal_id]
    if len(entries) != 1 or entries[0]['kind'] != 'codigo' or entries[0]['status'] != 'quarentena':
        raise ValueError('Proposta de código em quarentena não encontrada')
    patch = entries[0]['evidence'].get('patch')
    if not isinstance(patch, str) or not patch.strip():
        raise ValueError('Proposta de código não contém patch')
    baseline = prepare_baseline(root, reference, output / 'antes', esbmc_command,
                                suite_runner=suite_runner, probe_runner=probe_runner, replay_runner=replay_runner)
    if not baseline.get('ready'):
        return {'applied': False, **baseline}
    if _snapshot(root) != baseline['snapshot']:
        return {'applied': False, 'reason': 'o código mudou depois de medir a base'}

    def evaluate(candidate: Path) -> dict:
        before = _snapshot(candidate)
        suite = suite_runner(candidate, output / 'depois' / 'suite')
        probes = probe_runner(candidate, output / 'depois' / 'sondas', esbmc_command)
        replay = replay_runner(candidate, reference, output / 'depois' / 'replay', esbmc_command)
        result = run_gate(reference, esbmc_command=esbmc_command, runner=lambda: probes,
                          replay=lambda path: replay, suite=lambda: suite, baseline_probes=baseline['probes'],
                          baseline_failures=baseline['suite']['failures'], baseline_passed=baseline['suite']['passed'])
        import hashlib

        if hashlib.sha256(reference.read_bytes()).hexdigest() != baseline['reference_hash']:
            result['verdict'] = 'REJEITADA'
            result['reasons'].append('a referência mudou durante a avaliação')
        if _snapshot(candidate) != before:
            result['verdict'] = 'REJEITADA'
            result['reasons'].append('o candidato mudou durante os testes')
        return result

    result = apply_proposal(root, patch.encode('utf-8'), scratch=output / 'candidatos', evaluate=evaluate)
    if result['applied']:
        accept_by_gate(proposals_root, proposal_id, result['gate'])
    return result


def start_automatic_worker(root: Path, run_dir: Path, esbmc_command: list[str], output: Path) -> dict:
    """Delega inclusive a consulta da fila e a abertura do log para outro processo."""
    import json
    import uuid

    if not esbmc_command:
        return {'scheduled': False, 'reason': 'comando ESBMC ausente'}
    log_path = output / f'auto_{uuid.uuid4().hex}.log'
    program = ('import json,sys; from pathlib import Path; '
               'from research_pipeline.maintenance.execution import _launch_automatic_worker; '
               'root,run,command,output,log=json.loads(sys.argv[1]); '
               '_launch_automatic_worker(Path(root),Path(run),command,Path(output),log_path=Path(log))')
    command = [str(root / '.venv/bin/python'), '-c', program,
               json.dumps([str(root), str(run_dir), esbmc_command, str(output), str(log_path)])]
    shell_command = ['/bin/bash', '-c', 'ulimit -c 0; exec "$@"', 'maintenance-launcher', *command]
    process = subprocess.Popen(shell_command, cwd=root, env=_environment(root), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {'scheduled': True, 'pid': process.pid, 'log': str(log_path)}


def _launch_automatic_worker(root: Path, run_dir: Path, esbmc_command: list[str], output: Path, *,
                             log_path: Path | None = None) -> dict:
    """Inicia avaliação em segundo plano quando uma rodada deixa propostas pendentes."""
    import tempfile

    from .proposals import list_proposals

    queue = run_dir / 'quarentena'
    if not any(p['status'] == 'quarentena' and p['kind'] in {'licao', 'codigo'} for p in list_proposals(queue)):
        return {'started': False, 'reason': 'sem propostas pendentes'}
    if not esbmc_command:
        return {'started': False, 'reason': 'comando ESBMC ausente'}
    output.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        fd, log_path = tempfile.mkstemp(prefix='auto_', suffix='.log', dir=output)
    else:
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    command = [str(root / '.venv/bin/python'), str(root / 'scripts/maintenance.py'), '--output-dir', str(output),
               '--esbmc', esbmc_command[0], *(f'--esbmc-arg={flag}' for flag in esbmc_command[1:]),
               'auto', str(queue)]
    shell_command = ['/bin/bash', '-c', 'ulimit -c 0; exec "$@"', 'maintenance-worker', *command]
    with os.fdopen(fd, 'w', encoding='utf-8') as log:
        process = subprocess.Popen(shell_command, cwd=root, env=_environment(root), stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    return {'started': True, 'pid': process.pid, 'log': log_path}
