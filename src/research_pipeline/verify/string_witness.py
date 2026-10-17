"""The strings behind an ESBMC counterexample. The trace prints a nondet_str() only as a pointer
(docs/projeto/possiveis_problemas/45_nondet_str_contraexemplo.py), but ESBMC's pytest witness
(--generate-pytest-testcase --pytest-values-only) records its value; replay gets them as seeds."""

from __future__ import annotations

import ast
from pathlib import Path

from .esbmc_run import Runner
from research_pipeline.verification.esbmc_runner import run_esbmc_direct


def parse_witness(text: str) -> list:
    """The values of every witness entry, in file order; nothing when the file has no readable list."""
    try:
        body = ast.parse(text).body
    except SyntaxError:
        return []
    for node in body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "witness"):
            try:
                entries = ast.literal_eval(node.value)
            except ValueError:
                return []
            return [value for entry in entries if isinstance(entry, dict) for value in entry.values()]
    return []


def string_witness(path: Path, *, esbmc_command: list[str], bound: int, timeout_seconds: int, work_dir: Path,
                   runner: Runner | None = None) -> list[str]:
    """Run ESBMC again for its witness. It only extracts values: the verdict comes from the first run,
    so stopping at the first violation and dropping unwinding assertions here changes no verdict."""
    out = work_dir / "pytest_witness"
    (runner or run_esbmc_direct)(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                                 output_dir=work_dir / "esbmc_witness",
                                 bound_flags=["--unwind", str(bound), "--no-unwinding-assertions"],
                                 extra_flags=["--generate-pytest-testcase", "--pytest-values-only",
                                              "--pytest-output-dir", str(out)],
                                 multi_property=False)
    values = [v for f in sorted(out.glob("test_*.py")) for v in parse_witness(f.read_text(encoding="utf-8"))]
    return [v for v in values if isinstance(v, str)]
