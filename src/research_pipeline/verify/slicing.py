"""Keep only what the target needs; swap unmodeled library imports for declared stubs."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field

from .context import context_module

# Modules with ESBMC-Python 8.5 operational models (src/python-frontend/models); itertools, functools
# and json failed in the 2026-09-29 probes, sys ("Cannot open file: sys.json") in the 2026-09-30 one.
# Models are partial (re.sub): the members ESBMC refuses are stubbed one by one, see oracle.py.
# numpy/torch stay stubbed: the CPython replay runs isolated (-I -S) and could not import them.
MODELED_MODULES = frozenset({
    "cmath", "collections", "dataclasses", "datetime", "decimal", "enum", "heapq", "math", "os",
    "queue", "random", "re", "string", "threading", "time", "typing", "unittest", "__future__",
})


# Library members with a fixed model instead of a nondet stub, as class-body lines. ``exit`` ends
# the path (ESBMC 8.5 has no SystemExit); the values are the replay interpreter's, so both agree.
# The path cut lives at module level: inside ``class sys`` the name ``__ESBMC_assume`` is mangled.
END_PATH = ("def _esbmc_end_path() -> None:", "    __ESBMC_assume(False)", "", "")
KNOWN_MEMBERS = {
    "sys": {
        "exit": ("    @staticmethod", "    def exit(a0=None) -> None:", "        _esbmc_end_path()"),
        "maxsize": (f"    maxsize: int = {sys.maxsize}",),
        "version_info": ("    version_info: tuple[int, int, int] = ({}, {}, {})".format(*sys.version_info[:3]),),
        "platform": (f"    platform: str = {sys.platform!r}",),
    },
}


# Fixed models for members ESBMC refuses, as class bodies named ``{name}``. The driver runs one
# thread, where a reentrant lock always succeeds and thread-local storage is a plain object.
MEMBER_MODELS = {
    "threading.RLock": (
        "class {name}:",
        "    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:",
        "        return True",
        "",
        "    def release(self) -> None:",
        "        pass",
        "",
        "    def __enter__(self) -> bool:",
        "        return True",
        "",
        "    def __exit__(self, a: object = None, b: object = None, c: object = None) -> None:",
        "        pass",
    ),
    "threading.local": ("class {name}:", "    pass"),
}


@dataclass(frozen=True)
class CallShape:
    positional: int
    keywords: tuple[str, ...]


@dataclass
class ExternalPlan:
    calls: dict[str, CallShape] = field(default_factory=dict)
    # namespace -> attribute -> call shape, or None when the attribute is read as a value
    namespaces: dict[str, dict[str, CallShape | None]] = field(default_factory=dict)
    constants: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    # Classes the code also instantiates: they get an __init__ with the call's shape.
    constructors: dict[str, CallShape] = field(default_factory=dict)
    exceptions: set[str] = field(default_factory=set)
    # Name in the program -> ``module.member`` with a fixed model in MEMBER_MODELS.
    models: dict[str, str] = field(default_factory=dict)
    # Stub key -> number of names its result is unpacked into (``a, b = lib.f()``).
    unpacked: dict[str, int] = field(default_factory=dict)
    problem: str = ""

    @property
    def stub_keys(self) -> tuple[str, ...]:
        keys = [*self.calls, *self.constants]
        keys += [f"{ns}.{attr}" for ns, attrs in self.namespaces.items() for attr in attrs
                 if attr not in KNOWN_MEMBERS.get(ns, {})]
        return tuple(sorted(keys))


def _first_line(node: ast.stmt) -> int:
    return min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def prune_class(module: str, class_name: str, reachable: set[str], drop_init: bool = True,
                properties: frozenset[str] | set[str] = frozenset()) -> tuple[str, list[str]]:
    """Drop non-dunder methods the target cannot reach, ``__init__`` when a shell replaces it, and
    the ``properties`` the shell supplies as plain attributes."""
    tree = ast.parse(module)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    removed = [m for m in methods if m.name != "__init__" and m.name not in reachable and not _dunder(m.name)
               and m.name not in properties]
    # The shell builds the receiver's state, so the real construction (__new__ too) is not run.
    init = [m for m in methods if m.name == "__init__" or (m.name == "__new__" and m.name not in reachable)
            ] if drop_init else []
    props = [n for n in cls.body if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in properties)
             or (isinstance(n, ast.Assign) and {t.id for t in n.targets if isinstance(t, ast.Name)} & properties)]
    lines = module.splitlines()
    for node in sorted([*removed, *init, *props], key=_first_line, reverse=True):
        del lines[_first_line(node) - 1:node.end_lineno]
    transforms = (["receiver_init_replaced" if any(m.name == "__init__" for m in init) else "receiver_init_added"]
                  if drop_init else [])
    if any(m.name == "__new__" for m in init):
        transforms.append("receiver_new_removed")
    if removed:
        transforms.append("unreachable_methods_removed:" + ",".join(sorted(m.name for m in removed)))
    if props:
        transforms.append("properties_as_attributes:" + ",".join(sorted(properties)))
    return "\n".join(lines) + "\n", transforms


def _bound(alias: ast.alias) -> str:
    return (alias.asname or alias.name).split(".")[0]


def _top_level_imports(body: list[ast.stmt]) -> list[ast.stmt]:
    """Imports at top level, including inside top-level if/try blocks (py2/py3 fallbacks)."""
    found = []
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.append(node)
        elif isinstance(node, (ast.If, ast.Try)):
            blocks = [node.body, node.orelse]
            if isinstance(node, ast.Try):
                blocks += [h.body for h in node.handlers] + [node.finalbody]
            found += [n for block in blocks for n in _top_level_imports(block)]
    return found


def _modeled(module: str, refused: frozenset[str]) -> bool:
    return module in MODELED_MODULES and module not in refused


def import_bindings(tree: ast.Module) -> tuple[dict[str, str], dict[str, str]]:
    """Top-level imports: alias -> module (``import a.b as c`` gives c -> a.b, ``import a.b`` gives
    a -> a), and name -> ``module.member`` for ``from module import member``."""
    modules, members = {}, {}
    for node in _top_level_imports(tree.body):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[_bound(alias)] = alias.name if alias.asname else alias.name.split(".")[0]
        elif node.module and not node.level:
            for alias in node.names:
                members[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return modules, members


def _unmodeled_imports(tree: ast.Module, refused: frozenset[str]) -> list[tuple[ast.stmt, list[str]]]:
    found = []
    for node in _top_level_imports(tree.body):
        if isinstance(node, ast.Import):
            names = [_bound(a) for a in node.names if not _modeled(a.name.split(".")[0], refused)]
        else:
            modeled = not node.level and _modeled((node.module or "").split(".")[0], refused)
            names = [] if modeled else [_bound(a) for a in node.names]
        if names:
            found.append((node, names))
    return found


def _shape(call: ast.Call) -> CallShape | None:
    if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
        return None
    return CallShape(len(call.args), tuple(k.arg for k in call.keywords))


def _merge(old: CallShape | None, new: CallShape) -> CallShape:
    if old is None:
        return new
    return CallShape(max(old.positional, new.positional), tuple(sorted(set(old.keywords) | set(new.keywords))))


_EXCEPTION_SUFFIXES = ("Error", "Exception", "Warning")


def _exception_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Raise) and node.exc is not None:
            targets = [node.exc.func if isinstance(node.exc, ast.Call) else node.exc]
        elif isinstance(node, ast.ExceptHandler) and node.type is not None:
            targets = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def _in_class_position(node: ast.expr, parents: dict[int, ast.AST], subscript: bool = True) -> bool:
    """Used where only a type makes sense: base class, annotation, isinstance's second argument,
    and, when ``subscript``, X[...] (outside annotations that is also plain indexing)."""
    parent = parents.get(id(node))
    if isinstance(parent, ast.Tuple):
        node, parent = parent, parents.get(id(parent))
    if isinstance(parent, ast.ClassDef):
        return node in parent.bases
    if isinstance(parent, ast.Subscript) and subscript:
        return parent.value is node
    if isinstance(parent, ast.Call):
        return (isinstance(parent.func, ast.Name) and parent.func.id in {"isinstance", "issubclass"}
                and len(parent.args) == 2 and parent.args[1] is node)
    annotated = [getattr(parent, "annotation", None), getattr(parent, "returns", None)]
    return any(a is not None and any(n is node for n in ast.walk(a)) for a in annotated)


def _plan(tree: ast.Module, external: set[str], imports: set[int]) -> ExternalPlan:
    plan = ExternalPlan(exceptions=_exception_names(tree) & external)
    plan.exceptions |= {n for n in external if n.endswith(_EXCEPTION_SUFFIXES)}
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and node.id in external) or id(parents.get(id(node))) in imports:
            continue
        name, parent = node.id, parents.get(id(node))
        grand = parents.get(id(parent))
        if name in plan.exceptions:
            continue
        if isinstance(parent, (ast.FunctionDef, ast.ClassDef)) and node in parent.decorator_list:
            plan.problem = f"external name {name!r} is used as a decorator"
        elif isinstance(parent, ast.Call) and parent.func is node:
            shape = _shape(parent)
            if shape is None:
                plan.problem = f"external call {name}(...) uses *args/**kwargs"
            else:
                plan.calls[name] = _merge(plan.calls.get(name), shape)
        elif isinstance(parent, ast.Attribute) and parent.value is node:
            attrs = plan.namespaces.setdefault(name, {})
            if isinstance(grand, ast.Call) and grand.func is parent:
                shape = _shape(grand)
                if shape is None or (parent.attr in attrs and attrs[parent.attr] is None):
                    plan.problem = f"external call {name}.{parent.attr}(...) cannot be stubbed"
                else:
                    attrs[parent.attr] = _merge(attrs.get(parent.attr), shape)
            elif isinstance(grand, ast.Attribute):
                # ESBMC 8.5 resolves no two-level stub (nested class, alias or instance; probed 2026-09-29).
                plan.problem = f"external attribute chain {name}.{parent.attr}.{grand.attr}"
            elif attrs.get(parent.attr) is not None:
                plan.problem = f"external {name}.{parent.attr} is both called and read"
            else:
                attrs[parent.attr] = None
        elif _in_class_position(node, parents):
            plan.classes.add(name)
        else:
            plan.constants.add(name)
        if plan.problem:
            return plan
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple)
                and isinstance(node.value, ast.Call)):
            func = node.value.func
            key = (func.id if isinstance(func, ast.Name) and func.id in external
                   else f"{func.value.id}.{func.attr}" if isinstance(func, ast.Attribute)
                   and isinstance(func.value, ast.Name) and func.value.id in external else None)
            if key is not None:
                plan.unpacked[key] = len(node.targets[0].elts)
    # A class used as a namespace, value or constructor too renders as one class.
    for name in plan.classes & set(plan.calls):
        plan.constructors[name] = plan.calls.pop(name)
    plan.constants -= plan.classes
    return plan


def _dotted(node: ast.expr) -> list[str] | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return [node.id, *reversed(parts)] if isinstance(node, ast.Name) else None


def _flatten_chains(module: str, external: set[str]) -> tuple[str, set[str]]:
    """Rename ``lib.a.b`` references to one-level names ESBMC can resolve (``lib_a.b``).

    Only the external reference is renamed, in place on its own line; types, including two-level
    ones (``lib.T``), keep the whole chain as one class name (``lib_a_B``). Returns the module and
    the new external names.
    """
    tree = ast.parse(module)
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    chains = []
    for node in ast.walk(tree):
        parts = _dotted(node) if isinstance(node, ast.Attribute) else None
        outer = isinstance(parents.get(id(node)), ast.Attribute) and parents[id(node)].value is node
        if parts and parts[0] in external and not outer and node.lineno == node.end_lineno:
            chains.append((node, parts, _in_class_position(node, parents, subscript=len(parts) > 2)))
    # A chain used as a type anywhere is that class everywhere, so ``isinstance(lib.T(), lib.T)`` holds.
    types = {tuple(parts) for _, parts, as_type in chains if as_type}
    edits, new_names = [], set()
    for node, parts, as_type in chains:
        as_type = as_type or tuple(parts) in types
        # ESBMC resolves ``lib.f`` as a stub namespace, but a type must be one class name (``lib_T``).
        if len(parts) < (2 if as_type else 3):
            continue
        if as_type:
            target, text = node, "_".join(parts)
        else:
            target, text = node.value, "_".join(parts[:-1])
        new_names.add(text)
        edits.append((target.lineno, target.col_offset, target.end_col_offset, text))
    lines = module.splitlines()
    for lineno, start, end, text in sorted(edits, reverse=True):
        raw = lines[lineno - 1].encode("utf-8")  # ast offsets count UTF-8 bytes
        lines[lineno - 1] = (raw[:start] + text.encode("utf-8") + raw[end:]).decode("utf-8")
    return "\n".join(lines) + "\n", new_names


def _rename_refused_members(module: str, refused: frozenset[str]) -> tuple[str, dict[str, str]]:
    """``re.sub(x)`` becomes ``_esbmc_re_sub(x)`` when ESBMC refused ``re.sub``; the import stays, so the
    module's other members keep their model. Returns the module and new name -> ``module.member``."""
    tree = ast.parse(module)
    modules, members = import_bindings(tree)
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    # A from-imported name rebound anywhere else is not only the library member.
    rebound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
    rebound |= {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    names: dict[str, str] = {}

    def fresh(origin: str) -> str:
        for name, known in names.items():
            if known == origin:
                return name
        base = "_esbmc_" + origin.replace(".", "_")
        name, suffix = base, 1
        while name in taken:
            name, suffix = f"{base}_{suffix}", suffix + 1
        taken.add(name)
        names[name] = origin
        return name

    edits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules
                and f"{modules[node.value.id]}.{node.attr}" in refused and node.lineno == node.end_lineno):
            edits.append((node.lineno, node.col_offset, node.end_col_offset,
                          fresh(f"{modules[node.value.id]}.{node.attr}")))
        elif (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in members
              and members[node.id] in refused and node.id not in rebound):
            edits.append((node.lineno, node.col_offset, node.end_col_offset, fresh(members[node.id])))
    lines = module.splitlines()
    for lineno, start, end, text in sorted(edits, reverse=True):
        raw = lines[lineno - 1].encode("utf-8")  # ast offsets count UTF-8 bytes
        lines[lineno - 1] = (raw[:start] + text.encode("utf-8") + raw[end:]).decode("utf-8")
    return "\n".join(lines) + "\n", names


