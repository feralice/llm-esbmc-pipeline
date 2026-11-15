"""Bounded repository definitions for a detector that explicitly requested missing context."""

from __future__ import annotations

import ast

from .callgraph import CallGraph

MAX_RETRY_DEFINITIONS = 3
MAX_RETRY_DEFINITION_CHARS = 4000


def missing_context(entry: dict) -> bool:
    return entry.get('reason', '').endswith('(missing context)')


def retry_context(graph: CallGraph, target, held: list[dict]) -> str:
    names = set()
    for entry in held:
        if not missing_context(entry):
            continue
        try:
            tree = ast.parse(entry['expression'])
        except (SyntaxError, ValueError, RecursionError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    names.add(node.func.attr)
    owner = graph.functions[target.key]
    matches = [f for f in graph.functions.values()
               if f.name in names and not f.ambiguous and f.key != target.key]
    matches.sort(key=lambda f: (not (owner.class_qualname and f.module == owner.module
                                     and f.class_qualname == owner.class_qualname),
                                f.module != owner.module, f.file, f.start_line))
    blocks = []
    for function in matches[:MAX_RETRY_DEFINITIONS]:
        source = '\n'.join(graph.sources[function.file][function.start_line - 1:function.end_line])
        blocks.append(f'Definition from {function.file}:{function.start_line}\n'
                      + source[:MAX_RETRY_DEFINITION_CHARS])
    return '\n\n'.join(blocks)
