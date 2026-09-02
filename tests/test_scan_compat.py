from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.scan.compat import (
    VERDICT_INVALID,
    VERDICT_OK,
    VERDICT_UNSUPPORTED,
    check_harness,
    undefined_names,
)

_GOOD = """\
def div_core(a: int, b: int) -> int:
    __ESBMC_assume(b >= 0)
    __ESBMC_assume(b <= 100)
    assert b != 0
    return a // b


def main() -> None:
    div_core(nondet_int(), nondet_int())


main()
"""


def test_good_harness_passes():
    r = check_harness(_GOOD)
    assert r.ok
    assert r.verdict == VERDICT_OK
    assert r.reasons == []


def test_syntax_error_is_invalid():
    r = check_harness("def f(:\n    return 1\n")
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "does not parse" in r.reasons[0]


def test_any_import_is_invalid():
    r = check_harness("import math\n\ndef f(x: int) -> int:\n    return x\nf(nondet_int())\n")
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "imports math" in r.reasons[0]


def test_from_import_is_invalid():
    src = "from collections import deque\n\ndef f(x: int) -> int:\n    return x\nf(1)\n"
    r = check_harness(src)
    assert r.verdict == VERDICT_INVALID


def test_numpy_reference_is_unsupported():
    src = (
        "def f(n: int) -> int:\n"
        "    a = np.zeros(n)\n"
        "    return len(a)\n"
        "f(nondet_int())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_UNSUPPORTED
    assert "np" in r.reasons[0]


def test_missing_module_level_driver_is_invalid():
    src = "def f(a: int, b: int) -> int:\n    return a // b\n"
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "module-level driver" in r.reasons[0]


def test_if_name_main_counts_as_driver():
    src = (
        "def f(a: int, b: int) -> int:\n    return a // b\n\n"
        "if __name__ == '__main__':\n    f(nondet_int(), nondet_int())\n"
    )
    assert check_harness(src).ok


def test_loop_is_invalid_before_builtin_compatibility():
    src = (
        "def f(xs: list, ys: list) -> int:\n"
        "    for a, b in zip(xs, ys):\n"
        "        pass\n"
        "    return 0\n"
        "f([1, 2], [3, 4])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "loop" in r.reasons[0]


def test_enumerate_loop_is_invalid_for_scan_protocol():
    src = (
        "def f(xs: list) -> int:\n"
        "    for i, v in enumerate(xs):\n"
        "        pass\n"
        "    return 0\n"
        "f([1, 2])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "loop" in r.reasons[0]


def test_loop_free_unsupported_builtin_is_reported():
    src = (
        "def f(xs: list, ys: list) -> object:\n"
        "    return zip(xs, ys)\n"
        "f([1, 2], [3, 4])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_UNSUPPORTED
    assert "zip" in r.reasons[0]


def test_hallucinated_nondet_name_is_invalid():
    src = (
        "def f(a: int, b: int) -> int:\n"
        "    assert b != 0\n"
        "    return a // b\n"
        "f(__ESBMC_nondet_int(), __ESBMC_nondet_int())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "nondet" in r.reasons[0]


def test_real_intrinsic_names_pass():
    assert check_harness(_GOOD).ok


def test_undefined_names_ignores_intrinsics_and_builtins():
    assert undefined_names(_GOOD) == set()


def test_undefined_names_flags_unknown_symbol():
    src = "def f(x: int) -> int:\n    return x + MYSTERY_CONST\nf(nondet_int())\n"
    assert "MYSTERY_CONST" in undefined_names(src)
