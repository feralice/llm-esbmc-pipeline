"""Scan mode: repository -> call graph -> detection per function (with its callers) -> verify engine.

``plan_scan`` never calls an LLM: it builds the graph, picks the functions and estimates the cost.
``execute_scan`` spends the calls, one function at a time, and checkpoints after each one.
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from ..llm.prompts import build_user_prompt, load_system_prompt
from ..models import CodeUnit
from ..preprocess import preprocess_file
from ..verify.candidate import Candidate
from ..verify.hypothesis import BugHypothesis
from ..verify.loop import run_verify
from ..verify.outcome import CONFIRMED
from ..verify.report import summarize
from .callgraph import CallGraph, build_callgraph
from .context import caller_context

# A5 (the benchmark's detection prompt) plus the repository call sites.
DEFAULT_VARIANTS = ("A1", "A2", "A12")
# Detection replies are a short JSON list; this is a generous ceiling, not a measurement.
OUTPUT_TOKENS_PER_CALL = 1_500
CHARS_PER_TOKEN = 4
_RISKY_KINDS = {"division", "subscript"}


@dataclass
class Target:
    key: str
    file: str
    qualname: str
    start_line: int
    callers: int
    risky_operations: int
    unit: CodeUnit = field(repr=False)

    def to_dict(self) -> dict:
        return {"key": self.key, "file": self.file, "function": self.qualname, "line": self.start_line,
                "callers": self.callers, "risky_operations": self.risky_operations}


@dataclass
class ScanPlan:
    root: Path
    output_dir: Path
    graph: CallGraph
    targets: list[Target]
    variants: tuple[str, ...]
    estimated_tokens: int
    candidates_total: int

    def to_dict(self) -> dict:
        return {"root": str(self.root), "variants": list(self.variants), "candidates_total": self.candidates_total,
                "selected": len(self.targets), "estimated_detection_tokens": self.estimated_tokens,
                "targets": [t.to_dict() for t in self.targets]}


def _units_by_location(graph: CallGraph) -> dict[tuple[str, int], CodeUnit]:
    units: dict[tuple[str, int], CodeUnit] = {}
    for relative in graph.sources:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                found = preprocess_file(graph.root / relative)
        except (OSError, UnicodeDecodeError, ValueError, RecursionError):
            continue
        units.update({(relative, unit.start_line): unit for unit in found if unit.kind == "function"})
    return units


def rank_key(target: Target) -> tuple:
    """Functions with a division or subscript first: the crashes ESBMC-Python checks live there. Then the
    most called (more impact, and more caller context for the prompt), then source order for determinism."""
    return (target.risky_operations == 0, -target.callers, -target.risky_operations, target.file,
            target.start_line)


def select_targets(graph: CallGraph, *, limit: int | None = None) -> tuple[list[Target], int]:
    """Returns the selection and how many functions were eligible before ``limit``."""
    units = _units_by_location(graph)
    targets = []
    for function in graph.functions.values():
        unit = units.get((function.file, function.start_line))
        if not function.verifiable or unit is None:
            continue
        unit = replace(unit, caller_context=caller_context(graph, function.key))
        risky = sum(1 for op in unit.operations if op.kind in _RISKY_KINDS)
        targets.append(Target(function.key, str(graph.root / function.file), function.qualname,
                              function.start_line, len(graph.callers(function.key)), risky, unit))
    targets.sort(key=rank_key)
    return (targets[:limit] if limit else targets), len(targets)


def estimate_tokens(targets: list[Target], variants: tuple[str, ...]) -> int:
    system = len(load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants))
    chars = sum(system + len(build_user_prompt(t.unit, include_smells=False, v2_variants=variants)) for t in targets)
    return chars // CHARS_PER_TOKEN + OUTPUT_TOKENS_PER_CALL * len(targets)


def plan_scan(root: str | Path, output_dir: str | Path, *, limit: int | None = None, include_tests: bool = False,
              variants: tuple[str, ...] = DEFAULT_VARIANTS) -> ScanPlan:
    graph = build_callgraph(root, include_tests=include_tests)
    targets, total = select_targets(graph, limit=limit)
    plan = ScanPlan(graph.root, Path(output_dir), graph, targets, variants, estimate_tokens(targets, variants), total)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(plan.output_dir / "scan_graph.json", graph.to_dict())
    _write_json(plan.output_dir / "scan_selection.json", plan.to_dict())
    stats = graph.stats()
    print(f"Grafo de {graph.root}: {stats['modules']} módulo(s), {stats['skipped_files']} ignorado(s) por erro, "
          f"{stats['functions']} função(ões), {stats['verifiable_functions']} alcançável(is) pelo motor; "
          f"{stats['call_sites']} chamada(s), {stats['resolved_calls']} resolvida(s) no repositório.")
    print(f"Selecionadas {len(targets)} de {total} função(ões). Estimativa da detecção: {len(targets)} chamada(s) "
          f"à LLM, ~{plan.estimated_tokens} tokens; a verificação gasta até 3 chamadas por hipótese a mais.")
    return plan


def _fingerprint(plan: ScanPlan, model: str) -> str:
    payload = json.dumps({"root": str(plan.root), "variants": plan.variants, "model": model,
                          "targets": [t.key for t in plan.targets]}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _detect(analyzer, target: Target) -> dict:
    try:
        findings = analyzer.analyze(target.unit)
    except Exception as exc:  # noqa: BLE001 - one failed call must not end the scan
        return {"error": f"{type(exc).__name__}: {exc}", "candidates": [], "held": []}
    candidates, held = [], []
    for finding in findings:
        expression = str(finding.metadata.get("expression", ""))
        if not finding.verifiable:
            held.append({"expression": expression, "explanation": finding.explanation})
            continue
        candidates.append(Candidate(file=target.file, function=target.qualname, expression=expression,
                                    note=finding.explanation,
                                    violated_property=str(finding.metadata.get("violated_property", ""))).to_dict())
    return {"error": "", "candidates": candidates, "held": held}


def execute_scan(plan: ScanPlan, *, analyzer, spec_llm, resume: bool = False,
                 verify: Callable[..., list[dict]] | None = None, **verify_kwargs) -> dict:
    checkpoint_path = plan.output_dir / "scan_checkpoint.json"
    fingerprint = _fingerprint(plan, getattr(analyzer, "model", ""))
    checkpoint = {"fingerprint": fingerprint, "detection": {}, "verify_results": {}}
    if resume and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if saved.get("fingerprint") != fingerprint:
            raise ValueError("cannot resume: repository selection, prompt variants or model changed")
        checkpoint = saved

    def save() -> None:
        _write_json(checkpoint_path, checkpoint)

    for index, target in enumerate(plan.targets, 1):
        done = checkpoint["detection"].get(target.key)
        if done is not None and not done["error"]:
            continue
        print(f"  [{index}/{len(plan.targets)}] {Path(target.file).name}::{target.qualname}")
        checkpoint["detection"][target.key] = _detect(analyzer, target)
        save()

    candidates = [Candidate.from_dict(c) for t in plan.targets for c in checkpoint["detection"][t.key]["candidates"]]
    hypotheses = list({h.hypothesis_id: h for h in map(BugHypothesis.from_candidate, candidates)}.values())

    def on_result(index: int, data: dict) -> None:
        checkpoint["verify_results"][str(index)] = data
        save()

    completed = {int(i): d for i, d in checkpoint["verify_results"].items() if d.get("verdict") != "PIPELINE_ERROR"}
    results = (verify or run_verify)(hypotheses, llm=spec_llm, output_dir=plan.output_dir, completed=completed,
                     on_result=on_result, **verify_kwargs) if hypotheses else []
    report = _report(plan, checkpoint["detection"], hypotheses, results, analyzer)
    _write_json(plan.output_dir / "scan_report.json", report)
    (plan.output_dir / "scan_summary.md").write_text(summary_markdown(report), encoding="utf-8")
    print(f"Relatório: {plan.output_dir / 'scan_report.json'}")
    return report


def _report(plan: ScanPlan, detection: dict, hypotheses: list[BugHypothesis], results: list[dict],
            analyzer) -> dict:
    rows = [{**t.to_dict(), **detection[t.key]} for t in plan.targets]
    detection_tokens = sum(int(e.get("total_tokens") or 0) for e in getattr(analyzer, "telemetry_events", []))
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {"root": str(plan.root), "variants": list(plan.variants),
                   "model": getattr(analyzer, "model", "")},
        "graph": plan.graph.stats(),
        "detection": {"functions": len(rows), "failed": sum(1 for r in rows if r["error"]),
                      "hypotheses": len(hypotheses), "held": sum(len(r["held"]) for r in rows),
                      "tokens": detection_tokens, "functions_detail": rows},
        "verification": summarize(results),
        "verification_tokens": sum(int(r.get("tokens") or 0) for r in results),
        "results": results,
    }


def summary_markdown(report: dict) -> str:
    graph, detection = report["graph"], report["detection"]
    verdicts = {k: v for k, v in report["verification"]["by_verdict"].items() if v}
    lines = [
        f"# Varredura de {report['config']['root']}",
        "",
        (f"- Grafo: {graph['functions']} funções em {graph['modules']} módulos, "
         f"{graph['resolved_calls']} de {graph['call_sites']} chamadas resolvidas no repositório."),
        (f"- Detecção: {detection['functions']} funções analisadas ({detection['failed']} com erro), "
         f"{detection['hypotheses']} hipóteses enviadas ao ESBMC, {detection['held']} seguradas pela LLM."),
        f"- Vereditos: {verdicts or 'nenhum'}.",
        "",
        "## Confirmados (ESBMC e reexecução no CPython)",
        "",
    ]
    confirmed = [r for r in report["results"] if r["verdict"] == CONFIRMED]
    if not confirmed:
        lines.append("Nenhum.")
    for result in confirmed:
        h = result["hypothesis"]
        replay = result.get("replay") or {}
        lines.append(f"- `{os.path.relpath(h['file'], report['config']['root'])}` `{h['function']}`: "
                     f"`{h['suspect_expression']}`; {replay.get('exception_type') or result['reason'][:120]}"
                     + (f"; entrada: `{replay['inputs']}`" if replay.get("inputs") else "")
                     + (f"; programa: `{result['program_path']}`" if result.get("program_path") else "")
                     + (f"; teste: `{result['pytest']['path']}`" if (result.get("pytest") or {}).get("path") else ""))
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
