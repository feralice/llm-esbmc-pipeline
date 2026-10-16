"""Locate a hypothesis in the real source and collect what the harness must supply."""

from __future__ import annotations

import ast
import copy
import dataclasses
import symtable
from dataclasses import dataclass, field

from .astutil import expression_nodes, find_function
from .compat import remove_unused
from .context import context_module
from .hypothesis import BugHypothesis
from .rules import ALL_RULES, PROPERTIES_AS_ATTRIBUTES
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
    # Input ("param", "self.attr" or "input.member") -> number of names the target unpacks it into.
    unpacked_inputs: dict[str, int] = field(default_factory=dict)
    # Non-empty when the entry point has a shape the driver cannot call.
    unsupported: str = ""
    # The module also constructs the class with arguments: its real __init__ stays and the shell
    # becomes a subclass.
    receiver_subclass: bool = False
    # Receiver attributes only ever called: stub methods in the shell, typed by their return value.
    called_attrs: dict[str, CallShape] = field(default_factory=dict)
    # (input, helper, helper parameter) for each helper an input is passed on to.
    forwarded: tuple[tuple[str, str, str], ...] = ()

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


def _constructed_with_args(module: str, class_name: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == class_name
               and (n.args or n.keywords) for n in ast.walk(ast.parse(module)))


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


def _replaced(cls: ast.ClassDef, start: str, replace_properties: bool) -> set[str]:
    return _replaced_properties(cls, start) if replace_properties else set()


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


def _loaded_self_attrs(cls: ast.ClassDef, method: str, replace_properties: bool = True) -> set[str]:
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        _self_attribute(node)
        for name in _reachable_methods(cls, method, _replaced(cls, method, replace_properties))
        for node in ast.walk(methods[name])
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and _self_attribute(node)
    }


def _receiver_attrs(cls: ast.ClassDef, method: str, replace_properties: bool = True) -> tuple[str, ...]:
    values = _class_level_values(cls) - _replaced(cls, method, replace_properties)
    return tuple(sorted(_loaded_self_attrs(cls, method, replace_properties) - values))


