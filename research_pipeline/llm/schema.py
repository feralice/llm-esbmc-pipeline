from __future__ import annotations

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
                            "enum": [
                                "assertion_violation",
                                "division_by_zero",
                                "out_of_bounds",
                                "long_method",
                                "many_parameters",
                                "complex_conditional",
                            ],
                        },
                        "explanation": {"type": "string"},
                        "verifiable":  {"type": "boolean"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "expression": {"type": "string"},
                            },
                            "required": ["expression"],
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
