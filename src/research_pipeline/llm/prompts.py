from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

from ..models import CodeUnit
from ..smell_policy import load_smell_thresholds
from .schema import (
    FINDINGS_JSON_SCHEMA,  # noqa: F401 - re-exported for backward compatibility
)

"""Prompt builders for the LLM analysis step.

The LLM receives the function source and minimal metadata, but not the file path
or pre-extracted AST operations. This avoids leaking dataset labels such as
division_by_zero through paths or structural hints.
"""


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Fixed reasoning checklist appended to the prompt. The model must infer
# dangerous operations and guards from the source code itself.
def _reasoning_steps() -> str:
    policy = load_smell_thresholds()
    return (
        "Faça uma passagem completa e aplique o raciocínio do system prompt (itens 1-5) "
        "a cada operação perigosa encontrada. Retorne todas as causas raiz independentes "
        "com evidência concreta, sem quantidade fixa e sem duplicatas.\n"
        "Independentemente de haver bugs, aplique os limiares operacionais: "
        f"long_method (>={policy['long_method_min_executable_lines']} linhas executáveis), "
        f"many_parameters (>={policy['many_parameters_min']} parâmetros, excluindo self/cls), "
        "complex_conditional "
        f"(>={policy['complex_conditional_min_boolean_operators']} operadores and/or em uma condição). "
        "Smells detectados devem entrar no array findings como finding_type='smell_heuristic', verifiable=false.\n"
        "Responda SOMENTE com JSON válido (use true/false minúsculos), sem markdown."
    )


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Load the system prompt once and reuse it across LLM calls."""
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def build_user_prompt(unit: CodeUnit) -> str:
    """Build the leakage-resistant user prompt for one CodeUnit."""
    return (
        "Analise a função 'target_function' para o pipeline LLM + ESBMC.\n\n"
        "CÓDIGO DA FUNÇÃO:\n"
        f"```python\n{_source_for_llm(unit)}\n```\n\n"
        "METADADOS DA FUNÇÃO:\n"
        f"{json.dumps(_function_metadata_raw(unit), ensure_ascii=False, indent=2)}\n\n"
        + _reasoning_steps()
    )


def _function_metadata_raw(unit: CodeUnit) -> dict:
    """Minimal metadata for the LLM prompt.

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


def _source_for_llm(unit: CodeUnit) -> str:
    """Return a semantics-preserving, label-resistant copy for prompting.

    Comments and docstrings can describe the known bug in benchmark harnesses;
    the target function name may also contain labels such as ``buggy``. The AST
    used for grounding remains the original source. Only the prompt copy is
    sanitized.
    """
    try:
        tree = ast.parse(unit.source)
    except SyntaxError:
        return unit.source
    if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return unit.source
    function = tree.body[0]
    original_name = function.name
    function.name = "target_function"
    if function.body and isinstance(function.body[0], ast.Expr):
        value = function.body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            function.body.pop(0)
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id == original_name:
            node.id = "target_function"
    ast.fix_missing_locations(tree)
    return ast.unparse(function)
