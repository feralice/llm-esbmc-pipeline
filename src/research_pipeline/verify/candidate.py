"""A bug hypothesis as detection produces it: file, function, expression, explanation, violated property.

V2 detection gives no category; oracle runs keep the ground truth's as a label.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Candidate:
    file: str
    function: str
    category: str = ""
    expression: str = ""
    note: str = ""
    violated_property: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Candidate:
        """Older checkpoints may carry extra keys (e.g. harness_strategy); they are ignored."""
        missing = [key for key in ("file", "function") if not data.get(key)]
        if missing:
            raise ValueError(f"candidate missing field(s): {', '.join(missing)}")
        return cls(str(data["file"]), str(data["function"]), str(data.get("category", "")),
                   str(data.get("expression", "")), str(data.get("note", "")),
                   str(data.get("violated_property", "")))
