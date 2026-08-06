from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# AST / Preprocess layer
# ---------------------------------------------------------------------------

@dataclass
class OperationRecord:
    """Operation extracted from a function body during preprocessing."""

    kind: str          # Operation kind: "division", "subscript", or "call".
    expression: str    # Normalized source text for the operation, e.g. "a / b".
    line: int          # Absolute line in the source file.
    relative_line: int # Line relative to the start of the function.


@dataclass
class CodeUnit:
    """One analyzable Python function extracted from a source file."""

    path: Path                         # File that contains the function.
    name: str                          # Simple function name, e.g. "divide".
    qualname: str                      # Qualified name, including class scope when present.
    source: str                        # Exact source code for this function.
    start_line: int                    # First line of the function in the file.
    end_line: int                      # Last line of the function in the file.
    parameters: list[str]              # Function parameters, e.g. ["a", "b"].
    type_hints: dict[str, str]         # Parameter and return annotations.
    operations: list[OperationRecord]  # AST-extracted operations used for validation.
    loops: list[str]                   # Loop source snippets found in the function.
    conditionals: list[str]            # If-condition expressions.
    guards: list[str]                  # Conditions/assertions that may guard unsafe operations.
    metrics: dict[str, int]            # Simple metrics such as line and parameter count.


# ---------------------------------------------------------------------------
# LLM layer
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A candidate issue reported by the LLM or synthesized by the pipeline."""

    id: str
    stage: str          # Pipeline stage that produced the finding, usually "llm_analysis".
    finding_type: str   # "suspected_bug" | "smell_heuristic" | "llm_false_positive"
    category: str       # Issue category, e.g. "division_by_zero" or "long_method".
    title: str
    explanation: str
    evidence: list[str]
    verifiable: bool    # True when the finding can be sent to ESBMC.
    confidence: str
    metadata: dict[str, object] = field(default_factory=dict) # Extra data: expression, line, function, etc.


# ---------------------------------------------------------------------------
# ESBMC layer  (two variants: direct and function-scoped)
# ---------------------------------------------------------------------------

@dataclass
class ESBMCResult:
    """Result of running ESBMC on a function (Flow B, --function flag)."""

    finding_id: str
    status: str          # violation_found | no_violation_found | inconclusive | skipped | tool_error
    command: list[str]   # Exact ESBMC command that was executed.
    returncode: int | None
    summary: str         # Human-readable summary of the verification result.
    time_seconds: float = 0.0
    stdout: str = ""     # Raw ESBMC stdout.
    stderr: str = ""     # Pretty/diagnostic output shown in reports.
    details: dict[str, object] = field(default_factory=dict) # Parsed property, location, counterexample, etc.
    raw_log_path: str = "" # Path to the full ESBMC log.


@dataclass
class ESBMCDirectResult:
    """Aggregated result for the ESBMC-only baseline (Flow A)."""

    source_file: str
    status: str          # violation_found | no_violation_found | no_vcc_generated | timeout | tool_error | unsupported_case | skipped | inconclusive
    command: list[str]   # Baseline command shape; per-function commands live in details.
    returncode: int | None
    summary: str         # Human-readable summary for Flow A.
    time_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    details: dict[str, object] = field(default_factory=dict) # Aggregated per-function ESBMC data.
    raw_log_path: str = ""

    def to_dict(self) -> dict:
        """Serialize the direct ESBMC result to a JSON-friendly dictionary."""

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

# Canonical classification values used across report.py, pipeline.py, evaluator.py.
# They are grouped by the kind of result they describe.

# Formal bug classifications: used when the finding is a verifiable bug candidate.
CLASSIFICATION_ESBMC_NATIVE_BUG        = "esbmc_native_bug"
CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC  = "llm_confirmed_by_esbmc"
CLASSIFICATION_LLM_MISSED_ESBMC_BUG    = "llm_missed_esbmc_bug"
CLASSIFICATION_LLM_ONLY                = "llm_only_suspected"
CLASSIFICATION_NOT_CONFIRMED           = "not_confirmed_within_bound"
CLASSIFICATION_ESBMC_INCONCLUSIVE      = "esbmc_inconclusive"

# LLM/AST rejection: used when the LLM proposed something invalid or outside scope.
CLASSIFICATION_LLM_FALSE_POSITIVE      = "llm_false_positive"
CLASSIFICATION_OUT_OF_SCOPE            = "out_of_scope_finding"

# Code smell classification: smells are heuristic and never go to ESBMC.
CLASSIFICATION_HEURISTIC_SMELL         = "heuristic_smell_only"

# Generic skip: used when the pipeline cannot turn a finding into a formal check.
CLASSIFICATION_SKIPPED                 = "skipped_not_verifiable"


@dataclass
class FinalResult:
    """Final user/report-facing result after LLM, AST and ESBMC decisions."""

    unit_name: str
    source_file: str
    finding: Finding
    esbmc_result: ESBMCResult | None              # Flow B verification result, when available.
    esbmc_direct_result: ESBMCDirectResult | None # Flow A baseline result, when available.
    final_classification: str                     # Canonical classification constant.
    interpretation: str                           # Human-readable explanation.

    def to_dict(self) -> dict:
        """Serialize the final result to a JSON-friendly dictionary."""

        data: dict = {
            "unit_name": self.unit_name,
            "source_file": self.source_file,
            "final_classification": self.final_classification,
            "interpretation": self.interpretation,
            "finding": asdict(self.finding),
            "esbmc_result": asdict(self.esbmc_result) if self.esbmc_result else None,
            "esbmc_direct_result": self.esbmc_direct_result.to_dict() if self.esbmc_direct_result else None,
        }
        return data
