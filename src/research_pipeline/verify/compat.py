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


# Methods that, called on an exact str, return an exact str.
_STR_METHODS = {"join", "format", "strip", "lstrip", "rstrip", "lower", "upper", "title", "replace",
                "capitalize", "casefold", "zfill", "center", "ljust", "rjust"}
_MATCHERS = {"match", "search", "fullmatch"}


def _exact_str(node: ast.expr, assigned: dict[str, list[ast.expr]], re_names: set[str],
               seen: frozenset[str] = frozenset()) -> bool:
    """Is ``node`` an exact ``str`` (or None) at run time? Then ``"%s" % node`` is ``str(node)``: no tuple
    unpacking and no ``__rmod__`` of a str subclass. ``assigned`` maps a local to every value bound to it."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) or node.value is None
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in assigned and node.id not in seen and all(
            _exact_str(value, assigned, re_names, seen | {node.id}) for value in assigned[node.id])
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    func = node.func
    if func.attr in _STR_METHODS:
        return isinstance(func.value, ast.Constant) and isinstance(func.value.value, str)
    # re.match(...).group(g) is str or None; group(g1, g2) and group(*gs) are tuples.
    if func.attr == "group" and len(node.args) <= 1 and not node.keywords and not any(
            isinstance(arg, ast.Starred) for arg in node.args):
        return _is_match(func.value, assigned, re_names)
    return False


def _is_match(node: ast.expr, assigned: dict[str, list[ast.expr]], re_names: set[str]) -> bool:
    """A real ``re`` match object, or None."""
    if isinstance(node, ast.Name):
        return node.id in assigned and all(_is_match(v, assigned, re_names) for v in assigned[node.id])
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MATCHERS
            and isinstance(node.func.value, ast.Name) and node.func.value.id in re_names)


def _local_values(function: ast.AST) -> dict[str, list[ast.expr]]:
    """Locals bound only by plain ``name = value`` statements, with every value bound to them."""
    values: dict[str, list[ast.expr]] = {}
    plain: set[int] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    plain.add(id(target))
                    values.setdefault(target.id, []).append(node.value)
    excluded = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)
                and isinstance(node.ctx, (ast.Store, ast.Del)) and id(node) not in plain}
    for node in ast.walk(function):
        if isinstance(node, ast.arg):
            excluded.add(node.arg)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            excluded.update(node.names)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            excluded.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            excluded.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            excluded.add(node.rest)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not function:
            excluded.add(node.name)
    return {name: value for name, value in values.items() if name not in excluded}


def _percent_pieces(fmt: str, operands: list[ast.expr], domain: dict[str, str],
                    str_safe: bool = False) -> list[str] | None:
    """``str_safe``: every operand is formatted by ``%s`` exactly as ``str(operand)`` whatever its type."""
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
        if kind not in _SCALAR and not (conversion == "s" and str_safe) and not (fmt == "%s" and len(operands) == 1):
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
    re_modules = {alias.asname or alias.name for node in tree.body if isinstance(node, ast.Import)
                  for alias in node.names if alias.name == "re"}
    scopes: dict[int, tuple[dict[str, list[ast.expr]], set[str]]] = {}
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (_local_values(function), re_modules - _bound_names(function))
            pending = list(function.body)
            while pending:
                child = pending.pop()
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    scopes[id(child)] = scope
                    pending.extend(ast.iter_child_nodes(child))
    edits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
            continue
        domain = domains.get(node, {})
        # A tuple literal's elements, and a single exact str, are each formatted as str().
        # Tuple elements must be names or constants: evaluating them first, as % does, has no effect.
        if isinstance(node.right, ast.Tuple):
            operands = node.right.elts
            str_safe = all(isinstance(e, (ast.Name, ast.Constant)) for e in operands)
        elif _operand_kind(node.right, domain) in _SCALAR:
            operands, str_safe = [node.right], False
        elif _exact_str(node.right, *scopes.get(id(node), ({}, set()))):
            operands, str_safe = [node.right], True
        else:
            continue
        if any(isinstance(operand, ast.Starred) for operand in operands):
            continue
        pieces = _percent_pieces(node.left.value, operands, domain, str_safe)
        if pieces:
            # str() may return a str subclass with its own __add__; join copies characters, as % does.
            untyped = any(_operand_kind(operand, domain) not in _SCALAR for operand in operands)
            joined = '"".join([' + ", ".join(pieces) + "])" if untyped else " + ".join(pieces)
            replacement = "(" + joined + "\n" * (node.end_lineno - node.lineno) + ")"
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


# Dunders a statement can call without naming them stay; these two only print the object.
_DISPLAY = frozenset({"__repr__", "__str__"})


def _removable_method(node: ast.stmt, display: bool) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
        not (node.name.startswith("__") and node.name.endswith("__")) or (display and node.name in _DISPLAY))


def _defined_name(node: ast.stmt) -> str:
    return node.targets[0].id if isinstance(node, ast.Assign) else node.name


def _computed_class_value(node: ast.stmt) -> bool:
    """``pattern = re.compile(...)`` in a class body: ESBMC must type it even when nothing reads it."""
    return (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call))


def _unused_definitions(tree: ast.Module, keep: set[str], display: bool = True) -> list[ast.stmt]:
    """Top-level functions and classes, and methods (with ``display``, also computed class values),
    nothing still kept names, to a fixpoint."""
    candidates = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    candidates += [m for c in tree.body if isinstance(c, ast.ClassDef) for m in c.body
                   if _removable_method(m, display) or (display and _computed_class_value(m))]
    candidates = [n for n in candidates if _defined_name(n) not in keep]
    removed: set[int] = set()
    while True:
        loaded: set[str] = set()
        pending: list[ast.AST] = [tree]
        while pending:
            node = pending.pop()
            if id(node) in removed:
                continue
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                loaded.add(node.id)
            elif isinstance(node, ast.Attribute):
                loaded.add(node.attr)
            pending += list(ast.iter_child_nodes(node))
        dead = [n for n in candidates if id(n) not in removed and _defined_name(n) not in loaded]
        # A method named only by itself (recursion) is still loaded; that leaves it, which is safe.
        if not dead:
            return [n for n in candidates if id(n) in removed]
        removed |= {id(n) for n in dead}


def remove_unused(source: str, function: str, display: bool = True) -> tuple[str, list[str]]:
    """Definitions and methods nothing names leave as blank lines: they cannot run, and ESBMC still
    converts them and may refuse their code. ``display`` also drops ``__repr__``/``__str__``, which
    only printing calls: right for the ESBMC copy, not for the replay."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    keep = {function.split(".")[0], function.split(".")[-1], "_esbmc_main", "_esbmc_end_path",
            "_esbmc_none_attribute", "_esbmc_none_type"}
    removed = _unused_definitions(tree, keep, display)
    if not removed:
        return source, []
    lines = source.splitlines()
    for node in removed:
        start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
        for row in range(start - 1, node.end_lineno):
            lines[row] = ""
    # A class that stays but lost every statement still needs one.
    gone = {id(r) for r in removed}
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef) and id(n) not in gone):
        if all(id(m) in gone for m in cls.body):
            lines[cls.body[0].lineno - 1] = " " * cls.body[0].col_offset + "pass"
    return "\n".join(lines) + "\n", ["unused_definitions_removed:" + ",".join(sorted(_defined_name(n) for n in removed))]


