"""Regressions for the boundary around untrusted Python, without running an LLM."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from research_pipeline.verify.sandbox import host_replay_problem


def _environment():
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}


@pytest.mark.parametrize("source", [
    "import random\nself = random\nx = self.__dict__['_os']\n",
    "from random import __builtins__ as b\n",
    "x = getattr(generator, 'gi_frame')\n",
    "x = getattr(frame, 'f_builtins')\n",
    "from random import *\n",
])
def test_indirect_access_to_host_objects_is_rejected(source):
    assert host_replay_problem(source)


def test_own_instance_dict_remains_available():
    assert host_replay_problem("class A:\n    def f(self):\n        return list(self.__dict__)\n") == ""


def test_kernel_boundary_preserves_external_files_and_allows_local_results(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("preserve this")
    scratch = tmp_path / "worker"
    scratch.mkdir()
    script = """
import json, os, sys
from pathlib import Path
from research_pipeline.verify.confinement import IsolationUnavailable, confine_writes
outside, work = Path(sys.argv[1]), Path(sys.argv[2])
try:
    confine_writes(work)
except IsolationUnavailable as exc:
    print(json.dumps({'unavailable': str(exc)}))
    raise SystemExit(0)
blocked = []
for operation in (
    lambda: outside.write_text('changed'),
    lambda: os.truncate(outside, 0),
    lambda: outside.unlink(),
    lambda: outside.chmod(0),
    lambda: outside.rename(work / 'stolen'),
    lambda: (outside.parent / 'unexpected').mkdir(),
):
    try:
        operation()
    except OSError:
        blocked.append(True)
    else:
        blocked.append(False)
(work / 'result.json').write_text(json.dumps(blocked))
print(json.dumps({'blocked': blocked}))
"""
    done = subprocess.run([sys.executable, "-c", script, str(sentinel), str(scratch)],
                          capture_output=True, text=True, check=True, env=_environment())
    data = json.loads(done.stdout)
    if "unavailable" in data:
        pytest.skip(data["unavailable"])
    assert data["blocked"] == [True] * 6
    assert sentinel.read_text() == "preserve this"
    assert not (tmp_path / "unexpected").exists()
    assert json.loads((scratch / "result.json").read_text()) == [True] * 6


def test_unsupported_isolation_fails_before_changing_process(monkeypatch, tmp_path):
    from research_pipeline.verify import confinement

    monkeypatch.setattr(confinement.sys, "platform", "unsupported")
    with pytest.raises(confinement.IsolationUnavailable, match="Linux"):
        confinement.confine_writes(tmp_path)


def test_real_module_import_cannot_write_outside_the_worker(tmp_path):
    from research_pipeline.verify.differential import differential
    from research_pipeline.verify.hypothesis import BugHypothesis

    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("original")
    source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('changed')\n\ndef f(x):\n    return 1 // x\n"
    original = tmp_path / "original.py"
    original.write_text(source)
    harness = "def f(x: int):\n    return 1 // x\n\ndef main():\n    x: int = nondet_int()\n    f(x)\n\nmain()\n"
    result = differential(harness, source, BugHypothesis(str(original), "f", "1 // x"),
                          {"int": [0]}, runs=1, original_path=original)
    assert sentinel.read_text() == "original"
    assert result.level == "stubs"
    assert "PermissionError" in result.reason or "isolation" in result.reason


def test_replay_worker_records_unavailable_if_isolation_cannot_start(monkeypatch, tmp_path):
    from research_pipeline.verify import confinement, replay_worker

    def unavailable(directory):
        raise confinement.IsolationUnavailable("test isolation unavailable")

    monkeypatch.setattr(replay_worker, "confine_writes", unavailable)
    program = tmp_path / "program.py"
    program.write_text("raise AssertionError('must not execute')\n")
    config = tmp_path / "config.json"
    config.write_text('{}')
    output = tmp_path / "output.json"
    replay_worker.main(str(program), str(config), str(output))
    data = json.loads(output.read_text())
    assert data["status"] == "unavailable"
    assert "isolation" in data["reason"]


def test_confined_worker_cannot_signal_its_parent(tmp_path):
    script = """
import os, signal, sys
from pathlib import Path
from research_pipeline.verify.confinement import IsolationUnavailable, confine_writes
parent = os.getppid()
try:
    confine_writes(Path(sys.argv[1]))
except IsolationUnavailable:
    raise SystemExit(77)
blocked = []
try:
    os.kill(parent, 0)
except PermissionError:
    blocked.append(True)
else:
    blocked.append(False)
if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
    fd = os.pidfd_open(parent)
    try:
        try:
            signal.pidfd_send_signal(fd, 0)
        except PermissionError:
            blocked.append(True)
        else:
            blocked.append(False)
    finally:
        os.close(fd)
print(all(blocked))
"""
    done = subprocess.run([sys.executable, "-c", script, str(tmp_path)], capture_output=True,
                          text=True, check=False, env=_environment())
    if done.returncode == 77:
        pytest.skip("OS isolation unavailable")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "True"
