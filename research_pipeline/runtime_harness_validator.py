"""runtime_harness_validator.py — Executa harnesses mínimos gerados pela LLM em ambiente controlado.

Responsabilidades:
  1. Receber o código-fonte original e um harness mínimo (corpo de chamada).
  2. Validar o harness via AST antes de qualquer execução (rejeitar construções perigosas).
  3. Montar arquivo temporário e executar em subprocess isolado com timeout.
  4. Capturar e comparar a exceção levantada com a exceção esperada.
  5. Retornar resultado estruturado sem vazar segredos de ambiente.

Este módulo é fallback para casos em que o Formalizer não consegue gerar uma
propriedade formal verificável pelo ESBMC. Não substitui o ESBMC.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

HARNESS_REPRODUCED      = "reproduced"
HARNESS_NOT_REPRODUCED  = "not_reproduced"
HARNESS_WRONG_EXCEPTION = "wrong_exception"
HARNESS_TIMEOUT         = "timeout"
HARNESS_UNSAFE          = "unsafe_harness"
HARNESS_EXECUTION_ERROR = "execution_error"
HARNESS_SKIPPED         = "skipped"

# ---------------------------------------------------------------------------
# Safety allowlist / blocklist (validado via AST, não via regex)
# ---------------------------------------------------------------------------

_FORBIDDEN_AST_NODES = (ast.Import, ast.ImportFrom, ast.While)

_FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset({
    "open", "eval", "exec", "input", "compile",
    "globals", "locals", "__import__",
    "setattr", "delattr", "getattr",
})

_FORBIDDEN_ATTRIBUTES: frozenset[str] = frozenset({
    "__class__", "__subclasses__", "__globals__", "__builtins__",
    "__dict__", "__code__", "__bases__", "__mro__", "__import__",
})

_FORBIDDEN_NAME_FRAGMENTS: frozenset[str] = frozenset({
    "subprocess", "socket", "requests", "urllib",
    "http", "ftp", "pathlib", "shutil", "glob",
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class HarnessValidationResult:
    status: str
    exception_type: str = ""
    inputs: str = ""
    stdout: str = ""
    stderr: str = ""
    traceback_summary: str = ""
    time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "exception_type": self.exception_type,
            "inputs": self.inputs,
            "stdout": self.stdout[:500],
            "stderr": self.stderr[:500],
            "traceback_summary": self.traceback_summary[:500],
            "time_seconds": round(self.time_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_harness(
    source_code: str,
    function_name: str,
    harness_body: str,
    expected_exception: str,
    timeout_seconds: float = 5.0,
) -> HarnessValidationResult:
    """Execute a LLM-generated reproduction harness in a controlled subprocess.

    Args:
        source_code: full source of the file containing the function under test.
        function_name: name of the function being tested (informational).
        harness_body: minimal call expression(s), e.g. 'remove_upstream_option([], 0)'.
        expected_exception: exception class name expected, e.g. 'IndexError'.
        timeout_seconds: maximum execution time before HARNESS_TIMEOUT.

    Returns:
        HarnessValidationResult with status and captured output.
    """
    if not harness_body or not harness_body.strip():
        return HarnessValidationResult(status=HARNESS_SKIPPED)

    if not _is_safe(harness_body):
        return HarnessValidationResult(status=HARNESS_UNSAFE)

    temp_source = _build_runnable_source(source_code, harness_body)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(temp_source)
        tmp_path = Path(tmp.name)

    try:
        return _run_and_classify(tmp_path, expected_exception, timeout_seconds)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Safety validation (AST-based)
# ---------------------------------------------------------------------------

def _is_safe(harness_body: str) -> bool:
    """Return True only if the harness contains no dangerous constructs."""
    try:
        tree = ast.parse(harness_body)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            return False

        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _FORBIDDEN_CALL_NAMES:
                return False
            if any(fragment in name for fragment in _FORBIDDEN_NAME_FRAGMENTS):
                return False

        if isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRIBUTES:
                return False
            if any(fragment in node.attr for fragment in _FORBIDDEN_NAME_FRAGMENTS):
                return False

        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAME_FRAGMENTS:
                return False

    return True


def _call_name(node: ast.Call) -> str:
    try:
        return ast.unparse(node.func)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Temp file builder
# ---------------------------------------------------------------------------

def _build_runnable_source(source_code: str, harness_body: str) -> str:
    """Wrap source + harness in a try/except that prints a structured result line."""
    indented = textwrap.indent(harness_body.strip(), "    ")
    return textwrap.dedent(f"""\
{source_code}

