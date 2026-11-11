"""Identidade do código e do verificador usados na manutenção."""

from __future__ import annotations

import resource
import shutil
import subprocess
from pathlib import Path

from research_pipeline.verify.capabilities import esbmc_identity
from research_pipeline.verify.lessons import notebook_version

from .execution import run_probes


def pipeline_fingerprint(root: Path, *, esbmc_command: list[str] | None = None,
                         cache_dir: Path | None = None) -> dict:
    command = esbmc_command or [str(Path.home() / 'esbmc-master/build-bw/src/esbmc/esbmc')]
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    identity = esbmc_identity(command)
    version = identity.get('version', '')
    if not version or version.startswith('unavailable:') or 'ESBMC version' not in version:
        raise RuntimeError(f'ESBMC ausente ou versão indisponível: {version}')
    def git(*args: str) -> str:
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()
    notebook = root / 'src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md'
    windows_disk = Path('/mnt/c')
    if windows_disk.is_dir() and shutil.disk_usage(windows_disk).free < 3 * 1024 ** 3:
        raise RuntimeError('espaço insuficiente no disco C para executar sondas')
    rules = run_probes(root, cache_dir or root / 'artifacts/esbmc_capabilities', command)
    if rules.get('reason') == 'sondas' and rules.get('identity') != identity:
        raise RuntimeError('A identidade do ESBMC mudou durante as sondas')
    return {'git_commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
            'notebook_version': notebook_version(notebook), 'rules': rules, 'esbmc_identity': identity}
