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
import shutil
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
from research_pipeline.storage import write_json_atomic as _write_json_atomic
from research_pipeline.cli_config import resolve_model as _resolve_model, resolve_models
from research_pipeline.cli_args import build_parser, _positive_int as _positive_int, _review_score as _review_score, _CommandWords as _CommandWords
from research_pipeline.verification.esbmc_runner import DEFAULT_ESBMC
from research_pipeline.llm.backends.factory import (
    _GEMINI_OPENAI_BASE_URL,
    Backend,
    build_analyzer,
)
from research_pipeline.llm.detection_cache import make_cache
from research_pipeline.llm.prompt_routing import DEFAULT_VARIANTS, ROUTING_VERSION, route_variants
from research_pipeline.llm.example_pool import load_example_pool
from research_pipeline.llm.prompts import (
    load_system_prompt,
    set_context_sources,
    set_detection_focus,
    set_example_pool,
)
from research_pipeline.llm.rate_limit import USAGE_LIMIT_EXIT, UsageLimitReached
from research_pipeline.llm.schema import v2_findings_schema
from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan.pipeline import execute_scan, judge_smells, plan_scan
from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.capabilities import resolve_rules
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.llm_client import LLMClient
from research_pipeline.verify.agent_arm import make_agent, run_agent_fallback
from research_pipeline.verify.agent_scan import agent_verifier
from research_pipeline.verify.levels import consolidate, level_summary
from research_pipeline.verify.healing import build_healer
from research_pipeline.verify.loop import run_verify
from research_pipeline.hypothesis_cap import cap_per_function
from research_pipeline.hypothesis_review import PROMPT_PATH as REVIEW_PROMPT_PATH, review_candidates, split_by_threshold
from research_pipeline.v2_evaluator import evaluate_detection
from research_pipeline.verify.report import evaluate_verify, summarize
from research_pipeline.verify.rules import ALL_RULES

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------










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




def _resolve_keys(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key    = args.openai_api_key    or os.environ.get("OPENAI_API_KEY")
    google_key    = args.google_api_key    or os.environ.get("GEMINI_API_KEY")
    return anthropic_key, openai_key, google_key




def _default_output_dir(mode: str) -> str:
    return str(REPO_ROOT / "artifacts" / mode)




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
    # The composed prompt covers every v2_variants/*.txt a variant reads; with no variant it is system_prompt_v2.txt.
    if variants:
        system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants)
        fingerprint["detector_system_prompt"] = sha256(system.encode()).hexdigest()
    if config.get("review_threshold") is not None:
        fingerprint["review_prompt"] = sha256(REVIEW_PROMPT_PATH.read_bytes()).hexdigest()
    if "A15" in variants:
        fingerprint["value_prompt"] = sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/value_property_prompt.txt").read_bytes()
        ).hexdigest()
    if "A13" in variants:
        fingerprint["example_pool"] = sha256(Path(config["example_pool"]).read_bytes()).hexdigest()
    return fingerprint


def _summarize_v2_telemetry(events: list[dict]) -> dict:
    by_stage: dict[str, dict[str, float | int | None]] = {}
    for event in events:
        stage = str(event["stage"])
        totals = by_stage.setdefault(
            stage,
            {
                "calls": 0, "failed_calls": 0, "tokens": 0, "prompt_tokens": 0,
                "cached_tokens": 0, "calls_with_cache_data": 0, "seconds": 0.0,
                "localization_calls": 0, "classification_calls": 0, "cost_usd": None, "calls_without_cost": 0,
                "cost_reported_usd": None, "cost_estimated_usd": None, "billed_usd": None,
                "cache_creation_tokens": 0, "usage_limit_calls": 0, "timeout_calls": 0, "retried_calls": 0,
            },
        )
        totals["calls"] += 1
        cost = event.get("cost_usd")
        if isinstance(cost, (int, float)):
            totals["cost_usd"] = round((totals["cost_usd"] or 0.0) + cost, 6)
            source_key = "cost_reported_usd" if event.get("cost_source") == "cli_reported" else "cost_estimated_usd"
            totals[source_key] = round((totals[source_key] or 0.0) + cost, 6)
        else:
            totals["calls_without_cost"] += 1
        billed = event.get("billed_usd")
        if isinstance(billed, (int, float)):
            totals["billed_usd"] = round((totals["billed_usd"] or 0.0) + billed, 6)
        totals["failed_calls"] += int(event.get("status") != "success")
        totals["usage_limit_calls"] += int(event.get("error_kind") == "usage_limit")
        totals["retried_calls"] += int((event.get("attempts") or 1) > 1)
        totals["timeout_calls"] += int(event.get("error_kind") == "timeout")
        totals["cache_creation_tokens"] += int(event.get("cache_creation_tokens") or 0)
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


