import ast
from pathlib import Path

from research_pipeline.verify.astutil import body_signature, find_function
from research_pipeline.verify.validation import program_for_result

SOURCE = 'def f(n):\n    """doc"""\n    return 10 // n\n'


def test_body_signature_ignores_the_docstring() -> None:
    without = find_function(ast.parse("def f(n):\n    return 10 // n\n"), "f")
    assert body_signature(find_function(ast.parse(SOURCE), "f")) == body_signature(without)


def test_program_for_result_marks_the_hypothesis_lines(tmp_path: Path) -> None:
    path = tmp_path / "p.py"
    path.write_text(SOURCE)
    program = program_for_result(path, {"function": "f", "suspect_expression": "10 // n"})
    assert program is not None and program.target_spans == ((3, 3),) and program.target_range == (1, 3)


from research_pipeline.verify.validation import target_preserved

HARNESS = SOURCE + "\n\ndef driver():\n    f(nondet_int())\n"


def test_a_harness_around_the_unchanged_function_preserves_it() -> None:
    assert target_preserved(SOURCE, HARNESS, "f")


def test_a_simplified_body_is_not_preserved() -> None:
    assert not target_preserved(SOURCE, HARNESS.replace("10 // n", "10 // (n or 1)"), "f")


def test_a_refused_library_call_replaced_by_its_stub_is_preserved() -> None:
    original = "import re\ndef f(s):\n    return re.findall('a', s)[0]\n"
    stubbed = "def f(s):\n    return _esbmc_re_findall('a', s)[0]\n"
    assert target_preserved(original, stubbed, "f")
    assert not target_preserved(original, stubbed.replace("[0]", "[1]"), "f")


def test_a_missing_target_is_not_preserved() -> None:
    assert not target_preserved(SOURCE, "def driver():\n    pass\n", "f")


import pytest

from research_pipeline.verify.validation import (INCONCLUSIVE, REACHABLE, UNREACHABLE,
                                                 read_reachability, with_unreachable_marker)

GUARDED = "def f(n):\n    if n > 10:\n        return 1 // (n - 11)\n    return 0\n"


def test_the_marker_goes_right_before_the_statement_of_the_line() -> None:
    marked = with_unreachable_marker(GUARDED, 3)
    assert marked.splitlines()[2] == "        __ESBMC_unreachable()"


def test_a_marker_that_would_break_an_elif_gives_none() -> None:
    source = "def f(n):\n    if n:\n        return 0\n    elif n > 1:\n        return 1\n    return 2\n"
    assert with_unreachable_marker(source, 4) is None


@pytest.mark.parametrize(("output", "expected"), [
    ("  FAILED [f.reachable-error.1] line 4 reachability: unreachable code reached\nVERIFICATION FAILED", REACHABLE),
    ("  PASSED [f.reachable-error.1] line 4 reachability: unreachable code reached\nVERIFICATION SUCCESSFUL", UNREACHABLE),
    ("  PASSED [f.reachable-error.1] line 4 reachability: unreachable code reached\n"
     "  FAILED [f.unwind.1] line 2 unwinding assertion loop 1\nVERIFICATION FAILED", INCONCLUSIVE),
    (None, INCONCLUSIVE),
    ("ERROR: Type inference failed", INCONCLUSIVE),
])
def test_read_reachability(output, expected) -> None:
    assert read_reachability(output) == expected


from research_pipeline.verify.validation import natural_mutation_matrix


def _r(hid: str, verdict: str) -> dict:
    return {"hypothesis": {"hypothesis_id": hid}, "verdict": verdict}


def test_natural_mutation_matrix_separates_real_bugs_from_false_alarms() -> None:
    buggy = [_r("a", "CONFIRMED"), _r("b", "CONFIRMED"), _r("c", "NOT_CONFIRMED"), _r("d", "UNSUPPORTED")]
    fixed = [_r("a", "NOT_CONFIRMED"), _r("b", "CONFIRMED"), _r("c", "CONFIRMED")]

    matrix = natural_mutation_matrix(buggy, fixed)

    assert matrix == {"only_buggy": ["a"], "both": ["b"], "only_fixed": ["c"], "neither": 1}


from research_pipeline.verify.validation import mutants

TARGET = (
    "def f(xs, i, limit):\n"
    "    if xs is None:\n"
    "        return 0\n"
    "    v = xs[i]\n"
    "    total = limit\n"
    "    return v if i < len(xs) else total\n"
)


