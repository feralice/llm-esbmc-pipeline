from __future__ import annotations

import json
from pathlib import Path

import main
from research_pipeline.models import Finding
from research_pipeline.verify.llm_client import SynthResult

SCORES = {"x // y": 9, "x+1": 2, "y - 1": 5}


class _ThreeFindings:
    def analyze(self, unit):
        return [Finding(id=str(i), stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                        explanation="", evidence=[], verifiable=True, confidence="high",
                        metadata={"expression": expression})
                for i, expression in enumerate(SCORES)]


class _Reviewer:
    model = ""
    calls = 0
    answer = None

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        type(self).calls += 1
        expression = next(e for e in SCORES if f"suspect expression: {e}\n" in user_prompt)
        text = type(self).answer or json.dumps({"explanation": "e", "guard_found": False, "feasible": True,
                                                "score": SCORES[expression]})
        return SynthResult(harness=text, raw_response=text, model="fake")


def _detect(tmp_path: Path, monkeypatch, *extra: str, resume: bool = False) -> dict:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y + x+1 + y - 1\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _ThreeFindings())
    monkeypatch.setattr(main, "LLMClient", lambda **kwargs: _Reviewer())
    out = tmp_path / "out"
    argv = ["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source), "--output-dir", str(out), *extra]
    if resume:
        argv.append("--resume")
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    return json.loads((out / "v2_verify_report.json").read_text())


def setup_function(_):
    _Reviewer.calls, _Reviewer.answer = 0, None


def test_no_threshold_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    report = _detect(tmp_path, monkeypatch)
    assert len(report["detection"]["candidates"]) == 3 and "review_dropped" not in report["detection"]
    assert "review_threshold" not in report["config"] and _Reviewer.calls == 0


def test_threshold_drops_low_scores_into_the_report(tmp_path: Path, monkeypatch) -> None:
    report = _detect(tmp_path, monkeypatch, "--review-threshold", "5")
    assert [c["expression"] for c in report["detection"]["candidates"]] == ["x // y", "y - 1"]
    dropped = report["detection"]["review_dropped"]
    assert [d["expression"] for d in dropped] == ["x+1"] and dropped[0]["score"] == 2.0
    assert dropped[0]["explanation"] == "e" and report["detection"]["review_errors"] == 0
    assert report["config"]["review_threshold"] == 5.0


def test_resume_does_not_call_the_reviewer_again(tmp_path: Path, monkeypatch) -> None:
    _detect(tmp_path, monkeypatch, "--review-threshold", "5")
    assert _Reviewer.calls == 3
    report = _detect(tmp_path, monkeypatch, "--review-threshold", "5", resume=True)
    assert _Reviewer.calls == 3
    assert [d["expression"] for d in report["detection"]["review_dropped"]] == ["x+1"]


def test_review_error_keeps_the_candidate(tmp_path: Path, monkeypatch) -> None:
    _Reviewer.answer = "garbage"
    report = _detect(tmp_path, monkeypatch, "--review-threshold", "9")
    assert len(report["detection"]["candidates"]) == 3
    assert report["detection"]["review_dropped"] == [] and report["detection"]["review_errors"] == 3


def test_threshold_must_be_between_0_and_10(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(SystemExit):
        main.build_parser().parse_args(["--review-threshold", "11"])


class _ReviewerThatHitsTheLimit(_Reviewer):
    def __init__(self):
        self.telemetry_events = []

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        if type(self).calls >= 1:
            from research_pipeline.llm.rate_limit import UsageLimitReached
            raise UsageLimitReached("You've hit your 5-hour limit")
        self.telemetry_events.append({"provider": "claude_cli", "requested_model": "sonnet", "status": "success",
                                      "prompt_tokens": 5, "completion_tokens": 9, "cost_usd": 0.01,
                                      "cost_source": "cli_reported", "billed_usd": None})
        return super().complete(system_prompt, user_prompt, json_mode=json_mode)


def test_calls_made_before_the_usage_limit_stay_in_the_telemetry(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y + x+1 + y - 1\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _ThreeFindings())
    monkeypatch.setattr(main, "LLMClient", lambda **kwargs: _ReviewerThatHitsTheLimit())
    out = tmp_path / "out"
    argv = ["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source), "--output-dir", str(out),
            "--review-threshold", "5"]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == main.USAGE_LIMIT_EXIT
    events = json.loads((out / "llm_telemetry.json").read_text())
    assert [e["stage"] for e in events] == ["synthesis"]
    assert events[0]["cost_usd"] == 0.01
