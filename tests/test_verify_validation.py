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
