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

# These V2 categories are grounded by exact source-AST evidence before reaching
# ESBMC. The AST check does not classify the bug; it only verifies that the
# LLM-reported expression exists in executable source.
SOURCE_GROUNDED_CATEGORIES: frozenset[str] = frozenset(
    {
        "assertion_violation",
        "none_misuse",
        "type_mismatch",
        "invalid_precondition",
        "variable_misuse",
        "integer_overflow",
    }
)
