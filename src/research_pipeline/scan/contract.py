"""Structured harness contracts and deterministic scalar rendering.

The contract is the boundary between semantic reasoning and code generation.
LLM output may populate the contract later, but the rendered harness is always
validated and produced here from a small, explicit template.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


_SCALAR_TYPES = frozenset({"int", "float", "bool", "str"})


@dataclass(frozen=True)
class OperandSpec:
    name: str
    type: str
    source: str


@dataclass(frozen=True)
class ExpressionShape:
    names: tuple[str, ...]
    calls: tuple[str, ...]
    operators: tuple[str, ...]


@dataclass(frozen=True)
class HarnessContract:
    strategy: str
    category: str
    expression: str
    operands: dict[str, OperandSpec]
    preserve: tuple[str, ...]
    assumptions: tuple[str, ...]


def contract_from_dict(data: dict[str, Any]) -> HarnessContract:
    """Validate and normalize a contract received from a planner."""
    required = ("strategy", "category", "expression", "operands")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"contract missing field(s): {', '.join(missing)}")

    raw_operands = data["operands"]
    if not isinstance(raw_operands, dict) or not raw_operands:
        raise ValueError("contract operands must be a non-empty object")

    operands: dict[str, OperandSpec] = {}
    for name, raw in raw_operands.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            raise ValueError("each operand must be an object")
        operand_type = raw.get("type")
        if operand_type not in _SCALAR_TYPES:
            raise ValueError(f"unsupported operand type for {name!r}: {operand_type!r}")
        source = raw.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"operand {name!r} needs a source")
        operands[name] = OperandSpec(name, operand_type, source)

    expression = str(data["expression"]).strip()
    shape = inspect_expression(expression)
    if set(shape.names) != set(operands):
        raise ValueError(
            "contract operands do not match expression names: "
            f"expression={shape.names!r}, operands={tuple(operands)!r}"
        )

    return HarnessContract(
        strategy=str(data["strategy"]),
        category=str(data["category"]),
        expression=expression,
        operands=operands,
        preserve=tuple(str(value) for value in data.get("preserve", [])),
        assumptions=tuple(str(value) for value in data.get("assumptions", [])),
    )


def inspect_expression(expression: str) -> ExpressionShape:
    """Return the semantic pieces a renderer must preserve."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"expression does not parse: {exc.msg}") from exc

    names: list[str] = []
    calls: list[str] = []
    operators: list[str] = []
    operator_names = {ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%", ast.Add: "+",
                      ast.Sub: "-", ast.Mult: "*"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(node.func.id)
        elif isinstance(node, ast.Name) and node.id not in names:
            names.append(node.id)
        elif type(node) in operator_names:
            operators.append(operator_names[type(node)])
    call_names = set(calls)
    return ExpressionShape(
        tuple(name for name in names if name not in call_names),
        tuple(calls),
        tuple(operators),
    )


def render_scalar_harness(contract: HarnessContract) -> str:
    """Render the first safe scalar template: an explicit division check."""
    if contract.strategy != "scalar":
        raise ValueError("scalar renderer requires strategy='scalar'")
    if contract.category != "division_by_zero":
        raise ValueError("scalar division renderer requires division_by_zero category")

    shape = inspect_expression(contract.expression)
    if shape.operators != ("/",):
        raise ValueError("division renderer requires exactly one / operator")
    if any(call != "float" for call in shape.calls):
        raise ValueError("division renderer only supports float casts")
    if set(contract.preserve) != {"/", "float"}:
        raise ValueError("division contract must preserve / and float")

    expression_tree = ast.parse(contract.expression, mode="eval").body
    if not isinstance(expression_tree, ast.BinOp) or not isinstance(expression_tree.op, ast.Div):
        raise ValueError("division renderer requires a direct binary division")
    denominator = expression_tree.right
    if isinstance(denominator, ast.Call) and isinstance(denominator.func, ast.Name):
        if denominator.func.id != "float" or len(denominator.args) != 1:
            raise ValueError("division denominator must be a single float cast")
        denominator = denominator.args[0]
    if not isinstance(denominator, ast.Name) or denominator.id not in contract.operands:
        raise ValueError("division denominator must be one declared operand")

    lines = [
        "def scalar_model(" + ", ".join(
            f"{operand.name}: {operand.type}" for operand in contract.operands.values()
        ) + ") -> float:",
        "    return " + contract.expression,
        "",
        "def main() -> None:",
    ]
    for operand in contract.operands.values():
        lines.append(f"    {operand.name}: {operand.type} = nondet_{operand.type}()")
    for assumption in contract.assumptions:
        lines.append(f"    __ESBMC_assume({assumption})")
    for operand in contract.operands.values():
        if operand.type in {"int", "float"}:
            lines.append(f"    __ESBMC_assume(abs({operand.name}) <= 1000)")
        if operand.type == "float":
            lines.append(f"    __ESBMC_assume({operand.name} == {operand.name})")
    lines.extend(
        [
            f"    assert {denominator.id} != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'",
            "    scalar_model(" + ", ".join(contract.operands) + ")",
            "",
            "main()",
            "",
        ]
    )
    return "\n".join(lines)
