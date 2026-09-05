"""
main.py — Pipeline LLM + AST + ESBMC para verificação de bugs em Python.


Modos de execução:
  esbmc-only  Flow A: ESBMC puro com --function, sem LLM.
  llm-only    Flow C: LLM puro, sem ESBMC.
  hybrid      Flow B: LLM aponta bug → ESBMC confirma.
  benchmark   Roda os três fluxos (A+B+C) e calcula P/R/F1 vs ground truth.
  ensemble    Agrega votos de modelos já rodados (sem chamar LLM/ESBMC).
  v2          Evolução: LLM detecta hipótese → gera harness → ESBMC verifica.


Exemplos:
  python src/main.py --mode esbmc-only  --input dataset/labeled --bound 5
  python src/main.py --mode llm-only    --input dataset/labeled --model gpt-4o
  python src/main.py --mode hybrid      --input dataset/labeled --model gpt-4o --bound 5
  python src/main.py --mode benchmark   --input dataset/labeled/ground_truths --model gpt-4o
  python src/main.py --mode v2 --input dataset/v2_real_world/detection --model gpt-4o-mini
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")


from research_pipeline.evaluator import (
    EvalCounts,
    accuracy_defined,
    evaluate_model,
    formal_confirmation_rate_defined,
    hallucination_rate_defined,
    mcc_defined,
    noise_reduction_rate_defined,
    prf_defined,
)
from research_pipeline.llm.backends.factory import build_analyzer
from research_pipeline.pipeline import (
    Backend,
    run_pipeline_esbmc_direct,
    run_pipeline_llm_only,
    run_pipeline_multi,
)
from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan.pipeline import (
    ScanCandidate,
    ScanCaseResult,
    run_pipeline_scan,
)
from research_pipeline.scan.synth import HarnessSynthesizer, load_synth_prompt
from research_pipeline.v2_evaluator import evaluate_v2_results
from research_pipeline.voting import aggregate_votes, write_vote_report

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
        choices=["esbmc-only", "llm-only", "hybrid", "benchmark", "ensemble", "v2"],
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
        "--synth-backend",
        choices=["openai", "ollama", "codex"],
        default=None,
        help=(
            "Backend só para a síntese de harness no modo V2 (padrão: mesmo de --backend). "
            "'codex' chama o `codex exec` local via assinatura já paga, em vez da API "
            "OpenAI cobrada por token."
        ),
    )
    parser.add_argument(
        "--synth-model",
        default=None,
        metavar="MODELO",
        help="Modelo só para a síntese de harness no modo V2 (padrão: mesmo de --model).",
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
            "Ground truth para comparação. "
            "No modo benchmark, pode ser passado aqui em vez de --input. "
            "No modo V2, informe dataset/v2_real_world/ground_truths.json; "
            "ele é lido somente depois das chamadas às LLMs e ao ESBMC."
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
        help="Modo V2: pula a checagem de compatibilidade do harness.",
    )
    parser.add_argument(
        "--no-guards",
        action="store_true",
        help="Modo V2: não passa a allowlist de precondição para a síntese.",
    )
    parser.add_argument(
        "--no-ablation",
        action="store_true",
        help="Modo V2: não roda ablação nos vereditos SUCCESSFUL.",
    )
    parser.add_argument(
        "--synth-retries",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Modo V2: tentativas extras de síntese quando uma falha é "
            "recuperável (harness inválido, erro do ESBMC). (padrão: 1)"
        ),
    )
    parser.add_argument(
        "--v2-stage",
        choices=["end-to-end", "synthesis"],
        default="end-to-end",
        help=(
            "Modo V2: 'end-to-end' detecta e sintetiza; 'synthesis' usa "
            "hipóteses conhecidas somente para avaliar a geração de harness "
            "isoladamente (requer --ground-truth)."
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


def _v2_candidate_dict(candidate: ScanCandidate) -> dict[str, str]:
    return {
        "file": candidate.file,
        "function": candidate.function,
        "category": candidate.category,
        "expression": candidate.expression,
        "note": candidate.note,
    }


def _load_v2_oracle_candidates(
    ground_truth_path: str | Path, input_paths: list[Path]
) -> list[ScanCandidate]:
    """Load synthesis-only hypotheses without exposing human harness contents."""
    gt_path = Path(ground_truth_path)
    manifest_path = gt_path.parent / "manifest_pilot.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = {str(path.resolve()) for path in input_paths}
    candidates: list[ScanCandidate] = []
    for item in manifest.get("items", []):
        detection = manifest_path.parent / item["detection_file"]
        if str(detection.resolve()) not in allowed:
            continue
        declared_function = str(item["function"])
        units = preprocess_file(detection)
        selected_function = declared_function
        if units:
            alternatives = [part.strip() for part in declared_function.split("/")]
            matched_unit = next(
                (
                    unit
                    for unit in units
                    if any(
                        alt and (unit.qualname == alt or unit.name == alt.split(".")[-1])
                        for alt in alternatives
                    )
                ),
                None,
            )
            if matched_unit is None:
                expression = str(item.get("expression", ""))
                matched_unit = next(
                    (unit for unit in units if expression and expression in unit.source),
                    units[0],
                )
            selected_function = matched_unit.qualname
        for category in item.get("categories", []):
            candidates.append(
                ScanCandidate(
                    file=str(detection),
                    function=selected_function,
                    category=str(category),
                    expression=str(item.get("expression", "")),
                    note="Oracle-seeded hypothesis for synthesis-only evaluation.",
                )
            )
    return candidates


def _v2_fingerprint(config: dict, input_paths: list[Path]) -> dict:
    return {
        "config": config,
        "sources": {
            str(path.resolve()): sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
        "detector_prompt": sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/system_prompt.txt").read_bytes()
        ).hexdigest(),
        "synth_prompt": sha256(load_synth_prompt().encode("utf-8")).hexdigest(),
    }


def _summarize_v2_telemetry(events: list[dict]) -> dict:
    by_stage: dict[str, dict[str, float | int]] = {}
    for event in events:
        stage = str(event["stage"])
        totals = by_stage.setdefault(
            stage, {"calls": 0, "failed_calls": 0, "tokens": 0, "seconds": 0.0}
        )
        totals["calls"] += 1
        totals["failed_calls"] += int(event.get("status") != "success")
        totals["tokens"] += int(event.get("total_tokens") or 0)
        totals["seconds"] += float(event.get("duration_seconds") or 0.0)
    for totals in by_stage.values():
        totals["seconds"] = round(float(totals["seconds"]), 3)
    return by_stage




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
        print("\n  Por categoria (Flow B — híbrido):")
        for cat, c in sorted(counts.per_category_hybrid.items()):
            metrics = prf_defined(c["tp"], c["fp"], c["fn"])
            print(f"    {cat:<30} P={_fmt_optional(metrics['precision'])} R={_fmt_optional(metrics['recall'])} F1={_fmt_optional(metrics['f1'])}  TP={c['tp']} FP={c['fp']} FN={c['fn']}")
    if counts.per_category:
        print("\n  Por categoria (Flow C — LLM only):")
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


def mode_v2(args: argparse.Namespace) -> int:
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo Python encontrado para a V2.", file=sys.stderr)
        return 1
    if args.v2_stage == "synthesis" and not args.ground_truth:
        print("--v2-stage synthesis requer --ground-truth.", file=sys.stderr)
        return 1

    model = _resolve_model(args.model, "openai") or "gpt-4o-mini"
    backend: Backend = args.backend or _infer_backend(model)
    if backend not in {"openai", "ollama"}:
        print(
            "O modo V2 detecta via OpenAI ou Ollama por enquanto.",
            file=sys.stderr,
        )
        return 1

    synth_backend = args.synth_backend or backend
    # 'model' is resolved against OpenAI/Ollama naming; codex has its own model
    # namespace, so only fall back to it when synth_backend wasn't overridden.
    synth_model = args.synth_model or ("" if args.synth_backend == "codex" else model)

    anthropic_key, openai_key, google_key = _resolve_keys(args)
    try:
        analyzer = build_analyzer(
            backend=backend,
            llm_model=model,
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            google_api_key=google_key,
            ollama_base_url=args.ollama_base_url,
            timeout_seconds=args.llm_timeout,
        )
        synthesizer = HarnessSynthesizer(
            backend=synth_backend,
            model=synth_model,
            api_key=openai_key if synth_backend == "openai" else "ollama",
            base_url=(args.ollama_base_url or "http://localhost:11434/v1")
            if synth_backend == "ollama"
            else "https://api.openai.com/v1/responses",
            timeout_seconds=args.llm_timeout,
        )
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("v2")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    config = {
        "model": model,
        "backend": backend,
        "synth_backend": synth_backend,
        "synth_model": synth_model,
        "v2_stage": args.v2_stage,
        "input_files": [str(path.resolve()) for path in input_paths],
        "compat": not args.no_compat,
        "guards": not args.no_guards,
        "ablation": not args.no_ablation,
        "synth_retries": args.synth_retries,
        "bound": args.bound,
        "timeout": args.timeout,
        "llm_timeout": args.llm_timeout,
        "esbmc_command": args.esbmc_command or ["esbmc"],
    }
    fingerprint = _v2_fingerprint(config, input_paths)
    checkpoint_path = output_path / "v2_checkpoint.json"
    if args.resume:
        if not checkpoint_path.exists():
            print(f"Checkpoint V2 não encontrado: {checkpoint_path}", file=sys.stderr)
            return 1
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("fingerprint") != fingerprint:
            print("Não é seguro retomar a V2: configuração, prompt ou fontes mudaram.", file=sys.stderr)
            return 1
    else:
        checkpoint = {
            "fingerprint": fingerprint,
            "detection_units": {},
            "synthesis_results": {},
            "status": "running",
            "telemetry_events": [],
    }
        _write_json_atomic(checkpoint_path, checkpoint)

    analyzer_events_seen = 0
    synthesizer_events_seen = 0

    def capture_telemetry() -> None:
        nonlocal analyzer_events_seen, synthesizer_events_seen
        analyzer_events = getattr(analyzer, "telemetry_events", [])
        synthesizer_events = getattr(synthesizer, "telemetry_events", [])
        checkpoint.setdefault("telemetry_events", []).extend(
            {**event, "stage": "detection"}
            for event in analyzer_events[analyzer_events_seen:]
        )
        checkpoint["telemetry_events"].extend(
            {**event, "stage": "synthesis"}
            for event in synthesizer_events[synthesizer_events_seen:]
        )
        analyzer_events_seen = len(analyzer_events)
        synthesizer_events_seen = len(synthesizer_events)

    candidates: list[ScanCandidate] = (
        _load_v2_oracle_candidates(args.ground_truth, input_paths)
        if args.v2_stage == "synthesis"
        else []
    )
    rejected_findings: list[dict[str, str]] = []
    detection_errors: list[dict[str, str]] = []
    analyzed_units = 0
    detection_inputs = [] if args.v2_stage == "synthesis" else input_paths
    if args.v2_stage == "synthesis":
        print(f"\nModo V2 — síntese isolada: {len(candidates)} hipótese(s) conhecida(s)")
    else:
        print(f"\nModo V2 — etapa 1: detecção em {len(input_paths)} arquivo(s)")
    for file_index, file_path in enumerate(detection_inputs, 1):
        units = preprocess_file(file_path)
        for unit in units:
            analyzed_units += 1
            unit_key = f"{file_path.resolve()}::{unit.qualname}"
            saved_unit = checkpoint["detection_units"].get(unit_key)
            if saved_unit is not None:
                candidates.extend(ScanCandidate.from_dict(item) for item in saved_unit["candidates"])
                rejected_findings.extend(saved_unit.get("rejected_findings", []))
                print(f"  [{file_index}/{len(input_paths)}] Retomada: {file_path.name}::{unit.qualname}")
                continue
            print(f"  [{file_index}/{len(input_paths)}] Analisando {file_path.name}::{unit.qualname}...")
            try:
                findings = analyzer.analyze(unit)
            except Exception as exc:  # one API failure must not discard other units
                detection_errors.append(
                    {"file": str(file_path), "function": unit.qualname, "error": str(exc)}
                )
                capture_telemetry()
                _write_json_atomic(checkpoint_path, checkpoint)
                continue
            unit_candidates: list[ScanCandidate] = []
            unit_rejections: list[dict[str, str]] = []
            for finding in findings:
                if not finding.verifiable or finding.finding_type != "suspected_bug":
                    if finding.finding_type in {
                        "llm_false_positive", "out_of_scope_finding", "suspected_bug"
                    }:
                        unit_rejections.append(
                            {
                                "file": str(file_path),
                                "function": unit.qualname,
                                "category": finding.category,
                                "finding_type": finding.finding_type,
                                "expression": str(finding.metadata.get("expression", "")),
                                "reason": str(finding.metadata.get("ast_rejection_reason", "")),
                            }
                        )
                    continue
                unit_candidates.append(
                    ScanCandidate(
                        file=str(file_path),
                        function=unit.qualname,
                        category=finding.category,
                        expression=str(finding.metadata.get("expression", "")),
                        note=finding.explanation,
                    )
                )
            candidates.extend(unit_candidates)
            rejected_findings.extend(unit_rejections)
            checkpoint["detection_units"][unit_key] = {
                "candidates": [_v2_candidate_dict(candidate) for candidate in unit_candidates],
                "rejected_findings": unit_rejections,
            }
            capture_telemetry()
            _write_json_atomic(checkpoint_path, checkpoint)

    if detection_errors:
        checkpoint["status"] = "partial_detection"
        checkpoint["detection_errors"] = detection_errors
        _write_json_atomic(checkpoint_path, checkpoint)
        report_path = Path(args.report) if args.report else output_path / "v2_report.json"
        capture_telemetry()
        telemetry_events = checkpoint["telemetry_events"]
        telemetry_summary = _summarize_v2_telemetry(telemetry_events)
        _write_json_atomic(output_path / "llm_telemetry.json", telemetry_events)
        _write_json_atomic(
            report_path,
            {
                "config": config,
                "coverage": {"status": "partial", "stage": "detection"},
                "detection": {
                    "analyzed_units": analyzed_units,
                    "hypotheses": len(candidates),
                    "failed_units": len(detection_errors),
                    "errors": detection_errors,
                    "candidates": [_v2_candidate_dict(c) for c in candidates],
                    "rejected_findings": rejected_findings,
                },
                "summary": _scan_summary([]),
                "telemetry": telemetry_summary,
                "results": [],
            },
        )
        print("Execução V2 parcial na detecção; retome com --resume.", file=sys.stderr)
        return 2

    layers = "".join(
        f" +{name}" for name in ("compat", "guards", "ablation") if config[name]
    ) or " synth-only"
    candidate_origin = "conhecida(s)" if args.v2_stage == "synthesis" else "detectada(s)"
    print(
        f"\nModo V2 — etapa 2: {len(candidates)} hipótese(s) {candidate_origin} → "
        f"síntese de harness com {synth_backend}:{synth_model or '(padrão da conta)'} | camadas:{layers}"
    )

    completed_results = {
        int(index): ScanCaseResult.from_dict(data)
        for index, data in checkpoint.get("synthesis_results", {}).items()
    }

    def save_synthesis_result(index: int, result: ScanCaseResult) -> None:
        checkpoint["synthesis_results"][str(index)] = result.to_dict()
        checkpoint["status"] = "running"
        capture_telemetry()
        _write_json_atomic(checkpoint_path, checkpoint)

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
        synth_retries=args.synth_retries,
        completed_results=completed_results,
        on_result=save_synthesis_result,
    )

    summary = _scan_summary(results)
    if args.verbose:
        for r in results:
            detail = r.error or r.esbmc_summary or ", ".join(r.compat_reasons)
            print(f"  [{r.classification:24s}] {r.candidate.function:20s} {detail[:56]}")
    print("\n  por classificação:")
    for k, v in sorted(summary["by_classification"].items()):
        print(f"    {k:26s} {v}")
    print("\n  por categoria (confirmado / total, nativo e não-verificado entre parênteses):")
    for cat, d in sorted(summary["by_category"].items()):
        extra = []
        if d["native"]:
            extra.append(f"{d['native']} via --function nativo")
        if d["unverified"]:
            extra.append(f"{d['unverified']} não-verificado")
        suffix = f" ({', '.join(extra)})" if extra else ""
        print(f"    {cat:22s} {d['confirmed']}/{d['total']}{suffix}")

    if args.report:
        report_path = Path(args.report)
    else:
        report_path = output_path / "v2_report.json"
    incomplete = {
        "invalid_harness", "unsupported_harness", "no_property",
        "esbmc_inconclusive", "esbmc_unavailable", "candidate_not_found",
        "synth_failed",
    }
    partial = any(result.classification in incomplete for result in results)
    capture_telemetry()
    telemetry_events = checkpoint["telemetry_events"]
    telemetry_summary = _summarize_v2_telemetry(telemetry_events)
    _write_json_atomic(output_path / "llm_telemetry.json", telemetry_events)
    _write_json_atomic(
        report_path,
        {
            "config": config,
            "coverage": {
                "status": "partial" if partial else "complete",
                "stage": "synthesis" if partial else "complete",
                "planned_hypotheses": len(candidates),
                "evaluated_hypotheses": len(results),
            },
            "detection": {
                "evaluated": args.v2_stage == "end-to-end",
                "oracle_seeded": args.v2_stage == "synthesis",
                "analyzed_units": analyzed_units,
                "hypotheses": len(candidates),
                "failed_units": len(detection_errors),
                "errors": detection_errors,
                "candidates": [
                    {
                        "file": c.file, "function": c.function,
                        "category": c.category, "expression": c.expression,
                    }
                    for c in candidates
                ],
                "rejected_findings": rejected_findings,
            },
            "summary": summary,
            "telemetry": telemetry_summary,
            "evaluation": (
                evaluate_v2_results(
                    candidates=candidates,
                    results=results,
                    ground_truth_path=args.ground_truth,
                    evaluated_sources=input_paths,
                    rejected_findings=rejected_findings,
                    evaluate_detection=args.v2_stage == "end-to-end",
                )
                if args.ground_truth
                else None
            ),
            "results": [r.to_dict() for r in results],
        },
    )
    print(f"\nRelatório JSON: {report_path}")
    checkpoint["status"] = "partial_synthesis" if partial else "complete"
    _write_json_atomic(checkpoint_path, checkpoint)
    if partial:
        print("Execução V2 parcial; consulte as classificações no relatório.", file=sys.stderr)
        return 2
    return 0


def _scan_summary(results) -> dict:
    from collections import Counter

    by_class = Counter(r.classification for r in results)
    by_cat: dict = {}
    for r in results:
        cat = r.candidate.category
        d = by_cat.setdefault(cat, {"total": 0, "confirmed": 0, "native": 0, "unverified": 0})
        d["total"] += 1
        if r.classification == "confirmed_native":
            d["confirmed"] += 1
            d["native"] += 1
        elif r.classification == "confirmed_on_abstraction":
            d["confirmed"] += 1
        elif r.classification == "confirmed_unverified":
            d["unverified"] += 1
    total_tokens = sum(r.synth_total_tokens or 0 for r in results)
    total_synth_seconds = sum(r.synth_seconds for r in results)
    total_esbmc_seconds = sum(r.esbmc_seconds for r in results)
    return {
        "n": len(results),
        "by_classification": dict(by_class),
        "by_category": by_cat,
        "total_synth_tokens": total_tokens,
        "total_synth_seconds": round(total_synth_seconds, 3),
        "total_esbmc_seconds": round(total_esbmc_seconds, 3),
        "mean_attempts": round(
            sum(r.attempts for r in results) / max(1, len(results)), 2
        ),
    }




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
        "v2":         mode_v2,
    }
    return dispatch[args.mode](args)




if __name__ == "__main__":
    raise SystemExit(main())
