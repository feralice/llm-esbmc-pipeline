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
    _build_esbmc_command,
    _classify_esbmc_result,
    _classify_esbmc_direct_result,
    _extract_generated_vcc_count,
)
from research_pipeline.verification.formalizer import formalize_finding
from research_pipeline.verification.instrumenter import instrument_unit
from research_pipeline.evaluator import evaluate_file, load_ground_truth_cases
from research_pipeline.report import consolidate_result
from research_pipeline.pipeline import run_pipeline
from research_pipeline.experimental.runtime_harness_validator import (
    HARNESS_NOT_REPRODUCED,
    HARNESS_REPRODUCED,
    HARNESS_UNSAFE,
    HARNESS_WRONG_EXCEPTION,
    expression_exists_in_executable_ast,
    validate_harness,
)
from research_pipeline.preprocess import preprocess_file
from research_pipeline.llm.findings import normalize_findings
from research_pipeline.models import Finding


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


def test_esbmc_command_scopes_flags_by_finding_category() -> None:
    div_command = _build_esbmc_command(None, ["--no-bounds-check"])
    oob_command = _build_esbmc_command(None, ["--no-div-by-zero-check"])

    assert "--no-bounds-check" in div_command
    assert "--no-div-by-zero-check" not in div_command

    assert "--no-div-by-zero-check" in oob_command
    assert "--no-bounds-check" not in oob_command


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


def test_formalizer_attaches_asserts_and_esbmc_flags() -> None:
    unit = SimpleNamespace(
        operations=[
            SimpleNamespace(kind="subscript", expression="values[idx]", line=5, relative_line=2),
            SimpleNamespace(kind="division", expression="item // denom", line=6, relative_line=3),
        ]
    )

    div_finding = SimpleNamespace(
        id="f1",
        category="division_by_zero",
        verifiable=True,
        metadata={"expression": "item // denom", "line": "6", "relative_line": "3"},
    )
    oob_finding = SimpleNamespace(
        id="f2",
        category="out_of_bounds",
        verifiable=True,
        metadata={"expression": "values[idx]", "line": "5", "relative_line": "2"},
    )

    div_property = formalize_finding(unit, div_finding)
    oob_property = formalize_finding(unit, oob_finding)

    assert div_property is not None
    assert div_property.assertion == "(denom) != 0"
    assert div_property.esbmc_flags == ["--no-bounds-check"]
    assert div_property.assumptions == ["(0 <= (idx)) and ((idx) < len(values))"]

    assert oob_property is not None
    assert oob_property.assertion == "(0 <= (idx)) and ((idx) < len(values))"
    assert oob_property.esbmc_flags == ["--no-div-by-zero-check"]
    assert oob_property.assumptions == []


def test_formalizer_unsupported_patterns_do_not_generate_false_property() -> None:
    unit = SimpleNamespace(operations=[])

    unsupported = [
        _make_finding("out_of_bounds", "items.pop(index)"),
        _make_finding("out_of_bounds", "re.findall('x', text)[0]"),
        _make_finding("out_of_bounds", "items[1:3]"),
        _make_finding("assertion_violation", "raise AssertionError('fail')"),
        _make_finding("division_by_zero", "divide(a, b)"),
    ]

    for finding in unsupported:
        assert formalize_finding(unit, finding) is None


def test_pop_without_formal_property_is_skipped_not_confirmed() -> None:
    finding = _make_finding("out_of_bounds", "items.pop(index)")
    result = consolidate_result(
        unit_name="remove",
        source_file="sample.py",
        finding=finding,
        formal_property=None,
        esbmc_result=None,
        esbmc_direct_result=None,
    )

    assert result.final_classification == "skipped_not_verifiable"


def test_instrumenter_imports_esbmc_stubs(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def divide(numerator: int, denominator: int) -> float:\n"
        "    return numerator / denominator\n",
        encoding="utf-8",
    )
    unit = preprocess_file(sample)[0]
    finding = _make_finding("division_by_zero", "numerator / denominator")
    normalized = normalize_findings(unit, [finding])[0]
    formal_property = formalize_finding(unit, normalized)

    assert formal_property is not None
    instrumentation = instrument_unit(unit, formal_property, tmp_path / "instrumented")

    assert "from esbmc import __ESBMC_assert, __ESBMC_assume, nondet_bool, nondet_int" in instrumentation.instrumented_source
    assert "def nondet_float() -> float:" in instrumentation.instrumented_source
    assert "denominator = nondet_int()" in instrumentation.instrumented_source
    assert "assert (denominator) != 0" in instrumentation.instrumented_source


