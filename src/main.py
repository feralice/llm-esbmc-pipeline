"""
main.py — Pipeline LLM + AST + ESBMC para verificação de bugs em Python.


Modos de execução:
  esbmc-only  Flow A: ESBMC puro com --function, sem LLM.
  llm-only    Flow C: LLM puro, sem ESBMC.
  hybrid      Flow B: LLM aponta bug → ESBMC confirma.
  benchmark   Roda os três fluxos (A+B+C) e calcula P/R/F1 vs ground truth.
  ensemble    Agrega votos de modelos já rodados (sem chamar LLM/ESBMC).
  scan        V2: para cada candidato, a LLM sintetiza um harness → ESBMC → ablação.


Exemplos:
  python src/main.py --mode esbmc-only  --input dataset/labeled --bound 5
  python src/main.py --mode llm-only    --input dataset/labeled --model gpt-4o
  python src/main.py --mode hybrid      --input dataset/labeled --model gpt-4o --bound 5
  python src/main.py --mode benchmark   --input dataset/labeled/ground_truths --model gpt-4o
  python src/main.py --mode scan        --input candidatos.json --model gpt-4o-mini
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
    Backend,
    run_pipeline_esbmc_direct,
    run_pipeline_llm_only,
    run_pipeline_multi,
)
from research_pipeline.voting import aggregate_votes, write_vote_report
from research_pipeline.scan.pipeline import load_candidates, run_pipeline_scan
from research_pipeline.scan.synth import HarnessSynthesizer
from research_pipeline.evaluator import (
    EvalCounts,
    accuracy_defined,
    compute_bootstrap_cis,
    evaluate_model,
    formal_confirmation_rate_defined,
    hallucination_rate_defined,
    mcc_defined,
    noise_reduction_rate_defined,
    prf_defined,
)




# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("deve ser um inteiro maior ou igual a 1")
    return parsed

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline LLM + AST + ESBMC para análise de bugs em Python.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["esbmc-only", "llm-only", "hybrid", "benchmark", "ensemble", "scan"],
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
            "No modo benchmark, passe o diretório raiz de ground truth (ex: dataset/labeled/ground_truths). Inclui bugs, clean e smells recursivamente. "
            "No modo ensemble, passe 2+ diretórios per_file de --report de modelos diferentes "
            "(ex: reports/json/v1_benchmark/per_file/gpt-5_5 reports/json/v1_benchmark/per_file/claude-sonnet-4-6)."
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
            "'gpt-5.5', 'claude-opus-4-8', 'deepseek-r1:7b'. "
            "(padrão: gpt-5.5)"
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
        type=_positive_int,
        default=5,
        help="Bound de unwinding para o ESBMC. (padrão: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=30,
        help="Timeout em segundos para cada chamada ao ESBMC. (padrão: 30)",
    )
    parser.add_argument(
        "--llm-timeout",
        type=_positive_int,
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
        "--verbose", "-v",
        action="store_true",
        help="Mostrar detalhes de cada arquivo durante avaliação.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Retomar unidades concluídas no --output-dir; exige a mesma "
            "configuração de modelo, prompt, bound e timeout."
        ),
    )
    parser.add_argument(
        "--min-votes",
        type=int,
        default=2,
        metavar="N",
        help=(
            "Somente no modo ensemble. Número mínimo de modelos que precisam "
            "concordar em (função, categoria) para o achado ser selecionado. "
            "(padrão: 2)"
        ),
    )
    parser.add_argument(
        "--no-compat",
        action="store_true",
        help="Modo scan: pula o compat.py (roda ESBMC no harness sem checar dependências).",
    )
    parser.add_argument(
        "--no-guards",
        action="store_true",
        help="Modo scan: não passa a allowlist de precondição (guards.py) para a síntese.",
    )
    parser.add_argument(
        "--no-ablation",
        action="store_true",
        help="Modo scan: não roda ablação nos vereditos SUCCESSFUL.",
    )
    parser.add_argument(
        "--v2-manifest",
        default=None,
        metavar="CAMINHO",
        help=(
            "Somente no modo hybrid. Caminho do manifest_pilot.json do V2 "
            "(dataset/v2_real_world/manifest_pilot.json). Quando informado, o "
            "ESBMC verifica o harness oculto (bugs/<id>.py) referenciado no "
            "manifesto para cada arquivo de --input que estiver em detection/, "
            "em vez de rodar --function no mesmo arquivo que a LLM leu. Sem "
            "essa flag, o hybrid se comporta como no V1 (arquivo único)."
        ),
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




def _load_v2_harness_map(manifest_path: str | None) -> dict[str, Path] | None:
    """Build {detection_file: harness_file} from manifest_pilot.json, or None."""
    if not manifest_path:
        return None
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        print(f"--v2-manifest não encontrado: {manifest_file}", file=sys.stderr)
        return None
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    base_dir = manifest_file.parent
    harness_map: dict[str, Path] = {}
    for item in data.get("items", []):
        detection_file = base_dir / item["detection_file"]
        harness_file = base_dir / item["harness_file"]
        harness_map[str(detection_file.resolve())] = harness_file.resolve()
    return harness_map




def _infer_backend(model: str | None) -> Backend:
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




def _resolve_model(model: str | None, backend: Backend) -> str | None:
    if model is None:
        return None
    aliases = {
        "claude":  "claude-opus-4-8",
        "gpt":     "gpt-5.5",
        "gemini":  "gemini-2.5-flash",
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


def _run_status_exit_code(output_dir: str | Path) -> int:
    status_path = Path(output_dir) / "run_status.json"
    if not status_path.exists():
        return 0
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") == "complete":
        return 0
    print(f"Execução parcial; veja {status_path}", file=sys.stderr)
    return 2


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)




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


def _round_optional(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _fmt_optional(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "N/A"


def _fmt_rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "N/A"


def _category_metrics(counts: dict[str, int]) -> dict[str, float | int | None]:
    values = prf_defined(counts["tp"], counts["fp"], counts["fn"])
    return {
        "precision": _round_optional(values["precision"]),
        "recall": _round_optional(values["recall"]),
        "f1": _round_optional(values["f1"]),
        "tp": counts["tp"],
        "fp": counts["fp"],
        "fn": counts["fn"],
    }




def _print_benchmark_table(label: str, counts: EvalCounts, cis: dict | None = None) -> None:
    cis = cis or {}
    bug = prf_defined(counts.bug_tp, counts.bug_fp, counts.bug_fn)
    smell = prf_defined(counts.smell_tp, counts.smell_fp, counts.smell_fn)
    esbmc = prf_defined(counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn)
    hybrid = prf_defined(counts.hybrid_bug_tp, counts.hybrid_bug_fp, counts.hybrid_bug_fn)
    bug_acc = accuracy_defined(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
    bug_mcc = mcc_defined(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)
    hybrid_acc = accuracy_defined(counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn)
    hybrid_mcc = mcc_defined(counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn)
    esbmc_acc = accuracy_defined(counts.esbmc_direct_func_tp, counts.esbmc_direct_func_fp, counts.esbmc_direct_func_fn, counts.esbmc_direct_func_tn)
    esbmc_mcc = mcc_defined(counts.esbmc_direct_func_tp, counts.esbmc_direct_func_fp, counts.esbmc_direct_func_fn, counts.esbmc_direct_func_tn)
    fcr = formal_confirmation_rate_defined(counts)
    nrr = noise_reduction_rate_defined(counts)
    hlr = hallucination_rate_defined(counts)


    print(f"\n{'─' * 60}")
    print(f"Modelo: {label}")
    print(f"{'─' * 60}")
    print(f"  Bug LLM P/R/F1:          {_fmt_optional(bug['precision'])} / {_fmt_optional(bug['recall'])} / {_fmt_optional(bug['f1'])}{_fmt_ci(cis, 'llm_bug_f1')}")
    print(f"    finding TP={counts.bug_tp}  FP={counts.bug_fp}  FN={counts.bug_fn}")
    print(f"    função Acc/MCC:        {_fmt_optional(bug_acc)} / {_fmt_optional(bug_mcc)}{_fmt_ci(cis, 'llm_bug_mcc')}")
    print(f"    função TP={counts.bug_func_tp}  FP={counts.bug_func_fp}  FN={counts.bug_func_fn}  TN={counts.bug_func_tn}")
    print(f"  Bug Híbrido P/R/F1:      {_fmt_optional(hybrid['precision'])} / {_fmt_optional(hybrid['recall'])} / {_fmt_optional(hybrid['f1'])}{_fmt_ci(cis, 'hybrid_bug_f1')}")
    print(f"    finding TP={counts.hybrid_bug_tp}  FP={counts.hybrid_bug_fp}  FN={counts.hybrid_bug_fn}")
    print(f"    função Acc/MCC:        {_fmt_optional(hybrid_acc)} / {_fmt_optional(hybrid_mcc)}{_fmt_ci(cis, 'hybrid_bug_mcc')}")
    print(f"    função TP={counts.hybrid_bug_func_tp}  FP={counts.hybrid_bug_func_fp}  FN={counts.hybrid_bug_func_fn}  TN={counts.hybrid_bug_func_tn}")
    print(f"    confirmados ESBMC={counts.llm_confirmed_by_esbmc}  não confirmados={counts.not_confirmed_within_bound}  inconclusivos={counts.esbmc_inconclusive}")
    print(f"    FCR/NRR:               {_fmt_optional(fcr)} / {_fmt_optional(nrr)}")
    print(f"  Smell P/R/F1:            {_fmt_optional(smell['precision'])} / {_fmt_optional(smell['recall'])} / {_fmt_optional(smell['f1'])}{_fmt_ci(cis, 'smell_f1')}")
    print(f"    TP={counts.smell_tp}  FP={counts.smell_fp}  FN={counts.smell_fn}")
    print(f"  Flow A P/R/F1:           {_fmt_optional(esbmc['precision'])} / {_fmt_optional(esbmc['recall'])} / {_fmt_optional(esbmc['f1'])}{_fmt_ci(cis, 'esbmc_bug_f1')}")
    print(f"    função Acc/MCC:        {_fmt_optional(esbmc_acc)} / {_fmt_optional(esbmc_mcc)}{_fmt_ci(cis, 'esbmc_bug_mcc')}")
    print(f"    função TP={counts.esbmc_direct_func_tp}  FP={counts.esbmc_direct_func_fp}  FN={counts.esbmc_direct_func_fn}  TN={counts.esbmc_direct_func_tn}")
    print(f"  Alucinações LLM:         {counts.hallucination_count}  (taxa: {_fmt_rate(hlr)})")
    print(f"  Fora do escopo LLM:      {counts.out_of_scope_count}")
    print(
        f"  Cobertura do benchmark:  {counts.cases_evaluated}/{counts.cases_planned} "
        f"casos; falhas={counts.cases_failed}"
    )


    if counts.per_category_hybrid:
        print(f"\n  Por categoria (Flow B — híbrido):")
        for cat, c in sorted(counts.per_category_hybrid.items()):
            metrics = prf_defined(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={_fmt_optional(metrics['precision'])} R={_fmt_optional(metrics['recall'])} F1={_fmt_optional(metrics['f1'])}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
    if counts.per_category:
        print(f"\n  Por categoria (Flow C — LLM only):")
        for cat, c in sorted(counts.per_category.items()):
            metrics = prf_defined(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={_fmt_optional(metrics['precision'])} R={_fmt_optional(metrics['recall'])} F1={_fmt_optional(metrics['f1'])}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
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
    incomplete = {
        "skipped", "timeout", "tool_error", "unsupported_case", "inconclusive",
        "no_vcc_generated",
    }
    return 2 if any(result.status in incomplete for result in results) else 0




def mode_llm_only(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1


    backend: Backend = args.backend or _infer_backend(args.model)
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
        resume=args.resume,
    )


    report_path = Path(output_dir) / "report.json"
    _print_summary(results)
    print(f"\nRelatório JSON: {report_path}")
    return _run_status_exit_code(output_dir)




def mode_hybrid(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo .py encontrado.", file=sys.stderr)
        return 1


    backend: Backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key, google_key = _resolve_keys(args)
    output_dir = args.output_dir or _default_output_dir("hybrid")
    harness_for = _load_v2_harness_map(getattr(args, "v2_manifest", None))


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
        harness_for=harness_for,
        resume=args.resume,
    )


    report_path = Path(output_dir) / "report.json"
    _print_summary(results)
    print(f"\nRelatório JSON: {report_path}")
    return _run_status_exit_code(output_dir)




def mode_benchmark(args: argparse.Namespace) -> int:
    if args.resume and not args.report:
        print("--resume no modo benchmark requer --report para localizar o checkpoint.", file=sys.stderr)
        return 1
    # --ground-truth tem prioridade; fallback para --input (compatibilidade retroativa)
    gt_raw = getattr(args, "ground_truth", None) or args.input[0]
    gt_path = Path(gt_raw)


    if not gt_path.exists():
        print(f"Ground truth não encontrado em: {gt_path}", file=sys.stderr)
        print("Exemplo: --ground-truth dataset/labeled/ground_truths", file=sys.stderr)
        return 1


    backend: Backend = args.backend or _infer_backend(args.model)
    model   = _resolve_model(args.model, backend)
    anthropic_key, openai_key, google_key = _resolve_keys(args)


    label = f"{backend}/{model or '(padrão)'}"
    print(f"Benchmark — {label}")


    report_arg = getattr(args, "report", None)
    per_file_dir: Path | None = None
    if report_arg:
        per_file_dir = Path(report_arg).parent / "per_file" / Path(report_arg).stem.removeprefix("benchmark_")


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
        output_dir=per_file_dir,
        resume=args.resume,
    )


    _print_benchmark_table(label, counts, cis)

    if report_arg:
        fcr = formal_confirmation_rate_defined(counts)
        nrr = noise_reduction_rate_defined(counts)
        bug_defined = prf_defined(counts.bug_tp, counts.bug_fp, counts.bug_fn)
        hybrid_defined = prf_defined(
            counts.hybrid_bug_tp, counts.hybrid_bug_fp, counts.hybrid_bug_fn
        )
        smell_defined = prf_defined(counts.smell_tp, counts.smell_fp, counts.smell_fn)
        esbmc_defined = prf_defined(
            counts.esbmc_direct_tp, counts.esbmc_direct_fp, counts.esbmc_direct_fn
        )
        report_data = {
            "model": label,
            "backend": backend,
            "ground_truth": str(gt_path.resolve()),
            "bound": args.bound,
            "timeout": args.timeout,
            "coverage": {
                "status": "complete" if counts.cases_failed == 0 else "partial",
                "planned": counts.cases_planned,
                "evaluated": counts.cases_evaluated,
                "failed": counts.cases_failed,
                "failed_cases": counts.failed_cases,
            },
            "metrics": {
                "bugs_llm_only": {
                    "precision": _round_optional(bug_defined["precision"]),
                    "recall": _round_optional(bug_defined["recall"]),
                    "f1": _round_optional(bug_defined["f1"]),
                    "tp": counts.bug_tp,
                    "fp": counts.bug_fp,
                    "fn": counts.bug_fn,
                    "function_accuracy": _round_optional(accuracy_defined(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)),
                    "function_mcc": _round_optional(mcc_defined(counts.bug_func_tp, counts.bug_func_fp, counts.bug_func_fn, counts.bug_func_tn)),
                    "function_tp": counts.bug_func_tp,
                    "function_fp": counts.bug_func_fp,
                    "function_fn": counts.bug_func_fn,
                    "function_tn": counts.bug_func_tn,
                },
                "bugs_hybrid_pipeline": {
                    "precision": _round_optional(hybrid_defined["precision"]),
                    "recall": _round_optional(hybrid_defined["recall"]),
                    "f1": _round_optional(hybrid_defined["f1"]),
                    "tp": counts.hybrid_bug_tp,
                    "fp": counts.hybrid_bug_fp,
                    "fn": counts.hybrid_bug_fn,
                    "function_accuracy": _round_optional(accuracy_defined(counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn)),
                    "function_mcc": _round_optional(mcc_defined(counts.hybrid_bug_func_tp, counts.hybrid_bug_func_fp, counts.hybrid_bug_func_fn, counts.hybrid_bug_func_tn)),
                    "function_tp": counts.hybrid_bug_func_tp,
                    "function_fp": counts.hybrid_bug_func_fp,
                    "function_fn": counts.hybrid_bug_func_fn,
                    "function_tn": counts.hybrid_bug_func_tn,
                    "llm_confirmed_by_esbmc": counts.llm_confirmed_by_esbmc,
                    "not_confirmed_within_bound": counts.not_confirmed_within_bound,
                    "esbmc_inconclusive": counts.esbmc_inconclusive,
                    "formal_confirmation_rate": _round_optional(fcr),
                    "noise_reduction_rate": _round_optional(nrr),
                },
                "smells": {
                    "precision": _round_optional(smell_defined["precision"]),
                    "recall": _round_optional(smell_defined["recall"]),
                    "f1": _round_optional(smell_defined["f1"]),
                    "tp": counts.smell_tp,
                    "fp": counts.smell_fp,
                    "fn": counts.smell_fn,
                },
                "esbmc_direct_baseline": {
                    "precision": _round_optional(esbmc_defined["precision"]),
                    "recall": _round_optional(esbmc_defined["recall"]),
                    "f1": _round_optional(esbmc_defined["f1"]),
                    "tp": counts.esbmc_direct_tp,
                    "fp": counts.esbmc_direct_fp,
                    "fn": counts.esbmc_direct_fn,
                    "function_accuracy": _round_optional(accuracy_defined(counts.esbmc_direct_func_tp, counts.esbmc_direct_func_fp, counts.esbmc_direct_func_fn, counts.esbmc_direct_func_tn)),
                    "function_mcc": _round_optional(mcc_defined(counts.esbmc_direct_func_tp, counts.esbmc_direct_func_fp, counts.esbmc_direct_func_fn, counts.esbmc_direct_func_tn)),
                    "function_tp": counts.esbmc_direct_func_tp,
                    "function_fp": counts.esbmc_direct_func_fp,
                    "function_fn": counts.esbmc_direct_func_fn,
                    "function_tn": counts.esbmc_direct_func_tn,
                },
            },
            "hallucinations": {
                "count": counts.hallucination_count,
                "rate": _round_optional(hallucination_rate_defined(counts)),
            },
            "out_of_scope_findings": {
                "count": counts.out_of_scope_count,
            },
            "per_category_llm": {
                cat: _category_metrics(c)
                for cat, c in sorted(counts.per_category.items())
            },
            "per_category_hybrid": {
                cat: _category_metrics(c)
                for cat, c in sorted(counts.per_category_hybrid.items())
            },
            "confidence_intervals_95": {
                key: ([_round_optional(value[0]), _round_optional(value[1])] if value else None)
                for key, value in cis.items()
            },
        }
        report_path_out = Path(report_arg)
        _write_json_atomic(report_path_out, report_data)
        print(f"\nRelatório JSON: {report_path_out}")


    if counts.cases_failed:
        print(
            "Benchmark parcial: há casos ausentes das métricas; consulte coverage no relatório.",
            file=sys.stderr,
        )
        return 2
    return 0


def mode_ensemble(args: argparse.Namespace) -> int:
    if len(args.input) < 2:
        print(
            "Modo ensemble requer 2+ diretórios per_file (um por modelo) em --input.",
            file=sys.stderr,
        )
        return 1


    try:
        report = aggregate_votes(args.input, min_votes=args.min_votes)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Erro no ensemble: {exc}", file=sys.stderr)
        return 1


    print(f"\nEnsemble — {report['model_count']} modelo(s): {', '.join(report['models'])}")
    print(f"  min_votes={report['min_votes']}")
    print(f"  candidatos={report['candidate_count']}  selecionados={report['selected_count']}")
    if args.verbose:
        for candidate in report["candidates"]:
            mark = "✓" if candidate["selected"] else " "
            print(
                f"  [{mark}] {candidate['votes']} voto(s)  "
                f"{candidate['file']}::{candidate['function']}  {candidate['category']}  "
                f"({', '.join(candidate['models'])})"
            )


    if args.report:
        report_path = write_vote_report(report, args.report)
        print(f"\nRelatório JSON: {report_path}")


    return 0


def mode_scan(args: argparse.Namespace) -> int:
    candidates_path = Path(args.input[0])
    if not candidates_path.exists():
        print(f"Candidatos não encontrados: {candidates_path}", file=sys.stderr)
        return 1

    model = _resolve_model(args.model, "openai") or "gpt-4o-mini"
    backend: Backend = args.backend or _infer_backend(model)
    if backend != "openai":
        print(
            "O modo scan só sintetiza harness via OpenAI por enquanto "
            "(--model gpt-4o-mini ou gpt-4o).",
            file=sys.stderr,
        )
        return 1

    _, openai_key, _ = _resolve_keys(args)
    try:
        synthesizer = HarnessSynthesizer(
            model=model, api_key=openai_key, timeout_seconds=args.llm_timeout
        )
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    try:
        candidates = load_candidates(candidates_path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Arquivo de candidatos inválido: {exc}", file=sys.stderr)
        return 1
    if not candidates:
        print("Nenhum candidato no arquivo.", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("scan")
    config = {
        "model": model,
        "compat": not args.no_compat,
        "guards": not args.no_guards,
        "ablation": not args.no_ablation,
        "bound": args.bound,
        "timeout": args.timeout,
    }
    layers = "".join(
        f" +{name}" for name in ("compat", "guards", "ablation") if config[name]
    ) or " synth-only"
    print(
        f"\nModo scan — {len(candidates)} candidato(s) → "
        f"{len(candidates)} chamada(s) de síntese ao modelo {model} | camadas:{layers}"
    )

    results = run_pipeline_scan(
        candidates,
        synthesizer=synthesizer,
        esbmc_command=args.esbmc_command,
        bound=args.bound,
        timeout_seconds=args.timeout,
        output_dir=output_dir,
        use_compat=not args.no_compat,
        use_guards=not args.no_guards,
        use_ablation=not args.no_ablation,
    )

    from collections import Counter

    for r in results:
        detail = r.error or r.esbmc_summary or ", ".join(r.compat_reasons)
        print(f"  [{r.classification:24s}] {r.candidate.function:20s} {detail[:56]}")
    tally = Counter(r.classification for r in results)
    print("\n  " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    if args.report:
        report_path = Path(args.report)
    else:
        report_path = Path(output_dir) / "scan_report.json"
    _write_json_atomic(
        report_path, {"config": config, "results": [r.to_dict() for r in results]}
    )
    print(f"\nRelatório JSON: {report_path}")
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
        "ensemble":   mode_ensemble,
        "scan":       mode_scan,
    }
    return dispatch[args.mode](args)




if __name__ == "__main__":
    raise SystemExit(main())
