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
from ..smells.filter import SmellCandidate, filter_candidates, ruff_candidates
from ..verify.agent_arm import REPRODUCED_CPYTHON
from ..verify.candidate import Candidate
from ..verify.hypothesis import BugHypothesis
from ..verify.levels import agent_levels, consolidate, level_summary
from ..verify.loop import run_verify
from ..verify.outcome import CONFIRMED
from ..verify.report import summarize
from ..verify.run_report import render_run_report
from .callgraph import CallGraph, build_callgraph
from .context import caller_context
from .graph_metrics import (
    architecture_smells,
    envy_candidates,
    feature_envy_metrics,
    pagerank,
)

# A5 (the benchmark's detection prompt) plus the repository call sites.
DEFAULT_VARIANTS = ("A1", "A2", "A12")
# Detection replies are a short JSON list; this is a generous ceiling, not a measurement.
OUTPUT_TOKENS_PER_CALL = 1_500
CHARS_PER_TOKEN = 4
_RISKY_KINDS = {"division", "subscript"}
# Code a repository ships for reading, not running: scanning it spends calls on tutorials.
NON_PRODUCT_DIRS = frozenset({"examples", "example", "docs", "doc"})


@dataclass
class Target:
    key: str
    file: str
    qualname: str
    start_line: int
    callers: int
    risky_operations: int
    unit: CodeUnit = field(repr=False)
    centrality: float | None = None  # only measured with rank="pagerank"
    position: int | None = None  # 1-based rank among all eligible functions, kept when ``only`` narrows them

    def to_dict(self) -> dict:
        return {"key": self.key, "file": self.file, "function": self.qualname, "line": self.start_line,
                "callers": self.callers, "risky_operations": self.risky_operations,
                "centrality": None if self.centrality is None else round(self.centrality, 6),
                "position": self.position}


@dataclass
class ScanPlan:
    root: Path
    output_dir: Path
    graph: CallGraph
    targets: list[Target]
    variants: tuple[str, ...]
    estimated_tokens: int
    candidates_total: int
    rank: str = "callers"
    focus: str = ""
    excluded: dict[str, int] = field(default_factory=dict)
    only: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"root": str(self.root), "variants": list(self.variants), "rank": self.rank, "focus": self.focus,
                "only": list(self.only),
                "candidates_total": self.candidates_total, "excluded": self.excluded,
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


def rank_key(target: Target, rank: str = "callers") -> tuple:
    """Functions with a division or subscript first: the crashes ESBMC-Python checks live there. Then the
    most called (more impact, and more caller context for the prompt), or with ``pagerank`` the most
    central, then source order for determinism."""
    importance = -(target.centrality or 0.0) if rank == "pagerank" else -target.callers
    return (target.risky_operations == 0, importance, -target.risky_operations, target.file, target.start_line)


def _in_async(graph: CallGraph, function) -> bool:
    parts = function.qualname.split(".")
    enclosing = (graph.functions.get(f"{function.module}:{'.'.join(parts[:i])}") for i in range(1, len(parts)))
    return function.is_async or any(f is not None and f.is_async for f in enclosing)


def _exclusion(graph: CallGraph, function, include_examples: bool) -> str:
    """Why a function is left out of the selection (it stays in the graph as a caller), or ''."""
    if _in_async(graph, function):
        return "async"  # ESBMC-Python does not model coroutines
    if include_examples:
        return ""
    parts = Path(function.file).parts
    if any(part in NON_PRODUCT_DIRS for part in parts[:-1]):
        return "examples"
    return "setup" if parts == ("setup.py",) else ""


