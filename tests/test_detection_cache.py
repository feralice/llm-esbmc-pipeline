from pathlib import Path
from types import SimpleNamespace

from research_pipeline.llm.detection_cache import DetectionCache, make_cache
from research_pipeline.models import CodeUnit, Finding


def _unit(source: str) -> CodeUnit:
    return CodeUnit(path=Path("m.py"), name="f", qualname="f", source=source, start_line=1, end_line=2,
                    parameters=["x"], type_hints={}, operations=[], loops=[], conditionals=[], guards=[],
                    metrics={})


def _finding() -> Finding:
    return Finding(id="1", stage="llm_analysis", finding_type="suspected_bug", category="division_by_zero",
                   title="t", explanation="e", evidence=[], verifiable=True, confidence="high",
                   metadata={"expression": "10 // x", "line": 2})


def _analyzer(**overrides):
    settings = {"model": "claude-sonnet-5-5", "v2_variants": ("A1",), "include_smells": False, "v2_detection": True}
    settings.update(overrides)
    return SimpleNamespace(**settings)


def test_a_stored_detection_comes_back_unchanged(tmp_path):
    cache = DetectionCache(tmp_path, "k")
    cache.put(_unit("def f(x):\n    return 10 // x\n"), [_finding()], {"strategy": "single"})
    findings, trace = cache.get(_unit("def f(x):\n    return 10 // x\n"))
    assert findings == [_finding()] and trace == {"strategy": "single"}


def test_a_changed_function_is_a_miss(tmp_path):
    cache = DetectionCache(tmp_path, "k")
    cache.put(_unit("def f(x):\n    return 10 // x\n"), [_finding()], {})
    assert cache.get(_unit("def f(x):\n    return 11 // x\n")) is None


def test_a_different_configuration_is_a_miss(tmp_path):
    unit = _unit("def f(x):\n    return 10 // x\n")
    DetectionCache(tmp_path, "config-a").put(unit, [_finding()], {})
    assert DetectionCache(tmp_path, "config-b").get(unit) is None


def test_changing_the_variants_or_model_changes_the_key(tmp_path):
    unit = _unit("def f(x):\n    return 10 // x\n")
    first = make_cache(_analyzer(), tmp_path)
    first.put(unit, [_finding()], {})
    assert make_cache(_analyzer(), tmp_path).get(unit) is not None
    assert make_cache(_analyzer(v2_variants=("A2",)), tmp_path).get(unit) is None
    assert make_cache(_analyzer(model="claude-opus-5-5"), tmp_path).get(unit) is None


def test_a_corrupt_file_is_a_miss_not_a_crash(tmp_path):
    cache = DetectionCache(tmp_path, "k")
    unit = _unit("def f(x):\n    return 10 // x\n")
    cache.put(unit, [_finding()], {})
    cache._path(unit).write_text("{not json", encoding="utf-8")
    assert cache.get(unit) is None
