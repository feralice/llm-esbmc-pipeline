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
    "attrgetter", "methodcaller", "bltns", "eval", "exec", "globals", "locals", "vars",
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


def _in_read_position(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """``os.environ`` read by subscript or ``.get(...)``; anywhere else it is an alias the gate cannot follow."""
    parent = parents.get(node)
    if isinstance(parent, ast.Subscript) and parent.value is node:
        return isinstance(parent.ctx, ast.Load)
    if isinstance(parent, ast.Attribute) and parent.attr == "get":
        call = parents.get(parent)
        return isinstance(call, ast.Call) and call.func is parent
    return False


def _literal_named_access(node: ast.Name, parents: dict[ast.AST, ast.AST]) -> bool:
    """``getattr(obj, "name")`` with a literal, non-dunder, non-introspective name; any other use is an alias."""
    call = parents.get(node)
    if not (isinstance(call, ast.Call) and call.func is node and len(call.args) >= 2):
        return False
    name = call.args[1]
    return (isinstance(name, ast.Constant) and isinstance(name.value, str)
            and not name.value.startswith("__") and not _unsafe_attribute(name.value))


def _unsafe_attribute(name: str) -> bool:
    return name in _UNSAFE_DUNDERS or name in _UNSAFE_MEMBERS or name.startswith(_UNSAFE_PREFIXES)


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (*_attribute_path(node.value), node.attr)
    return ()


def host_replay_problem(source: str) -> str:
    """Why ``source`` must not run on the host, or "" when it only computes."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
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
                by_name = _SAFE_OS_MEMBERS - {"environ"}
                if any(alias.asname for alias in node.names) or "*" in members or not members <= by_name:
                    return f"imports unsafe member from os: {', '.join(sorted(members - by_name)) or 'alias'}"
            elif node.module == "os.path":
                members = {alias.name for alias in node.names}
                if any(alias.asname for alias in node.names) or "*" in members or not members <= _SAFE_OS_PATH:
                    return f"imports unsafe member from os.path: {', '.join(sorted(members - _SAFE_OS_PATH)) or 'alias'}"
            unsafe = [name for name in names if name.split(".")[0] not in safe]
            if unsafe or (isinstance(node, ast.ImportFrom) and node.level):
                return f"imports {', '.join(unsafe) or 'a relative module'}"
            if isinstance(node, ast.ImportFrom):
                hidden = [alias.name for alias in node.names
                          if alias.name == "*" or alias.name in _UNSAFE_NAMES or _unsafe_attribute(alias.name)]
                if hidden:
                    return f"imports {', '.join(hidden)} from {node.module}"
        elif isinstance(node, ast.Name) and node.id in _UNSAFE_NAMES:
            return f"uses {node.id}"
        elif isinstance(node, ast.Name) and node.id == "os" and not isinstance(parents.get(node), ast.Attribute):
            return "uses os as a value"
        elif isinstance(node, ast.Name) and node.id in _NAMED_ACCESS and not _literal_named_access(node, parents):
            return f"uses {node.id} without a literal attribute name"
        elif isinstance(node, ast.Attribute):
            if _attribute_path(node) == ("os", "environ") and not _in_read_position(node, parents):
                return "uses os.environ outside a read"
            path = _attribute_path(node)
            if path[:1] == ("os",):
                allowed = (path in {("os", "path"), ("os", "environ"), ("os", "getenv"),
                                    ("os", "environ", "get")}
                           or (len(path) == 3 and path[:2] == ("os", "path") and path[2] in _SAFE_OS_PATH))
                if not allowed:
                    return f"uses unsupported os member: {'.'.join(path[1:])}"
            if _unsafe_attribute(node.attr):
                return f"uses introspection attribute {node.attr}"
    return ""


def process_limits(timeout_seconds: int, memory_bytes: int = 512 * 1024 * 1024):
    """preexec_fn for subprocess: CPU time, address space and no child processes."""
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return apply
