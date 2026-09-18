from __future__ import annotations

from .categories import FORMAL_CATEGORIES, SMELL_CATEGORIES

# Single source of truth for the category enum: categories.py, system_prompt.txt,
# and this schema must agree on the same 11 names, or OpenAI's strict-mode
# schema silently rejects a category the prompt just asked the model to use.
# Deriving the enum here (instead of a fourth hardcoded copy) removes one of
# the three places that had to be kept in sync by hand.
_CATEGORY_ENUM: list[str] = sorted(FORMAL_CATEGORIES | SMELL_CATEGORIES)

FINDINGS_JSON_SCHEMA: dict = {
    "name": "pipeline_findings",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "finding_type": {
                            "type": "string",
                            "enum": [
                                "suspected_bug",
                                "smell_heuristic"
                            ],
                        },
                        "category": {
                            "type": "string",
                            "enum": _CATEGORY_ENUM,
                        },
                        "explanation": {"type": "string"},
                        "verifiable":  {"type": "boolean"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "expression": {"type": "string"},
                                "line": {"type": "integer"},
                                "operands": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "guard_evidence": {"type": "string"},
                                "missing_guard": {"type": "string"},
                                "context_needed": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            # OpenAI Structured Outputs strict mode requires
                            # every declared property to be required. Fields
                            # that are semantically optional must be emitted
                            # with an empty/default value instead of omitted.
                            "required": [
                                "expression", "line", "operands",
                                "guard_evidence", "missing_guard",
                                "context_needed",
                            ],
                        },
                    },
                    "required": [
                        "finding_type", "category", "explanation",
                        "verifiable", "metadata",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
    "strict": True,
}
