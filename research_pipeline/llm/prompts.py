from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import CodeUnit

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

FINDINGS_JSON_SCHEMA = {
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
                        "id": {"type": "string"},
                        "stage": {"type": "string"},
                        "finding_type": {"type": "string"},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "explanation": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "verifiable": {"type": "boolean"},
                        "confidence": {"type": "string"},
                        "expected_exception": {"type": "string"},
                        "reproduction_harness": {"type": "string"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "expression": {"type": "string"},
                                "line": {"type": "string"},
                                "relative_line": {"type": "string"},
                            },
                            "required": ["expression", "line", "relative_line"],
                        },
                    },
                    "required": [
                        "id",
                        "stage",
                        "finding_type",
                        "category",
                        "title",
                        "explanation",
                        "evidence",
                        "verifiable",
                        "confidence",
                        "expected_exception",
                        "reproduction_harness",
                        "metadata",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
    "strict": True,
}


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def build_user_prompt(unit: CodeUnit) -> str:
    divisions = [operation for operation in unit.operations if operation.kind == "division"]
    subscripts = [operation for operation in unit.operations if operation.kind == "subscript"]

    return (
        f"Analise a função '{unit.qualname}' para o pipeline LLM + ESBMC.\n\n"
        "OPERAÇÕES DETECTADAS PELA ANÁLISE ESTÁTICA:\n"
        f"  Divisões/módulos (/, //, %):\n{_format_operations(divisions)}\n"
        f"  Acessos indexados (subscripts):\n{_format_operations(subscripts)}\n\n"
        f"  Asserts/AssertionError:\n{_format_assertions(unit)}\n\n"
        f"GUARDAS/ASSERTS EXISTENTES:\n{_format_guards(unit)}\n\n"
        "CÓDIGO DA FUNÇÃO:\n"
        f"```python\n{unit.source}\n```\n\n"
        "METADADOS DA FUNÇÃO:\n"
        f"{json.dumps(_function_metadata(unit), ensure_ascii=False, indent=2)}\n\n"
        "Instruções:\n"
        "1. Revise cada operação detectada para riscos de runtime "
        "(assertion_violation, division_by_zero, out_of_bounds).\n"
        "2. Se guardas existentes já protegem a operação, NÃO reporte como verifiable=true.\n"
        "3. Identifique smells de qualidade de código presentes.\n"
        "4. Para cada achado: explanation clara e evidence com trecho real do código.\n\n"
        "Responda SOMENTE com JSON válido no schema solicitado."
    )


def _format_operations(operations: list) -> str:
    if not operations:
        return "  (nenhuma)"
    return "\n".join(
        f"  - linha relativa {operation.relative_line}: {operation.expression}"
        for operation in operations
    )


def _format_guards(unit: CodeUnit) -> str:
    if not unit.guards:
        return "  (nenhuma guarda detectada)"
    return "\n".join(f"  - {guard}" for guard in unit.guards)


def _format_assertions(unit: CodeUnit) -> str:
    assertion_lines: list[str] = []
    for offset, line in enumerate(unit.source.splitlines(), start=1):
        stripped_line = line.strip()
        if stripped_line.startswith("assert ") or "raise AssertionError" in stripped_line:
            assertion_lines.append(f"  - linha relativa {offset}: {stripped_line}")
    return "\n".join(assertion_lines) if assertion_lines else "  (nenhum)"


def _function_metadata(unit: CodeUnit) -> dict:
    return {
        "path": str(unit.path),
        "start_line": unit.start_line,
        "end_line": unit.end_line,
        "parameters": unit.parameters,
        "type_hints": unit.type_hints,
        "metrics": unit.metrics,
    }
