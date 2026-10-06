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


def _matching(function: ast.FunctionDef, expression: str) -> list[ast.AST]:
    try:
        suspect: ast.AST = ast.parse(expression, mode="eval").body
        kind: type = ast.expr
    except SyntaxError:
        try:
            body = ast.parse(textwrap.dedent(expression).strip()).body
        except SyntaxError:
            return []
        if len(body) != 1:
            return []
        suspect, kind = body[0], ast.stmt
    wanted = ast.dump(suspect, include_attributes=False)
    return [node for node in ast.walk(function)
            if isinstance(node, kind) and ast.dump(node, include_attributes=False) == wanted]


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
