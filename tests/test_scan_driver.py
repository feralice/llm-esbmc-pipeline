from __future__ import annotations

from pathlib import Path

import pytest

from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan.driver_check import (
    VERDICT_INVALID,
    VERDICT_UNSUPPORTED,
    check_driver_harness,
)
from research_pipeline.scan.pipeline import (
    CONFIRMED_DRIVER,
    CONFIRMED_UNVERIFIED,
    OVER_RESTRICTED,
    SAFE_DRIVER,
    ScanCandidate,
    run_pipeline_scan,
)
from research_pipeline.scan.synth import STYLE_DRIVER, SynthResult

_REAL = "def cdiv(a, b):\n    return -(a // -b)\n"
_EXPR = "-(a // -b)"

_SLICE_HARNESS = (
    "def slice_model(a: int, b: int) -> int:\n"
    "    return -(a // -b)\n"
    "def main() -> None:\n"
    "    a = nondet_int()\n"
    "    b = nondet_int()\n"
    "    __ESBMC_assume(0 <= a)\n"
    "    __ESBMC_assume(a <= 1024)\n"
    "    __ESBMC_assume(1 <= b)\n"
    "    __ESBMC_assume(b <= 1024)\n"
    "    result = slice_model(a, b)\n"
    "    assert result * b >= a\n"
    "main()\n"
)

_DIFFERENTIAL_SLICE_HARNESS = (
    "def slice_model(a: int, b: int) -> int:\n"
    "    return -(a // -b)\n"
    "def expected_model(a: int, b: int) -> int:\n"
    "    return (a + b - 1) // b\n"
    "def main() -> None:\n"
    "    a = nondet_int()\n"
    "    b = nondet_int()\n"
    "    __ESBMC_assume(0 <= a)\n"
    "    __ESBMC_assume(a <= 1024)\n"
    "    __ESBMC_assume(1 <= b)\n"
    "    __ESBMC_assume(b <= 1024)\n"
    "    result = slice_model(a, b)\n"
    "    expected = expected_model(a, b)\n"
    "    assert result == expected\n"
    "main()\n"
)


def _check(src, **kw):
    kw.setdefault("real_source", _REAL)
    kw.setdefault("function_name", "cdiv")
    kw.setdefault("expression", _EXPR)
    return check_driver_harness(src, **kw)


# --- check_driver_harness -------------------------------------------------


def test_slice_harness_is_ok():
    assert _check(_SLICE_HARNESS).ok


def test_reimplemented_arithmetic_is_rejected():
    # divisor rebuilt without the real operator skeleton
    rewritten = _SLICE_HARNESS.replace("-(a // -b)", "(a + b - 1) // b")
    res = _check(rewritten)
    assert not res.ok and res.verdict == VERDICT_INVALID


def test_collapsed_divisor_into_single_nondet_is_rejected():
    # `a // -b` replaced by a bare nondet divisor -> the `//` / unary-minus the
    # bug lives in is gone
    collapsed = _SLICE_HARNESS.replace(
        "def slice_model(a: int, b: int) -> int:\n    return -(a // -b)\n",
        "def slice_model(q: int) -> int:\n    return q\n",
    ).replace("slice_model(a, b)", "slice_model(nondet_int())")
    res = _check(collapsed)
    assert not res.ok


def test_prose_expression_falls_back_to_line_overlap():
    res = _check(_SLICE_HARNESS, expression="ceiling division of a by b")
    assert res.ok  # `return -(a // -b)` survives verbatim


def test_prose_expression_with_no_real_line_is_rejected():
    junk = _SLICE_HARNESS.replace("    return -(a // -b)\n", "    return a + b\n")
    res = _check(junk, expression="ceiling division of a by b")
    assert not res.ok


def test_import_is_rejected():
    res = _check("import os\n" + _SLICE_HARNESS)
    assert not res.ok and res.verdict == VERDICT_INVALID


def test_cover_is_rejected():
    withcover = _SLICE_HARNESS.replace(
        "    result = slice_model(a, b)\n", "    __ESBMC_cover(b == 0)\n    result = slice_model(a, b)\n"
    )
    res = _check(withcover)
    assert not res.ok and res.verdict == VERDICT_INVALID


def test_shadowing_an_intrinsic_is_rejected():
    res = _check("def nondet_int() -> int:\n    return 0\n" + _SLICE_HARNESS)
    assert not res.ok and "intrinsic" in " ".join(res.reasons)


def test_annotated_result_binding_counts_as_live():
    ann = _SLICE_HARNESS.replace(
        "    result = slice_model(a, b)\n", "    result: int = slice_model(a, b)\n"
    )
    assert _check(ann).ok


def test_discarded_result_is_rejected():
    dead = _SLICE_HARNESS.replace(
        "    result = slice_model(a, b)\n    assert result * b >= a\n",
        "    slice_model(a, b)\n    assert a >= 0\n",
    )
    assert not _check(dead).ok


def test_empty_harness_is_rejected():
    res = _check("")
    assert not res.ok and res.verdict == VERDICT_INVALID


def test_numpy_leak_is_unsupported():
    leak = _SLICE_HARNESS.replace("    result = slice_model(a, b)\n", "    result = np.foo(a, b)\n")
    res = _check(leak)
    assert not res.ok and res.verdict == VERDICT_UNSUPPORTED


def test_no_module_driver_is_rejected():
    nodriver = _SLICE_HARNESS.replace("main()\n", "")
    assert not _check(nodriver).ok


