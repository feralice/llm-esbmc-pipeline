#!/usr/bin/env python3
"""Smoke test: roda benchmark com N arquivos por categoria (sem modificar o dataset).

Uso:
    # LLM + ESBMC Flow B apenas (sem esbmc-direct)
    python scripts/smoke_benchmark.py --model gpt-4o-2024-11-20 --n 2 --no-direct

    # Ambos os fluxos
    python scripts/smoke_benchmark.py --model gpt-4o-2024-11-20 --n 2
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
    _infer_source_root_for_ground_truth_dir,
    _match_with_categories,
    _source_path_for_item,
    prf,
)
from research_pipeline.llm.backends.factory import build_analyzer
from research_pipeline.models import Finding
from research_pipeline.preprocess import preprocess_file
from research_pipeline.verification.esbmc_runner import run_esbmc, run_esbmc_direct
from research_pipeline.verification.formalizer import formalize_finding
from research_pipeline.verification.instrumenter import instrument_unit


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

    # Flow B — LLM + ESBMC instrumented
    instrumented_dir = ROOT / "artifacts" / "smoke_instrumented"
    esbmc_confirmed: list[Finding] = []

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
            esbmc_confirmed.append(bug_finding)
            counts.llm_confirmed_by_esbmc += 1
        elif esbmc_result.status == "no_violation_found":
            counts.not_confirmed_within_bound += 1
        else:
            counts.esbmc_inconclusive += 1

    h_tp, h_fp, h_fn, _ = _match_with_categories(esbmc_confirmed, exp_bugs)
    counts.hybrid_bug_tp = h_tp
    counts.hybrid_bug_fp = h_fp
    counts.hybrid_bug_fn = h_fn

    # Flow A — ESBMC direto (opcional)
    if run_direct:
        direct = run_esbmc_direct(
            file_path,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
        )
        esbmc_found = direct.status == "violation_found"
        has_bug     = bool(exp_bugs)
        if esbmc_found and has_bug:
            counts.esbmc_direct_tp = 1
        elif esbmc_found and not has_bug:
            counts.esbmc_direct_fp = 1
        elif not esbmc_found and has_bug:
            if direct.status not in ("inconclusive", "tool_error", "skipped", "timeout", "unsupported_case", "no_vcc_generated"):
                counts.esbmc_direct_fn = 1
        if esbmc_found:
            counts.esbmc_native_bug = 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4o-2024-11-20")
    parser.add_argument("--n", type=int, default=2, help="Arquivos por categoria")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-direct", action="store_true", help="Pula o Flow A (esbmc-direct)")
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

    run_direct = not args.no_direct
    label = f"{args.model} | {'LLM+ESBMC Flow B' if args.no_direct else 'Flow A+B'} | {args.n} por categoria"
    print(f"\n=== Smoke benchmark — {label} ===\n")

    total = EvalCounts()
    for gt_json in GROUND_TRUTH_JSONS:
        cases = load_n_cases(gt_json, args.n)
        print(f"[{gt_json.stem}] {len(cases)} arquivo(s)")
        for file_path, expected in cases:
            print(f"  {file_path.name} ... ", end="", flush=True)
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
                line += f" | direct={c.esbmc_direct_tp}/{c.esbmc_direct_fp}/{c.esbmc_direct_fn}"
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
    print(f"  Híbrido (Flow B) P={hp:.2f} R={hr:.2f} F1={hf1:.2f}  (tp={total.hybrid_bug_tp} fp={total.hybrid_bug_fp} fn={total.hybrid_bug_fn})")
    print(f"  Confirmados ESBMC Flow B: {total.llm_confirmed_by_esbmc}")
    print(f"  Não confirmados (bound):  {total.not_confirmed_within_bound}")
    print(f"  Inconclusivos ESBMC:      {total.esbmc_inconclusive}")
    print(f"  Skipped (sem prop formal):{total.skipped_not_verifiable}")
    print(f"  Alucinações LLM:          {total.hallucination_count}")
    if run_direct:
        ep, er, ef1 = prf(total.esbmc_direct_tp, total.esbmc_direct_fp, total.esbmc_direct_fn)
        print(f"  ESBMC direto    P={ep:.2f} R={er:.2f} F1={ef1:.2f}  (tp={total.esbmc_direct_tp} fp={total.esbmc_direct_fp} fn={total.esbmc_direct_fn})")
        print(f"  ESBMC nativo (Flow A):    {total.esbmc_native_bug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
