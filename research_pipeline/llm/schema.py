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
                        "id":                   {"type": "string"},
                        "stage":                {"type": "string"},
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
                        "title":                {"type": "string"},
                        "explanation":          {"type": "string"},
                        "evidence":             {"type": "array", "items": {"type": "string"}},
                        "verifiable":           {"type": "boolean"},
                        "confidence":           {"type": "string"},
                        "expected_exception":   {"type": "string"},
                        "reproduction_harness": {"type": "string"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "expression":    {"type": "string"},
                                "line":          {"type": "integer"},
                                "relative_line": {"type": "integer"},
                            },
                            "required": ["expression", "line", "relative_line"],
                        },
                    },
                    "required": [
                        "id", "stage", "finding_type", "category", "title",
                        "explanation", "evidence", "verifiable", "confidence",
                        "expected_exception", "reproduction_harness", "metadata",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
    "strict": True,
}
