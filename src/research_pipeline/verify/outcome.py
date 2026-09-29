"""Read an ESBMC run and combine it with the CPython replay into the final verdict."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from research_pipeline.models import ESBMCDirectResult
from .diagnose import diagnose_esbmc
from research_pipeline.verification.esbmc_runner import only_verifier_artifacts

from .replay import ReplayVerdict

CONFIRMED = "CONFIRMED"
ESBMC_MISSED = "ESBMC_MISSED"
UNVALIDATED = "UNVALIDATED"
OTHER_FAILURE = "OTHER_FAILURE"
NOT_CONFIRMED = "NOT_CONFIRMED"
GROUNDING_FAILED = "GROUNDING_FAILED"
MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
UNSUPPORTED = "UNSUPPORTED"
SPEC_FAILED = "SPEC_FAILED"
ESBMC_TIMEOUT = "ESBMC_TIMEOUT"
ESBMC_ERROR = "ESBMC_ERROR"
PIPELINE_ERROR = "PIPELINE_ERROR"
NO_SOURCE = "NO_SOURCE"

VERDICTS = (CONFIRMED, ESBMC_MISSED, UNVALIDATED, OTHER_FAILURE, NOT_CONFIRMED, GROUNDING_FAILED,
            MISSING_DEPENDENCY, UNSUPPORTED, SPEC_FAILED, ESBMC_TIMEOUT, ESBMC_ERROR, PIPELINE_ERROR, NO_SOURCE)
# Verdicts reached by a program ESBMC actually checked: the success@k numerator.
CHECKED = frozenset({CONFIRMED, ESBMC_MISSED, UNVALIDATED, OTHER_FAILURE, NOT_CONFIRMED})

# "inconclusive" is VERIFICATION UNKNOWN or a crash without a verdict, never evidence of safety.
_SAFE_STATUSES = frozenset({"no_violation_found", "no_vcc_generated"})


@dataclass(frozen=True)
class EsbmcReading:
    # violation | artifact | safe | repairable | missing_dependency | timeout | error
    kind: str
    message: str
    # CPython exceptions the reported violations correspond to.
    exceptions: frozenset[str] = field(default_factory=frozenset)


def _python_exceptions(kind: str) -> set[str]:
    match = re.match(r"uncaught exception: ([A-Za-z_]\w*)", kind) or re.match(r"([A-Z]\w*(?:Error|Exception))\b", kind)
    if match:
        return {match.group(1)}
    lowered = kind.lower()
    if lowered.startswith("assertion "):
        # A failed `assert` of the program itself; "unwinding assertion" is a bound artefact.
        return {"AssertionError"}
    if "division by zero" in lowered:
        return {"ZeroDivisionError"}
    if "null pointer" in lowered:
        return {"AttributeError", "TypeError"}
    if "array bounds" in lowered or "out-of-bounds read in list" in lowered or "index out of bounds" in lowered:
        return {"IndexError"}
    return set()


def classify_esbmc(result: ESBMCDirectResult) -> EsbmcReading:
    status = result.status
    if status == "violation_found":
        if only_verifier_artifacts(result.details):
            return EsbmcReading("artifact", "; ".join(result.details.get("violated_properties") or []))
        kinds = [str(k) for k in result.details.get("violated_properties") or []]
        names = frozenset(name for kind in kinds for name in _python_exceptions(kind))
        return EsbmcReading("violation", "; ".join(kinds), names)
    if status in _SAFE_STATUSES:
        return EsbmcReading("safe", status)
    if status == "timeout":
        return EsbmcReading("timeout", result.summary)
    if status in {"tool_error", "unsupported_case"}:
        diagnostic = diagnose_esbmc(status, result.stdout, result.stderr, result.raw_log_path,
                                    summary=result.summary)
        if diagnostic.kind in {"import", "dependency"}:
            return EsbmcReading("missing_dependency", diagnostic.message)
        if diagnostic.kind == "timeout":
            return EsbmcReading("timeout", diagnostic.message)
        return EsbmcReading("repairable", diagnostic.message)
    return EsbmcReading("error", result.summary or status)


_TERMINAL = {"timeout": ESBMC_TIMEOUT, "missing_dependency": MISSING_DEPENDENCY,
             "repairable": UNSUPPORTED, "error": ESBMC_ERROR}


def final_verdict(reading: EsbmcReading, replay: ReplayVerdict) -> str:
    if reading.kind == "violation":
        if replay.status == "reproduced":
            # ESBMC must have seen the same failure the replay reproduced at the hypothesis.
            return CONFIRMED if replay.exception_type in reading.exceptions else UNVALIDATED
        return OTHER_FAILURE if replay.status == "other_failure" else UNVALIDATED
    if reading.kind in {"safe", "artifact"}:
        return ESBMC_MISSED if replay.status == "reproduced" else NOT_CONFIRMED
    return _TERMINAL[reading.kind]
