"""Executa reprodutores e compara resultados, sem inferir correções."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from research_pipeline.verification.esbmc_runner import run_esbmc_direct
from research_pipeline.verify.capabilities import esbmc_identity
from research_pipeline.verify.esbmc_run import Runner, esbmc_output
from research_pipeline.verify.levels import _CRASH, _LANGUAGE


def run_limits(esbmc_command: list[str], limits_dir: Path, *, runner: Runner | None = None,
               timeout_seconds: int = 300) -> dict[str, dict]:
    if not esbmc_command:
        raise RuntimeError('Comando do ESBMC ausente')
    identity = esbmc_identity(esbmc_command)
    version = identity.get('version', '')
    if not version or version.startswith('unavailable:') or 'ESBMC version' not in version:
        raise RuntimeError(f'ESBMC ausente ou versão indisponível: {version}')
    run = runner or run_esbmc_direct
    outcomes = {}
    for path in sorted(limits_dir.glob('[0-9]*.py')):
        if Path('/mnt/c').is_dir() and shutil.disk_usage('/mnt/c').free < 3 * 1024 ** 3:
            raise RuntimeError('espaço insuficiente no disco C para executar ESBMC')
        bound_flags = (['--incremental-bmc', '--max-k-step', '5'] if path.name.startswith('12_')
                       else ['--unwind', '5'])
        result = run(path, esbmc_command=esbmc_command, bound=5, timeout_seconds=timeout_seconds,
                     bound_flags=bound_flags, extra_flags=['--no-pointer-check', '--no-align-check'],
                     multi_property=True)
        output = esbmc_output(result)
        output = f'{output}\n{result.stderr}'
        lines = output.splitlines()
        detail = next((line.strip() for line in lines if 'ERROR:' in line or 'Violated property:' in line
                       or 'ESBMC caught SIGSEGV' in line), '')
        if detail == 'Violated property:':
            index = next(i for i, line in enumerate(lines) if 'Violated property:' in line)
            detail = next((line.strip() for line in lines[index + 1:]
                           if line.strip() and not line.strip().startswith('file ')), detail)
        if result.status == 'timeout':
            outcome = 'timeout'
        elif (result.returncode in (-11, 139) or 'ESBMC caught SIGSEGV' in output
              or any(_CRASH.search(line) for line in lines if 'ERROR:' in line or 'uncaught exception [' in line)):
            outcome = 'crash'
        elif result.status in {'no_violation_found', 'no_vcc_generated'} and 'VERIFICATION SUCCESSFUL' in output:
            outcome = 'successful'
        elif result.status == 'violation_found' or 'VERIFICATION FAILED' in output:
            outcome = 'failed'
        else:
            outcome = 'refused'
            if not detail:
                detail = next((line.strip() for line in lines if _LANGUAGE.search(line)), result.summary)
        outcomes[path.name] = {'outcome': outcome, 'detail': detail}
    return outcomes


def diff_outcomes(old: dict[str, dict], new: dict[str, dict]) -> dict[str, list[str]]:
    common = old.keys() & new.keys()
    return {'changed': sorted(k for k in common if old[k]['outcome'] != new[k]['outcome']),
            'unchanged': sorted(k for k in common if old[k]['outcome'] == new[k]['outcome']),
            'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys())}


def compare_baseline(path: Path, outcomes: dict[str, dict], *, identity: dict) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'identity': identity, 'outcomes': outcomes}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return {'comparison': None, 'message': 'Base criada, sem comparação.'}
    previous = json.loads(path.read_text(encoding='utf-8'))
    comparison = diff_outcomes(previous['outcomes'], outcomes)
    changed = any(comparison[key] for key in ('changed', 'added', 'removed'))
    message = 'Resultado mudou, conferir.' if changed else 'Resultado sem mudança nas categorias.'
    return {'comparison': comparison, 'message': message}