# The configured wrapper; LLM_ESBMC overrides the default master checkout.
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
    agent, skill = make_agent(args.agent_backend, model=args.agent_model, esbmc=esbmc[0] if args.agent_backend in {"claude", "codex"} else esbmc, bound=args.bound,
                              esbmc_timeout=args.timeout, llm_timeout=args.llm_timeout,
                              base_url=args.ollama_base_url if args.agent_backend == "ollama" else None)
    return run_agent_fallback(
        results, run_agent=agent, skill=skill, work_dir=output_path / "agent_cases",
        esbmc_command=esbmc, bound=args.bound, timeout_seconds=args.timeout, agent_timeout=args.agent_timeout,
        sources=Path(args.verification_sources) if args.verification_sources else None,
        state=checkpoint, save=lambda: _save_checkpoint(checkpoint_path, checkpoint),
        config={"backend": args.agent_backend, "model": args.agent_model, "bound": args.bound,
                "timeout": args.timeout, "esbmc": esbmc})


def _apply_review(candidates, sources, llm, checkpoint, checkpoint_path, threshold):
    """Second-pass scores and the drop decision live in the checkpoint, so a resume repeats neither."""
    state = checkpoint.setdefault("review", {"scores": {}})
    if "dropped" not in state:
        try:
            reviews = review_candidates(candidates, sources, llm, state["scores"])
        finally:
            _save_checkpoint(checkpoint_path, checkpoint)
        _, dropped = split_by_threshold(candidates, reviews, threshold)
        state["dropped"] = [
            {**_v2_candidate_dict(c), "score": r.score, "guard_found": r.guard_found, "feasible": r.feasible,
             "explanation": r.explanation} for c, r in dropped]
        state["errors"] = sum(bool(r.error) for r in reviews)
        _save_checkpoint(checkpoint_path, checkpoint)
    dropped_ids = {(d["file"], d["function"], d["expression"], d["oracle"]) for d in state["dropped"]}
    kept = [c for c in candidates if (c.file, c.function, c.expression, c.oracle) not in dropped_ids]
    return kept, {"review_dropped": state["dropped"], "review_errors": state["errors"]}


