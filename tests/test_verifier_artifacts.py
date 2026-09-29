"""Verifier artefacts must not count as confirmed bugs.

Outputs below are real ESBMC 8.5.0 blocks observed during the 2026-09-28
dataset audit (docs/projeto/auditoria_dataset_verificavel_v2.md).
"""
from __future__ import annotations


import pytest

from research_pipeline.models import ESBMCDirectResult, ESBMCResult
from research_pipeline.report import _category_from_esbmc_property
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


def _native(output: str) -> ESBMCResult:
    return ESBMCResult(finding_id="n", status="violation_found", command=["esbmc"], returncode=1,
                       summary="v", details=_extract_esbmc_details(output))


def _direct(status: str, output: str = "") -> ESBMCDirectResult:
    return ESBMCDirectResult(source_file="x.py", status=status, command=["esbmc"], returncode=1,
                             summary=status, details=_extract_esbmc_details(output))


