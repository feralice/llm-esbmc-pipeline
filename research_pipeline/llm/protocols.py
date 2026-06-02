from __future__ import annotations

from typing import Protocol

from ..models import CodeUnit, Finding


class LLMAnalyzer(Protocol):
    def analyze(self, unit: CodeUnit) -> list[Finding]: ...
