"""Keep only what the target needs; swap unmodeled library imports for declared stubs."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from research_pipeline.scan.context import context_module

# Modules with ESBMC-Python 8.5 operational models (src/python-frontend/models); itertools, functools
# and json failed in the 2026-09-29 probes. numpy/torch models are partial, so their calls get stubs.
MODELED_MODULES = frozenset({
    "cmath", "collections", "dataclasses", "datetime", "decimal", "enum", "heapq", "math", "os",
    "queue", "random", "re", "string", "sys", "threading", "time", "typing", "unittest", "__future__",
})


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
    problem: str = ""

    @property
    def stub_keys(self) -> tuple[str, ...]:
        keys = [*self.calls, *self.constants]
        keys += [f"{ns}.{attr}" for ns, attrs in self.namespaces.items() for attr in attrs]
        return tuple(sorted(keys))


def _first_line(node: ast.stmt) -> int:
    return min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def prune_class(module: str, class_name: str, reachable: set[str], drop_init: bool = True) -> tuple[str, list[str]]:
    """Drop non-dunder methods the target cannot reach, and ``__init__`` when a shell replaces it."""
    tree = ast.parse(module)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    removed = [m for m in methods if m.name != "__init__" and m.name not in reachable and not _dunder(m.name)]
    init = [m for m in methods if m.name == "__init__"] if drop_init else []
    lines = module.splitlines()
    for node in sorted([*removed, *init], key=_first_line, reverse=True):
        del lines[_first_line(node) - 1:node.end_lineno]
    transforms = (["receiver_init_replaced" if init else "receiver_init_added"] if drop_init else [])
    if removed:
        transforms.append("unreachable_methods_removed:" + ",".join(sorted(m.name for m in removed)))
    return "\n".join(lines) + "\n", transforms


def _bound(alias: ast.alias) -> str:
    return (alias.asname or alias.name).split(".")[0]


def _unmodeled_imports(tree: ast.Module) -> list[tuple[ast.stmt, list[str]]]:
    found = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [_bound(a) for a in node.names if a.name.split(".")[0] not in MODELED_MODULES]
        elif isinstance(node, ast.ImportFrom):
            modeled = not node.level and (node.module or "").split(".")[0] in MODELED_MODULES
            names = [] if modeled else [_bound(a) for a in node.names]
        else:
            continue
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


def _in_class_position(node: ast.Name, parents: dict[int, ast.AST]) -> bool:
    """Used where only a type makes sense: base class, annotation, X[...], isinstance's second argument."""
    parent = parents.get(id(node))
    if isinstance(parent, ast.Tuple):
        node, parent = parent, parents.get(id(parent))
    if isinstance(parent, ast.ClassDef):
        return node in parent.bases
    if isinstance(parent, ast.Subscript):
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

    Only the external reference is renamed, in place on its own line; types keep the whole chain
    as one class name (``lib_a_B``). Returns the module and the new external names.
    """
    tree = ast.parse(module)
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    edits, new_names = [], set()
    for node in ast.walk(tree):
        parts = _dotted(node) if isinstance(node, ast.Attribute) else None
        outer = isinstance(parents.get(id(node)), ast.Attribute) and parents[id(node)].value is node
        if not parts or len(parts) < 3 or parts[0] not in external or outer or node.lineno != node.end_lineno:
            continue
        if _in_class_position(node, parents):
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


def stub_imports(module: str) -> tuple[str, ExternalPlan, list[str]]:
    """Remove unmodeled imports the slice still needs and plan a stub for each use."""
    tree = ast.parse(module)
    imports = _unmodeled_imports(tree)
    if not imports:
        return module, ExternalPlan(), []
    external = {name for _, names in imports for name in names}
    lines = module.splitlines()
    for node, _ in sorted(imports, key=lambda item: item[0].lineno, reverse=True):
        # Blank, not delete: the chain edits below use this tree's line numbers.
        lines[node.lineno - 1:node.end_lineno] = [""] * (node.end_lineno - node.lineno + 1)
    module = "\n".join(lines) + "\n"
    transforms = ["stubbed_imports:" + ",".join(sorted(external))]
    module, flattened = _flatten_chains(module, external)
    if flattened:
        transforms.append("external_chains_flattened:" + ",".join(sorted(flattened)))
    plan = _plan(ast.parse(module), external | flattened, set())
    return module, plan, transforms


def reslice(module: str, function: str) -> str:
    return context_module(module, function) or module