def _called_attrs(cls: ast.ClassDef, method: str, attrs: tuple[str, ...],
                  replace_properties: bool = True) -> dict[str, CallShape]:
    """Receiver attributes the reachable methods only call (``self.write(x)``): methods the class
    inherits from a library base, so the shell gives them a stub method, not a field."""
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    calls: dict[str, CallShape] = {}
    values: set[str] = set()
    for name in _reachable_methods(cls, method, _replaced(cls, method, replace_properties)):
        parents = {id(c): n for n in ast.walk(methods[name]) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(methods[name]):
            attr = _self_attribute(node)
            if attr not in attrs:
                continue
            parent = parents.get(id(node))
            shape = _shape(parent) if isinstance(parent, ast.Call) and parent.func is node else None
            if shape is None:
                values.add(attr)
            else:
                calls[attr] = _merge(calls.get(attr), shape)
    return {attr: shape for attr, shape in calls.items() if attr not in values}


def _inherited_reads(tree: ast.Module, cls: ast.ClassDef, method: str, replace_properties: bool = True) -> set[str]:
    inherited = set()
    for base in cls.bases:
        base_cls = _class_of(tree, base.id) if isinstance(base, ast.Name) else None
        if base_cls is not None:
            inherited |= _class_level_values(base_cls)
    return (_loaded_self_attrs(cls, method, replace_properties) & inherited) - _class_level_values(cls)


def _inline_inherited(source: str, tree: ast.Module, cls: ast.ClassDef, names: set[str]) -> str | None:
    """Copy the base-class definitions of ``names`` (and of the base members they read in turn)
    to the end of ``cls``, re-indented: the receiver then owns them and the base stays as it is.
    Inserted after the class, so the target's line numbers do not move."""
    lines = source.splitlines()
    copied: list[str] = []
    pending, seen = sorted(names), set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for base in (b for b in cls.bases if isinstance(b, ast.Name)):
            base_cls = _class_of(tree, base.id)
            nodes = [n for n in base_cls.body if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
                     or (isinstance(n, ast.Assign) and name in _defined_by(n))] if base_cls else []
            if not nodes:
                continue
            shift = cls.body[0].col_offset - nodes[0].col_offset
            for node in nodes:
                first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
                text = lines[first - 1:node.end_lineno]
                copied += ["", *((" " * shift + line) if shift >= 0 else line[-shift:] for line in text)]
                pending += [a for a in (_self_attribute(n) for n in ast.walk(node)) if a]
            break
    if not copied:
        return None
    return "\n".join([*lines[:cls.end_lineno], *copied, *lines[cls.end_lineno:]]) + "\n"


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


def _forwarded(function: ast.FunctionDef, params: set[str], methods: dict[str, ast.FunctionDef],
               functions: dict[str, ast.FunctionDef]) -> list[tuple[str, ast.FunctionDef, str]]:
    """(caller input, callee, callee parameter) for each input passed on to a method or module function."""
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = _self_attribute(node.func)
        callee = methods.get(name) if name else (
            functions.get(node.func.id) if isinstance(node.func, ast.Name) else None)
        if callee is None:
            continue
        names = [a.arg for a in [*callee.args.posonlyargs, *callee.args.args]][1 if name else 0:]
        bound = [*zip(names, node.args), *((k.arg, k.value) for k in node.keywords if k.arg)]
        found += [(value.id, callee, param) for param, value in bound
                  if isinstance(value, ast.Name) and value.id in params]
    return found


def _forwarding_chain(cls: ast.ClassDef | None, function: ast.FunctionDef, params: list[str],
                      functions: dict[str, ast.FunctionDef]) -> list[tuple[str, ast.FunctionDef, str]]:
    """(input, callee, callee parameter) for every helper an input reaches, following calls to a fixpoint."""
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))} if cls else {}
    chain, pending, seen = [], [(p, function, p) for p in params], set()
    while pending:
        owner, scope, name = pending.pop()
        for _, callee, param in _forwarded(scope, {name}, methods, functions):
            if (owner, callee.name, param) not in seen:
                seen.add((owner, callee.name, param))
                chain.append((owner, callee, param))
                pending.append((owner, callee, param))
    return chain


_MAX_CHAIN = 3


def _rooted(node: ast.AST, is_root) -> str | None:
    """``node`` as text when it is an input (``is_root``) or a chain of up to _MAX_CHAIN attributes on
    one: ``self.a.b`` owns the members read on it, like ``self.a`` does."""
    current, depth = node, 0
    while not is_root(current):
        if not isinstance(current, ast.Attribute) or depth == _MAX_CHAIN:
            return None
        current, depth = current.value, depth + 1
    return ast.unparse(node)


def _object_members(cls: ast.ClassDef | None, function: ast.FunctionDef, params: list[str],
                    attrs: tuple[str, ...], chain: list[tuple[str, ast.FunctionDef, str]],
                    ) -> dict[str, dict[str, CallShape | None]]:
    members = _members([function], lambda v: _rooted(v, lambda n: isinstance(n, ast.Name) and n.id in params))
    # Members the helpers an input is passed to use on it belong to the same object.
    for owner, callee, param in chain:
        used = _members([callee], lambda v, p=param: p if isinstance(v, ast.Name) and v.id == p else None)
        for attr, shape in used.get(param, {}).items():
            previous = members.setdefault(owner, {}).get(attr)
            members[owner][attr] = _merge(previous, shape) if shape is not None else previous
    if cls is not None and attrs:
        methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        scopes = [methods[name] for name in _reachable_methods(cls, function.name)]
        members.update(_members(scopes, lambda v: _rooted(v, lambda n: _self_attribute(n) in attrs)))
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


