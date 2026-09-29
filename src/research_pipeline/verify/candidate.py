"""A bug hypothesis as detection produces it: file, function, category, expression, explanation."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Candidate:
    file: str
    function: str
    category: str
    expression: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Candidate:
        """Older checkpoints may carry extra keys (e.g. harness_strategy); they are ignored."""
        missing = [key for key in ("file", "function", "category") if not data.get(key)]
        if missing:
            raise ValueError(f"candidate missing field(s): {', '.join(missing)}")
        return cls(str(data["file"]), str(data["function"]), str(data["category"]),
                   str(data.get("expression", "")), str(data.get("note", "")))
