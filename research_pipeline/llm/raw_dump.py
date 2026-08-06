from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from ..models import CodeUnit


def dump_raw_response(model: str, unit: CodeUnit, raw_response: object) -> None:
    """Write the untouched API response to disk, for manual inspection later.

    Opt-in only: no-op unless LLM_RAW_DUMP_DIR is set. Kept outside the
    normal pipeline data model on purpose — this is for reading model
    answers by hand (research notes), not for evaluator.py to consume.
    """
    dump_dir = os.environ.get("LLM_RAW_DUMP_DIR")
    if not dump_dir:
        return

    model_dir = Path(dump_dir) / _safe_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Prefix with the source file stem (e.g. "av_01") so this dump can be
    # matched by eye against the corresponding "<stem>_eval.json" produced
    # by evaluator.py for the same benchmark run.
    file_stem = _safe_name(Path(unit.path).stem)
    stem = _safe_name(f"{file_stem}_{unit.qualname}")
    out_path = model_dir / f"{stem}_{int(time.time() * 1000)}.json"
    out_path.write_text(
        json.dumps(
            {
                "model": model,
                "function": unit.qualname,
                "file": str(unit.path),
                "raw_response": raw_response,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)