def test_each_operator_yields_a_mutant_that_keeps_the_line_numbers() -> None:
    found = {m.operator: m for m in mutants(TARGET, "f", near_line=4)}

    assert set(found) == {"remove_guard", "assign_none", "index_plus_one", "lt_to_le"}
    assert "if xs is None" not in found["remove_guard"].source
    assert "total = None" in found["assign_none"].source
    assert "xs[i + 1]" in found["index_plus_one"].source
    assert "i <= len(xs)" in found["lt_to_le"].source
    assert all(len(m.source.splitlines()) == len(TARGET.splitlines()) for m in found.values())


def test_no_mutant_far_from_the_hypothesis() -> None:
    assert mutants(TARGET, "f", near_line=40, window=2) == []


from research_pipeline.verify.validation import validate_results


def test_validate_results_reclassifies_and_skips_results_without_program(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(SOURCE)
    program = tmp_path / "p.py"
    program.write_text(HARNESS)
    altered = tmp_path / "q.py"
    altered.write_text(HARNESS.replace("10 // n", "10 // (n or 1)"))
    base = {"function": "f", "suspect_expression": "10 // n", "file": str(tmp_path / "a.py")}
    results = [
        {"hypothesis": {**base, "hypothesis_id": "1"}, "verdict": "NOT_CONFIRMED", "program_path": str(program),
         "attempts": [{}]},
        {"hypothesis": {**base, "hypothesis_id": "2"}, "verdict": "CONFIRMED", "program_path": str(altered),
         "attempts": [{}]},
        {"hypothesis": {**base, "hypothesis_id": "3"}, "verdict": "GROUNDING_FAILED", "attempts": []},
    ]

    report = validate_results(results, sources=src, esbmc="esbmc", timeout_seconds=5, work_dir=tmp_path / "w",
                              reach=lambda *a, **k: "unreachable")

    rows = {r["hypothesis_id"]: r for r in report["rows"]}
    assert rows["1"]["validated_verdict"] == "NOT_CONFIRMED_VACUOUS"
    assert rows["2"]["validated_verdict"] == "TARGET_ALTERED"
    assert rows["3"]["checked"] is False
    assert report["summary"]["vacuous"] == 1 and report["summary"]["altered"] == 1


def _row(tmp_path: Path, verdict: str, program_text: str = HARNESS, **extra) -> dict:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / "a.py").write_text(SOURCE)
    program = tmp_path / f"{verdict}_a0.py"
    program.write_text(program_text)
    hypothesis = {"function": "f", "suspect_expression": "10 // n", "file": str(tmp_path / "a.py"),
                  "hypothesis_id": verdict}
    return {"hypothesis": hypothesis, "verdict": verdict, "program_path": str(program), "attempts": [{}], **extra}


def _validate(tmp_path: Path, results: list[dict], **kwargs) -> dict:
    return validate_results(results, sources=tmp_path / "src", esbmc="esbmc", timeout_seconds=5,
                            work_dir=tmp_path / "w", reach=lambda *a, **k: "reachable", **kwargs)


def test_a_verdict_without_an_esbmc_reading_is_not_checked(tmp_path: Path) -> None:
    # SPEC_FAILED can keep the program_path of an earlier, rewritten attempt.
    report = _validate(tmp_path, [_row(tmp_path, "SPEC_FAILED")])
    assert report["rows"][0]["checked"] is False and report["summary"]["with_program"] == 0


def test_a_catalogue_rewrite_without_its_replay_program_is_not_called_altered(tmp_path: Path) -> None:
    rewritten = HARNESS.replace("10 // n", "10 // int(n)")
    report = _validate(tmp_path, [_row(tmp_path, "NOT_CONFIRMED", rewritten, transforms=["compat_percent"])])
    row = report["rows"][0]
    assert row["preserved"] is None and row["validated_verdict"] == "NOT_CONFIRMED"
    assert report["summary"]["altered"] == 0


def test_mutants_run_only_on_safe_verdicts(tmp_path: Path) -> None:
    mutable = HARNESS.replace("    return 10 // n\n", "    k = n\n    return 10 // n\n")
    calls = []
    _validate(tmp_path, [_row(tmp_path, "NOT_CONFIRMED", mutable)], with_mutants=True,
              run=lambda m, *a, **k: calls.append(m) or "killed")
    assert calls
    report = _validate(tmp_path, [_row(tmp_path, "CONFIRMED", mutable)], with_mutants=True,
                       run=lambda *a, **k: pytest.fail("a confirmed program already violates: mutants say nothing"))
    assert "mutants" not in report["rows"][0]


def test_an_error_in_one_row_is_recorded_and_the_rest_still_run(tmp_path: Path) -> None:
    broken = _row(tmp_path, "NOT_CONFIRMED")
    broken["program_path"] = str(tmp_path / "missing.py")
    good = _row(tmp_path, "ESBMC_MISSED")
    report = _validate(tmp_path, [broken, good])
    assert "error" in report["rows"][0] and report["rows"][1]["checked"] is True
