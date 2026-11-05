"""AST lookups shared by the verify engine: target function, suspect expression, free names."""

from __future__ import annotations

import ast
import builtins
import symtable
import textwrap
from collections.abc import Callable
from itertools import pairwise

_INTRINSICS = {
    "nondet_int", "nondet_float", "nondet_bool", "nondet_str",
    "nondet_list", "nondet_dict", "__ESBMC_assume",
}


def find_function(tree: ast.Module, qualified_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """A module-level function (``async def`` included) or a method of a module-level class, defined once."""
    parts = qualified_name.split(".")
    if len(parts) == 1:
        matches = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == parts[0]]
    elif len(parts) == 2:
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
        matches = [method for cls in classes for method in cls.body
                   if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and method.name == parts[1]]
    else:
        return None
    if len(matches) != 1 or (len(parts) == 2 and isinstance(matches[0], ast.AsyncFunctionDef)):
        return None
    return matches[0]


CROSS_MODULE_AWAIT = "await of a function from another module"


def coroutine_limit(function: ast.AsyncFunctionDef, awaited: Callable[[ast.Call], str | None], *,
                    module_level: bool) -> str:
    """Why ESBMC-Python (measured on d520a903ae) or the single-module harness cannot run ``function``; ""
    when it can. It runs a module-level undecorated ``async def`` awaited or passed to ``asyncio.run``, and
    refuses methods, nested coroutines, decorators, ``async for``/``with`` and an ``await`` of anything but a
    call to a module-level ``async def``. ``awaited`` gives the limit of the coroutine a call reaches ("" when
    it has none, CROSS_MODULE_AWAIT when it lives in another module), or None when it is not one."""
    if not module_level:
        return "async method or nested coroutine"
    if function.decorator_list:
        return "decorated coroutine"
    for child in _own_nodes(function):
        if isinstance(child, (ast.AsyncFor, ast.AsyncWith)) or (
                isinstance(child, ast.comprehension) and child.is_async):
            return "async for or async with"
        if isinstance(child, ast.Await):
            limit = awaited(child.value) if isinstance(child.value, ast.Call) else None
            if limit is None:
                return "await of something other than a module-level async function"
            if limit:
                return limit
    return ""


_DEFINITIONS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def definitions_in(body: list[ast.stmt], name: str) -> list[ast.AST]:
    """Classes and functions called ``name`` in a scope, also under if/try/with/for (Keras' ``rnn`` and
    pandas' ``dispatch_to_series`` define one helper per branch), never inside another definition."""
    found, pending = [], list(body)
    while pending:
        node = pending.pop(0)
        if isinstance(node, _DEFINITIONS):
            if node.name == name:
                found.append(node)
            continue
        for field in ("body", "orelse", "finalbody", "handlers"):
            pending += [n for n in getattr(node, field, []) if isinstance(n, ast.AST)]
        if isinstance(node, ast.ExceptHandler):
            pending += node.body
    return found


def _definition_path(tree: ast.Module, qualified: str, expression: str = "") -> list[ast.AST] | None:
    """The definitions along ``a.b.c``; when branches define the last name more than once, the one
    holding ``expression`` is it."""
    chain, scope = [], tree.body
    names = qualified.split(".")
    for position, name in enumerate(names):
        found = definitions_in(scope, name) if chain else [
            n for n in scope if isinstance(n, _DEFINITIONS) and n.name == name]
        if len(found) > 1 and expression and position == len(names) - 1:
            found = [n for n in found if isinstance(n, ast.FunctionDef) and expression_nodes(n, expression)]
        if len(found) != 1:
            return None
        chain.append(found[0])
        scope = found[0].body
    return chain if isinstance(chain[-1], (ast.FunctionDef, ast.AsyncFunctionDef)) else None


def nested_chain(tree: ast.Module, qualified: str, expression: str = "") -> list[ast.AST] | None:
    """``outer.Inner.method`` or ``outer.inner``: the nodes along the name, when one of them sits
    inside a function (the LLM located it, but it only exists once outer runs)."""
    chain = _definition_path(tree, qualified, expression)
    if chain is None or all(isinstance(n, ast.ClassDef) for n in chain[:-1]):
        return None
    return chain


def find_definition(tree: ast.Module, qualified: str, expression: str = "") -> ast.FunctionDef | None:
    """Like ``find_function``, at any depth: functions inside functions and classes inside functions."""
    chain = _definition_path(tree, qualified, expression)
    return chain[-1] if chain and isinstance(chain[-1], ast.FunctionDef) else None


def entry_of(tree: ast.Module, qualified: str, expression: str = "") -> str | None:
    """For a nested target, the outermost function on its path that ``find_function`` locates (the one a
    harness can call); None when the target is not nested or nothing on the path is callable."""
    chain = nested_chain(tree, qualified, expression)
    if chain is None:
        return None
    names = qualified.split(".")
    return next((".".join(names[:i + 1]) for i in range(len(chain) - 1)
                 if isinstance(find_function(tree, ".".join(names[:i + 1])), ast.FunctionDef)), None)


def locate(tree: ast.Module, qualified: str, expression: str = "") -> ast.FunctionDef | None:
    """The target in a program that may have hoisted or nested it: a module-level copy of a nested target
    first (that is the code that runs), then the path, then the only function with that name in the file."""
    found = find_function(tree, qualified)
    if found is not None:
        return found
    name = qualified.split(".")[-1]
    if "." in qualified:
        copies = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(copies) == 1:
            return copies[0]
    found = find_definition(tree, qualified, expression)
    if found is not None:
        return found
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    return matches[0] if len(matches) == 1 else None


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Nodes of the scope's body that run when it runs: not those in nested definitions or lambdas."""
    nodes, pending = [], list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, (*_DEFINITIONS, ast.Lambda)):
            continue
        nodes.append(node)
        pending += ast.iter_child_nodes(node)
    return nodes


