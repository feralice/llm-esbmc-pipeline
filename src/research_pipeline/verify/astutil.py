"""AST lookups shared by the verify engine: target function, suspect expression, free names."""

from __future__ import annotations

import ast
import builtins
import symtable
import textwrap

_INTRINSICS = {
    "nondet_int", "nondet_float", "nondet_bool", "nondet_str",
    "nondet_list", "nondet_dict", "__ESBMC_assume",
}


def find_function(tree: ast.Module, qualified_name: str) -> ast.FunctionDef | None:
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
    return matches[0] if len(matches) == 1 and isinstance(matches[0], ast.FunctionDef) else None


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


def locate(tree: ast.Module, qualified: str) -> ast.FunctionDef | None:
    """The target in a program that may have hoisted or nested it: by path first, then the only function
    with that name anywhere in the file."""
    found = find_function(tree, qualified) or find_definition(tree, qualified)
    if found is not None:
        return found
    name = qualified.split(".")[-1]
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    return matches[0] if len(matches) == 1 else None


def _own_calls(scope: ast.AST) -> list[ast.Call]:
    """Calls in the scope's body, not in the definitions nested in it."""
    calls, pending = [], list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, _DEFINITIONS):
            continue
        if isinstance(node, ast.Call):
            calls.append(node)
        pending += ast.iter_child_nodes(node)
    return calls


def _runs(scope: ast.AST, link: ast.AST, after: ast.AST | None) -> bool:
    """Whether ``scope`` runs ``link``: calls the function, or for a class, builds it and calls ``after`` on it."""
    calls = _own_calls(scope)
    called = {c.func.id for c in calls if isinstance(c.func, ast.Name)}
    if not isinstance(link, ast.ClassDef):
        return link.name in called
    return link.name in called and after is not None and any(
        isinstance(c.func, ast.Attribute) and c.func.attr == after.name for c in calls)


def outer_entry(tree: ast.Module, qualified: str, expression: str = "") -> str | None:
    """For a function nested in another: the outermost enclosing function ``find_function`` locates, when
    every definition on the way runs the next one. Entering there keeps the captured values real."""
    chain = nested_chain(tree, qualified, expression)
    if chain is None:
        return None
    names = qualified.split(".")
    entry = next((i for i in range(len(chain) - 1)
                  if not isinstance(chain[i], ast.ClassDef) and find_function(tree, ".".join(names[:i + 1]))), None)
    if entry is None:
        return None
    for position in range(entry, len(chain) - 1):
        scope, link = chain[position], chain[position + 1]
        if isinstance(scope, ast.ClassDef):
            continue
        after = chain[position + 2] if position + 2 < len(chain) else None
        if not _runs(scope, link, after):
            return None
    return ".".join(names[:entry + 1])


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
