import pytest
import subprocess
from pathlib import Path

from research_pipeline.scan.capability import diagnose_esbmc
from research_pipeline.verification import esbmc_runner


def test_method_entry_error_is_diagnosed() -> None:
    diagnostic = diagnose_esbmc(
        "tool_error",
        "ERROR: --function: 'choose' is not a @staticmethod, and its receiver "
        "is a class instance the entry harness cannot build",
        "",
        "/tmp/esbmc.log",
    )
    assert diagnostic.kind == "method_entry"
    assert diagnostic.raw_log_path == "/tmp/esbmc.log"


def test_unsupported_builtin_is_diagnosed() -> None:
    diagnostic = diagnose_esbmc(
        "tool_error", "ERROR: Unsupported builtin call 'zip' at /tmp/probe.py:8", ""
    )
    assert diagnostic.kind == "builtin"
    assert diagnostic.source_line == 8


def test_generator_conversion_error_is_diagnosed() -> None:
    diagnostic = diagnose_esbmc(
        "tool_error", "ERROR: Unsupported expression GeneratorExp at /tmp/probe.py:11", ""
    )
    assert diagnostic.kind == "generator"
    assert diagnostic.source_line == 11


def test_timeout_remains_timeout() -> None:
    diagnostic = diagnose_esbmc("inconclusive", "", "", summary="ESBMC timeout")
    assert diagnostic.kind == "timeout"


def test_passed_typeerror_does_not_mask_failed_division() -> None:
    output = (
        "PASSED [list_size.assertion.1] TypeError: object of this type has no len()\n"
        "Violated property:\n  file /tmp/probe.py line 6 column 11 function ratio\n"
        "  uncaught exception: ZeroDivisionError\nVERIFICATION FAILED\n"
    )
    diagnostic = diagnose_esbmc("violation_found", output, "")
    assert diagnostic.kind == "unknown"
    assert "TypeError" not in diagnostic.message


def test_unknown_error_keeps_raw_log() -> None:
    diagnostic = diagnose_esbmc(
        "tool_error", "ERROR: Internal solver failure", "stack trace", "/tmp/raw.log"
    )
    assert diagnostic.kind == "unknown"
    assert diagnostic.raw_log_path == "/tmp/raw.log"
    assert "Internal solver failure" in diagnostic.message


def test_direct_runner_persists_partial_output_on_timeout(tmp_path: Path, monkeypatch) -> None:
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"Converting", stderr=b"partial error")

    monkeypatch.setattr(esbmc_runner.subprocess, "run", timeout)
    source = tmp_path / "probe.py"
    source.write_text("pass\n", encoding="utf-8")
    result = esbmc_runner.run_esbmc_direct(
        source, esbmc_command=["/bin/true"], output_dir=tmp_path / "logs"
    )
    assert result.status == "timeout"
    assert "Converting" in result.stdout
    assert "partial error" in result.stderr
    assert "partial error" in Path(result.raw_log_path).read_text(encoding="utf-8")


def test_function_runner_persists_partial_output_on_timeout(tmp_path: Path, monkeypatch) -> None:
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="Converting", stderr="partial error")

    monkeypatch.setattr(esbmc_runner.subprocess, "run", timeout)
    source = tmp_path / "probe.py"
    source.write_text("def f(x: int):\n    return x\n", encoding="utf-8")
    result = esbmc_runner.run_esbmc_on_function(
        source, "f", "probe", "division_by_zero", esbmc_command=["/bin/true"],
        output_dir=tmp_path / "logs",
    )
    assert result.status == "inconclusive"
    assert "Converting" in result.stdout
    assert Path(result.raw_log_path).exists()
    assert "partial error" in Path(result.raw_log_path).read_text(encoding="utf-8")


def test_diagnosis_reads_raw_log_when_output_was_summarized(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "Converting\nERROR: --function: 'per' is not a @staticmethod, and its receiver is a "
        "class instance the entry harness cannot build\n",
        encoding="utf-8",
    )
    diagnostic = diagnose_esbmc("tool_error", "ESBMC version 8.5.0\n", "ESBMC retornou erro.", str(log))
    assert diagnostic.kind == "method_entry"
    assert "staticmethod" in diagnostic.message


@pytest.mark.parametrize("error,kind", [
    ('ERROR: Object "driver" not found.', "dependency"),
    ('ERROR: Function "_expand_iterable" not found (x.py line 2)', "dependency"),
    ("ERROR: unsupported: non-constant argument in str % formatting", "builtin"),
])
def test_converter_errors_seen_on_eligible_dataset_are_named(error, kind):
    assert diagnose_esbmc("tool_error", error, "").kind == kind


@pytest.mark.parametrize("message,hint", [
    ("ERROR: Return type undefined", "return annotation"),
    ('ERROR: Object "binascii" not found.', "not modeled"),
    ("ERROR: TypeError at x.py 9: list indices must be integers or slices, not str", "element type"),
    ("ERROR: --function: 'f' is not a @staticmethod, and its receiver", "obj = "),
])
def test_fix_hints_for_known_esbmc_errors(message, hint):
    from research_pipeline.scan.capability import fix_hint
    assert hint in fix_hint(diagnose_esbmc("tool_error", message, ""))
