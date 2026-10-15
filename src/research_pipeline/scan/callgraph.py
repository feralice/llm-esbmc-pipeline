"""Repository call graph from the AST alone: every function, and who calls whom, in both directions.

Resolution is conservative: a call gets a callee only when the name can be bound without running
the code (same-module definitions, imports of repository modules, ``self``/``cls``/``super()``
inside a class, ``Class(...)`` to ``Class.__init__``). Everything else is recorded as external.
"""

from __future__ import annotations

import ast
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

SKIP_DIRS = frozenset({".git", "venv", ".venv", "build", "dist", "site-packages", "__pycache__",
                       "node_modules", ".tox", ".eggs", ".mypy_cache", ".pytest_cache"})
TEST_DIRS = frozenset({"test", "tests", "testing"})
MODULE_CALLER = "<module>"

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class FunctionNode:
    module: str
    qualname: str
    file: str
    start_line: int
    end_line: int
    class_qualname: str = ""
    nested: bool = False
    top_level: bool = True
    ambiguous: bool = False

    @property
    def key(self) -> str:
        return f"{self.module}:{self.qualname}"

    @property
    def name(self) -> str:
        return self.qualname.rsplit(".", 1)[-1]

    @property
    def verifiable(self) -> bool:
        """What the verify engine can locate: a module function or a method of a module class, defined once."""
        return self.top_level and not self.nested and not self.ambiguous and self.qualname.count(".") <= 1


@dataclass(frozen=True)
class CallSite:
    caller: str
    callee: str
    file: str
    line: int
    end_line: int
    expression: str


@dataclass
class _ClassInfo:
    module: str
    qualname: str
    bases: list[ast.expr]
    methods: set[str] = field(default_factory=set)


@dataclass
class _Module:
    name: str
    file: str
    tree: ast.Module
    is_package: bool
    lines: list[str]


@dataclass
class CallGraph:
    root: Path
    functions: dict[str, FunctionNode]
    calls: list[CallSite]
    modules: dict[str, str]
    skipped: list[dict[str, str]]
    sources: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._callers: dict[str, list[CallSite]] = defaultdict(list)
        self._callees: dict[str, list[CallSite]] = defaultdict(list)
        for site in self.calls:
            self._callees[site.caller].append(site)
            if site.callee:
                self._callers[site.callee].append(site)

    def callers(self, key: str) -> list[CallSite]:
        return list(self._callers.get(key, []))

    def callees(self, key: str) -> list[CallSite]:
        return [site for site in self._callees.get(key, []) if site.callee]

    def external_calls(self, key: str) -> list[CallSite]:
        return [site for site in self._callees.get(key, []) if not site.callee]

    def stats(self) -> dict:
        resolved = sum(1 for site in self.calls if site.callee)
        return {
            "modules": len(self.modules),
            "skipped_files": len(self.skipped),
            "functions": len(self.functions),
            "verifiable_functions": sum(1 for f in self.functions.values() if f.verifiable),
            "call_sites": len(self.calls),
            "resolved_calls": resolved,
            "external_calls": len(self.calls) - resolved,
            "functions_with_callers": sum(1 for key in self.functions if self._callers.get(key)),
        }

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "stats": self.stats(),
            "skipped": self.skipped,
            "functions": [{**vars(f), "key": f.key, "verifiable": f.verifiable,
                           "callers": len(self._callers.get(f.key, [])), "callees": len(self.callees(f.key))}
                          for f in self.functions.values()],
            "edges": [vars(site) for site in self.calls if site.callee],
        }


def python_files(root: Path, *, include_tests: bool = False) -> list[Path]:
    found = []
    for path in sorted(Path(root).rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in parts[:-1]):
            continue
        if not include_tests and _is_test_path(parts):
            continue
        found.append(path)
    return found


def _is_test_path(parts: tuple[str, ...]) -> bool:
    name = parts[-1]
    return (any(part in TEST_DIRS for part in parts[:-1]) or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


def _package_prefix(root: Path) -> list[str]:
    """A root that is itself a package imports itself by name (``from _pytest.x import y``)."""
    prefix, directory = [], root
    while (directory / "__init__.py").exists() and directory.parent != directory:
        prefix.insert(0, directory.name)
        directory = directory.parent
    return prefix


def _module_name(relative: Path, prefix: list[str]) -> tuple[str, bool]:
    parts = [*prefix, *relative.with_suffix("").parts]
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts) or "__init__", is_package


def build_callgraph(root: str | Path, *, include_tests: bool = False) -> CallGraph:
    root = Path(root).resolve()
    modules: dict[str, _Module] = {}
    skipped: list[dict[str, str]] = []
    prefix = _package_prefix(root)
    for path in python_files(root, include_tests=include_tests):
        relative = path.relative_to(root)
        try:
            data = path.read_bytes()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(data, filename=str(relative))
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError, OSError) as exc:
            skipped.append({"file": relative.as_posix(), "error": f"{type(exc).__name__}: {exc}"})
            continue
        name, is_package = _module_name(relative, prefix)
        lines = data.decode("utf-8", errors="replace").splitlines()
        modules[name] = _Module(name, relative.as_posix(), tree, is_package, lines)
    return _Builder(root, modules, skipped).build()


