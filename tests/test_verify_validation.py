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
