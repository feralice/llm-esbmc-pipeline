import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("label_candidates", ROOT / "scripts" / "label_candidates.py")
label = importlib.util.module_from_spec(spec)
sys.modules["label_candidates"] = label
spec.loader.exec_module(label)

BUGGY = '''def first(lines, key):
    head = lines[0]
    if key in head:
        return head[key]
    return None
'''


def test_changed_line_gives_that_statement():
    fixed = BUGGY.replace("    return head[key]", "    return head.get(key)")
    result = label.label_pair(BUGGY, fixed, "first")
    assert result["expression"] == "return head[key]"
    assert result["expression_source"] == "changed_line"
    assert result["grounded"] is True


def test_changed_if_header_gives_only_its_condition():
    fixed = BUGGY.replace("if key in head:", "if head and key in head:")
    result = label.label_pair(BUGGY, fixed, "first")
    assert result["expression"] == "key in head"


def test_pure_insertion_gives_the_next_statement():
    fixed = BUGGY.replace("    head = lines[0]", "    if not lines:\n        return None\n    head = lines[0]")
    result = label.label_pair(BUGGY, fixed, "first")
    assert result["expression"] == "head = lines[0]"
    assert result["expression_source"] == "statement_after_insertion"
    assert result["category"] == "unclassified"


def test_category_rules_follow_the_added_code():
    assert label.category_from_fix(["if value is None:", "    return 0"]) == "none_misuse"
    assert label.category_from_fix(["if count == 0:"]) == "division_by_zero"
    assert label.category_from_fix(["if len(parts) < 2:"]) == "out_of_bounds"
    assert label.category_from_fix(["if not isinstance(x, str):"]) == "type_mismatch"
    assert label.category_from_fix(["x = compute(y)"]) == "unclassified"


def test_function_missing_is_reported():
    result = label.label_pair(BUGGY, BUGGY + "\n", "nope")
    assert result["expression"] == "" and result["grounded"] is False


def test_docstring_changes_are_ignored():
    buggy = 'def f(x):\n    """Old doc."""\n    return x[0]\n'
    fixed = 'def f(x):\n    """New doc."""\n    return x[0] if x else None\n'
    assert label.label_pair(buggy, fixed, "f")["expression"] == "return x[0]"


def test_nested_function_body_gives_the_inner_statement():
    buggy = "def outer(a, b):\n    def op(x):\n        return x[b]\n    return op(a)\n"
    fixed = buggy.replace("return x[b]", "return x.get(b)")
    assert label.label_pair(buggy, fixed, "outer")["expression"] == "return x[b]"
