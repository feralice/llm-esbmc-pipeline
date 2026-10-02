"""A pytest reproducer for a confirmed bug, written by ESBMC's own generator and checked by running it.

ESBMC's --generate-pytest-testcase (https://esbmc.github.io/docs/python/pytest-testgen/) writes a
parametrized test from its counterexample. Measured on ESBMC 8.5 and master (2026-10-01), it only
emits a usable test for a free function called with ``__VERIFIER_nondet_*()`` arguments: with a
receiver it prints internal names (``x&0#1``), and with several arguments it may drop some. So the
program is rewritten into that shape, the test is run under pytest, and it is kept only when it
fails with the bug's exception, which is how ESBMC's tests show a bug (they carry no assert).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from .render import Program
from .replay import _no_network_prefix
from .sandbox import host_replay_problem, process_limits
from .spec import parse_type

_SCALARS = {"int", "float", "bool", "str"}


def _source_without_driver(source: str, driver_start: int) -> list[str]:
    return source.splitlines()[:driver_start - 1]


def pytest_reproducer(program: Program, *, function: str, params: dict[str, str], exception: str,
                      esbmc_command: list[str], bound: int, out_dir: Path, name: str,
                      timeout_seconds: int = 120) -> dict:
    """Try ESBMC's generator on the confirmed program; returns {"status", "path", "reason"}."""
    if "." in function:
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator handles free functions only"}
    types = [parse_type(text) for text in params.values()]
    if any(t is None or t.kind not in _SCALARS or t.optional for t in types):
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator here needs scalar inputs"}
    out_dir.mkdir(parents=True, exist_ok=True)
    module = out_dir / f"{name}.py"
    call = f"{function}({', '.join(f'__VERIFIER_nondet_{t.kind}()' for t in types)})"
    module.write_text("\n".join([*_source_without_driver(program.source, program.driver_start), call]) + "\n",
                      encoding="utf-8")
    test = out_dir / f"test_{name}.py"
    test.unlink(missing_ok=True)
    try:
        subprocess.run([*esbmc_command, str(module), "--unwind", str(bound), "--generate-pytest-testcase",
                        "--pytest-output-dir", str(out_dir)], capture_output=True, text=True,
                       timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "not_generated", "path": "", "reason": f"ESBMC did not finish: {type(exc).__name__}"}
    if not test.exists():
        return {"status": "not_generated", "path": "", "reason": "ESBMC wrote no test"}
    try:
        ast.parse(test.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return {"status": "invalid", "path": str(test), "reason": f"ESBMC wrote invalid Python: {exc.msg}"}
    # The test imports the module: CPython gets the replayed program (real exceptions), without the call.
    library = "\n".join(_source_without_driver(program.replay_source or program.source, program.driver_start)) + "\n"
    problem = host_replay_problem(library)
    if problem:
        return {"status": "not_run", "path": str(test), "reason": f"not executed on host: {problem}"}
    module.write_text(library, encoding="utf-8")
    try:
        done = subprocess.run([*_no_network_prefix(), sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                               test.name], cwd=out_dir, capture_output=True, text=True, timeout=60, check=False,
                              env={key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ},
                              preexec_fn=process_limits(60))
    except subprocess.TimeoutExpired:
        return {"status": "invalid", "path": str(test), "reason": "pytest timed out"}
    output = done.stdout + done.stderr
    tail = " ".join(output.strip().splitlines()[-2:])[:300]
    if "No module named pytest" in output:
        return {"status": "not_run", "path": str(test), "reason": "pytest is not installed"}
    if f"- {exception}" in output or f"E   {exception}" in output:
        return {"status": "reproduces", "path": str(test), "reason": f"pytest fails with {exception}"}
    if done.returncode == 0:
        return {"status": "does_not_reproduce", "path": str(test), "reason": tail}
    # Any other failure (a missing argument, an import error) is a defect of the generated test.
    return {"status": "invalid", "path": str(test), "reason": tail}
