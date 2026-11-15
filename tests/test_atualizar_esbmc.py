import json
import os
import subprocess
from pathlib import Path

from test_esbmc_provenance import checkout

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/atualizar_esbmc.sh'


def test_update_check_only_reads_metadata(tmp_path):
    root, binary, _ = checkout(tmp_path)
    build = root / 'build-bw'
    build.mkdir()
    (build / 'CMakeCache.txt').write_text('ENABLE_BITWUZLA:BOOL=On\nENABLE_Z3:BOOL=On\n')
    before = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'])
    done = subprocess.run(['bash', str(SCRIPT), '--check'], capture_output=True, text=True,
                          env={**os.environ, 'ESBMC_UPDATE_ROOT': str(root),
                               'ESBMC_UPDATE_BINARY': str(binary)})
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)['binary'] == str(binary)
    assert subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain']) == before


def test_update_requires_explicit_execution_mode():
    done = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True)
    assert done.returncode == 2
    assert '--execute' in done.stderr
