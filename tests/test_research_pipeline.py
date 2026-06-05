from __future__ import annotations

import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_needs_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY não configurada — teste requer API real",
)

from research_pipeline.verification.esbmc_runner import (
    _FLOW_B_CATEGORY_FLAGS,
    _classify_esbmc_result,
    _classify_esbmc_direct_result,
    _extract_generated_vcc_count,
)
from research_pipeline import evaluator
from research_pipeline.ast_utils import expression_exists_in_executable_ast
from research_pipeline.evaluator import evaluate_file, load_ground_truth_cases
from research_pipeline.report import consolidate_result
from research_pipeline.pipeline import run_pipeline
from research_pipeline.preprocess import preprocess_file
from research_pipeline.llm.findings import finding_from_dict, normalize_findings
from research_pipeline.llm.schema import FINDINGS_JSON_SCHEMA
from research_pipeline.llm.backends import openai as openai_backend
from research_pipeline.llm.backends.openai import OpenAIResponsesAnalyzer
from research_pipeline.models import ESBMCDirectResult, Finding


@_needs_openai
def test_pipeline_generates_mixed_results(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "\n".join(
            [
                "def avg(values, n):",
                "    total = 0",
                "    for i in range(n):",
                "        total += values[i]",
                "    return total / n",
                "",
                "def long_method(a, b, c, d, e, f):",
                "    x = a + b",
                "    if x > 0:",
                "        x += c",
                "    if x > 1:",
                "        x += d",
                "    if x > 2:",
                "        x += e",
                "    if x > 3:",
                "        x += f",
                "    return x",
            ]
        ),
        encoding="utf-8",
    )

    results = run_pipeline(sample, output_dir=tmp_path / "artifacts")

    classifications = {result.final_classification for result in results}
    categories = {result.finding.category for result in results}

    assert (
        "llm_confirmed_by_esbmc" in classifications
        or "not_confirmed_within_bound" in classifications
        or "esbmc_inconclusive" in classifications
        or "skipped_not_verifiable" in classifications
    )
    assert "heuristic_smell_only" in classifications
    assert "division_by_zero" in categories
    assert "out_of_bounds" in categories


@_needs_openai
def test_preprocess_ignores_test_functions_and_annotations(tmp_path: Path) -> None:
    sample = tmp_path / "sample_annotations.py"
    sample.write_text(
        "\n".join(
            [
                "from typing import List",
                "",
                "def target(xs: List[int], i: int):",
                "    return xs[i]",
                "",
                "def test_target():",
                "    data: List[int] = [1, 2, 3]",
                "    return data[0]",
            ]
        ),
        encoding="utf-8",
    )

    results = run_pipeline(sample, output_dir=tmp_path / "artifacts")

    unit_names = {result.unit_name for result in results}
    expressions = {result.finding.metadata.get("expression") for result in results if result.finding.metadata}

    assert "test_target" not in unit_names
    assert "List[int]" not in expressions


def test_flow_b_scopes_flags_by_finding_category() -> None:
    assert _FLOW_B_CATEGORY_FLAGS["division_by_zero"] == ["--no-bounds-check"]
    assert _FLOW_B_CATEGORY_FLAGS["out_of_bounds"] == ["--no-div-by-zero-check", "--assign-param-nondet"]
    assert _FLOW_B_CATEGORY_FLAGS["assertion_violation"] == []


