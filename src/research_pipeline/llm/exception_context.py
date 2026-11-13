"""Which exceptions the callers of a function already catch, and which functions nothing in the file calls.

Context for the detector (variant A21): an exception that every caller catches does not crash the program.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ..models import CodeUnit
from ..scan.callgraph import CallGraph, _shorten, build_source_callgraph

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_MAX_ENTRIES = 8


def handler_names(handler: ast.ExceptHandler) -> set[str]:
    if handler.type is None:
        return {"BaseException"}
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return {t.id if isinstance(t, ast.Name) else t.attr for t in types if isinstance(t, (ast.Name, ast.Attribute))}


def caught_at(tree: ast.Module, call: ast.Call) -> frozenset[str]:
    """Exception names caught by the ``try`` blocks that enclose ``call`` inside its function."""
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    names: set[str] = set()
    node: ast.AST = call
    while id(node) in parents and not isinstance(node, _SCOPES):
        parent = parents[id(node)]
        if isinstance(parent, ast.Try) and any(node is statement for statement in parent.body):
            for handler in parent.handlers:
                names |= handler_names(handler)
        node = parent
    return frozenset(names)


def _call_at(tree: ast.Module, line: int, end_line: int, expression: str) -> ast.Call | None:
    return next((n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.lineno == line
                 and (n.end_lineno or n.lineno) == end_line and _shorten(ast.unparse(n.func)) == expression), None)


def _key(graph: CallGraph, qualname: str) -> str | None:
    return next((key for key, node in graph.functions.items() if node.qualname == qualname), None)


def exception_context(unit: CodeUnit) -> str:
    """Text for the prompt; "" when the file cannot be read or holds no caller and no candidate entry."""
    try:
        source = Path(unit.path).read_text(encoding="utf-8")
        graph = build_source_callgraph(source, Path(unit.path).name)
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError, RecursionError):
        return ""
    key = _key(graph, unit.qualname)
    if key is None:
        return ""
    lines = []
    for site in graph.callers(key):
        call = _call_at(tree, site.line, site.end_line, site.expression)
        caller = graph.functions[site.caller].qualname if site.caller in graph.functions else site.caller
        if call is None:
            lines.append(f"- {caller} line {site.line}: call site not located")
            continue
        caught = caught_at(tree, call)
        lines.append(f"- {caller} line {site.line}: "
                     + (f"catches {', '.join(sorted(caught))}" if caught else "no try/except around the call"))
    entries = [node.qualname for k, node in graph.functions.items()
               if not graph.callers(k) and not node.qualname.split(".")[-1].startswith("_")][:_MAX_ENTRIES]
    if not lines and not entries:
        return ""
    return ("Callers in this file and the exceptions they catch:\n" + ("\n".join(lines) or "- none in this file")
            + "\nFunctions no caller in this file calls (possible public entries):\n"
            + ("\n".join(f"- {name}" for name in entries) or "- none"))
