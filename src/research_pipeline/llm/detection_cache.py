"""Persistent cache of detection output per function, so a rerun does not pay for the same LLM call again.

The key covers everything that shapes the answer: the function's source, the model and backend, the prompt
variants, the flags, and the system prompt text. Any change to one of them is a miss, never a stale hit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.models import CodeUnit, Finding

_FORMAT = "detection-cache-v1"


def make_cache(analyzer, root: Path) -> DetectionCache:
    system_prompt = load_system_prompt(include_smells=bool(getattr(analyzer, "include_smells", True)),
                                       v2_detection=bool(getattr(analyzer, "v2_detection", False)),
                                       v2_variants=tuple(getattr(analyzer, "v2_variants", ()) or ()))
    return DetectionCache(root, _fingerprint(analyzer, system_prompt))


def _fingerprint(analyzer, system_prompt: str) -> str:
    settings = {
        "format": _FORMAT,
        "class": type(analyzer).__name__,
        "model": getattr(analyzer, "model", ""),
        "variants": list(getattr(analyzer, "v2_variants", ()) or ()),
        "include_smells": bool(getattr(analyzer, "include_smells", False)),
        "v2_detection": bool(getattr(analyzer, "v2_detection", False)),
        "system_prompt": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()


class DetectionCache:
    def __init__(self, root: Path, key_prefix: str):
        self.root = Path(root)
        self.key_prefix = key_prefix

    def _path(self, unit: CodeUnit) -> Path:
        digest = hashlib.sha256(f"{self.key_prefix}\0{unit.source}".encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, unit: CodeUnit) -> tuple[list[Finding], dict] | None:
        path = self._path(unit)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            findings = [Finding(**item) for item in data["findings"]]
            trace = dict(data["trace"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return findings, trace

    def put(self, unit: CodeUnit, findings: list[Finding], trace: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"findings": [asdict(f) for f in findings], "trace": trace}
        tmp = self._path(unit).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path(unit))
