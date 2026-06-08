from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .llm.backends.factory import build_analyzer
from .llm.prompts import PromptMode
from .models import (
    ESBMCDirectResult,
    Finding,
)
from .preprocess import preprocess_file
from .report import _category_from_esbmc_property, _esbmc_result_matches_category
from .verification.esbmc_runner import run_esbmc_function_baseline, run_esbmc_on_function


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
    out_of_scope_count: int = 0    # findings whose category is outside the benchmark scope

    # Flow A (ESBMC-only --function) vs. ground truth
    esbmc_direct_tp: int = 0
    esbmc_direct_fp: int = 0
    esbmc_direct_fn: int = 0

    # Hybrid pipeline (LLM + ESBMC Flow B confirmed) vs. ground truth
    hybrid_bug_tp: int = 0
    hybrid_bug_fp: int = 0
    hybrid_bug_fn: int = 0

    # Ghost bugs (suspected_bug + verifiable=False) — excluded from hallucination_rate denominator.
    ghost_bug_count: int = 0

    # Function-level binary bug classification for MCC/accuracy.
    # Unit: one function = one vote. Only formal bug and clean cases participate;
    # smell cases are evaluated separately and excluded from bug MCC.
    bug_func_tp: int = 0
    bug_func_fp: int = 0
    bug_func_fn: int = 0
    bug_func_tn: int = 0
    hybrid_bug_func_tp: int = 0
    hybrid_bug_func_fp: int = 0
    hybrid_bug_func_fn: int = 0
    hybrid_bug_func_tn: int = 0
    esbmc_direct_func_tp: int = 0
    esbmc_direct_func_fp: int = 0
    esbmc_direct_func_fn: int = 0
    esbmc_direct_func_tn: int = 0

    # Combined pipeline outcomes (counts across all verifiable findings)
    llm_confirmed_by_esbmc: int = 0
    esbmc_native_bug: int = 0
    llm_missed_esbmc_bug: int = 0
    not_confirmed_within_bound: int = 0
    esbmc_inconclusive: int = 0
    skipped_not_verifiable: int = 0

    # Per-category breakdown: {category: {"tp": int, "fp": int, "fn": int}}
    # per_category = LLM-only (Flow C) verdicts
    # per_category_hybrid = hybrid pipeline (Flow B) verdicts
    per_category: dict = None
    per_category_hybrid: dict = None

    def __post_init__(self):
        if self.per_category is None:
            self.per_category = {}
        if self.per_category_hybrid is None:
            self.per_category_hybrid = {}

    def add_category_tp(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1

    def add_category_fp(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1

    def add_category_fn(self, category: str) -> None:
        self.per_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1

    def add_hybrid_category_tp(self, category: str) -> None:
        self.per_category_hybrid.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1

    def add_hybrid_category_fp(self, category: str) -> None:
        self.per_category_hybrid.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1

    def add_hybrid_category_fn(self, category: str) -> None:
        self.per_category_hybrid.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1

    def merge_category(self, other: "EvalCounts") -> None:
        for cat, counts in other.per_category.items():
            d = self.per_category.setdefault(cat, {"tp": 0, "fp": 0, "fn": 0})
            d["tp"] += counts["tp"]
            d["fp"] += counts["fp"]
            d["fn"] += counts["fn"]

    def merge_category_hybrid(self, other: "EvalCounts") -> None:
        for cat, counts in other.per_category_hybrid.items():
            d = self.per_category_hybrid.setdefault(cat, {"tp": 0, "fp": 0, "fn": 0})
            d["tp"] += counts["tp"]
            d["fp"] += counts["fp"]
            d["fn"] += counts["fn"]


def load_ground_truth_cases(ground_truth_path: Path) -> list[tuple[Path, list[dict]]]:
    """Load either the legacy ground_truth.json or the new per-category dataset JSONs."""
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
    # dataset/labeled/ground_truths/bugs -> dataset/labeled/ok/bugs
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
    """Return index of the match for exp in generated, or None.

    Fix 2: strict category + function match only. Both sides always carry
    function info, so category-only fallback would silently reward wrong-function
    localization as a true positive.
    """
    cat = exp["category"]
    exp_func = exp.get("function", "")
    for i, g in enumerate(generated):
        if i in already_matched:
            continue
        g_func = g.metadata.get("function", "")
        if g.category == cat and g_func == exp_func:
            return i
    return None


def _count_llm_missed_flow_a_findings(flow_a_findings: list[Finding], llm_bugs: list[Finding]) -> int:
    """Count Flow A findings not covered by any LLM verifiable finding."""
    matched_llm: set[int] = set()
    missed = 0
    for flow_a_finding in flow_a_findings:
        idx = _find_match(
            llm_bugs,
            {
                "category": flow_a_finding.category,
                "function": flow_a_finding.metadata.get("function", ""),
            },
            matched_llm,
        )
        if idx is None:
            missed += 1
        else:
            matched_llm.add(idx)
    return missed


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
        if counts.bug_fn:
            counts.bug_func_fn = 1
            counts.hybrid_bug_func_fn = 1
            counts.esbmc_direct_func_fn = 1
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
    out_of_scope    = [f for _, f in unit_findings if f.finding_type == "out_of_scope_finding"]
    # Fix 5: suspected_bug + verifiable=False = ghost finding — treat as FP.
    ghost_bugs      = [f for _, f in unit_findings if f.finding_type == "suspected_bug" and not f.verifiable]

    exp_bugs   = [e for e in expected if e.get("verifiable") is True]
    is_clean_case = bool(expected) and all(e.get("category") == "clean" for e in expected)
    exp_smells = [e for e in expected if e.get("verifiable") is False and e.get("category") != "clean"]

    bug_tp, bug_fp, bug_fn, bug_verdicts         = _match_with_categories(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn, smell_verdicts = _match_with_categories(smells, exp_smells)

    if is_clean_case:
        bug_tp = bug_fn = smell_tp = smell_fn = 0
        bug_fp = len(bugs) + len(hallucinations) + len(ghost_bugs)
        smell_fp = len(smells)
        bug_verdicts = [(f.category, "fp") for f in bugs + hallucinations + ghost_bugs]
        smell_verdicts = [(f.category, "fp") for f in smells]
    else:
        bug_fp += len(hallucinations) + len(ghost_bugs)
        bug_verdicts.extend((f.category, "fp") for f in hallucinations + ghost_bugs)

    counts.bug_tp   = bug_tp
    counts.bug_fp   = bug_fp
    counts.bug_fn   = bug_fn
    counts.smell_tp = smell_tp
    counts.smell_fp = smell_fp
    counts.smell_fn = smell_fn
    counts.hallucination_count    = len(hallucinations)
    counts.out_of_scope_count     = len(out_of_scope)
    counts.ghost_bug_count        = len(ghost_bugs)
    counts.skipped_not_verifiable = 0
    if exp_bugs:
        if bug_tp > 0:
            counts.bug_func_tp = 1
        else:
            counts.bug_func_fn = 1
    elif is_clean_case:
        if bug_fp > 0:
            counts.bug_func_fp = 1
        else:
            counts.bug_func_tn = 1

    for cat, verdict in bug_verdicts + smell_verdicts:
        if verdict == "tp":
            counts.add_category_tp(cat)
        elif verdict == "fp":
            counts.add_category_fp(cat)
        elif verdict == "fn":
            counts.add_category_fn(cat)

    # ---- Flow B — ESBMC with --function (symbolic entry point) ----
    esbmc_confirmed_bugs: list[Finding] = []
    # Track all inconclusive findings for per-function FP accounting (Fix 8/9 unified).
    inconclusive_findings: list[Finding] = []

    num_hypotheses = len(bugs_with_units)
    for j, (unit, bug_finding) in enumerate(bugs_with_units, 1):
        print(f"    - Validando hipótese {j}/{num_hypotheses}: {bug_finding.category} em {unit.name}...")
        esbmc_result = run_esbmc_on_function(
            file_path=file_path,
            function_name=unit.name,
            finding_id=bug_finding.id,
            category=bug_finding.category,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
        )
        if esbmc_result.status == "violation_found" and _esbmc_result_matches_category(esbmc_result.details, bug_finding.category):
            esbmc_confirmed_bugs.append(bug_finding)
            counts.llm_confirmed_by_esbmc += 1
        elif esbmc_result.status == "violation_found":
            counts.esbmc_inconclusive += 1
            inconclusive_findings.append(bug_finding)
        elif esbmc_result.status == "no_violation_found":
            counts.not_confirmed_within_bound += 1
        elif esbmc_result.status == "skipped":
            counts.skipped_not_verifiable += 1
        else:  # timeout, tool_error, inconclusive
            counts.esbmc_inconclusive += 1
            inconclusive_findings.append(bug_finding)

    # Use FULL exp_bugs — no dynamic exclusion.
    # Timeout on a real bug = FN (the pipeline failed to prove it). This is honest.
    hybrid_tp, hybrid_fp, hybrid_fn, hybrid_verdicts = _match_with_categories(
        esbmc_confirmed_bugs, exp_bugs
    )
    # Inconclusive LLM-proposed bugs that have NO matching expected (function, category) are FPs:
    # the LLM pointed at a clean function, ESBMC couldn't even disprove it — LLM noise.
    exp_bug_signatures = {(e.get("function", ""), e.get("category", "")) for e in exp_bugs}
    for f in inconclusive_findings:
        sig = (f.metadata.get("function", ""), f.category)
        if sig not in exp_bug_signatures:
            hybrid_fp += 1
            counts.add_hybrid_category_fp(f.category)

    counts.hybrid_bug_tp = hybrid_tp
    counts.hybrid_bug_fp = hybrid_fp
    counts.hybrid_bug_fn = hybrid_fn
    if exp_bugs:
        if hybrid_tp > 0:
            counts.hybrid_bug_func_tp = 1
        else:
            counts.hybrid_bug_func_fn = 1
    elif is_clean_case:
        if hybrid_fp > 0:
            counts.hybrid_bug_func_fp = 1
        else:
            counts.hybrid_bug_func_tn = 1

    # Fix 4: per_category_hybrid tracks hybrid (Flow B) verdicts, not LLM-only.
    for cat, verdict in hybrid_verdicts:
        if verdict == "tp":
            counts.add_hybrid_category_tp(cat)
        elif verdict == "fp":
            counts.add_hybrid_category_fp(cat)
        elif verdict == "fn":
            counts.add_hybrid_category_fn(cat)

    # ---- Flow A: ESBMC-only function baseline ----
    print(f"    - Executando baseline ESBMC (Flow A)...")
    direct = run_esbmc_function_baseline(
        file_path=file_path,
        function_names=[unit.name for unit in units],
        esbmc_command=esbmc_command,
        bound=bound,
        timeout_seconds=timeout_seconds,
        output_dir=output_dir,
    )
    flow_a_findings = _flow_a_findings_from_direct(direct)
    # Fix 3: always run matching for Flow A (symmetric with Flow B).
    # Timeout/error → empty flow_a_findings → FN for expected bugs, just like Flow B.
    a_tp, a_fp, a_fn, _ = _match_with_categories(flow_a_findings, exp_bugs)
    counts.esbmc_direct_tp = a_tp
    counts.esbmc_direct_fp = a_fp
    counts.esbmc_direct_fn = a_fn
    if exp_bugs:
        if a_tp > 0:
            counts.esbmc_direct_func_tp = 1
        else:
            counts.esbmc_direct_func_fn = 1
    elif is_clean_case:
        if a_fp > 0:
            counts.esbmc_direct_func_fp = 1
        else:
            counts.esbmc_direct_func_tn = 1

    if flow_a_findings:
        counts.esbmc_native_bug = len(flow_a_findings)
        counts.llm_missed_esbmc_bug = _count_llm_missed_flow_a_findings(flow_a_findings, bugs)

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
    llm_timeout_seconds: int = 300,
    verbose: bool = False,
    output_dir: str | Path | None = None,
    prompt_mode: PromptMode = "raw",
    n_bootstrap: int = 2000,
) -> tuple[EvalCounts, dict[str, tuple[float, float]]]:
    cases = load_ground_truth_cases(ground_truth_path)
    analyzer = build_analyzer(
        backend=backend,
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        ollama_base_url=ollama_base_url,
        timeout_seconds=llm_timeout_seconds,
        prompt_mode=prompt_mode,
    )

    total = EvalCounts()
    case_list: list[EvalCounts] = []
    num_cases = len(cases)
    for i, (file_path, expected) in enumerate(cases, 1):
        print(f"[{i}/{num_cases}] Processando {file_path.name}...")
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
        case_list.append(c)
        total.bug_tp   += c.bug_tp
        total.bug_fp   += c.bug_fp
        total.bug_fn   += c.bug_fn
        total.smell_tp += c.smell_tp
        total.smell_fp += c.smell_fp
        total.smell_fn += c.smell_fn
        total.hallucination_count      += c.hallucination_count
        total.out_of_scope_count       += c.out_of_scope_count
        total.esbmc_direct_tp          += c.esbmc_direct_tp
        total.esbmc_direct_fp          += c.esbmc_direct_fp
        total.esbmc_direct_fn          += c.esbmc_direct_fn
        total.esbmc_direct_func_tp     += c.esbmc_direct_func_tp
        total.esbmc_direct_func_fp     += c.esbmc_direct_func_fp
        total.esbmc_direct_func_fn     += c.esbmc_direct_func_fn
        total.esbmc_direct_func_tn     += c.esbmc_direct_func_tn
        total.hybrid_bug_tp            += c.hybrid_bug_tp
        total.hybrid_bug_fp            += c.hybrid_bug_fp
        total.hybrid_bug_fn            += c.hybrid_bug_fn
        total.hybrid_bug_func_tp       += c.hybrid_bug_func_tp
        total.hybrid_bug_func_fp       += c.hybrid_bug_func_fp
        total.hybrid_bug_func_fn       += c.hybrid_bug_func_fn
        total.hybrid_bug_func_tn       += c.hybrid_bug_func_tn
        total.bug_func_tp              += c.bug_func_tp
        total.bug_func_fp              += c.bug_func_fp
        total.bug_func_fn              += c.bug_func_fn
        total.bug_func_tn              += c.bug_func_tn
        total.llm_confirmed_by_esbmc   += c.llm_confirmed_by_esbmc
        total.esbmc_native_bug         += c.esbmc_native_bug
        total.llm_missed_esbmc_bug     += c.llm_missed_esbmc_bug
        total.not_confirmed_within_bound += c.not_confirmed_within_bound
        total.esbmc_inconclusive       += c.esbmc_inconclusive
        total.skipped_not_verifiable   += c.skipped_not_verifiable
        total.ghost_bug_count          += c.ghost_bug_count
        total.merge_category(c)
        total.merge_category_hybrid(c)

    cis = compute_bootstrap_cis(case_list, n_bootstrap=n_bootstrap) if n_bootstrap > 0 else {}
    return total, cis


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    """Matthews Correlation Coefficient — stable for imbalanced datasets."""
    import math
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denom == 0:
        return 0.0
    return (tp * tn - fp * fn) / denom


def accuracy(tp: int, fp: int, fn: int, tn: int) -> float:
    total = tp + fp + fn + tn
    if total == 0:
        return 0.0
    return (tp + tn) / total


def _flow_a_findings_from_direct(direct: ESBMCDirectResult | None) -> list[Finding]:
    if direct is None or direct.status != "violation_found":
        return []

    findings: list[Finding] = []
    for item in direct.details.get("functions", []):
        if not isinstance(item, dict) or item.get("status") != "violation_found":
            continue
        property_text = " ".join(
            str(item.get(key, ""))
            for key in ("property_kind", "property_text")
        )
        category = _category_from_esbmc_property(property_text)
        findings.append(
            Finding(
                id=f"flow_a_{item.get('name', len(findings))}",
                stage="esbmc_direct",
                finding_type="suspected_bug",
                category=category,
                title=f"Flow A violation in {item.get('name', '?')}",
                explanation=str(item.get("summary", "")),
                evidence=[str(item.get("property_kind", ""))],
                verifiable=True,
                confidence="high",
                metadata={"function": str(item.get("name", ""))},
            )
        )
    return findings


def hallucination_rate(counts: EvalCounts) -> float:
    # Denominator = LLM verifiable claims only (bugs + hallucinations).
    # Exclude ghost_bugs (suspected_bug + verifiable=False) — they inflate bug_fp
    # but are not true hallucinations (AST didn't reject them outright).
    total_verifiable_claims = counts.bug_tp + counts.bug_fp - counts.ghost_bug_count
    if total_verifiable_claims == 0:
        return 0.0
    return counts.hallucination_count / total_verifiable_claims


def formal_confirmation_rate(counts: EvalCounts) -> float:
    """Share of AST-valid LLM bug hypotheses confirmed by ESBMC in Flow B."""
    total_formal_attempts = (
        counts.llm_confirmed_by_esbmc
        + counts.not_confirmed_within_bound
        + counts.esbmc_inconclusive
    )
    if total_formal_attempts == 0:
        return 0.0
    return counts.llm_confirmed_by_esbmc / total_formal_attempts


def noise_reduction_rate(counts: EvalCounts) -> float:
    """Reduction in bug false positives from Flow C to Flow B.

    If Flow C has no false positives, the mathematical ratio is undefined.
    Reports use 0.0 as an operational JSON convention for that case.
    """
    if counts.bug_fp == 0:
        return 0.0
    return (counts.bug_fp - counts.hybrid_bug_fp) / counts.bug_fp


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals
# ---------------------------------------------------------------------------

def _accumulate(cases: list[EvalCounts]) -> EvalCounts:
    """Sum a list of per-case EvalCounts into one aggregate."""
    total = EvalCounts()
    for c in cases:
        total.bug_tp                     += c.bug_tp
        total.bug_fp                     += c.bug_fp
        total.bug_fn                     += c.bug_fn
        total.smell_tp                   += c.smell_tp
        total.smell_fp                   += c.smell_fp
        total.smell_fn                   += c.smell_fn
        total.hallucination_count        += c.hallucination_count
        total.out_of_scope_count         += c.out_of_scope_count
        total.esbmc_direct_tp            += c.esbmc_direct_tp
        total.esbmc_direct_fp            += c.esbmc_direct_fp
        total.esbmc_direct_fn            += c.esbmc_direct_fn
        total.esbmc_direct_func_tp       += c.esbmc_direct_func_tp
        total.esbmc_direct_func_fp       += c.esbmc_direct_func_fp
        total.esbmc_direct_func_fn       += c.esbmc_direct_func_fn
        total.esbmc_direct_func_tn       += c.esbmc_direct_func_tn
        total.hybrid_bug_tp              += c.hybrid_bug_tp
        total.hybrid_bug_fp              += c.hybrid_bug_fp
        total.hybrid_bug_fn              += c.hybrid_bug_fn
        total.hybrid_bug_func_tp         += c.hybrid_bug_func_tp
        total.hybrid_bug_func_fp         += c.hybrid_bug_func_fp
        total.hybrid_bug_func_fn         += c.hybrid_bug_func_fn
        total.hybrid_bug_func_tn         += c.hybrid_bug_func_tn
        total.bug_func_tp                += c.bug_func_tp
        total.bug_func_fp                += c.bug_func_fp
        total.bug_func_fn                += c.bug_func_fn
        total.bug_func_tn                += c.bug_func_tn
        total.llm_confirmed_by_esbmc     += c.llm_confirmed_by_esbmc
        total.esbmc_native_bug           += c.esbmc_native_bug
        total.llm_missed_esbmc_bug       += c.llm_missed_esbmc_bug
        total.not_confirmed_within_bound += c.not_confirmed_within_bound
        total.esbmc_inconclusive         += c.esbmc_inconclusive
        total.skipped_not_verifiable     += c.skipped_not_verifiable
        total.ghost_bug_count            += c.ghost_bug_count
        total.merge_category(c)
        total.merge_category_hybrid(c)
    return total


def bootstrap_ci(
    case_counts: list[EvalCounts],
    metric_fn: Callable[[EvalCounts], float],
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap CI for a scalar metric computed on resampled case-level EvalCounts."""
    rng = random.Random(seed)
    n = len(case_counts)
    samples: list[float] = []
    for _ in range(n_bootstrap):
        resample = [rng.choice(case_counts) for _ in range(n)]
        samples.append(metric_fn(_accumulate(resample)))
    samples.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = samples[int(alpha * n_bootstrap)]
    hi = samples[min(int((1.0 - alpha) * n_bootstrap), n_bootstrap - 1)]
    return lo, hi


_BOOTSTRAP_METRICS: dict[str, Callable[[EvalCounts], float]] = {
    "llm_bug_precision":    lambda c: prf(c.bug_tp, c.bug_fp, c.bug_fn)[0],
    "llm_bug_recall":       lambda c: prf(c.bug_tp, c.bug_fp, c.bug_fn)[1],
    "llm_bug_f1":           lambda c: prf(c.bug_tp, c.bug_fp, c.bug_fn)[2],
    "llm_bug_mcc":          lambda c: mcc(c.bug_func_tp, c.bug_func_fp, c.bug_func_fn, c.bug_func_tn),
    "hybrid_bug_precision": lambda c: prf(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)[0],
    "hybrid_bug_recall":    lambda c: prf(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)[1],
    "hybrid_bug_f1":        lambda c: prf(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)[2],
    "hybrid_bug_mcc":       lambda c: mcc(c.hybrid_bug_func_tp, c.hybrid_bug_func_fp, c.hybrid_bug_func_fn, c.hybrid_bug_func_tn),
    "esbmc_bug_precision":  lambda c: prf(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)[0],
    "esbmc_bug_recall":     lambda c: prf(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)[1],
    "esbmc_bug_f1":         lambda c: prf(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)[2],
    "esbmc_bug_mcc":        lambda c: mcc(c.esbmc_direct_func_tp, c.esbmc_direct_func_fp, c.esbmc_direct_func_fn, c.esbmc_direct_func_tn),
    "smell_precision":      lambda c: prf(c.smell_tp, c.smell_fp, c.smell_fn)[0],
    "smell_recall":         lambda c: prf(c.smell_tp, c.smell_fp, c.smell_fn)[1],
    "smell_f1":             lambda c: prf(c.smell_tp, c.smell_fp, c.smell_fn)[2],
}


def compute_bootstrap_cis(
    case_counts: list[EvalCounts],
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Compute percentile bootstrap CIs for all standard metrics. Returns {metric: (lo, hi)}."""
    return {
        name: bootstrap_ci(case_counts, fn, n_bootstrap=n_bootstrap, confidence=confidence, seed=seed)
        for name, fn in _BOOTSTRAP_METRICS.items()
    }


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
        print(f"  Flow A: {direct.status} — {direct.summary[:80]}")


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
