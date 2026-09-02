from __future__ import annotations


import json
import random
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable, cast

from .llm.backends.factory import Backend, build_analyzer
from .models import (
    ESBMCDirectResult,
    Finding,
)
from .preprocess import preprocess_file
from .report import _category_from_esbmc_property, _esbmc_result_matches_category
from .verification.esbmc_runner import run_esbmc_function_baseline, run_esbmc_on_function




@dataclass
class EvalCounts:
    # Benchmark coverage. Failed cases never disappear silently from the run.
    cases_planned: int = 0
    cases_evaluated: int = 0
    cases_failed: int = 0
    failed_cases: list[dict[str, str]] = field(default_factory=list)

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
    per_category: dict[str, dict[str, int]] = field(default_factory=dict)
    per_category_hybrid: dict[str, dict[str, int]] = field(default_factory=dict)


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
        if _is_flat_multilabel_dataset(payload, ground_truth_path):
            return _load_flat_multilabel_cases(payload, ground_truth_path.parent / "bugs")
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
    """Load dataset JSONs recursively from a ground_truths directory or category dir.


    Multiple ground-truth items for the same source file are grouped into a
    single case so the file is only sent to the LLM once.
    """
    grouped: dict[Path, list[dict]] = {}
    for json_path in sorted(directory.rglob("*.json")):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "items" not in payload:
            continue
        source_root = _infer_source_root_for_ground_truth_dir(json_path.parent)
        category = str(payload.get("category") or json_path.stem)
        for item in payload.get("items", []):
            if not isinstance(item, dict) or not item.get("file"):
                continue
            src = _source_path_for_item(source_root, category, item)
            grouped.setdefault(src, []).append(_expected_from_dataset_item(item))
    return [(path, expected) for path, expected in grouped.items()]




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


def _is_flat_multilabel_dataset(payload: dict, ground_truth_path: Path) -> bool:
    """Return whether this is the V2 flat ``bugs/`` + category-list layout."""
    items = payload.get("items", [])
    return (
        (ground_truth_path.parent / "bugs").is_dir()
        and isinstance(items, list)
        and any(isinstance(item, dict) and isinstance(item.get("categories"), list) for item in items)
    )


def _load_flat_multilabel_cases(payload: dict, source_root: Path) -> list[tuple[Path, list[dict]]]:
    """Load V2 items, expanding each category tag into one expected finding."""
    grouped: dict[Path, list[dict]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict) or not item.get("file"):
            continue
        categories = item.get("categories", [])
        if not isinstance(categories, list) or not categories:
            continue
        source = source_root / str(item["file"])
        expected = grouped.setdefault(source, [])
        for category in categories:
            entry = _expected_from_dataset_item(item)
            entry["category"] = str(category)
            expected.append(entry)
    return sorted(grouped.items(), key=lambda case: str(case[0]))




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


    # Deduplicate bugs by (function, category): cap to max(expected_count, 1)
    # so multiple distinct bugs of the same type in the same function are kept
    # when the ground truth expects them, but excess over-reporting is suppressed.
    from collections import Counter as _Counter
    _exp_count = _Counter(
        (e.get("function", ""), e.get("category", "")) for e in exp_bugs
    )
    _seen_count: dict[tuple, int] = {}
    bugs_deduped: list = []
    for f in bugs:
        key = (f.metadata.get("function", ""), f.category)
        allowed = max(_exp_count.get(key, 0), 1)
        if _seen_count.get(key, 0) < allowed:
            _seen_count[key] = _seen_count.get(key, 0) + 1
            bugs_deduped.append(f)


    bug_tp, bug_fp, bug_fn, bug_verdicts         = _match_with_categories(bugs_deduped, exp_bugs)
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
    # Expand findings so multi-instance ground truth entries (same function/category)
    # are all counted as TP when ESBMC confirms a violation — ESBMC stops at the first
    # violation per run, so one confirmation covers all instances of that bug.
    flow_a_findings_expanded = _expand_flow_a_findings(flow_a_findings, exp_bugs)
    a_tp, a_fp, a_fn, _ = _match_with_categories(flow_a_findings_expanded, exp_bugs)
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


    if output_dir:
        _save_per_file_result(
            output_dir=Path(output_dir),
            file_name=file_path.name,
            bugs=bugs,
            exp_bugs=exp_bugs,
            smells=smells,
            exp_smells=exp_smells,
            bug_verdicts=bug_verdicts,
            smell_verdicts=smell_verdicts,
            rejected_findings=hallucinations,
        )


    return counts




