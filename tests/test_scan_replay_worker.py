"""Use only literal trusted fixtures here; production replay requires a container."""

import json
import subprocess
import sys

import pytest

from research_pipeline.scan import replay_worker


def _run(tmp_path, source, function="f", args=(0,)):
    candidate = tmp_path / "candidate.py"
    result = tmp_path / "result.json"
    candidate.write_text(source, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-I", replay_worker.__file__, str(candidate), function,
         json.dumps(args), "{}", str(result)],
        check=True, capture_output=True, text=True, timeout=5,
    )
    return json.loads(result.read_text(encoding="utf-8"))


def test_worker_records_exact_target_exception_location(tmp_path):
    result = _run(tmp_path, "def f(x):\n    return 10 // x\n")
    assert result["kind"] == "exception"
    assert result["phase"] == "call"
    assert result["exception_location"] == {
        "file": "<candidate>", "function": "f", "line": 2, "column": 11,
    }


@pytest.mark.parametrize("source,function,phase", [
    ("value = 1 // 0\ndef f(x): return x\n", "f", "load"),
    ("class C:\n    def __init__(self):\n        value = 1 // 0\n    def f(self, x): return x\n", "C.f", "resolve"),
    ("def f(x): return x\n", "missing", "resolve"),
])
def test_worker_setup_error_is_unavailable(tmp_path, source, function, phase):
    result = _run(tmp_path, source, function)
    assert result["kind"] == "unavailable"
    assert result["phase"] == phase


def test_worker_argument_binding_error_is_unavailable(tmp_path):
    result = _run(tmp_path, "def f(): return 1\n")
    assert result["kind"] == "unavailable"
    assert result["phase"] == "resolve"


@pytest.mark.parametrize("body", ["return 1", "return 1.0", "return True"])
def test_worker_return_value_keeps_its_type(tmp_path, body):
    results = {
        variant: _run(tmp_path, f"def f(x):\n    {variant}\n")
        for variant in ("return 1", "return 1.0", "return True")
    }
    others = [result for variant, result in results.items() if variant != body]
    assert all(results[body] != other for other in others)


def test_worker_tuple_and_list_returns_differ(tmp_path):
    as_tuple = _run(tmp_path, "def f(x):\n    return (x,)\n")
    as_list = _run(tmp_path, "def f(x):\n    return [x]\n")
    assert as_tuple != as_list


def test_worker_records_argument_mutation(tmp_path):
    pure = _run(tmp_path, "def f(items):\n    return len(items)\n", args=([1, 2],))
    mutating = _run(tmp_path, "def f(items):\n    items.pop()\n    return 2\n", args=([1, 2],))
    assert pure["value"] == mutating["value"]
    assert pure["effects"]["arguments"] != mutating["effects"]["arguments"]
