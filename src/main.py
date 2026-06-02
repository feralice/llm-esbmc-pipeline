"""
main.py — Pipeline LLM + AST + ESBMC para verificação de bugs em Python.

Modos de execução:
  esbmc-direct  Roda o ESBMC diretamente nos arquivos, sem LLM.
  esbmc-harness Roda ESBMC em harnesses experimentais gerados para funções.
  llm-first     Roda apenas o pipeline LLM + AST + ESBMC instrumentado.
  full          Roda Flow A (ESBMC direto) + Flow B (LLM-first) integrados.
  benchmark     Avalia todos os modelos configurados contra o ground truth.

Exemplos:
  python src/main.py --mode esbmc-direct --input examples/labeled --bound 5
  python src/main.py --mode llm-first    --input examples/labeled --model claude --bound 5
  python src/main.py --mode full         --input examples/labeled --model claude --bound 5 --timeout 30 --report reports/full_report.json
  python src/main.py --mode benchmark    --input examples/labeled/ground_truths/bugs --model claude
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from research_pipeline.pipeline import (
    run_full_pipeline,
    run_pipeline_esbmc_direct,
    run_pipeline_multi,
)
from research_pipeline.evaluator import EvalCounts, evaluate_model, hallucination_rate, prf
from research_pipeline.full_report import build_full_report, write_full_report
from research_pipeline.harness_runner import run_esbmc_harness_pipeline


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline LLM + AST + ESBMC para análise de bugs em Python.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["esbmc-direct", "esbmc-harness", "llm-first", "full", "benchmark"],
        default="full",
        help="Modo de execução. (padrão: full)",
    )
    parser.add_argument(
        "--input", "-i",
        nargs="+",
        required=True,
        metavar="CAMINHO",
        help=(
            "Arquivo(s) Python ou diretório. Diretórios são lidos recursivamente. "
            "No modo benchmark, passe um diretório com JSONs de ground truth (ex: examples/labeled/ground_truths/bugs)."
        ),
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        metavar="DIR",
        help="Diretório de saída para relatórios e artefatos.",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODELO",
        help=(
            "Modelo LLM a usar. "
            "Valores: 'claude' ou nome completo como 'claude-sonnet-4-6', "
            "'gpt-4o', 'qwen2.5-coder:7b'. (padrão: gpt-4o)"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "anthropic", "ollama"],
        default=None,
        help="Backend LLM. Inferido automaticamente do --model se omitido.",
    )
    parser.add_argument(
        "--bound",
        type=int,
        default=5,
        help="Bound de unwinding para o ESBMC. (padrão: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout em segundos para cada chamada ao ESBMC. (padrão: 30)",
    )
    parser.add_argument(
        "--esbmc-command",
        nargs="+",
        default=None,
        metavar="CMD",
        help="Comando ESBMC customizado, ex: --esbmc-command esbmc --python python3",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=None,
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
    )
    parser.add_argument(
        "--report",
        default=None,
        metavar="CAMINHO",
        help=(
            "Caminho do relatório JSON de saída no modo full. "
            "(padrão: artifacts/full-pipeline/full_report.json)"
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        metavar="CAMINHO",
        help=(
            "Diretório de ground truth para comparação. "
            "No modo benchmark, pode ser passado aqui em vez de --input. "
            "Exemplo: examples/labeled/ground_truths/bugs"
        ),
    )
    parser.add_argument(
        "--enable-harness",
        action="store_true",
        default=False,
        help=(
            "[Experimental] Habilita validação por harness runtime como fallback "
            "quando o Formalizer não consegue gerar propriedade formal. "
            "Desabilitado por padrão na V1 — não entra nas métricas principais."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar detalhes de cada arquivo durante avaliação.",
    )
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_input_paths(inputs: list[str]) -> list[Path]:
    """Expand directories to .py files; keep individual file paths."""
    paths: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            paths.extend(sorted(candidate for candidate in p.rglob("*.py") if "__pycache__" not in candidate.parts))
        elif p.suffix == ".py" and p.exists():
            paths.append(p)
        # If it's a .json, the caller handles it (benchmark mode)
    return paths


def _infer_ground_truth_path(inputs: list[str]) -> Path | None:
    for raw in inputs:
        p = Path(raw)
        parts = p.parts
        if p.is_dir() and len(parts) >= 3 and parts[-2:] == ("ok", "bugs"):
            candidate = p.parent.parent / "ground_truths" / p.name
            if candidate.exists():
                return candidate
        if p.is_dir() and p.name == "bugs" and p.parent.name == "ok":
            candidate = p.parent.parent / "ground_truths" / "bugs"
            if candidate.exists():
                return candidate
    return None


def _infer_backend(model: str | None) -> str:
    if model is None:
        return "openai"
    m = model.lower()
    if "claude" in m:
        return "anthropic"
    if any(x in m for x in ("gpt", "o1", "o3", "o4")):
        return "openai"
    return "ollama"


def _resolve_model(model: str | None, backend: str) -> str | None:
    if model is None:
        return None
    aliases = {
        "claude": "claude-sonnet-4-6",
        "gpt":    "gpt-4o",
    }
    return aliases.get(model.lower(), model)


def _resolve_keys(args: argparse.Namespace) -> tuple[str | None, str | None]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key    = args.openai_api_key    or os.environ.get("OPENAI_API_KEY")
    return anthropic_key, openai_key


def _default_output_dir(mode: str) -> str:
    return str(REPO_ROOT / "artifacts" / mode)


def _print_summary(results) -> None:
    from collections import Counter
    counts = Counter(r.final_classification for r in results)
    print("\n── Resumo ────────────────────────────────")
    for cls, n in sorted(counts.items()):
        print(f"  {n:3d}  {cls}")
    print(f"  {len(results):3d}  TOTAL")
    print("──────────────────────────────────────────")


def _print_full_summary(summary: dict) -> None:
    print("\n── Resumo ──────────────────────────────────────────")
    print(f"  {summary['total_files']:3d}  arquivos analisados")
    print(f"  {summary['total_llm_findings']:3d}  achados da LLM")
    print(f"  {summary['total_esbmc_direct_violations']:3d}  violações ESBMC direto")
    print(f"  {summary['total_no_vcc_generated']:3d}  arquivos sem VCC gerada (ESBMC direto)")
    print(f"  {summary['total_confirmed_by_esbmc']:3d}  confirmados LLM+ESBMC (formal)")
    print(f"  {summary.get('total_runtime_reproduced', 0):3d}  reproduzidos por harness (auxiliar)")
    print(f"  {summary['total_llm_false_positives']:3d}  falsos positivos LLM")
    print(f"  {summary['total_smells']:3d}  smells heurísticos")
    print(f"  {summary['total_out_of_scope_findings']:3d}  fora do escopo MVP")
    print(f"  {summary['total_inconclusive']:3d}  inconclusivos")
    print("────────────────────────────────────────────────────")


def _print_benchmark_table(label: str, counts: EvalCounts) -> None:
    bug_p, bug_r, bug_f1 = prf(counts.bug_tp, counts.bug_fp, counts.bug_fn)
    smell_p, smell_r, smell_f1 = prf(counts.smell_tp, counts.smell_fp, counts.smell_fn)
    esbmc_p, esbmc_r, esbmc_f1 = prf(
        counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn
    )
    hlr = hallucination_rate(counts)

    print(f"\n{'─' * 60}")
    print(f"Modelo: {label}")
    print(f"{'─' * 60}")
    print(f"  Bug P/R/F1:          {bug_p:.2f} / {bug_r:.2f} / {bug_f1:.2f}")
    print(f"    TP={counts.bug_tp}  FP={counts.bug_fp}  FN={counts.bug_fn}")
    print(f"  Smell P/R/F1:        {smell_p:.2f} / {smell_r:.2f} / {smell_f1:.2f}")
    print(f"    TP={counts.smell_tp}  FP={counts.smell_fp}  FN={counts.smell_fn}")
    print(f"  ESBMC direct P/R/F1: {esbmc_p:.2f} / {esbmc_r:.2f} / {esbmc_f1:.2f}")
    print(f"  Alucinações LLM:     {counts.hallucination_count}  (taxa: {hlr:.1%})")

    if counts.per_category:
        print(f"\n  Por categoria:")
        for cat, c in sorted(counts.per_category.items()):
            cp, cr, cf1 = prf(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={cp:.2f} R={cr:.2f} F1={cf1:.2f}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

def mode_esbmc_direct(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("esbmc-direct")
    results = run_pipeline_esbmc_direct(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
    )

    print(f"\nESBMC direto — {len(results)} arquivo(s) analisado(s):")
    for r in results:
        print(f"  [{r.status:20s}]  {Path(r.source_file).name}  — {r.summary[:70]}")

    summary_path = Path(output_dir) / "esbmc_direct_results.json"
    print(f"\nResultados JSON: {summary_path}")
    return 0


def mode_esbmc_harness(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("esbmc-harness")
    results = run_esbmc_harness_pipeline(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
    )

    print(f"\nESBMC com harness experimental — {len(results)} harness(es) analisado(s):")
    for r in results:
        esbmc = r.esbmc_result
        print(f"  [{esbmc.status:20s}]  {Path(r.source_file).name}::{r.function}  — {esbmc.summary[:70]}")

    summary_path = Path(output_dir) / "esbmc_harness_results.json"
    print(f"\nResultados JSON: {summary_path}")
    return 0


def mode_llm_first(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key = _resolve_keys(args)
    output_dir = args.output_dir or _default_output_dir("llm-first")

    results = run_pipeline_multi(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        backend=backend,
        llm_model=model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        ollama_base_url=args.ollama_base_url,
        timeout_seconds=args.timeout,
        enable_harness=getattr(args, "enable_harness", False),
    )

    report_path = Path(output_dir) / "report.json"
    _print_summary(results)
    print(f"\nRelatório JSON: {report_path}")
    return 0


def mode_full(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key = _resolve_keys(args)
    output_dir = args.output_dir or _default_output_dir("full-pipeline")
    gt_path = (
        Path(args.ground_truth)
        if getattr(args, "ground_truth", None)
        else _infer_ground_truth_path(args.input)
    )

    print(f"Pipeline completo — {len(input_paths)} arquivo(s)")
    print(f"  Backend: {backend} / Modelo: {model or '(padrão)'}")
    print(f"  Bound: {args.bound}  |  Timeout: {args.timeout}s")

    enable_harness = getattr(args, "enable_harness", False)
    if enable_harness:
        print("  Harness runtime: HABILITADO (experimental)")

    results = run_full_pipeline(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        backend=backend,
        llm_model=model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        ollama_base_url=args.ollama_base_url,
        bound=args.bound,
        timeout_seconds=args.timeout,
        enable_harness=enable_harness,
    )

    report = build_full_report(
        input_paths=input_paths,
        results=results,
        mode="full",
        model=model,
        bound=args.bound,
        timeout=args.timeout,
        ground_truth_path=gt_path,
    )

    report_path = Path(getattr(args, "report", None) or Path(output_dir) / "full_report.json")
    write_full_report(report, report_path)

    _print_full_summary(report["summary"])
    print(f"\nRelatório JSON: {report_path}")
    return 0


def mode_benchmark(args: argparse.Namespace) -> int:
    # --ground-truth tem prioridade; fallback para --input (compatibilidade retroativa)
    gt_raw = getattr(args, "ground_truth", None) or args.input[0]
    gt_path = Path(gt_raw)

    if not gt_path.exists():
        print(f"Ground truth não encontrado em: {gt_path}", file=sys.stderr)
        print("Exemplo: --ground-truth examples/labeled/ground_truths/bugs", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key = _resolve_keys(args)

    label = f"{backend}/{model or '(padrão)'}"
    print(f"Benchmark — {label}")

    counts = evaluate_model(
        ground_truth_path=gt_path,
        backend=backend,
        model=model or "",
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        ollama_base_url=args.ollama_base_url,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
        verbose=args.verbose,
    )

    _print_benchmark_table(label, counts)

    report_arg = getattr(args, "report", None)
    if report_arg:
        bug_p, bug_r, bug_f1 = prf(counts.bug_tp, counts.bug_fp, counts.bug_fn)
        smell_p, smell_r, smell_f1 = prf(counts.smell_tp, counts.smell_fp, counts.smell_fn)
        esbmc_p, esbmc_r, esbmc_f1 = prf(
            counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn
        )
        report_data = {
            "model": label,
            "backend": backend,
            "ground_truth": str(gt_path.resolve()),
            "bound": args.bound,
            "timeout": args.timeout,
            "metrics": {
                "bugs": {
                    "precision": round(bug_p, 4),
                    "recall": round(bug_r, 4),
                    "f1": round(bug_f1, 4),
                    "tp": counts.bug_tp,
                    "fp": counts.bug_fp,
                    "fn": counts.bug_fn,
                },
                "smells": {
                    "precision": round(smell_p, 4),
                    "recall": round(smell_r, 4),
                    "f1": round(smell_f1, 4),
                    "tp": counts.smell_tp,
                    "fp": counts.smell_fp,
                    "fn": counts.smell_fn,
                },
                "esbmc_direct_baseline": {
                    "precision": round(esbmc_p, 4),
                    "recall": round(esbmc_r, 4),
                    "f1": round(esbmc_f1, 4),
                    "tp": counts.esbmc_direct_tp,
                    "fp": counts.esbmc_direct_fp,
                    "fn": counts.esbmc_direct_fn,
                },
            },
            "hallucinations": {
                "count": counts.hallucination_count,
                "rate": round(hallucination_rate(counts), 4),
            },
            "per_category": {
                cat: {
                    "precision": round(prf(c["tp"], c["fp"], c["fn"])[0], 4),
                    "recall":    round(prf(c["tp"], c["fp"], c["fn"])[1], 4),
                    "f1":        round(prf(c["tp"], c["fp"], c["fn"])[2], 4),
                    "tp": c["tp"],
                    "fp": c["fp"],
                    "fn": c["fn"],
                }
                for cat, c in sorted(counts.per_category.items())
            },
        }
        report_path_out = Path(report_arg)
        report_path_out.parent.mkdir(parents=True, exist_ok=True)
        report_path_out.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nRelatório JSON: {report_path_out}")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "esbmc-direct": mode_esbmc_direct,
        "esbmc-harness": mode_esbmc_harness,
        "llm-first":    mode_llm_first,
        "full":         mode_full,
        "benchmark":    mode_benchmark,
    }
    return dispatch[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
