"""What may run on the host during a replay, and the process limits it runs under."""

from __future__ import annotations

import ast

_SAFE_MODULES = frozenset({
    "abc", "bisect", "collections", "copy", "dataclasses", "decimal", "enum", "fractions",
    "functools", "heapq", "itertools", "json", "math", "numbers", "operator", "re",
    "statistics", "string", "textwrap", "typing", "typing_extensions", "unicodedata",
})


# Introspection that reaches other objects' globals, builtins or code (the classic escapes, e.g.
# ().__class__.__bases__[0].__subclasses__()); protocol methods such as __len__ or __eq__ are ordinary code.
_UNSAFE_DUNDERS = frozenset({
    "__subclasses__", "__globals__", "__builtins__", "__code__", "__bases__", "__base__", "__mro__",
    "__getattribute__", "__loader__", "__spec__", "__import__", "__reduce__", "__reduce_ex__",
    "__closure__", "__func__", "__self__", "__dict__", "__module__", "__qualname__", "__defaults__",
    "__kwdefaults__", "__traceback__", "__frame__",
})


# Modules that safe modules re-export (typing.sys, dataclasses.inspect, collections._sys...) and
# operator's string-driven attribute access: reaching them reaches everything.
_UNSAFE_MEMBERS = frozenset({
    "sys", "_sys", "os", "_os", "inspect", "builtins", "importlib", "subprocess", "modules",
    "attrgetter", "methodcaller",
})
_UNSAFE_PREFIXES = ("f_", "gi_", "cr_", "ag_", "tb_", "co_")
# Attribute access by name is safe only with a literal, non-dunder name.
_NAMED_ACCESS = frozenset({"getattr", "setattr", "delattr", "hasattr"})


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
            if isinstance(node, ast.ImportFrom):
                hidden = [alias.name for alias in node.names if alias.name in _UNSAFE_MEMBERS]
                if hidden:
                    return f"imports {', '.join(hidden)} from {node.module}"
        elif isinstance(node, ast.Name) and node.id in _UNSAFE_NAMES:
            return f"uses {node.id}"
        elif isinstance(node, ast.Attribute) and (node.attr in _UNSAFE_DUNDERS or node.attr in _UNSAFE_MEMBERS
                                                  or node.attr.startswith(_UNSAFE_PREFIXES)):
            return f"uses introspection attribute {node.attr}"
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _NAMED_ACCESS
              and not (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                       and isinstance(node.args[1].value, str) and not node.args[1].value.startswith("__"))):
            return f"uses {node.func.id} without a literal attribute name"
    return ""


def process_limits(timeout_seconds: int, memory_bytes: int = 512 * 1024 * 1024):
    """preexec_fn for subprocess: CPU time, address space and no child processes."""
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return apply
