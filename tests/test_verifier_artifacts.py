"""Verifier artefacts must not count as confirmed bugs.

Outputs below are real ESBMC 8.5.0 blocks observed during the 2026-09-28
dataset audit (docs/projeto/auditoria_dataset_verificavel_v2.md).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult, ESBMCResult
from research_pipeline.report import _category_from_esbmc_property
from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan.pipeline import (
    CONFIRMED_DRIVER,
    CONFIRMED_NATIVE,
    ScanCandidate,
    run_pipeline_scan,
)
from research_pipeline.scan.synth import SynthResult
from research_pipeline.verification.esbmc_runner import (
    _extract_esbmc_details,
    only_verifier_artifacts,
)

# `"php -s" in script` on a symbolic str: no Python exception is possible.
STRSTR_INVALID_POINTER = """Violated property:
  file /esbmc-vfs/libc/library/string.c line 235 column 3 function strstr
  dereference failure: invalid pointer
  CWE: CWE-416, CWE-822, CWE-824, CWE-908

VERIFICATION FAILED
"""
UNWINDING_IN_STRING_MODEL = """Violated property:
  file /home/runner/work/esbmc/esbmc/src/c2goto/library/python/string.c line 509 column 3 function __python_str_lower
  unwinding assertion loop 68

VERIFICATION FAILED
"""
NATIVE_INDEX_ERROR = """Violated property:
  uncaught exception: IndexError
  !(c:@__ESBMC_exc_thrown && c:@__ESBMC_exc_typeid == 14)

VERIFICATION FAILED
"""
LIST_POP_INDEX_ERROR = """Violated property:
  file /home/runner/work/esbmc/esbmc/src/c2goto/library/python/list.c line 845 column 3 function __ESBMC_list_pop
  IndexError: pop index out of range
  actual_index < l->size

VERIFICATION FAILED
"""
INT_INVALID_LITERAL = """Violated property:
  file /home/runner/work/esbmc/esbmc/src/c2goto/library/python/string.c line 1217 column 7 function __python_int
  invalid literal for int() - invalid character
  0

VERIFICATION FAILED
"""
USER_NULL_DEREFERENCE = """Violated property:
  file /tmp/case/nm_real_12.py line 15 column 8 function unlink
  dereference failure: NULL pointer
  CWE: CWE-476

VERIFICATION FAILED
"""


def test_details_record_the_file_of_each_violated_property() -> None:
    details = _extract_esbmc_details(STRSTR_INVALID_POINTER + NATIVE_INDEX_ERROR)
    assert details["violated_files"] == ["/esbmc-vfs/libc/library/string.c", ""]


@pytest.mark.parametrize(
    ("output", "artifact"),
    [
        (STRSTR_INVALID_POINTER, True),
        (UNWINDING_IN_STRING_MODEL, True),
        (NATIVE_INDEX_ERROR, False),
        (LIST_POP_INDEX_ERROR, False),
        (INT_INVALID_LITERAL, False),
        (USER_NULL_DEREFERENCE, False),
        (STRSTR_INVALID_POINTER + NATIVE_INDEX_ERROR, False),
    ],
)
def test_only_verifier_artifacts(output: str, artifact: bool) -> None:
    assert only_verifier_artifacts(_extract_esbmc_details(output)) is artifact


def test_details_without_parsed_properties_are_not_called_artifacts() -> None:
    assert only_verifier_artifacts({}) is False


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Missing return statement detected in function 'multi_get'", "none_misuse"),
        ("dereference failure: invalid pointer", "unknown_esbmc_violation"),
        ("dereference failure: NULL pointer", "none_misuse"),
    ],
)
def test_property_to_category_mapping(text: str, category: str) -> None:
    assert _category_from_esbmc_property(text) == category


class _SpySynthesizer:
    model = "spy"

    def __init__(self) -> None:
        self.called = False

    def synthesize(self, *args, **kwargs) -> SynthResult:
        self.called = True
        return SynthResult("", "", self.model, {})


def _candidate(tmp_path: Path, source: str, function: str, category: str) -> ScanCandidate:
    path = tmp_path / "mod.py"
    path.write_text(source, encoding="utf-8")
    return ScanCandidate(file=str(path), function=function, category=category)


def _native(output: str) -> ESBMCResult:
    return ESBMCResult(finding_id="n", status="violation_found", command=["esbmc"], returncode=1,
                       summary="v", details=_extract_esbmc_details(output))


def _direct(status: str, output: str = "") -> ESBMCDirectResult:
    return ESBMCDirectResult(source_file="x.py", status=status, command=["esbmc"], returncode=1,
                             summary=status, details=_extract_esbmc_details(output))


def test_native_artifact_is_not_a_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", lambda *a, **k: _native(STRSTR_INVALID_POINTER))
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", lambda *a, **k: _direct("tool_error"))
    spy = _SpySynthesizer()
    source = 'def is_php_server(script):\n    return "php -s" in script\n'
    result = run_pipeline_scan(
        [_candidate(tmp_path, source, "is_php_server", "assertion_violation")],
        synthesizer=spy, output_dir=tmp_path / "out", synth_retries=0, use_driver=False,
    )[0]
    assert result.classification != CONFIRMED_NATIVE
    assert spy.called


def test_native_python_exception_still_confirms(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", lambda *a, **k: _native(NATIVE_INDEX_ERROR))
    spy = _SpySynthesizer()
    result = run_pipeline_scan(
        [_candidate(tmp_path, "def first(items):\n    return items[0]\n", "first", "out_of_bounds")],
        synthesizer=spy, output_dir=tmp_path / "out",
    )[0]
    assert result.classification == CONFIRMED_NATIVE
    assert not spy.called


def test_real_body_artifact_is_not_a_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        scan_pipeline, "run_esbmc_on_function",
        lambda *a, **k: ESBMCResult(finding_id="n", status="skipped", command=["esbmc"], returncode=0, summary="s"),
    )
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", lambda *a, **k: _direct("violation_found", UNWINDING_IN_STRING_MODEL))
    spy = _SpySynthesizer()
    source = "def at(values: list[int], index: int) -> int:\n    return values[index]\n"
    result = run_pipeline_scan(
        [_candidate(tmp_path, source, "at", "out_of_bounds")],
        synthesizer=spy, output_dir=tmp_path / "out", synth_retries=0, use_driver=False,
    )[0]
    assert not (result.classification == CONFIRMED_DRIVER and result.harness_tier == "real_body")
    assert spy.called
