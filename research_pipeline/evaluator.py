from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .esbmc_runner import run_esbmc
from .formalizer import formalize_finding
from .instrumenter import instrument_unit
from .models import (
    ESBMCDirectResult,
    Finding,
)
from .pipeline import build_analyzer, run_esbmc_direct
from .preprocess import preprocess_file


@dataclass
class EvalCounts:
    # LLM vs. ground truth — global
    bug_tp: int = 0
    bug_fp: int = 0
    bug_fn: int = 0
    smell_tp: int = 0
    smell_fp: int = 0
    smell_fn: int = 0

    # LLM quality
    hallucination_count: int = 0   # findings where LLM claimed verifiable but AST rejected

    # ESBMC direct vs. ground truth (Flow A)
    esbmc_direct_tp: int = 0
    esbmc_direct_fp: int = 0
    esbmc_direct_fn: int = 0

    # Hybrid pipeline (LLM + ESBMC Flow B confirmed) vs. ground truth
    hybrid_bug_tp: int = 0
    hybrid_bug_fp: int = 0
    hybrid_bug_fn: int = 0

    # Combined pipeline outcomes (counts across all verifiable findings)
    llm_confirmed_by_esbmc: int = 0
    esbmc_native_bug: int = 0
    llm_missed_esbmc_bug: int = 0
    not_confirmed_within_bound: int = 0
    esbmc_inconclusive: int = 0
    skipped_not_verifiable: int = 0

    # Per-category breakdown: {category: {"tp": int, "fp": int, "fn": int}}
    per_category: dict = None

    def __post_init__(self):
        if self.per_category is None:
            self.per_category = {}

    def add_category_tp(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1

    def add_category_fp(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1

    def add_category_fn(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1

    def merge_category(self, other: "EvalCounts") -> None:
        for cat, counts in other.per_category.items():
            d = self.per_category.setdefault(cat, {"tp": 0, "fp": 0, "fn": 0})
            d["tp"] += counts["tp"]
            d["fp"] += counts["fp"]
            d["fn"] += counts["fn"]


def load_ground_truth_cases(ground_truth_path: Path) -> list[tuple[Path, list[dict]]]:
    """Load either the legacy ground_truth.json or the new per-category dataset JSONs."""
    ground_truth_path = ground_truth_path.resolve()
    if ground_truth_path.is_dir():
        return _load_cases_from_dir(ground_truth_path)

    payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "items" in payload:
        source_root = _infer_source_root_for_ground_truth_dir(ground_truth_path.parent)
        category = str(payload.get("category") or ground_truth_path.stem)
        return [
            (_source_path_for_item(source_root, category, item), [_expected_from_dataset_item(item)])
            for item in payload.get("items", [])
            if isinstance(item, dict) and item.get("file")
        ]

    labeled_dir = ground_truth_path.parent
    return [
        (labeled_dir / filename, entry.get("expected_findings", []))
        for filename, entry in payload.items()
    ]


def _load_cases_from_dir(directory: Path) -> list[tuple[Path, list[dict]]]:
    """Load dataset JSONs recursively from a ground_truths directory or category dir."""
    cases: list[tuple[Path, list[dict]]] = []
    for json_path in sorted(directory.rglob("*.json")):
        if "archive" in json_path.parts:
            continue
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "items" not in payload:
            continue
        source_root = _infer_source_root_for_ground_truth_dir(json_path.parent)
        category = str(payload.get("category") or json_path.stem)
        for item in payload.get("items", []):
            if not isinstance(item, dict) or not item.get("file"):
                continue
            cases.append((_source_path_for_item(source_root, category, item), [_expected_from_dataset_item(item)]))
    return cases


def _infer_source_root_for_ground_truth_dir(ground_truth_dir: Path) -> Path:
    # examples/labeled/ground_truths/bugs -> examples/labeled/ok/bugs
    if ground_truth_dir.parent.name == "ground_truths":
        return ground_truth_dir.parent.parent / "ok" / ground_truth_dir.name
    return ground_truth_dir.parent / "ok" / ground_truth_dir.name


def _source_path_for_item(source_root: Path, category: str, item: dict) -> Path:
    filename = str(item["file"])
    if category == "clean" or source_root.name == category:
        return source_root / filename
    return source_root / category / filename


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
    tp = fp = fn = 0
    for exp in expected:
        idx = _find_match(generated, exp, matched)
        if idx is not None:
            matched.add(idx)
            tp += 1
        else:
            fn += 1
    fp = sum(1 for i in range(len(generated)) if i not in matched)
    return tp, fp, fn


def _match_with_categories(
    generated: list[Finding],
    expected: list[dict],
) -> tuple[int, int, int, list[tuple[str, str]]]:
    """Match findings against expected entries by category and, when available, function name."""
    matched: set[int] = set()
    tp = fp = fn = 0
    verdicts: list[tuple[str, str]] = []
    for exp in expected:
        cat = exp["category"]
        idx = _find_match(generated, exp, matched)
        if idx is not None:
            matched.add(idx)
            tp += 1
            verdicts.append((cat, "tp"))
        else:
            fn += 1
            verdicts.append((cat, "fn"))
    for i, g in enumerate(generated):
        if i not in matched:
            fp += 1
            verdicts.append((g.category, "fp"))
    return tp, fp, fn, verdicts


def _find_match(
    generated: list[Finding],
    exp: dict,
    already_matched: set[int],
) -> int | None:
    """Return index of the best match for exp in generated, or None.

    Prefers category + function match; falls back to category-only when either
    side is missing function information.
    """
    cat = exp["category"]
    exp_func = exp.get("function", "")

    # First pass: require both category and function to match (strict)
    if exp_func:
        for i, g in enumerate(generated):
            if i in already_matched:
                continue
            g_func = g.metadata.get("function", "")
            if g.category == cat and g_func and g_func == exp_func:
                return i

    # Second pass: category-only (covers cases with missing function annotation)
    for i, g in enumerate(generated):
        if i in already_matched:
            continue
        if g.category == cat:
            return i

    return None


def evaluate_file(
    file_path: Path,
    expected: list[dict],
    analyzer,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    verbose: bool = False,
    output_dir: str | Path | None = None,
) -> EvalCounts:
    counts = EvalCounts()

    if not file_path.exists():
        counts.bug_fn   = sum(1 for e in expected if e.get("verifiable") is True)
        counts.smell_fn = sum(1 for e in expected if e.get("verifiable") is False and e.get("category") != "clean")
        counts.hybrid_bug_fn    = counts.bug_fn
        counts.esbmc_direct_fn  = counts.bug_fn
        return counts

    # ---- LLM evaluation ----
    units = preprocess_file(file_path)
    unit_findings: list[tuple] = []
    for unit in units:
        for finding in analyzer.analyze(unit):
            # Annotate function name for improved matching (MÉDIO 1)
            finding.metadata["function"] = unit.name
            unit_findings.append((unit, finding))

    bugs_with_units = [(u, f) for u, f in unit_findings if f.verifiable]
    bugs            = [f for _, f in bugs_with_units]
    smells          = [f for _, f in unit_findings if not f.verifiable and f.finding_type == "smell_heuristic"]
    hallucinations  = [f for _, f in unit_findings if f.finding_type == "llm_false_positive"]

    exp_bugs   = [e for e in expected if e.get("verifiable") is True]
    is_clean_case = bool(expected) and all(e.get("category") == "clean" for e in expected)
    # Clean files should produce zero findings; they are negative controls, not smells.
    exp_smells = [e for e in expected if e.get("verifiable") is False and e.get("category") != "clean"]

    bug_tp, bug_fp, bug_fn, bug_verdicts         = _match_with_categories(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn, smell_verdicts = _match_with_categories(smells, exp_smells)

    if is_clean_case:
        bug_tp = bug_fn = smell_tp = smell_fn = 0
        bug_fp = len(bugs) + len(hallucinations)
        smell_fp = len(smells)
        bug_verdicts = [(f.category, "fp") for f in bugs + hallucinations]
        smell_verdicts = [(f.category, "fp") for f in smells]

    counts.bug_tp   = bug_tp
    counts.bug_fp   = bug_fp
    counts.bug_fn   = bug_fn
    counts.smell_tp = smell_tp
    counts.smell_fp = smell_fp
    counts.smell_fn = smell_fn
    counts.hallucination_count   = len(hallucinations)
    counts.skipped_not_verifiable = len(smells)

    for cat, verdict in bug_verdicts + smell_verdicts:
        if verdict == "tp":
            counts.add_category_tp(cat)
        elif verdict == "fp":
            counts.add_category_fp(cat)
        elif verdict == "fn":
            counts.add_category_fn(cat)

    # ---- CRÍTICO 1: Flow B — ESBMC instrumented verification for verifiable bugs ----
    instrumented_dir = _resolve_instrumented_dir(output_dir, file_path)
    esbmc_confirmed_bugs: list[Finding] = []

    for unit, bug_finding in bugs_with_units:
        formal_property = formalize_finding(unit, bug_finding)
        if formal_property is None:
            counts.skipped_not_verifiable += 1
            continue
        instrumentation = instrument_unit(unit, formal_property, instrumented_dir)
        esbmc_result = run_esbmc(
            instrumentation,
            esbmc_command=esbmc_command,
            timeout_seconds=timeout_seconds,
        )
        if esbmc_result.status == "violation_found":
            esbmc_confirmed_bugs.append(bug_finding)
            counts.llm_confirmed_by_esbmc += 1
        elif esbmc_result.status == "no_violation_found":
            counts.not_confirmed_within_bound += 1
        else:
            counts.esbmc_inconclusive += 1

    hybrid_tp, hybrid_fp, hybrid_fn, _ = _match_with_categories(esbmc_confirmed_bugs, exp_bugs)
    counts.hybrid_bug_tp = hybrid_tp
    counts.hybrid_bug_fp = hybrid_fp
    counts.hybrid_bug_fn = hybrid_fn

    # ---- Flow A: ESBMC direct evaluation ----
    direct = run_esbmc_direct(
        file_path,
        esbmc_command=esbmc_command,
        bound=bound,
        timeout_seconds=timeout_seconds,
    )
    esbmc_found_bug  = direct.status == "violation_found"
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


def _resolve_instrumented_dir(output_dir: str | Path | None, file_path: Path) -> Path:
    if output_dir is not None:
        return Path(output_dir) / "instrumented_eval"
    return Path(__file__).resolve().parents[1] / "artifacts" / "benchmark_instrumented"


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
    output_dir: str | Path | None = None,
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
            output_dir=output_dir,
        )
        total.bug_tp   += c.bug_tp
        total.bug_fp   += c.bug_fp
        total.bug_fn   += c.bug_fn
        total.smell_tp += c.smell_tp
        total.smell_fp += c.smell_fp
        total.smell_fn += c.smell_fn
        total.hallucination_count      += c.hallucination_count
        total.esbmc_direct_tp          += c.esbmc_direct_tp
        total.esbmc_direct_fp          += c.esbmc_direct_fp
        total.esbmc_direct_fn          += c.esbmc_direct_fn
        total.hybrid_bug_tp            += c.hybrid_bug_tp
        total.hybrid_bug_fp            += c.hybrid_bug_fp
        total.hybrid_bug_fn            += c.hybrid_bug_fn
        total.llm_confirmed_by_esbmc   += c.llm_confirmed_by_esbmc
        total.not_confirmed_within_bound += c.not_confirmed_within_bound
        total.esbmc_inconclusive       += c.esbmc_inconclusive
        total.skipped_not_verifiable   += c.skipped_not_verifiable
        total.merge_category(c)

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
        idx = _find_match(generated, exp, matched)
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
