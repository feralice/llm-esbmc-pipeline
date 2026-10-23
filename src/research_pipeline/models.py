from __future__ import annotations

from dataclasses import dataclass, field
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
    """One analyzable function or module-level source unit."""

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
    kind: str = "function"             # ``function`` or ``module``.
    caller_context: str = ""           # Call sites from the repo graph (scan mode, variant A12).


# ---------------------------------------------------------------------------
# LLM layer
# ---------------------------------------------------------------------------

# Finding.confidence_source values. Keep in one place so a groupby over
# "accuracy by confidence" (or any future consumer) can filter by source
# instead of trusting the confidence string alone.
CONFIDENCE_SOURCE_LLM_SELF_REPORT = "llm_self_report"      # model's own "low"/"medium"/"high" guess
CONFIDENCE_SOURCE_UNSPECIFIED = "unspecified"               # constructed before this taxonomy existed


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
    confidence_source: str = CONFIDENCE_SOURCE_UNSPECIFIED


# ---------------------------------------------------------------------------
# ESBMC layer
# ---------------------------------------------------------------------------

@dataclass
class ESBMCDirectResult:
    """Result of one ESBMC run on a file (see run_esbmc_direct)."""

    source_file: str
    status: str          # violation_found | no_violation_found | no_vcc_generated | timeout | tool_error | unsupported_case | skipped | inconclusive
    command: list[str]   # Exact ESBMC command that was executed.
    returncode: int | None
    summary: str         # Human-readable summary of the verification result.
    time_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    details: dict[str, object] = field(default_factory=dict) # Parsed property, location, counterexample, etc.
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