def stub_imports(module: str, refused: frozenset[str] = frozenset()) -> tuple[str, ExternalPlan, list[str]]:
    """Remove unmodeled imports the slice still needs and plan a stub for each use. ``refused`` names
    modules and ``module.member`` entries ESBMC did not convert, which are stubbed too."""
    module, members = _rename_refused_members(module, refused) if refused else (module, {})
    tree = ast.parse(module)
    imports = _unmodeled_imports(tree, refused)
    if not imports and not members:
        return module, ExternalPlan(), []
    external = {name for _, names in imports for name in names}
    lines = module.splitlines()
    for node, _ in sorted(imports, key=lambda item: item[0].lineno, reverse=True):
        # Replace, not delete: the chain edits below use this tree's line numbers. ``pass`` keeps
        # an enclosing block (``except ImportError: import x``) non-empty.
        head = lines[node.lineno - 1].encode("utf-8")[:node.col_offset]  # ast offsets count UTF-8 bytes
        tail = lines[node.end_lineno - 1].encode("utf-8")[node.end_col_offset:] if node.lineno == node.end_lineno else b""
        first = "" if not head and not tail.strip() else (head + b"pass" + tail).decode("utf-8")
        lines[node.lineno - 1:node.end_lineno] = [first] + [""] * (node.end_lineno - node.lineno)
    module = "\n".join(lines) + "\n"
    transforms = ["stubbed_imports:" + ",".join(sorted(external))] if external else []
    if members:
        transforms.append("esbmc_refused_members_stubbed:" + ",".join(sorted(members)))
    module, flattened = _flatten_chains(module, external)
    if flattened:
        transforms.append("external_chains_flattened:" + ",".join(sorted(flattened)))
    plan = _plan(ast.parse(module), external | flattened | set(members), set())
    for name, origin in members.items():
        if origin in MEMBER_MODELS and (name in plan.calls or name in plan.classes):
            plan.calls.pop(name, None)
            plan.constructors.pop(name, None)
            plan.classes.discard(name)
            plan.models[name] = origin
    if plan.models:
        transforms.append("member_models:" + ",".join(sorted(plan.models.values())))
    return module, plan, transforms


def reslice(module: str, function: str) -> str:
    return context_module(module, function) or module
