"""What may run on the host during a replay, and the process limits it runs under."""

from __future__ import annotations

import ast

_SAFE_MODULES = frozenset({
    "abc", "bisect", "collections", "copy", "dataclasses", "decimal", "enum", "fractions",
    "functools", "heapq", "itertools", "json", "math", "numbers", "operator", "re",
    "statistics", "string", "textwrap", "typing", "typing_extensions", "unicodedata",
})


_UNSAFE_NAMES = frozenset({
    "open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
    "input", "breakpoint", "exit", "quit", "__builtins__",
})


def host_replay_problem(source: str) -> str:
    """Why ``source`` must not run on the host, or "" when it only computes."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            unsafe = [name for name in names if name.split(".")[0] not in _SAFE_MODULES]
            if unsafe or (isinstance(node, ast.ImportFrom) and node.level):
                return f"imports {', '.join(unsafe) or 'a relative module'}"
        elif isinstance(node, ast.Name) and node.id in _UNSAFE_NAMES:
            return f"uses {node.id}"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in {"__init__", "__name__", "__class__"}:
            return f"uses dunder attribute {node.attr}"
    return ""


def process_limits(timeout_seconds: int, memory_bytes: int = 512 * 1024 * 1024):
    """preexec_fn for subprocess: CPU time, address space and no child processes."""
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return apply
