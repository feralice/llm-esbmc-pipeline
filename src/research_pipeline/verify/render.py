"""Build the verification program from the verbatim slice and the input spec, without an LLM."""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, replace

from .astutil import expression_nodes, find_function, undefined_globals
from .compat import rewrite_compat
from .grounding import Grounded
from .slicing import END_PATH, KNOWN_MEMBERS, MEMBER_MODELS, CallShape
from .spec import (
    OBJECT,
    SCALARS,
    InputSpec,
    TypeShape,
    input_types,
    parse_type,
    resolved_types,
    spec_problems,
)

RECEIVER = "_receiver"
OPAQUE = "_Opaque"
DRIVER = "_esbmc_main"


class RenderError(ValueError):
    """The hypothesis cannot be turned into a program; the message says why."""


@dataclass(frozen=True)
class Program:
    source: str
    driver_start: int
    target_spans: tuple[tuple[int, int], ...]
    transforms: tuple[str, ...]
    target_range: tuple[int, int] = (0, 0)
    replay_source: str | None = None
    replay_target_spans: tuple[tuple[int, int], ...] | None = None
    replay_target_range: tuple[int, int] | None = None


def object_class(input_key: str) -> str:
    return "_Obj_" + input_key.replace(".", "_")


def _annotation(shape: TypeShape, obj_class: str | None = None) -> str:
    if shape.kind in ("list", "set", "frozenset"):
        base = f"{shape.kind}[{_annotation(shape.elem)}]"
    elif shape.kind == "dict":
        base = f"dict[{shape.key}, {_annotation(shape.elem)}]"
    elif shape.kind == "tuple":
        base = f"tuple[{', '.join(_annotation(item) for item in shape.items)}]"
    elif shape.kind == OBJECT:
        base = obj_class or OPAQUE
    else:
        base = shape.kind
    return f"Optional[{base}]" if shape.optional else base


def _simple(shape: TypeShape) -> bool:
    return (shape.kind in SCALARS or shape.kind in (OBJECT, "tuple")
            or (shape.kind == "list" and shape.elem.kind in SCALARS and not shape.elem.optional))


def _value(shape: TypeShape, obj_class: str | None) -> str:
    if shape.kind == "list":
        return f"nondet_list(3, elem_type=nondet_{shape.elem.kind}())"
    if shape.kind == OBJECT:
        return f"{obj_class or OPAQUE}()"
    if shape.kind == "tuple":
        return "(" + ", ".join(f"nondet_{item.kind}()" for item in shape.items) + ")"
    return f"nondet_{shape.kind}()"


class _Declarer:
    """Statements that give a target a nondet value of a type; containers hold at most two items."""

    def __init__(self) -> None:
        self.count = 0

    def fresh(self) -> str:
        self.count += 1
        return f"_v{self.count}"

    def declare(self, target: str, type_text: str, indent: str, obj_class: str | None = None) -> list[str]:
        shape = parse_type(type_text)
        assert shape is not None  # spec_problems already rejected unsupported types
        return self._shape(target, shape, indent, obj_class)

    def _shape(self, target: str, shape: TypeShape, indent: str, obj_class: str | None) -> list[str]:
        annotation = _annotation(shape, obj_class)
        inner = indent + "    "
        if shape.kind == "none":
            return [f"{indent}{target} = None"]
        if shape.optional:
            # A conditional expression here triggers an ESBMC 8.5 modelling artefact.
            base = replace(shape, optional=False)
            head = [f"{indent}{target}: {annotation} = None", f"{indent}if nondet_bool():"]
            if _simple(base):
                return [*head, f"{inner}{target} = {_value(base, obj_class)}"]
            temp = self.fresh()
            return [*head, *self._shape(temp, base, inner, obj_class), f"{inner}{target} = {temp}"]
        if _simple(shape):
            return [f"{indent}{target}: {annotation} = {_value(shape, obj_class)}"]
        if shape.kind == "bytes":
            return [f'{indent}{target}: bytes = b"ab"', f"{indent}if nondet_bool():", f'{inner}{target} = b""']
        if shape.kind == "frozenset":
            members = self.fresh()
            return [*self._shape(members, replace(shape, kind="set"), indent, None),
                    f"{indent}{target}: {annotation} = frozenset({members})"]
        empty = {"dict": "{}", "set": "set()"}.get(shape.kind, "[]")
        lines = [f"{indent}{target}: {annotation} = {empty}"]
        for _ in range(2):
            value = self.fresh()
            lines.append(f"{indent}if nondet_bool():")
            if shape.kind == "dict":
                key = self.fresh()
                lines += [f"{inner}{key}: {shape.key} = nondet_{shape.key}()",
                          *self._shape(value, shape.elem, inner, None), f"{inner}{target}[{key}] = {value}"]
            else:
                add = "add" if shape.kind == "set" else "append"
                lines += [*self._shape(value, shape.elem, inner, None), f"{inner}{target}.{add}({value})"]
        return lines


