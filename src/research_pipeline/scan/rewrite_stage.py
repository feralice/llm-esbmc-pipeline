"""Evidence-tiered compatibility rewrite: LLM proposal -> static gate -> replay -> ESBMC -> witness.

A violation on the rewrite is never reported as a bug in the original code
unless its concrete input reproduces the same native exception, at the same
operation, when the original runs in isolation (DESENHO_HARNESS_GENERICO.md).
"""

from __future__ import annotations

import ast
import difflib
import json
import time
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path

from ..verification.esbmc_runner import only_verifier_artifacts, run_esbmc_direct
from .capability import CapabilityDiagnostic, diagnose_esbmc, fix_hint
from .context import context_module
from .replay import (
    ReplayReport,
    UnavailableReplayExecutor,
    boundary_cases,
    compare_rewrite,
    merge_cases,
)
from .rewrite import RewriteProposal
from .rewrite_guard import _expression_nodes, _find_function, validate_rewrite
from .synth import _MAX_UNTRUSTED_CHARS
from .witness import assess_witness

REWRITE_CONFIRMED_ORIGINAL = "confirmed_original"
REWRITE_VIOLATION_EMPIRICAL = "rewrite_violation_empirical"
REWRITE_REJECTED = "rewrite_rejected"
# Violation at the suspect operation of the unchanged target, with unresolved
# dependencies replaced by nondet-returning stubs (over-approximated environment).
REWRITE_CONFIRMED_WITH_STUBS = "confirmed_with_stubs"
REWRITE_INCONCLUSIVE = "inconclusive"
REWRITE_STATUSES = frozenset({
    REWRITE_CONFIRMED_ORIGINAL, REWRITE_VIOLATION_EMPIRICAL, REWRITE_REJECTED, REWRITE_INCONCLUSIVE,
    REWRITE_CONFIRMED_WITH_STUBS,
})


@dataclass
class RewriteStageResult:
    status: str
    reason: str
    esbmc_status: str = ""
    esbmc_summary: str = ""
    tokens: int = 0
    synth_seconds: float = 0.0
    esbmc_seconds: float = 0.0
    attempts: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _original_location(module: str, function: str, expression: str) -> tuple[int, int | None, int | None] | None:
    """(line, column, end_line): column for an expression anchor, end_line for a statement one."""
    target = _find_function(ast.parse(module), function)
    nodes = _expression_nodes(target, expression) if target else []
    if len(nodes) != 1:
        return None
    node = nodes[0]
    if isinstance(node, ast.stmt):
        return node.lineno, None, node.end_lineno
    return node.lineno, node.col_offset, None


def _write_artifacts(directory: Path, module: str, proposal: RewriteProposal, harness: str) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    diff = "".join(difflib.unified_diff(
        module.splitlines(keepends=True), proposal.rewritten_source.splitlines(keepends=True),
        "original.py", "rewritten.py",
    ))
    files = {
        "original.py": module,
        "rewritten.py": harness,
        "rewrite.diff": diff,
        "proposal.json": json.dumps({
            "changes": [asdict(change) for change in proposal.changes],
            "input_cases": list(proposal.input_cases),
            "assumptions": list(proposal.assumptions),
            "oracle_ref": proposal.oracle_ref,
            "driver_source": proposal.driver_source,
        }, indent=2),
    }
    artifacts = {}
    for name, text in files.items():
        path = directory / name
        path.write_text(text, encoding="utf-8")
        artifacts[name] = {"path": str(path), "sha256": sha256(text.encode("utf-8")).hexdigest()}
    return artifacts


