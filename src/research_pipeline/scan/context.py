"""Smallest verbatim module that still defines a target and its dependencies."""

from __future__ import annotations

import ast

_DEFINITIONS = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
)


def _defined_names(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(alias.asname or alias.name).split(".")[0] for alias in node.names}
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {name.id for target in targets for name in ast.walk(target) if isinstance(name, ast.Name)}


def _loaded_names(node: ast.stmt) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _is_main_guard(node: ast.stmt) -> bool:
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")


def _pruned_code_touches(tree: ast.Module, statements: list[ast.stmt], kept: set[int], names: set[str]) -> bool:
    """Would dropping code change a kept name's value at import time?

    Conservative: any dropped top-level statement that mentions a kept name,
    a second definition of it, or a ``global`` rebinding of it anywhere.
    """
    for node in tree.body:
        if id(node) in kept or _is_main_guard(node):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # A dropped definition runs no body at import; only its name can clash.
            touched = {node.name}
        else:
            touched = (_defined_names(node) if node in statements else set()) | _loaded_names(node)
        if touched & names:
            return True
    return any(isinstance(node, ast.Global) and set(node.names) & names for node in ast.walk(tree))


def context_module(source: str, function: str) -> str:
    """Return the target's top-level statement plus the definitions it reaches by name.

    Module-level side effects (bare calls, ``if __name__`` blocks) are left out,
    so the result can be executed or verified without running the real module.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    root_name = function.split(".")[0]
    statements = [node for node in tree.body if isinstance(node, _DEFINITIONS)]
    roots = [node for node in statements
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and node.name == root_name]
    if len(roots) != 1:
        return ""

    kept = {id(roots[0])}
    pending = [roots[0]]
    while pending:
        needed = _loaded_names(pending.pop())
        for node in statements:
            if id(node) not in kept and _defined_names(node) & needed:
                kept.add(id(node))
                pending.append(node)

    kept_names = set().union(*(_defined_names(node) for node in statements if id(node) in kept))
    if _pruned_code_touches(tree, statements, kept, kept_names):
        return ""

    lines = source.splitlines(keepends=True)
    chunks = []
    for node in statements:
        if id(node) in kept:
            start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
            chunks.append("".join(lines[start - 1:node.end_lineno]).rstrip() + "\n")
    return "\n\n".join(chunks)
