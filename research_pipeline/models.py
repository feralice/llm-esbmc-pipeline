from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class OperationRecord:
    kind: str
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


@dataclass
class Finding:
    id: str
    stage: str
    finding_type: str
    category: str
    title: str
    explanation: str
    evidence: list[str]
    verifiable: bool
    confidence: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class FormalProperty:
    finding_id: str
    category: str
    hypothesis: str
    assertion: str
    assumptions: list[str]
    notes: str
    insertion_line: int | None = None
    absolute_line: int | None = None


@dataclass
class InstrumentationResult:
    finding_id: str
    category: str
    instrumented_source: str
    assertions: list[str]
    assumptions: list[str]
    output_path: Path


@dataclass
class ESBMCResult:
    finding_id: str
    status: str
    command: list[str]
    returncode: int | None
    summary: str
    stdout: str = ""
    stderr: str = ""
    details: dict[str, object] = field(default_factory=dict)
    raw_log_path: str = ""


@dataclass
class FinalResult:
    unit_name: str
    finding: Finding
    formal_property: FormalProperty | None
    esbmc_result: ESBMCResult | None
    final_classification: str
    interpretation: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["finding"] = asdict(self.finding)
        if self.formal_property is not None:
            data["formal_property"] = asdict(self.formal_property)
        if self.esbmc_result is not None:
            data["esbmc_result"] = asdict(self.esbmc_result)
        return data
