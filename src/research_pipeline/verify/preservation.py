"""Whether a harness kept the target's code: its body must equal the original's once what CPython never
runs is dropped and the renames the pipeline makes by construction are mapped back. Anything else (a
statement removed or reordered, a condition, operator, constant or loop bound changed, a raise or assert
removed, a call replaced by a value, a guard or ``__ESBMC_assume`` added) still counts as a change."""

from __future__ import annotations

import ast
import copy
import re

from .astutil import entry_of, find_function, locate
from .compat import rewrite_compat
from .slicing import COMPAT_RENAMED

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPE_TRICKS = frozenset({"locals", "vars", "eval", "exec", "globals", "dir"})
_SPREAD = re.compile(r"_(star|kw)\d+")


def _is_docstring(statement: ast.stmt) -> bool:
    return (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str))


def _stored(nodes: list[ast.AST]) -> set[str]:
    return {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}


def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    return (body[1:] or [ast.Pass()]) if body and _is_docstring(body[0]) else body


class Cosmetic(ast.NodeTransformer):
    """Drops what never runs: annotations, docstrings and a ``pass`` beside other statements. A class body
    keeps its annotations (dataclasses read them) and a decorated function its own (a decorator may too);
    a bare ``x: T`` goes only where ``x`` is bound anyway, since it alone would make ``x`` local."""

    def __init__(self) -> None:
        self.bound: list[set[str] | None] = []  # per enclosing scope; None for a class body

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        if not node.decorator_list:
            node.returns = None
            for arg in ast.walk(node.args):
                if isinstance(arg, ast.arg):
                    arg.annotation = None
        node.body = _without_docstring(node.body)
        self.bound.append(set().union(*_locals(node)))
        self.generic_visit(node)
        self.bound.pop()
        return node

    visit_FunctionDef = visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.body = _without_docstring(node.body)
        self.bound.append(None)
        self.generic_visit(node)
        self.bound.pop()
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        scope = self.bound[-1] if self.bound else set()  # a statement alone: as in a function
        if scope is None:
            return self.generic_visit(node)
        if node.value is not None:
            return self.visit(ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node))
        if isinstance(node.target, ast.Name) and node.target.id in scope:
            return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> ast.AST:
        super().generic_visit(node)
        if isinstance(node, ast.stmt):
            for name in ("body", "orelse", "finalbody"):
                block = getattr(node, name, None)
                if isinstance(block, list) and len(block) > 1:
                    setattr(node, name, [s for s in block if not isinstance(s, ast.Pass)] or block[:1])
        return node


def _texts(function: ast.AST) -> set[str]:
    return {ast.unparse(n) for n in ast.walk(function) if isinstance(n, (ast.Name, ast.Attribute))}


def _bound_at_module_level(tree: ast.Module) -> set[str]:
    names, pending = set(), list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
            continue
        names |= _stored(list(ast.walk(node)))
        for field in ("body", "orelse", "finalbody", "handlers"):
            pending += [n for n in getattr(node, field, []) if isinstance(n, ast.AST)]
    return names


class _AsStubs(ast.NodeTransformer):
    """The slicer's stub renames, applied to the original where the checked copy uses the new name:
    ``re.sub`` -> ``_esbmc_re_sub`` (refused member), ``email.utils`` -> ``email_utils`` (flattened chain),
    ``lib.f(a).x`` -> ``lib.f__x(a)`` (result member) and ``compat_str`` -> ``str`` (``COMPAT_RENAMED``)."""

    def __init__(self, original: ast.AST, checked: ast.AST, compat_builtins: set[str]) -> None:
        names = {n.id for n in ast.walk(original) if isinstance(n, ast.Name)}
        self.stubs = {n.id for n in ast.walk(checked) if isinstance(n, ast.Name)} - names
        self.new = _texts(checked) - _texts(original)
        self.compat = {name for name in compat_builtins if name not in _texts(checked)}

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.compat and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Name(COMPAT_RENAMED[node.id], node.ctx), node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        call = node.value
        if isinstance(call, ast.Call) and isinstance(node.ctx, ast.Load):
            name = f"{ast.unparse(call.func)}__{node.attr}"
            flat = name.replace(".", "_")
            if name in self.new or flat in self.stubs or "_esbmc_" + flat in self.stubs:
                func = ast.parse(name, mode="eval").body
                return self.visit(ast.Call(func=func, args=call.args, keywords=call.keywords))
        flat = ast.unparse(node).replace(".", "_")
        for name in ("_esbmc_" + flat, flat):
            if name in self.stubs:
                return ast.Name(name, node.ctx)
        return self.generic_visit(node)