def _propose(candidate, unit, finding, diagnostic, synthesizer, module, result, feedback, previous, directory):
    """One proposal; returns (proposal, guard, raw, error) with error set when it is unusable."""
    started = time.monotonic()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        proposal, synth = synthesizer.synthesize_rewrite(
            unit, finding, diagnostic, module_source=module,
            repair_feedback=feedback, previous_proposal=previous,
        )
    except ValueError as exc:
        result.synth_seconds += time.monotonic() - started
        paid = getattr(exc, "synth", None)
        if paid is not None:
            result.tokens += int((paid.telemetry or {}).get("total_tokens") or 0)
            (directory / "response.txt").write_text(paid.raw_response, encoding="utf-8")
        error = f"malformed rewrite proposal: {exc}"
        result.attempts.append({"attempt": len(result.attempts) + 1, "error": error})
        return None, None, getattr(paid, "raw_response", ""), error
    result.synth_seconds += time.monotonic() - started
    result.tokens += int((synth.telemetry or {}).get("total_tokens") or 0)
    (directory / "response.txt").write_text(synth.raw_response, encoding="utf-8")
    guard = validate_rewrite(
        module, proposal, function=candidate.function,
        expression=candidate.expression, category=candidate.category,
    )
    result.attempts.append({
        "attempt": len(result.attempts) + 1, "guard_ok": guard.ok, "guard_reasons": list(guard.reasons),
        "risk": guard.risk, "manifest_matches": guard.manifest_matches,
    })
    if not guard.ok:
        return None, guard, synth.raw_response, "static gate: " + "; ".join(guard.reasons)
    return proposal, guard, synth.raw_response, ""


_VERDICTS = frozenset({"violation_found", "no_violation_found", "timeout"})


def run_rewrite_stage(
    candidate,
    unit,
    finding,
    diagnostic: CapabilityDiagnostic,
    *,
    synthesizer,
    executor,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
    output_dir: Path,
    finding_id: str,
    max_rounds: int = 4,
) -> RewriteStageResult:
    """One proposal per round; any failure (JSON, static gate, replay divergence,
    ESBMC conversion error) is fed back to the model, up to ``max_rounds``."""
    result = RewriteStageResult(REWRITE_INCONCLUSIVE, "")
    result.evidence["diagnostic"] = asdict(diagnostic)
    source = Path(candidate.file).read_text(encoding="utf-8")
    module = context_module(source, candidate.function)
    if not module:
        result.reason = "target has no self-contained module context"
        return result
    if len(module) > _MAX_UNTRUSTED_CHARS:
        result.reason = f"module context has {len(module)} chars, above the prompt limit"
        return result
    location = _original_location(module, candidate.function, candidate.expression)
    if location is None:
        result.reason = "suspect expression is missing or ambiguous in the original function"
        return result

    feedback = ""
    previous = ""
    for round_number in range(1, max(1, max_rounds) + 1):
        result.evidence["rounds"] = round_number
        directory = Path(output_dir) / finding_id / f"round_{round_number}"
        proposal, guard, previous, error = _propose(
            candidate, unit, finding, diagnostic, synthesizer, module, result, feedback, previous, directory,
        )
        if proposal is None:
            result.status = REWRITE_REJECTED if guard is not None else REWRITE_INCONCLUSIVE
            result.reason = error
            feedback = (
                f"Your previous answer was rejected: {error}\n"
                "Return only the JSON object, keep the suspect expression and its control flow unchanged, "
                "and make the driver define main() that calls the target exactly once."
            )
            continue
        result.status = REWRITE_INCONCLUSIVE
        result.evidence["guard"] = {"risk": guard.risk, "suspect_rewrite_line": guard.suspect_rewrite_line}
        result.evidence["stubs"] = list(guard.stubs)

        harness = proposal.rewritten_source.rstrip() + "\n\n\n" + proposal.driver_source
        result.evidence["artifacts"] = _write_artifacts(directory, module, proposal, harness)

        cases = merge_cases(proposal.input_cases, proposal.rewritten_source, candidate.function)
        if guard.stubs:
            # The original cannot run without the stubbed dependencies.
            replay = ReplayReport("skipped_stubbed", 0)
        else:
            replay = compare_rewrite(module, proposal.rewritten_source, candidate.function, cases, executor)
        result.evidence["replay"] = {
            "status": replay.status, "compared": replay.compared,
            "cases": len(cases), "divergences": list(replay.divergences),
        }
        if replay.status == "diverged":
            result.status = REWRITE_REJECTED
            result.reason = "differential replay: " + "; ".join(replay.divergences)
            feedback = (
                "The rewrite behaves differently from the original on concrete inputs "
                "(return value, exception or argument state). Keep the original semantics:\n- "
                + "\n- ".join(replay.divergences)
            )
            continue

        harness_path = directory / "rewritten.py"
        # Without --no-slice ESBMC drops driver inputs irrelevant to the property,
        # and the witness would have to guess them.
        esbmc = run_esbmc_direct(
            harness_path, esbmc_command=esbmc_command, bound=bound,
            timeout_seconds=timeout_seconds, output_dir=str(directory),
            extra_flags=["--no-slice"],
        )
        result.esbmc_status = esbmc.status
        result.esbmc_summary = esbmc.summary
        result.esbmc_seconds += esbmc.time_seconds
        result.evidence["esbmc"] = {"command": esbmc.command, "raw_log_path": esbmc.raw_log_path}
        if esbmc.status not in _VERDICTS:
            rejected = diagnose_esbmc(
                esbmc.status, esbmc.stdout, esbmc.stderr, esbmc.raw_log_path, summary=esbmc.summary,
            )
            result.reason = f"ESBMC rejected the rewrite: {rejected.kind}: {rejected.message}"
            result.evidence.setdefault("esbmc_rejections", []).append(asdict(rejected))
            feedback = (
                "ESBMC-Python could not convert your rewrite. Fix only this, keeping the "
                f"suspect expression and control flow:\n{rejected.kind}: {rejected.message}\n"
                f"Typical fix: {fix_hint(rejected) or 'change the construct at that line to a supported one.'}"
            )
            continue
        return _classify(result, esbmc, candidate, guard, proposal, module, location, executor, harness_path, replay)
    return result


