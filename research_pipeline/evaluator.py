from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import (
    CLASSIFICATION_ESBMC_INCONCLUSIVE,
    CLASSIFICATION_ESBMC_NATIVE_BUG,
    CLASSIFICATION_HEURISTIC_SMELL,
    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
    CLASSIFICATION_LLM_FALSE_POSITIVE,
    CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
    CLASSIFICATION_NOT_CONFIRMED,
    CLASSIFICATION_SKIPPED,
    ESBMCDirectResult,
    Finding,
)
from .pipeline import build_analyzer, run_esbmc_direct
from .preprocess import preprocess_file


@dataclass
class EvalCounts:
    # LLM vs. ground truth
    bug_tp: int = 0
    bug_fp: int = 0
    bug_fn: int = 0
    smell_tp: int = 0
    smell_fp: int = 0
    smell_fn: int = 0

    # LLM quality
    hallucination_count: int = 0   # findings where LLM claimed verifiable but AST rejected

    # ESBMC direct vs. ground truth
    esbmc_direct_tp: int = 0
    esbmc_direct_fp: int = 0
    esbmc_direct_fn: int = 0

    # Combined pipeline outcomes
    llm_confirmed_by_esbmc: int = 0
    esbmc_native_bug: int = 0
    llm_missed_esbmc_bug: int = 0
    not_confirmed_within_bound: int = 0
    esbmc_inconclusive: int = 0
    skipped_not_verifiable: int = 0


def load_ground_truth_cases(ground_truth_path: Path) -> list[tuple[Path, list[dict]]]:
    """Load either the legacy ground_truth.json or the new per-category dataset JSONs."""
    ground_truth_path = ground_truth_path.resolve()
    if ground_truth_path.is_dir():
        json_paths = sorted(ground_truth_path.glob("*.json"))
        source_root = _infer_source_root_for_ground_truth_dir(ground_truth_path)
        cases: list[tuple[Path, list[dict]]] = []
        for json_path in json_paths:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            category = str(payload.get("category") or json_path.stem)
            for item in payload.get("items", []):
                if not isinstance(item, dict) or not item.get("file"):
                    continue
                cases.append((source_root / category / str(item["file"]), [_expected_from_dataset_item(item)]))
        return cases

    payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "items" in payload:
        source_root = _infer_source_root_for_ground_truth_dir(ground_truth_path.parent)
        category = str(payload.get("category") or ground_truth_path.stem)
        return [
            (source_root / category / str(item["file"]), [_expected_from_dataset_item(item)])
            for item in payload.get("items", [])
            if isinstance(item, dict) and item.get("file")
        ]

    labeled_dir = ground_truth_path.parent
    return [
        (labeled_dir / filename, entry.get("expected_findings", []))
        for filename, entry in payload.items()
    ]


def _infer_source_root_for_ground_truth_dir(ground_truth_dir: Path) -> Path:
    # examples/labeled/ground_truths/bugs -> examples/labeled/ok/bugs
    if ground_truth_dir.parent.name == "ground_truths":
        return ground_truth_dir.parent.parent / "ok" / ground_truth_dir.name
    return ground_truth_dir.parent / "ok" / ground_truth_dir.name


