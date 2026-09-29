"""The LLM's only output: input types and preconditions, never code."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field

from .grounding import Grounded

# The subset ESBMC-Python 8.5.0 converted in the 2026-09-29 probes.
SCALARS = ("int", "float", "bool", "str")
_LIST_NAMES = ("list", "List")
_DICT_NAMES = ("dict", "Dict")
_DICT_KEYS = ("str", "int")
_MAX_DEPTH = 3
# An object whose fields the grounding step found; each field is typed separately.
OBJECT = "object"


@dataclass(frozen=True)
class TypeShape:
    kind: str  # a scalar name, "bytes", "list", "dict", "tuple", "object" or "none"
    elem: TypeShape | None = None  # list element or dict value
    key: str | None = None  # dict key
    optional: bool = False
    items: tuple[TypeShape, ...] = ()  # tuple members, scalars only


@dataclass(frozen=True)
class InputSpec:
    params: dict[str, str]
    attributes: dict[str, str]
    assumptions: tuple[str, ...]
    # Return type of each stubbed library call, keyed "name" or "module.attr".
    stubs: dict[str, str] = field(default_factory=dict)


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _optional_inner(node: ast.expr) -> ast.expr | None:
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Optional":
        return node.slice
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        if _is_none(node.right):
            return node.left
        if _is_none(node.left):
            return node.right
    return None


def _shape(node: ast.expr, depth: int = 0) -> TypeShape | None:
    if depth > _MAX_DEPTH:
        return None
    inner = _optional_inner(node)
    if inner is not None:
        shape = _shape(inner, depth)
        if shape is None or shape.kind == "none" or shape.optional:
            return None
        return TypeShape(shape.kind, shape.elem, shape.key, optional=True, items=shape.items)
    if isinstance(node, ast.BinOp):
        return None
    if _is_none(node):
        return TypeShape("none")
    if isinstance(node, ast.Name) and node.id in (*SCALARS, "bytes"):
        return TypeShape(node.id)
    if isinstance(node, ast.Name) and node.id in (OBJECT, "Any"):
        # Top-level inputs with used members get a generated class; anywhere else it is an opaque value.
        return TypeShape(OBJECT)
    if not (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)):
        return None
    if node.value.id in ("tuple", "Tuple"):
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        items = tuple(_shape(item, depth + 1) for item in elts)
        if all(item is not None and item.kind in SCALARS for item in items):
            return TypeShape("tuple", items=items)
        return None
    if node.value.id in _LIST_NAMES:
        elem = _shape(node.slice, depth + 1)
        return TypeShape("list", elem) if elem is not None and elem.kind != "none" else None
    if (node.value.id in _DICT_NAMES and isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2
            and isinstance(node.slice.elts[0], ast.Name) and node.slice.elts[0].id in _DICT_KEYS):
        value = _shape(node.slice.elts[1], depth + 1)
        return TypeShape("dict", value, key=node.slice.elts[0].id) if value is not None else None
    return None


def parse_type(text: str) -> TypeShape | None:
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except SyntaxError:
        return None
    return _shape(node)


def parse_spec(text: str) -> InputSpec:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("spec must be a JSON object")
    params, attributes = data.get("params") or {}, data.get("attributes") or {}
    assumptions, stubs = data.get("assumptions") or [], data.get("stubs") or {}
    if not (isinstance(params, dict) and isinstance(attributes, dict) and isinstance(stubs, dict)
            and isinstance(assumptions, list)):
        raise ValueError("params/attributes/stubs must be objects and assumptions a list")
    return InputSpec(
        {str(k): str(v) for k, v in params.items()},
        {str(k): str(v) for k, v in attributes.items()},
        tuple(str(a) for a in assumptions),
        {str(k): str(v) for k, v in stubs.items()},
    )


def resolved_types(spec: InputSpec, grounded: Grounded) -> tuple[dict[str, str], dict[str, str]]:
    """Declared annotations win; the spec only fills what the source leaves open."""
    params = {}
    for param in grounded.params:
        declared = param.annotation if param.annotation and parse_type(param.annotation) else None
        params[param.name] = declared or spec.params.get(param.name, "")
    attributes = {}
    for attr in grounded.receiver_attrs:
        declared = grounded.attr_annotations.get(attr)
        attributes[attr] = declared if declared and parse_type(declared) else spec.attributes.get(attr, "")
    return params, attributes


def input_types(spec: InputSpec, grounded: Grounded) -> dict[str, str]:
    """Every harness input keyed as the prompt names it: ``param`` or ``self.attr``."""
    params, attributes = resolved_types(spec, grounded)
    return {**params, **{f"self.{name}": text for name, text in attributes.items()}}


def _object_keys(spec: InputSpec, grounded: Grounded) -> list[str]:
    keys = []
    for key, text in input_types(spec, grounded).items():
        shape = parse_type(text) if text else None
        if shape is not None and shape.kind == OBJECT:
            keys += [f"{key}.{member}" for member in sorted(grounded.object_members.get(key, {}))]
    return keys


_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.Compare,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.BinOp, ast.Add,
    ast.Sub, ast.Mult, ast.Constant, ast.Name, ast.Load, ast.Attribute, ast.Call,
)


def _assumption_problem(text: str, params: set[str], attrs: set[str], receiver: bool) -> str:
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        return f"assumption {text!r} is not a Python expression"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"assumption {text!r} uses {type(node).__name__}"
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1):
            return f"assumption {text!r} may only call len()"
        if isinstance(node, ast.Attribute) and not (
                isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in attrs):
            return f"assumption {text!r} reads an attribute that is not an input"
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - {"len"} - ({"self"} if receiver else set())
    unknown = names - params
    if unknown:
        return f"assumption {text!r} uses unknown name(s) {', '.join(sorted(unknown))}"
    return ""


def spec_problems(spec: InputSpec, grounded: Grounded) -> list[str]:
    problems: list[str] = []
    params, attributes = resolved_types(spec, grounded)
    for kind, types in (("parameter", params), ("attribute", attributes)):
        for name, text in types.items():
            if not text:
                problems.append(f"{kind} {name!r}: missing type")
            elif parse_type(text) is None:
                problems.append(f"{kind} {name!r}: unsupported type {text!r}")
    problems += [f"unknown parameter {name!r}" for name in spec.params if name not in params]
    problems += [f"unknown attribute {name!r}" for name in spec.attributes if name not in attributes]
    object_keys = _object_keys(spec, grounded)
    for key in [*grounded.stub_keys, *object_keys]:
        text = spec.stubs.get(key, "")
        shape = parse_type(text) if text else None
        if not text:
            problems.append(f"stub {key!r}: missing return type")
        elif shape is None:
            problems.append(f"stub {key!r}: unsupported type {text!r}")
    problems += [f"unknown stub {key!r}" for key in spec.stubs if key not in {*grounded.stub_keys, *object_keys}]
    for assumption in spec.assumptions:
        problem = _assumption_problem(assumption, set(params), set(attributes), grounded.has_receiver)
        if problem:
            problems.append(problem)
    return problems