def test_openai_timeout_reports_clear_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = OpenAIResponsesAnalyzer(api_key="test-key", model="test-model")

    def fake_urlopen(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(openai_backend.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(openai_backend.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="Timeout ao chamar OpenAI"):
        analyzer._post_json({"input": []})


# ---------------------------------------------------------------------------
# Testes unitários do classificador ESBMC — sem chamada de API
# ---------------------------------------------------------------------------

def test_classify_verification_failed_is_violation_found() -> None:
    """VERIFICATION FAILED no output → violation_found."""
    output = (
        "Parsing /tmp/test.py\n"
        "Violated property:\n"
        "  file /tmp/test.py line 3\n"
        "  assertion violated\n"
        "VERIFICATION FAILED\n"
    )
    assert _classify_esbmc_result(output, 1) == "violation_found"
    assert _classify_esbmc_direct_result(output, 1) == "violation_found"


def test_classify_zero_vcc_is_no_vcc_generated() -> None:
    """VERIFICATION SUCCESSFUL com 0 VCCs → status deve ser no_vcc_generated (após override)."""
    output = (
        "Parsing /tmp/test.py\n"
        "Generated 0 VCC(s), 0 remaining after simplification (0 assignments)\n"
        "VERIFICATION SUCCESSFUL\n"
    )
    # _classify_esbmc_result retorna no_violation_found; o override para no_vcc_generated
    # acontece em run_esbmc_direct após a chamada. Aqui validamos a função base e o extrator.
    assert _classify_esbmc_result(output, 0) == "no_violation_found"
    assert _extract_generated_vcc_count(output) == 0


def test_classify_filename_with_violation_not_false_positive() -> None:
    """Arquivo com 'assertion_violation' no nome não pode gerar violation_found se ESBMC diz SUCCESSFUL."""
    output = (
        "Parsing /path/to/black_23_assertion_violation.py\n"
        "Generated 0 VCC(s), 0 remaining after simplification (0 assignments)\n"
        "VERIFICATION SUCCESSFUL\n"
    )
    assert _classify_esbmc_result(output, 0) == "no_violation_found", (
        "O nome do arquivo contém 'violation' mas o ESBMC retornou SUCCESSFUL — "
        "não deve ser classificado como violation_found."
    )
    assert _classify_esbmc_direct_result(output, 0) == "no_violation_found"


def test_classify_pandas_assertion_violation_filename() -> None:
    """Variante com pandas_42_assertion_violation.py."""
    output = (
        "Parsing /home/user/pandas_42_assertion_violation.py\n"
        "Generated 0 VCC(s), 0 remaining after simplification (0 assignments)\n"
        "VERIFICATION SUCCESSFUL\n"
    )
    assert _classify_esbmc_result(output, 0) == "no_violation_found"


def test_classify_verification_successful_with_vccs() -> None:
    """VERIFICATION SUCCESSFUL com VCCs geradas → no_violation_found."""
    output = (
        "Parsing /tmp/test.py\n"
        "Generated 3 VCC(s), 1 remaining after simplification\n"
        "VERIFICATION SUCCESSFUL\n"
    )
    assert _classify_esbmc_result(output, 0) == "no_violation_found"
    assert _extract_generated_vcc_count(output) == 3


def test_classify_tool_error() -> None:
    """ERROR: sem 'Cannot open file' e sem 'not supported' → tool_error."""
    output = "Parsing /tmp/test.py\nERROR: internal ESBMC error\n"
    assert _classify_esbmc_direct_result(output, 1) == "tool_error"


def test_classify_unsupported_case() -> None:
    """Cannot open file → unsupported_case."""
    output = "Parsing /tmp/test.py\nERROR: Cannot open file 'numpy'\n"
    assert _classify_esbmc_direct_result(output, 1) == "unsupported_case"


def test_pop_without_esbmc_result_is_skipped_not_confirmed() -> None:
    finding = _make_finding("out_of_bounds", "items.pop(index)")
    result = consolidate_result(
        unit_name="remove",
        source_file="sample.py",
        finding=finding,
        esbmc_result=None,
        esbmc_direct_result=None,
    )

    assert result.final_classification == "skipped_not_verifiable"


class _FakeAnalyzer:
    def __init__(self, findings_by_function: dict[str, list[Finding]]):
        self.findings_by_function = findings_by_function

    def analyze(self, unit):
        return list(self.findings_by_function.get(unit.name, []))


def test_clean_case_without_findings_does_not_generate_fn(tmp_path: Path) -> None:
    sample = tmp_path / "clean.py"
    sample.write_text("def safe_add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "safe_add", "category": "clean", "verifiable": False}],
        analyzer=_FakeAnalyzer({}),
    )

    assert counts.bug_fn == 0
    assert counts.smell_fn == 0
    assert counts.bug_fp == 0
    assert counts.smell_fp == 0


def test_clean_case_with_findings_counts_false_positive(tmp_path: Path) -> None:
    sample = tmp_path / "clean.py"
    sample.write_text("def safe_add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    smell = _make_finding("long_method", "", verifiable=False)
    smell.finding_type = "smell_heuristic"
    bug = _make_finding("division_by_zero", "a / b")
    bug.finding_type = "llm_false_positive"
    bug.verifiable = False

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "safe_add", "category": "clean", "verifiable": False}],
        analyzer=_FakeAnalyzer({"safe_add": [smell, bug]}),
    )

    assert counts.bug_fn == 0
    assert counts.smell_fn == 0
    assert counts.bug_fp == 1
    assert counts.smell_fp == 1


