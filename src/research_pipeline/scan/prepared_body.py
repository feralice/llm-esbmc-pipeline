"""Prepare a narrow real-body witness for nested-list division bugs."""

from __future__ import annotations

import ast
import copy


def _indexed_list(node: ast.expr | None, name: str, index: str) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == name
        and isinstance(node.slice, ast.Name)
        and node.slice.id == index
    )


def _len_argument(node: ast.expr) -> ast.expr | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "len" and len(node.args) == 1 and not node.keywords):
        return node.args[0]
    return None


def _division_denominator(expression: str) -> str | None:
    try:
        root = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(root, ast.BinOp) or not isinstance(root.op, ast.Div):
        return None
    denominator = root.right
    if isinstance(denominator, ast.Call) and isinstance(denominator.func, ast.Name):
        if denominator.func.id != "float" or len(denominator.args) != 1:
            return None
        denominator = denominator.args[0]
    return denominator.id if isinstance(denominator, ast.Name) else None


def _hoist_enumerate(body: list[ast.stmt], used: set[str]) -> None:
    result: list[ast.stmt] = []
    for statement in body:
        if isinstance(statement, ast.For):
            _hoist_enumerate(statement.body, used)
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (isinstance(call.func, ast.Name) and call.func.id == "min"
                    and len(call.args) == 1 and len(call.keywords) == 1
                    and call.keywords[0].arg == "key"
                    and isinstance(call.keywords[0].value, ast.Lambda)):
                enumeration = call.args[0]
                key = call.keywords[0].value.body
                if (isinstance(enumeration, ast.Call)
                        and isinstance(enumeration.func, ast.Name)
                        and enumeration.func.id == "enumerate"
                        and len(enumeration.args) == 1
                        and isinstance(enumeration.args[0], ast.Name)
                        and not enumeration.keywords
                        and not any(isinstance(n, (ast.Call, ast.Attribute))
                                    for n in ast.walk(key))):
                    name = "_esbmc_indexed"
                    while name in used:
                        name += "_"
                    used.add(name)
                    result.append(ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Call(func=ast.Name(id="list", ctx=ast.Load()),
                                       args=[copy.deepcopy(enumeration)], keywords=[]),
                    ))
                    call.args[0] = ast.Name(id=name, ctx=ast.Load())
        result.append(statement)
    body[:] = result


def prepare_real_body(source: str, function: str, expression: str) -> str | None:
    """Return a concrete driver for an empty inner list, when that path is explicit."""
    parts = function.split(".")
    if len(parts) != 2:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == parts[0]]
    if len(classes) != 1 or classes[0].bases or classes[0].keywords:
        return None
    cls = classes[0]
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)]
    targets = [node for node in methods if node.name == parts[1]]
    if len(targets) != 1 or any(node.name == "__init__" for node in methods):
        return None
    method = targets[0]
    if (method.decorator_list or method.args.vararg or method.args.kwarg
            or method.args.kwonlyargs or method.args.posonlyargs
            or len(method.args.args) != 3
            or method.args.args[0].arg != "self"
            or any(isinstance(node, ast.Attribute)
                   and isinstance(node.value, ast.Name) and node.value.id == "self"
                   for node in ast.walk(method))):
        return None
    local_lists = {
        target.id for statement in method.body
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.List)
        and not statement.value.elts
        for target in statement.targets if isinstance(target, ast.Name)
    }
    allowed_calls = {"len", "range", "float", "any", "enumerate", "min", "list"}
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name) and callee.id in allowed_calls:
            continue
        if (isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name)
                and ((callee.attr == "append" and callee.value.id in local_lists)
                     or callee.attr == "isdigit")):
            continue
        return None
    outer, inner = (arg.arg for arg in method.args.args[1:])
    denominator = _division_denominator(expression)
    if denominator is None:
        return None
    loops = [node for node in method.body if isinstance(node, ast.For)]
    if len(loops) != 1 or not isinstance(loops[0].target, ast.Name):
        return None
    loop = loops[0]
    index = loop.target.id
    range_call = loop.iter
    if (not isinstance(range_call, ast.Call)
            or not isinstance(range_call.func, ast.Name)
            or range_call.func.id != "range" or len(range_call.args) != 1
            or not isinstance(_len_argument(range_call.args[0]), ast.Name)
            or _len_argument(range_call.args[0]).id != outer):
        return None
    definitions = [node for node in loop.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == denominator
                   and _indexed_list(_len_argument(node.value), inner, index)]
    if len(definitions) != 1:
        return None
    try:
        suspect = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return None
    matches = [node for node in ast.walk(method)
               if isinstance(node, ast.BinOp) and ast.dump(node) == ast.dump(suspect)]
    if len(matches) != 1 or not any(
        node is matches[0] for node in ast.walk(loop)
    ):
        return None

    prepared = copy.deepcopy(cls)
    prepared.body = [copy.deepcopy(method)]
    target = prepared.body[0]
    uses_dictionary = any(isinstance(node, ast.Subscript)
                          and isinstance(node.slice, ast.Constant)
                          and isinstance(node.slice.value, str)
                          for node in ast.walk(target))
    uses_string = any(isinstance(node, ast.Attribute) and node.attr == "isdigit"
                      for node in ast.walk(target))
    outer_type = "list[list[dict[str, int]]]" if uses_dictionary else "list[list[int]]"
    inner_type = "list[list[str]]" if uses_string else "list[list[int]]"
    target.args.args[1].annotation = ast.parse(outer_type, mode="eval").body
    target.args.args[2].annotation = ast.parse(inner_type, mode="eval").body
    used = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
    _hoist_enumerate(target.body, used)
    prepared.decorator_list = []
    ast.fix_missing_locations(prepared)
    driver = (
        ast.unparse(prepared)
        + f"\n\ndef main() -> None:\n"
        + f"    {prepared.name}().{target.name}([[]], [[]])\n\nmain()\n"
    )
    return driver
