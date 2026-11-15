"""Measure exact AST duplicate groups in saved scan reports, without LLM calls.

Usage: python scripts/medir_dedupe.py scan_report.json [...]
Source files must still be present at the paths recorded in the report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from research_pipeline.scan.dedupe import deduplicate, function_ast  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402


def measure(path: Path) -> dict:
    report = json.loads(path.read_text(encoding='utf-8'))
    hypotheses = [BugHypothesis(**{k: v for k, v in r['hypothesis'].items() if k != 'hypothesis_id'})
                  for r in report.get('results', [])]
    bodies = {}
    for h in hypotheses:
        key = (h.file, h.function)
        if key in bodies:
            continue
        try:
            bodies[key] = function_ast(Path(h.file).read_text(encoding='utf-8'), h.function)
        except (OSError, UnicodeError):
            bodies[key] = None
    representatives, groups = deduplicate(hypotheses, lambda h: bodies[(h.file, h.function)])
    return {'hypotheses': len(hypotheses), 'representatives': len(representatives),
            'collapsed': len(hypotheses) - len(representatives), 'duplicates': groups,
            'unresolved_sources': sum(bodies[(h.file, h.function)] is None for h in hypotheses)}


def main(paths: list[str]) -> int:
    for path in paths:
        print(json.dumps({'report': path, **measure(Path(path))}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
