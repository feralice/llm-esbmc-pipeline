"""Testa um patch em cópia isolada antes de aplicá-lo ao pipeline."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path


def _git_apply(root: Path, patch: bytes, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', 'apply', *flags, '-'], cwd=root, input=patch, capture_output=True, check=True)


def _targets(root: Path, patch: bytes) -> list[Path]:
    result = _git_apply(root, patch, '--numstat', '-z')
    entries = result.stdout.split(b'\0')
    paths = []
    for entry in filter(None, entries):
        fields = entry.decode('utf-8').split('\t')
        if len(fields) != 3 or '-' in fields[:2]:
            raise ValueError('Patch binário ou renomeação não são aceitos')
        path = Path(fields[2])
        if path.is_absolute() or '..' in path.parts or not path.parts[:3] == ('src', 'research_pipeline', 'verify'):
            raise ValueError('O patch deve alterar apenas código do verificador')
        resolved = (root / path).resolve()
        if not resolved.is_relative_to((root / 'src/research_pipeline/verify').resolve()):
            raise ValueError('Caminho fora do verificador')
        if not (root / path).is_file() or (root / path).is_symlink():
            raise ValueError('O patch deve alterar arquivos existentes, sem links')
        paths.append(path)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Patch vazio ou arquivo repetido')
    return paths


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    snapshot = {}
    for area in ('src', 'tests', 'dataset/disciplina_pgene601'):
        for path in (root / area).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.pyc'):
                snapshot[str(path.relative_to(root))] = _digest(path)
    return snapshot


def apply_proposal(root: Path, patch: bytes, *, scratch: Path, evaluate: Callable[[Path], dict]) -> dict:
    root = root.resolve()
    if scratch.resolve().is_relative_to(root):
        raise ValueError('A pasta temporária deve ficar fora do repositório')
    paths = _targets(root, patch)
    before = _snapshot(root)
    _git_apply(root, patch, '--check')
    scratch.mkdir(parents=True, exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix='candidato_', dir=scratch))
    ignored = shutil.ignore_patterns('.git', '.claude', '.codex', '.agents', '.aws', '.ssh', '.env', '.env.*',
                                     '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')
    shutil.copytree(root, candidate, dirs_exist_ok=True, ignore=ignored, symlinks=False)
    _git_apply(candidate, patch)
    if any(not (candidate / path).is_file() or (candidate / path).is_symlink() for path in paths):
        raise ValueError('Remoções e links não são aceitos')
    evaluation = evaluate(candidate)
    if evaluation.get('verdict') != 'ACEITA':
        return {'applied': False, 'gate': evaluation, 'candidate': str(candidate)}
    if _snapshot(root) != before or any((root / path).is_symlink() for path in paths):
        return {'applied': False, 'gate': evaluation, 'candidate': str(candidate),
                'reason': 'O código original mudou durante a avaliação'}
    _git_apply(root, patch, '--check')
    _git_apply(root, patch)
    return {'applied': True, 'gate': evaluation, 'candidate': str(candidate)}