def _unpacked_inputs(function: ast.FunctionDef, params: set[str], attrs: set[str]) -> dict[str, int]:
    """``a, b = x`` where ``x`` is an input or a field of one: its type must be a tuple of that size.
    Inputs the function rebinds, and inputs unpacked with two different sizes, get no constraint."""
    nodes, pending = [], list(function.body)
    while pending:
        node = pending.pop()
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            nodes.append(node)
            pending.extend(ast.iter_child_nodes(node))
    rebound = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
    rebound |= {f"self.{n.attr}" for n in nodes if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name) and n.value.id == "self"}
    inputs = (params | {f"self.{a}" for a in attrs}) - rebound
    found: dict[str, int] = {}
    conflicting: set[str] = set()
    for node in sorted((n for n in nodes if isinstance(n, ast.Assign)), key=lambda n: (n.lineno, n.col_offset)):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple)
                and not any(isinstance(e, ast.Starred) for e in node.targets[0].elts)
                and isinstance(node.value, (ast.Name, ast.Attribute))):
            text = ast.unparse(node.value)
            if text in inputs or text.rsplit(".", 1)[0] in inputs:
                count = len(node.targets[0].elts)
                if found.get(text, count) != count:
                    conflicting.add(text)
                found[text] = count
    return {key: count for key, count in found.items() if key not in conflicting}


