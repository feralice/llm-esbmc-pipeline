import importlib.util
import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("pdp", Path(__file__).parents[1] / "scripts/print_detection_prompt.py")
pdp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdp)


@pytest.fixture
def no_llm(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("print_detection_prompt must not call an LLM")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_prints_system_and_user_prompts(tmp_path: Path, capsys, no_llm) -> None:
    source = tmp_path / "m.py"
    source.write_text("def head(xs):\n    return xs[0]\n", encoding="utf-8")
    assert pdp.main(["--input", str(source), "--v2-variants", "A1,A2,A14"]) == 0
    captured = capsys.readouterr()
    assert "## EVIDÊNCIA CITADA" in captured.out and "return xs[0]" in captured.out
    assert "=== m.py::head ===" in captured.out and "tokens" in captured.err


def test_writes_one_file_per_function_with_a13(tmp_path: Path, no_llm) -> None:
    sources = tmp_path / "funcao_com_bug"
    sources.mkdir()
    (sources / "x_1.py").write_text("def pick(values, i):\n    return values[i + 1]\n", encoding="utf-8")
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [
        {"id": "x_1", "file": "x_1.py", "function": "pick", "expression": "values[i + 1]",
         "failure_kind": "excecao_local", "provenance": {"project": "outro"}}]}), encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text("def head(xs, k):\n    return xs[k + 1]\n", encoding="utf-8")
    out = tmp_path / "out"
    assert pdp.main(["--input", str(target), "--v2-variants", "A13", "--example-pool", str(ground_truth),
                     "--out", str(out)]) == 0
    assert "## EXEMPLOS DE BUGS REAIS" in (out / "system.txt").read_text(encoding="utf-8")
    assert "<UNTRUSTED_EXEMPLOS>" in (out / "m.py__head.txt").read_text(encoding="utf-8")


def test_no_matching_function_returns_one(tmp_path: Path, no_llm) -> None:
    source = tmp_path / "m.py"
    source.write_text("def head(xs):\n    return xs[0]\n", encoding="utf-8")
    assert pdp.main(["--input", str(source), "--function", "nada"]) == 1
