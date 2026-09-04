"""V2 steps 3--6: harness synthesis and verification orchestrator.

Wires the scan pieces into one runnable flow, one candidate at a time:

    candidate (file, function, category, expression)
      -> synth.py       LLM writes a scalar ESBMC harness      (1 paid API call)
      -> compat.py       harness runs on ESBMC-Python?
      -> ESBMC           verify the harness at module level
      -> ablation.py     SUCCESSFUL? was an __ESBMC_assume masking the bug?
      -> classification

There is no repository scanning here: the candidate list is the input. Where the
candidates come from (manual review, an exploration agent) is deliberately
outside the measured method, the same way BugsInPy supplies the cases in V1.
"""

from __future__ import annotations

import json
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Finding
from ..preprocess import preprocess_file
from ..verification.esbmc_runner import run_esbmc_direct
from .ablation import FAILED, AblationReport, ablate
from .compat import EXPECTED_PROPERTY_MARKER, VERDICT_UNSUPPORTED, check_harness
from .synth import HarnessSynthesizer

# Scan-specific classifications. Distinct from the V1 constants in models.py
# because "confirmed" here means "on the synthesized abstraction", not "on the
# original file".
CONFIRMED_ON_ABSTRACTION = "confirmed_on_abstraction"
OVER_RESTRICTED = "over_restricted"
SAFE_ON_ABSTRACTION = "safe_on_abstraction"
INVALID_HARNESS = "invalid_harness"
UNSUPPORTED_HARNESS = "unsupported_harness"
NO_PROPERTY = "no_property"
ESBMC_INCONCLUSIVE = "esbmc_inconclusive"
ESBMC_UNAVAILABLE = "esbmc_unavailable"
CANDIDATE_NOT_FOUND = "candidate_not_found"
SYNTH_FAILED = "synth_failed"

# A conclusive verdict ends the retry loop; a recoverable one triggers another
# synthesis attempt (the LLM output varies run to run).
_CONCLUSIVE = frozenset({CONFIRMED_ON_ABSTRACTION, OVER_RESTRICTED, SAFE_ON_ABSTRACTION})
_RECOVERABLE = frozenset(
    {INVALID_HARNESS, UNSUPPORTED_HARNESS, NO_PROPERTY, ESBMC_INCONCLUSIVE, SYNTH_FAILED}
)


@dataclass
class ScanCandidate:
    """One function to investigate, supplied from outside the measured method."""

    file: str
    function: str
    category: str
    expression: str = ""
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ScanCandidate:
        need = [k for k in ("file", "function", "category") if not data.get(k)]
        if need:
            raise ValueError(f"candidate missing field(s): {', '.join(need)}")
        return cls(
            file=str(data["file"]),
            function=str(data["function"]),
            category=str(data["category"]),
            expression=str(data.get("expression", "")),
            note=str(data.get("note", "")),
        )


