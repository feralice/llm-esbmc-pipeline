from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import CodeUnit
from .schema import FINDINGS_JSON_SCHEMA  # noqa: F401 — re-exported for backward compat

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def build_user_prompt(unit: CodeUnit) -> str:
    divisions  = [op for op in unit.operations if op.kind == "division"]
    subscripts = [op for op in unit.operations if op.kind == "subscript"]

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
        "Execute os 8 passos obrigatórios antes de gerar o JSON:\n"
        "1. Inventário de parâmetros (livres vs. derivados)\n"
        "2. Inventário de operações perigosas (divisões, subscripts, asserts)\n"
        "3. Mapeamento: qual parâmetro controla cada operação?\n"
        "4. Valor problemático: que valor concreto causa a falha?\n"
        "5. Fluxo de execução: existe caminho que leva esse valor até a operação?\n"
        "6. Guarda: ela bloqueia EXATAMENTE o valor problemático em TODOS os caminhos?\n"
        "7. Smells: long_method, many_parameters (>=5), complex_conditional?\n"
        "8. Veredicto: gere o JSON com findings.\n\n"
        "No campo `explanation` de cada finding, documente os resultados dos passos 3–7.\n"
        "Responda SOMENTE com JSON válido no schema solicitado."
    )


def _format_operations(operations: list) -> str:
    if not operations:
        return "  (nenhuma)"
    return "\n".join(
        f"  - linha relativa {op.relative_line}: {op.expression}"
        for op in operations
    )


def _format_guards(unit: CodeUnit) -> str:
    if not unit.guards:
        return "  (nenhuma guarda detectada)"
    return "\n".join(f"  - {guard}" for guard in unit.guards)


def _format_assertions(unit: CodeUnit) -> str:
    lines = []
    for offset, line in enumerate(unit.source.splitlines(), start=1):
        s = line.strip()
        if s.startswith("assert ") or "raise AssertionError" in s:
            lines.append(f"  - linha relativa {offset}: {s}")
    return "\n".join(lines) if lines else "  (nenhum)"


def _function_metadata(unit: CodeUnit) -> dict:
    return {
        "path":        str(unit.path),
        "start_line":  unit.start_line,
        "end_line":    unit.end_line,
        "parameters":  unit.parameters,
        "type_hints":  unit.type_hints,
        "metrics":     unit.metrics,
    }