def test_tautological_isinstance_is_rejected():
    # the false-negative shape codex produced for av_real_01: stand-in typed as
    # the very type isinstance checks
    taut = (
        "def slice_model(param_value: bool) -> bool:\n"
        "    param = param_value\n"
        "    assert isinstance(param, bool)\n"
        "    return param\n"
        "def main() -> None:\n"
        "    param_value = nondet_bool()\n"
        "    result = slice_model(param_value)\n"
        "    assert isinstance(result, bool)\n"
        "main()\n"
    )
    res = _check(taut, expression="assert isinstance(param, bool)")
    assert not res.ok and "always true" in " ".join(res.reasons)


def test_differently_typed_stand_in_isinstance_is_ok():
    ok = (
        "def slice_model(kind: int) -> int:\n"
        "    # real: params.get(param); assert isinstance(param, bool)\n"
        "    is_bool: bool = kind == 0\n"
        "    assert is_bool\n"
        "    return kind\n"
        "def main() -> None:\n"
        "    kind = nondet_int()\n"
        "    __ESBMC_assume(0 <= kind)\n"
        "    __ESBMC_assume(kind <= 2)\n"
        "    result = slice_model(kind)\n"
        "    assert result >= 0\n"
        "main()\n"
    )
    assert _check(ok, expression="assert isinstance(param, bool)").ok


# --- pipeline _try_driver ------------------------------------------------


class _DriverSynth:
    def __init__(self, harness: str):
        self._harness = harness
        self.model = "driver-model"
        self.seen_styles: list[str] = []

    def synthesize(self, unit, finding, *, use_guards: bool = True, style: str = "scalar", **kw):
        self.seen_styles.append(style)
        return SynthResult(self._harness, self._harness, self.model, {"total_tokens": 10})


def _esbmc(status: str):
    from research_pipeline.models import ESBMCDirectResult

    return ESBMCDirectResult(
        source_file="x.py", status=status, command=["esbmc"], returncode=0, summary=status
    )


@pytest.fixture(autouse=True)
def _native_skipped(monkeypatch):
    from research_pipeline.models import ESBMCResult

    monkeypatch.setattr(
        scan_pipeline,
        "run_esbmc_on_function",
        lambda *a, **k: ESBMCResult(finding_id="n", status="skipped", command=["esbmc"], returncode=0, summary="skipped"),
    )


def _candidate(tmp_path: Path, category: str = "assertion_violation") -> ScanCandidate:
    f = tmp_path / "mod.py"
    f.write_text(_REAL, encoding="utf-8")
    return ScanCandidate(file=str(f), function="cdiv", category=category, expression=_EXPR)


def _run(tmp_path, monkeypatch, esbmc_fn, *, category="assertion_violation", harness=_SLICE_HARNESS):
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", esbmc_fn)
    synth = _DriverSynth(harness)
    result = run_pipeline_scan(
        [_candidate(tmp_path, category)],
        synthesizer=synth,
        output_dir=tmp_path / "out",
        synth_retries=0,
    )[0]
    return result, synth


def test_driver_violation_confirms(tmp_path, monkeypatch):
    result, synth = _run(
        tmp_path, monkeypatch, lambda *a, **k: _esbmc("violation_found"), category="division_by_zero"
    )
    assert result.classification == CONFIRMED_DRIVER
    assert result.compat_verdict == "driver"
    assert result.driver_note == "conclusive"
    assert synth.seen_styles == [STYLE_DRIVER]


def test_driver_violation_in_outcome_category_is_demoted(tmp_path, monkeypatch):
    result, _ = _run(tmp_path, monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    assert result.classification == CONFIRMED_UNVERIFIED


def test_differential_driver_violation_in_outcome_category_confirms(tmp_path, monkeypatch):
    result, _ = _run(
        tmp_path,
        monkeypatch,
        lambda *a, **k: _esbmc("violation_found"),
        harness=_DIFFERENTIAL_SLICE_HARNESS,
    )
    assert result.classification == CONFIRMED_DRIVER
    assert result.compat_reasons == []


def test_driver_no_violation_is_safe(tmp_path, monkeypatch):
    result, _ = _run(
        tmp_path, monkeypatch, lambda *a, **k: _esbmc("no_violation_found"), category="division_by_zero"
    )
    assert result.classification == SAFE_DRIVER


def test_driver_ablation_flips_to_over_restricted(tmp_path, monkeypatch):
    def flips(file_path, **kw):
        text = Path(file_path).read_text(encoding="utf-8")
        return _esbmc("violation_found" if "# [ablated] " in text else "no_violation_found")

    result, _ = _run(tmp_path, monkeypatch, flips, category="division_by_zero")
    assert result.classification == OVER_RESTRICTED
    assert result.masking_assumptions


def test_rejected_driver_harness_falls_through_to_scalar(tmp_path, monkeypatch):
    result, synth = _run(
        tmp_path, monkeypatch, lambda *a, **k: _esbmc("violation_found"), harness=""
    )
    assert result.classification != CONFIRMED_DRIVER
    assert STYLE_DRIVER in synth.seen_styles       # driver attempted first
    assert result.driver_note.startswith("invalid")


def test_divergent_body_note_records_invalid(tmp_path, monkeypatch):
    rewritten = _SLICE_HARNESS.replace("-(a // -b)", "(a + b - 1) // b")
    result, _ = _run(
        tmp_path, monkeypatch, lambda *a, **k: _esbmc("violation_found"),
        category="division_by_zero", harness=rewritten,
    )
    assert result.driver_note.startswith("invalid x")
