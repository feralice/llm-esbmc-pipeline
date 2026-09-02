from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.scan.ablation import (
    FAILED,
    ablate,
    build_variants,
)

_HARNESS = """\
def core(h: int, n: int) -> int:
    assert h != 0
    return (n - 1) // h


def main() -> None:
    h: int = nondet_int()
    n: int = nondet_int()
    __ESBMC_assume(h >= 1)
    __ESBMC_assume(abs(h) <= 1000)
    __ESBMC_assume(abs(n) <= 1000)
    core(h, n)


main()
"""


def test_build_variants_one_per_assume():
    variants = build_variants(_HARNESS)
    assert [v.assumption for v in variants] == ["h >= 1", "abs(h) <= 1000", "abs(n) <= 1000"]


def test_build_variants_comments_out_the_line():
    variants = build_variants(_HARNESS)
    first = next(v for v in variants if v.assumption == "h >= 1")
    lines = first.source.splitlines()
    assumed = next(ln for ln in lines if "__ESBMC_assume(h >= 1)" in ln)
    assert assumed.lstrip().startswith("# [ablated] ")
    # the other assumes are untouched
    assert "    __ESBMC_assume(abs(h) <= 1000)" in first.source


def test_nan_guard_is_not_ablated():
    src = (
        "def core(x: float) -> float:\n"
        "    return x + 1.0\n\n"
        "def main() -> None:\n"
        "    x: float = nondet_float()\n"
        "    __ESBMC_assume(x == x)\n"
        "    __ESBMC_assume(abs(x) <= 1000)\n"
        "    core(x)\n\n"
        "main()\n"
    )
    assert [v.assumption for v in build_variants(src)] == ["abs(x) <= 1000"]


def test_ablate_flags_the_masking_assumption():
    # `h >= 1` is the invented precondition; dropping it exposes h == 0.
    def fake_run(source: str) -> str:
        active = [
            ln for ln in source.splitlines()
            if "__ESBMC_assume" in ln and not ln.lstrip().startswith("# [ablated]")
        ]
        reaches_zero = not any("h >= 1" in ln for ln in active)
        return FAILED if reaches_zero else "SUCCESSFUL"

    report = ablate(_HARNESS, fake_run)
    assert report.over_restricted
    assert report.masking_assumptions == ["h >= 1"]
    assert report.per_assumption["abs(n) <= 1000"] == "SUCCESSFUL"


def test_ablate_clean_when_no_assume_masks():
    report = ablate(_HARNESS, lambda _src: "SUCCESSFUL")
    assert not report.over_restricted
    assert report.masking_assumptions == []


def test_ablate_handles_multiline_assume():
    src = (
        "def core(a: int, b: int) -> int:\n"
        "    return a // b\n\n"
        "def main() -> None:\n"
        "    a: int = nondet_int()\n"
        "    b: int = nondet_int()\n"
        "    __ESBMC_assume(\n"
        "        b >= 1\n"
        "    )\n"
        "    core(a, b)\n\n"
        "main()\n"
    )
    variants = build_variants(src)
    assert len(variants) == 1
    assert variants[0].source.count("# [ablated] ") == 3


def test_syntax_error_yields_no_variants():
    assert build_variants("def f(:\n bad") == []
