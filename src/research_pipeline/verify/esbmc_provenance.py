"""Read the selected verifier's identity and compare its date with its checkout's commit."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import file_digest, sha256
from pathlib import Path

from .esbmc_knowledge import DOCS, README, esbmc_root_of, knowledge_digest


def _output(command: list[str]) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f'Não foi possível conferir a procedência do ESBMC: {exc}') from exc
    if done.returncode:
        raise ValueError(f'Não foi possível conferir a procedência do ESBMC: {done.stderr.strip()}')
    return done.stdout.strip()


def esbmc_provenance(esbmc_command: list[str]) -> dict:
    if not esbmc_command:
        raise ValueError('Informe o comando do ESBMC para conferir a procedência.')
    declared = Path(shutil.which(str(Path(esbmc_command[0]).expanduser())) or esbmc_command[0]).expanduser().absolute()
    command = declared.resolve()
    binary, declared_binary = command, declared
    try:
        if command.suffix == '.sh':
            target = re.search(r'(/\S+/esbmc)\b', command.read_text(encoding='utf-8'))
            if target is None:
                raise ValueError('Não foi possível identificar o binário no wrapper do ESBMC.')
            declared_binary = Path(target.group(1))
            binary = declared_binary.resolve()
        # The build directory may be a link to another disk: look for the checkout along the path as declared.
        root = esbmc_root_of([str(declared_binary)]) or esbmc_root_of([str(binary)])
        if root is None:
            raise ValueError('Não foi possível localizar o checkout do ESBMC; informe o binário compilado nele.')
        stat = binary.stat()
        version = _output([str(command), '--version'])
        if not version:
            raise ValueError('O ESBMC não informou sua versão.')
        with binary.open("rb") as stream:
            binary_hash = file_digest(stream, "sha256").hexdigest()
        return {
            'binary': str(binary), 'binary_sha256': binary_hash,
            'binary_mtime_ns': stat.st_mtime_ns,
            'binary_date': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            'version': version, 'repository_root': str(root),
            'commit': _output(['git', '-C', str(root), 'rev-parse', 'HEAD']),
            'commit_timestamp': int(_output(['git', '-C', str(root), 'show', '-s', '--format=%ct', 'HEAD'])),
            'dirty': bool(_output(['git', '-C', str(root), 'status', '--porcelain'])),
            'knowledge_sha256': knowledge_digest(root),
            'documents': {str(page): sha256((root / page).read_bytes()).hexdigest()
                          for page in (README, *DOCS) if (root / page).is_file()},
            **({'wrapper': str(command), 'wrapper_sha256': sha256(command.read_bytes()).hexdigest()}
               if command != binary else {}),
        }
    except OSError as exc:
        raise ValueError(f'Não foi possível ler o binário ou os documentos do ESBMC: {exc}') from exc


def check_fresh(provenance: dict) -> None:
    if provenance['binary_mtime_ns'] < provenance['commit_timestamp'] * 1_000_000_000:
        raise ValueError('O binário do ESBMC é anterior ao commit atual do checkout. '
                         'É necessário recompilar o ESBMC antes da rodada com o perfil congelado.')


def record_version(provenance: dict, path: Path) -> None:
    """Append identity after the update script has passed its regression checks."""
    header = ('| Data UTC | Commit | Versão | Binário | SHA-256 | Teste de regressão |\n'
              '|---|---|---|---|---|---|\n')
    if path.exists() and '| SHA-256 |' not in path.read_text(encoding='utf-8'):
        raise ValueError('O registro existente precisa da coluna SHA-256 antes de acrescentar uma versão.')
    cells = [datetime.now(timezone.utc).isoformat(), provenance['commit'], provenance['version'],
             provenance['binary'], provenance['binary_sha256'], 'cps_simpleio_43 confirmado antes e depois']
    row = '| ' + ' | '.join(str(cell).replace('\n', ' ').replace('|', '\\|') for cell in cells) + ' |\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('# Versões do ESBMC usadas nos experimentos\n\n' + header, encoding='utf-8')
    with path.open('a', encoding='utf-8') as stream:
        stream.write(row)


def check_update_checkout(root: Path) -> None:
    """The local launcher is expected; every other uncommitted change blocks the update."""
    pending = _output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all']).splitlines()
    if any(line != '?? esbmc.sh' for line in pending):
        raise ValueError('O checkout do ESBMC tem alterações locais além do wrapper esbmc.sh. '
                         'Resolva-as antes de atualizar; nada foi alterado.')