import traceback as _tb
try:
{indented}
    print("__RESULT__:NO_EXCEPTION")
except Exception as _exc:
    _etype = type(_exc).__name__
    _lines = _tb.format_exc().splitlines()
    _last  = next((ln for ln in reversed(_lines) if ln.strip()), "")
    print(f"__RESULT__:EXCEPTION:{{_etype}}:{{_last[:200]}}")
""")


# ---------------------------------------------------------------------------
# Execution and classification
# ---------------------------------------------------------------------------

def _run_and_classify(
    tmp_path: Path,
    expected_exception: str,
    timeout_seconds: float,
) -> HarnessValidationResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return HarnessValidationResult(
            status=HARNESS_TIMEOUT,
            time_seconds=round(timeout_seconds, 3),
        )

    elapsed = round(time.monotonic() - start, 3)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""

    result_line = next(
        (line for line in stdout.splitlines() if line.startswith("__RESULT__:")),
        None,
    )

    if result_line is None:
        return HarnessValidationResult(
            status=HARNESS_EXECUTION_ERROR,
            stdout=stdout[:500],
            stderr=stderr[:500],
            time_seconds=elapsed,
        )

    parts = result_line.split(":", 3)

    if len(parts) >= 2 and parts[1] == "NO_EXCEPTION":
        return HarnessValidationResult(
            status=HARNESS_NOT_REPRODUCED,
            stdout=stdout[:500],
            time_seconds=elapsed,
        )

    exception_type    = parts[2] if len(parts) > 2 else ""
    traceback_summary = parts[3] if len(parts) > 3 else ""

    status = _match_exception(exception_type, expected_exception)

    return HarnessValidationResult(
        status=status,
        exception_type=exception_type,
        traceback_summary=traceback_summary,
        stdout=stdout[:500],
        stderr=stderr[:500],
        time_seconds=elapsed,
    )


def _match_exception(got: str, expected: str) -> str:
    """Return REPRODUCED, WRONG_EXCEPTION, or NOT_REPRODUCED."""
    if not got:
        return HARNESS_NOT_REPRODUCED
    if not expected:
        return HARNESS_REPRODUCED
    # Normalize: ZeroDivisionError == ZeroDivisionError, also accept partial match
    if got == expected or got in expected or expected in got:
        return HARNESS_REPRODUCED
    return HARNESS_WRONG_EXCEPTION


# ---------------------------------------------------------------------------
# Existence check (used by findings.py to replace strict AST-kind gating)
# ---------------------------------------------------------------------------

_EXECUTABLE_NODE_TYPES = (ast.Call, ast.Subscript, ast.BinOp, ast.Compare, ast.Attribute)


def expression_exists_in_executable_ast(expression: str, unit_source: str) -> bool:
    """Return True if expression matches an executable AST node in the function source.

    Parses both the expression and the unit source as AST and compares via
    ast.unparse — immune to comments (stripped by parser) and string literals
    (represented as ast.Constant, not as Call/Subscript/BinOp).
    """
    if not expression:
        return False
    try:
        target = ast.unparse(ast.parse(expression, mode="eval").body)
    except SyntaxError:
        return False
    try:
        unit_tree = ast.parse(unit_source)
    except SyntaxError:
        return False
    for node in ast.walk(unit_tree):
        if isinstance(node, _EXECUTABLE_NODE_TYPES):
            try:
                if ast.unparse(node) == target:
                    return True
            except Exception:
                continue
    return False
