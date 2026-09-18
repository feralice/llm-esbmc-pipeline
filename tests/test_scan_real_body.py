"""Tests for the deterministic real-body driver tier (`_try_real_body_driver`).

This tier verifies the original CodeUnit body directly -- no LLM call, no
rewritten model -- for functions whose parameters are scalars or bounded
list[T]. It sits before the LLM driver/scalar tiers in `_run_one`'s cascade,
so a case it can settle should never reach the synthesizer.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research_pipeline.models import CodeUnit, ESBMCDirectResult, ESBMCResult
from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan.pipeline import (
    CONFIRMED_DRIVER,
    SAFE_DRIVER,
    ScanCandidate,
    _annotation_shape,
    _real_body_parameters,
    run_pipeline_scan,
)
from research_pipeline.scan.synth import SynthResult


class _RefusingSynthesizer:
    """Fails the test if the LLM tier is ever reached."""

    model = "should-not-be-called"

    def synthesize(self, *args, **kwargs):
        raise AssertionError("LLM synth should not run when the real-body tier applies")


class _SpySynthesizer:
    def __init__(self, harness: str = ""):
        self._harness = harness
        self.model = "spy"
        self.called = False

    def synthesize(self, *args, **kwargs) -> SynthResult:
        self.called = True
        return SynthResult(self._harness, self._harness, self.model, {})


def _esbmc_direct(status: str) -> ESBMCDirectResult:
    return ESBMCDirectResult(
        source_file="x.py", status=status, command=["esbmc"], returncode=0, summary=status,
    )


@pytest.fixture(autouse=True)
def _native_skipped(monkeypatch):
    monkeypatch.setattr(
        scan_pipeline,
        "run_esbmc_on_function",
        lambda *a, **k: ESBMCResult(
            finding_id="n", status="skipped", command=["esbmc"], returncode=0, summary="skipped"
        ),
    )


def _candidate(tmp_path: Path, source: str, function: str, category: str = "out_of_bounds") -> ScanCandidate:
    f = tmp_path / "mod.py"
    f.write_text(source, encoding="utf-8")
    return ScanCandidate(file=str(f), function=function, category=category)


def _unit(source: str, name: str, parameters: list[str]) -> CodeUnit:
    return CodeUnit(
        path=Path("m.py"), name=name, qualname=name, source=source,
        start_line=1, end_line=source.count("\n") + 1, parameters=parameters,
        type_hints={}, operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


# --- _annotation_shape ------------------------------------------------------


def _shape(annotation_src: str):
    tree = ast.parse(f"x: {annotation_src}\n")
    return _annotation_shape(tree.body[0].annotation)


def test_scalar_shapes_accepted():
    assert _shape("int") == ("int",)
    assert _shape("bool") == ("bool",)
    assert _shape("str") == ("str",)


def test_float_scalar_accepted_but_float_list_refused():
    # A scalar float gets the NaN-exclusion assume; a float list has no
    # per-element hook to exclude NaN from, so it is refused rather than
    # modelled unsoundly.
    assert _shape("float") == ("float",)
    assert _shape("list[float]") is None


def test_list_of_supported_elements_accepted():
    assert _shape("list[int]") == ("list", "int")
    assert _shape("list[str]") == ("list", "str")
    assert _shape("list[bool]") == ("list", "bool")


def test_dict_not_supported_yet():
    # nondet_dict timed out at 60s in manual testing (2026-09-12); accepting
    # the shape would burn the timeout budget on every candidate before
    # falling through, which is worse than refusing outright.
    assert _shape("dict[str, int]") is None
    assert _shape("dict[int, int]") is None


def test_custom_class_refused():
    assert _shape("Box") is None
    assert _shape("list[Box]") is None


# --- _real_body_parameters: local-variable regression -----------------------
#
# A `for` target or an intermediate result used to be flagged as a "free
# name" alongside genuinely undefined globals, because only PARAMETERS were
# added to the allowed-names set. That refused every function with more than
# a bare `return expr` body -- scalar or container alike.


def test_local_variable_is_not_mistaken_for_a_free_name():
    source = (
        "def total(values: list[int]) -> int:\n"
        "    result: int = 0\n"
        "    for v in values:\n"
        "        result = result + v\n"
        "    return result\n"
    )
    unit = _unit(source, "total", ["values"])
    assert _real_body_parameters(unit) == [("values", ("list", "int"))]


def test_reference_to_undefined_global_is_still_refused():
    source = "def f(n: int) -> int:\n    return n + SOME_GLOBAL\n"
    unit = _unit(source, "f", ["n"])
    assert _real_body_parameters(unit) is None


def test_unsupported_param_type_refused():
    source = "class Box:\n    pass\ndef unwrap(b: Box) -> int:\n    return 1\n"
    unit = _unit(source, "unwrap", ["b"])
    assert _real_body_parameters(unit) is None


# --- _try_real_body_driver end to end, via run_pipeline_scan ----------------


def test_list_param_violation_confirmed_without_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", lambda *a, **k: _esbmc_direct("violation_found"))
    source = "def get_at(values: list[int], index: int) -> int:\n    return values[index]\n"
    result = run_pipeline_scan(
        [_candidate(tmp_path, source, "get_at")],
        synthesizer=_RefusingSynthesizer(),
        output_dir=tmp_path / "out",
    )[0]
    assert result.classification == CONFIRMED_DRIVER
    assert result.compat_verdict == "real_body_driver"
    assert "nondet_list" in result.harness
    assert "def get_at(values: list[int], index: int) -> int:" in result.harness


def test_list_param_no_violation_is_safe_without_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", lambda *a, **k: _esbmc_direct("no_violation_found"))
    source = "def get_at(values: list[int], index: int) -> int:\n    return values[index]\n"
    result = run_pipeline_scan(
        [_candidate(tmp_path, source, "get_at")],
        synthesizer=_RefusingSynthesizer(),
        output_dir=tmp_path / "out",
        use_ablation=False,
    )[0]
    assert result.classification == SAFE_DRIVER


def test_dict_param_falls_through_to_llm_tier_at_zero_esbmc_cost(tmp_path, monkeypatch):
    esbmc_calls = 0

    def _direct(*a, **k):
        nonlocal esbmc_calls
        esbmc_calls += 1
        return _esbmc_direct("violation_found")

    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", _direct)
    source = "def lookup(prices: dict[str, int], key: str) -> int:\n    return prices[key]\n"
    spy = _SpySynthesizer(harness="")
    run_pipeline_scan(
        [_candidate(tmp_path, source, "lookup")],
        synthesizer=spy,
        output_dir=tmp_path / "out",
        synth_retries=0,
        use_driver=False,
    )
    assert spy.called
    assert esbmc_calls == 0  # dict is refused before any ESBMC invocation