def _nested_chain(tree: ast.Module, qualified: str) -> list[ast.AST] | None:
    """``outer.Inner.method`` or ``outer.inner``: the nodes along the name, when one of them sits
    inside a function (the LLM located it, but it only exists once outer runs)."""
    chain, scope = [], tree.body
    for name in qualified.split("."):
        found = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == name]
        if len(found) != 1:
            return None
        chain.append(found[0])
        scope = found[0].body
    if not isinstance(chain[-1], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    inside = any(not isinstance(n, ast.ClassDef) for n in chain[:-1])
    return chain if inside else None


def _free_names(table: symtable.SymbolTable) -> set[str]:
    """Names the scope and those nested in it take from an enclosing function."""
    free = {s.get_name() for s in table.get_symbols() if s.is_free()}
    inner = set().union(*(_free_names(child) for child in table.get_children()))
    if table.get_type() == "function":
        inner -= set(table.get_locals())
    return (free | inner) - {"__class__"}


def _table_of(table: symtable.SymbolTable, node: ast.AST) -> symtable.SymbolTable | None:
    for child in table.get_children():
        if child.get_name() == node.name and child.get_lineno() == node.lineno:
            return child
        found = _table_of(child, node)
        if found is not None:
            return found
    return None


def _hoist_nested(tree: ast.Module, source: str, h: BugHypothesis) -> tuple[str, BugHypothesis] | None:
    """Copy the outermost definition that lives inside a function to the end of the module, the
    names it takes from the enclosing function becoming keyword-only parameters; the body stays
    verbatim. A class taking names from its function, or code using ``nonlocal``, is left alone."""
    chain = _nested_chain(tree, h.function)
    if chain is None:
        return None
    index = next(i for i, n in enumerate(chain) if i and not isinstance(chain[i - 1], ast.ClassDef))
    node = chain[index]
    if any(isinstance(n, ast.Nonlocal) for n in ast.walk(node)) or any(
            getattr(n, "name", None) == node.name for n in tree.body):
        return None
    table = _table_of(symtable.symtable(source, "module", "exec"), node)
    # A recursive function names itself through the enclosing scope; hoisted, the name is global.
    free = sorted(_free_names(table) - {node.name}) if table is not None else None
    if free is None or (free and not isinstance(node, ast.FunctionDef)):
        return None
    lines = source.splitlines()
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    text = [line[node.col_offset:] for line in lines[first - 1:node.end_lineno]]
    if free:
        header = copy.copy(node)
        header.args = copy.copy(node.args)
        header.args.kwonlyargs = [*node.args.kwonlyargs, *(ast.arg(name) for name in free)]
        header.args.kw_defaults = [*node.args.kw_defaults, *([None] * len(free))]
        header.body, header.decorator_list = [ast.Pass()], []
        signature = ast.unparse(header).splitlines()[0]
        head = node.body[0].lineno - node.lineno
        if head < 1:
            return None
        text[node.lineno - first:node.lineno - first + head] = [signature, *([""] * (head - 1))]
    start = len(lines) + 3
    hoisted = "\n".join([*lines, "", "", *text]) + "\n"
    line = h.line - first + start if first <= h.line <= node.end_lineno else 0
    name = ".".join(n.name for n in chain[index:])
    return hoisted, dataclasses.replace(h, function=name, line=line)


def ground(h: BugHypothesis, source: str, refused: frozenset[str] = frozenset(),
           rules: frozenset[str] = ALL_RULES) -> Grounded | GroundingFailure:
    properties = PROPERTIES_AS_ATTRIBUTES in rules
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return GroundingFailure(f"source does not parse: {exc.msg}")
    function = find_function(tree, h.function)
    if function is None:
        name = h.function.split(".")[-1]
        if any(isinstance(n, ast.AsyncFunctionDef) and n.name == name for n in ast.walk(tree)):
            return GroundingFailure("async entry point is not supported", unsupported=True)
        hoisted = _hoist_nested(tree, source, h)
        if hoisted is not None:
            grounded = ground(hoisted[1], hoisted[0], refused, rules)
            if isinstance(grounded, Grounded):
                return dataclasses.replace(grounded, transforms=(f"nested_entry_hoisted:{h.function}",
                                                                 *grounded.transforms))
            return grounded
        if _nested_chain(tree, h.function):
            return GroundingFailure("entry point is nested inside a function; the harness cannot call it",
                                    unsupported=True)
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
        inherited = _inherited_reads(tree, cls, function.name, properties)
        inlined = _inline_inherited(source, tree, cls, inherited) if inherited else None
        if inlined is not None:
            grounded = ground(h, inlined, refused, rules)
            if isinstance(grounded, Grounded):
                return dataclasses.replace(grounded, transforms=(
                    "inherited_members_inlined:" + ",".join(sorted(inherited)), *grounded.transforms))
            return grounded
        if inherited:
            problem = f"receiver reads inherited member(s): {', '.join(sorted(inherited))}"
    receiver_attrs = _receiver_attrs(cls, function.name, properties) if entry == "method" else ()
    stripped, transforms = (source, ()) if problem else _strip_decorators(source, function)
    module, plan = context_module(stripped, h.function), ExternalPlan()
    subclass = False
    if module and not problem:
        transforms = list(transforms)
        if cls is not None:
            # Only a method gets a shell; every other entry keeps the real constructor.
            replaced = _replaced(cls, function.name, properties) if entry == "method" else set()
            subclass = entry == "method" and _constructed_with_args(module, cls.name)
            if subclass and any(isinstance(n, ast.FunctionDef) and n.name == "__new__" for n in cls.body):
                problem = "the target builds its own class, which defines __new__; the receiver cannot subclass it"
            reachable = _reachable_methods(cls, function.name, replaced)
            if subclass and "__init__" in {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}:
                reachable |= _reachable_methods(cls, "__init__", replaced)
            module, pruned = prune_class(module, cls.name, reachable,
                                         drop_init=entry == "method" and not subclass, properties=replaced)
            transforms += [*pruned, "receiver_subclass"] if subclass else pruned
            module = reslice(module, h.function)
        # Before planning stubs: an unreached method's decorators would otherwise need stubs too.
        module, unused = remove_unused(module, h.function, display=False)
        transforms += unused
        module, plan, stubbed = stub_imports(module, refused)
        transforms += stubbed
        problem = problem or plan.problem
    chain = _forwarding_chain(cls, function, [p.name for p in params],
                              {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)})
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
        object_members=_object_members(cls, function, [p.name for p in params], receiver_attrs, chain),
        forwarded=tuple((owner, callee.name, param) for owner, callee, param in chain),
        unpacked_inputs=_unpacked_inputs(function, {p.name for p in params}, set(receiver_attrs)),
        unsupported=problem,
        receiver_subclass=subclass,
        called_attrs=_called_attrs(cls, function.name, receiver_attrs, properties) if receiver_attrs else {},
    )
