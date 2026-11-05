from __future__ import annotations

import json
from pathlib import Path

import main
from research_pipeline.hypothesis_cap import cap_per_function
from research_pipeline.models import Finding
from research_pipeline.verify.candidate import Candidate


def _candidate(expression: str, function: str = "f", file: str = "a.py", oracle: str = "") -> Candidate:
    return Candidate(file=file, function=function, expression=expression, oracle=oracle)


def test_keeps_the_first_n_distinct_expressions_of_each_function_in_llm_order() -> None:
    candidates = [_candidate("a / b"), _candidate("a/b"), _candidate("xs[0]"), _candidate("d[k]"),
                  _candidate("y.z", function="g"), _candidate("q[1]", file="b.py")]
    kept, dropped = cap_per_function(candidates, 2)
    assert [c.expression for c in kept] == ["a / b", "xs[0]", "y.z", "q[1]"]
    assert [c.expression for c in dropped] == ["a/b", "d[k]"]


def test_the_prompt_rename_and_the_oracle_decide_what_counts_as_a_repeat() -> None:
    candidates = [_candidate("f(x - 1)"), _candidate("target_function(x - 1)"),
                  _candidate("f(x - 1)", oracle="value")]
    kept, dropped = cap_per_function(candidates, 5)
    assert [c.expression for c in dropped] == ["target_function(x - 1)"]
    assert [c.oracle for c in kept] == ["", "value"]


class _ThreeFindings:
    def analyze(self, unit):
        return [Finding(id=str(i), stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                        explanation="", evidence=[], verifiable=True, confidence="high",
                        metadata={"expression": expression})
                for i, expression in enumerate(("x // y", "x+1", "y - 1"))]


def _detect(tmp_path: Path, monkeypatch, *extra: str) -> dict:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y + x+1 + y - 1\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _ThreeFindings())
    monkeypatch.setattr(main, "LLMClient", lambda **kwargs: type("S", (), {"model": ""})())
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out), *extra])
    assert main.mode_v2(args) == 0
    return json.loads((out / "v2_verify_report.json").read_text())


def test_the_cli_cap_sends_the_first_n_and_keeps_the_rest_in_the_report(tmp_path: Path, monkeypatch) -> None:
    report = _detect(tmp_path, monkeypatch, "--max-hypotheses-per-function", "2")
    assert [c["expression"] for c in report["detection"]["candidates"]] == ["x // y", "x+1"]
    assert [c["expression"] for c in report["detection"]["capped_candidates"]] == ["y - 1"]
    assert report["detection"]["hypotheses"] == 2 and report["config"]["max_hypotheses_per_function"] == 2


def test_without_the_option_nothing_is_capped_and_the_config_is_unchanged(tmp_path: Path, monkeypatch) -> None:
    report = _detect(tmp_path, monkeypatch)
    assert len(report["detection"]["candidates"]) == 3 and report["detection"]["capped_candidates"] == []
    assert "max_hypotheses_per_function" not in report["config"]
