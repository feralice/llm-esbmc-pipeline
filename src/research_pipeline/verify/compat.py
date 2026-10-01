"""ESBMC-only compatibility rewrites; CPython replays the version before these edits.

Percent formatting is lowered only for literal formats and primitive driver domains.
Annotations alone do not establish a domain. Dynamic string %r stays unsupported:
ESBMC 8.5 does not model repr() faithfully. Edits preserve the number of source lines.
"""

from __future__ import annotations

import ast

from .astutil import find_function

_NUMERIC = {"int", "float", "bool"}
_SCALAR = _NUMERIC | {"str", "bytes", "None", "none"}


def _bound_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                               ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            if node.name:
                names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
    return names


def _parameter_domains(tree: ast.Module, parameter_types: dict[str, dict[str, str]]) -> dict[ast.AST, dict[str, str]]:
    domains = {}
    if any(isinstance(node, ast.Name) and node.id in {"getattr", "eval", "exec", "globals", "locals"}
           for node in ast.walk(tree)):
        return domains
    for name, types in parameter_types.items():
        function = find_function(tree, name)
        if (function is None or function.decorator_list
                or (function.name.startswith("__") and function.name.endswith("__"))):
            continue
        refs = [node for node in ast.walk(tree)
                if ((isinstance(node, ast.Name) and node.id == function.name)
                    or (isinstance(node, ast.Attribute) and node.attr == function.name))]
        if len(refs) > 1 or any(node in refs for node in ast.walk(function)):
            continue
        parameters = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
        readonly = parameters - _bound_names(function)
        domain = {key: value for key, value in types.items() if key in readonly}
        pending = list(function.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            domains[node] = domain
            pending.extend(ast.iter_child_nodes(node))
    return domains


def _operand_kind(node: ast.AST, domain: dict[str, str]) -> str:
    if isinstance(node, ast.Constant):
        return type(node.value).__name__ if node.value is not None else "None"
    if isinstance(node, ast.Name):
        return domain.get(node.id, "")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        kind = _operand_kind(node.operand, domain)
        return kind if kind in _NUMERIC else ""
    return ""


def _percent_pieces(fmt: str, operands: list[ast.expr], domain: dict[str, str]) -> list[str] | None:
    pieces, literal, used, index = [], "", 0, 0
    while index < len(fmt):
        char = fmt[index]
        index += 1
        if char != "%":
            literal += char
            continue
        if index == len(fmt):
            return None
        conversion = fmt[index]
        index += 1
        if conversion == "%":
            literal += "%"
            continue
        if conversion not in {"s", "r", "d"} or used == len(operands):
            return None
        operand = operands[used]
        kind = _operand_kind(operand, domain)
        if kind not in _SCALAR and not (fmt == "%s" and len(operands) == 1):
            return None
        argument = ast.unparse(operand)
        if conversion == "d":
            if kind not in _NUMERIC:
                return None
            converted = f"str(int({argument}))"
        elif conversion == "r" and kind == "str":
            if not isinstance(operand, ast.Constant):
                return None
            converted = repr(repr(operand.value))
        else:
            # str == repr for exact numeric, bool, bytes and None values.
            converted = f"str({argument})"
        if literal:
            pieces.append(repr(literal))
            literal = ""
        pieces.append(converted)
        used += 1
    if literal:
        pieces.append(repr(literal))
    return pieces if used == len(operands) else None


def _percent_format_edits(tree: ast.Module, parameter_types: dict[str, dict[str, str]]) -> list[tuple[int, int, int, int, str]]:
    bindings = _bound_names(tree) | {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    if bindings & {"str", "int"}:
        return []
    domains = _parameter_domains(tree, parameter_types)
    edits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
            continue
        domain = domains.get(node, {})
        if isinstance(node.right, ast.Tuple):
            operands = node.right.elts
        elif _operand_kind(node.right, domain) in _SCALAR:
            operands = [node.right]
        else:
            continue
        if any(isinstance(operand, ast.Starred) for operand in operands):
            continue
        pieces = _percent_pieces(node.left.value, operands, domain)
        if pieces:
            replacement = "(" + " + ".join(pieces) + "\n" * (node.end_lineno - node.lineno) + ")"
            edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, replacement))
    return [edit for edit in edits if not any(other is not edit and other[:2] <= edit[:2]
                                              and edit[2:4] <= other[2:4] for other in edits)]


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


def rewrite_compat(source: str, *, parameter_types: dict[str, dict[str, str]] | None = None) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    percent = _percent_format_edits(tree, parameter_types or {})
    aliases = _method_alias_edits(tree)
    if not percent and not aliases:
        return source, []
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    edits = [*percent, *((line, start, line, end, text) for line, start, end, text in aliases)]
    raw = source.encode("utf-8")
    for line, start, end_line, end, text in sorted(edits, reverse=True):
        raw = raw[:offsets[line - 1] + start] + text.encode("utf-8") + raw[offsets[end_line - 1] + end:]
    transforms = [f"compat_percent_format:{len(percent)}"] if percent else []
    if aliases:
        transforms.append(f"compat_method_alias:{len(aliases)}")
    return raw.decode("utf-8"), transforms
