"""Integration tests for preparing real source methods for ESBMC."""

from pathlib import Path

from research_pipeline.scan.prepared_body import prepare_real_body
from research_pipeline.scan.pipeline import (
    ScanCandidate, run_pipeline_scan,
)
from research_pipeline.scan.synth import SynthResult
from research_pipeline.verification.esbmc_runner import run_esbmc_direct


def test_empty_nested_list_reaches_real_division(tmp_path: Path) -> None:
    source = (
        "class Search:\n"
        "    def ratio(self, groups, parts):\n"
        "        for i in range(len(groups)):\n"
        "            n = len(parts[i])\n"
        "            return float(0) / float(n)\n"
    )
    prepared = prepare_real_body(source, "Search.ratio", "float(0) / float(n)")
    assert prepared is not None
    path = tmp_path / "probe.py"
    path.write_text(prepared, encoding="utf-8")
    result = run_esbmc_direct(path, bound=6, timeout_seconds=20, multi_property=False)
    assert result.status == "violation_found"
    assert "ZeroDivisionError" in result.summary or "ZeroDivisionError" in str(result.details)


def test_method_with_constructor_is_not_silently_prepared() -> None:
    source = (
        "class Search:\n"
        "    def __init__(self, service):\n"
        "        self.service = service\n"
        "    def ratio(self, groups, parts):\n"
        "        for i in range(len(groups)):\n"
        "            n = len(parts[i])\n"
        "            return float(0) / float(n)\n"
    )
    assert prepare_real_body(source, "Search.ratio", "float(0) / float(n)") is None


def test_real_dz02_body_reaches_its_original_division(tmp_path: Path) -> None:
    original = (Path(__file__).resolve().parents[1] /
                "dataset/v2_real_world/detection/dz_real_02.py").read_text(encoding="utf-8")
    prepared = prepare_real_body(
        original, "ExactLanguageSearch.choose_best_split",
        "float(not_parsed)/float(num_substrings)",
    )
    assert prepared is not None
    path = tmp_path / "dz02.py"
    path.write_text(prepared, encoding="utf-8")
    result = run_esbmc_direct(path, bound=6, timeout_seconds=20, multi_property=False)
    assert result.status == "violation_found"
    assert result.details["property_kind"] == "uncaught exception: ZeroDivisionError"


def test_unknown_suspect_expression_is_refused() -> None:
    source = "class Search:\n    def ratio(self, groups, parts):\n        for i in range(len(groups)):\n            n = len(parts[i])\n            return 1 / n\n"
    assert prepare_real_body(source, "Search.ratio", "2 / n") is None


def test_suspect_outside_validated_loop_is_refused() -> None:
    source = (
        "class Search:\n"
        "    def ratio(self, groups, parts):\n"
        "        n = 0\n"
        "        prior = 1 / n\n"
        "        for i in range(len(groups)):\n"
        "            n = len(parts[i])\n"
        "            return 2 / n\n"
    )
    assert prepare_real_body(source, "Search.ratio", "1 / n") is None


def test_external_function_call_is_refused() -> None:
    source = (
        "class Search:\n"
        "    def ratio(self, groups, parts):\n"
        "        for i in range(len(groups)):\n"
        "            n = len(parts[i])\n"
        "            external_hook()\n"
        "            return 1 / n\n"
    )
    assert prepare_real_body(source, "Search.ratio", "1 / n") is None


class _RecordingSynthesizer:
    model = "recording"

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, *args, **kwargs) -> SynthResult:
        self.calls += 1
        return SynthResult("", "", self.model, {})


def test_scan_does_not_promote_shape_specific_preparation(tmp_path: Path) -> None:
    source = tmp_path / "general_case.py"
    source.write_text(
        "class General:\n"
        "    def ratio(self, groups, parts):\n"
        "        for i in range(len(groups)):\n"
        "            count = len(parts[i])\n"
        "            return float(1) / float(count)\n",
        encoding="utf-8",
    )
    candidate = ScanCandidate(
        file=str(source), function="General.ratio",
        category="division_by_zero", expression="float(1) / float(count)",
    )
    synthesizer = _RecordingSynthesizer()
    result = run_pipeline_scan(
        [candidate], synthesizer=synthesizer, output_dir=tmp_path / "out",
        use_driver=False, synth_retries=0, loop_fallback=False,
    )[0]
    assert synthesizer.calls == 1
    assert result.compat_verdict != "prepared_real_body"
    assert result.harness_tier != "real_body"