def select_targets(graph: CallGraph, *, limit: int | None = None, rank: str = "callers",
                   include_examples: bool = False, only: tuple[str, ...] = (),
                   excluded: dict[str, int] | None = None) -> tuple[list[Target], int]:
    """Returns the selection and how many functions were eligible before ``limit``; ``excluded`` receives the
    count left out per reason. ``only`` (keys or qualified names) keeps just those functions, each with its
    position in the full ranking, so a run on known functions still reports whether the ranking reaches them."""
    units = _units_by_location(graph)
    scores = pagerank(graph) if rank == "pagerank" else {}
    counts = excluded if excluded is not None else {}
    counts.update({"examples": 0, "setup": 0, "async": 0})
    targets = []
    for function in graph.functions.values():
        if not function.verifiable:
            continue
        reason = _exclusion(graph, function, include_examples)
        if reason:
            counts[reason] += 1
            continue
        unit = units.get((function.file, function.start_line))
        if unit is None:
            continue
        unit = replace(unit, caller_context=caller_context(graph, function.key))
        risky = sum(1 for op in unit.operations if op.kind in _RISKY_KINDS)
        targets.append(Target(function.key, str(graph.root / function.file), function.qualname,
                              function.start_line, len(graph.callers(function.key)), risky, unit,
                              scores.get(function.key, 0.0) if rank == "pagerank" else None))
    targets.sort(key=lambda target: rank_key(target, rank))
    for position, target in enumerate(targets, 1):
        target.position = position
    total = len(targets)
    if only:
        missing = [name for name in only if not any(name in (t.key, t.qualname) for t in targets)]
        if missing:
            raise ValueError(f"--scan-only names no selectable function: {', '.join(missing)}")
        targets = [t for t in targets if t.key in only or t.qualname in only]
    return (targets[:limit] if limit else targets), total


def estimate_tokens(targets: list[Target], variants: tuple[str, ...]) -> int:
    system = len(load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants))
    chars = sum(system + len(build_user_prompt(t.unit, include_smells=False, v2_variants=variants)) for t in targets)
    return chars // CHARS_PER_TOKEN + OUTPUT_TOKENS_PER_CALL * len(targets)


def plan_scan(root: str | Path, output_dir: str | Path, *, limit: int | None = None, include_tests: bool = False,
              variants: tuple[str, ...] = DEFAULT_VARIANTS, rank: str = "callers", smells: bool = False,
              focus: str = "", include_examples: bool = False, only: tuple[str, ...] = ()) -> ScanPlan:
    graph = build_callgraph(root, include_tests=include_tests)
    excluded: dict[str, int] = {}
    targets, total = select_targets(graph, limit=limit, rank=rank, include_examples=include_examples,
                                    only=only, excluded=excluded)
    plan = ScanPlan(graph.root, Path(output_dir), graph, targets, variants, estimate_tokens(targets, variants), total,
                    rank, focus.strip(), excluded, only)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(plan.output_dir / "scan_graph.json", graph.to_dict())
    if smells:
        try:
            tool, tool_error = ruff_candidates(graph.root), ""
        except RuntimeError as exc:
            tool, tool_error = [], str(exc)
        # No ground truth for smells: the file says so, and nothing here counts as a measured result.
        # The code is kept so the LLM judges what the tool saw, even if the repository changes before --yes.
        _write_json(plan.output_dir / "scan_smells.json", {
            "exploratory": True, "architecture": architecture_smells(graph),
            "feature_envy": [{"method": key, "metrics": feature_envy_metrics(graph, key)}
                             for key in envy_candidates(graph)],
            "tool_error": tool_error,
            "tool_candidates": [{"id": c.id, "smell": c.smell, "path": c.path, "line": c.line,
                                 "rule": c.tool.removeprefix("ruff:"), "metrics": c.metrics, "code": c.code,
                                 "first_line": c.first_line} for c in tool]})
    _write_json(plan.output_dir / "scan_selection.json", plan.to_dict())
    stats = graph.stats()
    print(f"Grafo de {graph.root}: {stats['modules']} módulo(s), {stats['skipped_files']} ignorado(s) por erro, "
          f"{stats['functions']} função(ões), {stats['verifiable_functions']} alcançável(is) pelo motor; "
          f"{stats['call_sites']} chamada(s), {stats['resolved_calls']} resolvida(s) no repositório.")
    print(f"Selecionadas {len(targets)} de {total} função(ões). Estimativa da detecção: {len(targets)} chamada(s) "
          f"à LLM, ~{plan.estimated_tokens} tokens; a verificação gasta até 3 chamadas por hipótese a mais.")
    nested = sum(graph.functions[t.key].nested for t in targets)
    if nested:
        print(f"{nested} função(ões) interna(s) incluída(s): entram pela função de fora ou levantadas.")
    if any(excluded.values()):
        print(f"Fora da seleção: {excluded['examples']} em examples/docs, {excluded['setup']} no setup.py da raiz, "
              f"{excluded['async']} async (o ESBMC-Python não modela)."
              + (" Exemplos e setup.py entram com --scan-include-examples." if excluded["examples"] + excluded["setup"]
                 else ""))
    return plan


