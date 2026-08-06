from __future__ import annotations

FORMAL_CATEGORIES: frozenset[str] = frozenset(
    {"assertion_violation", "division_by_zero", "out_of_bounds"}
)
SMELL_CATEGORIES: frozenset[str] = frozenset(
    {"long_method", "many_parameters", "complex_conditional"}
)
SUPPORTED_CATEGORIES: frozenset[str] = FORMAL_CATEGORIES | SMELL_CATEGORIES

VERIFIABLE_OPERATION_KIND: dict[str, str] = {
    "division_by_zero": "division",
    "out_of_bounds": "subscript",
}
