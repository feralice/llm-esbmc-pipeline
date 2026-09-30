"""Compatibility rewrites: Python constructs ESBMC-Python rejects, replaced by exact equivalents.

Each rewrite is equivalent by the language definition, applied in place on its own line so line
numbers do not move, and recorded as a transform.
"""

from __future__ import annotations

import ast
import json
import re

# printf-style formatting: "%s" converts with str() (Python docs, "printf-style String Formatting").
_CONVERSION = re.compile(r"%%|%s|%.")


def _percent_pieces(fmt: str, args: list[str]) -> list[str] | None:
    pieces, literal, used = [], "", 0
    for token in [t for t in re.split(f"({_CONVERSION.pattern})", fmt) if t]:
        if token == "%%":
            literal += "%"
        elif token == "%s":
            if used == len(args):
                return None
            if literal:
                pieces.append(json.dumps(literal, ensure_ascii=False))
                literal = ""
            pieces.append(f"str({args[used]})")
            used += 1
        elif token.startswith("%"):
            return None  # %d, %r, %f, %(key)s ... do not reduce to str()
        else:
            literal += token
    if literal:
        pieces.append(json.dumps(literal, ensure_ascii=False))
    return pieces if used == len(args) else None


def _percent_format_edits(source: str, tree: ast.Module) -> list[tuple[int, int, int, str]]:
    edits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
                and isinstance(node.right, ast.Tuple) and node.lineno == node.end_lineno
                and not any(isinstance(e, ast.Starred) for e in node.right.elts)):
            continue
        args = [ast.get_source_segment(source, element) for element in node.right.elts]
        pieces = _percent_pieces(node.left.value, args) if all(args) else None
        if pieces:
            edits.append((node.lineno, node.col_offset, node.end_col_offset, " + ".join(pieces)))
    # Keep only outermost edits; a nested one would be replaced twice.
    return [e for e in edits if not any(o is not e and o[0] == e[0] and o[1] <= e[1] and e[2] <= o[2]
                                        for o in edits)]


def _delegating_def(alias: str, method: ast.FunctionDef) -> str | None:
    """``alias = method`` as a one-line def that calls it; None when the signature cannot be
    forwarded exactly (decorators, *args/**kwargs, no receiver)."""
    args = method.args
    if method.decorator_list or args.vararg or args.kwarg or args.posonlyargs or not args.args:
        return None
    receiver, *positional = [a.arg for a in args.args]
    forwarded = [*positional, *(f"{a.arg}={a.arg}" for a in args.kwonlyargs)]
    returns = f" -> {ast.unparse(method.returns)}" if method.returns else ""
    return f"def {alias}({ast.unparse(args)}){returns}: return {receiver}.{method.name}({', '.join(forwarded)})"


def _method_alias_edits(tree: ast.Module) -> list[tuple[int, int, int, str]]:
    """ESBMC 8.5 rejects ``__repr__ = __str__`` in a class body ("Variable __str__ not found")."""
    edits = []
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        for node in cls.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Name) and node.value.id in methods
                    and node.lineno == node.end_lineno):
                continue
            text = _delegating_def(node.targets[0].id, methods[node.value.id])
            if text:
                edits.append((node.lineno, node.col_offset, node.end_col_offset, text))
    return edits


def rewrite_compat(source: str) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    percent, aliases = _percent_format_edits(source, tree), _method_alias_edits(tree)
    if not percent and not aliases:
        return source, []
    lines = source.splitlines(keepends=True)
    for lineno, start, end, text in sorted([*percent, *aliases], reverse=True):
        raw = lines[lineno - 1].encode("utf-8")  # ast offsets count UTF-8 bytes
        lines[lineno - 1] = (raw[:start] + text.encode("utf-8") + raw[end:]).decode("utf-8")
    transforms = [f"compat_percent_format:{len(percent)}"] if percent else []
    if aliases:
        transforms.append(f"compat_method_alias:{len(aliases)}")
    return "".join(lines), transforms