class _SpreadBack(ast.NodeTransformer):
    """``lib.f(_star0=a, _kw0=k)`` (the slicer naming spread arguments for a stub) read as ``lib.f(*a, **k)``."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        spread = [k for k in node.keywords if k.arg and _SPREAD.fullmatch(k.arg)]
        if spread:
            node.args = node.args + [ast.Starred(k.value, ast.Load()) for k in spread if k.arg.startswith("_star")]
            node.keywords = [ast.keyword(None, k.value) if k in spread else k for k in node.keywords
                             if not (k in spread and k.arg.startswith("_star"))]
        return node


def _imported(function: ast.AST) -> set[str]:
    return {(a.asname or a.name).split(".")[0] for n in ast.walk(function)
            if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}


class _DropImports(ast.NodeTransformer):
    """Function-level imports of ``names`` outside a ``try`` (whose handler may be the code that runs)."""

    def __init__(self, names: set[str]) -> None:
        self.names = names

    def visit_Try(self, node: ast.Try) -> ast.AST:
        for name in ("handlers", "orelse", "finalbody"):
            setattr(node, name, [self.visit(n) for n in getattr(node, name)])
        return node

    visit_TryStar = visit_Try

    def visit_Import(self, node: ast.Import | ast.ImportFrom) -> ast.AST:
        if {(a.asname or a.name).split(".")[0] for a in node.names} <= self.names:
            return ast.copy_location(ast.Pass(), node)
        return node

    visit_ImportFrom = visit_Import


def _local_scopes_only(function: ast.AST) -> bool:
    """A consistent renaming of locals keeps the behaviour unless a name is reached another way."""
    for node in ast.walk(function):
        if isinstance(node, (ast.ClassDef, ast.Global, ast.Nonlocal, ast.Match)):
            return False
        if isinstance(node, ast.Name) and node.id in _SCOPE_TRICKS:
            return False
        if isinstance(node, _COMPREHENSIONS) and any(isinstance(n, ast.NamedExpr) for n in ast.walk(node)):
            return False
    return True


def _arguments(args: ast.arguments) -> list[ast.arg]:
    return [*args.posonlyargs, *args.args, *args.kwonlyargs, *filter(None, (args.vararg, args.kwarg))]


def _inner(scope: ast.AST) -> list[ast.AST]:
    """What runs inside the scope: a comprehension's first iterable is evaluated outside it."""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return list(scope.body)
    if isinstance(scope, ast.Lambda):
        return [scope.body]
    first, *rest = scope.generators
    parts = [getattr(scope, f) for f in ("elt", "key", "value") if hasattr(scope, f)]
    return [*parts, first.target, *first.ifs, *rest]


def _locals(scope: ast.AST) -> tuple[set[str], set[str]]:
    """(locals a renaming may respell, locals that keep their spelling: parameters, nested definitions,
    import and ``except ... as`` names, which callers or the AST see as text)."""
    fixed = {a.arg for a in _arguments(scope.args)} if isinstance(scope, _FUNCTIONS) else set()
    stores, pending = set(), _inner(scope)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fixed.add(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, _COMPREHENSIONS):
            pending.append(node.generators[0].iter)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            fixed |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            fixed.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores.add(node.id)
        elif isinstance(node, ast.AnnAssign) and node.value is None:
            continue  # binds nothing
        pending += ast.iter_child_nodes(node)
    return stores - fixed, fixed


class _Alpha:
    """Structural equality up to a consistent renaming (a bijection per scope) of the locals a renaming
    may respell; with ``rename`` False, plain equality."""

    def __init__(self, rename: bool) -> None:
        self.rename = rename
        self.scopes: list[tuple] = []

    def push(self, left: ast.AST, right: ast.AST) -> None:
        self.scopes.append((*_locals(left), *_locals(right), {}, {}))

    def _scope(self, name: str, side: int) -> int | None:
        for index in range(len(self.scopes) - 1, -1, -1):
            free, fixed = self.scopes[index][2 * side:2 * side + 2]
            if name in free or name in fixed:
                return index
        return None

    def _name(self, x: ast.Name, y: ast.Name) -> bool:
        if type(x.ctx) is not type(y.ctx):
            return False
        index = self._scope(x.id, 0)
        if index is None or index != self._scope(y.id, 1):
            return index is None and self._scope(y.id, 1) is None and x.id == y.id
        _, left_fixed, _, right_fixed, forward, backward = self.scopes[index]
        if x.id in left_fixed or y.id in right_fixed or not self.rename:
            return x.id == y.id and (x.id in left_fixed) == (y.id in right_fixed)
        return forward.setdefault(x.id, y.id) == y.id and backward.setdefault(y.id, x.id) == x.id

    def _inside(self, x: ast.AST, y: ast.AST, left: list, right: list) -> bool:
        self.push(x, y)
        try:
            return self.same(left, right)
        finally:
            self.scopes.pop()

    def same(self, x: object, y: object) -> bool:
        if type(x) is not type(y):
            return False
        if isinstance(x, list):
            return len(x) == len(y) and all(self.same(a, b) for a, b in zip(x, y, strict=True))
        if not isinstance(x, ast.AST):
            return x == y
        if isinstance(x, ast.Name):
            return self._name(x, y)
        if isinstance(x, _FUNCTIONS):
            # Defaults, annotations and decorators run in the enclosing scope, the body in its own.
            if ast.dump(_shape(x.args)) != ast.dump(_shape(y.args)) or not all(
                    self.same(getattr(x.args, f), getattr(y.args, f)) for f in ("defaults", "kw_defaults")) \
                    or not all(self.same(a.annotation, b.annotation)
                               for a, b in zip(_arguments(x.args), _arguments(y.args), strict=True)) \
                    or not all(self.same(getattr(x, f), getattr(y, f)) for f in x._fields if f not in ("args", "body")):
                return False
            return self._inside(x, y, [x.body], [y.body])
        if isinstance(x, _COMPREHENSIONS):
            if len(x.generators) != len(y.generators) or x.generators[0].is_async != y.generators[0].is_async \
                    or not self.same(x.generators[0].iter, y.generators[0].iter):
                return False
            return self._inside(x, y, _inner(x), _inner(y))
        return all(self.same(getattr(x, f, None), getattr(y, f, None)) for f in x._fields)