def _prompts_hash(plan: ScanPlan) -> str:
    digest = hashlib.sha256(load_system_prompt(include_smells=False, v2_detection=True,
                                               v2_variants=plan.variants).encode("utf-8"))
    for target in plan.targets:
        digest.update(build_user_prompt(target.unit, include_smells=False, v2_variants=plan.variants).encode("utf-8"))
    return digest.hexdigest()


def _plain_config(kwargs: dict) -> dict:
    """Settings as values; an object (the graph, a healer) by its ``config_label`` or its type, so its address
    never enters the hash."""
    plain = (str, int, float, bool, type(None))

    def value_of(value):
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, plain) or (isinstance(value, (list, tuple)) and all(isinstance(v, plain) for v in value)):
            return value
        return f"{type(value).__name__}:{getattr(value, 'config_label', '')}"
    return {key: value_of(value) for key, value in kwargs.items()}


def _fingerprint(plan: ScanPlan, model: str, verifier: str = "engine", verify_config: dict | None = None) -> str:
    payload = json.dumps({"root": str(plan.root), "variants": plan.variants, "model": model, "focus": plan.focus,
                          "verifier": verifier, "verify_config": _plain_config(verify_config or {}), "prompts": _prompts_hash(plan),
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
    # A verifier names itself (agent_verifier does), so a resume never mixes the engine's verdicts with the agent's.
    fingerprint = _fingerprint(plan, getattr(analyzer, "model", ""), getattr(verify, "label", "engine"), verify_kwargs)
    checkpoint = {"fingerprint": fingerprint, "detection": {}, "verify_results": {}}
    if resume and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if saved.get("fingerprint") != fingerprint:
            raise ValueError("cannot resume: repository selection, prompts, model or verify settings changed")
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

    # Saved by hypothesis_id: a detection retried on resume can add hypotheses and shift every position.
    def on_result(index: int, data: dict) -> None:
        checkpoint["verify_results"][hypotheses[index].hypothesis_id] = data
        save()

    saved = checkpoint["verify_results"]
    completed = {index: saved[h.hypothesis_id] for index, h in enumerate(hypotheses)
                 if h.hypothesis_id in saved and saved[h.hypothesis_id].get("verdict") != "PIPELINE_ERROR"}
    results = (verify or run_verify)(hypotheses, llm=spec_llm, output_dir=plan.output_dir, completed=completed,
                     on_result=on_result, **verify_kwargs) if hypotheses else []
    report = _report(plan, checkpoint["detection"], hypotheses, results, analyzer,
                     agent=getattr(verify, "label", "").startswith("agent"))
    _write_json(plan.output_dir / "scan_report.json", report)
    (plan.output_dir / "scan_summary.md").write_text(summary_markdown(report), encoding="utf-8")
    held = [{"file": t.file, "function": t.qualname, **entry}
            for t in plan.targets for entry in checkpoint["detection"][t.key]["held"]]
    errors = [f"{t.qualname}: {checkpoint['detection'][t.key]['error']}" for t in plan.targets
              if checkpoint["detection"][t.key]["error"]]
    (plan.output_dir / "relatorio.md").write_text(
        render_run_report(results, held=held, detection=(len(plan.targets), errors), root=plan.root)
        + smells_section(plan.output_dir), encoding="utf-8")
    print(f"Relatório: {plan.output_dir / 'scan_report.json'}")
    return report


def _report(plan: ScanPlan, detection: dict, hypotheses: list[BugHypothesis], results: list[dict],
            analyzer, agent: bool = False) -> dict:
    levels = agent_levels(results) if agent else consolidate(results)
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
        # The agent's sessions report no tokens: unmeasured, not zero.
        "verification_tokens": (sum(int(r.get("tokens") or 0) for r in results)
                                if any("tokens" in r for r in results) else None),
        "levels": {"summary": level_summary(levels), "rows": levels},
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
        f"- Nível que decidiu: {report['levels']['summary']['by_level'] or 'nenhum'}.",
    ]
    for title, verdict in (("Confirmados (ESBMC e reexecução no CPython)", CONFIRMED),
                           ("Reproduzidos só no CPython (o ESBMC não decidiu)", REPRODUCED_CPYTHON)):
        lines += ["", f"## {title}", ""]
        found = [r for r in report["results"] if r["verdict"] == verdict]
        if not found:
            lines.append("Nenhum.")
        for result in found:
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


_ENVY_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "smell_feature_envy.txt"


def judge_smells(plan: ScanPlan, llm) -> dict:
    """Ask the LLM about each Feature Envy candidate in scan_smells.json, with the method, its class and the
    graph metrics, and filter the ruff reports (iSMELL, ASE 2024); the answers are written back to the same file."""
    path = plan.output_dir / "scan_smells.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    system = _ENVY_PROMPT.read_text(encoding="utf-8")
    for entry in report["feature_envy"]:
        if "llm" in entry and "error" not in entry["llm"]:
            continue  # answered by an earlier run: asking again only spends the API
        function = plan.graph.functions[entry["method"]]
        lines = plan.graph.sources.get(function.file, [])
        user = (f"<UNTRUSTED_PYTHON_METHOD>\n{chr(10).join(lines[function.start_line - 1:function.end_line])}\n"
                f"</UNTRUSTED_PYTHON_METHOD>\n\nClass: {function.class_qualname}\n\n"
                f"Metrics: {json.dumps(entry['metrics'])}\n")
        try:
            answer = json.loads(llm.complete(system, user, json_mode=True).raw_response)
            entry["llm"] = answer if isinstance(answer, dict) else {"error": f"not a JSON object: {answer!r}"[:300]}
        except Exception as exc:  # noqa: BLE001 - each backend raises its own errors; one must not lose the rest
            entry["llm"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        _write_json(path, report)
    entries = {entry["id"]: entry for entry in report.get("tool_candidates", [])}
    done = {i: e["llm"] for i, e in entries.items() if "llm" in e}

    def save(results: dict) -> None:
        for candidate_id, answer in results.items():
            if candidate_id in entries:
                entries[candidate_id]["llm"] = answer
        _write_json(path, report)

    candidates = [SmellCandidate(e["id"], e["smell"], e["path"], e["line"], f"ruff:{e['rule']}", e.get("metrics", {}),
                                 e.get("code", ""), e.get("first_line", e["line"])) for e in entries.values()]
    save(filter_candidates(candidates, llm, done=done, on_answer=save))
    return report


def smells_section(output_dir: Path) -> str:
    """The relatorio.md section for the tool's smell reports the LLM kept; exploratory, no ground truth."""
    path = Path(output_dir) / "scan_smells.json"
    if not path.exists():
        return ""
    saved = json.loads(path.read_text(encoding="utf-8"))
    entries = saved.get("tool_candidates", [])
    # The filter only removes: an entry the LLM did not answer keeps the tool's call and is counted apart.
    kept = [e for e in entries if (e.get("llm") or {}).get("smell") is not False]
    unanswered = [e for e in kept if (e.get("llm") or {}).get("smell") is not True]
    lines = ["", "## Smells (exploratório, sem gabarito)", ""]
    if saved.get("tool_error"):
        lines.append(f"O ruff não rodou: {saved['tool_error']}")
    lines.append(f"{len(entries)} apontados pelo ruff, {len(kept)} mantidos ({len(unanswered)} sem resposta da LLM, "
                 "que ficam com a decisão da ferramenta).")
    for e in kept:
        reason = " ".join(str((e.get("llm") or {}).get("reason") or "sem resposta da LLM").split())
        lines.append(f"- `{e['path']}:{e['line']}` {e['smell']} ({e['rule']}): {reason}")
    return "\n".join(lines) + "\n"