def _enclosing_blocks(body: list[ast.stmt], line: int) -> list[tuple[list[ast.stmt], int]]:
    """(block, index) from the function body down to the innermost statement holding ``line``."""
    for index, stmt in enumerate(body):
        if stmt.lineno <= line <= stmt.end_lineno:
            blocks = [getattr(stmt, name, []) for name in ("body", "orelse", "finalbody")]
            blocks += [handler.body for handler in getattr(stmt, "handlers", [])]
            for block in blocks:
                inner = _enclosing_blocks(block, line)
                if inner:
                    return [(body, index), *inner]
            return [(body, index)]
    return []


def cut_after_suspect(source: str, function: str, spans: tuple[tuple[int, int], ...]) -> tuple[str, list[str]]:
    """In each block around the suspect, the statements after it run only once it has finished, so
    they cannot decide whether it raises this time: the path ends there. Inside a loop that keeps the
    first pass only, an under-approximation: what ESBMC still finds is real, and CPython replays it.
    Not for recursive functions (the cut would change the inner call) or generators."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    target = find_function(tree, function)
    if target is None or not spans:
        return source, []
    name = function.split(".")[-1]
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(target)) or any(
            isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == name
            for n in ast.walk(target)):
        return source, []
    # Falling off the function's end is cheapest to solve (an assume(False) there doubled a loop's
    # time on 8.5), unless a return is annotated (ESBMC flags it missing); deeper blocks need the cut.
    # A call, since __ESBMC_assume itself would be mangled inside a class body.
    returns = target.returns is not None and not (isinstance(target.returns, ast.Constant)
                                                   and target.returns.value is None)
    lines, cut, ended = source.splitlines(), 0, False
    for depth, (block, index) in enumerate(_enclosing_blocks(target.body, max(end for _, end in spans))):
        rest = block[index + 1:]
        if not rest:
            continue
        for row in range(rest[0].lineno - 1, rest[-1].end_lineno):
            lines[row] = ""
        end_path = depth > 0 or returns
        lines[rest[0].lineno - 1] = " " * rest[0].col_offset + ("_esbmc_end_path()" if end_path else "pass")
        cut, ended = cut + len(rest), ended or end_path
    if not cut:
        return source, []
    if ended and not any(isinstance(n, ast.FunctionDef) and n.name == "_esbmc_end_path" for n in tree.body):
        lines += ["", "", "def _esbmc_end_path() -> None:", "    __ESBMC_assume(False)"]
    return "\n".join(lines) + "\n", [f"cut_after_suspect:{cut}"]


# ESBMC master checks none of these on a None value (docs/projeto/possiveis_problemas); CPython raises.
# They return True so a guard can open an ``if`` test.
NONE_GUARDS = (
    "def _esbmc_none_attribute(value_is_none: bool) -> bool:",
    "    if value_is_none:",
    "        raise AttributeError(\"'NoneType' object has no attribute\")",
    "    return True",
    "",
    "",
    "def _esbmc_none_type(value_is_none: bool) -> bool:",
    "    if value_is_none:",
    "        raise TypeError(\"'NoneType' object does not support this operation\")",
    "    return True",
    "",
    "",
)
_TYPE_CALLS = frozenset({"len", "int", "float"})
_ORDERING = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ARITHMETIC = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow)


def _is_chain(node: ast.expr, names: set[str], receiver: str | None) -> bool:
    """A local or parameter, or an attribute chain on one; a method's receiver is never None."""
    depth = 0
    while isinstance(node, ast.Attribute):
        node, depth = node.value, depth + 1
    return isinstance(node, ast.Name) and node.id in names and (depth > 0 or node.id != receiver)


