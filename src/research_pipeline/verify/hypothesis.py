"""The bug hypothesis: fixed at detection, never rewritten by later stages."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from .candidate import Candidate


@dataclass(frozen=True)
class BugHypothesis:
    file: str
    function: str
    suspect_expression: str
    line: int = 0
    trigger_condition: str = ""
    category: str = ""

    @property
    def hypothesis_id(self) -> str:
        key = "|".join((self.file, self.function, str(self.line), self.suspect_expression))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def from_candidate(cls, candidate: Candidate, line: int = 0) -> BugHypothesis:
        return cls(
            file=candidate.file,
            function=candidate.function,
            suspect_expression=candidate.expression,
            line=line,
            trigger_condition=candidate.note,
            category=candidate.category,
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "hypothesis_id": self.hypothesis_id}