def test_hallucinated_bug_on_buggy_file_counts_as_llm_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = tmp_path / "buggy.py"
    sample.write_text("def divide(a: int, b: int) -> int:\n    return a // b\n", encoding="utf-8")

    real_bug = _make_finding("division_by_zero", "a // b")
    hallucinated_bug = _make_finding("out_of_bounds", "items[i]")
    hallucinated_bug.finding_type = "llm_false_positive"
    hallucinated_bug.verifiable = False

    monkeypatch.setattr(evaluator, "run_esbmc_on_function", lambda **kwargs: SimpleNamespace(status="no_violation_found"))
    monkeypatch.setattr(
        evaluator,
        "run_esbmc_function_baseline",
        lambda **kwargs: ESBMCDirectResult(
            source_file=str(sample),
            status="no_violation_found",
            command=[],
            returncode=0,
            summary="no violation",
            details={"functions": []},
        ),
    )

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "divide", "category": "division_by_zero", "verifiable": True}],
        analyzer=_FakeAnalyzer({"divide": [real_bug, hallucinated_bug]}),
    )

    assert counts.bug_tp == 1
    assert counts.bug_fp == 1
    assert counts.hallucination_count == 1
    assert counts.per_category["out_of_bounds"]["fp"] == 1
    # hallucination_rate denominator = bug_tp + bug_fp (hallucinations already in bug_fp)
    from research_pipeline.evaluator import hallucination_rate
    rate = hallucination_rate(counts)
    assert abs(rate - 0.5) < 1e-9, f"expected 0.5, got {rate}"


def test_flow_a_bug_missed_by_llm_is_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = tmp_path / "oob.py"
    sample.write_text("def read(values, i):\n    return values[i]\n", encoding="utf-8")

    def fake_flow_a(**kwargs):
        return ESBMCDirectResult(
            source_file=str(sample),
            status="violation_found",
            command=[],
            returncode=1,
            summary="violation",
            details={
                "functions": [
                    {
                        "name": "read",
                        "status": "violation_found",
                        "property_kind": "dereference failure",
                        "summary": "array bounds violated",
                    }
                ]
            },
        )

    monkeypatch.setattr(evaluator, "run_esbmc_function_baseline", fake_flow_a)

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "read", "category": "out_of_bounds", "verifiable": True}],
        analyzer=_FakeAnalyzer({}),
    )

    assert counts.esbmc_native_bug == 1
    assert counts.llm_missed_esbmc_bug == 1


def test_flow_a_bug_reported_by_llm_is_not_counted_as_missed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = tmp_path / "oob.py"
    sample.write_text("def read(values, i):\n    return values[i]\n", encoding="utf-8")

    def fake_flow_a(**kwargs):
        return ESBMCDirectResult(
            source_file=str(sample),
            status="violation_found",
            command=[],
            returncode=1,
            summary="violation",
            details={
                "functions": [
                    {
                        "name": "read",
                        "status": "violation_found",
                        "property_kind": "dereference failure",
                        "summary": "array bounds violated",
                    }
                ]
            },
        )

    monkeypatch.setattr(evaluator, "run_esbmc_on_function", lambda **kwargs: SimpleNamespace(status="skipped", details={}))
    monkeypatch.setattr(evaluator, "run_esbmc_function_baseline", fake_flow_a)

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "read", "category": "out_of_bounds", "verifiable": True}],
        analyzer=_FakeAnalyzer({"read": [_make_finding("out_of_bounds", "values[i]")]}),
    )

    assert counts.esbmc_native_bug == 1
    assert counts.llm_missed_esbmc_bug == 0