def _shell_init(attributes: dict[str, str], indent: str, decl: _Declarer) -> list[str]:
    body = indent * 2
    lines = [f"{indent}def __init__(self) -> None:"]
    for name, type_text in attributes.items():
        cls = object_class(f"self.{name}")
        lines += decl.declare(f"_attr_{name}", type_text, body, cls)
        shape = parse_type(type_text)
        # ESBMC resolves self.x's methods from this annotation, not from the local's.
        annotation = "" if shape is None or shape.kind == "none" else f": {_annotation(shape, cls)}"
        lines.append(f"{body}self.{name}{annotation} = _attr_{name}")
    if len(lines) == 1:
        lines.append(f"{body}pass")
    return lines


def _insert_shell(module: str, class_name: str, attributes: dict[str, str], decl: _Declarer) -> str:
    tree = ast.parse(module)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    first = cls.body[0]
    docstring = (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                 and isinstance(first.value.value, str))
    at = first.end_lineno if docstring else min([first.lineno, *(d.lineno for d in getattr(first, "decorator_list", []))]) - 1
    lines = module.splitlines()
    lines[at:at] = _shell_init(attributes, " " * first.col_offset, decl)
    return "\n".join(lines) + "\n"


def _stub_params(shape: CallShape) -> str:
    # Calls of one stub may pass fewer positionals than the longest: every parameter is optional.
    return ", ".join([*(f"a{i}=None" for i in range(shape.positional)), *(f"{k}=None" for k in shape.keywords)])


def _stub_function(name: str, shape: CallShape, type_text: str, decl: _Declarer, indent: str = "",
                   receiver: bool = False) -> list[str]:
    parsed = parse_type(type_text)
    returns = "None" if parsed is None or parsed.kind == "none" else _annotation(parsed)
    params = ", ".join(p for p in ("self" if receiver else "", _stub_params(shape)) if p)
    lines = [f"{indent}def {name}({params}) -> {returns}:"]
    if returns == "None":
        return [*lines, f"{indent}    return None"]
    return [*lines, *decl.declare("_stub_value", type_text, indent + "    "), f"{indent}    return _stub_value"]


def _object_classes(grounded: Grounded, inputs: dict[str, str], types: dict[str, str], decl: _Declarer) -> list[str]:
    """One class per input typed ``object``: its read fields are nondet, its called methods are stubs."""
    lines: list[str] = []
    for key, type_text in inputs.items():
        shape = parse_type(type_text)
        if shape is None or shape.kind != OBJECT:
            continue
        members = grounded.object_members.get(key, {})
        lines += [f"class {object_class(key)}:", "    def __init__(self) -> None:"]
        fields = [m for m, call in sorted(members.items()) if call is None]
        for member in fields:
            field_shape = parse_type(types[f"{key}.{member}"])
            lines += decl.declare(f"_field_{member}", types[f"{key}.{member}"], "        ")
            annotation = "" if field_shape.kind == "none" else f": {_annotation(field_shape)}"
            lines.append(f"        self.{member}{annotation} = _field_{member}")
        if not fields:
            lines.append("        pass")
        for member, call in sorted(members.items()):
            if call is not None:
                lines += ["", *_stub_function(member, call, types[f"{key}.{member}"], decl, "    ", receiver=True)]
        lines += ["", ""]
    return lines