class _Builder:
    def __init__(self, root: Path, modules: dict[str, _Module], skipped: list[dict[str, str]]):
        self.root = root
        self.modules = modules
        self.skipped = skipped
        self.functions: dict[str, FunctionNode] = {}
        self.ast_of: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.classes: dict[str, _ClassInfo] = {}
        self._bound: dict[str, dict[str, tuple[str, str]]] = {}

    def build(self) -> CallGraph:
        for module in self.modules.values():
            self._index(module, module.tree, [], "", nested=False, direct=True)
        calls = []
        for module in self.modules.values():
            calls.extend(self._module_calls(module))
            for key, node in self.ast_of.items():
                if self.functions[key].module == module.name:
                    calls.extend(self._function_calls(module, self.functions[key], node))
        calls.sort(key=lambda s: (s.file, s.line, s.caller, s.expression))
        return CallGraph(self.root, self.functions, calls, {m.name: m.file for m in self.modules.values()},
                         self.skipped, {m.file: m.lines for m in self.modules.values()})

    def _index(self, module: _Module, node: ast.AST, scope: list[str], owner: str, *, nested: bool,
               direct: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _FUNCTION_NODES):
                qualname = ".".join([*scope, child.name])
                function = FunctionNode(module.name, qualname, module.file, child.lineno,
                                        child.end_lineno or child.lineno, owner, nested, direct)
                if function.key in self.functions:
                    self.functions[function.key] = replace(self.functions[function.key], ambiguous=True)
                else:
                    self.functions[function.key] = function
                    self.ast_of[function.key] = child
                if owner:
                    self.classes[f"{module.name}:{owner}"].methods.add(child.name)
                self._index(module, child, [*scope, child.name], "", nested=True, direct=False)
            elif isinstance(child, ast.ClassDef):
                qualname = ".".join([*scope, child.name])
                self.classes.setdefault(f"{module.name}:{qualname}", _ClassInfo(module.name, qualname, child.bases))
                self._index(module, child, [*scope, child.name], qualname, nested=nested, direct=direct)
            elif isinstance(child, ast.stmt):
                self._index(module, child, scope, owner, nested=nested, direct=False)

    def _bindings(self, module_name: str) -> dict[str, tuple[str, str]]:
        """Module-level names: ("function"|"class", key) or ("module", dotted name), imports included.
        Imports inside functions count too: lazy imports are how real code breaks import cycles."""
        if module_name in self._bound or module_name not in self.modules:
            return self._bound.get(module_name, {})
        module = self.modules[module_name]
        out: dict[str, tuple[str, str]] = {}
        self._bound[module_name] = out  # an import cycle sees the partial table instead of recursing
        for child in module.tree.body:
            if isinstance(child, _FUNCTION_NODES):
                out[child.name] = ("function", f"{module.name}:{child.name}")
            elif isinstance(child, ast.ClassDef):
                out[child.name] = ("class", f"{module.name}:{child.name}")
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    target = self._find_module(alias.name if alias.asname else bound)
                    if target:
                        out.setdefault(bound, ("module", target))
            elif isinstance(node, ast.ImportFrom):
                base = self._import_base(module, node)
                if base is None:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = self._member(base, alias.name)
                    if bound:
                        out.setdefault(alias.asname or alias.name, bound)
        return out

    def _import_base(self, module: _Module, node: ast.ImportFrom) -> str | None:
        if not node.level:
            return self._find_module(node.module or "")
        package = module.name.split(".") if module.is_package else module.name.split(".")[:-1]
        if node.level - 1 > len(package):
            return None
        package = package[:len(package) - (node.level - 1)]
        dotted = ".".join([*package, *([node.module] if node.module else [])])
        return dotted

    def _is_module(self, dotted: str) -> bool:
        """A module file, or a namespace package (a directory of modules without ``__init__.py``)."""
        return dotted in self.modules or any(name.startswith(dotted + ".") for name in self.modules)

    def _find_module(self, dotted: str) -> str | None:
        """Exact module name, else the one repository module whose name ends with it (``src/`` layouts)."""
        if not dotted:
            return None
        if self._is_module(dotted):
            return dotted
        matches = [name for name in self.modules if name.endswith("." + dotted)]
        return matches[0] if len(matches) == 1 else None

    def _member(self, module_name: str, name: str) -> tuple[str, str] | None:
        """``name`` as seen from ``module_name``: a submodule, a definition, or a re-export."""
        submodule = f"{module_name}.{name}" if module_name else name
        if self._is_module(submodule):
            return ("module", submodule)
        return self._bindings(module_name).get(name)

    def _module_calls(self, module: _Module) -> list[CallSite]:
        return [self._site(module, f"{module.name}:{MODULE_CALLER}", call, self._resolve(module, None, set(), call))
                for call in _own_calls(module.tree.body)]

    def _function_calls(self, module: _Module, function: FunctionNode,
                        node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CallSite]:
        local = _local_names(node)
        return [self._site(module, function.key, call, self._resolve(module, function, local, call))
                for call in _own_calls(node.body)]

    def _site(self, module: _Module, caller: str, call: ast.Call, callee: str) -> CallSite:
        return CallSite(caller, callee, module.file, call.lineno, call.end_lineno or call.lineno,
                        _shorten(ast.unparse(call.func)))

    def _resolve(self, module: _Module, function: FunctionNode | None, local: set[str], call: ast.Call) -> str:
        func = call.func
        if isinstance(func, ast.Attribute):
            return self._resolve_attribute(module, function, local, func)
        if not isinstance(func, ast.Name):
            return ""
        if function is not None and f"{function.key}.{func.id}" in self.functions:
            return f"{function.key}.{func.id}"
        if func.id in local:
            return ""
        return self._callable(self._bindings(module.name).get(func.id))

    def _resolve_attribute(self, module: _Module, function: FunctionNode | None, local: set[str],
                           func: ast.Attribute) -> str:
        receiver = func.value
        owner = self._enclosing_class(function)
        if owner and isinstance(receiver, ast.Name) and receiver.id in self._receiver_names(function):
            return self._method(owner, func.attr)
        if (owner and isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name)
                and receiver.func.id == "super"):
            return next((m for base in self._bases(owner) if (m := self._method(base, func.attr))), "")
        dotted = _dotted(receiver)
        if dotted is None or dotted.split(".", 1)[0] in local:
            return ""
        target = self._dotted_target(module, dotted)
        if target is None:
            return ""
        kind, key = target
        if kind == "class":
            return self._method(key, func.attr)
        if kind == "module":
            return self._callable(self._member(key, func.attr))
        return ""

    def _dotted_target(self, module: _Module, dotted: str) -> tuple[str, str] | None:
        head, *rest = dotted.split(".")
        target = self._bindings(module.name).get(head)
        for part in rest:
            if target is None or target[0] != "module":
                return None
            target = self._member(target[1], part)
        return target

    def _callable(self, bound: tuple[str, str] | None) -> str:
        if bound is None:
            return ""
        kind, key = bound
        if kind == "function":
            return key if key in self.functions else ""
        if kind == "class":
            return self._method(key, "__init__")
        return ""

    def _receiver_names(self, function: FunctionNode) -> set[str]:
        """The receiver is the first parameter, whatever its name; a staticmethod has none."""
        node = self.ast_of.get(function.key)
        if node is None or any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in node.decorator_list):
            return set()
        args = [*node.args.posonlyargs, *node.args.args]
        return {args[0].arg} if args else set()

    def _enclosing_class(self, function: FunctionNode | None) -> str:
        if function is None or not function.class_qualname:
            return ""
        return f"{function.module}:{function.class_qualname}"

    def _method(self, class_key: str, name: str) -> str:
        for cls in self._mro(class_key):
            info = self.classes[cls]
            if name in info.methods:
                key = f"{info.module}:{info.qualname}.{name}"
                return key if key in self.functions else ""
        return ""

    def _mro(self, class_key: str) -> list[str]:
        order, pending = [], [class_key]
        while pending:
            current = pending.pop(0)
            if current in order or current not in self.classes:
                continue
            order.append(current)
            pending.extend(self._bases(current))
        return order

    def _bases(self, class_key: str) -> list[str]:
        info = self.classes.get(class_key)
        if info is None:
            return []
        module = self.modules[info.module]
        out = []
        for base in info.bases:
            dotted = _dotted(base)
            if dotted is None:
                continue
            local = f"{info.module}:{dotted}"
            if local in self.classes:
                out.append(local)
                continue
            target = self._dotted_target(module, dotted)
            if target and target[0] == "class":
                out.append(target[1])
        return out


def _own_calls(body: list[ast.stmt]) -> list[ast.Call]:
    """Calls executed by this body, not those inside nested functions or classes (they are nodes of their own)."""
    found, pending = [], list(body)
    while pending:
        node = pending.pop()
        if isinstance(node, (*_FUNCTION_NODES, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            found.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return sorted(found, key=lambda c: (c.lineno, c.col_offset))


def _local_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Parameters and assigned names: a call through them is not the module-level definition."""
    args = node.args
    names = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    names |= {a.arg for a in (args.vararg, args.kwarg) if a is not None}
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
    return names


def _dotted(node: ast.expr) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def _shorten(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."