def test_preprocess_invalid_python_returns_no_units(tmp_path: Path) -> None:
    sample = tmp_path / "broken.py"
    sample.write_text("def broken(:\n    pass\n", encoding="utf-8")

    with pytest.warns(RuntimeWarning, match="Skipping invalid Python file"):
        assert preprocess_file(sample) == []


def test_ground_truth_loader_recurses_all_v1_subfolders() -> None:
    cases = load_ground_truth_cases(REPO_ROOT / "dataset" / "labeled" / "ground_truths")

    assert len(cases) == 70
    assert any(path.name == "clean_01.py" for path, _ in cases)
    assert all(path.exists() for path, _ in cases)


def test_frontend_benchmark_schema_uses_current_keys_with_legacy_fallback() -> None:
    html = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "metricBlock(data, 'bugs_llm_only', 'bugs')" in html
    assert "metricBlock(data, 'bugs_hybrid_pipeline', 'bugs')" in html


def _make_finding(category: str, expression: str, verifiable: bool = True) -> Finding:
    return Finding(
        id=f"test_{category}_1",
        stage="llm_analysis",
        finding_type="suspected_bug" if verifiable else "smell_heuristic",
        category=category,
        title="test",
        explanation="test",
        evidence=[],
        verifiable=verifiable,
        confidence="high",
        metadata={
            "expression": expression,
            "line": "2",
            "relative_line": "1",
            "has_guard": "false",
            "expected_exception": "",
        },
    )


# ---------------------------------------------------------------------------
# AST existence check — imune a comentários e strings literais
# ---------------------------------------------------------------------------

def test_expression_exists_in_executable_ast_subscript(tmp_path: Path) -> None:
    source = "def f(lst, i):\n    return lst[i]\n"
    assert expression_exists_in_executable_ast("lst[i]", source) is True


def test_expression_exists_in_executable_ast_pop(tmp_path: Path) -> None:
    source = "def f(lst, i):\n    lst.pop(i)\n"
    assert expression_exists_in_executable_ast("lst.pop(i)", source) is True


def test_expression_not_in_comment(tmp_path: Path) -> None:
    source = "def f(lst, i):\n    # lst[i] would be risky\n    return lst\n"
    assert expression_exists_in_executable_ast("lst[i]", source) is False


def test_expression_not_in_string_literal(tmp_path: Path) -> None:
    source = 'def f(lst, i):\n    msg = "lst[i]"\n    return lst\n'
    assert expression_exists_in_executable_ast("lst[i]", source) is False


# ---------------------------------------------------------------------------
# normalize_findings — pop não deve ser llm_false_positive
# ---------------------------------------------------------------------------

def test_normalize_pop_not_false_positive(tmp_path: Path) -> None:
    sample = tmp_path / "f.py"
    sample.write_text(
        "def remove(lst: list, i: int) -> list:\n    lst.pop(i)\n    return lst\n"
    )
    units = preprocess_file(sample)
    unit = units[0]

    finding = _make_finding("out_of_bounds", "lst.pop(i)")
    normalized = normalize_findings(unit, [finding])

    assert normalized[0].finding_type != "llm_false_positive", (
        ".pop(i) existe no código — não deve ser classificado como alucinação da LLM"
    )
    assert normalized[0].finding_type == "suspected_bug"
    assert normalized[0].metadata.get("ast_unrecognized") == "true"


def test_normalize_true_hallucination_is_false_positive(tmp_path: Path) -> None:
    sample = tmp_path / "f.py"
    sample.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    units = preprocess_file(sample)
    unit = units[0]

    finding = _make_finding("division_by_zero", "a / b")  # divisão não existe
    normalized = normalize_findings(unit, [finding])

    assert normalized[0].finding_type == "llm_false_positive", (
        "Divisão não existe no código — deve ser llm_false_positive"
    )