def _is_generator(function: ast.AST) -> bool:
    return any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in _own_nodes(function))


def _rebound(nodes: list[ast.AST], name: str) -> bool:
    """The name is stored again in the scope (``g = abs``, a loop variable), so a later ``g()`` may be another."""
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store) for n in nodes)


def _runs(scope: ast.AST, link: ast.AST, after: ast.AST | None) -> bool:
    """Whether running ``scope`` runs ``link``: calls the function, or for a class, calls ``after`` on an
    instance of it (``K().m()`` or ``k = K()`` then ``k.m()``)."""
    nodes = _own_nodes(scope)
    if _rebound(nodes, link.name):
        return False
    calls = [n for n in nodes if isinstance(n, ast.Call)]
    if not isinstance(link, ast.ClassDef):
        return any(isinstance(c.func, ast.Name) and c.func.id == link.name for c in calls)
    if after is None:
        return False

    def builds(node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == link.name

    instances = {target.id for n in nodes if isinstance(n, ast.Assign) and builds(n.value)
                 for target in n.targets if isinstance(target, ast.Name)}
    return any(isinstance(c.func, ast.Attribute) and c.func.attr == after.name and (
        builds(c.func.value) or (isinstance(c.func.value, ast.Name) and c.func.value.id in instances)) for c in calls)


def outer_entry(tree: ast.Module, qualified: str, expression: str = "") -> str | None:
    """For a function nested in another: the entry (``entry_of``) when calling it runs every definition on the
    way to the target, so the captured values are the ones real code computes. Generators and coroutines on
    the way only build an object when called, so they never qualify."""
    entry = entry_of(tree, qualified, expression)
    if entry is None:
        return None
    chain = nested_chain(tree, qualified, expression)
    start = entry.count(".")
    path = chain[start:]
    if any(isinstance(n, ast.AsyncFunctionDef) or (isinstance(n, ast.FunctionDef) and _is_generator(n))
           for n in path):
        return None
    for position, (scope, link) in enumerate(pairwise(path)):
        if isinstance(scope, ast.ClassDef):
            continue
        after = path[position + 2] if position + 2 < len(path) else None
        if not _runs(scope, link, after):
            return None
    return entry


def entry_preserved(original: ast.Module, program: ast.Module, qualified: str, expression: str = "") -> bool:
    """For a nested target, the entry function holds the guards and the captured values on the bug path: when the
    program still has it, its body must be unchanged too."""
    entry = entry_of(original, qualified, expression)
    if entry is None:
        return True
    checked = find_function(program, entry)
    if checked is None:
        return True
    return body_signature(find_function(original, entry)) == body_signature(checked)


_HEADERS = ("if ", "elif ", "while ", "return ", "assert ")


def _readings(expression: str) -> list[str]:
    """The text as given, then without a block header's keyword and colon (``if x:`` -> ``x``), then
    each ``;``-separated statement: LLMs often copy the whole source line."""
    readings = [expression]
    for piece in [expression, *expression.split(";")]:
        text = textwrap.dedent(piece).strip().removesuffix(":").strip()
        for header in _HEADERS:
            if text.startswith(header):
                text = text[len(header):]
                break
        readings.append(text)
    return list(dict.fromkeys(r for r in readings if r.strip()))


def _header_expression(text: str) -> ast.expr | None:
    """``for x in rows:`` or ``with open(f) as fh:`` copied without its body: the expression it evaluates."""
    if not text.endswith(":"):
        return None
    try:
        body = ast.parse(text + "\n    pass").body
    except SyntaxError:
        return None
    node = body[0] if len(body) == 1 else None
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return node.iter
    if isinstance(node, (ast.With, ast.AsyncWith)) and len(node.items) == 1:
        return node.items[0].context_expr
    return None


def _matching(function: ast.FunctionDef, expression: str) -> list[ast.AST]:
    try:
        suspect: ast.AST = ast.parse(expression, mode="eval").body
        kind: type = ast.expr
    except SyntaxError:
        text = textwrap.dedent(expression).strip()
        try:
            body = ast.parse(text).body
        except SyntaxError:
            header = _header_expression(text)
            if header is None:
                return []
            body = [header]
        if len(body) != 1:
            return []
        suspect, kind = body[0], (ast.expr if isinstance(body[0], ast.expr) else ast.stmt)
    wanted = ast.dump(suspect, include_attributes=False)
    return [node for node in ast.walk(function)
            if isinstance(node, kind) and ast.dump(node, include_attributes=False) == wanted]


def body_signature(function: ast.FunctionDef) -> list[str]:
    """The body without its docstring as AST dumps: equal signatures run the same code."""
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return [ast.dump(stmt, include_attributes=False) for stmt in body]


def expression_nodes(function: ast.FunctionDef, expression: str) -> list[ast.AST]:
    """Nodes equal to the suspect; datasets give either an expression or one statement."""
    for reading in _readings(expression):
        nodes = _matching(function, reading)
        if nodes:
            return nodes
    return []


def _defined_global_names(table: symtable.SymbolTable) -> set[str]:
    return {
        symbol.get_name() for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }


def undefined_globals(source: str, filename: str) -> set[str]:
    table = symtable.symtable(source, filename, "exec")
    module_names = _defined_global_names(table)
    undefined: set[str] = set()
    pending = [table]
    while pending:
        current = pending.pop()
        pending.extend(current.get_children())
        if current is table:
            continue
        for symbol in current.get_symbols():
            name = symbol.get_name()
            if (symbol.is_global() and name not in module_names
                    and not hasattr(builtins, name) and name not in _INTRINSICS):
                undefined.add(name)
    return undefined
