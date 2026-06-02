from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# AST / Preprocess layer
# ---------------------------------------------------------------------------

@dataclass
class OperationRecord:
    kind: str          # "division" | "subscript" | "call"
    expression: str
    line: int
    relative_line: int


@dataclass
class CodeUnit:
    path: Path
    name: str
    qualname: str
    source: str
    start_line: int
    end_line: int
    parameters: list[str]
    type_hints: dict[str, str]
    operations: list[OperationRecord]
    loops: list[str]
    conditionals: list[str]
    guards: list[str]
    metrics: dict[str, int]


# ---------------------------------------------------------------------------
# LLM layer
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    id: str
    stage: str
    finding_type: str   # "suspected_bug" | "smell_heuristic" | "llm_false_positive"
    category: str
    title: str
    explanation: str
    evidence: list[str]
    verifiable: bool
    confidence: str
    metadata: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Formalization layer
# ---------------------------------------------------------------------------

@dataclass
class FormalProperty:
    finding_id: str
    category: str
    hypothesis: str
    assertion: str
    assumptions: list[str]
    esbmc_flags: list[str]
    notes: str
    insertion_line: int | None = None
    absolute_line: int | None = None


# ---------------------------------------------------------------------------
# Instrumentation layer
# ---------------------------------------------------------------------------

@dataclass
class InstrumentationResult:
    finding_id: str
    category: str
    instrumented_source: str
    assertions: list[str]
    assumptions: list[str]
    esbmc_flags: list[str]
    output_path: Path


# ---------------------------------------------------------------------------
# ESBMC layer  (two variants: direct and instrumented)
# ---------------------------------------------------------------------------

@dataclass
class ESBMCResult:
    """Result of running ESBMC on an *instrumented* file (Flow B)."""
    finding_id: str
    status: str          # violation_found | no_violation_found | inconclusive | skipped | tool_error
    command: list[str]
    returncode: int | None
    summary: str
    time_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    details: dict[str, object] = field(default_factory=dict)
    raw_log_path: str = ""


@dataclass
class ESBMCDirectResult:
    """Result of running ESBMC directly on the *original* file (Flow A)."""
    source_file: str
    status: str          # violation_found | no_violation_found | no_vcc_generated | timeout | tool_error | unsupported_case | skipped | inconclusive
    command: list[str]
    returncode: int | None
    summary: str
    time_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    details: dict[str, object] = field(default_factory=dict)
    raw_log_path: str = ""

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "status": self.status,
            "command": self.command,
            "returncode": self.returncode,
            "summary": self.summary,
            "time_seconds": self.time_seconds,
            "details": self.details,
            "raw_log_path": self.raw_log_path,
        }


# ---------------------------------------------------------------------------
# Final classification layer
# ---------------------------------------------------------------------------

# Canonical classification values used across report.py, pipeline.py, evaluator.py
CLASSIFICATION_ESBMC_NATIVE_BUG        = "esbmc_native_bug"
CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC  = "llm_confirmed_by_esbmc"
CLASSIFICATION_LLM_MISSED_ESBMC_BUG    = "llm_missed_esbmc_bug"
CLASSIFICATION_LLM_FALSE_POSITIVE      = "llm_false_positive"
CLASSIFICATION_NOT_CONFIRMED           = "not_confirmed_within_bound"
CLASSIFICATION_ESBMC_INCONCLUSIVE      = "esbmc_inconclusive"
CLASSIFICATION_HEURISTIC_SMELL         = "heuristic_smell_only"
CLASSIFICATION_SKIPPED                 = "skipped_not_verifiable"
CLASSIFICATION_OUT_OF_SCOPE            = "out_of_scope_finding"
# Runtime harness validation (fallback when ESBMC cannot formalize the pattern)
CLASSIFICATION_RUNTIME_REPRODUCED      = "runtime_reproduced_by_harness"
CLASSIFICATION_RUNTIME_NOT_REPRODUCED  = "runtime_not_reproduced"
CLASSIFICATION_RUNTIME_INCONCLUSIVE    = "runtime_inconclusive"


@dataclass
class FinalResult:
    unit_name: str
    source_file: str
    finding: Finding
    formal_property: FormalProperty | None
    esbmc_result: ESBMCResult | None
    esbmc_direct_result: ESBMCDirectResult | None
    final_classification: str
    interpretation: str
    # Runtime harness result (dict from HarnessValidationResult.to_dict()), set when
    # the Formalizer cannot generate a formal property and a harness is used instead.
    harness_result: dict | None = None

    def to_dict(self) -> dict:
        data: dict = {
            "unit_name": self.unit_name,
            "source_file": self.source_file,
            "final_classification": self.final_classification,
            "interpretation": self.interpretation,
            "finding": asdict(self.finding),
            "formal_property": asdict(self.formal_property) if self.formal_property else None,
            "esbmc_result": asdict(self.esbmc_result) if self.esbmc_result else None,
            "esbmc_direct_result": self.esbmc_direct_result.to_dict() if self.esbmc_direct_result else None,
            "harness_result": self.harness_result,
        }
        return data
