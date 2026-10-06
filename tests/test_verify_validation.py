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
