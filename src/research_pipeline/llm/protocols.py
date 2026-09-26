from __future__ import annotations

from typing import Protocol

from ..models import CodeUnit, Finding
from .staged import ClassificationResult, LocationCandidate, Stage


class LLMAnalyzer(Protocol):
    def analyze(self, unit: CodeUnit) -> list[Finding]: ...

    def analyze_stage(
        self,
        unit: CodeUnit,
        *,
        stage: Stage,
        candidates: list[LocationCandidate] | None = None,
    ) -> list[LocationCandidate] | list[ClassificationResult]: ...
