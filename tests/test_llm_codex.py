import json
from pathlib import Path

from research_pipeline.llm.backends.codex import CodexAnalyzer
from research_pipeline.preprocess import preprocess_file


def test_codex_analyzer_parses_cli_json_and_normalizes(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(a: int, b: int) -> int:\n    return a // b\n", encoding="utf-8")
    unit = preprocess_file(source)[0]

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps({
            "findings": [{
                "finding_type": "suspected_bug",
                "category": "division_by_zero",
                "explanation": "divisor may be zero",
                "verifiable": True,
                "metadata": {"expression": "a // b"},
            }]
        }), encoding="utf-8")
        return type("Completed", (), {
            "returncode": 0,
            "stdout": '{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":4}}\n',
            "stderr": "",
        })()

    monkeypatch.setattr("research_pipeline.llm.backends.codex.subprocess.run", fake_run)

    analyzer = CodexAnalyzer(timeout_seconds=10)
    findings = analyzer.analyze(unit)

    assert len(findings) == 1
    assert findings[0].finding_type == "suspected_bug"
    assert findings[0].verifiable is True
    assert analyzer.telemetry_events[0]["provider"] == "codex"
    assert analyzer.telemetry_events[0]["total_tokens"] == 7
