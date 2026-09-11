from __future__ import annotations

from pathlib import Path

import pytest

from research_pipeline.models import Finding
from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan.synth import (
    STYLE_DRIVER,
    STYLE_LOOP,
    STYLE_SCALAR,
    HarnessSynthesizer,
    _strip_fence,
    build_synth_user_prompt,
    load_synth_prompt,
)


def _unit(tmp_path: Path, source: str):
    f = tmp_path / "m.py"
    f.write_text(source, encoding="utf-8")
    return preprocess_file(f)[0]


def _finding(category: str, expression: str) -> Finding:
    return Finding(
        id="f1",
        stage="llm_analysis",
        finding_type="suspected_bug",
        category=category,
        title="t",
        explanation="e",
        evidence=[],
        verifiable=True,
        confidence="medium",
        metadata={"expression": expression},
    )


def test_synth_prompt_file_loads():
    text = load_synth_prompt()
    assert "nondet_int()" in text
    assert "__ESBMC_assume" in text
    assert "module level" in text


def test_prompt_style_selects_distinct_files():
    scalar = load_synth_prompt(STYLE_SCALAR)
    driver = load_synth_prompt(STYLE_DRIVER)
    loop = load_synth_prompt(STYLE_LOOP)
    assert scalar != driver != loop != scalar
    assert "bounded loop" in loop
    assert "range(3)" in loop


def test_strip_fence_extracts_python_block():
    resp = "Here is the harness:\n```python\ndef f(x: int) -> int:\n    return x\nf(nondet_int())\n```\nDone."
    code = _strip_fence(resp)
    assert code.startswith("def f(x: int)")
    assert "Done." not in code
    assert code.endswith("\n")


def test_strip_fence_passthrough_when_no_fence():
    code = _strip_fence("def f(): pass")
    assert code == "def f(): pass\n"


def test_build_user_prompt_has_category_and_source(tmp_path: Path):
    unit = _unit(tmp_path, "def g(a: int, b: int) -> float:\n    return a / b\n")
    prompt = build_synth_user_prompt(unit, _finding("division_by_zero", "a / b"))
    assert "division_by_zero" in prompt
    assert "a / b" in prompt
    assert "def g(a: int, b: int)" in prompt


def test_repair_prompt_includes_validator_feedback_and_previous_harness(tmp_path: Path):
    unit = _unit(tmp_path, "def g(a: int, b: int) -> float:\n    return a / b\n")
    prompt = build_synth_user_prompt(
        unit,
        _finding("division_by_zero", "a / b"),
        repair_feedback="references unsupported dependency: np",
        previous_harness="value = np.array(data)",
    )
    assert "REPAIR REQUIRED" in prompt
    assert "unsupported dependency: np" in prompt
    assert "value = np.array(data)" in prompt


def test_synthesizer_requires_openai_backend():
    with pytest.raises(ValueError):
        HarnessSynthesizer(backend="anthropic", api_key="x")


def test_synthesizer_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        HarnessSynthesizer(api_key=None)


def test_ollama_synthesis_uses_chat_completions_shape(tmp_path: Path, monkeypatch):
    unit = _unit(tmp_path, "def g(a: int, b: int) -> int:\n    return a // b\n")
    response = {
        "model": "qwen2.5-coder:7b",
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        "choices": [{"message": {"content": "```python\ndef main():\n    assert False\nmain()\n```"}}],
    }
    synth = HarnessSynthesizer(
        backend="ollama", model="qwen2.5-coder:7b",
        base_url="http://localhost:11434/v1",
    )
    captured = {}

    def fake_post(payload):
        captured.update(payload)
        return response

    monkeypatch.setattr(synth, "_post_json", fake_post)
    result = synth.synthesize(unit, _finding("division_by_zero", "a // b"))
    assert captured["messages"][0]["role"] == "system"
    assert "input" not in captured
    assert "assert False" in result.harness
    assert result.telemetry["total_tokens"] == 30


def test_codex_backend_parses_json_events_and_output_file(tmp_path: Path, monkeypatch):
    """codex exec writes the harness to -o <file> and reports usage as a
    turn.completed JSONL event on stdout, not an HTTP response body - the
    parsing has to happen in _run_codex(), not _post_json().
    """
    unit = _unit(tmp_path, "def g(a: int, b: int) -> float:\n    return a / b\n")
    fake_harness = "def main() -> None:\n    assert False, 'x'\nmain()\n"

    import subprocess as subprocess_module

    from research_pipeline.scan import synth as synth_module

    captured_command: list[str] = []

    def fake_run(command, **kwargs):
        captured_command[:] = command
        out_index = command.index("-o") + 1
        Path(command[out_index]).write_text(f"```python\n{fake_harness}```", encoding="utf-8")
        stdout = "\n".join(
            [
                '{"type": "thread.started", "thread_id": "abc"}',
                '{"type": "item.completed", "item": {"type": "agent_message"}}',
                '{"type": "turn.completed", "usage": {"input_tokens": 17000, "output_tokens": 120}}',
            ]
        )
        return subprocess_module.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(synth_module.subprocess, "run", fake_run)

    synth = HarnessSynthesizer(backend="codex", model="gpt-5.1-codex")
    result = synth.synthesize(unit, _finding("division_by_zero", "a / b"))

    assert "--sandbox" in captured_command and "read-only" in captured_command
    assert "-m" in captured_command and "gpt-5.1-codex" in captured_command
    assert "assert False" in result.harness
    assert result.telemetry["prompt_tokens"] == 17000
    assert result.telemetry["completion_tokens"] == 120
    assert result.telemetry["status"] == "success"


def test_codex_backend_reports_missing_binary(tmp_path: Path, monkeypatch):
    unit = _unit(tmp_path, "def g(a: int, b: int) -> float:\n    return a / b\n")

    from research_pipeline.scan import synth as synth_module

    def fake_run(command, **kwargs):
        raise FileNotFoundError("codex")

    monkeypatch.setattr(synth_module.subprocess, "run", fake_run)

    synth = HarnessSynthesizer(backend="codex", model="")
    with pytest.raises(RuntimeError, match="não encontrado no PATH"):
        synth.synthesize(unit, _finding("division_by_zero", "a / b"))


def test_synthesize_with_mocked_api(tmp_path: Path, monkeypatch):
    unit = _unit(tmp_path, "def g(a: int, b: int) -> float:\n    return a / b\n")
    fake_harness = (
        "def g_core(a: int, b: int) -> float:\n"
        "    __ESBMC_assume(b >= 0)\n"
        "    assert b != 0\n"
        "    return a / b\n\n"
        "def main() -> None:\n    g_core(nondet_int(), nondet_int())\n\nmain()\n"
    )
    fake_response = {
        "model": "gpt-4o-mini",
        "usage": {"input_tokens": 300, "output_tokens": 80, "total_tokens": 380},
        "output": [{"content": [{"type": "output_text", "text": f"```python\n{fake_harness}```"}]}],
    }

    synth = HarnessSynthesizer(api_key="test-key", model="gpt-4o-mini")
    monkeypatch.setattr(synth, "_post_json", lambda payload: fake_response)

    result = synth.synthesize(unit, _finding("division_by_zero", "a / b"))
    assert "assert b != 0" in result.harness
    assert result.harness.rstrip().endswith("main()")
    assert result.model == "gpt-4o-mini"
    assert result.telemetry["total_tokens"] == 380
    assert result.telemetry["status"] == "success"