def test_instrumenter_float_fallback_keeps_float_parameters_working(tmp_path: Path) -> None:
    sample = tmp_path / "sample_float.py"
    sample.write_text(
        "def divide(numerator: float, denominator: float) -> float:\n"
        "    return numerator / denominator\n",
        encoding="utf-8",
    )
    unit = preprocess_file(sample)[0]
    finding = _make_finding("division_by_zero", "numerator / denominator")
    normalized = normalize_findings(unit, [finding])[0]
    formal_property = formalize_finding(unit, normalized)

    assert formal_property is not None
    instrumentation = instrument_unit(unit, formal_property, tmp_path / "instrumented")

    assert "try:\n    from esbmc import nondet_float" in instrumentation.instrumented_source
    assert "denominator = nondet_float()" in instrumentation.instrumented_source


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


def test_ground_truth_loader_recurses_all_v1_subfolders() -> None:
    cases = load_ground_truth_cases(REPO_ROOT / "dataset" / "labeled" / "ground_truths")

    assert len(cases) == 70
    assert any(path.name == "clean_01.py" for path, _ in cases)
    assert all(path.exists() for path, _ in cases)


def test_frontend_benchmark_schema_uses_current_keys_with_legacy_fallback() -> None:
    html = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "metricBlock(data, 'bugs_llm_only', 'bugs')" in html
    assert "metricBlock(data, 'bugs_hybrid_pipeline', 'bugs')" in html


# ---------------------------------------------------------------------------
# Runtime harness validator — testes sem API
# ---------------------------------------------------------------------------

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
            "reproduction_harness": "",
        },
    )


def test_harness_pop_reproduces_index_error() -> None:
    source = "def f(lst: list, i: int):\n    lst.pop(i)\n"
    result = validate_harness(source, "f", "f([], 0)", "IndexError")
    assert result.status == HARNESS_REPRODUCED
    assert result.exception_type == "IndexError"


def test_harness_split_index_reproduces_index_error() -> None:
    source = 'def f(s: str) -> str:\n    return s.split(";")[1]\n'
    result = validate_harness(source, "f", 'f("nocolon")', "IndexError")
    assert result.status == HARNESS_REPRODUCED
    assert result.exception_type == "IndexError"


def test_harness_division_by_zero_reproduces() -> None:
    source = "def divide(a: int, b: int) -> int:\n    return a // b\n"
    result = validate_harness(source, "divide", "divide(5, 0)", "ZeroDivisionError")
    assert result.status == HARNESS_REPRODUCED
    assert result.exception_type == "ZeroDivisionError"


def test_harness_assertion_reproduces() -> None:
    source = (
        "def parse(ok: bool) -> str:\n"
        "    if not ok:\n"
        "        raise AssertionError('fail')\n"
        "    return 'ok'\n"
    )
    result = validate_harness(source, "parse", "parse(False)", "AssertionError")
    assert result.status == HARNESS_REPRODUCED
    assert result.exception_type == "AssertionError"


def test_harness_not_reproduced_when_no_exception() -> None:
    source = "def safe(lst: list, i: int):\n    return lst[i] if 0 <= i < len(lst) else None\n"
    result = validate_harness(source, "safe", "safe([1, 2, 3], 1)", "IndexError")
    assert result.status == HARNESS_NOT_REPRODUCED


def test_harness_wrong_exception_detected() -> None:
    source = "def f(d: dict, k: str):\n    return d[k]\n"
    result = validate_harness(source, "f", 'f({}, "missing")', "IndexError")
    # KeyError != IndexError → wrong_exception
    assert result.status == HARNESS_WRONG_EXCEPTION
    assert result.exception_type == "KeyError"


def test_harness_unsafe_import_rejected() -> None:
    result = validate_harness("def f(): pass", "f", "import os; f()", "")
    assert result.status == HARNESS_UNSAFE


def test_harness_unsafe_eval_rejected() -> None:
    result = validate_harness("def f(): pass", "f", "eval('1+1')", "")
    assert result.status == HARNESS_UNSAFE


def test_harness_unsafe_while_rejected() -> None:
    result = validate_harness("def f(): pass", "f", "while True: f()", "")
    assert result.status == HARNESS_UNSAFE


def test_harness_unsafe_open_rejected() -> None:
    result = validate_harness("def f(): pass", "f", "open('/etc/passwd')", "")
    assert result.status == HARNESS_UNSAFE


def test_harness_clean_code_not_reproduced() -> None:
    source = "def add(a: int, b: int) -> int:\n    return a + b\n"
    result = validate_harness(source, "add", "add(1, 2)", "ZeroDivisionError")
    assert result.status == HARNESS_NOT_REPRODUCED


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