def _always_evaluated(root: ast.AST) -> list[ast.AST]:
    """Nodes ``root`` evaluates on every run: not the later operands of and/or, the branches of a
    conditional expression, later links of a comparison chain, lambdas or comprehensions."""
    found, pending = [], [root]
    while pending:
        node = pending.pop()
        found.append(node)
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(node, ast.BoolOp):
            pending.append(node.values[0])
        elif isinstance(node, ast.IfExp):
            pending.append(node.test)
        elif isinstance(node, ast.Compare):
            pending += [node.left, node.comparators[0]]
        else:
            pending += list(ast.iter_child_nodes(node))
    return found


def _guarded_values(evaluated: list[ast.AST], names: set[str], receiver: str | None) -> list[tuple[ast.expr, str]]:
    def _chain(node: ast.expr) -> bool:
        return _is_chain(node, names, receiver)

    found: list[tuple[ast.expr, str]] = []
    for node in evaluated:
        if isinstance(node, ast.Attribute) and _chain(node.value):
            found.append((node.value, "_esbmc_none_attribute"))
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and _chain(node.value):
            found.append((node.value, "_esbmc_none_type"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _TYPE_CALLS \
                and len(node.args) == 1 and _chain(node.args[0]):
            found.append((node.args[0], "_esbmc_none_type"))
        elif isinstance(node, ast.Compare):
            op, right = node.ops[0], node.comparators[0]
            if isinstance(op, (ast.In, ast.NotIn)) and _chain(right):
                found.append((right, "_esbmc_none_type"))
            elif isinstance(op, _ORDERING):
                found += [(side, "_esbmc_none_type") for side in (node.left, right) if _chain(side)]
        elif isinstance(node, ast.BinOp) and isinstance(node.op, _ARITHMETIC):
            found += [(side, "_esbmc_none_type") for side in (node.left, node.right) if _chain(side)]
    return found


def _innermost_statement(body: list[ast.stmt], line: int) -> ast.stmt | None:
    for stmt in body:
        if stmt.lineno <= line <= stmt.end_lineno:
            for block in ("body", "orelse", "finalbody"):
                inner = _innermost_statement(getattr(stmt, block, []), line)
                if inner is not None:
                    return inner
            for handler in getattr(stmt, "handlers", []):
                inner = _innermost_statement(handler.body, line)
                if inner is not None:
                    return inner
            return stmt
    return None


def _evaluated_part(stmt: ast.stmt, lines: list[str]) -> ast.AST | None:
    """What runs once, before anything else of ``stmt``: a simple statement, an ``if`` test (not an
    ``elif``, whose guard would land in the previous branch) or a ``for`` iterable."""
    if isinstance(stmt, ast.If):
        return None if lines[stmt.lineno - 1].lstrip().startswith("elif") else stmt.test
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return stmt.iter
    if isinstance(stmt, (ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef,
                         ast.ClassDef, ast.Match)):
        return None
    return stmt


def none_guards(source: str, function: str, spans: tuple[tuple[int, int], ...],
                never_none: frozenset[str] | set[str] = frozenset()) -> tuple[str, list[str]]:
    """Before the suspect statement, raise what CPython raises when a value it uses unconditionally is
    None: AttributeError for an attribute, TypeError for ``in``, indexing, ``len``/``int``/``float``,
    ordering and arithmetic. ``never_none`` names inputs (``x``, ``self.x``) whose type excludes None;
    on any other value that is never None a guard is a no-op."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    target = find_function(tree, function)
    if target is None or not spans:
        return source, []
    lines = source.splitlines()
    stmt = _innermost_statement(target.body, spans[0][0])
    part = _evaluated_part(stmt, lines) if stmt is not None else None
    if part is None or lines[stmt.lineno - 1][:stmt.col_offset].strip():
        return source, []
    args = target.args
    names = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    names |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    positional = [*args.posonlyargs, *args.args]
    in_class = any(isinstance(n, ast.ClassDef) and target in n.body for n in ast.walk(tree))
    static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in target.decorator_list)
    receiver = positional[0].arg if in_class and positional and not static else None
    values = sorted(_guarded_values(_always_evaluated(part), names, receiver),
                    key=lambda item: (item[0].lineno, item[0].col_offset, item[0].end_col_offset))
    calls: list[str] = []
    for value, helper in values:
        call = f"{helper}({ast.unparse(value)} is None)"
        if ast.unparse(value) not in never_none and call not in calls:
            calls.append(call)
    if not calls:
        return source, []
    # On the statement's own line, so the ESBMC copy keeps the replay's line numbers.
    if isinstance(stmt, ast.If):
        test, prefix = stmt.test, f"{' and '.join(calls)} and bool(".encode("utf-8")
        end = lines[test.end_lineno - 1].encode("utf-8")
        lines[test.end_lineno - 1] = (end[:test.end_col_offset] + b")" + end[test.end_col_offset:]).decode("utf-8")
        start = lines[test.lineno - 1].encode("utf-8")
        lines[test.lineno - 1] = (start[:test.col_offset] + prefix + start[test.col_offset:]).decode("utf-8")
    else:
        row = stmt.lineno - 1
        lines[row] = lines[row][:stmt.col_offset] + "; ".join(calls) + "; " + lines[row][stmt.col_offset:]
    return "\n".join(lines) + "\n", [f"none_guards:{len(calls)}"]


# Methods ESBMC dispatches by name to its list/dict/str model whatever the receiver's class
# (docs/projeto/possiveis_problemas/27_metodo_append_do_usuario.py; probed on master 2026-10-14:
# get, pop, copy, update, clear give "Dictionary variable not found", the others misbehave or hang).
_BUILTIN_METHOD_NAMES = frozenset({
    "get", "pop", "copy", "update", "clear", "setdefault", "popitem", "append", "remove", "insert",
    "extend", "index", "count", "sort", "reverse", "add", "discard", "split", "replace", "join",
    "find", "strip", "lstrip", "rstrip", "startswith", "endswith", "lower", "upper", "format",
    "encode", "decode",
})


def rename_builtin_named_methods(source: str, function: str) -> tuple[str, str, list[str]]:
    """Rename user methods named like a builtin container method (``get`` -> ``esbmc_get``) with
    every reference that surely reaches them: ``Class.m``, ``self.m``/``cls.m`` in the class or a
    subclass, the driver's receiver and variables annotated with the class. Returns the source, the target's new name and transforms."""
    tree = ast.parse(source)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    owned = {name: {m.name for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and m.name in _BUILTIN_METHOD_NAMES} for name, cls in classes.items()}
    changed = True
    while changed:  # a subclass reaches its bases' renamed methods through self
        changed = False
        for name, cls in classes.items():
            inherited = set().union(*(owned.get(b.id, set()) for b in cls.bases if isinstance(b, ast.Name)))
            if not inherited <= owned[name]:
                owned[name] |= inherited
                changed = True
    if not any(owned.values()):
        return source, function, []
    edits = []
    renamed: set[str] = set()

    def rename_attr(node: ast.Attribute) -> None:
        edits.append((node.end_lineno, node.end_col_offset - len(node.attr), node.end_col_offset))
        renamed.add(node.attr)

    for name, cls in classes.items():
        for method in (m for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if method.name in owned[name]:
                line = source.splitlines()[method.lineno - 1].encode("utf-8")
                start = line.index(f"def {method.name}".encode(), method.col_offset) + 4
                edits.append((method.lineno, start, start + len(method.name)))
            receivers = {"self", "cls", *(a.arg for a in method.args.args[:1])}
            for node in ast.walk(method):
                if (isinstance(node, ast.Attribute) and node.attr in owned[name] and isinstance(node.value, ast.Name)
                        and node.value.id in receivers):
                    rename_attr(node)
    # Variables annotated with one of the classes (``params: _Obj_params``, the driver's inputs).
    typed = {"_receiver": function.split(".")[0]} if "." in function else {}
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and isinstance(node.annotation, ast.Name) and node.annotation.id in classes:
            typed[node.arg] = node.annotation.id
        elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
              and isinstance(node.annotation, ast.Name) and node.annotation.id in classes):
            typed[node.target.id] = node.annotation.id
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)):
            continue
        owner = node.value.id if node.value.id in classes else typed.get(node.value.id)
        if owner in owned and node.attr in owned[owner]:
            rename_attr(node)
    lines = source.splitlines(keepends=True)
    for line, start, end in sorted(set(edits), reverse=True):
        raw = lines[line - 1].encode("utf-8")
        old = raw[start:end].decode("utf-8")
        lines[line - 1] = (raw[:start] + f"esbmc_{old}".encode("utf-8") + raw[end:]).decode("utf-8")
    parts = function.split(".")
    if len(parts) == 2 and parts[1] in owned.get(parts[0], set()):
        function = f"{parts[0]}.esbmc_{parts[1]}"
    names = sorted(renamed | {m for ms in owned.values() for m in ms})
    return "".join(lines), function, ["builtin_named_methods_renamed:" + ",".join(names)]