def test_assertion_violation_wrong_expression_is_false_positive(tmp_path: Path) -> None:
    sample = tmp_path / "assertion.py"
    sample.write_text(
        "def require_amount(amount: int) -> int:\n"
        "    assert amount > 0\n"
        "    return amount\n",
        encoding="utf-8",
    )
    unit = preprocess_file(sample)[0]

    finding = _make_finding("assertion_violation", "assert flag > 0")
    normalized = normalize_findings(unit, [finding])

    assert normalized[0].finding_type == "llm_false_positive"
    assert normalized[0].verifiable is False


def test_finding_from_dict_preserves_line_metadata_as_int() -> None:
    finding = finding_from_dict(
        {
            "id": "f1",
            "finding_type": "suspected_bug",
            "category": "division_by_zero",
            "metadata": {
                "expression": "x / y",
                "line": 12,
                "relative_line": "3",
            },
        }
    )

    assert finding.metadata["line"] == 12
    assert finding.metadata["relative_line"] == 3


def test_llm_schema_exposes_only_llm_finding_types() -> None:
    finding_schema = (
        FINDINGS_JSON_SCHEMA["schema"]["properties"]["findings"]["items"]["properties"]
    )

    assert finding_schema["finding_type"]["enum"] == [
        "suspected_bug",
        "smell_heuristic",
    ]
    assert finding_schema["metadata"]["properties"]["line"]["type"] == "integer"
    assert finding_schema["metadata"]["properties"]["relative_line"]["type"] == "integer"


def test_constant_nonzero_denominator_is_false_positive(tmp_path: Path) -> None:
    sample = tmp_path / "const_div.py"
    sample.write_text(
        "def compute(x: int, tax_rate: int) -> int:\n"
        "    return x * tax_rate // 100\n",
        encoding="utf-8",
    )
    unit = preprocess_file(sample)[0]
    finding = _make_finding("division_by_zero", "x * tax_rate // 100")
    normalized = normalize_findings(unit, [finding])

    assert normalized[0].finding_type == "llm_false_positive"
    assert normalized[0].verifiable is False


def test_free_parameter_denominator_is_still_suspected_bug(tmp_path: Path) -> None:
    sample = tmp_path / "free_div.py"
    sample.write_text(
        "def divide(x: int, n: int) -> int:\n"
        "    return x // n\n",
        encoding="utf-8",
    )
    unit = preprocess_file(sample)[0]
    finding = _make_finding("division_by_zero", "x // n")
    normalized = normalize_findings(unit, [finding])

    assert normalized[0].finding_type == "suspected_bug"
    assert normalized[0].verifiable is True


def test_skipped_not_verifiable_does_not_count_smells(tmp_path: Path) -> None:
    sample = tmp_path / "smelly.py"
    sample.write_text(
        "def long_fn(a: int, b: int, c: int, d: int, e: int) -> int:\n"
        "    x = a + b\n"
        "    y = c + d\n"
        "    return x + y + e\n",
        encoding="utf-8",
    )
    smell = _make_finding("many_parameters", "", verifiable=False)
    smell.finding_type = "smell_heuristic"

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "long_fn", "category": "many_parameters", "verifiable": False}],
        analyzer=_FakeAnalyzer({"long_fn": [smell]}),
    )

    assert counts.skipped_not_verifiable == 0
    assert counts.smell_tp == 1


def test_esbmc_native_bug_is_zero_when_no_violation_found(tmp_path: Path) -> None:
    sample = tmp_path / "clean.py"
    sample.write_text("def safe(a: int) -> int:\n    return a\n", encoding="utf-8")

    counts = evaluate_file(
        file_path=sample,
        expected=[{"function": "safe", "category": "clean", "verifiable": False}],
        analyzer=_FakeAnalyzer({}),
    )

    assert counts.esbmc_native_bug == 0