def _shape(args: ast.arguments) -> ast.arguments:
    """Parameter names and kinds without defaults or annotations (compared separately)."""
    return ast.arguments(posonlyargs=[ast.arg(a.arg) for a in args.posonlyargs],
                         args=[ast.arg(a.arg) for a in args.args],
                         vararg=args.vararg and ast.arg(args.vararg.arg),
                         kwonlyargs=[ast.arg(a.arg) for a in args.kwonlyargs], kw_defaults=[],
                         kwarg=args.kwarg and ast.arg(args.kwarg.arg), defaults=[])


def _compat_builtins(tree: ast.Module) -> set[str]:
    """``COMPAT_RENAMED`` names the module only imports (the slicer renames no other)."""
    imported = {(a.asname or a.name) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    rebound = _bound_at_module_level(ast.Module([n for n in tree.body if not isinstance(
        n, (ast.Import, ast.ImportFrom))], []))
    return {name for name in COMPAT_RENAMED if name in imported and name not in rebound}


def same_code(original: ast.FunctionDef, checked: ast.FunctionDef, original_module: ast.Module,
              checked_module: ast.Module) -> bool:
    """The two functions run the same statements (see the module docstring for what is ignored)."""
    original = _AsStubs(original, checked, _compat_builtins(original_module)).visit(copy.deepcopy(original))
    checked = _SpreadBack().visit(copy.deepcopy(checked))
    original, checked = Cosmetic().visit(original), Cosmetic().visit(checked)
    dropped = _imported(original) - _imported(checked)
    read = {n.id for n in ast.walk(checked) if isinstance(n, ast.Name)}
    if dropped and dropped & read <= _bound_at_module_level(checked_module):
        # The copy reads what the import bound from its own module-level definition (a stub).
        original = Cosmetic().visit(_DropImports(dropped).visit(original))
    alpha = _Alpha(rename=_local_scopes_only(original) and _local_scopes_only(checked))
    alpha.push(original, checked)
    # The target's own signature is not compared (a harness may type or reshape it): its parameters keep
    # their spelling on both sides.
    parameters = {a.arg for a in _arguments(original.args) + _arguments(checked.args)}
    for side in (1, 3):
        alpha.scopes[-1][side].update(parameters)
    return alpha.same(original.body, checked.body)


def _compat_module(tree: ast.Module) -> ast.Module | None:
    rewritten, transforms = rewrite_compat(ast.unparse(tree))
    return ast.parse(rewritten) if transforms else None


def preserved(original_module: ast.Module, checked_module: ast.Module, qualified: str, expression: str = "") -> bool:
    """The target, and for a nested target the entry function on the bug path when the program still has it,
    kept their code; also when they equal the original after the behaviour-preserving catalogue rewrites
    (``rewrite_compat``)."""
    compat: list[ast.Module | None] = []

    def kept(find) -> bool:
        checked = find(checked_module)
        if checked is None:
            return False
        function = find(original_module)
        if function is not None and same_code(function, checked, original_module, checked_module):
            return True
        if not compat:
            compat.append(_compat_module(original_module))
        rewritten = compat[0] and find(compat[0])
        return rewritten is not None and same_code(rewritten, checked, compat[0], checked_module)

    if not kept(lambda tree: locate(tree, qualified, expression)):
        return False
    entry = entry_of(original_module, qualified, expression)
    return entry is None or find_function(checked_module, entry) is None or kept(
        lambda tree: find_function(tree, entry))
