"""Step 4 of the scan mode: the orchestrator.

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
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Finding
from ..preprocess import preprocess_file
from ..verification.esbmc_runner import run_esbmc_direct
from .ablation import FAILED, AblationReport, ablate
from .compat import VERDICT_UNSUPPORTED, check_harness
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
    seconds: float = 0.0
    error: str = ""

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
            "seconds": round(self.seconds, 2),
            "error": self.error,
        }


def load_candidates(path: str | Path) -> list[ScanCandidate]:
    """Read the candidate list. Accepts a bare JSON list or {"candidates": [...]}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("candidates", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("candidate file must be a JSON list or {'candidates': [...]}")
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
) -> list[ScanCaseResult]:
    """Run the scan flow over every candidate and return one result each.

    The three layers are independently toggleable so the ablation study can run
    synth-only, then +compat, +guards, +ablation and compare.
    """
    harness_dir = Path(output_dir) / "harnesses"
    harness_dir.mkdir(parents=True, exist_ok=True)

    results: list[ScanCaseResult] = []
    for index, candidate in enumerate(candidates):
        results.append(
            _run_one(
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
            )
        )
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
) -> ScanCaseResult:
    started = time.monotonic()
    result = ScanCaseResult(
        candidate=candidate,
        classification=SYNTH_FAILED,
        synth_model=synthesizer.model,
    )

    source_path = Path(candidate.file)
    if not source_path.exists():
        result.classification = CANDIDATE_NOT_FOUND
        result.error = f"file not found: {candidate.file}"
        result.seconds = time.monotonic() - started
        return result

    unit = _find_unit(preprocess_file(source_path), candidate.function)
    if unit is None:
        result.classification = CANDIDATE_NOT_FOUND
        result.error = f"function {candidate.function!r} not found in {candidate.file}"
        result.seconds = time.monotonic() - started
        return result

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

    try:
        synth_result = synthesizer.synthesize(unit, finding, use_guards=use_guards)
    except Exception as exc:  # noqa: BLE001 - network/API failure is reported, not raised
        result.classification = SYNTH_FAILED
        result.error = f"synthesis failed: {exc}"
        result.seconds = time.monotonic() - started
        return result

    result.harness = synth_result.harness
    result.synth_total_tokens = synth_result.telemetry.get("total_tokens")

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

    harness_path = harness_dir / f"scan_{index:03d}_{unit.name}.py"
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

    result.classification = _classify_esbmc(esbmc.status)
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