@dataclass
class ScanCaseResult:
    """Outcome for one candidate after the full synth -> ESBMC -> ablation flow."""

    candidate: ScanCandidate
    classification: str
    harness: str = ""
    harness_path: str = ""
    compat_verdict: str = ""
    compat_reasons: list[str] = field(default_factory=list)
    esbmc_status: str = ""
    esbmc_summary: str = ""
    masking_assumptions: list[str] = field(default_factory=list)
    ablation_per_assumption: dict[str, str] = field(default_factory=dict)
    synth_model: str = ""
    synth_total_tokens: int | None = None
    synth_seconds: float = 0.0
    esbmc_seconds: float = 0.0
    attempts: int = 1
    attempt_history: list[dict] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ScanCaseResult:
        return cls(
            candidate=ScanCandidate.from_dict(data["candidate"]),
            classification=str(data["classification"]),
            harness=str(data.get("harness", "")),
            harness_path=str(data.get("harness_path", "")),
            compat_verdict=str(data.get("compat_verdict", "")),
            compat_reasons=list(data.get("compat_reasons", [])),
            esbmc_status=str(data.get("esbmc_status", "")),
            esbmc_summary=str(data.get("esbmc_summary", "")),
            masking_assumptions=list(data.get("masking_assumptions", [])),
            ablation_per_assumption=dict(data.get("ablation_per_assumption", {})),
            synth_model=str(data.get("synth_model", "")),
            synth_total_tokens=data.get("synth_total_tokens"),
            synth_seconds=float(data.get("synth_seconds", 0.0)),
            esbmc_seconds=float(data.get("esbmc_seconds", 0.0)),
            attempts=int(data.get("attempts", 1)),
            attempt_history=list(data.get("attempt_history", [])),
            seconds=float(data.get("seconds", 0.0)),
            error=str(data.get("error", "")),
        )

    def to_dict(self) -> dict:
        return {
            "candidate": {
                "file": self.candidate.file,
                "function": self.candidate.function,
                "category": self.candidate.category,
                "expression": self.candidate.expression,
                "note": self.candidate.note,
            },
            "classification": self.classification,
            "harness": self.harness,
            "harness_path": self.harness_path,
            "compat_verdict": self.compat_verdict,
            "compat_reasons": self.compat_reasons,
            "esbmc_status": self.esbmc_status,
            "esbmc_summary": self.esbmc_summary,
            "masking_assumptions": self.masking_assumptions,
            "ablation_per_assumption": self.ablation_per_assumption,
            "synth_model": self.synth_model,
            "synth_total_tokens": self.synth_total_tokens,
            "synth_seconds": round(self.synth_seconds, 3),
            "esbmc_seconds": round(self.esbmc_seconds, 3),
            "attempts": self.attempts,
            "attempt_history": self.attempt_history,
            "seconds": round(self.seconds, 2),
            "error": self.error,
        }


