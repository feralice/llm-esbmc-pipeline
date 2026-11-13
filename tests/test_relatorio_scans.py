from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import relatorio_scans


def _hyp(verdict: str, function: str) -> dict:
    return {"verdict": verdict, "hypothesis": {"function": function, "file": "/x/alvos/r/a.py",
                                               "suspect_expression": "d['k']", "trigger_condition": "gatilho"}}


def test_summary_counts_everything_but_lists_only_checked_verdicts(tmp_path: Path) -> None:
    (tmp_path / "scan_checkpoint.json").write_text(json.dumps({"verify_results": {
        "1": _hyp("CONFIRMED", "f"), "2": _hyp("LLM_ONLY", "g"), "3": _hyp("LLM_ONLY", "h")}}))
    text = relatorio_scans.summarize([tmp_path])
    assert "'LLM_ONLY': 2" in text and "`f`" in text and "`g`" not in text
    assert "não (rodada incompleta)" in text and "Nada aqui é achado confirmado" in text
