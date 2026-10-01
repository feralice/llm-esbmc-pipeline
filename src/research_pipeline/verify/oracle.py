"""Ask ESBMC which library members it cannot convert, instead of keeping a hand-written list.

The conversion alone (``--goto-functions-only``) takes about a second and names what it refuses;
those members are stubbed and the program is converted again. Anything else it reports is left to
the real verification run.
"""

from __future__ import annotations

import ast
import re
import subprocess
import tempfile
from pathlib import Path

from .slicing import import_bindings

# Diagnostics of ESBMC 8.5 and master (2026-10-01) that name one library member or module.
_MODULE = re.compile(r"no operational model for module '([\w.]+)'")
_UNDEFINED = re.compile(r"Undefined function '(\w+)' - replacing with assert\(false\)")
_NUMPY = (re.compile(r"Unsupported NumPy function call: (\w+)"),
          re.compile(r"numpy\.(\w+)\(\) currently supports"))
_NOT_YET = re.compile(r"([\w.]+)\.(\w+) is not yet supported by ESBMC")
_OBJECT = re.compile(r'Object "(\w+)" not found')


def _defined(tree: ast.Module) -> set[str]:
    """Names the program itself defines or binds, at any level."""
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    return names | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def refusals(diagnostics: str, source: str) -> set[str]:
    """Modules and ``module.member`` entries the diagnostics refuse, as the program imports them."""
    tree = ast.parse(source)
    modules, members = import_bindings(tree)
    found = {m.split(".")[0] for m in _MODULE.findall(diagnostics)}
    found |= {modules[name].split(".")[0] for name in _OBJECT.findall(diagnostics) if name in modules}
    for pattern in _NUMPY:
        found |= {f"numpy.{name}" for name in pattern.findall(diagnostics)}
    for prefix, member in _NOT_YET.findall(diagnostics):
        head, _, rest = prefix.partition(".")
        module = modules.get(head, head) + (f".{rest}" if rest else "")
        found.add(f"{module}.{member}")
    # The program's own function of that name (a method, say) is not the library's.
    undefined = set(_UNDEFINED.findall(diagnostics)) - _defined(tree)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr in undefined
                and isinstance(node.value, ast.Name) and node.value.id in modules):
            found.add(f"{modules[node.value.id]}.{node.attr}")
    found |= {members[name] for name in undefined if name in members}
    return found


def convert(source: str, esbmc_command: list[str], timeout_seconds: int = 60) -> str:
    """ESBMC's diagnostics for converting ``source`` to GOTO, without solving anything."""
    with tempfile.TemporaryDirectory(prefix="esbmc_oracle_") as tmp:
        path = Path(tmp) / "program.py"
        path.write_text(source, encoding="utf-8")
        try:
            done = subprocess.run([*esbmc_command, str(path), "--goto-functions-only"], capture_output=True,
                                  text=True, timeout=timeout_seconds, check=False)
        except (subprocess.TimeoutExpired, OSError):
            # No diagnostics: the harness keeps every import, and the real run reports the problem.
            return ""
    return done.stdout + done.stderr
