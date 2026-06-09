"""
main.py — Pipeline LLM + AST + ESBMC para verificação de bugs em Python.

Modos de execução:
  esbmc-only  Flow A: ESBMC puro com --function, sem LLM.
  llm-only    Flow C: LLM puro, sem ESBMC.
  hybrid      Flow B: LLM aponta bug → ESBMC confirma.
  benchmark   Roda os três fluxos (A+B+C) e calcula P/R/F1 vs ground truth.

Exemplos:
  python src/main.py --mode esbmc-only  --input dataset/labeled --bound 5
  python src/main.py --mode llm-only    --input dataset/labeled --model gpt-4o
  python src/main.py --mode hybrid      --input dataset/labeled --model gpt-4o --bound 5
  python src/main.py --mode benchmark   --input dataset/labeled/ground_truths --model gpt-4o
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
    run_pipeline_esbmc_direct,
    run_pipeline_llm_only,
    run_pipeline_multi,
)
from research_pipeline.evaluator import (
    EvalCounts,
    accuracy,
    compute_bootstrap_cis,
    evaluate_model,
    formal_confirmation_rate,
    hallucination_rate,
    mcc,
    noise_reduction_rate,
    prf,
)


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
        choices=["esbmc-only", "llm-only", "hybrid", "benchmark"],
        default="benchmark",
        help="Modo de execução. (padrão: benchmark)",
    )
    parser.add_argument(
        "--input", "-i",
        nargs="+",
        required=True,
        metavar="CAMINHO",
        help=(
            "Arquivo(s) Python ou diretório. Diretórios são lidos recursivamente. "
            "No modo benchmark, passe o diretório raiz de ground truth (ex: dataset/labeled/ground_truths). Inclui bugs, clean e smells recursivamente."
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
            "Valores: 'gpt', 'claude', 'deepseek' ou nome completo como "
            "'gpt-4o', 'claude-3-7-sonnet-20250219', 'deepseek-r1:7b'. "
            "(padrão: gpt-4o)"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "anthropic", "ollama", "google"],
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
        "--llm-timeout",
        type=int,
        default=300,
        help="Timeout em segundos para chamadas à API da LLM. (padrão: 300)",
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
        "--google-api-key",
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
            "Caminho do relatório JSON de saída. "
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        metavar="CAMINHO",
        help=(
            "Diretório de ground truth para comparação. "
            "No modo benchmark, pode ser passado aqui em vez de --input. "
            "Exemplo: dataset/labeled/ground_truths"
        ),
    )
    parser.add_argument(
        "--prompt-mode",
        choices=["raw", "ast_hints"],
        default="raw",
        dest="prompt_mode",
        help=(
            "Modo do prompt LLM. "
            "raw (padrão): LLM recebe apenas código da função, sem hints de AST. "
            "ast_hints: injeção de operações pré-extraídas — usar apenas para ablação."
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
    if "gemini" in m:
        return "google"
    if any(x in m for x in ("gpt", "o1", "o3", "o4")):
        return "openai"
    return "ollama"


def _resolve_model(model: str | None, backend: str) -> str | None:
    if model is None:
        return None
    aliases = {
        "claude":  "claude-3-7-sonnet-20250219",
        "gpt":     "gpt-4o",
        "gemini":  "gemini-3.1-flash-lite",
        "deepseek": "deepseek-r1:7b",
    }
    return aliases.get(model.lower(), model)


def _resolve_keys(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key    = args.openai_api_key    or os.environ.get("OPENAI_API_KEY")
    google_key    = args.google_api_key    or os.environ.get("GEMINI_API_KEY")
    return anthropic_key, openai_key, google_key


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



def _fmt_ci(cis: dict, key: str) -> str:
    v = cis.get(key)
    if v is None:
        return ""
    return f"  [95% CI: {v[0]:.2f}–{v[1]:.2f}]"


def _print_benchmark_table(label: str, counts: EvalCounts, cis: dict | None = None) -> None:
    cis = cis or {}
    bug_p, bug_r, bug_f1 = prf(counts.bug_tp, counts.bug_fp, counts.bug_fn)
    smell_p, smell_r, smell_f1 = prf(counts.smell_tp, counts.smell_fp, counts.smell_fn)
    esbmc_p, esbmc_r, esbmc_f1 = prf(
        counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn
    )
    hybrid_p, hybrid_r, hybrid_f1 = prf(
        counts.hybrid_bug_tp, counts.hybrid_bug_fp, counts.hybrid_bug_fn
    )
    bug_acc = accuracy(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
    bug_mcc = mcc(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
    hybrid_acc = accuracy(
        counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn
    )
    hybrid_mcc = mcc(
        counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn
    )
    esbmc_acc = accuracy(
        counts.esbmc_direct_func_tp,
        counts.esbmc_direct_func_fp,
        counts.esbmc_direct_func_fn,
        counts.esbmc_direct_func_tn,
    )
    esbmc_mcc = mcc(
        counts.esbmc_direct_func_tp,
        counts.esbmc_direct_func_fp,
        counts.esbmc_direct_func_fn,
        counts.esbmc_direct_func_tn,
    )
    fcr = formal_confirmation_rate(counts)
    nrr = noise_reduction_rate(counts)
    hlr = hallucination_rate(counts)

    print(f"\n{'─' * 60}")
    print(f"Modelo: {label}")
    print(f"{'─' * 60}")
    print(f"  Bug LLM P/R/F1:          {bug_p:.2f} / {bug_r:.2f} / {bug_f1:.2f}{_fmt_ci(cis, 'llm_bug_f1')}")
    print(f"    finding TP={counts.bug_tp}  FP={counts.bug_fp}  FN={counts.bug_fn}")
    print(f"    função Acc/MCC:        {bug_acc:.2f} / {bug_mcc:.2f}{_fmt_ci(cis, 'llm_bug_mcc')}")
    print(f"    função TP={counts.bug_func_tp}  FP={counts.bug_func_fp}  FN={counts.bug_func_fn}  TN={counts.bug_func_tn}")
    print(f"  Bug Híbrido P/R/F1:      {hybrid_p:.2f} / {hybrid_r:.2f} / {hybrid_f1:.2f}{_fmt_ci(cis, 'hybrid_bug_f1')}")
    print(f"    finding TP={counts.hybrid_bug_tp}  FP={counts.hybrid_bug_fp}  FN={counts.hybrid_bug_fn}")
    print(f"    função Acc/MCC:        {hybrid_acc:.2f} / {hybrid_mcc:.2f}{_fmt_ci(cis, 'hybrid_bug_mcc')}")
    print(f"    função TP={counts.hybrid_bug_func_tp}  FP={counts.hybrid_bug_func_fp}  FN={counts.hybrid_bug_func_fn}  TN={counts.hybrid_bug_func_tn}")
    print(f"    confirmados ESBMC={counts.llm_confirmed_by_esbmc}  não confirmados={counts.not_confirmed_within_bound}  inconclusivos={counts.esbmc_inconclusive}")
    print(f"    FCR/NRR:               {fcr:.2f} / {nrr:.2f}")
    print(f"  Smell P/R/F1:            {smell_p:.2f} / {smell_r:.2f} / {smell_f1:.2f}{_fmt_ci(cis, 'smell_f1')}")
    print(f"    TP={counts.smell_tp}  FP={counts.smell_fp}  FN={counts.smell_fn}")
    print(f"  Flow A P/R/F1:           {esbmc_p:.2f} / {esbmc_r:.2f} / {esbmc_f1:.2f}{_fmt_ci(cis, 'esbmc_bug_f1')}")
    print(f"    função Acc/MCC:        {esbmc_acc:.2f} / {esbmc_mcc:.2f}{_fmt_ci(cis, 'esbmc_bug_mcc')}")
    print(f"    função TP={counts.esbmc_direct_func_tp}  FP={counts.esbmc_direct_func_fp}  FN={counts.esbmc_direct_func_fn}  TN={counts.esbmc_direct_func_tn}")
    print(f"  Alucinações LLM:         {counts.hallucination_count}  (taxa: {hlr:.1%})")
    print(f"  Fora do escopo LLM:      {counts.out_of_scope_count}")

    if counts.per_category_hybrid:
        print(f"\n  Por categoria (Flow B — híbrido):")
        for cat, c in sorted(counts.per_category_hybrid.items()):
            cp, cr, cf1 = prf(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={cp:.2f} R={cr:.2f} F1={cf1:.2f}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
    if counts.per_category:
        print(f"\n  Por categoria (Flow C — LLM only):")
        for cat, c in sorted(counts.per_category.items()):
            cp, cr, cf1 = prf(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={cp:.2f} R={cr:.2f} F1={cf1:.2f}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

def mode_esbmc_only(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("esbmc-only")
    results = run_pipeline_esbmc_direct(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
    )

    print(f"\nFlow A — ESBMC-only com --function — {len(results)} arquivo(s) analisado(s):")
    for r in results:
        print(f"  [{r.status:20s}]  {Path(r.source_file).name}  — {r.summary[:70]}")

    summary_path = Path(output_dir) / "esbmc_direct_results.json"
    print(f"\nResultados JSON: {summary_path}")
    return 0


def mode_llm_only(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key, google_key = _resolve_keys(args)
    output_dir = args.output_dir or _default_output_dir("llm-only")

    results = run_pipeline_llm_only(
        input_paths=input_paths,
        output_dir=output_dir,
        backend=backend,
        llm_model=model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        google_api_key=google_key,
        ollama_base_url=args.ollama_base_url,
        timeout_seconds=args.llm_timeout,
        prompt_mode=args.prompt_mode,
    )

    report_path = Path(output_dir) / "report.json"
    _print_summary(results)
    print(f"\nRelatório JSON: {report_path}")
    return 0


def mode_hybrid(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key, google_key = _resolve_keys(args)
    output_dir = args.output_dir or _default_output_dir("hybrid")

    results = run_pipeline_multi(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=args.esbmc_command,
        backend=backend,
        llm_model=model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        google_api_key=google_key,
        ollama_base_url=args.ollama_base_url,
        bound=args.bound,
        timeout_seconds=args.timeout,
        llm_timeout_seconds=args.llm_timeout,
        prompt_mode=args.prompt_mode,
    )

    report_path = Path(output_dir) / "report.json"
    _print_summary(results)
    print(f"\nRelatório JSON: {report_path}")
    return 0


def mode_benchmark(args: argparse.Namespace) -> int:
    # --ground-truth tem prioridade; fallback para --input (compatibilidade retroativa)
    gt_raw = getattr(args, "ground_truth", None) or args.input[0]
    gt_path = Path(gt_raw)

    if not gt_path.exists():
        print(f"Ground truth não encontrado em: {gt_path}", file=sys.stderr)
        print("Exemplo: --ground-truth dataset/labeled/ground_truths", file=sys.stderr)
        return 1

    backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key, google_key = _resolve_keys(args)

    label = f"{backend}/{model or '(padrão)'}"
    print(f"Benchmark — {label}")

    counts, cis = evaluate_model(
        ground_truth_path=gt_path,
        backend=backend,
        model=model or "",
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        google_api_key=google_key,
        ollama_base_url=args.ollama_base_url,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
        llm_timeout_seconds=args.llm_timeout,
        verbose=args.verbose,
        prompt_mode=args.prompt_mode,
    )

    _print_benchmark_table(label, counts, cis)

    report_arg = getattr(args, "report", None)
    if report_arg:
        bug_p, bug_r, bug_f1 = prf(counts.bug_tp, counts.bug_fp, counts.bug_fn)
        smell_p, smell_r, smell_f1 = prf(counts.smell_tp, counts.smell_fp, counts.smell_fn)
        esbmc_p, esbmc_r, esbmc_f1 = prf(
            counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn
        )
        hybrid_p, hybrid_r, hybrid_f1 = prf(
            counts.hybrid_bug_tp, counts.hybrid_bug_fp, counts.hybrid_bug_fn
        )
        bug_acc = accuracy(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
        bug_mcc = mcc(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
        hybrid_acc = accuracy(
            counts.hybrid_bug_func_tp,
            counts.hybrid_bug_func_fp,
            counts.hybrid_bug_func_fn,
            counts.hybrid_bug_func_tn,
        )
        hybrid_mcc = mcc(
            counts.hybrid_bug_func_tp,
            counts.hybrid_bug_func_fp,
            counts.hybrid_bug_func_fn,
            counts.hybrid_bug_func_tn,
        )
        esbmc_acc = accuracy(
            counts.esbmc_direct_func_tp,
            counts.esbmc_direct_func_fp,
            counts.esbmc_direct_func_fn,
            counts.esbmc_direct_func_tn,
        )
        esbmc_mcc = mcc(
            counts.esbmc_direct_func_tp,
            counts.esbmc_direct_func_fp,
            counts.esbmc_direct_func_fn,
            counts.esbmc_direct_func_tn,
        )
        fcr = formal_confirmation_rate(counts)
        nrr = noise_reduction_rate(counts)
        report_data = {
            "model": label,
            "backend": backend,
            "prompt_mode": args.prompt_mode,
            "ground_truth": str(gt_path.resolve()),
            "bound": args.bound,
            "timeout": args.timeout,
            "metrics": {
                "bugs_llm_only": {
                    "precision": round(bug_p, 4),
                    "recall": round(bug_r, 4),
                    "f1": round(bug_f1, 4),
                    "tp": counts.bug_tp,
                    "fp": counts.bug_fp,
                    "fn": counts.bug_fn,
                    "function_accuracy": round(bug_acc, 4),
                    "function_mcc": round(bug_mcc, 4),
                    "function_tp": counts.bug_func_tp,
                    "function_fp": counts.bug_func_fp,
                    "function_fn": counts.bug_func_fn,
                    "function_tn": counts.bug_func_tn,
                },
                "bugs_hybrid_pipeline": {
                    "precision": round(hybrid_p, 4),
                    "recall": round(hybrid_r, 4),
                    "f1": round(hybrid_f1, 4),
                    "tp": counts.hybrid_bug_tp,
                    "fp": counts.hybrid_bug_fp,
                    "fn": counts.hybrid_bug_fn,
                    "function_accuracy": round(hybrid_acc, 4),
                    "function_mcc": round(hybrid_mcc, 4),
                    "function_tp": counts.hybrid_bug_func_tp,
                    "function_fp": counts.hybrid_bug_func_fp,
                    "function_fn": counts.hybrid_bug_func_fn,
                    "function_tn": counts.hybrid_bug_func_tn,
                    "llm_confirmed_by_esbmc": counts.llm_confirmed_by_esbmc,
                    "not_confirmed_within_bound": counts.not_confirmed_within_bound,
                    "esbmc_inconclusive": counts.esbmc_inconclusive,
                    "formal_confirmation_rate": round(fcr, 4),
                    "noise_reduction_rate": round(nrr, 4),
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
                    "function_accuracy": round(esbmc_acc, 4),
                    "function_mcc": round(esbmc_mcc, 4),
                    "function_tp": counts.esbmc_direct_func_tp,
                    "function_fp": counts.esbmc_direct_func_fp,
                    "function_fn": counts.esbmc_direct_func_fn,
                    "function_tn": counts.esbmc_direct_func_tn,
                },
            },
            "hallucinations": {
                "count": counts.hallucination_count,
                "rate": round(hallucination_rate(counts), 4),
            },
            "out_of_scope_findings": {
                "count": counts.out_of_scope_count,
            },
            "per_category_llm": {
                cat: {
                    "precision": round(prf(c["tp"], c["fp"], c["fn"])[0], 4),
                    "recall":    round(prf(c["tp"], c["fp"], c["fn"])[1], 4),
                    "f1":        round(prf(c["tp"], c["fp"], c["fn"])[2], 4),
                    "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                }
                for cat, c in sorted(counts.per_category.items())
            },
            "per_category_hybrid": {
                cat: {
                    "precision": round(prf(c["tp"], c["fp"], c["fn"])[0], 4),
                    "recall":    round(prf(c["tp"], c["fp"], c["fn"])[1], 4),
                    "f1":        round(prf(c["tp"], c["fp"], c["fn"])[2], 4),
                    "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                }
                for cat, c in sorted(counts.per_category_hybrid.items())
            },
            "confidence_intervals_95": {
                k: [round(lo, 4), round(hi, 4)]
                for k, (lo, hi) in cis.items()
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
        "esbmc-only": mode_esbmc_only,
        "llm-only":   mode_llm_only,
        "hybrid":     mode_hybrid,
        "benchmark":  mode_benchmark,
    }
    return dispatch[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
