#!/usr/bin/env python3
"""Smoke test: roda benchmark com N arquivos por categoria (sem modificar o dataset).

Uso:
    # LLM + ESBMC Flow B apenas (sem Flow A)
    python scripts/smoke_benchmark.py --model gpt-5.5-2026-04-23 --n 2 --no-direct

    # Ambos os fluxos
    python scripts/smoke_benchmark.py --model gpt-5.5-2026-04-23 --n 2
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
from research_pipeline.evaluator import (
    EvalCounts,
    _expected_from_dataset_item,
    _esbmc_result_matches_category,
    _flow_a_findings_from_direct,
    _infer_source_root_for_ground_truth_dir,
    _match_with_categories,
    _source_path_for_item,
    prf,
)
from research_pipeline.llm.backends.factory import build_analyzer
from research_pipeline.models import Finding
from research_pipeline.preprocess import preprocess_file
from research_pipeline.verification.esbmc_runner import run_esbmc_function_baseline, run_esbmc_on_function


GROUND_TRUTH_JSONS = [
    ROOT / "dataset/labeled/ground_truths/bugs/assertion_violation.json",
    ROOT / "dataset/labeled/ground_truths/bugs/division_by_zero.json",
    ROOT / "dataset/labeled/ground_truths/bugs/out_of_bounds.json",
    ROOT / "dataset/labeled/ground_truths/clean/clean.json",
    ROOT / "dataset/labeled/ground_truths/smells/complex_conditional.json",
    ROOT / "dataset/labeled/ground_truths/smells/long_method.json",
    ROOT / "dataset/labeled/ground_truths/smells/many_parameters.json",
]


def load_n_cases(gt_json: Path, n: int) -> list[tuple[Path, list[dict]]]:
    payload = json.loads(gt_json.read_text(encoding="utf-8"))
    category = str(payload.get("category") or gt_json.stem)
    source_root = _infer_source_root_for_ground_truth_dir(gt_json.parent)
    cases = []
    for item in payload.get("items", [])[:n]:
        if not isinstance(item, dict) or not item.get("file"):
            continue
        file_path = _source_path_for_item(source_root, category, item)
        cases.append((file_path, [_expected_from_dataset_item(item)]))
    return cases


def evaluate_llm_only(
    file_path: Path,
    expected: list[dict],
    analyzer,
) -> EvalCounts:
    """Flow C: LLM findings only, no ESBMC confirmation."""
    counts = EvalCounts()

    units = preprocess_file(file_path)
    unit_findings: list[tuple] = []
    for unit in units:
        for finding in analyzer.analyze(unit):
            finding.metadata["function"] = unit.name
            unit_findings.append((unit, finding))

    bugs         = [f for _, f in unit_findings if f.verifiable]
    smells       = [f for _, f in unit_findings if not f.verifiable and f.finding_type == "smell_heuristic"]
    hallucinations = [f for _, f in unit_findings if f.finding_type == "llm_false_positive"]

    exp_bugs   = [e for e in expected if e.get("verifiable") is True]
    exp_smells = [e for e in expected if e.get("verifiable") is False and e.get("category") != "clean"]
    is_clean   = bool(expected) and all(e.get("category") == "clean" for e in expected)

    bug_tp, bug_fp, bug_fn, _ = _match_with_categories(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn, _ = _match_with_categories(smells, exp_smells)

    if is_clean:
        bug_tp = bug_fn = smell_tp = smell_fn = 0
        bug_fp = len(bugs) + len(hallucinations)
        smell_fp = len(smells)

    counts.bug_tp             = bug_tp
    counts.bug_fp             = bug_fp
    counts.bug_fn             = bug_fn
    counts.smell_tp           = smell_tp
    counts.smell_fp           = smell_fp
    counts.smell_fn           = smell_fn
    counts.hallucination_count = len(hallucinations)
    # No ESBMC step — "hybrid" equals LLM baseline
    counts.hybrid_bug_tp = bug_tp
    counts.hybrid_bug_fp = bug_fp
    counts.hybrid_bug_fn = bug_fn

    return counts


def evaluate_llm_esbmc(
    file_path: Path,
    expected: list[dict],
    analyzer,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
    run_direct: bool,
) -> EvalCounts:
    counts = EvalCounts()

    units = preprocess_file(file_path)
    unit_findings: list[tuple] = []
    for unit in units:
        for finding in analyzer.analyze(unit):
            finding.metadata["function"] = unit.name
            unit_findings.append((unit, finding))

    bugs_with_units = [(u, f) for u, f in unit_findings if f.verifiable]
    bugs            = [f for _, f in bugs_with_units]
    smells          = [f for _, f in unit_findings if not f.verifiable and f.finding_type == "smell_heuristic"]
    hallucinations  = [f for _, f in unit_findings if f.finding_type == "llm_false_positive"]

    exp_bugs   = [e for e in expected if e.get("verifiable") is True]
    exp_smells = [e for e in expected if e.get("verifiable") is False and e.get("category") != "clean"]
    is_clean   = bool(expected) and all(e.get("category") == "clean" for e in expected)

    bug_tp, bug_fp, bug_fn, bug_verdicts     = _match_with_categories(bugs, exp_bugs)
    smell_tp, smell_fp, smell_fn, _          = _match_with_categories(smells, exp_smells)

    if is_clean:
        bug_tp = bug_fn = smell_tp = smell_fn = 0
        bug_fp = len(bugs) + len(hallucinations)
        smell_fp = len(smells)

    counts.bug_tp             = bug_tp
    counts.bug_fp             = bug_fp
    counts.bug_fn             = bug_fn
    counts.smell_tp           = smell_tp
    counts.smell_fp           = smell_fp
    counts.smell_fn           = smell_fn
    counts.hallucination_count = len(hallucinations)

    # Flow B — LLM + ESBMC with --function
    esbmc_confirmed: list[Finding] = []

    for unit, bug_finding in bugs_with_units:
        esbmc_result = run_esbmc_on_function(
            file_path=file_path,
            function_name=unit.name,
            finding_id=bug_finding.id,
            category=bug_finding.category,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
        )
        if esbmc_result.status == "violation_found" and _esbmc_result_matches_category(esbmc_result.details, bug_finding.category):
            esbmc_confirmed.append(bug_finding)
            counts.llm_confirmed_by_esbmc += 1
        elif esbmc_result.status == "violation_found":
            counts.esbmc_inconclusive += 1
        elif esbmc_result.status == "no_violation_found":
            counts.not_confirmed_within_bound += 1
        elif esbmc_result.status == "skipped":
            counts.skipped_not_verifiable += 1
        else:
            counts.esbmc_inconclusive += 1

    h_tp, h_fp, h_fn, _ = _match_with_categories(esbmc_confirmed, exp_bugs)
    counts.hybrid_bug_tp = h_tp
    counts.hybrid_bug_fp = h_fp
    counts.hybrid_bug_fn = h_fn

    # Flow A — ESBMC-only with --function (opcional)
    if run_direct:
        direct = run_esbmc_function_baseline(
            file_path=file_path,
            function_names=[unit.name for unit in units],
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
        )
        flow_a_findings = _flow_a_findings_from_direct(direct)
        if direct.status not in ("inconclusive", "tool_error", "skipped", "timeout", "unsupported_case", "no_vcc_generated"):
            a_tp, a_fp, a_fn, _ = _match_with_categories(flow_a_findings, exp_bugs)
            counts.esbmc_direct_tp = a_tp
            counts.esbmc_direct_fp = a_fp
            counts.esbmc_direct_fn = a_fn
        if flow_a_findings:
            counts.esbmc_native_bug = len(flow_a_findings)

    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5.5-2026-04-23")
    parser.add_argument("--n", type=int, default=2, help="Arquivos por categoria")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-direct", action="store_true", help="Pula o Flow A (ESBMC-only com --function)")
    parser.add_argument("--llm-only", action="store_true", help="Flow C: só LLM, sem ESBMC")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("OPENAI_API_KEY não definida", file=sys.stderr)
        return 1

    analyzer = build_analyzer(
        backend="openai",
        llm_model=args.model,
        openai_api_key=openai_key,
    )

    llm_only  = args.llm_only
    run_direct = not args.no_direct and not llm_only
    if llm_only:
        label = f"{args.model} | Flow C (LLM-only) | {args.n} por categoria"
    elif args.no_direct:
        label = f"{args.model} | Flow B (LLM+ESBMC) | {args.n} por categoria"
    else:
        label = f"{args.model} | Flow A+B | {args.n} por categoria"
    print(f"\n=== Smoke benchmark — {label} ===\n")

    total = EvalCounts()
    for gt_json in GROUND_TRUTH_JSONS:
        cases = load_n_cases(gt_json, args.n)
        print(f"[{gt_json.stem}] {len(cases)} arquivo(s)")
        for file_path, expected in cases:
            print(f"  {file_path.name} ... ", end="", flush=True)
            if llm_only:
                c = evaluate_llm_only(
                    file_path=file_path,
                    expected=expected,
                    analyzer=analyzer,
                )
                line = (
                    f"bug tp={c.bug_tp} fp={c.bug_fp} fn={c.bug_fn} | "
                    f"smell tp={c.smell_tp} fp={c.smell_fp} fn={c.smell_fn} | "
                    f"hallucinations={c.hallucination_count}"
                )
            else:
                c = evaluate_llm_esbmc(
                    file_path=file_path,
                    expected=expected,
                    analyzer=analyzer,
                    esbmc_command=None,
                    bound=args.bound,
                    timeout_seconds=args.timeout,
                    run_direct=run_direct,
                )
                line = (
                    f"bug tp={c.bug_tp} fp={c.bug_fp} fn={c.bug_fn} | "
                    f"smell tp={c.smell_tp} fp={c.smell_fp} fn={c.smell_fn} | "
                    f"confirmed={c.llm_confirmed_by_esbmc} not_confirmed={c.not_confirmed_within_bound} "
                    f"skipped={c.skipped_not_verifiable}"
                )
                if run_direct:
                    line += f" | flow_a={c.esbmc_direct_tp}/{c.esbmc_direct_fp}/{c.esbmc_direct_fn}"
            print(line)

            for attr in ("bug_tp", "bug_fp", "bug_fn", "smell_tp", "smell_fp", "smell_fn",
                         "hallucination_count", "esbmc_direct_tp", "esbmc_direct_fp",
                         "esbmc_direct_fn", "hybrid_bug_tp", "hybrid_bug_fp", "hybrid_bug_fn",
                         "llm_confirmed_by_esbmc", "esbmc_native_bug", "not_confirmed_within_bound",
                         "esbmc_inconclusive", "skipped_not_verifiable"):
                setattr(total, attr, getattr(total, attr) + getattr(c, attr))
            total.merge_category(c)

    print("\n=== TOTAIS ===")
    bp, br, bf1 = prf(total.bug_tp, total.bug_fp, total.bug_fn)
    sp, sr, sf1 = prf(total.smell_tp, total.smell_fp, total.smell_fn)
    hp, hr, hf1 = prf(total.hybrid_bug_tp, total.hybrid_bug_fp, total.hybrid_bug_fn)

    print(f"  LLM bugs        P={bp:.2f} R={br:.2f} F1={bf1:.2f}  (tp={total.bug_tp} fp={total.bug_fp} fn={total.bug_fn})")
    print(f"  LLM smells      P={sp:.2f} R={sr:.2f} F1={sf1:.2f}  (tp={total.smell_tp} fp={total.smell_fp} fn={total.smell_fn})")
    if llm_only:
        print(f"  Flow C (LLM)    P={hp:.2f} R={hr:.2f} F1={hf1:.2f}  (tp={total.hybrid_bug_tp} fp={total.hybrid_bug_fp} fn={total.hybrid_bug_fn})")
        print(f"  Alucinações LLM: {total.hallucination_count}")
    else:
        print(f"  Híbrido (Flow B) P={hp:.2f} R={hr:.2f} F1={hf1:.2f}  (tp={total.hybrid_bug_tp} fp={total.hybrid_bug_fp} fn={total.hybrid_bug_fn})")
        print(f"  Confirmados ESBMC Flow B: {total.llm_confirmed_by_esbmc}")
        print(f"  Não confirmados (bound):  {total.not_confirmed_within_bound}")
        print(f"  Inconclusivos ESBMC:      {total.esbmc_inconclusive}")
        print(f"  Skipped (não verificável): {total.skipped_not_verifiable}")
        print(f"  Alucinações LLM:          {total.hallucination_count}")
        if run_direct:
            ep, er, ef1 = prf(total.esbmc_direct_tp, total.esbmc_direct_fp, total.esbmc_direct_fn)
            print(f"  Flow A (ESBMC-only --function) P={ep:.2f} R={er:.2f} F1={ef1:.2f}  (tp={total.esbmc_direct_tp} fp={total.esbmc_direct_fp} fn={total.esbmc_direct_fn})")
            print(f"  ESBMC nativo (Flow A):    {total.esbmc_native_bug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
