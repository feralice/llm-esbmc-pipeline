"""Locate a hypothesis in the real source and collect what the harness must supply."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from .astutil import expression_nodes, find_function
from .compat import rewrite_compat
from .context import context_module
from .hypothesis import BugHypothesis
from .slicing import (
    CallShape,
    ExternalPlan,
    _merge,
    _shape,
    prune_class,
    reslice,
    stub_imports,
)


@dataclass(frozen=True)
class Param:
    name: str
    annotation: str | None
    keyword: bool = False


@dataclass(frozen=True)
class Grounded:
    hypothesis: BugHypothesis
    class_name: str | None
    method_name: str
    spans: tuple[tuple[int, int], ...]
    params: tuple[Param, ...]
    receiver_attrs: tuple[str, ...]
    module: str
    attr_annotations: dict[str, str] = field(default_factory=dict)
    is_static: bool = False
    # function | method | static | classmethod | constructor: how the driver reaches the target.
    entry: str = "function"
    function_start: int = 0
    transforms: tuple[str, ...] = ()
    externals: ExternalPlan = field(default_factory=ExternalPlan)
    # Members read (None) or called (their call shape) on each input, keyed "param" or "self.attr".
    object_members: dict[str, dict[str, CallShape | None]] = field(default_factory=dict)
    # Non-empty when the entry point has a shape the driver cannot call.
    unsupported: str = ""

    @property
    def stub_keys(self) -> tuple[str, ...]:
        return self.externals.stub_keys

    @property
    def has_receiver(self) -> bool:
        """A method called on a shell instance whose state the harness supplies."""
        return self.entry == "method"


@dataclass(frozen=True)
class GroundingFailure:
    reason: str
    # True when the hypothesis is real but its entry point has an unsupported shape.
    unsupported: bool = False


def _self_attribute(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr
    return None


def _class_of(tree: ast.Module, name: str) -> ast.ClassDef | None:
    return next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)


def _properties(cls: ast.ClassDef) -> set[str]:
    """Names the class binds with ``x = property(...)`` or ``@property``."""
    names = set()
    for node in cls.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "property"):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
            names.add(node.name)
    return names


def _with_setter(cls: ast.ClassDef) -> set[str]:
    names = set()
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names |= {d.value.id for d in node.decorator_list if isinstance(d, ast.Attribute)
                      and d.attr == "setter" and isinstance(d.value, ast.Name)}
        elif (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Name) and node.value.func.id == "property"
              and (len(node.value.args) > 1 or any(k.arg == "fset" for k in node.value.keywords))):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _replaced_properties(cls: ast.ClassDef, start: str) -> set[str]:
    """Properties a method reads become receiver attributes (ESBMC 8.5 has no ``property``).
    One the class assigns through a setter stays: dropping the setter would skip its conversion."""
    assigned = {_self_attribute(n) for n in ast.walk(cls)
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)}
    return _properties(cls) - {start} - (_with_setter(cls) & assigned)


def _reachable_methods(cls: ast.ClassDef, start: str, replaced: frozenset[str] | set[str] = frozenset()) -> set[str]:
    """``start``, methods it calls through self, and methods the class body names (``property(f)``),
    ignoring the ``replaced`` properties."""
    methods = {n.name: n for n in cls.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name not in replaced}
    body = [stmt for stmt in cls.body if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not (isinstance(stmt, ast.Assign) and _defined_by(stmt) & replaced)]
    named = {node.id for stmt in body for node in ast.walk(stmt)
             if isinstance(node, ast.Name) and node.id in methods}
    reached = {start} | named
    pending = list(reached)
    while pending:
        for node in ast.walk(methods[pending.pop()]):
            name = _self_attribute(node)
            if name in methods and name not in reached:
                reached.add(name)
                pending.append(name)
    return reached


def _defined_by(stmt: ast.Assign) -> set[str]:
    return {t.id for t in stmt.targets if isinstance(t, ast.Name)}


def _class_level_values(cls: ast.ClassDef) -> set[str]:
    """Names the class body binds to a value; they keep that value, never a nondet one."""
    names = set()
    for node in cls.body:
        if isinstance(node, ast.Assign):
            names |= {t.id for target in node.targets for t in ast.walk(target) if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _loaded_self_attrs(cls: ast.ClassDef, method: str) -> set[str]:
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        _self_attribute(node)
        for name in _reachable_methods(cls, method, _replaced_properties(cls, method))
        for node in ast.walk(methods[name])
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and _self_attribute(node)
    }


def _receiver_attrs(cls: ast.ClassDef, method: str) -> tuple[str, ...]:
    values = _class_level_values(cls) - _replaced_properties(cls, method)
    return tuple(sorted(_loaded_self_attrs(cls, method) - values))


def _inherited_reads(tree: ast.Module, cls: ast.ClassDef, method: str) -> set[str]:
    inherited = set()
    for base in cls.bases:
        base_cls = _class_of(tree, base.id) if isinstance(base, ast.Name) else None
        if base_cls is not None:
            inherited |= _class_level_values(base_cls)
    return _loaded_self_attrs(cls, method) & inherited


def _members(scopes: list[ast.AST], owner_of) -> dict[str, dict[str, CallShape | None]]:
    """``owner_of(node)`` names the input an attribute access hangs off, or None."""
    found: dict[str, dict[str, CallShape | None]] = {}
    for scope in scopes:
        parents = {id(child): node for node in ast.walk(scope) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(scope):
            owner = owner_of(node.value) if isinstance(node, ast.Attribute) else None
            if owner is None:
                continue
            members = found.setdefault(owner, {})
            parent = parents.get(id(node))
            call = _shape(parent) if isinstance(parent, ast.Call) and parent.func is node else None
            previous = members.get(node.attr)
            members[node.attr] = _merge(previous, call) if call is not None else previous
    return found


def _object_members(cls: ast.ClassDef | None, function: ast.FunctionDef, params: list[str],
                    attrs: tuple[str, ...]) -> dict[str, dict[str, CallShape | None]]:
    members = _members([function], lambda v: v.id if isinstance(v, ast.Name) and v.id in params else None)
    if cls is not None and attrs:
        methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        scopes = [methods[name] for name in _reachable_methods(cls, function.name)]
        members.update(_members(scopes, lambda v: f"self.{_self_attribute(v)}"
                                if _self_attribute(v) in attrs else None))
    return members


def _attr_annotations(cls: ast.ClassDef) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in ast.walk(cls):
        if not isinstance(node, ast.AnnAssign):
            continue
        if isinstance(node.target, ast.Name) and node in cls.body:
            found[node.target.id] = ast.unparse(node.annotation)
        elif _self_attribute(node.target):
            found[_self_attribute(node.target)] = ast.unparse(node.annotation)
    return found


_BINDING_DECORATORS = frozenset({"staticmethod", "classmethod"})


def _entry_kind(function: ast.FunctionDef, is_method: bool) -> str:
    decorators = {ast.unparse(d) for d in function.decorator_list}
    if not is_method:
        return "function"
    if "staticmethod" in decorators:
        return "static"
    if "classmethod" in decorators:
        return "classmethod"
    return "constructor" if function.name == "__init__" else "method"


def _entry_shape_problem(function: ast.FunctionDef, entry: str) -> str:
    if entry in {"method", "classmethod", "constructor"} and not (function.args.posonlyargs or function.args.args):
        return "method without a receiver argument"
    return ""


def _strip_decorators(source: str, function: ast.FunctionDef) -> tuple[str, tuple[str, ...]]:
    """Blank the target's wrapping decorators so the verified code is its own body.

    Lines are blanked, not deleted, so every line number stays the original's.
    """
    wrapping = [d for d in function.decorator_list if ast.unparse(d) not in _BINDING_DECORATORS]
    if not wrapping:
        return source, ()
    lines = source.splitlines(keepends=True)
    for decorator in wrapping:
        for index in range(decorator.lineno - 1, decorator.end_lineno):
            lines[index] = "\n"
    return "".join(lines), ("decorators_removed:" + ",".join(ast.unparse(d) for d in wrapping),)


def ground(h: BugHypothesis, source: str) -> Grounded | GroundingFailure:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return GroundingFailure(f"source does not parse: {exc.msg}")
    function = find_function(tree, h.function)
    if function is None:
        name = h.function.split(".")[-1]
        if any(isinstance(n, ast.AsyncFunctionDef) and n.name == name for n in ast.walk(tree)):
            return GroundingFailure("async entry point is not supported", unsupported=True)
        return GroundingFailure(f"function {h.function!r} not found (or ambiguous)")
    nodes = expression_nodes(function, h.suspect_expression)
    if not nodes:
        return GroundingFailure(f"suspect expression not found in {h.function}")
    if h.line:
        nodes = [min(nodes, key=lambda n: abs(n.lineno - h.line))]
    spans = tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes}))

    parts = h.function.split(".")
    # Modules may define a class twice (e.g. py2/py3 variants); use the one that holds the target.
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == parts[0]
                and function in n.body), None) if len(parts) == 2 else None
    entry = _entry_kind(function, cls is not None)
    is_static = entry == "static"
    positional = [*function.args.posonlyargs, *function.args.args]
    if entry in {"method", "classmethod", "constructor"}:
        positional = positional[1:]
    params = [Param(a.arg, ast.unparse(a.annotation) if a.annotation else None) for a in positional]
    params += [Param(a.arg, ast.unparse(a.annotation) if a.annotation else None, keyword=True)
               for a in function.args.kwonlyargs]
    problem = _entry_shape_problem(function, entry)
    if not problem and entry == "method":
        inherited = _inherited_reads(tree, cls, function.name)
        if inherited:
            problem = f"receiver reads inherited member(s): {', '.join(sorted(inherited))}"
    receiver_attrs = _receiver_attrs(cls, function.name) if entry == "method" else ()
    stripped, transforms = (source, ()) if problem else _strip_decorators(source, function)
    module, plan = context_module(stripped, h.function), ExternalPlan()
    if module and not problem:
        transforms = list(transforms)
        if cls is not None:
            # Only a method gets a shell; every other entry keeps the real constructor.
            replaced = _replaced_properties(cls, function.name) if entry == "method" else set()
            module, pruned = prune_class(module, cls.name, _reachable_methods(cls, function.name, replaced),
                                         drop_init=entry == "method", properties=replaced)
            transforms += pruned
            module = reslice(module, h.function)
        module, plan, stubbed = stub_imports(module)
        transforms += stubbed
        module, compat = rewrite_compat(module)
        transforms += compat
        problem = plan.problem
    return Grounded(
        hypothesis=h,
        class_name=cls.name if cls else None,
        method_name=function.name,
        spans=spans,
        params=tuple(params),
        receiver_attrs=receiver_attrs,
        module=module,
        attr_annotations=_attr_annotations(cls) if cls else {},
        is_static=is_static,
        entry=entry,
        function_start=function.lineno,
        transforms=tuple(transforms),
        externals=plan,
        object_members=_object_members(cls if receiver_attrs else None, function, [p.name for p in params],
                                       receiver_attrs),
        unsupported=problem,
    )
