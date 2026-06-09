from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..models import CodeUnit
from .schema import FINDINGS_JSON_SCHEMA  # noqa: F401 - re-exported for backward compatibility

"""Prompt builders for the LLM analysis step.

The scientific/default mode is prompt_mode="raw": the LLM receives the function
source and minimal metadata, but not the file path and not pre-extracted AST
operations. This avoids leaking dataset labels such as division_by_zero through
paths or AST hints.

prompt_mode="ast_hints" is kept only for ablation experiments.
"""


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PromptMode = Literal["raw", "ast_hints"]

# Fixed reasoning checklist appended to both prompt modes. It asks the model to
# reason about dangerous operations and guards, but in raw mode the model must
# infer them from the source code itself.
_REASONING_STEPS = (
    "Aplique o raciocínio do system prompt (itens 1-4) para cada operação perigosa encontrada.\n"
    "Independentemente de haver bugs, avalie também se a função apresenta smells: "
    "long_method (função longa), many_parameters (>= 5 parâmetros), complex_conditional (condições compostas/aninhadas). "
    "Smells detectados devem entrar no array findings como finding_type='smell_heuristic', verifiable=false.\n"
    "Responda SOMENTE com JSON válido (use true/false minúsculos), sem markdown."
)


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Load the system prompt once and reuse it across LLM calls."""
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def build_user_prompt(unit: CodeUnit, prompt_mode: PromptMode = "raw") -> str:
    """Build the user-turn prompt for one CodeUnit.

    raw:
        Main evaluation mode. Sends function name, source code, parameters,
        type hints, line count and parameter count. It intentionally excludes
        file path, AST operation lists, guards and operation_count.

    ast_hints:
        Ablation mode. Sends pre-extracted divisions, subscripts, asserts,
        guards and full metrics. Do not use this for the main benchmark result.
    """
    if prompt_mode == "ast_hints":
        return _build_ast_hints_prompt(unit)
    return _build_raw_prompt(unit)


def _build_raw_prompt(unit: CodeUnit) -> str:
    """Build the leakage-resistant prompt used in main experiments."""
    return (
        f"Analise a função '{unit.qualname}' para o pipeline LLM + ESBMC.\n\n"
        "CÓDIGO DA FUNÇÃO:\n"
        f"```python\n{unit.source}\n```\n\n"
        "METADADOS DA FUNÇÃO:\n"
        f"{json.dumps(_function_metadata_raw(unit), ensure_ascii=False, indent=2)}\n\n"
        + _REASONING_STEPS
    )


def _build_ast_hints_prompt(unit: CodeUnit) -> str:
    """Build the ablation prompt that explicitly exposes AST-derived hints."""
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
        + _REASONING_STEPS
    )


def _format_operations(operations: list) -> str:
    """Format AST-extracted operations for the ast_hints ablation prompt."""
    if not operations:
        return "  (nenhuma)"
    return "\n".join(
        f"  - linha relativa {op.relative_line}: {op.expression}"
        for op in operations
    )


def _format_guards(unit: CodeUnit) -> str:
    """Format guards/asserts extracted during preprocessing."""
    if not unit.guards:
        return "  (nenhuma guarda detectada)"
    return "\n".join(f"  - {guard}" for guard in unit.guards)


def _format_assertions(unit: CodeUnit) -> str:
    """Find assertion-like lines directly in the function source for hints."""
    lines = []
    for offset, line in enumerate(unit.source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("assert ") or "raise AssertionError" in stripped:
            lines.append(f"  - linha relativa {offset}: {stripped}")
    return "\n".join(lines) if lines else "  (nenhum)"


def _function_metadata(unit: CodeUnit) -> dict:
    """Full metadata used only in ast_hints mode."""
    return {
        "start_line":  unit.start_line,
        "end_line":    unit.end_line,
        "parameters":  unit.parameters,
        "type_hints":  unit.type_hints,
        "metrics":     unit.metrics,
    }


def _function_metadata_raw(unit: CodeUnit) -> dict:
    """Minimal metadata for raw mode.

    Excludes:
    - path, because dataset folder names can reveal labels;
    - operation_count, because it reveals AST-derived operation information;
    - branch_count/loop_count, because raw should stay close to source-only.
    """
    return {
        "start_line":  unit.start_line,
        "end_line":    unit.end_line,
        "parameters":  unit.parameters,
        "type_hints":  unit.type_hints,
        "metrics": {
            "line_count":      unit.metrics.get("line_count", 0),
            "parameter_count": unit.metrics.get("parameter_count", 0),
        },
    }
