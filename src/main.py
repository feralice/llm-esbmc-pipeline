"""
main.py — Pipeline LLM + AST + ESBMC para verificação de bugs em Python.


Modos de execução:
  hybrid      Fluxo principal: LLM detecta → gera harness → ESBMC confirma.
  benchmark   Benchmark V2 end-to-end com métricas vs ground truth.
  scan        Varre um repositório: grafo de chamadas, detecção por função, motor verify.


Exemplos:
  python src/main.py --mode hybrid      --input dataset/bugs_reais/funcao_com_bug --backend codex
  python src/main.py --mode benchmark   --input dataset/bugs_reais/funcao_com_bug --ground-truth dataset/bugs_reais/ground_truths.json --backend codex --synth-backend codex
  python src/main.py --mode scan --input <repo> --backend codex --scan-limit 20 --output-dir artifacts/scan [--yes]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")


from research_pipeline.dataset_audit import match_unit
from research_pipeline.verification.esbmc_runner import DEFAULT_ESBMC
from research_pipeline.llm.backends.factory import (
    _DEFAULT_MODEL,
    _GEMINI_OPENAI_BASE_URL,
    Backend,
    build_analyzer,
)
from research_pipeline.llm.example_pool import load_example_pool
from research_pipeline.llm.prompts import (
    load_system_prompt,
    set_context_sources,
    set_example_pool,
)
from research_pipeline.llm.schema import v2_findings_schema
from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan.pipeline import execute_scan, plan_scan
from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.capabilities import resolve_rules
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.llm_client import LLMClient
from research_pipeline.verify.agent_arm import make_agent, run_agent_fallback
from research_pipeline.verify.levels import consolidate, level_summary
from research_pipeline.verify.healing import HEAL_MODES, build_healer
from research_pipeline.verify.loop import run_verify
from research_pipeline.v2_evaluator import evaluate_detection
from research_pipeline.verify.report import evaluate_verify, summarize
from research_pipeline.verify.rules import ALL_RULES

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
        choices=["hybrid", "benchmark", "scan"],
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
            "No modo scan, um único diretório de repositório."
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
        choices=["openai", "anthropic", "ollama", "google", "codex", "claude_cli"],
        default=None,
        help="Backend LLM. Inferido automaticamente do --model se omitido.",
    )
    parser.add_argument(
        "--synth-backend",
        choices=["openai", "ollama", "google", "codex", "claude_cli", "anthropic"],
        default=None,
        help=(
            "Backend só para a síntese de harness no modo V2 (padrão: mesmo de --backend). "
            "'google' usa a API compatível do Gemini; 'codex' chama o `codex exec` local via assinatura já paga, em vez da API "
            "OpenAI cobrada por token; 'claude_cli' chama `claude -p` local via assinatura Claude já paga, sem precisar de "
            "OPENAI_API_KEY/GEMINI_API_KEY."
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
        default=20,
        help="Bound de unwinding para o ESBMC (teto do --max-k-step incremental). (padrão: 20)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=60,
        help="Timeout em segundos para cada chamada ao ESBMC. (padrão: 60)",
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
            "Ground truth para comparação (obrigatório no modo benchmark). "
            "Informe dataset/bugs_reais/ground_truths.json; "
            "ele é lido somente depois das chamadas às LLMs e ao ESBMC."
        ),
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
        "--agent-fallback",
        action="store_true",
        help="Motor verify: quando o harness determinístico não chega a um veredito do ESBMC, tenta o "
             "agente (Claude Code + plugin ESBMC, assinatura do Claude Code); o resultado é refeito pelo pipeline.",
    )
    parser.add_argument(
        "--agent-backend", default="claude", choices=["claude", "openai", "google", "ollama", "claude_cli", "codex", "anthropic"],
        help="Agente do nível 2: 'claude' é o Claude Code com o plugin ESBMC; os outros fazem o mesmo ciclo por API "
             "(qualquer pessoa reproduz sem assinatura do Claude; 'ollama' usa modelo local).",
    )
    parser.add_argument("--agent-model", default=None, help="Modelo do agente (padrão: o do Claude Code, ou gpt-4o-mini).")
    parser.add_argument("--agent-timeout", type=int, default=900, help="Segundos por sessão do agente (padrão: 900).")
    parser.add_argument(
        "--verification-sources-strict",
        action="store_true",
        help="Motor verify: pula a hipótese sem arquivo em --verification-sources em vez de usar o recorte.",
    )
    parser.add_argument(
        "--spec-strategy",
        choices=["repair", "resample"],
        default="repair",
        help="Motor verify: 'repair' mostra o erro anterior à LLM; 'resample' faz amostras independentes "
             "com o mesmo orçamento (linha de base do reparo).",
    )
    parser.add_argument(
        "--no-capability-probes",
        dest="capability_probes",
        action="store_false",
        help="Motor verify: não roda as sondas de capacidade do ESBMC; todas as regras de reescrita "
             "ficam ligadas (para reproduzir uma rodada congelada).",
    )
    parser.add_argument(
        "--capability-cache",
        default="artifacts/esbmc_capabilities",
        metavar="DIR",
        help="Motor verify: cache das sondas, uma entrada por binário, flags e versão do ESBMC.",
    )
    parser.add_argument(
        "--heal",
        choices=list(HEAL_MODES),
        default="none",
        help="Motor verify: self-healing quando o ESBMC não chega a veredito; 'error' devolve a mensagem do ESBMC "
             "ao LLM, 'error+kb' também o README e os testes de regressão do checkout do ESBMC",
    )
    parser.add_argument("--heal-rounds", type=int, default=3, help="Rodadas de self-healing por hipótese")
    parser.add_argument(
        "--spec-context",
        choices=["none", "callers"],
        default="callers",
        help="Motor verify: 'callers' mostra ao LLM do spec as chamadas da função e os fatos de uso das entradas, "
             "e rejeita tipo contrariado pelo uso; 'none' é o pedido de antes (linha de base).",
    )
    parser.add_argument(
        "--verification-sources",
        default=None,
        metavar="DIR",
        help="Motor verify: verifica no arquivo de mesmo nome deste diretório (ex.: arquivo_com_bug) quando existir.",
    )
    parser.add_argument(
        "--fixed-sources",
        default=None,
        metavar="DIR",
        help="Motor verify: versões corrigidas (ex.: arquivo_corrigido) para o controle do oráculo de valor; "
             "o LLM nunca as vê.",
    )
    parser.add_argument(
        "--context-sources",
        default=None,
        metavar="DIR",
        help="Variante A11: lê o contexto (imports, classe, chamadores) do arquivo de mesmo nome deste "
             "diretório; padrão: --verification-sources.",
    )
    parser.add_argument(
        "--v2-variants",
        default="",
        metavar="A1,A2",
        help="Variantes do prompt V2 (research_pipeline/llm/prompt_variants.py), aplicadas em ordem.",
    )
    parser.add_argument(
        "--example-pool",
        default=str(REPO_ROOT / "dataset/bugs_reais/ground_truths.json"),
        metavar="JSON",
        help="Variante A13: gabarito de onde saem os exemplos (funções em funcao_com_bug/ ao lado dele).",
    )
    parser.add_argument("--example-k", type=_positive_int, default=3, metavar="K",
                        help="Variante A13: quantos exemplos por função (padrão: 3).")
    parser.add_argument(
        "--v2-stage",
        choices=["end-to-end", "synthesis", "detection"],
        default="end-to-end",
        help=(
            "Modo V2: 'end-to-end' detecta e sintetiza; 'synthesis' usa "
            "hipóteses conhecidas somente para avaliar a geração de harness "
            "isoladamente (requer --ground-truth); 'detection' para depois da "
            "detecção, para comparar prompts sem gastar verificação."
        ),
    )
    parser.add_argument("--scan-limit", type=_positive_int, default=None, metavar="N",
                        help="Modo scan: analisa só as N primeiras funções do ranking (padrão: todas).")
    parser.add_argument("--scan-include-tests", action="store_true",
                        help="Modo scan: inclui arquivos e pastas de teste no grafo e na seleção.")
    parser.add_argument("--yes", action="store_true",
                        help="Modo scan: confirma o gasto com a LLM; sem ele, só monta o grafo e a seleção.")
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
    return paths








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


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _save_checkpoint(path: Path, payload: object) -> None:
    """Best-effort checkpoint save inside a per-unit loop.

    A transient OSError here (e.g. ENOMEM) must not abort the whole batch:
    the data is still in memory and the next iteration will retry the save.
    """
    try:
        _write_json_atomic(path, payload)
    except OSError as exc:
        print(f"Aviso: falha transitória ao salvar checkpoint ({exc}); seguindo sem persistir.", file=sys.stderr)


def _v2_candidate_dict(candidate: Candidate) -> dict[str, str]:
    return candidate.to_dict()


def _v2_detection_input_paths(
    ground_truth_path: str | Path, input_paths: list[Path]
) -> list[Path]:
    """Return only V2 sources whose category is inferable without the patch."""
    gt_path = Path(ground_truth_path)
    manifest_path = gt_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    excluded = set(
        str(item)
        for item in manifest.get("evaluation_policy", {}).get(
            "patch_context_items", []
        )
    )
    excluded_paths = {
        str((manifest_path.parent / item["detection_file"]).resolve())
        for item in manifest.get("items", [])
        if str(item.get("id")) in excluded
    }
    return [path for path in input_paths if str(path.resolve()) not in excluded_paths]


def _load_v2_oracle_candidates(
    ground_truth_path: str | Path, input_paths: list[Path]
) -> list[Candidate]:
    """Load synthesis-only hypotheses without exposing human harness contents."""
    gt_path = Path(ground_truth_path)
    manifest_path = gt_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = {str(path.resolve()) for path in input_paths}
    candidates: list[Candidate] = []
    for item in manifest.get("items", []):
        detection = manifest_path.parent / item["detection_file"]
        if str(detection.resolve()) not in allowed:
            continue
        declared_function = str(item["function"])
        units = preprocess_file(detection)
        selected_function = declared_function
        if units:
            matched_unit = (
                match_unit(units, declared_function, str(item.get("expression", "")))
                or units[0]
            )
            # Keep the manifest label for module-level cases; it may describe
            # a group of constants rather than a Python function name.
            if matched_unit.kind != "module":
                selected_function = matched_unit.qualname
        for category in item.get("categories", []):
            candidates.append(
                Candidate(
                    file=str(detection),
                    function=selected_function,
                    category=str(category),
                    expression=str(item.get("expression", "")),
                    note="Oracle-seeded hypothesis for synthesis-only evaluation.",
                )
            )
    return candidates


def _v2_fingerprint(config: dict, input_paths: list[Path]) -> dict:
    variants = tuple(config.get("v2_variants", ()))
    fingerprint = {
        "config": config,
        "sources": {
            str(path.resolve()): sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
        "detector_prompt": sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/system_prompt_v2.txt").read_bytes()
        ).hexdigest(),
        "detector_schema": sha256(json.dumps(v2_findings_schema(variants), sort_keys=True).encode()).hexdigest(),
        "spec_prompt": sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/input_spec_prompt.txt").read_bytes()
        ).hexdigest(),
    }
    # Only for A13 onwards, which keeps the fingerprint of earlier variants as it was. That no longer makes old
    # checkpoints resume: config always carries spec_context and the spec prompt changed on 16/10.
    if {"A13", "A14", "A15"} & set(variants):
        system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants)
        fingerprint["detector_system_prompt"] = sha256(system.encode()).hexdigest()
    if "A15" in variants:
        fingerprint["value_prompt"] = sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/value_property_prompt.txt").read_bytes()
        ).hexdigest()
    if "A13" in variants:
        fingerprint["example_pool"] = sha256(Path(config["example_pool"]).read_bytes()).hexdigest()
    return fingerprint


def _summarize_v2_telemetry(events: list[dict]) -> dict:
    by_stage: dict[str, dict[str, float | int]] = {}
    for event in events:
        stage = str(event["stage"])
        totals = by_stage.setdefault(
            stage,
            {
                "calls": 0, "failed_calls": 0, "tokens": 0, "prompt_tokens": 0,
                "cached_tokens": 0, "calls_with_cache_data": 0, "seconds": 0.0,
                "localization_calls": 0, "classification_calls": 0,
            },
        )
        totals["calls"] += 1
        totals["failed_calls"] += int(event.get("status") != "success")
        if event.get("analysis_stage") == "localize":
            totals["localization_calls"] += 1
        elif event.get("analysis_stage") == "classify":
            totals["classification_calls"] += 1
        totals["tokens"] += int(event.get("total_tokens") or 0)
        totals["prompt_tokens"] += int(event.get("prompt_tokens") or 0)
        totals["seconds"] += float(event.get("duration_seconds") or 0.0)
        cached = event.get("cached_tokens")
        if isinstance(cached, int):
            totals["calls_with_cache_data"] += 1
            totals["cached_tokens"] += cached
    for totals in by_stage.values():
        totals["seconds"] = round(float(totals["seconds"]), 3)
        # 0 calls_with_cache_data means no event in this stage reported the
        # field (e.g. Ollama backend) -- report the rate as unknown, not 0%.
        totals["cache_hit_rate"] = (
            round(totals["cached_tokens"] / totals["prompt_tokens"], 4)
            if totals["calls_with_cache_data"] and totals["prompt_tokens"] > 0
            else None
        )
    return by_stage


def _summarize_detection_trace(trace: list[dict]) -> dict:
    """Aggregate auditable detection counts without inventing measurements."""
    summary = {
        "units": len(trace),
        "located_candidates": 0,
        "classified_candidates": 0,
        "rejected_candidates": 0,
        "localization_failures": 0,
        "classification_failures": 0,
    }
    for item in trace:
        summary["located_candidates"] += int(item.get("located_candidates", 0) or 0)
        summary["classified_candidates"] += int(item.get("classified_candidates", 0) or 0)
        summary["rejected_candidates"] += int(item.get("rejected_candidates", 0) or 0)
        if item.get("failure_stage") == "localize":
            summary["localization_failures"] += 1
        elif item.get("failure_stage") == "classify":
            summary["classification_failures"] += 1
    return summary


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------


def mode_benchmark(args: argparse.Namespace) -> int:
    """Run the V2 end-to-end benchmark under the stable benchmark name."""
    if not args.ground_truth:
        print(
            "O benchmark V2 requer --ground-truth com o manifesto V2.",
            file=sys.stderr,
        )
        return 1
    args.v2_stage = "end-to-end"
    return mode_v2(args)


# The release build; ~/.local/bin/esbmc may shadow it with a development build.
_VERIFY_DEFAULT_ESBMC = DEFAULT_ESBMC


def _esbmc_version(command: list[str]) -> str:
    import subprocess
    try:
        completed = subprocess.run([*command[:1], "--version"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    lines = (completed.stdout or completed.stderr or "").strip().splitlines()
    return lines[0] if lines else ""


def _agent_fallback(args: argparse.Namespace, results: list[dict], output_path: Path, checkpoint: dict,
                    checkpoint_path: Path) -> list[dict]:
    """Second level: the agent tries each hypothesis the engine left without an ESBMC verdict."""
    esbmc = args.esbmc_command or [DEFAULT_ESBMC]
    agent, skill = make_agent(args.agent_backend, model=args.agent_model, esbmc=esbmc[0], bound=args.bound,
                              base_url=args.ollama_base_url if args.agent_backend == "ollama" else None)
    return run_agent_fallback(
        results, run_agent=agent, skill=skill, work_dir=output_path / "agent_cases",
        esbmc_command=esbmc, bound=args.bound, timeout_seconds=args.timeout, agent_timeout=args.agent_timeout,
        sources=Path(args.verification_sources) if args.verification_sources else None,
        state=checkpoint, save=lambda: _save_checkpoint(checkpoint_path, checkpoint),
        config={"backend": args.agent_backend, "model": args.agent_model, "bound": args.bound,
                "timeout": args.timeout, "esbmc": esbmc})


def _resumable_results(checkpoint: dict) -> dict[int, dict]:
    """Saved verdicts a resume keeps; PIPELINE_ERROR (network, usage limit) is retried instead."""
    return {int(i): d for i, d in checkpoint.get("verify_results", {}).items() if d.get("verdict") != "PIPELINE_ERROR"}


def _mode_v2_verify(
    args: argparse.Namespace, *, candidates, llm, output_path: Path, config: dict, checkpoint: dict,
    checkpoint_path: Path, capture_telemetry, input_paths, rejected_findings, detection: dict,
) -> int:
    hypotheses = [BugHypothesis.from_candidate(c) for c in candidates]
    print(f"\nModo V2 (motor verify): {len(hypotheses)} hipótese(s) → especificação de entrada com {llm.model}")

    def save(index: int, data: dict) -> None:
        checkpoint.setdefault("verify_results", {})[str(index)] = data
        capture_telemetry()
        _save_checkpoint(checkpoint_path, checkpoint)

    capabilities = checkpoint.get("capabilities")
    if capabilities is None:
        # A batch keeps one rule set and a resume reuses it. A checkpoint with results but no rule set keeps
        # every rule on; none exists today (pre-16/10 checkpoints fail the fingerprint), the branch is a guard.
        # The probes run what check() runs: without --esbmc-command that is `esbmc` from PATH.
        capabilities = resolve_rules(args.esbmc_command or ["esbmc"], cache_dir=Path(args.capability_cache),
                                     enabled=args.capability_probes,
                                     resumed=bool(checkpoint.get("verify_results")),
                                     bound=args.bound, timeout_seconds=min(args.timeout, 60))
        checkpoint["capabilities"] = capabilities
        _save_checkpoint(checkpoint_path, checkpoint)
    if capabilities["disabled_rules"]:
        print("Regras desligadas pelas sondas: " + ", ".join(capabilities["disabled_rules"]))
    try:
        results = run_verify(
            hypotheses,
            llm=llm,
            output_dir=output_path,
            verification_sources=Path(args.verification_sources) if args.verification_sources else None,
            completed=_resumable_results(checkpoint),
            on_result=save,
            esbmc_command=args.esbmc_command,
            bound=args.bound,
            timeout_seconds=args.timeout,
            strategy=args.spec_strategy,
            spec_context=args.spec_context,
            strict_sources=args.verification_sources_strict,
            fixed_sources=Path(args.fixed_sources) if args.fixed_sources else None,
            rules=ALL_RULES - frozenset(capabilities["disabled_rules"]),
            healer=build_healer(args.heal, llm=llm, esbmc_command=args.esbmc_command),
            heal_rounds=args.heal_rounds,
        )
    except KeyboardInterrupt:
        checkpoint["status"] = "interrupted"
        checkpoint["interrupted_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint["interruption_reason"] = "keyboard_interrupt"
        capture_telemetry()
        _write_json_atomic(checkpoint_path, checkpoint)
        print("Execução V2 interrompida; retome com --resume.", file=sys.stderr)
        return 2
    agent_results = _agent_fallback(args, results, output_path, checkpoint, checkpoint_path) if args.agent_fallback else []
    capture_telemetry()
    checkpoint["status"] = "complete"
    _write_json_atomic(checkpoint_path, checkpoint)
    telemetry_events = checkpoint["telemetry_events"]
    _write_json_atomic(output_path / "llm_telemetry.json", telemetry_events)
    report_path = Path(args.report) if args.report else output_path / "v2_verify_report.json"
    summary = summarize(results)
    level_rows = consolidate(results, agent_results)
    levels = level_summary(level_rows)
    _write_json_atomic(report_path, {
        "config": {**config, "esbmc_version": _esbmc_version(args.esbmc_command or ["esbmc"]),
                   "capabilities": capabilities},
        "detection": detection,
        "verification": summary,
        "telemetry": _summarize_v2_telemetry(telemetry_events),
        "evaluation": (
            evaluate_verify(results, candidates, args.ground_truth, input_paths, rejected_findings)
            if args.ground_truth and args.v2_stage == "end-to-end" else None
        ),
        "results": results,
        "agent_results": agent_results,
        "levels": {"summary": levels, "rows": level_rows},
    })
    print("\nVereditos:", {k: v for k, v in summary["by_verdict"].items() if v})
    print(f"Níveis: {levels['by_level']}; veredito do ESBMC em {levels['esbmc_verdict']}/{levels['hypotheses']}, "
          f"{levels['confirmed']} confirmado(s); só LLM por motivo: "
          f"{ {k: v for k, v in levels['llm_only_by_limit'].items() if v} }")
    print(f"Relatório JSON: {report_path}")
    return 0


def _build_synthesizer(args: argparse.Namespace, synth_backend: str, synth_model: str,
                       openai_key: str | None, google_key: str | None) -> LLMClient:
    return LLMClient(
        backend=synth_backend,
        model=synth_model,
        api_key=(openai_key if synth_backend == "openai" else google_key)
        if synth_backend in {"openai", "google"}
        else None if synth_backend == "anthropic"
        else "ollama",
        base_url=(args.ollama_base_url or "http://localhost:11434/v1")
        if synth_backend == "ollama"
        else _GEMINI_OPENAI_BASE_URL
        if synth_backend == "google"
        else "https://api.openai.com/v1/responses",
        timeout_seconds=args.llm_timeout,
        request_delay=4.0 if synth_backend == "google" else 0.0,
    )


def mode_scan(args: argparse.Namespace) -> int:
    root = Path(args.input[0])
    if len(args.input) != 1 or not root.is_dir():
        print("O modo scan recebe um único diretório de repositório em --input.", file=sys.stderr)
        return 1
    plan = plan_scan(root, args.output_dir or _default_output_dir("scan"), limit=args.scan_limit,
                     include_tests=args.scan_include_tests)
    if not args.yes:
        print(f"Simulação: nenhuma chamada à LLM. Seleção em {plan.output_dir / 'scan_selection.json'}; "
              "rode de novo com --yes para gastar as chamadas.")
        return 0
    backend: Backend = args.backend or _infer_backend(args.model or "")
    model = "" if backend in {"codex", "claude_cli"} and not args.model else _resolve_model(args.model, backend)
    synth_backend = args.synth_backend or backend
    synth_model = args.synth_model or ("" if synth_backend in {"codex", "claude_cli"}
                                       else model if synth_backend == backend else _DEFAULT_MODEL[synth_backend])
    anthropic_key, openai_key, google_key = _resolve_keys(args)
    try:
        analyzer = build_analyzer(backend=backend, llm_model=model, openai_api_key=openai_key,
                                  anthropic_api_key=anthropic_key, google_api_key=google_key,
                                  ollama_base_url=args.ollama_base_url, timeout_seconds=args.llm_timeout,
                                  include_smells=False, v2_detection=True, v2_variants=plan.variants)
        spec_llm = _build_synthesizer(args, synth_backend, synth_model, openai_key, google_key)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    if args.esbmc_command is None and Path(_VERIFY_DEFAULT_ESBMC).exists():
        args.esbmc_command = [_VERIFY_DEFAULT_ESBMC]
    try:
        report = execute_scan(plan, analyzer=analyzer, spec_llm=spec_llm, resume=args.resume,
                              esbmc_command=args.esbmc_command, bound=args.bound, timeout_seconds=args.timeout,
                              strategy=args.spec_strategy, spec_context=args.spec_context, graph=plan.graph,
                              healer=build_healer(args.heal, llm=spec_llm, esbmc_command=args.esbmc_command,
                                                  graph=plan.graph),
                              heal_rounds=args.heal_rounds)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 2 if report["detection"]["failed"] else 0


def mode_v2(args: argparse.Namespace) -> int:
    variants = tuple(v for v in args.v2_variants.split(",") if v)
    input_paths = _resolve_input_paths(args.input)
    if not input_paths:
        print("Nenhum arquivo Python encontrado para a V2.", file=sys.stderr)
        return 1
    if args.v2_stage == "synthesis" and not args.ground_truth:
        print("--v2-stage synthesis requer --ground-truth.", file=sys.stderr)
        return 1
    prompt_sources = {Path(d).resolve() for d in (args.verification_sources, args.context_sources) if d}
    if args.fixed_sources and Path(args.fixed_sources).resolve() in prompt_sources:
        # The fixed version must never reach an LLM prompt; those two directories feed the prompts.
        print("--fixed-sources não pode ser o diretório de --verification-sources nem de --context-sources.",
              file=sys.stderr)
        return 1
    all_input_paths = input_paths
    if args.v2_stage in ("end-to-end", "detection") and args.ground_truth:
        input_paths = _v2_detection_input_paths(args.ground_truth, input_paths)
        if not input_paths:
            print("Nenhum arquivo V2 elegível sem contexto do patch.", file=sys.stderr)
            return 1

    backend: Backend = args.backend or _infer_backend(args.model or "")
    model = _resolve_model(args.model, backend)
    if backend in {"codex", "claude_cli"} and not args.model:
        model = ""
    if backend not in {"openai", "ollama", "google", "codex", "claude_cli"}:
        print(
            "O modo V2 detecta via OpenAI, Gemini, Ollama, Codex CLI ou Claude CLI.",
            file=sys.stderr,
        )
        return 1

    synth_backend = args.synth_backend or backend
    # 'model' is resolved against OpenAI/Ollama naming; codex/claude_cli have
    # their own model namespace, so only fall back to it when synth_backend
    # wasn't overridden.
    synth_model = args.synth_model or (
        "" if args.synth_backend in {"codex", "claude_cli"}
        else model or _DEFAULT_MODEL.get(synth_backend, "")
    )

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
            include_smells=False,
            v2_detection=True,
            v2_variants=variants,
        )
        context_sources = args.context_sources or args.verification_sources
        set_context_sources(Path(context_sources) if context_sources else None)
        if "A13" in variants:
            set_example_pool(load_example_pool(Path(args.example_pool)), k=args.example_k)
        else:
            set_example_pool(None)
        synthesizer = _build_synthesizer(args, synth_backend, synth_model, openai_key, google_key)
    except (ValueError, OSError, KeyError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    output_dir = args.output_dir or _default_output_dir("v2")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if args.esbmc_command is None and Path(_VERIFY_DEFAULT_ESBMC).exists():
        args.esbmc_command = [_VERIFY_DEFAULT_ESBMC]
    config = {
        "model": model,
        "backend": backend,
        "synth_backend": synth_backend,
        "synth_model": synth_model,
        "v2_stage": args.v2_stage,
        "v2_variants": list(variants),
        "input_files": [str(path.resolve()) for path in input_paths],
        "excluded_patch_context_files": len(all_input_paths) - len(input_paths),
        "verification_sources": args.verification_sources,
        "verification_sources_strict": args.verification_sources_strict,
        "context_sources": args.context_sources or args.verification_sources,
        "spec_strategy": args.spec_strategy,
        "spec_context": args.spec_context,
        "bound": args.bound,
        "timeout": args.timeout,
        "llm_timeout": args.llm_timeout,
        "esbmc_command": args.esbmc_command or ["esbmc"],
    }
    if args.fixed_sources:
        # Only when given, so a run without it keeps the same fingerprint (no pre-16/10 checkpoint resumes).
        config["fixed_sources"] = args.fixed_sources
    if "A13" in variants:
        config["example_pool"] = str(Path(args.example_pool).resolve())
        config["example_k"] = args.example_k
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
            "detection_trace": [],
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

    candidates: list[Candidate] = (
        _load_v2_oracle_candidates(args.ground_truth, input_paths)
        if args.v2_stage == "synthesis"
        else []
    )
    rejected_findings: list[dict[str, str]] = []
    # Rebuild the trace from per-unit checkpoint entries so --resume cannot
    # append the same trace twice when the checkpoint already contains an
    # aggregate copy.
    detection_trace: list[dict] = []
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
                candidates.extend(Candidate.from_dict(item) for item in saved_unit["candidates"])
                rejected_findings.extend(saved_unit.get("rejected_findings", []))
                if saved_unit.get("trace"):
                    detection_trace.append(saved_unit["trace"])
                print(f"  [{file_index}/{len(input_paths)}] Retomada: {file_path.name}::{unit.qualname}")
                continue
            print(f"  [{file_index}/{len(input_paths)}] Analisando {file_path.name}::{unit.qualname}...")
            try:
                findings = analyzer.analyze(unit)
            except Exception as exc:  # noqa: BLE001 - one API failure must not discard other units
                analyzer_trace = getattr(analyzer, "detection_trace", [])
                trace = dict(analyzer_trace[-1]) if analyzer_trace else {
                    "function": unit.qualname,
                    "strategy": "single",
                    "located_candidates": 0,
                    "classified_candidates": 0,
                    "rejected_candidates": 0,
                }
                trace.update({"error": str(exc), "failure_stage": trace.get("failure_stage", "detection")})
                detection_trace.append(trace)
                detection_errors.append(
                    {"file": str(file_path), "function": unit.qualname, "error": str(exc)}
                )
                checkpoint["detection_trace"] = detection_trace
                capture_telemetry()
                _save_checkpoint(checkpoint_path, checkpoint)
                continue
            analyzer_trace = getattr(analyzer, "detection_trace", [])
            trace = dict(analyzer_trace[-1]) if analyzer_trace else {
                "function": unit.qualname,
                "strategy": "single",
                "located_candidates": len(findings),
                "classified_candidates": len(findings),
                "rejected_candidates": 0,
            }
            unit_candidates: list[Candidate] = []
            unit_rejections: list[dict[str, str]] = []
            for finding in findings:
                # With A15 the LLM says how the bug shows; a wrong result goes to the value oracle.
                wrong_result = "A15" in variants and finding.metadata.get("failure_mode") == "resultado_errado"
                # Otherwise the LLM decides: only findings it marks formally verifiable reach ESBMC.
                if not finding.verifiable and not wrong_result:
                    unit_rejections.append(
                        {
                            "file": str(file_path),
                            "function": unit.qualname,
                            "finding_type": finding.finding_type,
                            "expression": str(finding.metadata.get("expression", "")),
                            "violated_property": str(finding.metadata.get("violated_property", "")),
                        }
                    )
                    continue
                unit_candidates.append(
                    Candidate(
                        file=str(file_path),
                        function=unit.qualname,
                        expression=str(finding.metadata.get("expression", "")),
                        note=finding.explanation,
                        violated_property=str(finding.metadata.get("violated_property", "")),
                        oracle=VALUE_ORACLE if wrong_result else "",
                    )
                )
            candidates.extend(unit_candidates)
            rejected_findings.extend(unit_rejections)
            if not analyzer_trace:
                trace["rejected_candidates"] = len(unit_rejections)
            detection_trace.append(trace)
            checkpoint["detection_units"][unit_key] = {
                "candidates": [_v2_candidate_dict(candidate) for candidate in unit_candidates],
                "rejected_findings": unit_rejections,
                "trace": trace,
            }
            checkpoint["detection_trace"] = detection_trace
            capture_telemetry()
            _save_checkpoint(checkpoint_path, checkpoint)

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
                    "trace": detection_trace,
                    "trace_summary": _summarize_detection_trace(detection_trace),
                },
                "verification": summarize([]),
                "telemetry": telemetry_summary,
                "results": [],
            },
        )
        print("Execução V2 parcial na detecção; retome com --resume.", file=sys.stderr)
        return 2

    if args.v2_stage == "detection":
        capture_telemetry()
        checkpoint["status"] = "detection_complete"
        _write_json_atomic(checkpoint_path, checkpoint)
        _write_json_atomic(output_path / "llm_telemetry.json", checkpoint["telemetry_events"])
        _write_json_atomic(
            Path(args.report) if args.report else output_path / "v2_verify_report.json",
            {
                "config": config,
                "coverage": {"status": "complete", "stage": "detection"},
                "detection": {
                    "analyzed_units": analyzed_units,
                    "hypotheses": len(candidates),
                    "failed_units": 0,
                    "errors": [],
                    "candidates": [_v2_candidate_dict(c) for c in candidates],
                    "rejected_findings": rejected_findings,
                    "trace": detection_trace,
                    "trace_summary": _summarize_detection_trace(detection_trace),
                },
                "evaluation": evaluate_detection(candidates=candidates, ground_truth_path=args.ground_truth,
                                                 evaluated_sources=input_paths, rejected_findings=rejected_findings)
                if args.ground_truth else None,
                "telemetry": _summarize_v2_telemetry(checkpoint["telemetry_events"]),
                "results": [],
            },
        )
        print(f"Detecção concluída: {len(candidates)} hipótese(s) enviada(s), "
              f"{len(rejected_findings)} segurada(s).")
        return 0

    return _mode_v2_verify(
        args,
        candidates=candidates,
        llm=synthesizer,
        output_path=output_path,
        config=config,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        capture_telemetry=capture_telemetry,
        input_paths=input_paths,
        rejected_findings=rejected_findings,
        detection={
            "evaluated": args.v2_stage == "end-to-end",
            "oracle_seeded": args.v2_stage == "synthesis",
            "analyzed_units": analyzed_units,
            "hypotheses": len(candidates),
            "failed_units": len(detection_errors),
            "candidates": [_v2_candidate_dict(c) for c in candidates],
            "rejected_findings": rejected_findings,
            "trace_summary": _summarize_detection_trace(detection_trace),
        },
    )










# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()


    dispatch = {
        "hybrid":    mode_v2,
        "benchmark": mode_benchmark,
        "scan":      mode_scan,
    }
    return dispatch[args.mode](args)




if __name__ == "__main__":
    raise SystemExit(main())
