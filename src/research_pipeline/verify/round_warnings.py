"""Cheap checks on each round's harness: did the target body change, and does mypy --strict report errors
the original does not have (a base class emptied by the harness shows up there)."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .astutil import find_function
from .preservation import same_code

NOT_MEASURED = "mypy: não medido"
_LOCATION = re.compile(r"^.*?:\d+(:\d+)?: ")


def _mypy_command() -> list[str]:
    return [sys.executable, "-m", "mypy", "--strict", "--no-error-summary"]


def mypy_messages(source: str, timeout: int) -> list[str] | None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "program.py"
        path.write_text(source, encoding="utf-8")
        try:
            run = subprocess.run([*_mypy_command(), str(path)], capture_output=True, text=True,
                                 timeout=timeout, cwd=folder)
        except (OSError, subprocess.TimeoutExpired):
            return None
    if run.returncode not in (0, 1) or run.stderr.strip():
        return None
    return [_LOCATION.sub("", line) for line in run.stdout.splitlines() if ": error: " in line or ": note: " in line]


_UNSET: list[str] = []


def mypy_new_errors(original: str, harness: str, timeout: int = 60,
                    original_messages: list[str] | None = _UNSET) -> list[str] | None:
    """Errors mypy reports for the harness and not for the original; None when mypy could not be run.
    ``original_messages`` carries a prior ``mypy_messages(original)`` (None included) so a case measures it once."""
    before = mypy_messages(original, timeout) if original_messages is _UNSET else original_messages
    after = mypy_messages(harness, timeout)
    if before is None or after is None:
        return None
    return [message for message in dict.fromkeys(after) if message not in before]


def _target(source: str, function: str) -> tuple[ast.Module | None, ast.FunctionDef | None]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None, None
    return tree, find_function(tree, function)


def _body_changed(source: str, original: str, function: str) -> bool:
    (original_tree, before), (tree, after) = _target(original, function), _target(source, function)
    if before is None or after is None:
        return (before is None) != (after is None)
    return not same_code(before, after, original_tree, tree)


def round_warnings(source: str, original: str, function: str, mypy_timeout: int = 60,
                   original_messages: list[str] | None = _UNSET) -> list[str]:
    warnings = []
    if _body_changed(source, original, function):
        warnings.append("body_changed")
    errors = mypy_new_errors(original, source, mypy_timeout, original_messages)
    if errors is None:
        warnings.append(NOT_MEASURED)
    else:
        warnings.extend(f"mypy_new:{error}" for error in errors)
    return warnings
