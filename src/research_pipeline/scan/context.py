"""Smallest verbatim module that still defines a target and its dependencies."""

from __future__ import annotations

import ast

_DEFINITIONS = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
)
# Allowed inside a kept top-level if/try block: bindings without other effects.
_SIMPLE = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.Pass, ast.Expr, ast.If, ast.Try)


def _defined_names(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(alias.asname or alias.name).split(".")[0] for alias in node.names}
    if isinstance(node, (ast.If, ast.Try)):
        return {name for child in _block_statements(node) for name in _defined_names(child)}
    targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
    return {name.id for target in targets if target is not None
            for name in ast.walk(target) if isinstance(name, ast.Name)}


def _block_statements(node: ast.If | ast.Try) -> list[ast.stmt]:
    blocks = [node.body, node.orelse]
    if isinstance(node, ast.Try):
        blocks += [handler.body for handler in node.handlers] + [node.finalbody]
    return [stmt for block in blocks for stmt in block]


def _is_simple_block(node: ast.stmt) -> bool:
    """A top-level if/try made only of imports, assignments and constant expressions."""
    if not isinstance(node, (ast.If, ast.Try)):
        return False
    for stmt in _block_statements(node):
        if not isinstance(stmt, _SIMPLE):
            return False
        if isinstance(stmt, (ast.If, ast.Try)) and not _is_simple_block(stmt):
            return False
    return True


def _loaded_names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _is_main_guard(node: ast.stmt) -> bool:
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")


def _data_names(tree: ast.Module) -> set[str]:
    """Names bound by assignment at top level: the only ones import-time code can mutate."""
    return {name for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            for name in (child.id for child in ast.walk(target) if isinstance(child, ast.Name))}


def _pruned_code_touches(tree: ast.Module, kept: set[int], names: set[str]) -> bool:
    """Would dropping code change a kept name's value at import time?

    A dropped statement may read kept modules, functions and classes freely.
    It must not rebind a kept name, nor mention kept module-level data (which
    it could mutate), and no ``global`` may rebind a kept name.
    """
    data = _data_names(tree) & names
    for node in tree.body:
        if id(node) in kept or _is_main_guard(node):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            touched = {node.name} & names
        else:
            stored = {child.id for child in ast.walk(node)
                      if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}
            touched = ((stored | _defined_names(node) if isinstance(node, _DEFINITIONS) else stored) & names
                       ) | (_loaded_names(node) & data)
        if touched:
            return True
    return any(isinstance(node, ast.Global) and set(node.names) & names for node in ast.walk(tree))


def context_module(source: str, function: str) -> str:
    """Return the target's top-level statement plus the definitions it reaches by name.

    Module-level side effects (bare calls, ``if __name__`` blocks) are left out,
    so the result can be executed or verified without running the real module.
    Simple ``if``/``try`` blocks that bind a needed name are kept whole.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    root_name = function.split(".")[0]
    candidates = [node for node in tree.body
                  if isinstance(node, _DEFINITIONS) or (_is_simple_block(node) and not _is_main_guard(node))]
    roots = [node for node in candidates
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and node.name == root_name]
    if len(roots) != 1:
        return ""

    kept = {id(roots[0])}
    pending = [roots[0]]
    while pending:
        needed = _loaded_names(pending.pop())
        for node in candidates:
            if id(node) not in kept and _defined_names(node) & needed:
                kept.add(id(node))
                pending.append(node)

    kept_names = set().union(*(_defined_names(node) for node in tree.body if id(node) in kept))
    if _pruned_code_touches(tree, kept, kept_names):
        return ""

    lines = source.splitlines(keepends=True)
    chunks = []
    for node in tree.body:
        if id(node) in kept:
            start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
            chunks.append("".join(lines[start - 1:node.end_lineno]).rstrip() + "\n")
    return "\n\n".join(chunks)