def _stubs(grounded: Grounded, types: dict[str, str], decl: _Declarer) -> list[str]:
    plan = grounded.externals
    lines: list[str] = []
    for name in sorted(plan.exceptions):
        lines += [f"class {name}(Exception):", "    pass", "", ""]
    for name, origin in sorted(plan.models.items()):
        lines += [line.format(name=name) for line in MEMBER_MODELS[origin]] + ["", ""]
    for name in sorted(plan.classes - set(plan.namespaces)):
        lines.append(f"class {name}:")
        if name in plan.constructors:
            lines += [f"    def __init__({', '.join(['self', _stub_params(plan.constructors[name])]).rstrip(', ')}) -> None:",
                      "        pass", "", ""]
        else:
            lines += ["    pass", "", ""]
    for name in sorted(plan.constants):
        lines += [*decl.declare(name, types[name], ""), "", ""]
    for name, shape in sorted(plan.calls.items()):
        lines += [*_stub_function(name, shape, types[name], decl), "", ""]
    for namespace, attrs in sorted(plan.namespaces.items()):
        if any("_esbmc_end_path()" in line for attr in attrs for line in KNOWN_MEMBERS.get(namespace, {}).get(attr, ())):
            lines += END_PATH
        lines.append(f"class {namespace}:")
        if namespace in plan.constructors:
            lines += [f"    def __init__({', '.join(['self', _stub_params(plan.constructors[namespace])]).rstrip(', ')}) -> None:",
                      "        pass"]
        nested: dict[str, list[tuple[str, CallShape | None]]] = {}
        for attr, shape in sorted(attrs.items()):
            key = f"{namespace}.{attr}"
            if attr in KNOWN_MEMBERS.get(namespace, {}):
                lines += KNOWN_MEMBERS[namespace][attr]
            elif "." in attr:
                inner, leaf = attr.split(".", 1)
                nested.setdefault(inner, []).append((leaf, shape))
            elif shape is None:
                lines += decl.declare(attr, types[key], "    ")
            else:
                lines += ["    @staticmethod", *_stub_function(attr, shape, types[key], decl, "    ")]
        for inner, members in nested.items():
            lines.append(f"    class {inner}:")
            for leaf, shape in members:
                key = f"{namespace}.{inner}.{leaf}"
                if shape is None:
                    lines += decl.declare(leaf, types[key], "        ")
                else:
                    lines += ["        @staticmethod", *_stub_function(leaf, shape, types[key], decl, "        ")]
        lines += ["", ""]
    return lines


# src/python-frontend/models/exceptions.py, unchanged between ESBMC 8.5 and master (2026-10-01).
ESBMC_EXCEPTIONS = frozenset({
    "BaseException", "Exception", "KeyboardInterrupt", "ValueError", "TypeError", "AttributeError",
    "IndexError", "KeyError", "ZeroDivisionError", "AssertionError", "NameError", "OSError",
    "FileNotFoundError", "FileExistsError", "PermissionError", "StopIteration", "RuntimeError",
    "NotImplementedError", "EOFError", "ImportError", "ModuleNotFoundError",
})
_EXCEPTION_SUFFIXES = ("Error", "Exception", "Warning")


def _modeled_ancestor(cls: type) -> bool:
    """Would a stub for ``cls`` miss handlers? It would when a modeled exception derives from it."""
    return any(issubclass(getattr(builtins, name), cls) for name in ESBMC_EXCEPTIONS)


def _exception_stubs(body: str) -> list[str]:
    """Classes for exceptions the program names but ESBMC does not model: builtin ones keep
    CPython's hierarchy, unknown ``*Error`` names (``WindowsError`` off Windows) derive from Exception."""
    tree = ast.parse(body)
    bound = {n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    bound |= {t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
              for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)}
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - bound - ESBMC_EXCEPTIONS
    undefined = undefined_globals(body, "program.py")
    lines: list[str] = []
    emitted: set[str] = set()

    def emit(name: str, cls: type) -> bool:
        if name in emitted or name in ESBMC_EXCEPTIONS:
            return True
        if cls.__name__ != name:
            if cls.__name__ not in ESBMC_EXCEPTIONS:
                return False
            lines.extend([f"{name} = {cls.__name__}", "", ""])
        else:
            if _modeled_ancestor(cls):
                return False
            if len(cls.__bases__) != 1:
                return False
            base = cls.__bases__[0]
            if not emit(base.__name__, base):
                return False
            lines.extend([f"class {name}({base.__name__}):", "    pass", "", ""])
        emitted.add(name)
        return True

    for name in sorted(used):
        cls = getattr(builtins, name, None)
        if isinstance(cls, type) and issubclass(cls, BaseException):
            emit(name, cls)
        elif cls is None and name.endswith(_EXCEPTION_SUFFIXES) and name in undefined:
            lines.extend([f"class {name}(Exception):", "    pass", "", ""])
    return lines


