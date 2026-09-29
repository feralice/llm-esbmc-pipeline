"""Recompute verify-engine verdicts offline after a change to the confirmation rule or the replay.

For every result whose last attempt reached an ESBMC verdict, the stored violated properties are
re-read and the CPython replay is re-run on the stored program; no LLM call and no ESBMC run.
Usage: python scripts/v2_reverdict.py <v2_verify_report.json> [--ground-truth ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.candidate import Candidate  # noqa: E402
from research_pipeline.verify.astutil import expression_nodes, find_function  # noqa: E402
from research_pipeline.verify.outcome import EsbmcReading, _python_exceptions, final_verdict  # noqa: E402
from research_pipeline.verify.render import Program  # noqa: E402
from research_pipeline.verify.replay import concrete_replay  # noqa: E402
from research_pipeline.verify.report import evaluate_verify, summarize  # noqa: E402

import ast  # noqa: E402

_CHECKED_READINGS = {"violation", "artifact", "safe"}


def _program(path: Path, hypothesis: dict) -> Program | None:
    source = path.read_text(encoding="utf-8")
    function = find_function(ast.parse(source), hypothesis["function"])
    if function is None:
        return None
    nodes = expression_nodes(function, hypothesis["suspect_expression"])
    if not nodes:
        return None
    spans = tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes}))
    return Program(source, 0, spans, (), (function.lineno, function.end_lineno))


def reverdict_result(result: dict) -> dict:
    attempts = result.get("attempts") or []
    reading_kind = attempts[-1].get("reading") if attempts else None
    if reading_kind not in _CHECKED_READINGS or not result.get("program_path"):
        return result
    kinds = result["reason"].split("; ") if reading_kind == "violation" else []
    reading = EsbmcReading(reading_kind, result["reason"],
                           frozenset(name for kind in kinds for name in _python_exceptions(kind)))
    program = _program(Path(result["program_path"]), result["hypothesis"])
    if program is None:
        return result
    replay = concrete_replay(program, result["hypothesis"]["function"].split(".")[-1])
    verdict = final_verdict(reading, replay)
    result["reverdict"] = {"previous": result["verdict"], "previous_replay": result.get("replay")}
    result.update(verdict=verdict, replay=replay.to_dict())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--ground-truth", default="dataset/v2_real_world/ground_truths.json")
    args = parser.parse_args()
    path = Path(args.report)
    report = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for result in report["results"]:
        before = result["verdict"]
        reverdict_result(result)
        if result["verdict"] != before:
            changed += 1
            print(f"{result['hypothesis']['function']}: {before} -> {result['verdict']}")
    report["verification"] = summarize(report["results"])
    detection = report.get("detection") or {}
    if report.get("evaluation") and detection.get("candidates"):
        candidates = [Candidate.from_dict(c) for c in detection["candidates"]]
        sources = report["config"]["input_files"]
        report["evaluation"] = evaluate_verify(report["results"], candidates, args.ground_truth, sources,
                                               detection.get("rejected_findings", []))
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{changed} veredito(s) alterado(s); {report['verification']['by_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
