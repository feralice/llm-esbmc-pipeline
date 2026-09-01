from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.scan.guards import (
    extract_guards,
    format_precondition_block,
)


def test_raise_guard_becomes_negated_precondition():
    src = (
        "def f(n_windows: int, h: int) -> int:\n"
        "    if n_windows < 2:\n"
        "        raise ValueError('need two windows')\n"
        "    return (100 - 1) // h\n"
    )
    clauses = extract_guards(src)
    assert [c.precondition for c in clauses] == ["n_windows >= 2"]
    assert clauses[0].origin == "raise"


def test_h_has_no_guard_so_no_precondition_for_it():
    src = (
        "def f(n_windows: int, h: int) -> int:\n"
        "    if n_windows < 2:\n"
        "        raise ValueError('x')\n"
        "    return (100 - 1) // h\n"
    )
    preconds = [c.precondition for c in extract_guards(src)]
    assert not any("h" in p for p in preconds)


def test_if_not_cond_raise_keeps_cond_positive():
    src = (
        "def f(x: int) -> int:\n"
        "    if not x > 0:\n"
        "        raise ValueError('x')\n"
        "    return 1 // x\n"
    )
    assert [c.precondition for c in extract_guards(src)] == ["x > 0"]


def test_bare_assert_is_a_precondition_verbatim():
    src = (
        "def f(a: int, b: int) -> int:\n"
        "    assert b != 0\n"
        "    return a // b\n"
    )
    clauses = extract_guards(src)
    assert clauses[0].precondition == "b != 0"
    assert clauses[0].origin == "assert"


def test_docstring_and_assignment_do_not_stop_the_scan():
    src = (
        "def f(a: int, b: int) -> int:\n"
        "    '''doc'''\n"
        "    scale = 2\n"
        "    if b == 0:\n"
        "        raise ZeroDivisionError\n"
        "    return a // b\n"
    )
    assert [c.precondition for c in extract_guards(src)] == ["b != 0"]


def test_guard_nested_in_a_loop_is_not_a_precondition():
    src = (
        "def f(xs: list, k: int) -> int:\n"
        "    for x in xs:\n"
        "        if k == 0:\n"
        "            raise ValueError\n"
        "    return xs[0] // k\n"
    )
    assert extract_guards(src) == []


def test_method_indentation_is_handled():
    src = (
        "    def choose(self, n: int) -> int:\n"
        "        if n < 1:\n"
        "            raise ValueError\n"
        "        return 10 // n\n"
    )
    assert [c.precondition for c in extract_guards(src)] == ["n >= 1"]


def test_format_block_when_no_guards_forbids_preconditions():
    src = "def f(h: int) -> int:\n    return 100 // h\n"
    block = format_precondition_block(src)
    assert "NONE" in block
    assert "Add NO precondition" in block


def test_format_block_lists_the_guards():
    src = (
        "def f(n: int) -> int:\n"
        "    if n < 2:\n"
        "        raise ValueError\n"
        "    return 10 // n\n"
    )
    block = format_precondition_block(src)
    assert "n >= 2" in block
    assert "add NO other precondition" in block


def test_unparseable_source_yields_no_guards():
    assert extract_guards("def f(:\n bad") == []