def _binds_optional(module: str) -> bool:
    return any(isinstance(node, ast.ImportFrom) and node.module == "typing"
               and any((alias.asname or alias.name) == "Optional" for alias in node.names)
               for node in ast.walk(ast.parse(module)))


class _ToReceiver(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.copy_location(ast.Name(RECEIVER, node.ctx), node) if node.id == "self" else node


def _driver(grounded: Grounded, params: dict[str, str], assumptions: tuple[str, ...], decl: _Declarer) -> list[str]:
    lines = [f"def {DRIVER}() -> None:"]
    for name, type_text in params.items():
        lines += decl.declare(name, type_text, "    ", object_class(name))
    receiver = grounded.has_receiver
    if receiver:
        lines.append(f"    {RECEIVER} = {grounded.class_name}()")
    for assumption in assumptions:
        tree = _ToReceiver().visit(ast.parse(assumption.strip(), mode="eval"))
        lines.append(f"    __ESBMC_assume({ast.unparse(tree)})")
    keyword = {p.name for p in grounded.params if p.keyword}
    args = ", ".join(f"{name}={name}" if name in keyword else name for name in params)
    if receiver:
        lines.append(f"    {RECEIVER}.{grounded.method_name}({args})")
    elif grounded.entry == "constructor":
        lines.append(f"    {grounded.class_name}({args})")
    elif grounded.class_name:
        lines.append(f"    {grounded.class_name}.{grounded.method_name}({args})")
    else:
        lines.append(f"    {grounded.method_name}({args})")
    return lines


def render_program(grounded: Grounded, spec: InputSpec) -> Program:
    if grounded.unsupported:
        raise RenderError(grounded.unsupported)
    if not grounded.module:
        raise RenderError("the target and its dependencies cannot be sliced verbatim from the module")
    problems = spec_problems(spec, grounded)
    if problems:
        raise RenderError("; ".join(problems))
    params, attributes = resolved_types(spec, grounded)
    decl = _Declarer()

    module, transforms = grounded.module, list(grounded.transforms)
    if grounded.has_receiver:
        module = _insert_shell(module, grounded.class_name, attributes, decl)
    stubs = _stubs(grounded, spec.stubs, decl) + _object_classes(grounded, input_types(spec, grounded), spec.stubs, decl)
    driver = _driver(grounded, params, spec.assumptions, decl)
    if any(OPAQUE in line for line in [*stubs, *driver]) or OPAQUE in module:
        stubs = [f"class {OPAQUE}:", "    pass", "", "", *stubs]
        transforms.append("opaque_values")
    body = "\n".join(stubs) + module.rstrip("\n") + "\n\n\n" + "\n".join(driver) + f"\n\n\n{DRIVER}()\n"
    # CPython has these exceptions: the replay gets blank lines instead, so line numbers still match.
    exceptions = "\n".join(_exception_stubs(body))
    replay = "\n" * exceptions.count("\n") + body
    if exceptions:
        body = exceptions + body
        names = (line.removeprefix("class ").split("(")[0].split(" =")[0]
                 for line in exceptions.splitlines() if line and not line.startswith(" "))
        transforms.append("builtin_exceptions_stubbed:" + ",".join(names))
    if "Optional[" in body and not _binds_optional(body):
        body, replay = "from typing import Optional\n" + body, "from typing import Optional\n" + replay
        transforms.append("typing_import_added")

    lines = body.splitlines()
    driver_start = lines.index(f"def {DRIVER}() -> None:") + 1
    function = find_function(ast.parse(body), grounded.hypothesis.function)
    if function is None:
        raise RenderError("target function lost while building the program")
    shift = function.lineno - grounded.function_start
    spans = tuple((start + shift, end + shift) for start, end in grounded.spans)
    target_range = (function.lineno, function.end_lineno)
    rewritten, compat = rewrite_compat(body, parameter_types={grounded.hypothesis.function: params})
    rewritten_function = find_function(ast.parse(rewritten), grounded.hypothesis.function)
    nodes = expression_nodes(rewritten_function, grounded.hypothesis.suspect_expression)
    if nodes and grounded.hypothesis.line:
        nodes = [min(nodes, key=lambda node: abs(node.lineno - spans[0][0]))]
    rewritten_spans = tuple(sorted({(node.lineno, node.end_lineno) for node in nodes})) if nodes else spans
    return Program(rewritten, driver_start, rewritten_spans, (*transforms, *compat), target_range,
                   replay_source=replay, replay_target_spans=spans, replay_target_range=target_range)
