from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

from .models import CodeUnit


THRESHOLDS_PATH = Path(__file__).resolve().parent / "config" / "smell_thresholds.json"


@lru_cache(maxsize=1)
def load_smell_thresholds() -> dict:
    """Load and minimally validate the versioned operational smell policy."""
    payload = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    required = {
        "long_method_min_executable_lines",
        "many_parameters_min",
        "complex_conditional_min_boolean_operators",
        "parameter_exclusions",
    }
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"smell threshold config is missing: {sorted(missing)}")
    for key in required - {"parameter_exclusions"}:
        if not isinstance(payload[key], int) or payload[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if not isinstance(payload["parameter_exclusions"], list):
        raise ValueError("parameter_exclusions must be a list")
    return payload


def smell_measurements(unit: CodeUnit) -> dict[str, int]:
    """Compute the three measurements used by the operational smell policy."""
    tree = ast.parse(unit.source)
    excluded = set(load_smell_thresholds()["parameter_exclusions"])
    parameters = sum(name not in excluded for name in unit.parameters)
    executable_lines = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and hasattr(node, "lineno")
    }
    max_boolean_operators = max(
        (_boolean_operator_count(node) for node in ast.walk(tree) if isinstance(node, ast.BoolOp)),
        default=0,
    )
    return {
        "executable_lines": len(executable_lines),
        "parameters": parameters,
        "max_boolean_operators": max_boolean_operators,
    }


def smells_from_policy(unit: CodeUnit) -> set[str]:
    """Return smells whose explicit thresholds are met by one code unit."""
    policy = load_smell_thresholds()
    measures = smell_measurements(unit)
    smells: set[str] = set()
    if measures["executable_lines"] >= policy["long_method_min_executable_lines"]:
        smells.add("long_method")
    if measures["parameters"] >= policy["many_parameters_min"]:
        smells.add("many_parameters")
    if (
        measures["max_boolean_operators"]
        >= policy["complex_conditional_min_boolean_operators"]
    ):
        smells.add("complex_conditional")
    return smells


def _boolean_operator_count(condition: ast.AST) -> int:
    return sum(
        len(candidate.values) - 1
        for candidate in ast.walk(condition)
        if isinstance(candidate, ast.BoolOp)
    )
