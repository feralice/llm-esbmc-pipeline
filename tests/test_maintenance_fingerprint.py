import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_pipeline.maintenance.fingerprint import pipeline_fingerprint


@pytest.fixture(autouse=True)
def simulated_windows_disk(monkeypatch):
    original = Path.is_dir
    monkeypatch.setattr(Path, 'is_dir', lambda path: True if str(path) == '/mnt/c' else original(path))


def test_fingerprint_does_not_run_probes_when_windows_disk_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.esbmc_identity',
                        lambda command: {'version': 'ESBMC version 8.6.0'})
    monkeypatch.setattr(shutil, 'disk_usage',
                        lambda path: SimpleNamespace(free=1))
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.run_probes',
                        lambda *args, **kwargs: pytest.fail('não executar sondas'))
    with pytest.raises(RuntimeError, match='espaço'):
        pipeline_fingerprint(tmp_path, esbmc_command=['esbmc'])


def test_fingerprint_uses_monitored_probes_and_retains_their_state(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.esbmc_identity',
                        lambda command: {'version': 'ESBMC version 8.6.0'})
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=10 * 1024 ** 3))
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.notebook_version', lambda path: 'notebook')
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='abc'))
    seen = []
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.run_probes',
                        lambda *args: seen.append(args) or {'reason': 'sondas indisponíveis', 'results': {}})
    result = pipeline_fingerprint(tmp_path, esbmc_command=['esbmc'], cache_dir=tmp_path / 'cache')
    assert result['rules']['reason'] == 'sondas indisponíveis'
    assert seen and seen[0][1] == tmp_path / 'cache'


def test_fingerprint_rejects_when_esbmc_changes_during_probes(tmp_path, monkeypatch):
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.esbmc_identity',
                        lambda command: {'version': 'ESBMC version 8.6.0', 'files': {'bin': 'a'}})
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=10 * 1024 ** 3))
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.notebook_version', lambda path: 'notebook')
    monkeypatch.setattr('research_pipeline.maintenance.fingerprint.run_probes', lambda *args:
                        {'reason': 'sondas', 'results': {}, 'identity': {'version': 'ESBMC version 8.6.0', 'files': {'bin': 'b'}}})
    with pytest.raises(RuntimeError, match='identidade'):
        pipeline_fingerprint(tmp_path, esbmc_command=['esbmc'])