def _save_per_file_result(
    output_dir: Path,
    file_name: str,
    bugs: list,
    exp_bugs: list[dict],
    smells: list,
    exp_smells: list[dict],
    bug_verdicts: list[tuple],
    smell_verdicts: list[tuple],
    rejected_findings: list,
) -> None:
    import json as _json
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(file_name).stem
    out: dict = {
        "file": file_name,
        "expected_bugs": [
            {"function": e.get("function", ""), "category": e.get("category", "")}
            for e in exp_bugs
        ],
        "generated_bugs": [
            {
                "function": f.metadata.get("function", ""),
                "category": f.category,
                "expression": getattr(f, "expression", ""),
                "line": f.metadata.get("line"),
                "confidence": getattr(f, "confidence", ""),
            }
            for f in bugs
        ],
        "expected_smells": [
            {"function": e.get("function", ""), "category": e.get("category", "")}
            for e in exp_smells
        ],
        "generated_smells": [
            {
                "function": f.metadata.get("function", ""),
                "category": f.category,
            }
            for f in smells
        ],
        "bug_verdicts": [{"category": c, "verdict": v} for c, v in bug_verdicts],
        "smell_verdicts": [{"category": c, "verdict": v} for c, v in smell_verdicts],
        "errors": {
            "bug_fp": [{"category": c, "verdict": v} for c, v in bug_verdicts if v == "fp"],
            "bug_fn": [{"category": c, "verdict": v} for c, v in bug_verdicts if v == "fn"],
            "smell_fp": [{"category": c, "verdict": v} for c, v in smell_verdicts if v == "fp"],
            "smell_fn": [{"category": c, "verdict": v} for c, v in smell_verdicts if v == "fn"],
        },
        "ast_rejections": [
            {
                "function": f.metadata.get("function", ""),
                "category": f.category,
                "expression": f.metadata.get("expression", ""),
                "line": f.metadata.get("line", 0),
                "reason": f.metadata.get("ast_rejection_reason", "unknown"),
                "candidate_expressions": f.metadata.get("ast_candidates", []),
                "matching_lines": f.metadata.get("ast_matching_lines", []),
            }
            for f in rejected_findings
        ],
    }
    out_path = output_dir / f"{stem}_eval.json"
    out_path.write_text(_json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")




def evaluate_model(
    ground_truth_path: Path,
    backend: str,
    model: str,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    google_api_key: str | None = None,
    ollama_base_url: str | None = None,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    llm_timeout_seconds: int = 300,
    verbose: bool = False,
    output_dir: str | Path | None = None,
    n_bootstrap: int = 2000,
    resume: bool = False,
) -> tuple[EvalCounts, dict[str, tuple[float, float] | None]]:
    cases = load_ground_truth_cases(ground_truth_path)
    analyzer = build_analyzer(
        backend=cast(Backend, backend),
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        timeout_seconds=llm_timeout_seconds,
    )


    checkpoint_path = Path(output_dir) / "benchmark_checkpoint.json" if output_dir else None
    fingerprint = {
        "ground_truth": str(ground_truth_path.resolve()),
        "backend": backend,
        "model": getattr(analyzer, "model", model),
        "bound": bound,
        "timeout": timeout_seconds,
        "llm_timeout": llm_timeout_seconds,
        "esbmc_command": esbmc_command or ["esbmc"],
    }
    completed: dict[str, dict] = {}
    if resume and checkpoint_path and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("fingerprint") != fingerprint:
            raise ValueError(
                "Não é seguro retomar o benchmark: a configuração difere do checkpoint."
            )
        completed = checkpoint.get("completed_cases", {})

    failed_cases: list[dict[str, str]] = []
    case_list: list[EvalCounts] = []
    num_cases = len(cases)
    _MAX_RETRIES = 3
    for i, (file_path, expected) in enumerate(cases, 1):
        case_key = _benchmark_case_key(file_path, expected)
        if case_key in completed:
            print(f"[{i}/{num_cases}] Retomada: {file_path.name} já concluído; pulando.")
            case_list.append(EvalCounts(**completed[case_key]))
            continue
        print(f"[{i}/{num_cases}] Processando {file_path.name}...")
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
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
                last_exc = None
                break
            except (RuntimeError, OSError) as exc:
                last_exc = exc
                print(f"  Tentativa {attempt}/{_MAX_RETRIES} falhou: {exc}", flush=True)
        if last_exc is not None:
            print(f"  WARN: {file_path.name} falhou após {_MAX_RETRIES} tentativas — pulando. Erro: {last_exc}", flush=True)
            failed_cases.append({"file": str(file_path), "error": str(last_exc)})
            continue
        case_list.append(c)
        completed[case_key] = asdict(c)
        if checkpoint_path:
            _write_benchmark_checkpoint(checkpoint_path, fingerprint, completed)

    total = _accumulate(case_list)
    total.cases_planned = len(cases)
    total.cases_evaluated = len(case_list)
    total.cases_failed = len(failed_cases)
    total.failed_cases = failed_cases


    cis = (
        compute_bootstrap_cis(case_list, n_bootstrap=n_bootstrap)
        if n_bootstrap > 0 and case_list
        else {}
    )
    if output_dir and hasattr(analyzer, "telemetry_events"):
        from .llm.telemetry import write_telemetry
        write_telemetry(
            analyzer.telemetry_events,
            Path(output_dir) / "llm_telemetry.json",
        )
    return total, cis


def _benchmark_case_key(file_path: Path, expected: list[dict]) -> str:
    expected_json = json.dumps(expected, sort_keys=True, ensure_ascii=False)
    digest = sha256(expected_json.encode("utf-8")).hexdigest()[:12]
    return f"{file_path.resolve()}::{digest}"


def _write_benchmark_checkpoint(
    path: Path,
    fingerprint: dict[str, object],
    completed: dict[str, dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": fingerprint, "completed_cases": completed}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)




def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def prf_defined(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    """Return P/R/F1 without converting undefined ratios into measured zeroes."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    elif precision == 0.0 and recall == 0.0:
        f1 = 0.0
    return {"precision": precision, "recall": recall, "f1": f1}




def mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    """Matthews Correlation Coefficient — stable for imbalanced datasets."""
    import math
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denom == 0:
        return 0.0
    return (tp * tn - fp * fn) / denom


def mcc_defined(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Return MCC, or None when its denominator is zero."""
    import math
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denom == 0:
        return None
    return (tp * tn - fp * fn) / denom




def accuracy(tp: int, fp: int, fn: int, tn: int) -> float:
    total = tp + fp + fn + tn
    if total == 0:
        return 0.0
    return (tp + tn) / total


def accuracy_defined(tp: int, fp: int, fn: int, tn: int) -> float | None:
    total = tp + fp + fn + tn
    return (tp + tn) / total if total else None




def _expand_flow_a_findings(
    flow_a_findings: list[Finding],
    exp_bugs: list[dict],
) -> list[Finding]:
    """Expand Flow A findings to cover multi-instance ground truth entries.


    ESBMC stops at the first violation per function. When the ground truth has N
    instances for the same (function, category), one ESBMC confirmation counts as
    N TPs — the function is confirmed buggy regardless of how many instances exist.
    """
    from collections import Counter
    exp_counts: Counter = Counter(
        (e.get("function", ""), e["category"]) for e in exp_bugs
    )
    expanded: list[Finding] = []
    for finding in flow_a_findings:
        key = (finding.metadata.get("function", ""), finding.category)
        n = exp_counts.get(key, 1)
        for _ in range(n):
            expanded.append(finding)
    return expanded




def _flow_a_findings_from_direct(direct: ESBMCDirectResult | None) -> list[Finding]:
    if direct is None or direct.status != "violation_found":
        return []


    findings: list[Finding] = []
    function_details = direct.details.get("functions", [])
    if not isinstance(function_details, list):
        return []
    for item in function_details:
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


def hallucination_rate_defined(counts: EvalCounts) -> float | None:
    total_verifiable_claims = counts.bug_tp + counts.bug_fp - counts.ghost_bug_count
    return (
        counts.hallucination_count / total_verifiable_claims
        if total_verifiable_claims > 0
        else None
    )




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


def formal_confirmation_rate_defined(counts: EvalCounts) -> float | None:
    attempts = (
        counts.llm_confirmed_by_esbmc
        + counts.not_confirmed_within_bound
        + counts.esbmc_inconclusive
    )
    return counts.llm_confirmed_by_esbmc / attempts if attempts else None


def noise_reduction_rate_defined(counts: EvalCounts) -> float | None:
    return (counts.bug_fp - counts.hybrid_bug_fp) / counts.bug_fp if counts.bug_fp else None




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
    metric_fn: Callable[[EvalCounts], float | None],
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for a scalar metric computed on resampled case-level EvalCounts."""
    rng = random.Random(seed)
    n = len(case_counts)
    samples: list[float] = []
    for _ in range(n_bootstrap):
        resample = [rng.choice(case_counts) for _ in range(n)]
        value = metric_fn(_accumulate(resample))
        if value is not None:
            samples.append(value)
    if not samples:
        return None
    samples.sort()
    alpha = (1.0 - confidence) / 2.0
    sample_count = len(samples)
    lo = samples[int(alpha * sample_count)]
    hi = samples[min(int((1.0 - alpha) * sample_count), sample_count - 1)]
    return lo, hi




_BOOTSTRAP_METRICS: dict[str, Callable[[EvalCounts], float | None]] = {
    "llm_bug_precision":    lambda c: prf_defined(c.bug_tp, c.bug_fp, c.bug_fn)["precision"],
    "llm_bug_recall":       lambda c: prf_defined(c.bug_tp, c.bug_fp, c.bug_fn)["recall"],
    "llm_bug_f1":           lambda c: prf_defined(c.bug_tp, c.bug_fp, c.bug_fn)["f1"],
    "llm_bug_mcc":          lambda c: mcc_defined(c.bug_func_tp, c.bug_func_fp, c.bug_func_fn, c.bug_func_tn),
    "hybrid_bug_precision": lambda c: prf_defined(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)["precision"],
    "hybrid_bug_recall":    lambda c: prf_defined(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)["recall"],
    "hybrid_bug_f1":        lambda c: prf_defined(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)["f1"],
    "hybrid_bug_mcc":       lambda c: mcc_defined(c.hybrid_bug_func_tp, c.hybrid_bug_func_fp, c.hybrid_bug_func_fn, c.hybrid_bug_func_tn),
    "esbmc_bug_precision":  lambda c: prf_defined(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)["precision"],
    "esbmc_bug_recall":     lambda c: prf_defined(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)["recall"],
    "esbmc_bug_f1":         lambda c: prf_defined(c.esbmc_direct_tp, c.esbmc_direct_fp, c.esbmc_direct_fn)["f1"],
    "esbmc_bug_mcc":        lambda c: mcc_defined(c.esbmc_direct_func_tp, c.esbmc_direct_func_fp, c.esbmc_direct_func_fn, c.esbmc_direct_func_tn),
    "smell_precision":      lambda c: prf_defined(c.smell_tp, c.smell_fp, c.smell_fn)["precision"],
    "smell_recall":         lambda c: prf_defined(c.smell_tp, c.smell_fp, c.smell_fn)["recall"],
    "smell_f1":             lambda c: prf_defined(c.smell_tp, c.smell_fp, c.smell_fn)["f1"],
}




def compute_bootstrap_cis(
    case_counts: list[EvalCounts],
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, tuple[float, float] | None]:
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
