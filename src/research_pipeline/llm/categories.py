from __future__ import annotations

HARNESS_STRATEGIES: frozenset[str] = frozenset(
    {
        "native_runtime",
        "explicit_assertion",
        "differential_assertion",
        "unsupported",
    }
)

# Compatibility map for eight-category V2 checkpoints and oracle reports.
# New detector output must use HARNESS_STRATEGIES directly.
LEGACY_CATEGORY_TO_HARNESS_STRATEGY: dict[str, str] = {
    "division_by_zero": "native_runtime",
    "out_of_bounds": "native_runtime",
    "none_misuse": "native_runtime",
    "type_mismatch": "native_runtime",
    "integer_overflow": "native_runtime",
    "assertion_violation": "explicit_assertion",
    "invalid_precondition": "explicit_assertion",
    "variable_misuse": "explicit_assertion",
}


def harness_strategy_for_category(category: str) -> str:
    """Return a four-value strategy for a new or legacy category."""
    if category in HARNESS_STRATEGIES:
        return category
    return LEGACY_CATEGORY_TO_HARNESS_STRATEGY.get(category, "unsupported")

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
