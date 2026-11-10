"""What may run on the host during a replay, and the process limits it runs under."""

from __future__ import annotations

import ast

_SAFE_MODULES = frozenset({
    "abc", "bisect", "collections", "copy", "dataclasses", "decimal", "enum", "fractions",
    "functools", "heapq", "itertools", "json", "math", "numbers", "operator", "random", "re",
    "statistics", "string", "textwrap", "time", "typing", "typing_extensions", "unicodedata",
})
_SAFE_OS_PATH = frozenset({"basename", "dirname", "getsize", "isabs", "join", "normcase", "normpath", "split",
                            "splitext"})
_SAFE_OS_MEMBERS = frozenset({"environ", "getenv", "path"})


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


def _only_asyncio_run(tree: ast.Module) -> bool:
    """The harness runs a coroutine with ``asyncio.run``; the rest of asyncio (subprocesses, sockets) stays out."""
    runs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "run"}
    return all(id(n) in runs for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "asyncio")


def _own_dict(node: ast.Attribute) -> bool:
    """``self.__dict__`` only lists the instance's own attributes; on a module or function it would reach globals."""
    return node.attr == "__dict__" and isinstance(node.value, ast.Name) and node.value.id == "self"


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (*_attribute_path(node.value), node.attr)
    return ()


def _os_environ_target(node: ast.AST) -> bool:
    while isinstance(node, ast.Subscript):
        node = node.value
    return _attribute_path(node)[:2] == ("os", "environ")


def host_replay_problem(source: str) -> str:
    """Why ``source`` must not run on the host, or "" when it only computes."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    safe = _SAFE_MODULES | {"os"} | ({"asyncio"} if _only_asyncio_run(tree) else set())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "asyncio" and a.asname not in (None, "asyncio")
                                                for a in node.names):
            return "imports asyncio under another name"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if isinstance(node, ast.ImportFrom) and names[0].split(".")[0] == "asyncio":
                return "imports from asyncio"
            if isinstance(node, ast.Import):
                os_imports = [alias for alias in node.names if alias.name.split(".")[0] == "os"]
                if any(alias.asname for alias in os_imports):
                    return "imports os under another name"
            elif node.module == "os":
                members = {alias.name for alias in node.names}
                if any(alias.asname for alias in node.names) or "*" in members or not members <= _SAFE_OS_MEMBERS:
                    return f"imports unsafe member from os: {', '.join(sorted(members - _SAFE_OS_MEMBERS)) or 'alias'}"
            elif node.module == "os.path":
                members = {alias.name for alias in node.names}
                if any(alias.asname for alias in node.names) or "*" in members or not members <= _SAFE_OS_PATH:
                    return f"imports unsafe member from os.path: {', '.join(sorted(members - _SAFE_OS_PATH)) or 'alias'}"
            unsafe = [name for name in names if name.split(".")[0] not in safe]
            if unsafe or (isinstance(node, ast.ImportFrom) and node.level):
                return f"imports {', '.join(unsafe) or 'a relative module'}"
            if isinstance(node, ast.ImportFrom):
                hidden = [alias.name for alias in node.names if alias.name in _UNSAFE_MEMBERS]
                if hidden:
                    return f"imports {', '.join(hidden)} from {node.module}"
        elif isinstance(node, ast.Name) and node.id in _UNSAFE_NAMES:
            return f"uses {node.id}"
        elif isinstance(node, ast.Attribute):
            if _own_dict(node):
                continue
            path = _attribute_path(node)
            if path[:1] == ("os",):
                allowed = (path in {("os", "path"), ("os", "environ"), ("os", "getenv"),
                                    ("os", "environ", "get")}
                           or (len(path) == 3 and path[:2] == ("os", "path") and path[2] in _SAFE_OS_PATH))
                if not allowed:
                    return f"uses unsupported os member: {'.'.join(path[1:])}"
            if node.attr in _UNSAFE_DUNDERS or node.attr in _UNSAFE_MEMBERS or node.attr.startswith(_UNSAFE_PREFIXES):
                return f"uses introspection attribute {node.attr}"
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if hasattr(node, "target")
                                                                         else node.targets)
            if any(_os_environ_target(target) for target in targets):
                return "writes os.environ"
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _NAMED_ACCESS
              and not (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                       and isinstance(node.args[1].value, str) and not node.args[1].value.startswith("__"))):
            return f"uses {node.func.id} without a literal attribute name"
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _NAMED_ACCESS
              and node.args and _attribute_path(node.args[0])[:1] == ("os",)):
            return f"uses {node.func.id} on os"
    return ""


def process_limits(timeout_seconds: int, memory_bytes: int = 512 * 1024 * 1024):
    """preexec_fn for subprocess: CPU time, address space and no child processes."""
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return apply
