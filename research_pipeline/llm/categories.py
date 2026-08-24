from __future__ import annotations

FORMAL_CATEGORIES: frozenset[str] = frozenset(
    {
        "assertion_violation",
        "division_by_zero",
        "out_of_bounds",
        "none_misuse",
        "type_mismatch",
        "invalid_precondition",
        "variable_misuse",
        "integer_overflow",
    }
)
SMELL_CATEGORIES: frozenset[str] = frozenset(
    {"long_method", "many_parameters", "complex_conditional"}
)
SUPPORTED_CATEGORIES: frozenset[str] = FORMAL_CATEGORIES | SMELL_CATEGORIES

VERIFIABLE_OPERATION_KIND: dict[str, str] = {
    "division_by_zero": "division",
    "out_of_bounds": "subscript",
}

# These V2 categories describe semantic misuse rather than one unique AST node
# shape. They still require an exact source-AST match before reaching ESBMC.
SOURCE_GROUNDED_CATEGORIES: frozenset[str] = frozenset(
    {
        "none_misuse",
        "type_mismatch",
        "invalid_precondition",
        "variable_misuse",
        "integer_overflow",
    }
)
