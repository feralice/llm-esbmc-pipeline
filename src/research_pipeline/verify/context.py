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


def _root(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


# Builtins that never mutate their arguments.
_PURE_BUILTINS = frozenset({
    "print", "len", "str", "repr", "format", "isinstance", "issubclass", "hasattr", "getattr", "id", "hash",
    "type", "bool", "int", "float", "list", "tuple", "set", "frozenset", "dict", "sorted", "min", "max",
    "sum", "any", "all", "enumerate", "zip", "iter", "range",
})


def _writes(node: ast.AST, names: set[str], data: set[str]) -> bool:
    """Could running ``node`` rebind a kept name or change kept data? Reading it cannot."""
    for child in ast.walk(node):
        if isinstance(child, ast.Global) and set(child.names) & names:
            return True
        if isinstance(child, (ast.Attribute, ast.Subscript)) and isinstance(child.ctx, (ast.Store, ast.Del)):
            if _root(child) in data:
                return True
        elif isinstance(child, ast.Call):
            method_on_data = isinstance(child.func, ast.Attribute) and _root(child.func.value) in data
            pure = isinstance(child.func, ast.Name) and child.func.id in _PURE_BUILTINS
            passes_data = not pure and any(_root(arg) in data for arg in [*child.args, *(k.value for k in child.keywords)])
            if method_on_data or passes_data:
                return True
    return False


def _mutators(tree: ast.Module, names: set[str], data: set[str]) -> set[str]:
    """Top-level functions, and classes with a method, that could change a kept name when called."""
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and _writes(node, names, data):
            found.add(node.name)
    return found


def _touches(node: ast.stmt, names: set[str], data: set[str], mutators: set[str]) -> bool:
    """Could this top-level statement change a kept name's value at import time?"""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name in names  # a redefinition
    stored = {child.id for child in ast.walk(node)
              if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}
    written = stored | _defined_names(node) if isinstance(node, _DEFINITIONS) else stored
    return bool(written & names or _loaded_names(node) & mutators) or _writes(node, names, data)


def _closure(tree: ast.Module, candidates: list[ast.stmt], root: ast.stmt) -> set[int]:
    """The root, what it reaches by name, and every top-level statement that could change
    one of those names at import time (with what that statement reaches), to a fixpoint."""
    kept, pending = {id(root)}, [root]
    while True:
        while pending:
            needed = _loaded_names(pending.pop())
            for node in candidates:
                if id(node) not in kept and _defined_names(node) & needed:
                    kept.add(id(node))
                    pending.append(node)
        names = set().union(*(_defined_names(node) for node in tree.body if id(node) in kept))
        data = _data_names(tree) & names
        mutators = _mutators(tree, names, data)
        pending = [node for node in tree.body if id(node) not in kept and not _is_main_guard(node)
                   and _touches(node, names, data, mutators)]
        if not pending:
            return kept
        kept |= {id(node) for node in pending}


def context_module(source: str, function: str) -> str:
    """Return the target's top-level statement plus the definitions it reaches by name.

    Module-level side effects (bare calls, ``if __name__`` blocks) are left out,
    so the result can be executed or verified without running the real module,
    unless they could change a kept name: those are kept verbatim too.
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

    kept = _closure(tree, candidates, roots[0])

    lines = source.splitlines(keepends=True)
    chunks = []
    for node in tree.body:
        if id(node) in kept:
            start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
            chunks.append("".join(lines[start - 1:node.end_lineno]).rstrip() + "\n")
    return "\n\n".join(chunks)
