from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Finding
from .pipeline import build_analyzer
from .preprocess import preprocess_file


@dataclass
class EvalCounts:
    bug_tp: int = 0
    bug_fp: int = 0
    bug_fn: int = 0
    smell_tp: int = 0
    smell_fp: int = 0
    smell_fn: int = 0


def _match(generated: list[Finding], expected: list[dict]) -> tuple[int, int, int]:
    matched: set[int] = set()
    tp = fn = 0
    for exp in expected:
        idx = next(
            (i for i, g in enumerate(generated) if i not in matched and g.category == exp["category"]),
            None,
        )
        if idx is not None:
            matched.add(idx)
            tp += 1
        else:
            fn += 1
    fp = sum(1 for i in range(len(generated)) if i not in matched)
    return tp, fp, fn


def evaluate_file(
    file_path: Path,
    expected: list[dict],
    analyzer,
    verbose: bool = False,
) -> EvalCounts:
    if not file_path.exists():
        return EvalCounts(
            bug_fn=sum(1 for e in expected if e.get("verifiable") is True),
            smell_fn=sum(1 for e in expected if e.get("verifiable") is False),
        )

    units = preprocess_file(file_path)
    findings: list[Finding] = []
    for unit in units:
        findings.extend(analyzer.analyze(unit))

    bugs = [f for f in findings if f.verifiable]
    smells = [f for f in findings if not f.verifiable]
    exp_bugs = [e for e in expected if e.get("verifiable") is True]
    exp_smells = [e for e in expected if e.get("verifiable") is False]

    bug_tp, bug_fp, bug_fn = _match(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn = _match(smells, exp_smells)

    if verbose:
        _print_detail(file_path.name, bugs, exp_bugs, smells, exp_smells)

    return EvalCounts(
        bug_tp=bug_tp, bug_fp=bug_fp, bug_fn=bug_fn,
        smell_tp=smell_tp, smell_fp=smell_fp, smell_fn=smell_fn,
    )


def evaluate_model(
    ground_truth_path: Path,
    backend: str,
    model: str,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    ollama_base_url: str | None = None,
    verbose: bool = False,
) -> EvalCounts:
    labeled_dir = ground_truth_path.parent
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    analyzer = build_analyzer(
        backend=backend,
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        ollama_base_url=ollama_base_url,
    )
    total = EvalCounts()
    for filename, entry in ground_truth.items():
        c = evaluate_file(
            file_path=labeled_dir / filename,
            expected=entry.get("expected_findings", []),
            analyzer=analyzer,
            verbose=verbose,
        )
        total.bug_tp += c.bug_tp
        total.bug_fp += c.bug_fp
        total.bug_fn += c.bug_fn
        total.smell_tp += c.smell_tp
        total.smell_fp += c.smell_fp
        total.smell_fn += c.smell_fn
    return total


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def _print_detail(
    name: str,
    bugs: list[Finding],
    exp_bugs: list[dict],
    smells: list[Finding],
    exp_smells: list[dict],
) -> None:
    print(f"\nArquivo: {name}")
    _print_matches("bug", bugs, exp_bugs)
    _print_matches("smell", smells, exp_smells)


def _print_matches(label: str, generated: list[Finding], expected: list[dict]) -> None:
    if not expected and not generated:
        print(f"  {label}: nenhum esperado, nenhum gerado ✓")
        return
    matched: set[int] = set()
    for exp in expected:
        idx = next(
            (i for i, g in enumerate(generated) if i not in matched and g.category == exp["category"]),
            None,
        )
        cat = exp["category"]
        func = exp.get("function", "?")
        if idx is not None:
            matched.add(idx)
            print(f"  {label}: {cat} em {func} ✓")
        else:
            print(f"  {label}: {cat} em {func} ✗  [falso negativo]")
    for i, g in enumerate(generated):
        if i not in matched:
            print(f"  {label}: {g.category} (extra) ✗  [falso positivo]")