def load_candidates(path: str | Path) -> list[ScanCandidate]:
    """Read the candidate list. Accepts a bare JSON list or {"candidates": [...]}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("candidates", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise TypeError("candidate file must be a JSON list or {'candidates': [...]}")
    return [ScanCandidate.from_dict(item) for item in items]


def _find_unit(units: list, function_name: str):
    """Match by simple name, tolerating a dotted qualname like 'Class.method'."""
    want = function_name.split(".")[-1]
    for unit in units:
        if unit.name == want or unit.qualname == function_name:
            return unit
    return None


def run_pipeline_scan(
    candidates: list[ScanCandidate],
    *,
    synthesizer: HarnessSynthesizer,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    output_dir: str | Path,
    use_compat: bool = True,
    use_guards: bool = True,
    use_ablation: bool = True,
    synth_retries: int = 1,
    completed_results: dict[int, ScanCaseResult] | None = None,
    on_result: Callable[[int, ScanCaseResult], None] | None = None,
) -> list[ScanCaseResult]:
    """Run the scan flow over every candidate and return one result each.

    The three layers are independently toggleable so the ablation study can run
    synth-only, then +compat, +guards, +ablation and compare. ``synth_retries``
    is the number of extra synthesis attempts allowed when an attempt ends in a
    recoverable failure (invalid harness, ESBMC error) rather than a verdict.
    """
    harness_dir = Path(output_dir) / "harnesses"
    harness_dir.mkdir(parents=True, exist_ok=True)

    results: list[ScanCaseResult] = []
    for index, candidate in enumerate(candidates):
        if completed_results and index in completed_results:
            result = completed_results[index]
            print(f"[{index + 1}/{len(candidates)}] Retomada: {candidate.function} já concluído; pulando.")
        else:
            result = _run_one(
                candidate,
                index=index,
                synthesizer=synthesizer,
                esbmc_command=esbmc_command,
                bound=bound,
                timeout_seconds=timeout_seconds,
                harness_dir=harness_dir,
                use_compat=use_compat,
                use_guards=use_guards,
                use_ablation=use_ablation,
                synth_retries=synth_retries,
            )
        results.append(result)
        if on_result is not None:
            on_result(index, result)
    return results


def _run_one(
    candidate: ScanCandidate,
    *,
    index: int,
    synthesizer: HarnessSynthesizer,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
    harness_dir: Path,
    use_compat: bool = True,
    use_guards: bool = True,
    use_ablation: bool = True,
    synth_retries: int = 1,
) -> ScanCaseResult:
    started = time.monotonic()

    source_path = Path(candidate.file)
    if not source_path.exists():
        return _early(candidate, synthesizer.model, CANDIDATE_NOT_FOUND,
                      f"file not found: {candidate.file}", started)

    unit = _find_unit(preprocess_file(source_path), candidate.function)
    if unit is None:
        return _early(candidate, synthesizer.model, CANDIDATE_NOT_FOUND,
                      f"function {candidate.function!r} not found in {candidate.file}", started)

    finding = Finding(
        id=f"scan_{index:03d}",
        stage="scan_candidate",
        finding_type="suspected_bug",
        category=candidate.category,
        title="",
        explanation=candidate.note,
        evidence=[],
        verifiable=True,
        confidence="medium",
        metadata={"expression": candidate.expression},
    )

    history: list[dict] = []
    total_tokens = 0
    total_synth_seconds = 0.0
    total_esbmc_seconds = 0.0
    repair_feedback = ""
    previous_harness = ""
    last: ScanCaseResult | None = None
    for attempt in range(1 + max(0, synth_retries)):
        result = _one_attempt(
            candidate, unit, finding,
            index=index, attempt=attempt,
            synthesizer=synthesizer, esbmc_command=esbmc_command,
            bound=bound, timeout_seconds=timeout_seconds, harness_dir=harness_dir,
            use_compat=use_compat, use_guards=use_guards, use_ablation=use_ablation,
            repair_feedback=repair_feedback,
            previous_harness=previous_harness,
        )
        result.attempts = attempt + 1
        result.seconds = time.monotonic() - started
        total_tokens += result.synth_total_tokens or 0
        total_synth_seconds += result.synth_seconds
        total_esbmc_seconds += result.esbmc_seconds
        history.append(
            {
                "attempt": attempt + 1,
                "classification": result.classification,
                "compat_reasons": result.compat_reasons,
                "esbmc_status": result.esbmc_status,
                "esbmc_summary": result.esbmc_summary,
                "error": result.error,
                "tokens": result.synth_total_tokens,
                "synth_seconds": result.synth_seconds,
                "esbmc_seconds": result.esbmc_seconds,
                "repair_feedback": repair_feedback,
            }
        )
        result.attempt_history = list(history)
        result.synth_total_tokens = total_tokens or None
        result.synth_seconds = total_synth_seconds
        result.esbmc_seconds = total_esbmc_seconds
        last = result
        if result.classification in _CONCLUSIVE:
            return result
        if result.classification not in _RECOVERABLE:
            return result
        repair_feedback = _repair_feedback(result)
        previous_harness = result.harness

    assert last is not None
    return last


def _repair_feedback(result: ScanCaseResult) -> str:
    """Turn deterministic validator output into the next synthesis instruction."""
    if result.compat_reasons:
        return "Compatibility validation failed:\n- " + "\n- ".join(result.compat_reasons)
    if result.classification == NO_PROPERTY:
        return (
            "ESBMC generated no usable property. Add an explicit, reachable assert "
            "for the suspected bug and keep a module-level symbolic driver."
        )
    if result.esbmc_summary:
        return f"ESBMC could not verify the harness: {result.esbmc_summary}"
    return result.error or f"Harness attempt ended as {result.classification}."


def _early(
    candidate: ScanCandidate, model: str, classification: str, error: str, started: float
) -> ScanCaseResult:
    return ScanCaseResult(
        candidate=candidate,
        classification=classification,
        synth_model=model,
        error=error,
        seconds=time.monotonic() - started,
    )


def _one_attempt(
    candidate: ScanCandidate,
    unit,
    finding: Finding,
    *,
    index: int,
    attempt: int,
    synthesizer: HarnessSynthesizer,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
    harness_dir: Path,
    use_compat: bool,
    use_guards: bool,
    use_ablation: bool,
    repair_feedback: str,
    previous_harness: str,
) -> ScanCaseResult:
    started = time.monotonic()
    result = ScanCaseResult(
        candidate=candidate,
        classification=SYNTH_FAILED,
        synth_model=synthesizer.model,
    )

    try:
        synth_result = synthesizer.synthesize(
            unit,
            finding,
            use_guards=use_guards,
            repair_feedback=repair_feedback,
            previous_harness=previous_harness,
        )
    except Exception as exc:  # noqa: BLE001 - network/API failure is reported, not raised
        result.classification = SYNTH_FAILED
        result.error = f"synthesis failed: {exc}"
        result.seconds = time.monotonic() - started
        return result

    result.harness = synth_result.harness
    result.synth_total_tokens = synth_result.telemetry.get("total_tokens")
    result.synth_seconds = float(synth_result.telemetry.get("duration_seconds") or 0.0)

    if use_compat:
        compat = check_harness(synth_result.harness)
        result.compat_verdict = compat.verdict
        result.compat_reasons = list(compat.reasons)
        if not compat.ok:
            result.classification = (
                UNSUPPORTED_HARNESS
                if compat.verdict == VERDICT_UNSUPPORTED
                else INVALID_HARNESS
            )
            result.seconds = time.monotonic() - started
            return result
    else:
        result.compat_verdict = "skipped"

    suffix = f"_try{attempt}" if attempt else ""
    harness_path = harness_dir / f"scan_{index:03d}_{unit.name}{suffix}.py"
    harness_path.write_text(synth_result.harness, encoding="utf-8")
    result.harness_path = str(harness_path)

    esbmc = run_esbmc_direct(
        harness_path,
        esbmc_command=esbmc_command,
        bound=bound,
        timeout_seconds=timeout_seconds,
        output_dir=str(harness_dir),
    )
    result.esbmc_status = esbmc.status
    result.esbmc_summary = esbmc.summary
    result.esbmc_seconds = esbmc.time_seconds

    result.classification = _classify_esbmc(esbmc.status)
    if result.classification == CONFIRMED_ON_ABSTRACTION:
        raw_violated = esbmc.details.get("violated_properties")
        violated = [str(v).strip() for v in raw_violated] if isinstance(raw_violated, list) else []
        if not violated:
            fallback = str(esbmc.details.get("property_kind", "")).strip()
            violated = [fallback] if fallback else []
        if EXPECTED_PROPERTY_MARKER not in violated:
            if violated and all(_looks_like_cover_negation(v) for v in violated):
                # --multi-property showed only __ESBMC_cover's own inverted-assert
                # failing (proving the bug input is reachable, as intended); the
                # marked assert itself was never violated, so this run is safe on
                # this abstraction, not an invalid harness.
                result.classification = SAFE_ON_ABSTRACTION
                result.esbmc_status = "no_violation_found"
            else:
                result.classification = INVALID_HARNESS
                result.compat_verdict = "invalid_harness"
                result.compat_reasons = [
                    (
                        "ESBMC failed a different property "
                        f"({violated[0] if violated else 'unknown'}), not the marked expected assertion"
                    )
                ]
    if use_ablation and result.classification == SAFE_ON_ABSTRACTION:
        report = _ablate_harness(
            synth_result.harness,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
        )
        result.ablation_per_assumption = dict(report.per_assumption)
        if report.over_restricted:
            result.classification = OVER_RESTRICTED
            result.masking_assumptions = list(report.masking_assumptions)

    result.seconds = time.monotonic() - started
    return result


def _looks_like_cover_negation(property_kind: str) -> bool:
    """True when a violated property's text is ESBMC's own inverted-assert form
    for __ESBMC_cover(cond) (compiled internally as assert(!cond)), not a real
    exception or the harness's own marked assert.

    Confirmed empirically (2026-09-04, real ESBMC 8.4.0, --multi-property): a
    tripped __ESBMC_cover always reports as "assertion !(<condition>)"; genuine
    exceptions (invalid int() conversion, uncaught exception on a missing dict
    key) never take this shape. See docs/experiment_log.md EXP-01.
    """
    return property_kind.startswith("assertion !(")


def _classify_esbmc(status: str) -> str:
    if status == "skipped":
        return ESBMC_UNAVAILABLE
    if status == "violation_found":
        return CONFIRMED_ON_ABSTRACTION
    if status in ("no_vcc_generated", "unsupported_case"):
        return NO_PROPERTY
    if status == "no_violation_found":
        return SAFE_ON_ABSTRACTION
    return ESBMC_INCONCLUSIVE


def _ablate_harness(
    harness: str,
    *,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
) -> AblationReport:
    def run(variant_source: str) -> str:
        status = _verdict_on_source(
            variant_source,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
        )
        return FAILED if status == "violation_found" else status.upper()

    return ablate(harness, run)


def _verdict_on_source(
    source: str,
    *,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ablated.py"
        path.write_text(source, encoding="utf-8")
        esbmc = run_esbmc_direct(
            path,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=tmp,
        )
    return esbmc.status
