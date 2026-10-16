"""Real bugs shown as few-shot examples (variant A13): the most similar ones, never from the analysed bug's project."""

from __future__ import annotations

import ast
import json
import textwrap
import warnings
from dataclasses import dataclass
from pathlib import Path

from ..models import CodeUnit
from ..preprocess import preprocess_file
from ..v2_evaluator import should_reach_esbmc

MAX_EXAMPLE_SOURCE_CHARS = 2_500
MAX_EFFECT_CHARS = 200
_COMMON_NODES = {"Name", "Attribute", "Constant", "Call", "Expr", "Assign"}
_EFFECT = {
    "excecao_local": "levanta exceção dentro da função",
    "excecao_modelavel": "levanta exceção numa chamada cuja regra depende só dos argumentos",
    "excecao_nao_modelavel": "levanta exceção que depende do ambiente ou de biblioteca",
    "resultado_errado": "devolve valor errado; nada quebra",
}


@dataclass(frozen=True)
class Example:
    id: str
    project: str
    file_stem: str
    unit: CodeUnit
    expression: str
    crash_expressions: tuple[str, ...]
    verifiable: bool
    effect: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class ExamplePool:
    examples: tuple[Example, ...]
    # Every labelled bug, including those left out of ``examples``, so the project exclusion covers all of them.
    project_by_stem: dict[str, str]


def code_tokens(source: str) -> frozenset[str]:
    """Identifiers plus the less common AST node kinds: what two functions that do similar things share."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return frozenset()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        kind = type(node).__name__
        if isinstance(node, (ast.expr, ast.stmt, ast.operator, ast.cmpop)) and kind not in _COMMON_NODES:
            out.add(f"ast:{kind}")
    return frozenset(out)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _project(item: dict) -> str:
    return str(item.get("provenance", {}).get("project", "")).strip().lower()


def _unit_for(item: dict, sources_dir: Path) -> CodeUnit | None:
    path = sources_dir / item["file"]
    if not path.exists():
        return None
    units = {unit.qualname: unit for unit in preprocess_file(path)}
    names = [part.strip() for part in str(item.get("function", "")).split("/") if part.strip()]
    return next((units[name] for name in names if name in units), None)


def load_example_pool(ground_truth: Path, sources_dir: Path | None = None) -> ExamplePool:
    """Labelled bugs whose function is short enough to show; ``sources_dir`` defaults to ``funcao_com_bug`` beside it."""
    ground_truth = Path(ground_truth)
    items = json.loads(ground_truth.read_text(encoding="utf-8"))["items"]
    sources_dir = sources_dir or ground_truth.parent / "funcao_com_bug"
    examples = []
    for item in items:
        verifiable = should_reach_esbmc(item)
        if verifiable is None or not item.get("expression"):
            continue
        unit = _unit_for(item, sources_dir)
        if unit is None or len(unit.source) > MAX_EXAMPLE_SOURCE_CHARS:
            continue
        effect = str(item.get("failure_kind_note") or _EFFECT[item["failure_kind"]])[:MAX_EFFECT_CHARS]
        examples.append(Example(
            id=str(item["id"]), project=_project(item), file_stem=Path(item["file"]).stem, unit=unit,
            expression=str(item["expression"]), crash_expressions=tuple(item.get("crash_expressions", [])),
            verifiable=verifiable, effect=effect, tokens=code_tokens(unit.source)))
    project_by_stem = {Path(item["file"]).stem: _project(item) for item in items}
    return ExamplePool(tuple(sorted(examples, key=lambda e: e.id)), project_by_stem)


def select_examples(pool: ExamplePool, unit: CodeUnit, k: int) -> list[Example]:
    """The k most similar examples, never the analysed file's bug nor any bug of its project; ties by id."""
    stem = unit.path.stem
    project = pool.project_by_stem.get(stem)
    allowed = [e for e in pool.examples if e.file_stem != stem and (project is None or e.project != project)]
    target = code_tokens(unit.source)
    return sorted(allowed, key=lambda e: (-similarity(target, e.tokens), e.id))[:k]
