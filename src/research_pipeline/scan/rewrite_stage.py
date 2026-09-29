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
from .capability import CapabilityDiagnostic
from .context import context_module
from .replay import boundary_cases, compare_rewrite, merge_cases
from .rewrite import RewriteProposal
from .rewrite_guard import _expression_nodes, _find_function, validate_rewrite
from .synth import _MAX_UNTRUSTED_CHARS
from .witness import assess_witness

REWRITE_CONFIRMED_ORIGINAL = "confirmed_original"
REWRITE_VIOLATION_EMPIRICAL = "rewrite_violation_empirical"
REWRITE_REJECTED = "rewrite_rejected"
REWRITE_INCONCLUSIVE = "inconclusive"
REWRITE_STATUSES = frozenset({
    REWRITE_CONFIRMED_ORIGINAL, REWRITE_VIOLATION_EMPIRICAL, REWRITE_REJECTED, REWRITE_INCONCLUSIVE,
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


def _original_location(module: str, function: str, expression: str) -> tuple[int, int] | None:
    target = _find_function(ast.parse(module), function)
    nodes = _expression_nodes(target, expression) if target else []
    return (nodes[0].lineno, nodes[0].col_offset) if len(nodes) == 1 else None


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


def _propose(candidate, unit, finding, diagnostic, synthesizer, module, max_repairs, result):
    """Ask for proposals until one passes the static gate; returns (proposal, guard) or (None, None)."""
    feedback = ""
    previous = ""
    last_error = ""
    for attempt in range(1 + max(0, max_repairs)):
        started = time.monotonic()
        try:
            proposal, synth = synthesizer.synthesize_rewrite(
                unit, finding, diagnostic, module_source=module,
                repair_feedback=feedback, previous_proposal=previous,
            )
        except ValueError as exc:
            result.synth_seconds += time.monotonic() - started
            paid = getattr(exc, "synth", None)
            result.tokens += int(((paid.telemetry if paid else None) or {}).get("total_tokens") or 0)
            last_error = f"malformed rewrite proposal: {exc}"
            result.attempts.append({"attempt": attempt + 1, "error": last_error})
            feedback = last_error
            continue
        result.synth_seconds += time.monotonic() - started
        result.tokens += int((synth.telemetry or {}).get("total_tokens") or 0)
        guard = validate_rewrite(
            module, proposal, function=candidate.function,
            expression=candidate.expression, category=candidate.category,
        )
        result.attempts.append({
            "attempt": attempt + 1, "guard_ok": guard.ok,
            "guard_reasons": list(guard.reasons), "risk": guard.risk,
        })
        if guard.ok:
            return proposal, guard
        last_error = "static gate: " + "; ".join(guard.reasons)
        result.status = REWRITE_REJECTED
        feedback = "The rewrite was rejected by the static gate:\n- " + "\n- ".join(guard.reasons)
        previous = synth.raw_response
    result.reason = last_error
    if result.status != REWRITE_REJECTED:
        result.status = REWRITE_INCONCLUSIVE
    return None, None


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
    max_repairs: int = 1,
) -> RewriteStageResult:
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

    proposal, guard = _propose(candidate, unit, finding, diagnostic, synthesizer, module, max_repairs, result)
    if proposal is None:
        return result
    result.status = REWRITE_INCONCLUSIVE
    result.evidence["guard"] = {"risk": guard.risk, "suspect_rewrite_line": guard.suspect_rewrite_line}

    harness = proposal.rewritten_source.rstrip() + "\n\n\n" + proposal.driver_source
    directory = Path(output_dir) / finding_id
    result.evidence["artifacts"] = _write_artifacts(directory, module, proposal, harness)

    cases = merge_cases(proposal.input_cases, proposal.rewritten_source, candidate.function)
    replay = compare_rewrite(module, proposal.rewritten_source, candidate.function, cases, executor)
    result.evidence["replay"] = {
        "status": replay.status, "compared": replay.compared,
        "cases": len(cases), "divergences": list(replay.divergences),
    }
    if replay.status == "diverged":
        result.status = REWRITE_REJECTED
        result.reason = "differential replay: " + "; ".join(replay.divergences)
        return result

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
    result.esbmc_seconds = esbmc.time_seconds
    result.evidence["esbmc"] = {"command": esbmc.command, "raw_log_path": esbmc.raw_log_path}
    if esbmc.status == "no_violation_found":
        result.reason = "no violation on the rewrite; this is not evidence that the original is safe"
        return result
    if esbmc.status != "violation_found" or only_verifier_artifacts(esbmc.details):
        result.reason = f"ESBMC on the rewrite: {esbmc.status}: {esbmc.summary}"
        return result

    witness = assess_witness(
        esbmc.details, expected_category=candidate.category,
        rewritten_file=str(harness_path), rewritten_line=guard.suspect_rewrite_line,
        original_source=module, function=candidate.function, executor=executor,
        original_line=location[0], original_column=location[1],
        driver_source=proposal.driver_source,
    )
    result.evidence["witness"] = {
        "status": witness.status, "reason": witness.reason,
        "case": None if witness.case is None else {"args": list(witness.case.args), "kwargs": witness.case.kwargs},
    }
    if witness.status == "reproduced_original":
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