def _expected_from_dataset_item(item: dict) -> dict:
    return {
        "function": item.get("function", ""),
        "category": item.get("expected_category", item.get("category", "")),
        "verifiable": bool(item.get("verifiable", False)),
        "expression": item.get("expression", ""),
        "line": item.get("line"),
        "id": item.get("id", ""),
        "expected_type": item.get("expected_type", ""),
        "should_go_to_esbmc": bool(item.get("should_go_to_esbmc", False)),
    }


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
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    verbose: bool = False,
) -> EvalCounts:
    counts = EvalCounts()

    if not file_path.exists():
        counts.bug_fn  = sum(1 for e in expected if e.get("verifiable") is True)
        counts.smell_fn = sum(1 for e in expected if e.get("verifiable") is False)
        counts.esbmc_direct_fn = counts.bug_fn
        return counts

    # ---- LLM evaluation ----
    units = preprocess_file(file_path)
    findings: list[Finding] = []
    for unit in units:
        findings.extend(analyzer.analyze(unit))

    bugs   = [f for f in findings if f.verifiable]
    smells = [f for f in findings if not f.verifiable and f.finding_type == "smell_heuristic"]
    hallucinations = [f for f in findings if f.finding_type == "llm_false_positive"]

    exp_bugs   = [e for e in expected if e.get("verifiable") is True]
    exp_smells = [e for e in expected if e.get("verifiable") is False]

    bug_tp, bug_fp, bug_fn       = _match(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn = _match(smells, exp_smells)

    counts.bug_tp   = bug_tp
    counts.bug_fp   = bug_fp
    counts.bug_fn   = bug_fn
    counts.smell_tp = smell_tp
    counts.smell_fp = smell_fp
    counts.smell_fn = smell_fn
    counts.hallucination_count = len(hallucinations)

    # ---- ESBMC direct evaluation ----
    direct = run_esbmc_direct(
        file_path,
        esbmc_command=esbmc_command,
        bound=bound,
        timeout_seconds=timeout_seconds,
    )
    esbmc_found_bug = direct.status == "violation_found"
    has_expected_bug = len(exp_bugs) > 0

    if esbmc_found_bug and has_expected_bug:
        counts.esbmc_direct_tp = 1
    elif esbmc_found_bug and not has_expected_bug:
        counts.esbmc_direct_fp = 1
    elif not esbmc_found_bug and has_expected_bug:
        if direct.status not in ("inconclusive", "tool_error", "skipped", "timeout", "unsupported_case", "no_vcc_generated"):
            counts.esbmc_direct_fn = 1

    if verbose:
        _print_detail(file_path.name, bugs, exp_bugs, smells, exp_smells, direct)

    return counts


def evaluate_model(
    ground_truth_path: Path,
    backend: str,
    model: str,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    ollama_base_url: str | None = None,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    verbose: bool = False,
) -> EvalCounts:
    cases = load_ground_truth_cases(ground_truth_path)
    analyzer = build_analyzer(
        backend=backend,
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        ollama_base_url=ollama_base_url,
    )

    total = EvalCounts()
    for file_path, expected in cases:
        c = evaluate_file(
            file_path=file_path,
            expected=expected,
            analyzer=analyzer,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            verbose=verbose,
        )
        total.bug_tp   += c.bug_tp
        total.bug_fp   += c.bug_fp
        total.bug_fn   += c.bug_fn
        total.smell_tp += c.smell_tp
        total.smell_fp += c.smell_fp
        total.smell_fn += c.smell_fn
        total.hallucination_count += c.hallucination_count
        total.esbmc_direct_tp += c.esbmc_direct_tp
        total.esbmc_direct_fp += c.esbmc_direct_fp
        total.esbmc_direct_fn += c.esbmc_direct_fn

    return total


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def hallucination_rate(counts: EvalCounts) -> float:
    total_verifiable_claims = counts.bug_tp + counts.bug_fp + counts.hallucination_count
    if total_verifiable_claims == 0:
        return 0.0
    return counts.hallucination_count / total_verifiable_claims


def _print_detail(
    name: str,
    bugs: list[Finding],
    exp_bugs: list[dict],
    smells: list[Finding],
    exp_smells: list[dict],
    direct: ESBMCDirectResult | None,
) -> None:
    print(f"\nArquivo: {name}")
    _print_matches("bug", bugs, exp_bugs)
    _print_matches("smell", smells, exp_smells)
    if direct:
        print(f"  ESBMC direto: {direct.status} — {direct.summary[:80]}")


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
        cat  = exp["category"]
        func = exp.get("function", "?")
        if idx is not None:
            matched.add(idx)
            print(f"  {label}: {cat} em {func} ✓")
        else:
            print(f"  {label}: {cat} em {func} ✗  [falso negativo]")
    for i, g in enumerate(generated):
        if i not in matched:
            print(f"  {label}: {g.category} (extra) ✗  [falso positivo]")