def _classify(result, esbmc, candidate, guard, proposal, module, location, executor, harness_path, replay):
    if esbmc.status == "no_violation_found":
        result.reason = "no violation on the rewrite; this is not evidence that the original is safe"
        return result
    if esbmc.status != "violation_found" or only_verifier_artifacts(esbmc.details):
        result.reason = f"ESBMC on the rewrite: {esbmc.status}: {esbmc.summary}"
        return result

    stubbed = bool(guard.stubs)
    witness = assess_witness(
        esbmc.details, expected_category=candidate.category,
        rewritten_file=str(harness_path), rewritten_line=guard.suspect_rewrite_line,
        original_source=module, function=candidate.function,
        executor=UnavailableReplayExecutor("stubbed dependencies") if stubbed else executor,
        original_line=location[0], original_column=location[1], original_end_line=location[2],
        rewritten_end_line=guard.suspect_rewrite_end_line if location[2] is not None else None,
        driver_source=proposal.driver_source,
    )
    result.evidence["witness"] = {
        "status": witness.status, "reason": witness.reason,
        "exception": witness.exception, "category_match": witness.category_match,
        "case": None if witness.case is None else {"args": list(witness.case.args), "kwargs": witness.case.kwargs},
    }
    if stubbed and witness.status == "rewrite_only":
        result.status = REWRITE_CONFIRMED_WITH_STUBS
    elif witness.status == "reproduced_original":
        result.status = REWRITE_CONFIRMED_ORIGINAL
    elif witness.status == "contradicted":
        result.status = REWRITE_REJECTED
    elif witness.status == "rewrite_only" and replay.status == "matched":
        if not boundary_cases(proposal.rewritten_source, candidate.function):
            result.reason = "replay matched only LLM-chosen inputs; no independent boundary case"
            return result
        result.status = REWRITE_VIOLATION_EMPIRICAL
    else:
        result.reason = f"witness {witness.status}; replay {replay.status}: {witness.reason}"
        return result
    result.reason = witness.reason
    return result