def _usage_limit_message(exc: UsageLimitReached, checkpoint_path: Path) -> str:
    return (f"Limite de uso da LLM atingido: {exc}\nExecução parada; checkpoint salvo em {checkpoint_path}. "
            "Retome com --resume depois que o limite renovar.")


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
            healer=build_healer(args.heal, llm=llm, esbmc_command=args.esbmc_command,
                                auto_lessons=args.auto_lessons, run_dir=output_path),
            heal_rounds=args.heal_rounds,
            workers=args.workers,
            heal_triage=args.heal_triage,
        )
        agent_results = (_agent_fallback(args, results, output_path, checkpoint, checkpoint_path)
                         if args.agent_fallback else [])
    except (KeyboardInterrupt, UsageLimitReached) as exc:
        limit = isinstance(exc, UsageLimitReached)
        checkpoint["status"] = "interrupted"
        checkpoint["interrupted_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint["interruption_reason"] = "usage_limit" if limit else "keyboard_interrupt"
        capture_telemetry()
        _write_json_atomic(checkpoint_path, checkpoint)
        _schedule_automatic_maintenance(args, output_path)
        if limit:
            print(_usage_limit_message(exc, checkpoint_path), file=sys.stderr)
            return USAGE_LIMIT_EXIT
        print("Execução V2 interrompida; retome com --resume.", file=sys.stderr)
        return 2
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
    _schedule_automatic_maintenance(args, output_path)
    return 0


def _schedule_automatic_maintenance(args: argparse.Namespace, run_dir: Path) -> None:
    """Inicia o processador de propostas sem bloquear a rodada de análise."""
    if not args.auto_lessons:
        return
    from research_pipeline.maintenance.execution import start_automatic_worker

    try:
        result = start_automatic_worker(REPO_ROOT, Path(run_dir), args.esbmc_command or ["esbmc"],
                                        Path("/mnt/e/manutencao_automatica"))
        if result.get("scheduled") or result.get("started"):
            print(f"Avaliação automática das lições agendada; log previsto se houver propostas: {result['log']}")
    except (OSError, ValueError) as exc:
        print(f"Não foi possível iniciar avaliação automática: {exc}", file=sys.stderr)


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
    try:
        plan = plan_scan(root, args.output_dir or _default_output_dir("scan"), limit=args.scan_limit,
                         include_tests=args.scan_include_tests, rank=args.scan_rank,
                         smells=args.scan_smells, focus=args.scan_focus,
                         include_examples=args.scan_include_examples, only=tuple(args.scan_only),
                         caller_depth=args.scan_caller_depth, repository_context=args.scan_repository_context)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    set_detection_focus(plan.focus)
    if args.scan_smells and not args.yes:
        smells = json.loads((plan.output_dir / "scan_smells.json").read_text(encoding="utf-8"))
        print(f"Smells: {len(smells['architecture'])} de arquitetura; {len(smells['feature_envy'])} candidato(s) a "
              f"Feature Envy e {len(smells['tool_candidates'])} apontado(s) pelo ruff, que a LLM filtra com --yes "
              "(uma chamada por Feature Envy e por trecho de código do ruff).")
    if not args.yes:
        print(f"Simulação: nenhuma chamada à LLM. Seleção em {plan.output_dir / 'scan_selection.json'}; "
              "rode de novo com --yes para gastar as chamadas.")
        return 0
    backend: Backend = args.backend or _infer_backend(args.model or "")
    model, synth_backend, synth_model = resolve_models(backend, args.model, args.synth_backend, args.synth_model)
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
    verifier = {}
    if args.scan_verify == "agent":
        esbmc = args.esbmc_command or [_VERIFY_DEFAULT_ESBMC]
        if not shutil.which(esbmc[0]):
            print(f"Erro: o ESBMC do agente não existe ou não é executável: {esbmc[0]}", file=sys.stderr)
            return 1
        has_tools = args.agent_backend in {"claude", "codex"}
        agent, skill = make_agent(args.agent_backend, model=args.agent_model, esbmc=esbmc[0] if args.agent_backend in {"claude", "codex"} else esbmc, bound=args.bound,
                              esbmc_timeout=args.timeout, llm_timeout=args.llm_timeout,
                                  log_rounds=has_tools, graph_tool=has_tools,
                                  base_url=args.ollama_base_url if args.agent_backend == "ollama" else None)
        verifier["verify"] = agent_verifier(agent, esbmc_command=esbmc, bound=args.bound,
                                            timeout_seconds=args.timeout, agent_timeout=args.agent_timeout,
                                            graph_tool=has_tools, model=args.agent_model,
                                            project_skills=has_tools, skill=skill,
                                            backend=args.agent_backend,
                                            documentation_root=plan.root,
                                            **({"repository_context": plan.repository_context} if plan.repository_context else {}),
                                            auto_lessons=args.auto_lessons)
    else:
        # The agent writes its own harness and ignores the rewrite rules: only the engine is probed.
        verifier["capabilities"] = resolve_rules(args.esbmc_command or ["esbmc"],
                                                 cache_dir=Path(args.capability_cache),
                                                 enabled=args.capability_probes, bound=args.bound,
                                                 timeout_seconds=min(args.timeout, 60))
        verifier["rules"] = ALL_RULES - frozenset(verifier["capabilities"]["disabled_rules"])
        if verifier["capabilities"]["disabled_rules"]:
            print("Regras desligadas pelas sondas: " + ", ".join(verifier["capabilities"]["disabled_rules"]))
    try:
        if args.scan_smells:
            judge_smells(plan, spec_llm)
        report = execute_scan(plan, analyzer=analyzer, spec_llm=spec_llm, resume=args.resume, **verifier,
                              esbmc_command=args.esbmc_command, bound=args.bound, timeout_seconds=args.timeout,
                              strategy=args.spec_strategy, spec_context=args.spec_context, graph=plan.graph,
                              healer=build_healer(args.heal, llm=spec_llm, esbmc_command=args.esbmc_command,
                                                  graph=plan.graph, auto_lessons=args.auto_lessons,
                                                  run_dir=plan.output_dir),
                              heal_rounds=args.heal_rounds)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except UsageLimitReached as exc:
        _schedule_automatic_maintenance(args, plan.output_dir)
        print(_usage_limit_message(exc, plan.output_dir / "scan_checkpoint.json"), file=sys.stderr)
        return USAGE_LIMIT_EXIT
    _schedule_automatic_maintenance(args, plan.output_dir)
    return 2 if report["detection"]["failed"] else 0


def mode_v2(args: argparse.Namespace) -> int:
    routing = args.v2_variants.strip() == "auto"
    variants = DEFAULT_VARIANTS if routing else tuple(v for v in args.v2_variants.split(",") if v)
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

    model, synth_backend, synth_model = resolve_models(backend, args.model, args.synth_backend, args.synth_model)

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
        "routing": ROUTING_VERSION if routing else None,
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
        # A resume under another --heal would mix healed and unhealed verdicts.
        "heal": args.heal,
    }
    if args.auto_lessons:
        # Only when on, so a --no-auto-lessons run keeps the fingerprint of runs that read a fixed notebook.
        config["auto_lessons"] = True
        config["lesson_storage"] = "quarantine-v1"
    if args.max_hypotheses_per_function:
        # Only when given, like fixed_sources: verify_results are indexed by the capped list.
        config["max_hypotheses_per_function"] = args.max_hypotheses_per_function
    if args.review_threshold is not None:
        # Only when given: verify_results are indexed by the reviewed list.
        config["review_threshold"] = args.review_threshold
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
        saved = checkpoint.get("fingerprint") or {}
        if set(saved) != set(fingerprint):
            print("Não é seguro retomar a V2: o formato da impressão digital mudou (desde 04/11 ela inclui o "
                  "texto de prompt de toda variante). Rode de novo, sem --resume, em outra pasta.", file=sys.stderr)
            return 1
        if saved != fingerprint:
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
    usage_limit: UsageLimitReached | None = None
    detection_inputs = [] if args.v2_stage == "synthesis" else input_paths
    if args.v2_stage == "synthesis":
        print(f"\nModo V2 — síntese isolada: {len(candidates)} hipótese(s) conhecida(s)")
    else:
        print(f"\nModo V2 — etapa 1: detecção em {len(input_paths)} arquivo(s)")
    unit_sources: dict[tuple[str, str], str] = {}
    detection_cache = make_cache(analyzer, Path(args.detection_cache)) if args.detection_cache else None
    for file_index, file_path in enumerate(detection_inputs, 1):
        if usage_limit is not None:
            break
        units = preprocess_file(file_path)
        for unit in units:
            analyzed_units += 1
            unit_sources[(str(file_path), unit.qualname)] = unit.source
            unit_key = f"{file_path.resolve()}::{unit.qualname}"
            saved_unit = checkpoint["detection_units"].get(unit_key)
            if saved_unit is not None:
                candidates.extend(Candidate.from_dict(item) for item in saved_unit["candidates"])
                rejected_findings.extend(saved_unit.get("rejected_findings", []))
                if saved_unit.get("trace"):
                    detection_trace.append(saved_unit["trace"])
                print(f"  [{file_index}/{len(input_paths)}] Retomada: {file_path.name}::{unit.qualname}")
                continue
            if routing:
                analyzer.v2_variants = route_variants(unit.source)
            cache_hit = detection_cache.get(unit) if detection_cache else None
            label = "Cache" if cache_hit else "Analisando"
            print(f"  [{file_index}/{len(input_paths)}] {label} {file_path.name}::{unit.qualname}...")
            try:
                findings, cached_trace = cache_hit if cache_hit else (analyzer.analyze(unit), None)
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
                if isinstance(exc, UsageLimitReached):
                    usage_limit = exc
                    break
                continue
            analyzer_trace = getattr(analyzer, "detection_trace", [])
            trace = cached_trace or (dict(analyzer_trace[-1]) if analyzer_trace else {
                "function": unit.qualname,
                "strategy": "single",
                "located_candidates": len(findings),
                "classified_candidates": len(findings),
                "rejected_candidates": 0,
            })
            if routing:
                trace = {**trace, "variants": list(analyzer.v2_variants)}
            if detection_cache and cache_hit is None:
                detection_cache.put(unit, findings, trace)
            unit_candidates: list[Candidate] = []
            unit_rejections: list[dict[str, str]] = []
            for finding in findings:
                # With A15 the LLM says how the bug shows; a wrong result goes to the value oracle.
                wrong_result = "A15" in variants and finding.metadata.get("failure_mode") in ("wrong_result", "resultado_errado")
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

    capped: list[Candidate] = []
    if args.max_hypotheses_per_function and args.v2_stage != "synthesis":
        candidates, capped = cap_per_function(candidates, args.max_hypotheses_per_function)
        print(f"Limite de {args.max_hypotheses_per_function} por função: {len(capped)} hipótese(s) fora da fila.")
    capped_dicts = [_v2_candidate_dict(c) for c in capped]

    review_report: dict = {}
    if args.review_threshold is not None and args.v2_stage != "synthesis" and usage_limit is None:
        try:
            candidates, review_report = _apply_review(
                candidates, unit_sources, synthesizer, checkpoint, checkpoint_path, args.review_threshold)
        except UsageLimitReached as exc:
            capture_telemetry()
            _save_checkpoint(checkpoint_path, checkpoint)
            _write_json_atomic(output_path / "llm_telemetry.json", checkpoint["telemetry_events"])
            print(_usage_limit_message(exc, checkpoint_path), file=sys.stderr)
            return USAGE_LIMIT_EXIT
        print(f"Revisão (corte {args.review_threshold}): {len(review_report['review_dropped'])} hipótese(s) "
              f"fora da fila, {review_report['review_errors']} sem nota.")

    if detection_errors:
        checkpoint["status"] = "partial_detection"
        checkpoint["detection_errors"] = detection_errors
        if usage_limit is not None:
            checkpoint["interruption_reason"] = "usage_limit"
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
                    "capped_candidates": capped_dicts,
                    **review_report,
                    "rejected_findings": rejected_findings,
                    "trace": detection_trace,
                    "trace_summary": _summarize_detection_trace(detection_trace),
                },
                "verification": summarize([]),
                "telemetry": telemetry_summary,
                "results": [],
            },
        )
        if usage_limit is not None:
            print(_usage_limit_message(usage_limit, checkpoint_path), file=sys.stderr)
            return USAGE_LIMIT_EXIT
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
                    "capped_candidates": capped_dicts,
                    **review_report,
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
            "capped_candidates": capped_dicts,
            **review_report,
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
    if args.mode != "scan" and args.scan_repository_context != "off":
        print("--scan-repository-context evidence é exclusivo do modo scan.", file=sys.stderr)
        return 1


    dispatch = {
        "hybrid":    mode_v2,
        "benchmark": mode_benchmark,
        "scan":      mode_scan,
    }
    return dispatch[args.mode](args)




if __name__ == "__main__":
    raise SystemExit(main())
